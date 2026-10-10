"""Durable parallel campaign; immutable cases, shared API spending ceiling."""
import argparse
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import psutil
from native_codex import write_json
from shared_budget import SharedBudget

def read(p):return json.loads(p.read_text('utf-8')) if p.exists() else {}
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True);args=parser.parse_args()
    root=Path(args.run).resolve();manifest=read(root/'manifest.json');budget=SharedBudget(manifest['shared_budget_db'])
    if (root/'STOP').exists():raise RuntimeError('Campaign is paused by STOP; no new cases launched')
    lock=root/'controller.lock'
    if lock.exists() and psutil.pid_exists(read(lock).get('pid',0)):raise RuntimeError('Campaign controller already running')
    lock.unlink(missing_ok=True)
    with lock.open('x',encoding='utf-8') as h:json.dump({'pid':os.getpid()},h)
    statuses=read(root/'campaign_status.json').get('runs',{});mutex=threading.RLock();stop=threading.Event()
    def save():
        with mutex:
            write_json(root/'campaign_status.json',{'controller_pid':os.getpid(),'updated':time.time(),'runs':statuses,
                'budget':budget.status(),'native_usage_limit':budget.native_status(),'native_cost_usd':None,'approved_cases':len(manifest['runs'])})
    def update(case,**values):
        with mutex:statuses.setdefault(case,{}).update(values);save()
    def snapshot(name,pid):
        folder=root/name/'simulation';state=read(folder/'checkpoint.json').get('state',{});journal=read(folder/'in_progress.json')
        update(name,status='running',pid=pid,completed_rounds=state.get('round',0),in_progress_round=journal.get('state',{}).get('round'),phase=journal.get('phase'),alive=sum(a['alive'] for a in state.get('agents',{}).values()))
    def case_run(case):
        name=case['name'];folder=root/name;result=folder/'simulation'/'result.json'
        if (root/'STOP').exists():update(name,status='paused_user');return
        if name not in manifest.get('active_cases',[]):update(name,status='pending_native_authorization');return
        if result.exists():update(name,status='complete',completed_rounds=read(result)['completed_rounds']);return
        old=statuses.get(name,{}).get('pid')
        if old and psutil.pid_exists(old):
            p=psutil.Process(old)
            if 'hybrid_codex.py' not in ' '.join(p.cmdline()) or name not in ' '.join(p.cmdline()):raise RuntimeError('Saved PID belongs to a different process')
            while p.is_running():snapshot(name,old);time.sleep(5)
            if result.exists():update(name,status='complete',completed_rounds=read(result)['completed_rounds']);return
        if stop.is_set():update(name,status='pending_budget');return
        cmd=[sys.executable,'-X','utf8',str(folder/'hybrid_codex.py'),'--run',str(folder),'--api-key-file','../api_key']
        for attempt in range(manifest.get('transport_restart_attempts', 3)):
            if (root/'STOP').exists():update(name,status='paused_user');return
            with (folder/f'runner_{attempt}.stdout.log').open('a',encoding='utf-8') as out,(folder/f'runner_{attempt}.stderr.log').open('a',encoding='utf-8') as err:
                p=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=out,stderr=err,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                update(name,status='running',pid=p.pid,attempt=attempt)
                while p.poll() is None:snapshot(name,p.pid);time.sleep(5)
            if p.returncode==0 and result.exists():update(name,status='complete',completed_rounds=read(result)['completed_rounds']);return
            error=(folder/f'runner_{attempt}.stderr.log').read_text('utf-8')[-3000:]
            if 'budget would be exceeded' in error or 'budget would be exceeded' in error.lower():
                update(name,status='paused_budget',error=error);stop.set();return
            if 'Shared native call authorization limit reached' in error:
                update(name,status='paused_native_limit',error=error);stop.set();return
            update(name,status='failed',attempt=attempt,error=error)
            if not any(s in error for s in ('Native CLI failed','timed out','PermissionError','URLError','RemoteDisconnected','IncompleteRead','TimeoutError','database is locked')):return
            time.sleep(min(30, 3 * (attempt + 1)))
    try:
        save()
        with ThreadPoolExecutor(max_workers=manifest['case_workers']) as pool:
            futures=[pool.submit(case_run,c) for c in manifest['runs']]
            for f in futures:f.result()
        save()
    finally:lock.unlink(missing_ok=True)
if __name__=='__main__':main()
