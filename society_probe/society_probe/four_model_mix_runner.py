"""Two durable sequential lanes. Fixed per-case caps sum to $4; $1 stays reserved."""
import argparse
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import psutil
from native_codex import write_json


def read(path):
    return json.loads(path.read_text('utf-8')) if path.exists() else {}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True);args=parser.parse_args()
    root=Path(args.run).resolve();manifest=read(root/'manifest.json')
    if sum(r['api_cost_cap_usd'] for r in manifest['runs'])>manifest['additional_authorized_api_budget_usd']:
        raise ValueError('Allocated caps exceed authorization')
    lockfile=root/'controller.lock'
    if lockfile.exists():
        old=read(lockfile);pid=old.get('pid')
        if pid and psutil.pid_exists(pid):raise RuntimeError('Existing campaign controller; refusing duplicate')
        lockfile.unlink()
    with lockfile.open('x',encoding='utf-8') as handle:json.dump({'pid':os.getpid()},handle)
    statuses=read(root/'campaign_status.json').get('runs',{});mutex=threading.RLock()

    def save():
        with mutex:
            cost=0.;billed=0.;reserved=0.
            for case in manifest['runs']:
                output=root/case['name']/'simulation';account=read(output/'api_accounting.json')
                if case['backend']!='codex_native_cli':
                    cost+=account.get('cost_usd',0);reserved+=account.get('reserved_usd',0)
                    for line in (output/'calls.jsonl').read_text('utf-8').splitlines() if (output/'calls.jsonl').exists() else []:
                        try:billed+=float(json.loads(line).get('usage',{}).get('cost') or 0)
                        except json.JSONDecodeError:pass
            write_json(root/'campaign_status.json',{'pid':os.getpid(),'updated':time.time(),'runs':statuses,
                'conservative_api_cost_usd':cost,'returned_request_billed_usd':billed,'in_flight_reserved_usd':reserved,
                'additional_authorized_api_budget_usd':manifest['additional_authorized_api_budget_usd'],'allocated_caps_usd':sum(c['api_cost_cap_usd'] for c in manifest['runs']),'native_cost_usd':None})

    def run_case(case):
        folder=root/case['name'];output=folder/'simulation'
        # Adopt a child left running by a controller restart; never duplicate calls.
        existing=statuses.get(case['name'],{}).get('pid')
        if existing and psutil.pid_exists(existing):
            process=psutil.Process(existing)
            command_line=' '.join(process.cmdline())
            if 'hybrid_codex.py' not in command_line or case['name'] not in command_line:
                raise RuntimeError('Saved child PID now belongs to another process')
            while process.is_running():
                with mutex:
                    state=read(output/'checkpoint.json').get('state',{});journal=read(output/'in_progress.json')
                    statuses[case['name']].update(status='running',adopted=True,completed_rounds=state.get('round',0),
                        in_progress_round=journal.get('state',{}).get('round'),phase=journal.get('phase'),
                        alive=sum(a['alive'] for a in state.get('agents',{}).values()))
                    save()
                time.sleep(10)
        if (output/'result.json').exists():
            with mutex:statuses[case['name']]={'status':'complete','result':read(output/'result.json').get('completed_rounds')};save()
            return
        native=True  # Hybrid adapter resumes itself.
        command=[sys.executable,'-X','utf8',str(folder/'hybrid_codex.py'),'--run',str(folder),'--api-key-file','../api_key']
        for attempt in range(3):
            actual=command+(['--resume'] if not native and (output/'checkpoint.json').exists() else [])
            with (folder/f'runner_{attempt}.stdout.log').open('a',encoding='utf-8') as out, (folder/f'runner_{attempt}.stderr.log').open('a',encoding='utf-8') as err:
                child=subprocess.Popen(actual,stdin=subprocess.DEVNULL,stdout=out,stderr=err,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                with mutex:statuses[case['name']]={'status':'running','pid':child.pid,'attempt':attempt};save()
                while child.poll() is None:
                    with mutex:
                        state=read(output/'checkpoint.json').get('state',{});journal=read(output/'in_progress.json')
                        statuses[case['name']].update(completed_rounds=state.get('round',0),
                            in_progress_round=journal.get('state',{}).get('round'),phase=journal.get('phase'),
                            alive=sum(a['alive'] for a in state.get('agents',{}).values()))
                        save()
                    time.sleep(10)
            if child.returncode==0:
                with mutex:statuses[case['name']]={'status':'complete','completed_rounds':read(output/'result.json')['completed_rounds']};save()
                return
            error=(folder/f'runner_{attempt}.stderr.log').read_text('utf-8')[-3000:]
            with mutex:statuses[case['name']]={'status':'failed','error':error,'attempt':attempt};save()
            retryable=any(token in error for token in ('Native CLI failed','Native request timed out','PermissionError','URLError','RemoteDisconnected','IncompleteRead','TimeoutError'))
            if not retryable:break
            time.sleep(5)

    def lane(native):
        for case in manifest['runs']:
            if (case['backend']=='codex_native_cli')==native:run_case(case)

    try:
        save()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(run_case,case) for case in manifest['runs']]
            for future in futures:future.result()
        save()
    finally:lockfile.unlink(missing_ok=True)


if __name__=='__main__':main()
