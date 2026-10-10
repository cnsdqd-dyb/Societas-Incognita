"""All-OpenRouter transport with model-specific schema/provider/reasoning settings."""
import argparse
import json
from pathlib import Path
import sim
from hybrid_codex import router_class


def main():
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--output',required=True)
    p.add_argument('--api-key-file',default='../api_key');p.add_argument('--mock',action='store_true');p.add_argument('--resume',action='store_true')
    args=p.parse_args();cfg=json.loads(Path(args.config).read_text('utf-8'))
    if any(r['backend']!='openrouter' for r in cfg['model_routes'].values()):raise ValueError('Small-model runner accepts only OpenRouter routes')
    if not args.mock:sim.load_api_key(args.api_key_file)
    sim.API=router_class(sim.API,external_only=True)
    sim.run(cfg,args.output,mock=args.mock,resume=args.resume)


if __name__=='__main__':main()
