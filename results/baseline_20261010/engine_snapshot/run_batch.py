"""Budgeted, resumable local API experiments with an immutable engine snapshot."""
import argparse
import copy
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from sim import dump
from analyze_runs import summarize
from audit_actions import audit


def service_failure(log_path):
    """Classify the latest process failure without exposing request data."""
    lines=log_path.read_text(encoding='utf-8').strip().splitlines() if log_path.exists() else []
    last=lines[-1] if lines else ''
    match=re.search(r'OpenRouter HTTP (\d{3})',last)
    if match:
        code=int(match.group(1))
        if code in (401,402,403):return 'account_http_'+str(code)
        if code==429 or code>=500:return 'transient_service'
    if any(kind in last for kind in ('TimeoutError:','URLError:','RemoteDisconnected:','IncompleteRead:','ConnectionError:')):
        return 'transient_service'
    return None


def spent(folder):
    values = []
    for name in ('result.json','failed_state.json','checkpoint.json','api_accounting.json'):
        p=folder/name
        if p.exists():
            x=json.loads(p.read_text(encoding='utf-8'))
            values.append(x.get('cost_usd',0)+x.get('reserved_usd',0))
    return max(values,default=0.)


def quality(folder):
    cfg=json.loads((folder/'config.json').read_text(encoding='utf-8'))
    result=json.loads((folder/'result.json').read_text(encoding='utf-8'))
    state=json.loads((folder/'checkpoint.json').read_text(encoding='utf-8'))['state']
    n=len(state['events']); surveys=result['surveys']
    bad=sum(bool(a['quality_flags']) for a in surveys)
    baseline=[a for a in surveys if a['round']==0]
    claims=sum(a['responses']['organization_exists'] is True for a in baseline)
    invalid=result['invalid_actions']/n if n else None
    flagged=bad/len(surveys) if surveys else None
    communication_errors=sum('communication_error' in e['outcome'] for e in state['events'])
    audited=audit(folder)
    syntax_fraction=audited['schema_or_range_rejections']/n if n else None
    passed=(result['completed_rounds']==cfg['rounds'] and not result['synthetic']
            and syntax_fraction is not None and syntax_fraction <= .05
            and flagged is not None and flagged <= .10 and claims==0
            and communication_errors/max(1,n)<=.05)
    return {'passed':passed, 'invalid_action_fraction':invalid,
            'schema_or_range_rejection_fraction':syntax_fraction,
            'state_constraint_rejections':audited['state_constraint_rejections'],
            'replay_verified':audited['verified_replay'], 'quality_flagged_survey_fraction':flagged,
            'baseline_organization_claims':claims, 'communication_errors':communication_errors,
            'completed_rounds':result['completed_rounds'], 'surveys':len(surveys),
            'note':'Engineering/measurement gate only. No test of social-organization hypotheses.'}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--config-dir',required=True);p.add_argument('--output',required=True)
    p.add_argument('--budget-usd',type=float,required=True)
    p.add_argument('--api-key-file',required=True);p.add_argument('--parallel-runs',type=int,default=2)
    p.add_argument('--names',nargs='+');p.add_argument('--sanity',action='store_true')
    p.add_argument('--prior-cost-root',action='append',default=[])
    p.add_argument('--recovery-transport',action='store_true')
    p.add_argument('--run-cost-cap',type=float)
    args=p.parse_args()
    if not 0 < args.budget_usd or not 1 <= args.parallel_runs <= 4:raise ValueError('Invalid batch limits')
    config_dir=Path(args.config_dir).resolve();output=Path(args.output).resolve()
    key_file=Path(args.api_key_file).resolve()
    output.mkdir(parents=True,exist_ok=True)
    engine=output/'engine_snapshot'
    if not engine.exists():
        engine.mkdir()
        for name in ('sim.py','environments.py','metrics.py','schemas.py','context_codec.py','hierarchical_memory.py','survey_measurement.py'):
            shutil.copyfile(Path(__file__).with_name(name),engine/name)
    if args.recovery_transport:
        for name in ('run_frozen.py','recovery_transport.py'):
            if not (engine/name).exists():
                shutil.copyfile(Path(__file__).with_name(name),engine/name)
    names=args.names or json.loads((config_dir/'manifest.json').read_text(encoding='utf-8'))['runs']
    external_cost=sum(spent(p.parent) for root in args.prior_cost_root
                      for p in Path(root).resolve().rglob('config.json'))
    status={'budget_usd':args.budget_usd,'prior_cost_usd':external_cost,'runs':{},
            'engine_snapshot':str(engine),'started_unix':time.time(), 'status':'running'}
    active={};failures=[];summaries=[];remaining=list(names)
    consecutive_service_failures=0
    def launch(name,cap):
        folder=output/name;folder.mkdir(exist_ok=True)
        cfg_path=folder/'launch_config.json'
        if not cfg_path.exists():
            cfg=json.loads((config_dir/(name+'.json')).read_text(encoding='utf-8'))
            cfg['max_estimated_cost_usd']=cap
            dump(cfg_path,cfg)
        command=[sys.executable,'-u',str(engine/'sim.py'),'--config',str(cfg_path),
                 '--output',str(folder),'--api-key-file',str(key_file)]
        if args.recovery_transport:
            command=[sys.executable,'-u',str(engine/'run_frozen.py'),
                     '--engine',str(engine),'--run-cost-cap',str(cap)]+command[3:]
        if (folder/'checkpoint.json').exists(): command.append('--resume')
        # launch_config exists before sim's nonempty guard; run into a nested folder.
        run_folder=folder/'simulation';run_folder.mkdir(exist_ok=True)
        if not (run_folder/'checkpoint.json').exists() and {p.name for p in run_folder.iterdir()}=={'.run.lock','config.json'}:
            archive=folder/('initial_config_'+str(time.time_ns())+'.json')
            (run_folder/'config.json').rename(archive)
        command[command.index('--output')+1]=str(run_folder)
        if '--resume' in command:command.remove('--resume')
        if (run_folder/'checkpoint.json').exists():command.append('--resume')
        with (folder/'process.log').open('a',encoding='utf-8') as log:
            env=os.environ.copy();env['PYTHONIOENCODING']='utf-8'
            code=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,env=env).returncode
        return name,code,run_folder
    # Run folders are nested so launcher metadata does not contaminate engine output.
    def batch_spent():return external_cost+sum(spent(output/n/'simulation') for n in names)
    with ThreadPoolExecutor(max_workers=args.parallel_runs) as pool:
        while remaining or active:
            while remaining and len(active)<args.parallel_runs:
                name=remaining.pop(0);folder=output/name/'simulation'
                if (folder/'result.json').exists():
                    q=quality(folder)
                    item={'status':'complete','cost_usd':spent(folder),'quality':q}
                    if args.sanity and not q['passed']:item['status']='quality_failed';failures.append(name)
                    summaries.append(summarize(folder));status['runs'][name]=item
                    continue
                budget_left=args.budget_usd-batch_spent()-sum(max(0,cap-spent(output/n/'simulation')) for _,(n,cap) in active.items())
                source=json.loads((config_dir/(name+'.json')).read_text(encoding='utf-8'))
                cap=args.run_cost_cap or source['max_estimated_cost_usd']
                existing=spent(folder)
                if budget_left+existing < cap:
                    status['runs'][name]={'status':'budget_deferred'}
                    status['status']='budget_limit';continue
                status['runs'][name]={'status':'running','cap_usd':cap}
                active[pool.submit(launch,name,cap)]=(name,cap)
                dump(output/'batch_status.json',status)
            completed=[future for future in active if future.done()]
            for future in completed:
                name,_=active.pop(future)
                try:
                    _,code,folder=future.result()
                    item={'status':'complete' if code==0 else 'failed','exit_code':code,'cost_usd':spent(folder)}
                    if code==0:
                        summaries.append(summarize(folder));item['quality']=quality(folder)
                        if args.sanity and not item['quality']['passed']:item['status']='quality_failed';failures.append(name)
                    else:
                        failures.append(name)
                        failure=service_failure(output/name/'process.log')
                        item['service_failure']=failure
                        consecutive_service_failures=consecutive_service_failures+1 if failure else 0
                        if failure and (failure.startswith('account_http_') or consecutive_service_failures>=3):
                            status['status']='service_blocked'
                            status['stop_reason']=failure
                            for pending in remaining:
                                status['runs'][pending]={'status':'service_deferred','reason':failure}
                            remaining.clear()
                    if code==0:consecutive_service_failures=0
                    status['runs'][name]=item
                    print(name,item['status'],f'cost=${item["cost_usd"]:.5f}',flush=True)
                except Exception as exc:
                    status['runs'][name]={'status':'failed','reason':str(exc)};failures.append(name)
                dump(output/'analysis.json',{'runs':summaries,'failures':failures,
                     'note':'Exploratory run-level summaries; organization development requires trajectory coding.'})
            status['spent_usd']=batch_spent();status['updated_unix']=time.time()
            dump(output/'batch_status.json',status)
            if active and not completed:time.sleep(2)
    if status['status']=='running':status['status']='complete' if not failures else 'completed_with_failures'
    status['spent_usd']=batch_spent();dump(output/'batch_status.json',status)
    print(json.dumps({'status':status['status'],'spent_usd':status['spent_usd'],'complete_runs':len(summaries),'failures':failures}))
    return 0 if status['status']=='complete' else 1


if __name__=='__main__':
    from process_guard import guard
    parser=argparse.ArgumentParser(add_help=False);parser.add_argument('--output')
    selected,_=parser.parse_known_args()
    if selected.output:
        with guard(selected.output,'batch'):sys.exit(main())
    else:sys.exit(main())
