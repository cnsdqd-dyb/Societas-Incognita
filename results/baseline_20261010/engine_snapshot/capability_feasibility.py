"""Bounded omniscient construction witnesses, executed by the real simulator.

No endowments, API calls or inference of global optimality. This constructive
strategy may fail in a feasible world; failures are explicitly inconclusive.
"""
import copy
import json
import math
import random
from pathlib import Path

import capability_devices as devices
import environments
import mini_world
import sim
import world_rule_engine as equations
from world_rule_library import digest


class Inconclusive(Exception):
    pass


def basket(inputs):
    return [{'item': k, 'amount': n} for k,n in inputs.items()]


def action_order(cfg, round_number, joint):
    order = sorted(joint)
    random.Random(cfg['seed']+round_number).shuffle(order)
    return order


class Builder:
    def __init__(self, cfg, target, horizon=50):
        self.cfg = copy.deepcopy(cfg)
        self.s = sim.Society(self.cfg)
        self.d = mini_world.spec(self.cfg)
        self.target = next((r for r in self.d.get('device_recipes', []) if r['id'] == target), None)
        if self.target is None: raise ValueError('Unknown target device recipe')
        if type(horizon) is not int or not 1 <= horizon <= 1000: raise ValueError('Invalid witness horizon')
        if any(cfg.get(k) for k in ('social_content', 'open_activities', 'resource_seizure')) or cfg.get('rescue', {}).get('enabled'):
            raise ValueError('Construction witness currently supports the core mini-world without social/security extensions')
        self.horizon = horizon; self.plan = []; self.trace = []; self.goal = None
        self.aid = 'a0'

    def fuel_item(self):
        if not self.d['pools']: raise Inconclusive('No pool fuel route in this strategy')
        return max(self.d['pools'], key=lambda k: self.d['resources'][k]['energy_value']*self.d['resources'][k]['liquidation_efficiency'])

    def sustain(self, aid):
        a = self.s.state['agents'][aid]
        if not self.cfg['world']['survival_pressure'] or a['stock'] >= 2*self.cfg['world']['consumption']:
            return {'tool': 'wait'}
        for k in self.d['pools']:
            n = min(self.d['max_quantity'], math.floor(a['inventory'][k]+1e-9))
            if n: return {'tool': 'liquidate', 'item': k, 'amount': n}
        return {'tool': 'gather', 'item': self.fuel_item(), 'amount': self.d['max_quantity']}

    def step(self, action):
        if self.s.state['round'] >= self.horizon: raise Inconclusive('Construction exceeded the declared round bound')
        if not all(a['alive'] for a in self.s.state['agents'].values()): raise Inconclusive('A member became inactive')
        self.s.state['round'] += 1
        joint = {aid: self.sustain(aid) for aid in self.s.state['agents']}
        joint[self.aid] = copy.deepcopy(action)
        before = environments.physical_snapshot(self.s.state); outcomes = {}
        try:
            order = action_order(self.cfg, self.s.state['round'], joint)
            for aid in order: outcomes[aid] = self.s.act(aid, joint[aid])
            self.s.settle(before)
        except (ValueError, TypeError, KeyError) as exc:
            raise Inconclusive('Strategy could not execute a legal transition: '+str(exc)) from exc
        self.plan.append(joint)
        self.trace.append({'round': self.s.state['round'], 'actions': copy.deepcopy(joint),
            'execution_order': order,
            'outcomes': copy.deepcopy(outcomes), 'members': {aid: {k: copy.deepcopy(a[k]) for k in ('stock', 'energy', 'alive', 'inventory')}
                for aid,a in self.s.state['agents'].items()},
            'devices': copy.deepcopy(self.s.state['mini_world']['devices']),
            'energy_accounting': mini_world.accounting(self.cfg, self.s.state)})
        if not all(a['alive'] for a in self.s.state['agents'].values()): raise Inconclusive('Construction strategy caused inactivity')
        return outcomes[self.aid]

    def energy(self, cost=0):
        reserve = 2*self.cfg['world']['consumption'] if self.cfg['world']['survival_pressure'] else 0
        while self.s.state['agents'][self.aid]['stock']+1e-9 < cost+reserve:
            item = self.fuel_item(); a = self.s.state['agents'][self.aid]
            units = min(self.d['max_quantity'], math.floor(a['inventory'][item]+1e-9))
            if units: self.step({'tool': 'liquidate', 'item': item, 'amount': units})
            else: self.step({'tool': 'gather', 'item': item, 'amount': self.d['max_quantity']})

    def ensure(self, item, amount, stack=()):
        if item in stack: raise Inconclusive('Selected production route contains a dependency cycle')
        while self.s.state['agents'][self.aid]['inventory'][item]+1e-9 < amount:
            self.energy()
            if item in self.d['pools']:
                short = amount-self.s.state['agents'][self.aid]['inventory'][item]
                self.step({'tool': 'gather', 'item': item, 'amount': min(self.d['max_quantity'], max(1, math.ceil(short)))})
                continue
            recipes = [r for r in self.d['recipes'] if r['output'] == item]
            if not recipes: raise Inconclusive('No selected producer for '+item)
            r = recipes[0]
            if r.get('requires_capability') and not devices.capacities(self.cfg, self.s.state, self.aid)[r['requires_capability']]:
                raise Inconclusive('Selected production route needs an unavailable capability')
            if not equations.evaluate(r['condition'], mini_world.context(self.cfg, self.s.state)):
                raise Inconclusive('Selected production condition is not met')
            output = max(1., equations.evaluate(r['yield'], mini_world.context(self.cfg, self.s.state)))
            short = amount-self.s.state['agents'][self.aid]['inventory'][item]
            batches = min(self.d['max_batches'], max(1, math.ceil((short+.05)/output)))
            inputs = {k: n*batches for k,n in r['inputs'].items()}
            self.ingredients(inputs, stack+(item,))
            self.energy(self.d['experiment_cost']+r['energy_cost']*batches)
            # Refueling and ingredient production also advance material decay.
            if any(self.s.state['agents'][self.aid]['inventory'][k]+1e-9 < n for k,n in inputs.items()):
                continue
            self.step({'tool': 'experiment', 'facility': r['facility'], 'mode': r['mode'],
                       'inputs': basket(r['inputs']), 'batches': batches})

    def ingredients(self, inputs, stack=()):
        while any(self.s.state['agents'][self.aid]['inventory'][k]+1e-9 < n for k,n in inputs.items()):
            for k,n in inputs.items():
                # Slight surplus prevents chasing exact integers of decaying inputs.
                self.ensure(k, n+(.1 if self.d['resources'][k]['decay'] else 0), stack)

    def build(self):
        r = self.target
        while True:
            self.energy(self.d['experiment_cost']+r['build_cost'])
            self.ingredients(r['inputs'])
            self.energy(self.d['experiment_cost']+r['build_cost'])
            if all(self.s.state['agents'][self.aid]['inventory'][k]+1e-9 >= n for k,n in r['inputs'].items()): break
        result = self.step({'tool': 'assemble_device', 'facility': r['facility'], 'mode': r['mode'], 'inputs': basket(r['inputs'])})
        if not result.get('assembled'): raise Inconclusive('No device assembled')
        key = result['device']['id']
        self.energy(r['fuel_per_recipient'])
        self.step({'tool': 'activate_device', 'device': key, 'targets': [self.aid]})
        self.energy()
        self.step({'tool': 'wait'})  # Actual next-round activation, including maintenance.
        if not any(v['id'] == key for v in devices.active(self.s.state, self.aid)):
            raise Inconclusive('Service expired before use')
        cap = r['capabilities']; evidence = {}
        if cap.get('communication_bonus'):
            base = self.cfg['communication'].get('budget', {}).get('limit', 0)
            limit = devices.communication_limit(self.cfg, self.s.state, self.aid, base)
            if limit <= base: raise Inconclusive('Communication device offers no increment under this configuration')
            evidence['communication'] = {'base_limit': base, 'effective_limit': limit,
                'scope': 'interface capacity, not actual language-model dialogue quality'}
        if cap.get('note_capacity'):
            self.energy()
            text = 'x'*(self.d.get('note_base_capacity', 256)+1)
            self.step({'tool': 'write_note', 'key': 'feasibility_probe', 'text': text})
            evidence['note_written_characters'] = len(text)
        if cap.get('measurements'):
            self.energy()
            field = next(iter(cap['measurements']))
            evidence['measurement'] = self.step({'tool': 'measure', 'device': key, 'field': field})
        if cap.get('manufacturing'):
            recipes = [q for q in self.d['recipes'] if q.get('requires_capability') == 'manufacturing']
            if not recipes: raise Inconclusive('No production recipe uses the manufacturing service')
            q = recipes[0]
            # Acquire inputs before renewing the service if gathering takes longer than its lifetime.
            self.ingredients(q['inputs']); self.energy(r['fuel_per_recipient']+self.d['experiment_cost']+q['energy_cost'])
            self.step({'tool': 'activate_device', 'device': key, 'targets': [self.aid]})
            self.step({'tool': 'experiment', 'facility': q['facility'], 'mode': q['mode'], 'inputs': basket(q['inputs']), 'batches': 1})
            if self.s.state['agents'][self.aid]['inventory'][q['output']] <= 0:
                raise Inconclusive('Manufacturing service did not yield a product')
            evidence['manufactured_item'] = q['output']
        self.goal = {'round': self.s.state['round'], 'device': key, 'recipe': r['id'], 'evidence': evidence,
                     'capabilities': devices.capacities(self.cfg, self.s.state, self.aid)}
        while self.s.state['round'] < self.horizon:
            self.step(self.sustain(self.aid))


