"""Prepare a four-family/eight-small-model population using saved public quotes."""
import copy
import json
from pathlib import Path
from datetime import datetime,timezone
import tiktoken
import schemas
import sim
import environments
import interaction_controls
from context_codec import pack,serialized

MODELS=[
 ('mistralai/ministral-3b-2512','Mistral',3),
 ('mistralai/ministral-8b-2512','Mistral',8),
 ('qwen/qwen3.5-9b','DeepInfra',9),
 ('google/gemma-3-4b-it','DeepInfra',4),
 ('meta-llama/llama-3.1-8b-instruct','DeepInfra',8),
 ('qwen/qwen-2.5-7b-instruct','Phala',7),
 ('meta-llama/llama-3.2-3b-instruct','Parasail',3),
 ('google/gemma-3-12b-it','DeepInfra',12)]


def main():
    directory=Path('configs/cheap_small8_v4_20261009')
    if directory.exists():raise ValueError('Refusing to overwrite prepared configs')
    reports=Path('reports/cheap_small_model_plan')
    catalog={m['id']:m for m in json.loads((reports/'model_catalog.json').read_text('utf-8'))['data']}
    endpoints=json.loads((reports/'endpoints.json').read_text('utf-8'))
    routes={};prices={};details=[]
    for mid,provider,size in MODELS:
        eligible=[e for e in endpoints[mid]['data']['endpoints'] if e['provider_name']==provider and e.get('status')==0]
        if not eligible:raise ValueError('No available quoted endpoint: '+mid)
        chosen=min(eligible,key=lambda e:float(e['pricing']['prompt'])+float(e['pricing']['completion']))
        strict='structured_outputs' in chosen['supported_parameters'] and 'structured_outputs' in catalog[mid]['supported_parameters']
        if not strict and 'response_format' not in chosen['supported_parameters']:raise ValueError('No supported output format')
        params={'provider_only':[provider],'structured_outputs':strict}
        if mid=='qwen/qwen3.5-9b':params['reasoning']={'enabled':False}
        routes[mid]={'backend':'openrouter','parameters':params};prices[mid]=chosen['pricing']
        details.append({'model':mid,'parameters_B':size,'provider':provider,'strict_schema':strict,
            'input_usd_per_M':float(prices[mid]['prompt'])*1e6,'output_usd_per_M':float(prices[mid]['completion'])*1e6,
            'quantization':chosen.get('quantization'),'quote_source':'https://openrouter.ai/api/v1/models/'+mid+'/endpoints'})
    configs={}
    for env in range(1,8):
        for pressure in (0,1):
            c=json.loads(Path(f'configs/communication_v4_20261009/M{env}_mixed4_p{pressure}.json').read_text('utf-8'))
            c['models']=[m[0] for m in MODELS];c['model_routes']=copy.deepcopy(routes);c['planning_prices']=copy.deepcopy(prices)
            c.pop('survey_proxy_model',None);c.pop('reasoning',None);c.pop('provider_only',None)
            c['structured_outputs']=False  # Specific routes enable strict schemas when supported.
            c['experiment'].update(stage='cheap_small8_prepared_not_run',population='cheap_small8',
                model_counts={mid:1 for mid in c['models']},model_details=copy.deepcopy(details),
                physical_interfaces_note='One member per distinct model; M5 ports balanced by family, with smaller/larger models split across A/B. Rotate ports and seeds before attributing effects to model size.')
            s=sim.Society(c)
            schemas.schema('act',s.observe('a0'),c)
            configs[f'M{env}_cheap_small8_p{pressure}']=c
    directory.mkdir(parents=True)
    for name,c in configs.items():(directory/(name+'.json')).write_text(json.dumps(c,ensure_ascii=False,indent=2)+'\n','utf-8')
    c=configs['M2_cheap_small8_p1'];s=sim.Society(c);s.state['round']=1;view=s.observe('a0')
    encoding=tiktoken.get_encoding('cl100k_base')
    action_prompt=c['actor_system']+'\n'+interaction_controls.actor_help(c,view,environments.action_help(c))+'\n'+serialized(pack(view))
    dialogue_prompt=c['actor_system']+'\n'+interaction_controls.communication_help()+'\n'+serialized(pack(view))
    observed_sizes={'initial_action_prompt_tokens_cl100k':len(encoding.encode(action_prompt,disallowed_special=())),
                    'initial_communication_prompt_tokens_cl100k':len(encoding.encode(dialogue_prompt,disallowed_special=()))}
    pin=sum(float(prices[mid]['prompt']) for mid in c['models'])/8
    pout=sum(float(prices[mid]['completion']) for mid in c['models'])/8
    scenarios=[]
    for comm in (1,3,6,12):
        # Scenario, not a measured forecast. Repeated messages/works increase context.
        calls=400*(1+comm)+144
        cost=calls*(10000*pin+300*pout)
        scenarios.append({'average_comm_outputs_per_agent_round':comm,'planned_calls_including_144_memory_calls':calls,
                          'assumed_mean_input_tokens':10000,'assumed_mean_output_tokens':300,'estimated_usd':round(cost,3)})
    result={'prepared_not_run':True,'default_environment':'M2_cheap_small8_p1','configs':list(configs),
        'quoted_at_utc':datetime.now(timezone.utc).isoformat(),'models':details,'population':[m[0] for m in MODELS],
        'prompt_token_proxy':observed_sizes,'cost_scenarios':scenarios,'budget_per_template_usd':0,
        'notes':['Public API quotes and metadata only; no paid actor or survey calls.',
                 'Quote precision, quantization and provider output-format support vary. Llama 8B uses JSON object validation rather than guaranteed strict decoding.',
                 'Estimates assume all eight agents live for all 50 rounds, equal calls per model, and no cache discounts, retries or questionnaires. Actual input/output lengths and provider billing can differ.',
                 'This is a heterogeneous model/size/version population, not an isolated model-size causal experiment.']}
    (directory/'index.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf-8')
    (reports/'plan.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps({'prepared_configs':len(configs),'launched_runs':0,'prompt_sizes':observed_sizes,'cost_scenarios':scenarios},ensure_ascii=False))


if __name__=='__main__':main()
