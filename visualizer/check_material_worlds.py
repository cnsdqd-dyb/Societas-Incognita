"""Validate all mechanism probes and the checkpoint adapter using real data."""
import json
from pathlib import Path
import mechanism_lab
import server

for item in mechanism_lab.catalog():
    for drive in ('idle', 'production'):
        result = mechanism_lab.simulate({'modules': [item['id']], 'rounds': 30, 'drive': drive})
        assert len(result['frames']) == 31
        assert all(abs(f['accounting']['residual']) <= 1e-7 for f in result['frames'])
        for f in result['frames']:
            assert all(-1e-8 <= v <= result['definition']['pools'][k]['capacity']+1e-8 for k, v in f['physics']['pools'].items())
    print(item['id'], 'PASS')
modules = [item['id'] for item in mechanism_lab.catalog()]
result = mechanism_lab.simulate({'modules': modules, 'rounds': 60})
assert all(abs(f['accounting']['residual']) <= 1e-7 for f in result['frames'])
assert result == mechanism_lab.simulate({'modules': modules, 'rounds': 60})
for rid in ['composed_sol_low_4x20_20261010/simulation', 'sol_low_pilot_20261010/simulation']:
    if not (server.RUNS / rid / 'checkpoint.json').exists():
        print(rid, 'SKIP: private local research log is absent')
        continue
    run = server.load_run(rid)
    state = json.loads((server.RUNS / rid / 'checkpoint.json').read_text(encoding='utf-8'))['state']
    assert len(run['events']) == len(state['events'])
    assert run['communications'] == state['communication_events']
    assert run['snapshots'] == state['snapshots']
    print(rid, 'PASS', len(run['communications']), 'dialogue records')
print('All 20 individual mechanisms, combined conservation, deterministic replay: PASS')