def verify(cfg, target, plan, goal):
    """Independent replay checks legal costs, survival and actual capability effects."""
    recipe = next((r for r in mini_world.spec(cfg).get('device_recipes', []) if r['id'] == target), None)
    if recipe is None: raise ValueError('Unknown verification target')
    if not isinstance(goal, dict) or goal.get('recipe') != target or type(goal.get('round')) is not int or not 1 <= goal['round'] <= len(plan):
        raise ValueError('Invalid goal identity or round')
    cap = recipe['capabilities']
    required = {field for condition,field in (
        (cap.get('communication_bonus'), 'communication'), (cap.get('note_capacity'), 'note_written_characters'),
        (cap.get('measurements'), 'measurement'), (cap.get('manufacturing'), 'manufactured_item')) if condition}
    if set(goal.get('evidence', {})) != required: raise ValueError('Goal must demonstrate each target capability')
    s = sim.Society(cfg)
    actual_goal = None; score = 0; members = len(s.state['agents'])
    for round_number, joint in enumerate(plan, 1):
        if set(joint) != {aid for aid,a in s.state['agents'].items() if a['alive']}:
            raise ValueError('Witness must provide one action per active member')
        s.state['round'] = round_number; before = environments.physical_snapshot(s.state)
        outcomes = {aid: s.act(aid, copy.deepcopy(joint[aid])) for aid in action_order(cfg, round_number, joint)}
        s.settle(before)
        alive = sum(a['alive'] for a in s.state['agents'].values())
        if alive != members: raise ValueError('Witness replay did not preserve every member')
        score += alive
        if round_number == goal['round']:
            device = s.state['mini_world']['devices'].get(goal['device'])
            if device is None or device['owner'] != 'a0' or device['researcher_provenance']['recipe_id'] != target:
                raise ValueError('Goal device does not match replay')
            if not any(v['id'] == goal['device'] for v in devices.active(s.state, 'a0')):
                raise ValueError('Goal service is not active and authorized')
            actual_goal = devices.capacities(cfg, s.state, 'a0')
            if actual_goal != goal['capabilities']: raise ValueError('Goal capability state does not match replay')
            evidence = goal['evidence']
            if 'note_written_characters' in evidence:
                size = evidence['note_written_characters']
                if size <= mini_world.spec(cfg).get('note_base_capacity', 256) or joint['a0']['tool'] != 'write_note' or len(s.state['agents']['a0']['private_notes'].get('feasibility_probe', '')) != size:
                    raise ValueError('Note effect does not demonstrate the additional capacity')
            if 'measurement' in evidence and outcomes['a0'] != evidence['measurement']:
                raise ValueError('Measurement does not match replay')
            if 'manufactured_item' in evidence:
                output = evidence['manufactured_item']; action = joint['a0']
                inputs = mini_world.parse_basket(cfg, action.get('inputs')) if action.get('tool') == 'experiment' else None
                actual_recipe = next((r for r in mini_world.spec(cfg)['recipes'] if
                    r['facility'] == action.get('facility') and r['mode'] == action.get('mode') and
                    r['inputs'] == inputs and r['output'] == output), None)
                last = s.state['mini_world']['discoveries'].get('a0', [{}])[-1]
                if actual_recipe is None or actual_recipe.get('requires_capability') != 'manufacturing' or last.get('round') != round_number or last.get('produced', {}).get(output, 0) <= 0:
                    raise ValueError('No capability-dependent manufactured item in replay')
            if 'communication' in evidence:
                e = evidence['communication']
                if e['base_limit'] != cfg['communication'].get('budget', {}).get('limit', 0) or e['effective_limit'] <= e['base_limit'] or devices.communication_limit(cfg, s.state, 'a0', e['base_limit']) != e['effective_limit']:
                    raise ValueError('Communication capacity does not match replay')
    if actual_goal is None: raise ValueError('Goal round is outside witness')
    return {'status': 'independently_replayed', 'score': score,
            'horizon': len(plan), 'formal_status': 'not_lean_verified',
            'execution_order': 'simulator_seed_plus_round_shuffle',
            'noise_scope': 'deterministic' if mini_world.spec(cfg)['noise']['distribution'] == 'none' else 'fixed_seed_trajectory_only'}


