"""Post-hoc re-elicitation from archived personal survey inputs, one request per answer."""
import argparse
import hashlib
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from context_codec import unpack
from run_batch import spent
from sim import API, dump, load_api_key
from survey_measurement import VERSION, SYSTEM, ITEMS, SOURCES, payload, validate, summarize, effective


def targets(root):
    for folder in sorted(Path(root).glob('*/simulation')):
        result_path = folder/'result.json'
        if result_path.exists():
            result = json.loads(result_path.read_text(encoding='utf-8'))
            if result.get('synthetic'): continue
            surveys = result['surveys']
            completed = result['completed_rounds']
        else:
            saved_path = folder/'failed_state.json'
            if not saved_path.exists(): saved_path = folder/'checkpoint.json'
            if not saved_path.exists(): continue
            saved = json.loads(saved_path.read_text(encoding='utf-8'))
            if saved.get('mock'): continue
            surveys = saved['state']['surveys']
            completed = -1
        existing = {(x['round'], x['agent']) for x in surveys}
        cfg = json.loads((folder/'config.json').read_text(encoding='utf-8'))
        seen = set()
        for line in (folder/'calls.jsonl').read_text(encoding='utf-8').splitlines():
            try: call = json.loads(line)
            except json.JSONDecodeError: continue
            if call['kind'] != 'survey_existence': continue
            observation = unpack(json.loads(call['messages'][1]['content']))
            t, aid = observation['round'], observation['self']['id']
            if (t, aid) not in existing or (t, aid) in seen: continue
            seen.add((t, aid))
            yield {'source_run': folder.parent.name, 'round': t, 'agent': aid,
                'source_request_key': call['request_key'], 'source_request_hash': call['request_hash'],
                'source_status': 'complete' if completed == cfg['rounds'] else 'incomplete',
                'model': call['requested_model'], 'observation': observation}


