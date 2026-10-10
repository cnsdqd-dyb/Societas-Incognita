"""Threshold, bilateral complementary production and consensual service networks."""
import copy
from collections import deque

TOOLS = {
    'threshold': ['wait', 'contribute', 'transfer'],
    'complementary': ['wait', 'propose', 'accept_offer', 'reject_offer', 'cancel_offer', 'transfer'],
    'network': ['wait', 'request_link', 'accept_link', 'reject_link', 'disconnect', 'transfer'],
}
HELP = {
 'threshold': 'contribute(amount integer 0..max_contribution) pays now, without refund. At settlement each living operator receives private_supply plus benefit_per_alive_member if total inputs reach threshold; otherwise only private_supply. You cannot see this round\'s submitted inputs before choosing.',
 'complementary': 'propose(target opposite interface, own_input integer 1..max_input, other_input integer 1..max_input, share integer 0..100) creates an offer valid for offer_ttl rounds. share is the proposer\'s percentage of output. It costs no stock until accepted. accept_offer(offer ID) consents and atomically pays both input_cost*inputs; output productivity*min(A_input/recipe_A,B_input/recipe_B) arrives at settlement, split by share. Both must be alive and solvent, and neither may have produced already this round. Offers created this round cannot be accepted until next round. reject_offer(offer), cancel_offer(offer) close a received or your own offer. No inputs are escrowed. Each operator has a fixed A or B physical port, not an assigned job. Each living operator also receives private_supply at settlement.',
 'network': 'request_link(target) proposes an undirected physical connection, valid for offer_ttl rounds. accept_link(target) accepts a previously visible request from target; reject_link(target) refuses it. disconnect(target) unilaterally removes a current edge. Requests created this round become acceptable next round. Settlement inflow is private_supply + service_gain*sum(distance_decay**shortest_path_distance) over other reachable living operators; each endpoint pays edge_cost_per_endpoint per edge from liquid stock plus this inflow. If a node cannot afford its edge fees, all its edges are removed, services recomputed, and this repeats until all remaining fees can be paid. Dead nodes have no service connections. Links are physical services, not chat membership or evidence of recognition.',
}

def integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('Integer argument outside its allowed range')
    return value

def initialize(cfg, state):
    w=cfg['world']; f=w['mechanism']; m=state['mechanism_state']
    if w.get('private_supply',0)<0: raise ValueError('Negative private supply')
    if f=='threshold':
        if min(w['threshold'],w['benefit_per_alive_member'],w['max_contribution'])<=0 or w.get('refund_on_failure'):
            raise ValueError('Invalid threshold specification')
    elif f=='complementary':
        if min(w['productivity'],w['recipe_A'],w['recipe_B'],w['input_cost'],w['max_input'],w['offer_ttl'])<=0:
            raise ValueError('Invalid production specification')
        ports=cfg['physical_interfaces']
        if set(ports)!=set(state['agents']) or set(ports.values())!={'A','B'}:raise ValueError('Invalid physical interfaces')
        m.update(offers={}, next_offer=1, production=[])
    else:
        if not 0<w['distance_decay']<=1 or min(w['service_gain'],w['edge_cost_per_endpoint'])<0 or w['offer_ttl']<1:
            raise ValueError('Invalid network specification')
        m.update(edges=[], link_requests={})

def visible_offers(cfg,state,aid):
    t=state['round'];m=state['mechanism_state']
    return {k:copy.deepcopy(o) for k,o in m['offers'].items() if aid in (o['from'],o['to'])
        and o['status']=='open' and o['expires']>=t and state['agents'][o['from']]['alive'] and state['agents'][o['to']]['alive']}

def observation(cfg,state,aid):
    m=state['mechanism_state'];f=m['family'];t=state['round']
    if f=='threshold':return {'previous_contributions':copy.deepcopy(m['last_contributions'])}
    if f=='complementary':
        return {'physical_interfaces':cfg['physical_interfaces'],'your_offers':visible_offers(cfg,state,aid)}
    return {'physical_edges':copy.deepcopy(m['edges']), 'incoming_link_requests':[
        {'from':p['from'],'created':p['created'],'expires':p['expires']} for p in m['link_requests'].values()
        if p['to']==aid and p['expires']>=t and state['agents'][p['from']]['alive']]}

def edge(a,b):return sorted([a,b])

