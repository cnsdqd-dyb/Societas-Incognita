"""Prepare bounded pilot, freeze implementation, certify; no model API calls."""
import hashlib
import json
import shutil
from pathlib import Path

import certify_composed_worlds
from shared_budget import SharedBudget
from survival_certificates import find_lean


def prepare(root):
    root=Path(root).resolve(); root.mkdir(parents=True,exist_ok=True)
    engine=root/'engine_snapshot'; engine.mkdir(exist_ok=True)
    if (root/'manifest.json').exists(): raise ValueError('Pilot already prepared; resume existing runs rather than overwrite')
    source=Path(__file__).resolve().parent
    files=list(source.glob('*.py'))+list(source.glob('*.lean'))
    for path in files: shutil.copy2(path,engine/path.name)
    budget=SharedBudget.create(root/'budget.sqlite',.50)
    runs=[]
    for pressure in (0,1):
        directory=root/f'p{pressure}_hidden'; directory.mkdir(exist_ok=True)
        cfg=json.loads((source/f'configs/capability_fixtures_20261010/capabilities_4agents_p{pressure}_hidden.json').read_text('utf-8'))
        cfg.update(backend='openrouter',max_estimated_cost_usd=.25,max_calls=1200,max_output_tokens=800,
                   structured_outputs=True,provider_only=['Mistral'],campaign_budget_db=str(root/'budget.sqlite'))
        cfg['experiment'].update(stage='bounded_pipeline_pilot',certificate_status='dependency_graph_certificate_with_trusted_world_adapter',
            purpose='Validate unknown-rule exploration, private material knowledge, communication and replay; not a causal research result',
            trusted_boundaries=['world_action_compiler','JSON_normalization','IEEE_float_runtime'])
        witness=json.loads((source/f'reports/capability_feasibility_20261010/archive_p{pressure}.json').read_text('utf-8'))
        certificate=directory/'survival_certificate.json'
        bundle=certify_composed_worlds.certify(cfg,witness['plan'],certificate,semantic=True)
        if bundle['lean']['status']!='lean_checked_composed_interval_certificate': raise ValueError('Pilot certificate rejected')
        cfg['survival_certificate']={'path':str(certificate),'sha256':hashlib.sha256(certificate.read_bytes()).hexdigest()}
        (directory/'config.json').write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
        runs.append({'pressure':pressure,'directory':str(directory),'members':4,'rounds':50,'model':cfg['models'][0],
                     'world_rules':'hidden','recipes':'hidden','per_run_cap_usd':.25})
        print(json.dumps({'prepared':pressure,'certificate_status':bundle['lean']['status'],'action_comparisons':bundle['lean']['action_phase_audit']['comparisons']}),flush=True)
    manifest={'stage':'prepared_not_started','api_total_cap_usd':.5,'runs':runs,'lean_executable':find_lean(),
              'frozen_engine_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    (root/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    return manifest


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='runs/mini_world_pilot_20261010')
    prepare(parser.parse_args().output)
