"""Bounded transport-only recovery of the two stopped API cases."""
import json
import subprocess
import sys
import time
from pathlib import Path
from native_codex import write_json

ROOT=Path('runs/open_campaign_v1_20261007').resolve()


def main():
    selected=sys.argv[1:] or ['ministral3b_p0','gptoss20b_p1']
    if not set(selected)<={'ministral3b_p0','gptoss20b_p1','gptoss20b_p0'}:raise ValueError('Unallocated recovery case')
    for name in selected:
        root=ROOT/name;output=root/'simulation'
        for attempt in range(3):
            if (output/'result.json').exists():
                write_json(root/'recovery_status.json',{'status':'complete','completed_rounds':50});break
            command=[sys.executable,'run_frozen.py','--engine',str(root/'engine_snapshot'),'--run-cost-cap','1',
                '--config',str(root/'config.json'),'--output',str(output),'--api-key-file','../api_key',
                '--network-retries','2','--reuse-catalog','--resume','--skip-exhausted-surveys']
            label=f'{int(time.time())}_{attempt}'
            with (root/f'recovery_{label}.stdout.log').open('a',encoding='utf-8') as stdout, \
                 (root/f'recovery_{label}.stderr.log').open('a',encoding='utf-8') as stderr:
                process=subprocess.Popen(command,stdout=stdout,stderr=stderr,stdin=subprocess.DEVNULL,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                write_json(root/'recovery_status.json',{'status':'running','pid':process.pid,'attempt':attempt,
                    'policy':'Same frozen engine, config, request cache and $1 case cap.'})
                code=process.wait()
            error=(root/f'recovery_{label}.stderr.log').read_text('utf-8',errors='replace')[-3000:]
            with (root/'recovery_attempts.jsonl').open('a',encoding='utf-8') as handle:
                handle.write(json.dumps({'exit_code':code,'error':error,'attempt':attempt,'finished':time.time()})+'\n')
            write_json(root/'recovery_status.json',{'status':'complete' if code==0 else 'failed',
                'exit_code':code,'error':error,'attempt':attempt})
            if code==0:break
            # Empty logs on a nonzero process exit indicate an unreported process loss,
            # not an agent result. Resume at most twice, preserving in-flight reserves.
            retryable=not error or any(t in error for t in ('PermissionError','URLError','RemoteDisconnected','IncompleteRead','TimeoutError'))
            if not retryable:break
            time.sleep(5)


if __name__=='__main__':main()
