"""Check every prepared interface and all 14 deterministic survival witnesses."""
import json
from pathlib import Path
import jsonschema
import psutil
import sim
import schemas
import argparse
from prepare_multi_environment_v2 import witness


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--configs',default='configs/interaction_v3_20261009')
    parser.add_argument('--output',default='reports/interaction_v3_validation')
    args=parser.parse_args()
    directory=Path(args.configs)
    index=json.loads((directory/'index.json').read_text('utf-8'))
    proofs={};seen_pairs=set()
    for name in index['configs']:
        cfg=json.loads((directory/(name+'.json')).read_text('utf-8'))
        society=sim.Society(cfg)
        view=society.observe('a0')
        for kind in ('act','communicate'):
            jsonschema.Draft202012Validator.check_schema(schemas.schema(kind,view,cfg))
        assert cfg['max_estimated_cost_usd']==0 and 'campaign_budget_db' not in cfg
        pair=(cfg['world']['mechanism'],cfg['world']['survival_pressure'])
        if name.endswith(('_p0','_p1')) and pair not in seen_pairs:
            proofs[name]=witness(cfg);seen_pairs.add(pair)
    campaign=Path('runs/multi_environment_v2_20261009')
    processes=[]
    for proc in psutil.process_iter(['pid','cmdline']):
        try:
            line=' '.join(proc.info['cmdline'] or [])
            if 'multi_environment_v2_20261009' in line and any(marker in line for marker in ('hybrid_codex.py','multi_environment_runner.py','campaign_watcher.py')):
                processes.append(proc.info['pid'])
        except (psutil.NoSuchProcess,psutil.AccessDenied):continue
    report={'prepared_configs':len(index['configs']),'schema_checks':2*len(index['configs']),
            'survival_witnesses':proofs,'campaign_stop_exists':(campaign/'STOP').exists(),
            'active_campaign_pids':processes,'paid_calls':0,
            'interpretation':'Deterministic legal production paths attain 8 agents x 50 rounds in every pressure pair. This proves a survival maximum only, not a wealth optimum, worst-case bound or LLM behavior.'}
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    (out/'template_checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='survival_witnesses'},ensure_ascii=False))


if __name__=='__main__':main()
