"""Budget-aware fresh 50-round protocol; previous experiments remain immutable."""
import json
import subprocess
import sys
from pathlib import Path
from process_guard import guard


def main():
    output=Path('runs/core_campaign_v6_50rounds_20261007')
    config=Path('configs/core_pilot_v6_50rounds_20261007')
    with guard(output,'launch'):
        roots=json.loads((config/'prior_cost_roots.json').read_text(encoding='utf-8'))['roots']
        for refill in sorted(Path('runs').glob('survey_refill_v3*')):
            if (refill/'api_accounting.json').exists(): roots.append(str(refill))
        for pilot in sorted(Path('runs').glob('gpt_oss*_pilot_*')):
            if list(pilot.rglob('api_accounting.json')): roots.append(str(pilot))
        command=[sys.executable,'-u','run_batch.py','--config-dir',str(config),
            '--output',str(output),'--budget-usd','10','--api-key-file','../api_key',
            '--parallel-runs','2','--recovery-transport','--run-cost-cap','0.2']
        for root in roots:command.extend(['--prior-cost-root',root])
        return subprocess.run(command).returncode


if __name__=='__main__':sys.exit(main())
