"""Read-only evidence audit: distinguish questionnaire completion from society evidence."""
import csv
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from sim import Society, dump
from metrics import measure
import environments


def main():
    root = Path('runs/core_campaign_v6_50rounds_20261007')
    refill = json.loads(Path('runs/survey_refill_v3_keyed_20261007/result.json').read_text(encoding='utf-8'))
    post = [a for a in refill['surveys'] if a['round'] > 0]
    grouped = defaultdict(list)
    for a in post: grouped[a['source_run'], a['round']].append(a)
    states, configs, series = {}, {}, {}
    for name in {a['source_run'] for a in refill['surveys']}:
        folder = root/name/'simulation'
        file = folder/'failed_state.json'
        if not file.exists(): file = folder/'checkpoint.json'
        states[name] = json.loads(file.read_text(encoding='utf-8'))['state']
        configs[name] = json.loads((folder/'config.json').read_text(encoding='utf-8'))
        series[name] = {x['round']: x for x in measure(states[name], configs[name])['round_series']}
    values = {}
    for field, codes in [('groups', ['I01', 'I09', 'I13']),
                         ('arrangements', ['J01', 'J06', 'L01', 'L02', 'D01', 'D02', 'C01'])]:
        for code in codes:
            scores = [o['scores'][code] for a in post for o in a['effective_responses'][field]]
            numeric = [v for v in scores if type(v) is int]
            values[code] = {'mean': statistics.mean(numeric) if numeric else None,
                           'valid_n': len(numeric), 'distribution': dict(Counter(map(str, scores)))}
    cross = Counter()
    rows = []
    for (name, t), answers in sorted(grouped.items()):
        state = states[name]
        old = {(a['round'], a['agent']): a for a in state['surveys']}
        for a in answers:
            cross[str(old[t, a['agent']]['responses']['organization_exists']), a['responses']['arrangement_detection']] += 1
        snapshot = next(x for x in state['snapshots'] if x['round'] == t)
        same_actions = []
        for step in range(max(1, t-4), t+1):
            events = [e for e in state['events'] if e['round'] == step and 'action_error' not in e['outcome']]
            signatures = Counter(json.dumps(e['decision']['action'], sort_keys=True) for e in events)
            if events: same_actions.append(max(signatures.values())/len(events))
        row = {'source_run': name, 'source_status': answers[0]['source_status'], 'round': t,
               'family': configs[name]['world']['mechanism'], 'pressure': configs[name]['world']['survival_pressure'],
               'respondents': len(answers), 'alive': sum(a['alive'] for a in snapshot['agents'].values()),
               'original_members': len(snapshot['agents']),
               'group_identified_n': sum(a['responses']['group_detection'] == 'identified' for a in answers),
               'arrangement_identified_n': sum(a['responses']['arrangement_detection'] == 'identified' for a in answers),
               'old_arrangement_exists_true_n': sum(old[t, a['agent']]['responses']['organization_exists'] is True for a in answers),
               'identity_excluded_n': sum('identity_ratings_for_nonmember_excluded' in a['quality_flags'] for a in answers),
               'mean_full_action_modal_share_5_rounds': statistics.mean(same_actions) if same_actions else None,
               'behavior_surprisal_bits': series[name][t]['mean_behavior_surprisal_bits'],
               'stock_gini_alive': series[name][t]['stock_gini_alive'],
               'transfer_edges': len(series[name][t]['transfer_graph']['directed_edges']),
               'private_message_edges': len(series[name][t]['private_message_graph']['directed_edges'])}
        for field, code in [('groups', 'I09'), ('arrangements', 'L01'), ('arrangements', 'D02')]:
            scores = [o['scores'][code] for a in answers for o in a['effective_responses'][field]]
            numeric = [v for v in scores if type(v) is int]
            row[code+'_mean'] = statistics.mean(numeric) if numeric else None
            row[code+'_valid_n'] = len(numeric)
        groups = Counter(tuple(sorted(o['member_ids'])) for a in answers for o in a['responses']['groups'])
        row['largest_same_membership_report_count'] = max(groups.values(), default=0)
        rows.append(row)
    # Mechanical no-cooperation counterexample; explicitly not an LLM run.
    cfg = configs['public_goods_p1_basic_s7']
    society = Society(cfg)
    for t in range(1, 51):
        society.state['round'] = t
        before = environments.physical_snapshot(society.state)
        for aid in society.state['agents']: society.act(aid, {'tool': 'wait'})
        society.settle(before)
    counterexample = {'synthetic_mechanical_check': True, 'rounds': 50,
        'policy': 'all wait; zero contributions, zero communication',
        'alive': sum(a['alive'] for a in society.state['agents'].values()),
        'stocks': {i: a['stock'] for i, a in society.state['agents'].items()},
        'interpretation': 'Verifies physical accounting only; NOT evidence of an LLM society.'}
    batch = json.loads((root/'batch_status.json').read_text(encoding='utf-8'))
    run_status = Counter(batch['runs'][name]['status'] for name in states)
    mortality_case = states['congestion_p1_information_s7']
    survival = [{'round': x['round'], 'alive': sum(a['alive'] for a in x['agents'].values())}
                for x in mortality_case['snapshots'] if x['round'] in (5, 10, 15, 20, 50)]
    collapse10 = next(x for x in rows if x['source_run'] == 'congestion_p1_information_s7' and x['round'] == 10)
    summary = {'scope': 'Descriptive audit; repeated agents/rounds are NOT independent samples.',
        'survey_count': len(refill['surveys']), 'postbaseline_count': len(post), 'original_runs': len(states),
        'source_run_status_counts': dict(run_status), 'model_ids': sorted({a['model'] for a in post}),
        'postbaseline_group_detection': dict(Counter(a['responses']['group_detection'] for a in post)),
        'postbaseline_arrangement_detection': dict(Counter(a['responses']['arrangement_detection'] for a in post)),
        'quality_flags': dict(Counter(f for a in post for f in a['quality_flags'])), 'item_statistics': values,
        'old_new_arrangement_cross_table': [{'old_exists': a, 'new_detection': b, 'n': n} for (a,b), n in sorted(cross.items())],
        'public_goods_zero_contribution_counterexample': counterexample,
        'congestion_complete_case_survival': survival, 'congestion_round10_survey_and_behavior': collapse10,
        'matched_stage_rows': rows}
    out = Path('../../refine-logs/SURVEY_EVIDENCE_ANALYSIS_20261007.json')
    dump(out, summary)
    csv_path = out.with_suffix('.csv')
    with csv_path.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    print(json.dumps({k: summary[k] for k in ('source_run_status_counts', 'postbaseline_group_detection',
        'postbaseline_arrangement_detection', 'quality_flags', 'public_goods_zero_contribution_counterexample',
        'congestion_complete_case_survival', 'congestion_round10_survey_and_behavior')}, ensure_ascii=False))
    for row in rows:
        if row['source_run'] in ('public_goods_p1_basic_s17', 'commons_p1_basic_s7', 'contest_p1_basic_s7') and row['round'] in (10,20):
            print(json.dumps(row, ensure_ascii=False))


if __name__ == '__main__': main()
