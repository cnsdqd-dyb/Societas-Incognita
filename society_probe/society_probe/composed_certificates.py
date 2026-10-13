"""Kernel-checked interval transition certificates for deterministic mini-worlds.

The adapter compiles world equations and a fixed action schedule into a numeric
constraint graph. Lean checks every arithmetic enclosure and branch, without
trusting Python-computed values. Decimal rational interval endpoints are rounded
outwards, preventing denominator explosion in ecological feedback. This is not
a formal proof of the Python adapter or IEEE-754 interpreter equivalence.
"""
import copy
import hashlib
import json
import math
from fractions import Fraction as F
from pathlib import Path

import capability_devices
import mini_world
import world_rule_engine
from capability_feasibility import action_order


class Unsupported(ValueError): pass


class Wire:
    def __init__(self, index, lo, hi): self.index, self.lo, self.hi = index, lo, hi


class Circuit:
    def __init__(self, digits=18):
        self.scale = 10**digits; self.nodes = []; self.cache = {}; self.guards = []; self.live = []

    def const(self, value):
        q = F(str(value))
        if q not in self.cache:
            self.cache[q] = self.emit('constant', None, None, q, q, q)
        return self.cache[q]

    def emit(self, op, a, b, lo, hi, constant=None):
        w = Wire(len(self.nodes), lo, hi)
        self.nodes.append((op, a, b, w, constant)); return w

    def op(self, op, a, b=None):
        if not isinstance(a, Wire): a = self.const(a)
        if b is not None and not isinstance(b, Wire): b = self.const(b)
        if op == 'add': lo, hi = a.lo+b.lo, a.hi+b.hi
        elif op == 'sub': lo, hi = a.lo-b.hi, a.hi-b.lo
        elif op == 'mul':
            products = [x*y for x in (a.lo,a.hi) for y in (b.lo,b.hi)]; lo,hi = min(products),max(products)
        elif op == 'div':
            if b.lo <= 0 <= b.hi: raise Unsupported('Interval denominator contains zero')
            products = [x/y for x in (a.lo,a.hi) for y in (b.lo,b.hi)]; lo,hi = min(products),max(products)
        elif op == 'min': lo,hi = min(a.lo,b.lo),min(a.hi,b.hi)
        elif op == 'max': lo,hi = max(a.lo,b.lo),max(a.hi,b.hi)
        elif op == 'neg': lo,hi = -a.hi,-a.lo
        elif op == 'floor':
            lo,hi = F(math.floor(a.lo)),F(math.floor(a.hi))
            if lo != hi: raise Unsupported('Floor decision is ambiguous within the certified interval')
        elif op in ('lt','le','eq','truth'):
            if op == 'lt': truth = True if a.hi < b.lo else False if a.lo >= b.hi else None
            elif op == 'le': truth = True if a.hi <= b.lo else False if a.lo > b.hi else None
            elif op == 'eq': truth = True if a.lo == a.hi == b.lo == b.hi else False if a.hi < b.lo or b.hi < a.lo else None
            else: truth = False if a.lo == a.hi == 0 else True if a.hi < 0 or a.lo > 0 else None
            if truth is None: raise Unsupported('Condition is ambiguous within the certified interval')
            lo = hi = F(int(truth))
        else: raise Unsupported('Unsupported circuit operation '+op)
        # Singleton exact arithmetic is preserved; only interval values are rounded.
        if lo != hi:
            lo = F(math.floor(lo*self.scale), self.scale)
            hi = F(math.ceil(hi*self.scale), self.scale)
        elif lo.denominator.bit_length() > 160:
            lo,hi = F(math.floor(lo*self.scale),self.scale),F(math.ceil(hi*self.scale),self.scale)
        return self.emit(op,a,b,lo,hi)

    def require(self, a, message):
        p = self.op('truth', a)
        if p.lo != 1: raise Unsupported(message)
        self.guards.append(p); return True

    def branch(self, a):
        p = self.op('truth',a)
        self.guards.append(self.op('eq', p, p.lo))
        return p.lo == 1

    def clip(self, a, lo, hi): return self.op('min',hi,self.op('max',lo,a))


