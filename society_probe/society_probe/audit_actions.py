"""Deterministic rejection audit; check replay against every recorded snapshot."""
import copy
import json
from collections import defaultdict
from pathlib import Path
from sim import Society
import environments
import social_content


def well_formed(action,cfg):
    if not isinstance(action,dict):return False
    action=copy.deepcopy(action)
    if 'args' in action:
        args=action.pop('args')
        if not isinstance(args,dict) or any(k in action and action[k]!=v for k,v in args.items()):return False
        action.update(args)
    tool=action.get('tool');w=cfg['world']
    if tool not in cfg['tools']:return False
    if (tool=='rescue' or cfg.get('social_content') and tool in social_content.TOOLS
            or cfg['world'].get('mechanism') == 'mini_world'):
        import jsonschema
        import schemas
        contract=schemas.schema('act',{'available_tools':[tool],'zones':[]},cfg)['properties']['action']
        try:jsonschema.validate(action,contract)
        except jsonschema.ValidationError:return False
        return True
    names={'wait':set(),'inspect':set(),'repair':set(),'harvest':{'zone','amount'},
           'transfer':{'target','amount'},'seize':{'target','amount'},'contribute':{'amount'},'allocate':{'amount'},'process':{'facility'},
           'create':{'title','content'},'play':{'target','text'},'interfere':{'target'},
           'damage':{'target'},'maintain':{'target'},'read_news':set(),'read_artifact':{'artifact'}}
    names.update(defend={'effort'},secure={'amount'},withdraw={'amount'})
    names.update(propose={'target','own_input','other_input','share'},accept_offer={'offer'},reject_offer={'offer'},cancel_offer={'offer'},request_link={'target'},accept_link={'target'},reject_link={'target'},disconnect={'target'})
    if cfg.get('resource_seizure',{}).get('version')=='seizure_v2':names['seize']|={'effort','resource'}
    if set(action)-{'tool'} != names.get(tool):return False
    if tool in ('harvest','contribute','allocate','transfer','seize','secure','withdraw'):
        amount=action['amount']
        maximum=w.get({'harvest':'max_harvest','contribute':'max_contribution','allocate':'max_effort'}.get(tool,''),float('inf'))
        if cfg.get('mixed_world') and tool in ('harvest','contribute'):maximum=2
        if tool in ('seize','secure','withdraw'):maximum=cfg.get('resource_seizure',{}).get('max_amount',0)
        minimum=1 if tool in ('transfer','seize','secure','withdraw') or (cfg.get('mixed_world') and tool=='contribute') else 0
        if type(amount) is not int or not minimum<=amount<=maximum:return False
    if tool=='harvest':
        count=1 if cfg.get('mixed_world') or w.get('mechanism')=='commons' else len(w['initial_stock'])
        if type(action['zone']) is not int or not 0<=action['zone']<count:return False
    if tool=='process' and (type(action['facility']) is not int or not 0<=action['facility']<w['facilities']):return False
    if tool in ('transfer','seize') and not isinstance(action['target'],str):return False
    if tool=='defend' or (tool=='seize' and cfg.get('resource_seizure',{}).get('version')=='seizure_v2'):
        maximum=cfg['resource_seizure']['max_defense_effort' if tool=='defend' else 'max_attack_effort']
        if type(action['effort']) is not int or not (0 if tool=='defend' else 1)<=action['effort']<=maximum:return False
        if tool=='seize' and action['resource'] not in ('liquid','vault'):return False
    if tool in ('play','damage','maintain','interfere') and not isinstance(action['target'],str):return False
    if tool=='read_artifact' and not isinstance(action['artifact'],str):return False
    if tool=='propose':
        if not isinstance(action['target'],str) or any(type(action[k]) is not int or not 1<=action[k]<=w['max_input'] for k in ('own_input','other_input')) or type(action['share']) is not int or not 0<=action['share']<=100:return False
    if tool in ('accept_offer','reject_offer','cancel_offer') and not isinstance(action['offer'],str):return False
    if tool in ('request_link','accept_link','reject_link','disconnect') and not isinstance(action['target'],str):return False
    for key,limit in ({'title':60,'content':180} if tool=='create' else {'text':180} if tool=='play' else {}).items():
        if not isinstance(action[key],str) or not 0<len(action[key])<=limit:return False
    return True


