"""Read-only local replay server. Uses only the Python standard library."""
import argparse
import json
import time
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

HERE = Path(__file__).resolve().parent
RUNS = HERE.parent / 'society_probe' / 'society_probe' / 'runs'
CACHE = {}


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def describe(path, checkpoint=None):
    cfg = read_json(path.parent / 'config.json')
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
    for path in RUNS.rglob('checkpoint.json'):
        try:
            stamp = (path.stat().st_mtime_ns, (path.parent / 'result.json').exists())
            cache_key = 'meta:' + str(path)
            prior = CACHE.get(cache_key)
            item = prior[1] if prior and prior[0] == stamp else describe(path)
            CACHE[cache_key] = (stamp, item)
            if item['agents'] and item['rounds']:
                items.append(item)
        except (OSError, ValueError, KeyError):
            continue  # A running experiment may be replacing a checkpoint.
    items.sort(key=lambda x: ('multi_environment_v2' not in x['id'], 'four_model_mix' not in x['id'], -x['updated']))
    CACHE.update(catalog=items, catalog_time=time.monotonic())
    return items


def load_run(rid):
    folder = (RUNS / rid).resolve()
    if not folder.is_relative_to(RUNS.resolve()):
        raise ValueError('Invalid run')
    path = folder / 'checkpoint.json'
    stamp = path.stat().st_mtime_ns
    if rid in CACHE and CACHE[rid][0] == stamp:
        return CACHE[rid][1]
    cp = read_json(path)
    state = cp['state']
    cfg = read_json(folder / 'config.json')
    events = state.get('events', [])
    # The checkpoint is the source of truth for settled events, not proposed calls.
    payload = dict(meta=describe(path, cp), config={k: cfg.get(k) for k in
                   ['world', 'tools', 'scenario', 'experiment', 'mixed_world']},
                   agents={k: {'model': v.get('model', ''), 'initial_stock': cfg.get('world', {}).get('initial_personal_stock', 0)}
                           for k, v in state.get('agents', {}).items()},
                   events=events, snapshots=state.get('snapshots', []),
                   environment_history=state.get('environment_history', []))
    payload['communications'] = state.get('communication_events') or [
        c for event in events for c in event.get('pre_action_dialogue', [])]
    payload['artifacts'] = state.get('culture', state.get('mixed', {})).get('artifacts', {})
    payload['social_content'] = state.get('social_content', {})
    payload['physics'] = state.get('mini_world', {})
    payload['final_agents'] = state.get('agents', {})
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
    args = parser.parse_args()
    print(f'Society Observatory: http://127.0.0.1:{args.port}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()
