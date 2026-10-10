"""Persist the sanity-to-pilot handoff; never start the pilot after a failed gate."""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from sim import dump


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--budget-usd',type=float,default=10)
    p.add_argument('--api-key-file',default='../api_key')
    p.add_argument('--output',default='runs/core_campaign_v5_20261005')
    p.add_argument('--sanity-root',default='runs/core_sanity_v4_20261005')
    p.add_argument('--config-dir',default='configs/core_pilot_v5_20261005')
    p.add_argument('--prior-cost-root',action='append',default=[])
    p.add_argument('--recovery-transport',action='store_true')
    p.add_argument('--run-cost-cap',type=float)
    args=p.parse_args()
    root=Path(args.output);root.mkdir(parents=True,exist_ok=True)
    sanity=Path(args.sanity_root)
    prior=[str(Path('runs')/name) for name in (
        'core_sanity_20261005','core_sanity_v2_20261005','core_sanity_v3_20261005','core_sanity_v4_20261005')]
    prior+=['runs/core_campaign_20261005/long_pilot']+args.prior_cost_root
    prior=list(dict.fromkeys(str(Path(path).resolve()) for path in prior))
    status={'status':'waiting_for_sanity','budget_usd':args.budget_usd,
            'sanity':str(sanity),'pilot':str(root/'long_pilot')}
    env=os.environ.copy();env['PYTHONIOENCODING']='utf-8'
    while True:
        state=json.loads((sanity/'batch_status.json').read_text(encoding='utf-8'))
        if state['status']!='running':break
        status['updated_unix']=time.time();dump(root/'campaign_status.json',status);time.sleep(3)
    passed=(len(state['runs'])==4 and all(x.get('quality',{}).get('passed') for x in state['runs'].values()))
    if not passed:
        status.update(status='sanity_failed',reason='Pilot not launched: four mechanism gates must pass.')
        dump(root/'campaign_status.json',status);print(status['reason']);return 1
    status['status']='pilot_running';dump(root/'campaign_status.json',status)
    command=[sys.executable,'-u','run_batch.py','--config-dir',args.config_dir,
        '--output',str(root/'long_pilot'),'--budget-usd',str(args.budget_usd),
        '--api-key-file',args.api_key_file,'--parallel-runs','2']
    for path in prior:command.extend(['--prior-cost-root',path])
    if args.recovery_transport:command.append('--recovery-transport')
    if args.run_cost_cap is not None:command.extend(['--run-cost-cap',str(args.run_cost_cap)])
    with (root/'campaign.log').open('a',encoding='utf-8') as log:
        code=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,env=env).returncode
    result_path=root/'long_pilot/batch_status.json'
    state=json.loads(result_path.read_text(encoding='utf-8')) if result_path.exists() else {}
    status.update(status=state.get('status','failed'),exit_code=code,
        spent_usd=state.get('spent_usd'),updated_unix=time.time())
    dump(root/'campaign_status.json',status);print(json.dumps(status))
    return 0 if status['status']=='complete' and code==0 else 1


if __name__=='__main__':
    from process_guard import guard
    parser=argparse.ArgumentParser(add_help=False)
    parser.add_argument('--output',default='runs/core_campaign_v5_20261005')
    selected,_=parser.parse_known_args()
    with guard(selected.output,'campaign'):sys.exit(main())
