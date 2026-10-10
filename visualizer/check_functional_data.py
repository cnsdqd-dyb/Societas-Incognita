"""Regression checks for declared directories and completed/live round isolation."""
import json
import tempfile
from pathlib import Path
import server

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')

original = server.RUNS
try:
    with tempfile.TemporaryDirectory() as tmp:
        runs = Path(tmp)/'runs'
        root = runs/'functional_homogeneous_4x50_20261010'
        group = runs/'functional_sol_low_4x50_20261010/sol_low'
        write(root/'manifest.json', {'groups': [{'group':'sol_low','model':'fixture','members':1,'rounds':50},
                                                {'group':'outside','model':'excluded'}],
              'group_directories': {'sol_low':str(group),'outside':str(Path(tmp)/'outside')}})
        write(group/'config.json', {'models':['fixture'],'rounds':50,'world':{'mechanism':'mini_world'}})
        write(group/'runner_status.json', {'status':'running'})
        write(group/'simulation/checkpoint.json', {'state':{'round':1,'agents':{'a0':{'model':'fixture'}},
              'events':[{'round':1},{'round':2}], 'snapshots':[{'round':1},{'round':2}],
              'communication_events':[{'round':1},{'round':2}]}})
        write(group/'simulation/in_progress.json', {'phase':'communicate','state':{'round':2,
              'communication_events':[{'round':1},{'round':2}]},'dialogue_turn':3})
        server.RUNS=runs
        server.CACHE.clear()
        catalog=server.catalog()
        assert len(catalog)==1
        loaded=server.load_run(catalog[0]['id'])
        for field in ('events','snapshots','communications'):
            assert [r['round'] for r in loaded[field]]==[1], field
        assert loaded['in_progress']['round']==2
        assert [r['round'] for r in loaded['in_progress']['communications']]==[2]
        # A live-round update must invalidate the loaded run even if checkpoint stays fixed.
        write(group/'simulation/in_progress.json', {'phase':'decide','state':{'round':2},'dialogue_turn':8})
        assert server.load_run(catalog[0]['id'])['in_progress']['dialogue_turn']==8
        write(group/'simulation/in_progress.json', {'phase':'decide','state':{'round':1}})
        assert server.load_run(catalog[0]['id'])['in_progress'] is None
        # A declared group exists in the selector before its first checkpoint.
        (group/'simulation/checkpoint.json').unlink()
        server.CACHE.clear()
        loaded=server.load_run(server.catalog()[0]['id'])
        assert loaded['meta']['rounds']==0 and len(loaded['agents'])==1
finally:
    server.RUNS=original
    server.CACHE.clear()
print('Declared-path boundary, completed/live isolation, live cache refresh, stale progress and first-checkpoint absence: PASS')
