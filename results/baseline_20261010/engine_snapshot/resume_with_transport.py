"""Let already active frozen runs finish before restarting dispatch with recovery."""
import json
import argparse
import msvcrt
import subprocess
import sys
import time
from pathlib import Path
from process_guard import guard


def active_run(path):
    with path.open('r+b') as handle:
        try:msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:return True
        handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
        return False


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--prior-cost-root',action='append',default=[])
    args=parser.parse_args()
    root=Path('runs/core_campaign_v5_20261005')
    with guard(root,'transport_recovery'):
        while any(active_run(p) for p in (root/'long_pilot').glob('*/simulation/.run.lock')):
            time.sleep(10)
        print('Active simulations finished. Restarting with audited transport recovery.',flush=True)
        command=[sys.executable,'-u','run_campaign.py','--budget-usd','10',
            '--api-key-file','../api_key','--recovery-transport','--run-cost-cap','0.8']
        for root_path in args.prior_cost_root:command.extend(['--prior-cost-root',root_path])
        return subprocess.run(command).returncode


if __name__=='__main__':sys.exit(main())