def evaluate(cfg, target, horizon=50):
    builder = Builder(cfg, target, horizon)
    reason = None
    try: builder.build()
    except Inconclusive as exc: reason = str(exc)
    success = reason is None
    report = {'version': 'capability_feasibility_v1', 'target': target,
        'world_sha256': digest(mini_world.spec(cfg)), 'pressure': cfg['world']['survival_pressure'],
        'configuration_sha256': digest(cfg), 'seed': cfg['seed'], 'requested_horizon': horizon,
        'members': len(cfg['models']),
        'status': 'feasible_witness_found' if success else 'inconclusive_strategy_failure',
        'reason': reason, 'initial_state': 'actual_configured_initial_state_without_endowment',
        'information_scope': 'omniscient constructive strategy; not unknown-rule agent discoverability',
        'optimality': 'not_computed', 'goal': builder.goal, 'plan': builder.plan, 'trace': builder.trace,
        'api_cost_usd': 0, 'formal_status': 'not_lean_verified'}
    if success: report['verification'] = verify(cfg, target, builder.plan, builder.goal)
    return report


def verify_report(cfg, report):
    if report.get('version') != 'capability_feasibility_v1' or report.get('configuration_sha256') != digest(cfg) or report.get('world_sha256') != digest(mini_world.spec(cfg)):
        raise ValueError('Report is not bound to this configuration and world')
    if report.get('status') != 'feasible_witness_found' or len(report['plan']) != report['requested_horizon']:
        raise ValueError('Report is not a complete success witness')
    return verify(cfg, report['target'], report['plan'], report['goal'])


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--configs', default='configs/capability_fixtures_20261010')
    p.add_argument('--output', default='reports/capability_feasibility_20261010')
    p.add_argument('--horizon', type=int, default=50)
    args = p.parse_args(); output = Path(args.output); output.mkdir(parents=True, exist_ok=True)
    summary = []
    for pressure in (0, 1):
        cfg = json.loads((Path(args.configs)/f'capabilities_4agents_p{pressure}_hidden.json').read_text('utf-8'))
        for recipe in mini_world.spec(cfg)['device_recipes']:
            report = evaluate(cfg, recipe['id'], args.horizon)
            (output/f'{recipe["id"]}_p{pressure}.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            summary.append({k: report[k] for k in ('target', 'pressure', 'status', 'reason', 'goal')} |
                {'survival_score': report.get('verification', {}).get('score'),
                 'minimum_vitality': min((a['energy'] for step in report['trace'] for a in step['members'].values()), default=None),
                 'maximum_ledger_residual': max((abs(t['energy_accounting']['residual']) for t in report['trace']), default=0)})
            print(json.dumps(summary[-1], ensure_ascii=False), flush=True)
    (output/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