def act(cfg,state,aid,action):
    w=cfg['world'];m=state['mechanism_state'];tool=action['tool'];t=state['round'];a=state['agents'][aid]
    if m['family']=='complementary':
        if tool=='propose':
            target=action.get('target')
            if target==aid or target not in state['agents'] or not state['agents'][target]['alive'] or cfg['physical_interfaces'][target]==cfg['physical_interfaces'][aid]:
                raise ValueError('Offer needs a living operator with the opposite port')
            own=integer(action.get('own_input'),1,w['max_input']);other=integer(action.get('other_input'),1,w['max_input']);share=integer(action.get('share'),0,100)
            k='offer'+str(m['next_offer']);m['next_offer']+=1
            m['offers'][k]={'from':aid,'to':target,'own_input':own,'other_input':other,'share':share,'created':t,'expires':t+w['offer_ttl'],'status':'open'}
            return {'offer_created':k}
        o=m['offers'].get(action.get('offer'))
        if o is None or o['status']!='open' or o['expires']<t:raise ValueError('Offer unavailable or expired')
        if tool=='cancel_offer':
            if o['from']!=aid:raise ValueError('Only the proposer can cancel')
            o['status']='cancelled';return {'offer_cancelled':action['offer']}
        if o['to']!=aid or o['created']>=t:raise ValueError('Offer not previously visible to its recipient')
        if tool=='reject_offer':o['status']='rejected';return {'offer_rejected':action['offer']}
        if tool!='accept_offer':raise ValueError('Unknown offer operation')
        members=(o['from'],o['to']);busy={i for p in m['production'] for i in (p['from'],p['to'])}
        costs=(w['input_cost']*o['own_input'],w['input_cost']*o['other_input'])
        if any(not state['agents'][i]['alive'] or i in busy or state['agents'][i]['stock']+1e-9<c for i,c in zip(members,costs)):
            raise ValueError('One of the production partners is dead, busy or insolvent')
        inputs={cfg['physical_interfaces'][o['from']]:o['own_input'],cfg['physical_interfaces'][o['to']]:o['other_input']}
        output=w['productivity']*min(inputs['A']/w['recipe_A'],inputs['B']/w['recipe_B'])
        for i,c in zip(members,costs):state['agents'][i]['stock']=max(0.,state['agents'][i]['stock']-c)
        o['status']='accepted';production={**o,'offer':action['offer'],'output':output,'input_costs':list(costs)}
        m['production'].append(production)
        return {'production_accepted':copy.deepcopy(production)}
    target=action.get('target')
    if target==aid or target not in state['agents'] or not state['agents'][target]['alive']:raise ValueError('Invalid living link target')
    e=edge(aid,target);key=target+'>'+aid
    if tool=='request_link':
        if e in m['edges']:raise ValueError('Already connected')
        m['link_requests'][aid+'>'+target]={'from':aid,'to':target,'created':t,'expires':t+w['offer_ttl']}
        return {'link_requested':target}
    if tool=='disconnect':
        if e not in m['edges']:raise ValueError('No such physical connection')
        m['edges'].remove(e);return {'disconnected':target}
    p=m['link_requests'].get(key)
    if p is None or p['created']>=t or p['expires']<t:raise ValueError('No previously visible valid request')
    if tool=='accept_link':
        if e in m['edges']:raise ValueError('Already connected')
        m['edges'].append(e);m['edges'].sort()
    elif tool!='reject_link':raise ValueError('Unknown link operation')
    del m['link_requests'][key]
    return {'link_accepted' if tool=='accept_link' else 'link_rejected':target}

def network_flows(w,agents,edges):
    alive=[i for i,a in agents.items() if a['alive']];adj={i:set() for i in alive}
    for a,b in edges:adj[a].add(b);adj[b].add(a)
    flows={};fees={}
    for i in alive:
        distances={i:0};q=deque([i])
        while q:
            v=q.popleft()
            for j in sorted(adj[v]):
                if j not in distances:distances[j]=distances[v]+1;q.append(j)
        flows[i]=w['private_supply']+w['service_gain']*sum(w['distance_decay']**d for j,d in distances.items() if j!=i)
        fees[i]=w['edge_cost_per_endpoint']*len(adj[i])
    return flows,fees

def settle(cfg,state):
    w=cfg['world'];m=state['mechanism_state'];alive=[i for i,a in state['agents'].items() if a['alive']]
    if m['family']=='threshold':
        c={i:m['pending'].get(i,0) for i in alive};active=sum(c.values())+1e-9>=w['threshold'];m['last_contributions']=c
        return {i:w['private_supply']+(w['benefit_per_alive_member'] if active else 0.) for i in alive}, {'contributions':c,'threshold_activated':active,'converted_output':len(alive)*w['benefit_per_alive_member']*active}
    if m['family']=='complementary':
        flows={i:w['private_supply'] for i in alive};transactions=copy.deepcopy(m['production'])
        for p in transactions:
            flows[p['from']]+=p['output']*p['share']/100;flows[p['to']]+=p['output']*(100-p['share'])/100
        m['production']=[]
        return flows,{'production_transactions':transactions,'converted_output':sum(p['output'] for p in transactions)}
    m['edges']=[e for e in m['edges'] if all(i in alive for i in e)];removed=[]
    while True:
        flows,fees=network_flows(w,state['agents'],m['edges'])
        insolvent={i for i in alive if state['agents'][i]['stock']+flows[i]+1e-9<fees[i]}
        if not insolvent:break
        cut=[e for e in m['edges'] if any(i in insolvent for i in e)]
        if not cut:raise RuntimeError('Network clearing failed to remove an edge')
        removed+=cut;m['edges']=[e for e in m['edges'] if e not in cut]
    # Apply income and upkeep together in the generic inflow loop; retain both gross terms.
    return {i:flows[i]-fees[i] for i in alive},{'physical_edges':copy.deepcopy(m['edges']),'gross_service_inflows':flows,'edge_upkeep':fees,'insolvency_removed_edges':removed}
