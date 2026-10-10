"""Wait for the current batch, then make one budget-preserving recovery pass."""
import json
import subprocess
import sys
import time
from pathlib import Path
from process_guard import guard, alive


def main():
    root=Path('runs/core_campaign_v5_20261005')
    with guard(root,'recovery'):
        while True:
            state=json.loads((root/'long_pilot/batch_status.json').read_text(encoding='utf-8'))
            if state['status']!='running':break
            time.sleep(20)
        if state['status']!='completed_with_failures':
            print('Recovery pass skipped: '+state['status'],flush=True)
            return 0
        owner=root/'campaign_owner.json'
        while owner.exists() and alive(json.loads(owner.read_text(encoding='utf-8'))['pid']):
            time.sleep(2)
        print('Starting one recovery pass; all earlier costs remain in the $10 budget.',flush=True)
        return subprocess.run([sys.executable,'-u','run_campaign.py',
            '--budget-usd','10','--api-key-file','../api_key']).returncode


if __name__=='__main__':sys.exit(main())
