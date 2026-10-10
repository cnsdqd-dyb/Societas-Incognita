"""Common fictional resource seizure; deterministic, budgeted and auditable."""
import copy

LEGACY={'version':'seizure_v1','attempt_cost':.5,'max_amount':2}
DEFAULT={'version':'seizure_v2','attack_unit_cost':.5,'defense_unit_cost':.5,'max_amount':2,
    'max_attack_effort':2,'max_defense_effort':2,'liquid_accessibility':1.,'vault_accessibility':.25,
    'vault_decay':.05,'energy_scale':5.}
LEGACY_HELP='''seize(target member ID,amount positive integer up to resource_seizure.max_amount): occupies one activity; requires a different living target and enough personal stock to pay attempt_cost before settlement. Pay attempt_cost, then take min(amount,target current stock) without consent. The cost is paid even if the target has no stock. It transfers existing stock, creates none, and does not directly lower energy. The target receives a next-round event notice identifying the actor and actual amount. No automatic retaliation, punishment, reputation or consent is imposed. Invalid target/amount or inability to pay is rejected without payment. Multiple seizures resolve in the same seeded action order as all activities.'''
HELP='''All security actions occupy your one activity slot; choosing them means zero draw effort in the supply contest.
stock is liquid spendable reserve; vault is protected stored reserve, unusable for action costs or personal maintenance until withdrawn. Both are finite existing resources, not new income.
seize(target different living ID,resource "liquid" or "vault",amount integer 1..max_amount,effort integer 1..max_attack_effort): pay attack_unit_cost*effort from existing liquid stock. A=accessibility(resource)*effort*(1+actor_energy/energy_scale); D=(1+target_energy/energy_scale)*(1+target_active_defense). Capture fraction eta=A/(A+D). Actual loot=min(amount,target selected reserve)*eta; subtract it from target and add to actor liquid stock. This is a deterministic fractional capture rule, NOT a random success probability. Even an empty target costs the attack fee. Liquid accessibility=1, vault=.25; low-energy or undefended targets are easier. Multiple attackers share the remaining stock in the seeded resolution order; energy does not change until maintenance.
defend(effort integer 0..max_defense_effort): pay defense_unit_cost*effort now; this defense is active ONLY next round, and affects either resource type. Current-round defense comes from a previous-round action and is not overwritten. No immediate response to an unseen same-round attack. Defending every round consumes actions and liquid stock every round.
secure(amount integer 1..max_amount): move that amount of existing liquid stock to vault; must afford it. withdraw(amount integer 1..max_amount): move min(amount,vault) back into liquid, permitting final fractional residues to be withdrawn. Each takes one action. After supply settlement, vault loses vault_decay=.05 of its remaining contents every round in both pressure conditions; this is real storage dissipation, not personal survival consumption.
Living members' energy and current/next defense are visible through the security index; inspect reveals their liquid and vault balances. Loot notices identifying actor, amount and resource go privately to the target for its next decision. No automatic retaliation, punishment, reputation or relationship is imposed. Invalid or unaffordable actions are rejected without payment. Attack/defense/storage effects are simulated.'''

def help_text(cfg):return LEGACY_HELP if cfg['resource_seizure']['version']=='seizure_v1' else HELP

def configure(cfg,version='seizure_v2'):
    if version not in ('seizure_v1','seizure_v2'):raise ValueError('Unsupported seizure version')
    cfg['resource_seizure']=copy.deepcopy(LEGACY if version=='seizure_v1' else DEFAULT)
    cfg['tools']=[t for t in cfg['tools'] if t not in ('seize','defend','secure','withdraw')]
    for tool in (['seize'] if version=='seizure_v1' else ['seize','defend','secure','withdraw']):
        if tool not in cfg['tools']:cfg['tools'].append(tool)
    return cfg