class Compiler:
    def __init__(self, cfg):
        world_rule_engine.validate(mini_world.spec(cfg))
        if mini_world.spec(cfg).get('production_semantics') == 'limiting_reagent_v1':
            raise Unsupported('Limiting-reagent settlement requires a new certificate compiler; old certificates must not be reused')
        if mini_world.spec(cfg)['noise']['distribution'] != 'none': raise Unsupported('Noise requires a separate robust or fixed-noise certificate')
        if any(cfg.get(k) for k in ('social_content','resource_seizure','open_activities','mixed_world','open_contest')) or cfg.get('rescue',{}).get('enabled'):
            raise Unsupported('Social/security/rescue extensions are outside this checker')
        self.cfg=cfg; self.d=mini_world.spec(cfg); self.c=Circuit(); C=self.c.const
        def supported(x):
            if isinstance(x,dict):
                if x.get('op')=='exp': raise Unsupported('Transcendental exp is outside the rational interval checker')
                for v in x.values(): supported(v)
            elif isinstance(x,list):
                for v in x: supported(v)
        supported(self.d)
        if not self.ids: raise Unsupported('Certificate needs a nonempty population')
        self.round=0; self.stock={a:C(cfg['world'].get('initial_personal_stock',4)) for a in self.ids}
        self.health={a:C(5) for a in self.ids}
        self.inv={a:{k:C(self.d.get('initial_inventory',{}).get(k,0)) for k in self.d['resources']} for a in self.ids}
        self.vars={k:C(v['initial']) for k,v in self.d['variables'].items()}
        self.pools={k:C(v['initial']) for k,v in self.d['pools'].items()}; self.reserve=C(self.d['initial_reserve'])
        self.devices={}; self.next_device=1; self.notes={a:{} for a in self.ids}; self.pending={}; self.schedulers={}; self.activity={}; self.rows=[]; self.action_rows=[]
        self.function_knowledge={aid:set() for aid in self.ids}
        self.discover_functions()

    def discover_functions(self):
        for aid in self.ids:
            for entry in self.d.get('combination_functions', []):
                if entry['id'] in self.function_knowledge[aid]: continue
                if all(self.inv[aid][k].lo >= F(str(n)) for k,n in entry['requires'].items()):
                    for k,n in entry['requires'].items():
                        self.c.require(self.c.op('le',n,self.inv[aid][k]),'Uncertified combination discovery')
                    self.function_knowledge[aid].add(entry['id'])

    @property
    def ids(self): return [f'a{i}' for i in range(len(self.cfg['models']))]

    def sum(self, values):
        result=self.c.const(0)
        for v in values: result=self.c.op('add',result,v)
        return result

    def ctx(self):
        c={'round':self.c.const(self.round),'living':self.c.const(len(self.ids)), 'liquid_total':self.sum(self.stock.values())}
        c.update({'state.'+k:v for k,v in self.vars.items()}); c.update({'pool.'+k:v for k,v in self.pools.items()})
        for name in ('produced','harvested','consumed'):
            for k in self.d['resources']: c['activity.'+name+'.'+k]=self.activity.get((name,k),self.c.const(0))
        for k in self.d['facilities']:
            c['activity.submitted.'+k]=self.activity.get(('submitted',k),self.c.const(0))
        return c

    def expr(self, e, ctx):
        if type(e) in (int,float): return self.c.const(e)
        if 'ref' in e: return ctx[e['ref']]
        op=e['op']; args=[self.expr(x,ctx) for x in e['args']]; c=self.c
        if op in ('add','mul','min','max'):
            out=args[0]
            for a in args[1:]: out=c.op(op,out,a)
        elif op in ('sub','div','lt','le','eq'): out=c.op(op,args[0],args[1])
        elif op in ('gt','ge'): out=c.op('lt' if op=='gt' else 'le',args[1],args[0])
        elif op=='clamp':
            c.require(c.op('le',args[1],args[2]),'Reversed clamp bounds'); out=c.clip(args[0],args[1],args[2])
        elif op=='pow':
            out=c.const(1)
            for _ in range(e['args'][1]): out=c.op('mul',out,args[0])
        elif op in ('and','or'):
            truth=[c.op('truth',x) for x in args]; out=truth[0]
            for x in truth[1:]: out=c.op('min' if op=='and' else 'max',out,x)
        elif op=='not': out=c.op('sub',1,c.op('truth',args[0]))
        else: raise Unsupported('Equation operator is not formally covered: '+op)
        c.require(c.op('le',-10**9,out),'Equation lower bound exceeded')
        c.require(c.op('le',out,10**9),'Equation upper bound exceeded')
        return out

    def add_activity(self,name,item,amount):
        k=(name,item); self.activity[k]=self.c.op('add',self.activity.get(k,self.c.const(0)),amount)

    def pay(self,aid,amount,item='ENERGY'):
        c=self.c; balance=self.stock[aid] if item=='ENERGY' else self.inv[aid][item]
        c.require(c.op('le',amount,c.op('add',balance,'0.000000001')),'Insufficient certified assets')
        new=c.op('max',0,c.op('sub',balance,amount))
        if item=='ENERGY': self.stock[aid]=new
        else: self.inv[aid][item]=new

    def move(self,aid,item,amount):
        if item=='ENERGY': self.stock[aid]=self.c.op('add',self.stock[aid],amount)
        else: self.inv[aid][item]=self.c.op('add',self.inv[aid][item],amount)

    def energy(self,inputs):
        return self.sum(self.c.op('mul',n,self.d['resources'][k]['energy_value']) for k,n in inputs.items())

    def active(self,device,aid):
        p=device.get('pending_service'); s=p if p and self.round>=p['active_from'] else device
        return aid in s['users'] and s['active_from']<=self.round<s['active_until']

    def capability(self,aid,name):
        if name=='manufacturing': return any(self.active(v,aid) and v['recipe']['capabilities'].get(name) for v in self.devices.values())
        return min(100000,sum(v['recipe']['capabilities'].get(name,0) for v in self.devices.values() if self.active(v,aid)))

    def act(self,aid,a):
        from audit_actions import well_formed
        if not well_formed(a,self.cfg): raise Unsupported('Malformed or unavailable action')
        c=self.c; tool=a['tool']; d=self.d
        c.require(c.op('lt',0,self.health[aid]),'Inactive actor')
        if tool in ('wait','inspect'): return
        if tool=='use_function':
            if a['function'] not in self.function_knowledge[aid]:
                raise Unsupported('Combination function has not been discovered')
            entry=next(e for e in d.get('combination_functions',[]) if e['id']==a['function'])
            if not a['confirm']: return
            if entry['kind'] != 'world_state':
                raise Unsupported('Functional services/security effects require a separate certificate adapter')
            if a['target'] != 'world': raise Unsupported('Invalid world function target')
            for k,n in entry['requires'].items():
                c.require(c.op('le',n,self.inv[aid][k]),'Combination materials missing')
            context=self.ctx()
            self.pay(aid,c.const(entry['energy_cost']))
            for k,n in entry['consume'].items():
                self.pay(aid,c.const(n),k); self.add_activity('consumed',k,c.const(n))
            for field,e in entry['effects'].items():
                self.vars[field]=c.clip(c.op('add',self.vars[field],self.expr(e,context)),d['variables'][field]['min'],d['variables'][field]['max'])
            return
        if tool=='gather':
            k=a['item']
            if k not in self.pools: raise Unsupported('No pool')
            rate=c.clip(self.expr(d['pools'][k].get('harvest_efficiency',1),self.ctx()),0,1)
            n=c.op('min',a['amount'],self.pools[k]); self.pools[k]=c.op('sub',self.pools[k],n)
            self.move(aid,k,c.op('mul',n,rate)); self.add_activity('harvested',k,n); return
        if tool=='liquidate':
            if a['amount'] > d['resources'][a['item']].get('liquidation_limit',d['max_quantity']):
                raise Unsupported('Material discharge power exceeded')
            k=a['item']; n=c.const(a['amount']); self.pay(aid,n,k)
            self.move(aid,'ENERGY',c.op('mul',c.op('mul',n,d['resources'][k]['energy_value']),d['resources'][k]['liquidation_efficiency']))
            self.add_activity('consumed',k,n); return
        if tool in ('transfer','give_item'):
            target=a['target']; k=a.get('item','ENERGY')
            if target==aid or target not in self.ids: raise Unsupported('Invalid recipient')
            n=c.const(a['amount']); self.pay(aid,n,k); self.move(target,k,n); return
        if tool=='use_item':
            k=a['item']; effects=d['resources'][k].get('use_effects',{})
            if not effects:
                c.require(c.op('le',a['amount'],c.op('add',self.inv[aid][k],'0.000000001')),'Insufficient certified assets')
            if effects:
                context=self.ctx(); self.pay(aid,c.const(a['amount']),k)
                for field,e in effects.items(): self.vars[field]=c.clip(c.op('add',self.vars[field],c.op('mul',a['amount'],self.expr(e,context))),d['variables'][field]['min'],d['variables'][field]['max'])
                self.add_activity('consumed',k,c.const(a['amount']))
            return
        if tool=='experiment':
            if aid in self.pending: raise Unsupported('Already has a pending experiment')
            self.add_activity('submitted',a['facility'],c.const(1))
            inputs=mini_world.parse_basket(self.cfg,a['inputs']); batches=a['batches']
            for k,n in inputs.items(): self.pay(aid,c.const(n*batches),k)
            self.pay(aid,c.const(d['experiment_cost']))
            self.pending[aid]={'facility':a['facility'],'mode':a['mode'],'inputs':inputs,'batches':batches}
            if any('service_capacity' in f for f in d['facilities'].values()) or mini_world.functional_effects.enabled(self.cfg):
                self.pending[aid].update(submitted_round=self.round,escrow={k:c.const(n*batches) for k,n in inputs.items()})
            return
        if tool=='assemble_device':
            inputs=mini_world.parse_basket(self.cfg,a['inputs'])
            for k,n in inputs.items(): c.require(c.op('le',n,c.op('add',self.inv[aid][k],'0.000000001')),'Insufficient assembly material')
            self.pay(aid,c.const(d['experiment_cost']))
            r=next((r for r in d.get('device_recipes',[]) if r['facility']==a['facility'] and r['mode']==a['mode'] and r['inputs']==inputs),None)
            if r:
                if len(self.devices)>=128: raise Unsupported('Device bound exceeded')
                self.pay(aid,c.const(r['build_cost']))
                for k,n in inputs.items(): self.pay(aid,c.const(n),k)
                key='device'+str(self.next_device); self.next_device+=1
                self.devices[key]={'owner':aid,'recipe':r,'embedded_energy':c.op('mul',c.op('add',self.energy(inputs),r['build_cost']),r['retained_fraction']),
                    'users':[],'active_from':0,'active_until':0}
            return
        if tool in ('write_note','read_note'):
            capacity=min(100000,d.get('note_base_capacity',256)+self.capability(aid,'note_capacity'))
            if tool=='write_note':
                n=len(a['text']); size=sum(v for k,v in self.notes[aid].items() if k!=a['key'])+n
                c.require(c.op('le',size,capacity),'Note capacity exceeded'); self.notes[aid][a['key']]=n
            else:
                if a['key'] not in self.notes[aid]: raise Unsupported('Unknown note')
                c.require(c.op('le',self.notes[aid][a['key']],capacity),'Read capacity exceeded')
            return
        if tool in ('activate_device','give_device','dismantle_device','measure'):
            v=self.devices.get(a['device'])
            if v is None: raise Unsupported('Unknown device')
            r=v['recipe']
            if tool=='measure':
                if not self.active(v,aid) or a['field'] not in r['capabilities'].get('measurements',{}): raise Unsupported('Unauthorized measurement')
                return # The noisy readout has no physical effect; readout accuracy is not certified.
            if v['owner']!=aid: raise Unsupported('Not device owner')
            if tool=='activate_device':
                users=a['targets']
                if not 1<=len(users)<=r['max_users'] or len(set(users))!=len(users) or not set(users)<=set(self.ids): raise Unsupported('Invalid service recipients')
                self.pay(aid,c.op('mul',r['fuel_per_recipient'],len(users)))
                p=v.get('pending_service')
                if p and self.round>=p['active_from']: v.update(p)
                v['pending_service']={'users':users[:],'active_from':self.round+1,'active_until':self.round+1+r['duration']}
            elif tool=='give_device':
                if a['target']==aid or a['target'] not in self.ids: raise Unsupported('Invalid device recipient')
                v.update(owner=a['target'],users=[],active_from=0,active_until=0); v.pop('pending_service',None)
            else:
                self.move(aid,'ENERGY',c.op('mul',v['embedded_energy'],r['recovery_efficiency'])); del self.devices[a['device']]
            return
        raise Unsupported('Action not covered by composed checker: '+tool)

    def settle(self):
        c=self.c; d=self.d; context=self.ctx(); effects={}; produced={}
        import mechanism_extensions
        selected,waiting=mechanism_extensions.service_jobs(d,{'pending':self.pending,'facility_schedulers':self.schedulers},self.round)
        import production_semantics
        proportional=production_semantics.proportional(d)
        for aid in selected:
            p=self.pending[aid]
            r,factor=production_semantics.match(d,p['facility'],p['mode'],p['inputs'])
            batches=p['batches']; n=factor*batches
            inputs=p.get('escrow',{k:c.const(x*batches) for k,x in p['inputs'].items()})
            matched=r is not None and c.branch(self.expr(r['condition'],context)) and (not r.get('requires_capability') or self.capability(aid,r['requires_capability']))
            if matched and 'escrow' in p:
                matched=all(c.branch(c.op('eq',inputs[k],c.const(x*batches))) for k,x in p['inputs'].items())
            if matched: matched=c.branch(c.op('le',r.get('min_processing_extent',d['facilities'][p['facility']].get('min_processing_extent',0)),n))
            cost=c.op('mul',n,c.op('max',0,self.expr(r.get('operating_cost',r['energy_cost']),context))) if r is not None else c.const(0)
            if matched: matched=c.branch(c.op('le',cost,c.op('add',self.stock[aid],'0.000000001')))
            if not matched:
                produced[aid]={}
                for k,x in inputs.items(): self.move(aid,k,x)
                self.discover_functions()
                continue
            self.pay(aid,cost); available=c.op('add',self.energy(inputs),cost)
            raw=c.op('mul',c.op('max',0,self.expr(r['yield'],context)),n)
            funded=c.op('div',available,d['resources'][r['output']]['energy_value'])
            out=c.op('min',raw,funded) if proportional else c.op('min',c.op('floor',c.op('add',raw,'0.000000001')),c.op('floor',c.op('add',funded,'0.000000001')))
            produced[aid]={r['output']:out}
            self.move(aid,r['output'],out); self.add_activity('produced',r['output'],out)
            remaining=c.op('max',0,c.op('sub',available,c.op('mul',out,d['resources'][r['output']]['energy_value'])))
            for item,yield_ in r.get('byproducts',{}).items():
                value=d['resources'][item]['energy_value']
                raw=c.op('mul',c.op('max',0,self.expr(yield_,context)),n)
                funded=c.op('div',remaining,value)
                count=c.op('min',raw,funded) if proportional else c.op('min',c.op('floor',c.op('add',raw,'0.000000001')),c.op('floor',c.op('add',funded,'0.000000001')))
                produced[aid][item]=count; remaining=c.op('sub',remaining,c.op('mul',count,value))
                self.move(aid,item,count); self.add_activity('produced',item,count)
            for k,x in inputs.items(): self.add_activity('consumed',k,x)
            for k,e in r.get('effects',{}).items(): effects[k]=c.op('add',effects.get(k,c.const(0)),c.op('mul',n,self.expr(e,context)))
            self.discover_functions()
        self.pending=waiting
        for k,e in effects.items(): self.vars[k]=c.clip(c.op('add',self.vars[k],e),d['variables'][k]['min'],d['variables'][k]['max'])
        context=self.ctx()
        self.vars={k:c.clip(self.expr(v['next'],context),v['min'],v['max']) for k,v in d['variables'].items()}
        context=self.ctx(); depletion={k:c.op('min',self.pools[k],c.op('max',0,self.expr(p.get('depletion',0),context))) for k,p in d['pools'].items()}
        recycled=self.sum(c.op('mul',c.op('mul',n,d['resources'][k]['energy_value']),d['pools'][k].get('recycled_fraction',0)) for k,n in depletion.items())
        for k,n in depletion.items(): self.pools[k]=c.op('sub',self.pools[k],n)
        self.reserve=c.op('min',d['reserve_capacity'],c.op('add',self.reserve,recycled))
        context=self.ctx()
        rates={f['id']:c.op('max',0,self.expr(f['rate'],context)) for f in d.get('pool_flows',[])}
        for f in d.get('pool_flows',[]):
            src,dst=f['source'],f['target']; ratio=d['resources'][src]['energy_value']*f.get('efficiency',1)/d['resources'][dst]['energy_value']
            room=c.op('max',0,c.op('sub',d['pools'][dst]['capacity'],self.pools[dst]))
            moved=c.op('min',c.op('min',rates[f['id']],self.pools[src]),c.op('div',room,ratio)) if ratio else c.const(0)
            self.pools[src]=c.op('sub',self.pools[src],moved)
            self.pools[dst]=c.op('add',self.pools[dst],c.op('mul',moved,ratio))
        context=self.ctx(); requested={k:c.op('max',0,self.expr(p['regeneration'],context)) for k,p in d['pools'].items()}
        external=c.op('max',0,self.expr(d['external_inflow'],context)); self.reserve=c.op('min',d['reserve_capacity'],c.op('add',self.reserve,external))
        demands={k:c.op('mul',c.op('min',requested[k],c.op('sub',d['pools'][k]['capacity'],self.pools[k])),d['resources'][k]['energy_value']) for k in self.pools}
        required=self.sum(demands.values())
        # Algebraically equivalent full-funding case, including zero demand:
        # every demand is zero when their nonnegative sum is zero.
        if required.hi <= self.reserve.lo:
            c.require(c.op('le',required,self.reserve),'Regeneration funding bound')
            factor=c.const(1)
        else:
            factor=c.op('min',1,c.op('div',self.reserve,required)) if c.branch(required) else c.const(0)
        for k,x in demands.items():
            self.pools[k]=c.clip(c.op('add',self.pools[k],c.op('div',c.op('mul',x,factor),d['resources'][k]['energy_value'])),0,d['pools'][k]['capacity'])
        self.reserve=c.op('max',0,c.op('sub',self.reserve,c.op('mul',required,factor)))
        for k,r in d['resources'].items():
            for aid in self.ids: self.inv[aid][k]=c.op('sub',self.inv[aid][k],c.op('mul',self.inv[aid][k],r['decay']))
            if k in self.pools: self.pools[k]=c.op('sub',self.pools[k],c.op('mul',self.pools[k],r['decay']))
            for p in self.pending.values():
                if k in p.get('escrow',{}):
                    p['escrow'][k]=c.op('sub',p['escrow'][k],c.op('mul',p['escrow'][k],r['decay']))
        if self.cfg['world']['survival_pressure']:
            for aid in self.ids:
                paid=c.op('min',self.cfg['world']['consumption'],self.stock[aid]); self.stock[aid]=c.op('max',0,c.op('sub',self.stock[aid],paid))
                met=c.branch(c.op('le',self.cfg['world']['consumption'],c.op('add',paid,'0.000000001')))
                self.health[aid]=c.op('min',5,c.op('add',self.health[aid],1)) if met else c.op('sub',self.health[aid],1)
        for aid in self.ids:
            c.require(c.op('lt',0,self.health[aid]),'Witness has a death'); c.live.append(self.health[aid])
        self.activity={}
        self.rows.append({'stock':self.stock.copy(),'health':self.health.copy(),'inventory':copy.deepcopy(self.inv),'variables':self.vars.copy(),'pools':self.pools.copy(),'reserve':self.reserve,'produced':produced,
            'function_knowledge':copy.deepcopy(self.function_knowledge),
            'devices':copy.deepcopy(self.devices),'pending':copy.deepcopy(self.pending),'schedulers':copy.deepcopy(self.schedulers)})

    def run(self,plan):
        for joint in plan:
            self.round+=1
            if set(joint)!=set(self.ids): raise Unsupported('Exactly one action per member is required')
            for aid in action_order(self.cfg,self.round,joint):
                self.act(aid,joint[aid])
                self.discover_functions()
                self.action_rows.append(copy.deepcopy({'round':self.round,'actor':aid,'stock':self.stock,
                    'function_knowledge':self.function_knowledge,
                    'health':self.health,'inventory':self.inv,'variables':self.vars,'pools':self.pools,
                    'reserve':self.reserve,'devices':self.devices,'notes':self.notes,'pending':self.pending,'schedulers':self.schedulers}))
            self.settle()
            self.discover_functions()
        return self