def total_spent(roots):
    folders = {p.parent.resolve() for root in roots for p in Path(root).rglob('config.json')}
    return sum(spent(p) for p in folders)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', default='runs/core_campaign_v6_50rounds_20261007')
    parser.add_argument('--output', default='runs/survey_refill_v3_keyed_20261007')
    parser.add_argument('--api-key-file', default='../api_key')
    parser.add_argument('--mock', action='store_true')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--reuse-from', help='Reuse valid answers with identical items and source observation hashes')
    args = parser.parse_args()
    output = Path(args.output); output.mkdir(parents=True, exist_ok=True)
    candidates = list(targets(args.source))
    candidates.sort(key=lambda x: (x['round'], x['source_run'], x['agent']))
    if args.limit is not None: candidates = candidates[:args.limit]
    roots = json.loads(Path('configs/core_pilot_v6_50rounds_20261007/prior_cost_roots.json').read_text(encoding='utf-8'))['roots']
    roots = list(dict.fromkeys(roots + [args.source]))
    if args.reuse_from: roots.append(args.reuse_from)
    # Include earlier survey-format trials in every future/resumed ledger,
    # independently of whether their answers are explicitly reused.
    for earlier in Path('runs').glob('survey_refill_v3*'):
        if earlier.resolve() != output.resolve() and (earlier/'api_accounting.json').exists():
            roots.append(str(earlier))
    for pilot in Path('runs').glob('gpt_oss*_pilot_*'):
        if list(pilot.rglob('api_accounting.json')):
            roots.append(str(pilot))
    roots = list(dict.fromkeys(roots))
    prior = total_spent(roots)
    local_cap = min(.18, max(0, 10-prior))
    cfg = {'models': sorted(set(x['model'] for x in candidates)), 'max_calls': 600,
           'max_estimated_cost_usd': local_cap, 'max_output_tokens': 1800, 'temperature': .5,
           'structured_outputs': True, 'context_encoding': 'compact_v1', 'network_retries': 0}
    fingerprint = hashlib.sha256(json.dumps([VERSION, SYSTEM, ITEMS, cfg, args.mock,
        [(x['source_run'], x['source_request_hash']) for x in candidates]], sort_keys=True).encode()).hexdigest()
    manifest_path = output/'manifest.json'
    if manifest_path.exists():
        old = json.loads(manifest_path.read_text(encoding='utf-8'))
        if old['fingerprint'] != fingerprint: raise ValueError('Refill inputs/config changed; choose another output')
    dump(manifest_path, {'fingerprint': fingerprint, 'protocol': VERSION, 'synthetic': args.mock,
        'prior_cost_usd': prior, 'local_cost_cap_usd': local_cap, 'global_budget_usd': 10,
        'source_roots': roots, 'item_definitions': ITEMS, 'item_sources': SOURCES,
        'interpretation': 'Post-hoc re-elicitation from original visible inputs; not contemporaneous responses',
        'scope': 'Completed respondent surveys in source result files, including explicitly marked incomplete runs'})
    dump(output/'config.json', cfg)
    if not args.mock: load_api_key(args.api_key_file)
    api = API(cfg, output, args.mock)
    accounting = output/'api_accounting.json'
    if accounting.exists():
        saved = json.loads(accounting.read_text(encoding='utf-8'))
        api.calls = saved['calls']
        # A killed/incomplete transport may have been billed. Keep its entire
        # reservation as uncertain cost instead of silently refunding it.
        api.cost = saved['cost_usd'] + saved.get('reserved_usd', 0)
        if saved.get('reserved_usd', 0):
            dump(output/'interrupted_reservation.json', {'conservative_cost_usd': saved['reserved_usd'],
                'note': 'Interrupted request charge unknown; retained in local and global budget'})
        api.accounting()
    result_path = output/'result.json'
    result = json.loads(result_path.read_text(encoding='utf-8')) if result_path.exists() else {
        'synthetic': args.mock, 'protocol': VERSION, 'surveys': [], 'failures': []}
    if args.reuse_from and not result['surveys']:
        source = Path(args.reuse_from)
        previous = json.loads((source/'manifest.json').read_text(encoding='utf-8'))
        if previous['synthetic'] != args.mock or previous['protocol'] != VERSION or json.dumps(previous['item_definitions'], ensure_ascii=False) != json.dumps(ITEMS, ensure_ascii=False):
            raise ValueError('Previous questionnaire semantics/backend differ')
        lookup = {(x['source_run'], x['round'], x['agent']): x for x in candidates}
        old = json.loads((source/'result.json').read_text(encoding='utf-8'))
        for answer in old['surveys']:
            item = lookup[(answer['source_run'], answer['round'], answer['agent'])]
            if answer['source_request_hash'] != item['source_request_hash']:
                raise ValueError('Previous personal observation hash differs')
            validate(answer['responses'], payload(item['observation']))
            answer['imported_from'] = str(source.resolve())
            answer['original_response_format'] = 'array_v1'
            for field, module in [('groups', 'identity'), ('arrangements', 'arrangement')]:
                for obj in answer['responses'][field]:
                    if isinstance(obj['scores'], list):
                        obj['scores'] = dict(zip([x[0] for x in ITEMS[module]], obj['scores']))
            result['surveys'].append(answer)
        dump(output/'import_audit.json', {'source': str(source.resolve()), 'answers_reused': len(result['surveys']),
            'historical_failed_attempts': len(old['failures']),
            'note': 'Only syntax normalized; no rating changes; historical calls/costs retained in source and budget.'})
    done = {x['refill_key'] for x in result['surveys'] + result['failures']}
    # A nonmember's identity module is inapplicable, rather than grounds to
    # discard all their other answers. Recover cached raw answers without a call.
    lookup = {(x['source_run'], x['round'], x['agent']): x for x in candidates}
    have = {(x['source_run'], x['round'], x['agent']) for x in result['surveys']}
    for rejected in result['failures']:
        identity = (rejected['source_run'], rejected['round'], rejected['agent'])
        cached = api.cached.get(rejected['refill_key'])
        if identity in have or not cached or 'Identity scores require own membership' not in rejected['error']: continue
        response = json.loads(cached['response'])
        request = payload(lookup[identity]['observation'])
        try: flags = validate(response, request)
        except ValueError: continue  # Other invalid fields still require re-elicitation.
        result['surveys'].append({**{k: v for k, v in rejected.items() if k != 'error'},
            'responses': response, 'effective_responses': effective(response, request),
            'quality_flags': flags, 'synthetic': args.mock, 'post_hoc': True,
            'recovered_without_new_call': True, 'schema_revision': 5})
        have.add(identity)
    for answer in result['surveys']:
        request = payload(lookup[(answer['source_run'], answer['round'], answer['agent'])]['observation'])
        answer['effective_responses'] = effective(answer['responses'], request)
    answered = {(x['source_run'], x['round'], x['agent']) for x in result['surveys']}
    schema_revision = 5
    dump(output/'schema_revision_5.json', {'revision': schema_revision,
        'changes': 'Per-item bounds; raw answers retained, identity module for nonmembers excluded from effective scores. No item changes.',
        'measurement_module_sha256': hashlib.sha256(Path('survey_measurement.py').read_bytes()).hexdigest(),
        'schema_module_sha256': hashlib.sha256(Path('schemas.py').read_bytes()).hexdigest()})
    failures = 0
    result['status'] = 'running'
    pending = []
    for item in candidates:
        key = f"refill:{VERSION}:{item['source_run']}:{item['round']}:{item['agent']}"
        if (item['source_run'], item['round'], item['agent']) in answered: continue
        if key in done: key += ':schema-revision-5'
        if key in done:
            # At most two additional re-elicitations, with syntax/applicability
            # feedback only. Never tell the model which attitude to choose.
            base = key
            for attempt in (1, 2):
                repaired = base + f':format-repair-{attempt}'
                if repaired not in done:
                    key = repaired
                    item = dict(item, format_correction=(
                        '此前输出未通过格式校验。identified必须有至少一个可指认对象；none或unknown对应空对象数组。'
                        '不能仅因环境设施/默认分配规则而识别共同约定。各题严格使用单独范围，未知用unknown、不适用用na。'
                        '这是格式与适用性说明，不要求任何特定态度或分数。'))
                    break
        if key not in done: pending.append((item, key))
    def perform(item, key):
        request = payload(item['observation'])
        if item.get('format_correction'): request['format_correction'] = item['format_correction']
        response = api.request(item['model'], 'survey_measurement', SYSTEM, request, request_key=key)
        return response, validate(response, request)
    with ThreadPoolExecutor(max_workers=4) as pool:
        for start in range(0, len(pending), 4):
            external = total_spent(roots)
            if not args.mock and external + api.cost >= 10:
                result['status'] = 'budget_limit'; break
            jobs = {pool.submit(perform, item, key): (item, key) for item, key in pending[start:start+4]}
            for job in as_completed(jobs):
                item, key = jobs[job]
                metadata = {k: v for k, v in item.items() if k != 'observation'}
                try:
                    response, flags = job.result()
                    result['surveys'].append({**metadata, 'refill_key': key, 'responses': response,
                        'effective_responses': effective(response, payload(item['observation'])),
                        'quality_flags': flags, 'synthetic': args.mock, 'post_hoc': True,
                        'schema_revision': schema_revision})
                    failures = 0
                except Exception as error:
                    result['failures'].append({**metadata, 'refill_key': key,
                        'error': type(error).__name__ + ': ' + str(error)})
                    failures += 1
                    if isinstance(error, RuntimeError) or failures >= 3:
                        result['status'] = 'stopped_after_error'
                result.update(calls=api.calls, cost_usd=api.cost, total_targets=len(candidates),
                              global_cost_usd=external+api.cost)
                dump(result_path, result)
                print(f"saved={len(result['surveys'])}/{len(candidates)} failures={len(result['failures'])} cost=${api.cost:.6f}", flush=True)
            if result['status'] != 'running': break
        else: result['status'] = 'complete' if not result['failures'] else 'complete_with_failures'
    result.update(calls=api.calls, cost_usd=api.cost, total_targets=len(candidates),
                  global_cost_usd=total_spent(roots)+api.cost)
    completed = {(a['source_run'], a['round'], a['agent']) for a in result['surveys']}
    result['completed_respondent_timepoints'] = len(completed)
    result['unresolved_respondent_timepoints'] = len(candidates)-len(completed)
    result['historical_failed_attempts'] = len(result['failures'])
    if len(completed) == len(candidates): result['status'] = 'complete'
    dump(result_path, result)
    # Separate runs and rounds, preserving incomplete-run labels.
    grouped = {}
    for answer in result['surveys']:
        grouped.setdefault((answer['source_run'], answer['round']), []).append(answer)
    dump(output/'summary.json', {'status': result['status'], 'synthetic': args.mock,
        'cost_usd': api.cost, 'global_cost_usd': result['global_cost_usd'],
        'stages': [{'source_run': run, 'round': t, 'source_status': rows[0]['source_status'],
                    **summarize(rows)} for (run, t), rows in sorted(grouped.items())]})


if __name__ == '__main__':
    from process_guard import guard
    # Acquire before network/catalog access or ledger changes. Process death
    # releases the lock, allowing a safe resume.
    guard_parser = argparse.ArgumentParser(add_help=False)
    guard_parser.add_argument('--output', default='runs/survey_refill_v3_keyed_20261007')
    guard_args, _ = guard_parser.parse_known_args()
    with guard(guard_args.output, 'refill'): main()
