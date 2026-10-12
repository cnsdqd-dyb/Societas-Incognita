"""Resume a frozen native pilot after rechecking its independent runtime witness."""
import argparse
import copy
import hashlib
import json
import os
import sys
import time
from pathlib import Path


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True)
    root=Path(parser.parse_args().root).resolve()
    engine=root/'engine_snapshot';sys.path.insert(0,str(engine))
    import sim,environments,survival_certificates
    from native_codex import NativeCodexAPI,write_json
    from capability_feasibility import action_order
    read=lambda p:json.loads(p.read_text('utf-8'))
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    cfg=read(root/'config.json');manifest=read(root/'manifest.json')
    def admission(candidate):
        if candidate!=cfg or digest(root/'config.json')!=manifest['config_sha256']:
            raise ValueError('Frozen native configuration changed')
        if digest(root/'runtime_plan.json')!=manifest['plan_sha256']:
            raise ValueError('Runtime witness changed')
        for name,sha in manifest['engine_sha256'].items():
            if digest(engine/name)!=sha:raise ValueError('Frozen engine changed: '+name)
        s=sim.Society(cfg)
        for t,joint in enumerate(read(root/'runtime_plan.json'),1):
            s.state['round']=t;before=environments.physical_snapshot(s.state)
            for aid in action_order(cfg,t,joint):s.act(aid,copy.deepcopy(joint[aid]))
            s.settle(before)
            if not all(a['alive'] for a in s.state['agents'].values()):raise ValueError('Runtime survival witness failed')
        return {'status':'runtime_checked_not_lean_certified','rounds':cfg['rounds']}
    survival_certificates.validate_admission=admission
    sim.API=NativeCodexAPI;sim.dump=write_json
    write_json(root/'runner_status.json',{'status':'running','pid':os.getpid(),'started':time.time()})
    output=root/'simulation'
    try:
        for attempt in range(3):
            try:
                sim.run(cfg,output,mock=False,resume=(output/'checkpoint.json').exists())
                break
            except RuntimeError as exc:
                if attempt==2 or not str(exc).startswith(('Native CLI failed','Native request timed out')):raise
                write_json(root/'runner_status.json',{'status':'retrying','pid':os.getpid(),'attempt':attempt+1,'error':str(exc)})
                time.sleep(5)
        result=read(output/'result.json')
        result.update(backend='codex_native_cli',native_cost_usd=None,external_api_calls=0)
        write_json(output/'result.json',result)
        write_json(root/'runner_status.json',{'status':'complete','finished':time.time(),
            'completed_rounds':result['completed_rounds'],'alive_fraction':result['alive_fraction']})
    except Exception as exc:
        write_json(root/'runner_status.json',{'status':'failed','finished':time.time(),'error':str(exc),
            'resume':'Run the same run_native_matched.py --root; durable replies and journals are reused'})
        raise


if __name__=='__main__':main()
