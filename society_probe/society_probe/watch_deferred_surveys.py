"""Wait for the actor controller to finish, then fill frozen views at low concurrency."""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
import psutil
def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);args=p.parse_args();root=Path(args.run).resolve()
    while True:
        if (root/'STOP').exists():return
        lock=root/'controller.lock'
        if lock.exists() and psutil.pid_exists(json.loads(lock.read_text('utf-8')).get('pid',0)):
            time.sleep(10);continue
        status=root/'campaign_status.json';d=json.loads(status.read_text('utf-8')) if status.exists() else {}
        if any(v.get('status')=='running' and psutil.pid_exists(v.get('pid',0)) for v in d.get('runs',{}).values()):
            time.sleep(10);continue
        break
    subprocess.run([sys.executable,'-X','utf8','complete_deferred_surveys.py','--run',str(root)],check=True)
if __name__=='__main__':main()