def qsource(q): return f'⟨({q.numerator}), {q.denominator}⟩'


def configuration_digest(cfg):
    bound=copy.deepcopy(cfg); bound.pop('survival_certificate',None)
    return hashlib.sha256(json.dumps(bound,sort_keys=True).encode()).hexdigest()


def export(cfg,plan,path,semantic=False):
    if not isinstance(plan,list) or not 1<=len(plan)<=1000: raise Unsupported('Certificate horizon must be 1..1000')
    compiler=Compiler(cfg).run(plan); c=compiler.c
    # Cross-check independent interval model against the actual floating simulator.
    from sim import Society
    from numerical_audit import FloatReplayAudit
    s=Society(cfg); audit=FloatReplayAudit(); action_audit=FloatReplayAudit(); action_rows=iter(compiler.action_rows)
    def agree(w,x,field):
        try: audit.compare(w.lo,w.hi,x,f'round={t}/{field}')
        except ValueError as error: raise Unsupported(str(error)) from error
    for t,joint in enumerate(plan,1):
        s.state['round']=t; before=__import__('environments').physical_snapshot(s.state)
        for aid in action_order(cfg,t,joint):
            s.act(aid,copy.deepcopy(joint[aid])); intermediate=next(action_rows)
            if intermediate['round']!=t or intermediate['actor']!=aid: raise Unsupported('Action-phase order differs')
            def compare_action(w,x,field):
                try: action_audit.compare(w.lo,w.hi,x,f'round={t}/after={aid}/{field}')
                except ValueError as error: raise Unsupported(str(error)) from error
            for member in compiler.ids:
                actual=s.state['agents'][member]
                if intermediate['function_knowledge'][member] != set(actual.get('function_knowledge', {})):
                    raise Unsupported('Action-phase combination discoveries differ')
                compare_action(intermediate['stock'][member],actual['stock'],f'{member}/stock')
                compare_action(intermediate['health'][member],actual['energy'],f'{member}/vitality')
                for k,w in intermediate['inventory'][member].items(): compare_action(w,actual['inventory'][k],f'{member}/inventory/{k}')
                if intermediate['notes'][member]!={k:len(v) for k,v in actual.get('private_notes',{}).items()}:
                    raise Unsupported('Action-phase note state differs')
            world=s.state['mini_world']
            for k,w in intermediate['variables'].items(): compare_action(w,world['variables'][k],f'variables/{k}')
            for k,w in intermediate['pools'].items(): compare_action(w,world['pools'][k],f'pools/{k}')
            compare_action(intermediate['reserve'],world['reserve'],'reserve')
            if set(intermediate['devices'])!=set(world['devices']): raise Unsupported('Action-phase device existence differs')
            for key,device in intermediate['devices'].items():
                for field in ('owner','users','active_from','active_until','pending_service'):
                    if device.get(field)!=world['devices'][key].get(field): raise Unsupported('Action-phase device permissions differ')
                compare_action(device['embedded_energy'],world['devices'][key]['embedded_energy'],f'devices/{key}/embedded_energy')
            if set(intermediate['pending'])!=set(world['pending']): raise Unsupported('Action-phase queue membership differs')
            for member,p in intermediate['pending'].items():
                actual=world['pending'][member]
                if any(p[k]!=actual[k] for k in ('facility','mode','batches')) or p.get('submitted_round')!=actual.get('submitted_round'):
                    raise Unsupported('Action-phase queue metadata differs')
                expected=p.get('escrow',{k:compiler.c.const(n*p['batches']) for k,n in p['inputs'].items()})
                if set(expected)!=set(actual['inputs']): raise Unsupported('Action-phase queue materials differ')
                for k,w in expected.items(): compare_action(w,actual['inputs'][k],f'queue/{member}/{k}')
            if intermediate['schedulers']!=world.get('facility_schedulers',{}): raise Unsupported('Action-phase scheduler differs')
        s.settle(before); row=compiler.rows[t-1]
        if row['schedulers']!=s.state['mini_world'].get('facility_schedulers',{}): raise Unsupported('Round scheduler differs')
        if set(row['pending'])!=set(s.state['mini_world']['pending']): raise Unsupported('Round queue membership differs')
        for member,p in row['pending'].items():
            actual=s.state['mini_world']['pending'][member]
            for k,w in p['escrow'].items(): agree(w,actual['inputs'][k],f'queue/{member}/{k}')
        for aid in compiler.ids:
            a=s.state['agents'][aid]; agree(row['stock'][aid],a['stock'],f'{aid}/stock'); agree(row['health'][aid],a['energy'],f'{aid}/vitality')
            if row['function_knowledge'][aid] != set(a.get('function_knowledge', {})):
                raise Unsupported('Settlement combination discoveries differ')
            if a['energy']!=row['health'][aid].lo or not a['alive']: raise Unsupported('Float survival branch differs')
            for k,w in row['inventory'][aid].items(): agree(w,a['inventory'][k],f'{aid}/inventory/{k}')
        for k,w in row['variables'].items(): agree(w,s.state['mini_world']['variables'][k],f'variables/{k}')
        for k,w in row['pools'].items(): agree(w,s.state['mini_world']['pools'][k],f'pools/{k}')
        agree(row['reserve'],s.state['mini_world']['reserve'],'reserve')
        for aid,expected in row['produced'].items():
            actual=s.state['mini_world']['discoveries'][aid][-1]['produced']
            import production_semantics
            if production_semantics.proportional(compiler.d):
                if set(actual)!=set(expected): raise Unsupported('Float production material keys differ')
                for k,w in expected.items(): agree(w,actual[k],f'{aid}/production/{k}')
            else:
                exact={k:int(w.lo) for k,w in expected.items() if w.lo==w.hi and w.lo.denominator==1}
                if len(exact)!=len(expected) or actual!=exact: raise Unsupported('Float discrete production result differs')
        actual_devices=s.state['mini_world']['devices']
        if set(row['devices'])!=set(actual_devices): raise Unsupported('Device existence differs')
        for key,device in row['devices'].items():
            actual=actual_devices[key]
            for field in ('owner','users','active_from','active_until','pending_service'):
                if device.get(field)!=actual.get(field): raise Unsupported('Device authorization or lifetime differs')
            agree(device['embedded_energy'],actual['embedded_energy'],f'devices/{key}/embedded_energy')
    source=Path(__file__).with_name('composed_checker.lean').read_text('utf-8')
    if semantic:
        import interval_proofs
        source=interval_proofs.source(include_advanced=True)
    # Bind normalized equations to the actual expr lowering implementation.
    # These universally quantified theorems complement the closed interval
    # checks; they do not prove the state-transition adapter or JSON parser.
    import tempfile
    import expression_certificates
    with tempfile.TemporaryDirectory() as folder:
        expression_artifact=expression_certificates.export(compiler.d,Path(folder)/'expressions.lean')
        expression_source=Path(expression_artifact['source']).read_text('utf-8').removeprefix('import Std\n')
    lines=[source,expression_source,'open Composed','set_option maxRecDepth 1000000','set_option maxHeartbeats 0']
    values={}
    for _,_,_,w,_ in c.nodes:
        pair=(w.lo,w.hi)
        if pair not in values: values[pair]=len(values)
    for (lo,hi),index in values.items(): lines.append(f'def v{index} : Box := ⟨{qsource(lo)}, {qsource(hi)}⟩')
    def ref(w): return 'v'+str(values[(w.lo,w.hi)])
    zero=c.const(0); checks=[]
    for op,a,b,w,constant in c.nodes:
        instruction=f'(.constant {qsource(constant)})' if op=='constant' else '.'+op
        checks.append(f'⟨{instruction}, {ref(a or zero)}, {ref(b or zero)}, {ref(w)}⟩')
    # Duplicate closed constraints are the same proposition, not omitted dynamics.
    checks=list(dict.fromkeys(checks))
    blocks=[]
    for start in range(0,len(checks),64):
        name='block'+str(start//64); blocks.append(name)
        lines.append(f'def {name} : Bool := checkBlock [{", ".join(checks[start:start+64])}]')
        lines.append(f'theorem {name}_checked : {name} = true := by decide')
    lines.append('def transitionCertificate : Bool := '+ ' && '.join(blocks))
    lines.append('theorem certified_transitions : transitionCertificate = true := by simp [transitionCertificate, '+', '.join(n+'_checked' for n in blocks)+']')
    lines.append('def guards : Bool := '+ ' && '.join(dict.fromkeys(f'singleton {ref(w)} one' for w in c.guards)))
    lines.append('theorem certified_action_and_branch_guards : guards = true := by decide')
    lines.append('def vitalityTrace : List Box := ['+', '.join(ref(w) for w in c.live)+']')
    lines.append('theorem certified_full_survival : allPositive vitalityTrace = true := by decide')
    lines.append(f'theorem certified_population_time : vitalityTrace.length = {len(plan)*len(compiler.ids)} := by decide')
    metadata={'world_sha256':hashlib.sha256(json.dumps(compiler.d,sort_keys=True).encode()).hexdigest(),
        'configuration_sha256':configuration_digest(cfg),
        'horizon':len(plan),'members':len(compiler.ids),'nodes':len(c.nodes),'unique_constraints':len(checks),'unique_values':len(values),'max_float_comparison_error':audit.max_error,
        'expression_count':expression_artifact['expression_count'],
        'expression_lowering':'lean_kernel_proved_normalized_expression_semantics',
        'scope':'Normalized expression lowering, outward rational interval transition constraints and positive vitality on a fixed action schedule. JSON normalization, primitive interval soundness, state adapter correctness and IEEE equivalence are not formally proved; no optimality or unknown-rule discovery claim.'}
    if semantic:
        import graph_certificates
        graph_source,graph_metadata=graph_certificates.fragment(c,ref,qsource)
        graph_metadata.pop('graph_records')
        lines.append(graph_source)
        metadata.update(graph_metadata)
        metadata['scope']='Normalized expression lowering, all-operator interval soundness, dependency-preserving rational DAG evaluation, branch guards and semantic vitality positivity. JSON normalization, world-action lowering and IEEE equivalence are not formally proved; no optimality or discovery claim.'
    lines.append('-- '+json.dumps(metadata,ensure_ascii=False))
    source='\n'.join(lines)+'\n'; path=Path(path); path.parent.mkdir(parents=True,exist_ok=True); path.write_text(source,encoding='utf-8')
    # Machine-dependent evidence is deliberately outside the Lean source/hash.
    # Admission independently repeats this replay on the admitting machine.
    return {'source':str(path.resolve()),'sha256':hashlib.sha256(source.encode()).hexdigest(),'status':'exported_not_checked',**metadata,'float_replay_audit':audit.report(),
            'action_phase_audit':action_audit.report()}


def check(artifact):
    from survival_certificates import check_lean
    result=check_lean(artifact,timeout=600 if artifact.get('graph_nodes',0)>5000 else 120)
    if result['status']=='lean_checked_restricted_projection': result['status']='lean_checked_composed_interval_certificate'
    return result


def validate_admission(cfg,bundle):
    if cfg.get('require_end_to_end_world_proof'):
        raise ValueError('End-to-end world proof is not implemented: JSON/world-action lowering and IEEE runtime equivalence remain trusted boundaries')
    if bundle.get('version') not in ('composed_interval_survival_v1','composed_semantic_survival_v2'): raise ValueError('Unsupported composed certificate version')
    semantic=bundle['version']=='composed_semantic_survival_v2'
    if semantic and bundle['lean'].get('graph_semantics')!='kernel_checked_dependency_preserving_rational_DAG':
        raise ValueError('Semantic certificate is missing dependency proof')
    if bundle['lean']['status']!='lean_checked_composed_interval_certificate': raise ValueError('Composed certificate was not checked by Lean')
    if len(bundle['plan'])!=cfg['rounds'] or bundle['lean']['members']!=len(cfg['models']): raise ValueError('Composed certificate horizon/population mismatch')
    import tempfile
    with tempfile.TemporaryDirectory() as folder:
        artifact=export(cfg,bundle['plan'],Path(folder)/'certificate.lean',semantic=semantic)
        if artifact['sha256']!=bundle['lean']['sha256']: raise ValueError('Composed certificate does not match configuration or current checker')
        result=check(artifact)
    if result['status']!='lean_checked_composed_interval_certificate':
        raise ValueError('Composed certificate rejected or Lean unavailable: '+json.dumps(result,ensure_ascii=False))
    return result
