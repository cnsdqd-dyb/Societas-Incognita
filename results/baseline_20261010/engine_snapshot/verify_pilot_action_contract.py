"""Two bounded interface probes, not a replay or a new society experiment."""
import json
from pathlib import Path

import jsonschema
import sim
import schemas
import interaction_controls
from context_codec import unpack
from provider_schema import mistral_transport_schema


def main():
    root=Path('runs/mini_world_pilot_20261010').resolve()
    sim.load_api_key('../api_key')
    original=schemas.schema
    def remote_schema(kind,payload,cfg):
        contract=original(kind,payload,cfg)
        return mistral_transport_schema(contract) if kind=='act' else contract
    rows=[]
    for pressure in (0,1):
        folder=root/f'p{pressure}_hidden'; cfg=json.loads((folder/'config.json').read_text('utf-8'))
        cfg.update(max_calls=2,max_estimated_cost_usd=.02)
        records=[json.loads(line) for line in (folder/'simulation'/'calls.jsonl').read_text('utf-8').splitlines()]
        previous=next(r for r in records if r['kind']=='act')
        payload=unpack(json.loads(previous['messages'][1]['content']))
        system=cfg['actor_system']+'\n'+interaction_controls.actor_help(cfg,payload,'')
        directory=root/f'action_contract_probe_p{pressure}'; directory.mkdir(exist_ok=True)
        api=sim.API(cfg,directory)
        try:
            schemas.schema=remote_schema
            response=api.request(cfg['models'][0],'act',system,payload,request_key=f'action-contract-v2:p{pressure}')
        finally: schemas.schema=original
        jsonschema.validate(response,original('act',payload,cfg))
        row={'pressure':pressure,'valid_full_action_contract':True,'response':response,'cost_usd':api.cost,
             'scope':'interface probe from original first action observation; does not replace historical trajectory'}
        rows.append(row); print(json.dumps(row,ensure_ascii=False),flush=True)
    (root/'action_contract_verification.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__': main()
