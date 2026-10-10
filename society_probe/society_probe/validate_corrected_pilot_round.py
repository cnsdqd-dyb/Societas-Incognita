"""One actual round under the ORIGINAL shared $0.50 cap; no full rerun."""
import hashlib
import json
from pathlib import Path

import certify_composed_worlds
import sim


def main():
    root=Path('runs/mini_world_pilot_20261010').resolve()
    directory=root/'corrected_one_round_acceptance'; directory.mkdir(exist_ok=True)
    cfg=json.loads((root/'p1_hidden'/'config.json').read_text('utf-8'))
    cfg.pop('survival_certificate',None)
    cfg.update(rounds=1,max_calls=100,max_estimated_cost_usd=.04)
    cfg['experiment']['stage']='corrected_one_round_interface_acceptance_not_research_result'
    plan=json.loads((root/'p1_hidden'/'survival_certificate.json').read_text('utf-8'))['plan'][:1]
    path=directory/'certificate.json'
    bundle=certify_composed_worlds.certify(cfg,plan,path,semantic=True)
    if bundle['lean']['status']!='lean_checked_composed_interval_certificate': raise ValueError('Certificate rejected')
    cfg['survival_certificate']={'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    (directory/'config.json').write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
    sim.load_api_key('../api_key'); sim.run(cfg,directory/'simulation',mock=False)
    state=json.loads((directory/'simulation'/'checkpoint.json').read_text('utf-8'))['state']
    report={'completed_rounds':state['round'],'actions':[{'agent':e['agent'],'decision':e['decision'],
        'outcome':e['outcome']} for e in state['events']],
        'invalid_physical_actions':sum(x.get('invalid',0) for x in state['action_counts'].values()),
        'interpretation':'Single-round interface acceptance only. Illegal chosen physical actions are recorded, not repaired.'}
    (directory/'acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)


if __name__=='__main__': main()
