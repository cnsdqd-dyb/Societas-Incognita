"""Refresh unstarted frozen files only; never changes an executed experiment."""
import hashlib
import json
import shutil
from pathlib import Path
from native_codex import write_json
from shared_budget import SharedBudget
ROOT=Path('runs/multi_environment_v2_20261009')
def main():
    if list(ROOT.glob('*/simulation')):raise RuntimeError('Cannot refresh engines after any run has initialized')
    budget=SharedBudget.create(ROOT/'budget.sqlite3',4.277054114)
    if budget.status()['request_count']:raise RuntimeError('Existing paid requests')
    files=list(Path('.').glob('*.py'));manifest=json.loads((ROOT/'manifest.json').read_text('utf-8'))
    for folder in [ROOT]+[ROOT/c['name'] for c in manifest['runs']]:
        for p in files:shutil.copy2(p,folder/'engine_snapshot'/p.name)
        if folder!=ROOT:
            for p in ('native_codex.py','hybrid_codex.py','recovery_transport.py'):shutil.copy2(p,folder/p)
    manifest.update(source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files},status='ready_pending_native_usage_approval',active_cases=[],native_call_cap=0,
        approval_block='Automatic approval rejected uncapped unknown Codex-native monetary usage. No model calls launched. Two-case maximum-400-call authorization requested.')
    write_json(ROOT/'manifest.json',manifest)
    print(json.dumps({'calls':budget.status()['request_count'],'native':budget.native_status(),'status':manifest['status']}))
if __name__=='__main__':main()