def initialize(cfg,state):
    rule=cfg.get('resource_seizure')
    if not rule:
        if 'seize' in cfg['tools']:raise ValueError('Seizure tool needs explicit rules')
        return
    if rule.get('version') not in ('seizure_v1','seizure_v2'):raise ValueError('Invalid seizure version')
    numeric=('attempt_cost',) if rule['version']=='seizure_v1' else ('attack_unit_cost','defense_unit_cost','liquid_accessibility','vault_accessibility','energy_scale')
    integer=('max_amount',) if rule['version']=='seizure_v1' else ('max_amount','max_attack_effort','max_defense_effort')
    if any(type(rule.get(k)) not in (int,float) or not 0<rule[k]<float('inf') for k in numeric):raise ValueError('Invalid security coefficients')
    if any(type(rule.get(k)) is not int or rule[k]<1 for k in integer):raise ValueError('Invalid security action bounds')
    required={'seize'} if rule['version']=='seizure_v1' else {'seize','defend','secure','withdraw'}
    if not required<=set(cfg['tools']):raise ValueError('Missing security tools')
    if rule['version']=='seizure_v2':
        if type(rule.get('vault_decay')) not in (int,float) or not 0<=rule['vault_decay']<1:raise ValueError('Invalid storage decay')
        for a in state['agents'].values():a.update(vault=0.,defense_schedule={})
    state['seizure_events']=[]
    if rule['version']=='seizure_v2':
        state['security_history']=[]
        start_round(state)

def active_defense(state,aid):return state['agents'][aid].get('defense_schedule',{}).get(str(state['round']),0)

def start_round(state):
    if any(x['round']==state['round'] for x in state.get('security_history',[])):return
    state['security_history'].append({'round':state['round'],'agents':{
        aid:{k:copy.deepcopy(a[k]) for k in ('stock','vault','energy','alive','defense_schedule')}
        for aid,a in state['agents'].items()}})

def capture_parameters(cfg,state,actor,target,resource,effort,defense_override=None):
    rule=cfg['resource_seizure']
    attack=rule[resource+'_accessibility']*effort*(1+state['agents'][actor]['energy']/rule['energy_scale'])
    g=active_defense(state,target) if defense_override is None else defense_override
    if cfg['world'].get('mechanism') == 'mini_world':
        import functional_effects
        g += functional_effects.live_bonus(state, target, 'shield')
    defense=(1+state['agents'][target]['energy']/rule['energy_scale'])*(1+g)
    return attack,defense,attack/(attack+defense)

def local_attack_bounds(cfg,state,aid):
    """Exact snapshot attack-or-wait net wealth change, excluding all other dynamics."""
    rule=cfg['resource_seizure'];options=[{'tool':'wait','net_wealth_change':0.,'loot':0.,'cost':0.}]
    for target,victim in state['agents'].items():
        if target==aid or not victim['alive']:continue
        for resource,balance in [('liquid','stock'),('vault','vault')]:
            for amount in range(1,rule['max_amount']+1):
                for effort in range(1,rule['max_attack_effort']+1):
                    cost=effort*rule['attack_unit_cost']
                    if cost>state['agents'][aid]['stock']+1e-9:continue
                    _,_,fraction=capture_parameters(cfg,state,aid,target,resource,effort)
                    loot=min(amount,victim[balance])*fraction
                    options.append({'tool':'seize','target':target,'resource':resource,'amount':amount,'effort':effort,
                        'loot':loot,'cost':cost,'net_wealth_change':loot-cost})
    best=max(options,key=lambda x:x['net_wealth_change']);worst=min(options,key=lambda x:x['net_wealth_change'])
    return {'lower':worst['net_wealth_change'],'upper':best['net_wealth_change'],'worst':worst,'best':best,
        'enumerated_actions':len(options),'scope':'Conditional snapshot attack-or-wait; no other actors, supply, storage decay, maintenance or future reactions. Not a full environment trajectory bound.'}

def conditional_defense_bounds(cfg,state,target,attacks):
    """Fixed threat-sequence diagnostic; next-round balance held fixed across postures."""
    rule=cfg['resource_seizure'];options=[]
    for g in range(rule['max_defense_effort']+1):
        remaining={'liquid':state['agents'][target]['stock'],'vault':state['agents'][target]['vault']};loss=0.
        for attack in attacks:
            if attack['target']!=target:continue
            resource=attack['resource'];_,_,fraction=capture_parameters(cfg,state,attack['actor'],target,resource,attack['effort'],g)
            taken=min(attack['amount'],remaining[resource])*fraction;remaining[resource]-=taken;loss+=taken
        cost=rule['defense_unit_cost']*g
        options.append({'defense_effort':g,'loss':loss,'preparation_cost':cost,'loss_plus_cost':loss+cost})
    return {'options':options,'best':min(options,key=lambda x:x['loss_plus_cost']),
        'worst':max(options,key=lambda x:x['loss_plus_cost']),
        'scope':'Fixed next-round balances, energies and ordered attacks; preparation cost is a separate prior-round expense. Not an equilibrium or dynamic feasible bound; does not assume actors optimize it.'}

