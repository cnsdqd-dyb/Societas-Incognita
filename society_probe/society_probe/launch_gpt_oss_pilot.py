"""One 50-round GPT-OSS pilot within the previously authorized global $10 cap."""
import json
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from process_guard import guard
from refill_surveys import total_spent
from sim import dump


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='runs/gpt_oss20b_pilot_20261007')
    parser.add_argument('--provider', default='Darkbloom')
    args = parser.parse_args()
    output = Path(args.output)
    with guard(output, 'launch'):
        evidence = json.loads(Path('../../refine-logs/GPT_OSS_20B_LIVE_PREFLIGHT_20261007.json').read_text(encoding='utf-8'))
        roots = evidence['prior_cost_roots']
        roots = list(dict.fromkeys(roots + [str(p) for p in Path('runs').glob('gpt_oss*_pilot_*')
                                           if p.resolve() != output.resolve()]))
        prior = total_spent(roots)
        cap = min(.10, max(0., 10. - prior))
        if cap < .001:
            raise RuntimeError('Previously authorized global API budget has no usable remainder')
        output.mkdir(parents=True, exist_ok=True)
        cfg_path = output / 'launch_config.json'
        if not cfg_path.exists():
            cfg = json.loads(Path('configs/core_pilot_v7_surveys_20261007/congestion_p1_information_s7.json').read_text(encoding='utf-8'))
            cfg['models'] = ['openai/gpt-oss-20b'] * len(cfg['models'])
            cfg['provider_only'] = [args.provider]
            cfg['reasoning'] = {'effort': 'low', 'exclude': args.provider == 'Darkbloom'}
            cfg['network_retries'] = 0
            cfg['max_estimated_cost_usd'] = cap
            cfg['experiment'].update(population='homogeneous_gpt_oss_20b', stage='cross_model_pilot',
                comparison_source='core_campaign_v6_50rounds_20261007/congestion_p1_information_s7',
                caveat='Model-family comparison, not isolated parameter-size effect; original comparison used conditional_v2 surveys.')
            dump(cfg_path, cfg)
        elif json.loads(cfg_path.read_text(encoding='utf-8'))['provider_only'] != [args.provider]:
            raise ValueError('Provider differs from frozen run configuration')
        engine = output / 'engine_snapshot'
        if not engine.exists():
            engine.mkdir()
            for name in ('sim.py', 'environments.py', 'metrics.py', 'schemas.py',
                         'context_codec.py', 'hierarchical_memory.py', 'survey_measurement.py',
                         'run_frozen.py', 'recovery_transport.py'):
                shutil.copyfile(Path(name), engine / name)
        dump(output / 'budget_manifest.json', {'global_budget_usd': 10., 'prior_cost_usd': prior,
            'source_roots': roots, 'local_cost_cap_usd': cap, 'remaining_before_usd': 10. - prior,
            'protocol': '8 agents, 50 rounds, congestion, pressure, information tools, seed7; checkpoints every round and mid-decision.'})
        simulation = output / 'simulation'
        cmd = [sys.executable, '-X', 'utf8', '-u', 'run_frozen.py',
               '--engine', str(engine), '--run-cost-cap', str(cap), '--config', str(cfg_path),
               '--output', str(simulation), '--api-key-file', '../api_key', '--network-retries', '2', '--reuse-catalog']
        if (simulation / 'checkpoint.json').exists():
            cmd.append('--resume')
        result = subprocess.run(cmd)
        dump(output / 'launcher_result.json', {'exit_code': result.returncode})
        if result.returncode == 0:
            import compare_model_pilot
            compare_model_pilot.main()
        return result.returncode


if __name__ == '__main__':
    sys.exit(main())
