"""Export a property-rule candidate and offline evidence; no model/API calls."""
import copy
import argparse
import json
from pathlib import Path

import environments
import mini_world
import property_rules
import sim
import world_rule_library as library
from capability_feasibility import action_order


def main():
    base = Path(__file__).resolve().parent
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',help='Source world configuration; defaults to a local run or the public fixture')
    parser.add_argument('--output',help='Offline output directory')
    args=parser.parse_args()
    source_path = Path(args.source) if args.source else base/'runs/native_luna_alternative_world_4x50_20261012/luna_low_p0_s7/config.json'
    if not source_path.exists() and not args.source:
        source_path=base/'configs/property_rules_v1/example_seed19.json'
    source = json.loads(source_path.read_text('utf-8'))
    candidate = {'definition': mini_world.spec(source), 'generation': source['experiment']['generation']}
    if not candidate['definition'].get('property_rules'):
        candidate = library.with_property_rules(candidate)
    cfg = copy.deepcopy(source)
    cfg['world']['mini_world']['definition'] = candidate['definition']
    cfg['experiment'].update(stage='property_rule_offline_candidate_not_run',
        generation=candidate['generation'], certificate_status='not_lean_certified')
    root = Path(args.output) if args.output else base/'configs/property_rules_v1_20261013/luna_low_p0_s7'
    root.mkdir(parents=True, exist_ok=True)
    def write(name, value):
        (root/name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    s = sim.Society(cfg)
    write('sample_observation.json', s.observe('a0'))
    plan = [{aid: {'tool':'wait'} for aid in s.state['agents']} for _ in range(50)]
    max_residual = 0.
    for t,joint in enumerate(plan,1):
        s.state['round'] = t
        before = environments.physical_snapshot(s.state)
        for aid in action_order(cfg,t,joint):
            s.act(aid,joint[aid])
        s.settle(before)
        assert all(a['alive'] for a in s.state['agents'].values())
        max_residual = max(max_residual, abs(mini_world.accounting(cfg,s.state)['residual']))
    control = sim.Society(cfg)
    r = candidate['definition']['recipes'][0]
    items = list(r['inputs'])
    actions = [{'tool':'gather','item':k,'amount':1} for k in items]
    trace = []
    for t in range(1,16):
        control.state['round'] = t
        before = environments.physical_snapshot(control.state)
        if t <= len(actions):
            action=actions[t-1]
        elif t == len(actions)+1:
            inv=control.state['agents']['a0']['inventory']
            # Deliberately unequal ratio, bounded by real gathered holdings.
            action={'tool':'experiment','facility':r['facility'],'mode':r['mode'],
                'inputs':[{'item':k,'amount': min(inv[k]*.8, .0025 if i==0 else .8)} for i,k in enumerate(items)],'batches':1}
        else:
            action={'tool':'wait'}
        outcome=control.act('a0',action)
        for aid in ['a1','a2','a3']:
            control.act(aid,{'tool':'wait'})
        control.settle(before)
        trace.append({'round':t,'action':action,'outcome':outcome})
        products=[e for h in control.state['environment_history'] for e in h.get('completed_experiments',[])
                  if any(v>0 for v in e['produced'].values())]
        if products:
            break
    assert products, 'No productive legal path'
    assert abs(mini_world.accounting(cfg,control.state)['residual']) < 1e-8
    write('config.json',cfg)
    write('runtime_plan.json',plan)
    write('validation.json',{'scope':'Offline controls, not autonomous discovery evidence or Lean proof',
        'external_api_calls':0,'property_consistency':candidate['generation']['property_rule_validation'],
        'survival_control':{'rounds':50,'alive':4,'maximum_accounting_residual':max_residual},
        'production_control':{'trace':trace,'completed':products,
            'accounting':mini_world.accounting(cfg,control.state)},
        'source_config':str(source_path),'model_run_started':False})
    print(json.dumps({'path':str(root),'survival_rounds':50,'production':products},ensure_ascii=False))


if __name__=='__main__':
    main()
