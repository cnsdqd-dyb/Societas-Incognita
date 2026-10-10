"""Paid paired replay: same private trajectory, three memory/encoding protocols."""
import copy
import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from sim import API,Society,compact,dump,load_api_key
from recovery_transport import install
from process_guard import guard


ROOT=Path('runs/context_cost_probe_20261007')
SOURCE=Path('runs/core_campaign_v5_20261005/long_pilot/commons_p1_information_s7/simulation')
ROUNDS=36
AID='a0'


def summarize(folder):
    categories={}
    for line in (folder/'calls.jsonl').read_text(encoding='utf-8').splitlines():
        record=json.loads(line);usage=record['usage'];kind=record['kind']
        row=categories.setdefault(kind,{'calls':0,'input_tokens':0,'output_tokens':0,'reported_cost_usd':0.})
        row['calls']+=1;row['input_tokens']+=usage.get('prompt_tokens',0)
        row['output_tokens']+=usage.get('completion_tokens',0)
        row['reported_cost_usd']+=usage.get('cost') or 0.
    return categories


def main():
    global ROOT,ROUNDS
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default=str(ROOT))
    parser.add_argument('--rounds',type=int,default=ROUNDS)
    parser.add_argument('--arms',nargs='+',default=['legacy','hierarchical','hierarchical_encoded'],
        choices=['legacy','hierarchical','hierarchical_encoded','hierarchical_tight_encoded'])
    args=parser.parse_args();ROOT=Path(args.output);ROUNDS=args.rounds
    ROOT.mkdir(parents=True,exist_ok=True)
    with guard(ROOT,'probe'):
        load_api_key('../api_key');install(API,.05)
        source_cfg=json.loads((SOURCE/'config.json').read_text(encoding='utf-8'))
        records=json.loads((SOURCE/'checkpoint.json').read_text(encoding='utf-8'))['state']['events']
        records={r['round']:r for r in records if r['agent']==AID and r['round']<=ROUNDS}
        observations={}
        for line in (SOURCE/'calls.jsonl').read_text(encoding='utf-8').splitlines():
            r=json.loads(line)
            if r['kind']=='act' and r['request_key'].endswith(':'+AID):
                payload=json.loads(r['messages'][1]['content'])
                if payload['round']<=ROUNDS:observations[payload['round']]=(r['messages'][0]['content'],payload)
        if set(records)!=set(range(1,ROUNDS+1)) or set(observations)!=set(records):
            raise ValueError('Source trajectory is incomplete')

        def run_arm(name):
            folder=ROOT/name;folder.mkdir(exist_ok=True)
            cfg=copy.deepcopy(source_cfg);cfg['max_estimated_cost_usd']=.05;cfg['max_calls']=200
            if name!='legacy':cfg['memory']={'mode':'hierarchical_v1','hierarchical':{}}
            if name in ('hierarchical_encoded','hierarchical_tight_encoded'):cfg['context_encoding']='compact_v1'
            if name=='hierarchical_tight_encoded':
                cfg['memory'].update(strict_sources=True,hierarchical={
                    'keep_recent_rounds':1,'episode_rounds':4,'episodes_per_overview':2,
                    'episode_max_chars':180,'overview_max_chars':60,
                    'open_items_max':3,'open_item_max_chars':60})
            dump(folder/'config.json',cfg)
            society=Society(cfg);done=0
            saved_path=folder/'progress.json'
            if saved_path.exists():
                saved=json.loads(saved_path.read_text(encoding='utf-8'))
                society.state=saved['state'];done=saved['completed_rounds']
            api=API(cfg,folder)
            if (folder/'api_accounting.json').exists():
                accounting=json.loads((folder/'api_accounting.json').read_text(encoding='utf-8'))
                api.calls=accounting['calls'];api.cost=accounting['cost_usd']+accounting.get('reserved_usd',0)
            def persist():
                dump(saved_path,{'completed_rounds':done,'state':society.state})
            error=None
            try:
                for t in range(done+1,ROUNDS+1):
                    society.state['round']=t
                    compact(society,AID,api,persist)
                    system,payload=observations[t];payload=copy.deepcopy(payload)
                    a=society.state['agents'][AID]
                    payload['memory']=copy.deepcopy(a['memory']);payload['recent']=copy.deepcopy(a['recent'])
                    api.request(a['model'],'act',system,payload,request_key=f'cost-probe-act:{t}:{AID}')
                    # Observe the identical archived next event, not the newly sampled decision.
                    a['recent'].append(copy.deepcopy(records[t]));done=t;persist()
                    print(name,'round',t,'ledger',round(api.cost,6),flush=True)
            except Exception as exc:
                error=type(exc).__name__+': '+str(exc);persist()
            result={'arm':name,'completed_rounds':done,'planned_rounds':ROUNDS,
                'ledger_cost_usd':api.cost,'by_kind':summarize(folder),'error':error,
                'note':'Paired cost replay on one agent, same archived observations; sampled decisions not applied. Not a social-outcome comparison.'}
            dump(folder/'probe_result.json',result)
            return result

        with ThreadPoolExecutor(max_workers=len(args.arms)) as pool:
            results=list(pool.map(run_arm,args.arms))
        dump(ROOT/'comparison.json',{'source':str(SOURCE),'agent':AID,'rounds':ROUNDS,
            'max_total_probe_budget_usd':.05*len(args.arms),'results':results})
        print(json.dumps(results),flush=True)


if __name__=='__main__':main()
