"""Read-only local replay server. Uses only the Python standard library."""
import argparse
import json
import time
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import run_sources

HERE = Path(__file__).resolve().parent
RUNS = HERE.parent / 'society_probe' / 'society_probe' / 'runs'
CACHE = {}


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def describe(path, checkpoint=None):
    cfg = run_sources.config(path.parent)
    cp = checkpoint or read_json(path)
    state = cp.get('state', {})
    exp = cfg.get('experiment', {})
    family = cfg.get('world', {}).get('mechanism', exp.get('family', 'unknown'))
    rid = path.parent.relative_to(RUNS).as_posix()
    return dict(id=rid, name=rid.replace('/simulation', ''), family=family,
                environment=exp.get('environment_id', family), models=list(dict.fromkeys(cfg.get('models', []))),
                pressure=cfg.get('world', {}).get('survival_pressure', False), seed=cfg.get('seed'),
                rounds=state.get('round', 0), planned=cfg.get('rounds', 0), agents=len(state.get('agents', {})),
                status='complete' if (path.parent / 'result.json').exists() else 'partial',
                mock=cp.get('mock', False), updated=path.stat().st_mtime)


def catalog():
    if time.monotonic() - CACHE.get('catalog_time', 0) < 8:
        return CACHE['catalog']
    items = []
    source, groups = run_sources.index(RUNS)
    paths = [(entry['folder'] / 'simulation' / 'checkpoint.json', entry) for entry in groups]
    if source is None:
        paths = [(p, None) for p in RUNS.glob('*/simulation/checkpoint.json')]
    for path, entry in paths:
        try:
            if entry:
                cp = run_sources.read(path) or {'state': {}}
                cfg = run_sources.config(path.parent)
                state = cp.get('state', {})
                status = run_sources.read(entry['folder'] / 'runner_status.json') or {}
                item = dict(id=path.parent.relative_to(RUNS).as_posix(),
                    name=entry['group'], group=entry['group'], family=cfg.get('world', {}).get('mechanism', 'material_world'),
                    environment=cfg.get('experiment', {}).get('environment_id', 'functional_material_world'),
                    models=[entry['definition'].get('model', '')],
                    pressure=cfg.get('world', {}).get('survival_pressure', False), seed=cfg.get('seed'),
                    rounds=state.get('round', 0), planned=cfg.get('rounds', entry['definition'].get('rounds', 0)),
                    agents=len(state.get('agents', {})) or entry['definition'].get('members', 0),
                    status=status.get('status', 'complete' if (path.parent/'result.json').exists() else 'running'),
                    mock=cp.get('mock', False), updated=path.stat().st_mtime if path.exists() else 0)
                progress = run_sources.pending(path.parent, item['rounds'])
                item['pending_round'] = progress['round'] if progress else None
                items.append(item)
                continue
            stamp = (path.stat().st_mtime_ns, (path.parent / 'result.json').exists())
            cache_key = 'meta:' + str(path)
            prior = CACHE.get(cache_key)
            item = prior[1] if prior and prior[0] == stamp else describe(path)
            CACHE[cache_key] = (stamp, item)
            if item['agents'] and item['rounds']:
                items.append(item)
        except (OSError, ValueError, KeyError):
            continue  # A running experiment may be replacing a checkpoint.
    if source is None:
        items.sort(key=lambda x: -x['updated'])
    CACHE.update(catalog=items, catalog_time=time.monotonic())
    return items


def load_run(rid):
    folder = (RUNS / rid).resolve()
    if not folder.is_relative_to(RUNS.resolve()):
        raise ValueError('Invalid run')
    path = folder / 'checkpoint.json'
    stamp = tuple(p.stat().st_mtime_ns if p.exists() else 0 for p in
                  (path, folder/'in_progress.json', folder.parent/'runner_status.json', folder.parent/'config.json'))
    if rid in CACHE and CACHE[rid][0] == stamp:
        return CACHE[rid][1]
    cp = read_json(path) if path.exists() else {'state': {'round': 0, 'agents': {}}}
    state = cp['state']
    cfg = run_sources.config(folder)
    completed = state.get('round', 0)
    events = [e for e in state.get('events', []) if e.get('round', 0) <= completed]
    meta = next((item for item in catalog() if item['id'] == rid), None)
    if meta is None:
        meta = describe(path, cp)
    else:
        meta = dict(meta, rounds=completed)
    # The checkpoint is the source of truth for settled events, not proposed calls.
    payload = dict(meta=meta, config={k: cfg.get(k) for k in
                   ['world', 'tools', 'scenario', 'experiment', 'mixed_world']},
                   agents={k: {'model': v.get('model', ''), 'initial_stock': cfg.get('world', {}).get('initial_personal_stock', 0)}
                           for k, v in state.get('agents', {}).items()},
                   events=events, snapshots=[s for s in state.get('snapshots', []) if s.get('round', 0) <= completed],
                   environment_history=[s for s in state.get('environment_history', []) if s.get('round', 0) <= completed])
    payload['communications'] = [c for c in (state.get('communication_events') or [
        c for event in events for c in event.get('pre_action_dialogue', [])]
        ) if c.get('round', 0) <= completed]
    payload['artifacts'] = state.get('culture', state.get('mixed', {})).get('artifacts', {})
    payload['social_content'] = state.get('social_content', {})
    payload['physics'] = state.get('mini_world', {})
    payload['final_agents'] = state.get('agents', {})
    if not payload['agents']:
        payload['agents'] = {f'a{i}': {'model': meta['models'][0], 'initial_stock': 0}
                             for i in range(meta['agents'])}
    payload['in_progress'] = run_sources.pending(folder, completed)
    payload['runner_status'] = (run_sources.read(folder.parent/'runner_status.json') or {}).get('status', meta['status'])
    CACHE[rid] = (stamp, payload)
    return payload


