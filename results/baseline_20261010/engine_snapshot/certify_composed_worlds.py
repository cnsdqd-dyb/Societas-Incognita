"""Export/check deterministic composition certificates; never call an LLM API."""
import hashlib
import json
from pathlib import Path

import composed_certificates as proof


def certify(cfg,plan,path,semantic=False):
    artifact=proof.export(cfg,plan,path.with_suffix('.lean'),semantic=semantic); checked=proof.check(artifact)
    bundle={'version':'composed_semantic_survival_v2' if semantic else 'composed_interval_survival_v1','plan':plan,'lean':checked}
    path.write_text(json.dumps(bundle,ensure_ascii=False,indent=2),encoding='utf-8')
    return bundle


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',default='reports/composed_lean_20261010')
    p.add_argument('--semantic',action='store_true')
    args=p.parse_args(); output=Path(args.output); output.mkdir(parents=True,exist_ok=True)
    summary=[]
    for pressure in (0,1):
        cfg=json.loads(Path(f'configs/capability_fixtures_20261010/capabilities_4agents_p{pressure}_hidden.json').read_text('utf-8'))
        for target in ('relay','archive','sensor','workbench'):
            witness=json.loads(Path(f'reports/capability_feasibility_20261010/{target}_p{pressure}.json').read_text('utf-8'))
            path=output/f'{target}_p{pressure}.json'
            bundle=certify(cfg,witness['plan'],path,semantic=args.semantic)
            row={'target':target,'pressure':pressure,**{k:bundle['lean'][k] for k in ('status','horizon','members','nodes','unique_constraints','max_float_comparison_error')}}
            summary.append(row); print(json.dumps(row),flush=True)
            if bundle['lean']['status']=='lean_checked_composed_interval_certificate':
                admitted=json.loads(json.dumps(cfg)); admitted['survival_certificate']={'path':str(path.resolve()),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
                # Prepared with zero API budget; generating this does not launch a run.
                (output/f'{target}_p{pressure}_certified_config.json').write_text(json.dumps(admitted,ensure_ascii=False,indent=2),encoding='utf-8')
            (output/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
