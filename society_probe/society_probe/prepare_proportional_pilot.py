"""Prepare a bounded native-Codex pilot; certify before any real model call."""
import hashlib
import json
import shutil
from pathlib import Path

import certify_composed_worlds
from certify_twenty_mechanisms import greedy_survival
import world_rule_library as library


def main():
    source=Path(__file__).resolve().parent
    root=source/'runs/proportional_sol_low_4x10_20261010'
    if (root/'config.json').exists():
        raise ValueError('Already prepared: resume the existing frozen run')
    root.mkdir(parents=True,exist_ok=True)
    cfg=json.loads((source/'runs/sol_low_pilot_20261010/config.json').read_text('utf-8'))
    cfg.pop('survival_certificate',None)
    keys=[key for key,_ in library.CANDIDATES_20]
    candidate=library.with_capabilities(library.generate(1,keys))
    cfg['world']['mini_world']['definition']=candidate['definition']
    import functional_effects
    cfg['tools']=sorted(set(cfg['tools']) | {'use_function'} | functional_effects.STORAGE_TOOLS)
    cfg.update(rounds=10,max_calls=200)
    cfg['experiment'].update(stage='small_proportional_twenty_mechanism_pilot',
        generation=candidate['generation'],model_counts={'gpt-6.1-sol':4},
        purpose='Descriptive small pilot of unknown composed-world exploration; no matched causal comparison to earlier worlds',
        certificate_status='pending',extensions_enabled=False)
    certificate=root/'survival_certificate.json'
    bundle=certify_composed_worlds.certify(cfg,greedy_survival(cfg),certificate,semantic=True)
    if bundle['lean']['status']!='lean_checked_composed_interval_certificate':
        raise RuntimeError('Pilot not admitted: '+bundle['lean']['status'])
    cfg['survival_certificate']={'path':str(certificate),'sha256':hashlib.sha256(certificate.read_bytes()).hexdigest()}
    (root/'config.json').write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
    engine=root/'engine_snapshot';engine.mkdir(exist_ok=True)
    hashes={}
    for item in list(source.glob('*.py'))+list(source.glob('*.lean')):
        shutil.copy2(item,engine/item.name)
        hashes[item.name]=hashlib.sha256(item.read_bytes()).hexdigest()
    manifest={'model':'gpt-6.1-sol','effort':'low','members':4,'rounds':10,
        'world_generation_seed':1,'simulation_seed':cfg['seed'],'modules':keys,
        'production_semantics':candidate['definition']['production_semantics'],
        'world_rules':'hidden','recipes':'hidden','pressure':True,'material_capabilities':True,
        'noise':candidate['definition']['noise'],'native_call_cap':200,'external_api_calls':0,
        'native_cost_usd':None,'frozen_engine_sha256':hashes,
        'certificate_status':bundle['lean']['status'],
        'scope':'All twenty bounded mechanisms; no games, seizure, rescue or questionnaires. One seed, descriptive pilot.'}
    (root/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'prepared':str(root),'certificate':bundle['lean']['status'],'rounds':10,'modules':20}),flush=True)


if __name__=='__main__':
    main()
