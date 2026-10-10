"""Bounded supervision of the authorized native run; never changes its policy."""
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import psutil
from native_codex import write_json
from native_run_report import report


def alive_runner(status, root):
    pid = status.get('pid')
    if not pid:
        return False
    try:
        process = psutil.Process(pid)
        command = ' '.join(process.cmdline())
        return process.is_running() and 'native_codex.py' in command and root.name in command
    except psutil.NoSuchProcess:
        return False
    except psutil.AccessDenied:
        # Do not spawn a competing process when liveness cannot be verified.
        return True


def terminal_error(root):
    errors = []
    for folder in sorted((root/'simulation/native_requests').glob('*'))[-3:]:
        for filename in ('stderr.log', 'events.jsonl'):
            path = folder / filename
            if not path.exists():
                continue
            content = path.read_text('utf-8')
            if filename == 'stderr.log':
                errors.append(content)
            else:
                for line in content.splitlines():
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if event.get('type') in ('error', 'turn.failed'):
                        errors.append(str(event))
                    elif event.get('item', {}).get('type') == 'error':
                        errors.append(str(event['item']))
    text = '\n'.join(errors)
    match = re.search(r'usage limit|quota|insufficient credits|unauthorized|authentication failed|rate limit|\b(?:401|403|429)\b', text, re.I)
    return match.group(0) if match else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    root = Path(args.run).resolve()
    restarts = []
    deadline = time.monotonic() + 10800
    while time.monotonic() < deadline:
        status = json.loads((root/'runner_status.json').read_text('utf-8'))
        report(root)
        if status.get('status') == 'complete':
            write_json(root/'supervisor_status.json', {'status': 'complete', 'restarts': restarts})
            return
        if alive_runner(status, root):
            write_json(root/'supervisor_status.json', {'status': 'watching', 'runner_pid': status['pid'], 'restarts': restarts})
            time.sleep(10)
            continue
        reason = terminal_error(root)
        error = status.get('error', '')
        retryable = status.get('status') in ('running', 'retrying') or error.startswith(('Native CLI failed', 'Native request timed out')) or '[WinError 5]' in error
        if reason or not retryable or len(restarts) >= 5:
            write_json(root/'supervisor_status.json', {'status': 'stopped', 'reason': reason or error or 'Restart limit reached', 'restarts': restarts})
            return
        time.sleep(5)
        # Recheck before spawning; a manual resume may have started meanwhile.
        status = json.loads((root/'runner_status.json').read_text('utf-8'))
        if alive_runner(status, root):
            continue
        number = len(restarts) + 1
        with (root/f'supervised_{number}.stdout.log').open('a', encoding='utf-8') as out, \
                (root/f'supervised_{number}.stderr.log').open('a', encoding='utf-8') as err:
            child = subprocess.Popen([sys.executable, '-X', 'utf8', str(root/'native_codex.py'), '--run', str(root)],
                                     stdout=out, stderr=err, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        restarts.append({'pid': child.pid, 'time': time.time(), 'previous_status': status})
        write_json(root/'supervisor_status.json', {'status': 'restarting', 'runner_pid': child.pid, 'restarts': restarts})
        time.sleep(10)
    write_json(root/'supervisor_status.json', {'status': 'stopped', 'reason': 'Three-hour supervision window ended', 'restarts': restarts})


if __name__ == '__main__':
    main()
