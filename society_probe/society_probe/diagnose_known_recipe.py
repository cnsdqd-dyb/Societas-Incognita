"""Goal-directed known-recipe execution diagnostic; excluded from free-run evidence."""
import argparse
import copy
import hashlib
import json
import os
import sys
import time
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True)
    root=Path(p.parse_args().root).resolve();sys.path.insert(0,str(root/'engine_snapshot'))
    import sim,environments
    from native_codex import NativeCodexAPI,write_json
    from mode_labels import public_mode
    from interface_feedback import record_error
    import interaction_controls
    cfg=json.loads((root/'config.json').read_text('utf-8'))
    manifest=json.loads((root/'manifest.json').read_text('utf-8'))
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    if digest(root/'config.json')!=manifest['config_sha256']:
        raise ValueError('Frozen diagnostic configuration changed')
    for name,sha in manifest['engine_sha256'].items():
        if digest(root/'engine_snapshot'/name)!=sha:raise ValueError('Frozen diagnostic engine changed: '+name)
    mode=public_mode(cfg,'compress')
    # Positive physical control: same world, actual legal gather/gather/experiment.
    control=sim.Society(cfg);control_trace=[]
    for t,action in enumerate([{'tool':'gather','item':'A','amount':1},
        {'tool':'gather','item':'B','amount':1},
        {'tool':'experiment','facility':'F0','mode':mode,'inputs':[{'item':'A','amount':.5},{'item':'B','amount':.5}],'batches':1}],1):
        control.state['round']=t;before=environments.physical_snapshot(control.state)
        result=control.act('a0',action);control.settle(before)
        control_trace.append({'round':t,'action':action,'result':result})
    positive=[e for h in control.state['environment_history'] for e in h.get('completed_experiments',[]) if any(v>0 for v in e['produced'].values())]
    if not positive:raise ValueError('Positive physics control failed; do not test model yet')
    write_json(root/'positive_control.json',{'scope':'Specific fresh-state 3-step execution, not all-state or Lean proof','trace':control_trace,'production':positive})
    output=root/'simulation';output.mkdir(exist_ok=True)
    api=NativeCodexAPI(cfg,output)
    cp=output/'checkpoint.json'
    society=sim.Society(cfg)
    if cp.exists():society.state=json.loads(cp.read_text('utf-8'))['state']
    instruction=('这是已知配方执行能力的短诊断，有明确的外部测试目标，不是自由演化实验。'
        '请通过合法动作实现一次实际有产物的加工。已通过本世界新鲜初始状态的合法动作验证：'
        '在F0使用模式'+mode+'，按1:1投料A与B，可以得到C及副产物W；产量随状态变化。'
        '每种材料仅一项，允许等比例小数投料（如0.5A与0.5B），batches为1。'
        '若尚未持有材料，先自行采集；操作数量不能超过自己的实际可用库存。'
        '其他三位成员在此诊断中由程序等待。仅输出action和communication，communication使用silent。')
    write_json(root/'intervention.json',{'type':'known_recipe_plus_explicit_execution_goal','agent':'a0','published_mode':mode,
        'published_inputs_ratio':{'A':1,'B':1},'other_members':'scripted wait','new_initial_assets':False,
        'exclude_from_free_run_analysis':True,'scope':'Tests execution after explicit instruction, not voluntary adoption or knowledge propagation'})
    write_json(root/'runner_status.json',{'status':'running','pid':os.getpid(),'started':time.time()})
    try:
        for t in range(society.state['round']+1,cfg['rounds']+1):
            society.state['round']=t;observation=society.observe('a0')
            help_text=interaction_controls.actor_help(cfg,observation,sim.SYSTEM)
            decision=api.request('gpt-6-luna','act',instruction+'\n'+help_text,observation,request_key=f'known-recipe:{t}:a0')
            before=environments.physical_snapshot(society.state);outcome={}
            try:outcome['action']=society.act('a0',decision['action'])
            except (ValueError,TypeError,KeyError) as exc:record_error(outcome,'action',exc)
            for aid in ['a1','a2','a3']:society.act(aid,{'tool':'wait'})
            event={'round':t,'agent':'a0','decision':decision,'outcome':outcome}
            society.state['events'].append(event);society.state['agents']['a0']['recent'].append(copy.deepcopy(event))
            society.settle(before)
            write_json(cp,{'state':society.state,'calls':api.calls,'native_cost_usd':None,'diagnostic_only':True})
            products=[e for h in society.state['environment_history'] for e in h.get('completed_experiments',[]) if any(v>0 for v in e['produced'].values())]
            print(json.dumps({'round':t,'action':decision['action'],'positive_production':bool(products)},ensure_ascii=False),flush=True)
            if products:break
        result={'diagnostic_only':True,'exclude_from_free_run_analysis':True,'model':'gpt-6-luna','effort':'low',
            'success':bool(products),'completed_rounds':society.state['round'],'calls':api.calls,'production':products,
            'events':society.state['events'],'intervention':'recipe disclosure plus explicit execution goal; other members wait; no added starting assets'}
        write_json(root/'result.json',result)
        write_json(root/'runner_status.json',{'status':'complete','finished':time.time(),'success':result['success'],'completed_rounds':result['completed_rounds']})
    except Exception as exc:
        write_json(root/'runner_status.json',{'status':'failed','error':str(exc),'finished':time.time()});raise


if __name__=='__main__':main()
