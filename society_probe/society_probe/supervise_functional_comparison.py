"""Maintain offline progress reports and bounded recovery of transport failures.

No decisions are synthesized and no prompts/configurations are changed.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import psutil
from native_codex import write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='runs/functional_homogeneous_4x50_20261010')
    parser.add_argument('--report-root', help='Optional combined campaign to refresh while monitoring this group')
    args = parser.parse_args()
    root = Path(args.root).resolve()
    report_root = Path(args.report_root).resolve() if args.report_root else root
    source = Path(__file__).resolve().parent
    manifest = json.loads((root / 'manifest.json').read_text('utf-8'))
    directories = manifest.get('group_directories', {g['group']: g['group'] for g in manifest['groups']})
    checkpoint = root / 'supervisor_status.json'
    saved = json.loads(checkpoint.read_text('utf-8')) if checkpoint.exists() else {}
    retries = saved.get('transport_restarts', {})
    deadline = time.time() + 6 * 3600
    next_analysis = 0
    while time.time() < deadline:
        terminal = True
        statuses = {}
        for label, directory in directories.items():
            folder = root / directory
            path = folder / 'runner_status.json'
            info = json.loads(path.read_text('utf-8')) if path.exists() else {'status': 'not_started'}
            statuses[label] = info['status']
            if info['status'] == 'complete' and not (folder / 'recorded_replay').exists():
                with (folder / 'offline_replay.log').open('w', encoding='utf-8') as log:
                    replay = subprocess.run([sys.executable, '-X', 'utf8',
                        str(source / 'replay_native_run.py'), '--run', str(folder),
                        '--output', str(folder / 'recorded_replay')], cwd=source,
                        stdout=log, stderr=log,
                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                write_json(folder / 'offline_replay_status.json', {'exit_code': replay.returncode,
                    'finished': time.time(), 'model_calls': 0})
            if info['status'] in ('running', 'retrying'):
                pid = info.get('pid')
                alive = False
                if pid and psutil.pid_exists(pid):
                    try:
                        cmd = ' '.join(psutil.Process(pid).cmdline())
                        alive = 'run_functional_comparison.py' in cmd and directory in cmd
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                if alive:
                    terminal = False
                    continue
                info = {'status': 'failed', 'error': 'Runner process disappeared; durable checkpoint preserved'}
            error = info.get('error', '')
            recoverable = any(s in error for s in (
                'OpenRouter HTTP 429', 'OpenRouter HTTP 500', 'OpenRouter HTTP 502',
                'OpenRouter HTTP 503', 'OpenRouter HTTP 504', 'timed out',
                'Remote end closed connection', 'Connection reset', 'Runner process disappeared',
                'malformed completion envelope')) or error == "'choices'"
            if (info['status'] == 'failed' and recoverable and retries.get(label, 0) < 3
                    and not (root / 'NO_AUTORESTART').exists()):
                # Native children may be finishing a paid request. Never overlap recovery.
                children_pending = False
                for p in (folder / 'simulation').glob('**/native_requests/*/process.json'):
                    record = json.loads(p.read_text('utf-8'))
                    if psutil.pid_exists(record['pid']):
                        try:
                            if str(p.parent).lower() in ' '.join(psutil.Process(record['pid']).cmdline()).lower():
                                children_pending = True
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                if children_pending:
                    terminal = False
                    continue
                retries[label] = retries.get(label, 0) + 1
                with (folder / f'supervised_{retries[label]}.stdout.log').open('w', encoding='utf-8') as out, \
                        (folder / f'supervised_{retries[label]}.stderr.log').open('w', encoding='utf-8') as err:
                    process = subprocess.Popen([sys.executable, '-u', '-X', 'utf8',
                        str(source / 'run_functional_comparison.py'), '--run', str(folder)],
                        cwd=source, stdout=out, stderr=err,
                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                write_json(folder / 'runner_status.json', {'status': 'running', 'pid': process.pid,
                    'started': time.time(), 'supervised_transport_restart': retries[label]})
                terminal = False
        write_json(checkpoint, {'status': 'finished' if terminal else 'monitoring',
            'pid': os.getpid(), 'updated': time.time(), 'groups': statuses,
            'transport_restarts': retries, 'model_and_world_changes': False})
        if time.time() >= next_analysis or terminal:
            with (root / 'analysis_refresh.log').open('a', encoding='utf-8') as log:
                result = subprocess.run([sys.executable, '-X', 'utf8',
                    str(source / 'analyze_functional_comparison.py'), '--root', str(report_root), '--plot'],
                    cwd=source, stdout=log, stderr=log,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            next_analysis = time.time() + 60
        if terminal:
            manifest = json.loads((root / 'manifest.json').read_text('utf-8'))
            manifest['stage'] = 'completed' if all(s == 'complete' for s in statuses.values()) else 'stopped_with_errors'
            write_json(root / 'manifest.json', manifest)
            return
        time.sleep(20)
    write_json(checkpoint, {'status': 'monitor_timeout_runners_unchanged', 'updated': time.time(),
               'transport_restarts': retries})


if __name__ == '__main__':
    main()