def detail(rid, round_number, agent):
    folder = (RUNS / rid).resolve()
    if not folder.is_relative_to(RUNS.resolve()):
        raise ValueError('Invalid run')
    key = f'act:{round_number}:{agent}'
    found = None
    calls = folder / 'calls.jsonl'
    if calls.exists():
        with calls.open(encoding='utf-8') as stream:
            for line in stream:
                try:
                    call = json.loads(line)
                    if call.get('request_key') == key:
                        response = call.get('response')
                        reasoning = call.get('reasoning') or call.get('reasoning_content')
                        if isinstance(response, dict):
                            reasoning = reasoning or response.get('reasoning_content') or response.get('reasoning')
                        observation = next((m.get('content') for m in reversed(call.get('messages', [])) if m.get('role') == 'user'), None)
                        found = dict(response=response, reasoning=reasoning, observation=observation,
                                     model=call.get('requested_model'), seconds=call.get('seconds'))
                except (ValueError, TypeError):
                    continue
    return found or {}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(HERE), **kwargs)

    def do_GET(self):
        url = urlparse(self.path)
        if not url.path.startswith('/api/'):
            if url.path == '/':
                self.path = '/index.html'
            elif url.path == '/lab':
                self.path = '/lab.html'
            elif url.path == '/replay':
                self.path = '/index.html'
            elif url.path == '/works':
                self.path = '/works.html'
            return super().do_GET()
        try:
            query = parse_qs(url.query)
            if url.path == '/api/runs':
                result = catalog()
            elif url.path == '/api/comparison':
                result = run_sources.comparison(RUNS)
            elif url.path == '/api/mechanisms':
                import mechanism_lab
                result = mechanism_lab.catalog()
            elif url.path == '/api/run':
                result = load_run(query.get('id', [''])[0])
            elif url.path == '/api/detail':
                result = detail(query.get('id', [''])[0], int(query.get('round', ['0'])[0]), query.get('agent', [''])[0])
            else:
                self.send_error(404)
                return
            data = json.dumps(result, ensure_ascii=False).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except (ValueError, OSError, KeyError):
            self.send_error(400, 'Run unavailable; refresh after checkpoint is saved')

    def do_POST(self):
        route = urlparse(self.path).path
        if route not in ('/api/lab', '/api/game-preview'):
            self.send_error(404)
            return
        try:
            length = int(self.headers.get('Content-Length', 0))
            if not 0 < length <= 16384:
                raise ValueError('Invalid request size')
            params = json.loads(self.rfile.read(length))
            if not isinstance(params, dict):
                raise ValueError('Expected parameters')
            import mechanism_lab
            if route == '/api/lab':
                result = mechanism_lab.simulate(params)
            else:
                import game_rules
                run = load_run(params['run'])
                work = run['artifacts'][params['artifact']]
                source = work.get('versions', {}).get(str(params.get('version', 1)), {}).get('content', work.get('content'))
                rules, _ = game_rules.parse(source, work['kind'])
                players = list(run['agents'])[:rules['min_players']]
                if len(players) < rules['min_players']:
                    raise ValueError('Not enough members for this game preview')
                if params.get('op') == 'move':
                    turn = int(params.get('turn', 0))
                    if not 0 <= turn < rules['max_moves']:
                        raise ValueError('Preview move limit reached')
                    result = game_rules.transition(source, work['kind'], params['state'], params['action'],
                        players[turn % len(players)], players, 'preview:'+str(turn))
                else:
                    result = {'state': rules['initial_state'], 'done': False}
                result.update(rules=rules, players=players)
            data = json.dumps(result, ensure_ascii=False, allow_nan=False).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except (ValueError, TypeError, KeyError, OverflowError, SyntaxError, IndexError) as exc:
            data = json.dumps({'error': str(exc)}).encode('utf-8')
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8776)
    parser.add_argument('--runs-root', type=Path, help='Read a published results bundle or a local demo output directory')
    args = parser.parse_args()
    if args.runs_root:
        RUNS = args.runs_root.resolve()
    elif not RUNS.exists():
        RUNS = HERE.parent / 'results' / 'baseline_20261010'
    print(f'Society Observatory: http://127.0.0.1:{args.port}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()