def observation(cfg,state):
    if cfg['resource_seizure']['version']=='seizure_v1':return {}
    return {'resource_security':{aid:{'energy':a['energy'],'active_defense':active_defense(state,aid),
        'next_round_defense':a['defense_schedule'].get(str(state['round']+1),0)} for aid,a in state['agents'].items() if a['alive']}}

def settle_storage(cfg,state):
    if cfg['resource_seizure']['version']=='seizure_v1':return {}
    losses={}
    for aid,a in state['agents'].items():
        if not a['alive']:continue
        loss=a['vault']*cfg['resource_seizure']['vault_decay'];a['vault']-=loss;losses[aid]=loss
        a['defense_schedule']={r:g for r,g in a['defense_schedule'].items() if int(r)>state['round']}
    return {'vault_storage_loss':sum(losses.values()),'vault_storage_loss_by_member':losses}

def act(cfg,state,aid,action):
    rule=cfg.get('resource_seizure');a=state['agents'][aid]
    tool=action.get('tool')
    if not rule or tool not in cfg['tools'] or not a['alive']:raise ValueError('Security action unavailable')
    if rule['version']=='seizure_v2' and tool!='seize':
        if tool=='defend':
            effort=action.get('effort')
            if type(effort) is not int or not 0<=effort<=rule['max_defense_effort']:raise ValueError('Invalid defense effort')
            cost=rule['defense_unit_cost']*effort
            if a['stock']+1e-9<cost:raise ValueError('Unaffordable defense')
            a['stock']=max(0.,a['stock']-cost);a['defense_schedule'][str(state['round']+1)]=effort
            return {'defense_effort':effort,'paid':cost,'active_round':state['round']+1}
        if tool in ('secure','withdraw'):
            amount=action.get('amount')
            if type(amount) is not int or not 1<=amount<=rule['max_amount']:raise ValueError('Invalid storage amount')
            if tool=='secure':
                if a['stock']+1e-9<amount:raise ValueError('Unaffordable storage')
                a['stock']=max(0.,a['stock']-amount);a['vault']+=amount;return {'secured':amount,'paid':0}
            amount=min(float(amount),a['vault']);a['vault']-=amount;a['stock']+=amount;return {'withdrawn':amount,'paid':0}
        raise ValueError('Unknown security action')
    target,amount=action.get('target'),action.get('amount')
    if not isinstance(target,str) or target==aid or target not in state['agents'] or not state['agents'][target]['alive']:
        raise ValueError('Invalid seizure target')
    if type(amount) is not int or not 1<=amount<=rule['max_amount']:raise ValueError('Invalid seizure amount')
    fraction=1.;resource='liquid'
    if rule['version']=='seizure_v2':
        effort,resource=action.get('effort'),action.get('resource')
        if type(effort) is not int or not 1<=effort<=rule['max_attack_effort'] or resource not in ('liquid','vault'):raise ValueError('Invalid attack parameters')
        cost=rule['attack_unit_cost']*effort
        attack,defense,fraction=capture_parameters(cfg,state,aid,target,resource,effort)
    else:cost=rule['attempt_cost']
    if a['stock']+1e-9<cost:raise ValueError('Unaffordable seizure')
    victim=state['agents'][target];balance='stock' if resource=='liquid' else 'vault'
    taken=min(float(amount),victim[balance])*fraction
    a['stock']=max(0.,a['stock']-cost)+taken;victim[balance]=max(0.,victim[balance]-taken)
    record={'round':state['round'],'actor':aid,'target':target,'requested':amount,
        'seized':taken,'paid':cost,'success':taken>0}
    if rule['version']=='seizure_v2':record.update(resource=resource,effort=effort,capture_fraction=fraction,attack_strength=attack,defense_strength=defense)
    state['seizure_events'].append(record)
    victim['inbox'].append({'round':state['round'],'kind':'resource_seizure','from':aid,
        'seized':taken,'requested':amount,'resource':resource,'evidence_type':'direct_environment_notification'})
    return {k:v for k,v in record.items() if k not in ('round','actor')}
