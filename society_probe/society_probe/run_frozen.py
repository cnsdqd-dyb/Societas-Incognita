"""Run a frozen engine with a separately versioned, audited transport adapter."""
import argparse
import hashlib
import sys
from pathlib import Path
import recovery_transport


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--engine',required=True);p.add_argument('--run-cost-cap',type=float,required=True)
    p.add_argument('--config',required=True);p.add_argument('--output',required=True)
    p.add_argument('--api-key-file',required=True);p.add_argument('--resume',action='store_true')
    p.add_argument('--mock',action='store_true')
    p.add_argument('--network-retries',type=int)
    p.add_argument('--reuse-catalog',action='store_true')
    p.add_argument('--skip-exhausted-surveys',action='store_true')
    args=p.parse_args()
    if args.run_cost_cap<=0:raise ValueError('Invalid operational budget')
    if args.network_retries is not None and not 0<=args.network_retries<=2:
        raise ValueError('Operational network retries must be 0..2')
    sys.path.insert(0,str(Path(args.engine).resolve()))
    import sim
    recovery_transport.install(sim.API,args.run_cost_cap,args.network_retries,args.reuse_catalog,args.skip_exhausted_surveys)
    folder=Path(args.output);folder.mkdir(parents=True,exist_ok=True)
    sim.dump(folder.parent/'recovery_transport_protocol.json',{
        'adapter_hash':hashlib.sha256(Path(recovery_transport.__file__).read_bytes()).hexdigest(),
        'max_additional_requests_per_invalid_response':2,
        'operational_run_cost_cap_usd':args.run_cost_cap,
        'operational_network_retries':args.network_retries,
        'reuse_verified_catalog_on_resume':args.reuse_catalog,
        'skip_exhausted_surveys':args.skip_exhausted_surveys,
        'note':'Same frozen engine/config/model/prompts. Raw failed responses and costs retained.'})
    sys.argv=[str(Path(args.engine)/'sim.py'),'--config',args.config,'--output',args.output,
        '--api-key-file',args.api_key_file]+(['--resume'] if args.resume else [])+(['--mock'] if args.mock else [])
    sim.main()
    if args.skip_exhausted_surveys:
        import json
        result=json.loads((folder/'result.json').read_text('utf-8'))
        checkpoint=json.loads((folder/'checkpoint.json').read_text('utf-8'))
        result['survey_failures']=checkpoint['state'].get('survey_failures',[])
        sim.dump(folder/'result.json',result)


if __name__=='__main__':main()