def audit(folder):
    folder=Path(folder)
    cfg=json.loads((folder/'config.json').read_text(encoding='utf-8'))
    saved=json.loads((folder/'checkpoint.json').read_text(encoding='utf-8'))['state']
    society=Society(cfg);groups=defaultdict(list);snapshots={s['round']:s for s in saved['snapshots']}
    if cfg.get('initial_checkpoint_branch'):
        from checkpoint_interventions import load_branch
        society.state = load_branch(cfg)
    start_round = society.state['round']+1
    for event in saved['events']:groups[event['round']].append(event)
    rejected=[];schema_errors=state_errors=0
    for t in range(start_round,saved['round']+1):
        society.state['round']=t
        import interaction_controls
        interaction_controls.start_round(cfg,society.state)
        if cfg.get('resource_seizure',{}).get('version')=='seizure_v2':
            import resource_seizure
            resource_seizure.start_round(society.state)
        before=environments.physical_snapshot(society.state)
        for event in groups[t]:
            aid=event['agent'];action=event['decision'].get('action');valid=well_formed(action,cfg)
            reason=None
            if not valid:reason='Malformed or out-of-range action'
            else:
                try:society.act(aid,action)
                except (ValueError,KeyError,TypeError) as exc:reason=str(exc)
            expected='action_error' in event['outcome']
            if expected != (reason is not None):raise ValueError('Action audit differs from recorded acceptance')
            if reason:
                category='state_constraint' if valid else 'schema_or_range'
                schema_errors+=not valid;state_errors+=valid
                rejected.append({'round':t,'agent':aid,'action':action,'category':category,'reason':reason})
        society.settle(before if cfg['world'].get('mechanism') else None)
        actual=society.state['agents'];recorded=snapshots[t]['agents']
        for aid,a in actual.items():
            if (abs(a['stock']-recorded[aid]['stock'])>1e-8 or a['energy']!=recorded[aid]['energy']
                    or a['alive']!=recorded[aid]['alive'] or abs(a.get('vault',0)-recorded[aid].get('vault',0))>1e-8):
                raise ValueError('Replayed physical state differs from saved snapshot')
            if cfg.get('social_content'):
                escrow=sum(g['escrow'].get(aid,0) for g in society.state['social_content']['games'].values())
                if abs(escrow-recorded[aid].get('game_escrow',0))>1e-8:raise ValueError('Replayed game escrow differs')
            if cfg['world'].get('mechanism') == 'mini_world' and a['inventory'] != recorded[aid]['inventory']:
                raise ValueError('Replayed material inventory differs')
            if cfg['world'].get('mechanism') == 'mini_world':
                for key in ('material_knowledge', 'device_knowledge', 'private_notes', 'function_knowledge', 'pending_revival'):
                    if key in recorded[aid] and a.get(key, {}) != recorded[aid][key]:
                        raise ValueError('Replayed private knowledge or notes differ')
        if cfg['world'].get('mechanism') == 'mini_world' and 'mini_world_physics' in snapshots[t]:
            expected = snapshots[t]['mini_world_physics']
            if {k: society.state['mini_world'][k] for k in expected} != expected:
                raise ValueError('Replayed world, device, escrow or ledger state differs')
    return {'verified_replay':True,'actions':len(saved['events']),
            'schema_or_range_rejections':schema_errors,'state_constraint_rejections':state_errors,
            'rejections':rejected,'note':'State-constraint rejections are behavioral diagnostics, not syntax failures.'}
