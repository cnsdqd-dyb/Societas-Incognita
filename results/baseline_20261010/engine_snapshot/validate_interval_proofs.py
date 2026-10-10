"""Two-agent, two-round offline composition check; never launches a model."""
import copy
import hashlib
import json
from pathlib import Path

import composed_certificates as composed
import interval_proofs


def main(include_advanced=False):
    root = Path('reports/interval_advanced_20261010' if include_advanced else 'reports/interval_soundness_20261010')
    root.mkdir(parents=True, exist_ok=True)
    cfg = json.loads(Path('configs/capability_fixtures_20261010/capabilities_4agents_p0_hidden.json').read_text('utf-8'))
    cfg = copy.deepcopy(cfg); cfg['models'] = cfg['models'][:2]; cfg['rounds'] = 2
    cfg.pop('survival_certificate', None)
    plan = [{f'a{i}': {'tool': 'wait'} for i in range(2)} for _ in range(2)]
    artifact = composed.export(cfg, plan, root/'two_agent_two_round.lean')
    path = Path(artifact['source'])
    data = path.read_text('utf-8') + '\n' + Path('interval_soundness.lean').read_text('utf-8').removeprefix('import Std\n')
    if include_advanced:
        data += Path('interval_advanced.lean').read_text('utf-8').removeprefix('import Std\n')
    path.write_text(data, encoding='utf-8')
    artifact['sha256'] = hashlib.sha256(data.encode()).hexdigest()
    artifact['proved_operators'] = list(interval_proofs.FULL_OPERATORS if include_advanced else interval_proofs.PROVED_OPERATORS)
    artifact['complete_operator_soundness'] = include_advanced
    artifact['scope'] += ' Companion universal soundness theorems cover the listed operators and positivity; no full DAG or world-transition theorem.'
    checked = composed.check(artifact)
    for name, value in (('two_agent_two_round_config.json',cfg),
                        ('two_agent_two_round_plan.json',plan),
                        ('two_agent_two_round_check.json',checked)):
        (root/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':checked['status'],'agents':2,'rounds':2,'api_cost_usd':0},ensure_ascii=False))
    if checked['status'] != 'lean_checked_composed_interval_certificate':
        raise RuntimeError(checked)


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--complete-operators',action='store_true')
    main(parser.parse_args().complete_operators)
