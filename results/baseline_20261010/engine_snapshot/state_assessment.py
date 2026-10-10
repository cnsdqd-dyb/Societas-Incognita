"""Offline physical assessment. No API calls or objectives added to agents.

Inputs must be a complete state after settlement. Policy witnesses establish
finite-horizon feasibility only; failure of one policy does not prove infeasibility.
"""
import copy
import json
from pathlib import Path

import environments
import interaction_controls
from audit_actions import well_formed
from sim import Society


def replay_settled(folder, round_number):
    """Reconstruct physical state and verify each completed round against logs."""
    folder = Path(folder)
    cfg = json.loads((folder / 'config.json').read_text(encoding='utf-8'))
    saved = json.loads((folder / 'checkpoint.json').read_text(encoding='utf-8'))['state']
    snapshots = {s['round']: s for s in saved['snapshots']}
    if round_number not in snapshots:
        raise ValueError('Requested round has no settled snapshot')
    society = Society(cfg)
    if cfg.get('initial_checkpoint_branch'):
        from checkpoint_interventions import load_branch
        society.state = load_branch(cfg)
        if round_number < society.state['round']:
            raise ValueError('Earlier branch history must be replayed from the source run')
    events = {}
    for event in saved['events']:
        events.setdefault(event['round'], []).append(event)
    for t in range(society.state['round']+1, round_number + 1):
        society.state['round'] = t
        interaction_controls.start_round(cfg,society.state)
        if cfg.get('resource_seizure',{}).get('version')=='seizure_v2':
            import resource_seizure
            resource_seizure.start_round(society.state)
        before = environments.physical_snapshot(society.state)
        for event in events.get(t, []):
            rejected = False
            try:
                society.act(event['agent'], event['decision']['action'])
            except (ValueError, KeyError, TypeError):
                rejected = True
            if rejected != ('action_error' in event['outcome']):
                raise ValueError('Replay acceptance differs from recorded action')
        society.settle(before)
        for aid, agent in society.state['agents'].items():
            recorded = snapshots[t]['agents'][aid]
            if (abs(agent['stock'] - recorded['stock']) > 1e-8
                    or agent['energy'] != recorded['energy']
                    or agent['alive'] != recorded['alive']):
                raise ValueError('Replay differs from settled snapshot')
            if abs(agent.get('vault',0)-recorded.get('vault',0))>1e-8:raise ValueError('Replay differs from vault snapshot')
            if cfg['world'].get('mechanism') == 'mini_world':
                if agent['inventory'] != recorded['inventory']: raise ValueError('Replay differs from material inventory')
            if cfg.get('social_content'):
                escrow=sum(g['escrow'].get(aid,0) for g in society.state['social_content']['games'].values())
                if abs(escrow-recorded.get('game_escrow',0))>1e-8:raise ValueError('Replay differs from escrow snapshot')
    return cfg, society.state


def rollout(cfg, settled_state, policy, horizon):
    """Execute one specified policy with explicit dictionary execution order."""
    if type(horizon) is not int or horizon < 1:
        raise ValueError('Horizon must be a positive integer')
    state = copy.deepcopy(settled_state)
    if state['mechanism_state']['pending'] or any(
            job['remaining'] is None for job in state['mechanism_state']['jobs'].values()):
        raise ValueError('State must be after settlement')
    members = [i for i, a in state['agents'].items() if a['alive']]
    trace, first_death = [], {}
    for step in range(1, horizon + 1):
        state['round'] += 1
        interaction_controls.start_round(cfg,state)
        if cfg.get('resource_seizure',{}).get('version')=='seizure_v2':
            import resource_seizure
            resource_seizure.start_round(state)
        before = environments.physical_snapshot(state)
        actions = policy(copy.deepcopy(state), step)
        errors = {}
        # Every living member has one action. Transfers and extraction are sequential.
        for aid in list(state['agents']):
            if not state['agents'][aid]['alive']:
                continue
            action = actions.get(aid, {'tool': 'wait'})
            try:
                if not well_formed(action, cfg):
                    raise ValueError('Malformed or out-of-range action')
                if 'args' in action:
                    action = {**{k: v for k, v in action.items() if k != 'args'},
                              **action['args']}
                environments.act(cfg, state, aid, action)
            except (ValueError, KeyError, TypeError) as exc:
                errors[aid] = str(exc)
        record = environments.settle_physics(cfg, state, before)
        environments.maintenance(cfg, state, record)
        for aid in members:
            if not state['agents'][aid]['alive']:
                first_death.setdefault(aid, state['round'])
        trace.append({'round': state['round'], 'actions': actions,
                      'action_errors': errors,
                      'agents': {i: {k: a[k] for k in ('stock', 'energy', 'alive','vault') if k in a}
                                 for i, a in state['agents'].items()},
                      'jobs': copy.deepcopy(state['mechanism_state']['jobs'])})
    success = bool(members) and not first_death and not any(t['action_errors'] for t in trace)
    return {'horizon': horizon, 'initial_living_members': members,
            'all_initial_living_survive': bool(members) and not first_death,
            'first_death_round': first_death,
            'feasibility': 'finite_horizon_witness' if success else 'not_established',
            'execution_order': list(state['agents']), 'trace': trace,
            'scope': 'Full-state physical feasibility under this policy and order; no social legitimacy inference.'}


def wait_policy(state, step):
    return {}


def congestion_t10_recovery(state, step):
    """Case-specific witness; support is consumed before next-round production.

    Recipients wait in transfer rounds, so the first three rounds do not depend
    on whether the donor or recipient executes first.
    """
    if step == 1:
        return {'a1': {'tool': 'transfer', 'target': 'a0', 'amount': 2}}
    if step == 2:
        return {'a0': {'tool': 'process', 'facility': 0},
                'a1': {'tool': 'transfer', 'target': 'a6', 'amount': 2}}
    if step == 3:
        return {'a0': {'tool': 'transfer', 'target': 'a1', 'amount': 2},
                'a6': {'tool': 'process', 'facility': 1}}
    facilities = {'a0': 0, 'a1': 0, 'a6': 1}
    return {aid: {'tool': 'process', 'facility': facilities[aid]}
            for aid in facilities if state['agents'][aid]['alive']
            and aid not in state['mechanism_state']['jobs']
            and state['agents'][aid]['stock'] >= 1}


def main():
    root = Path('runs/core_campaign_v6_50rounds_20261007')
    cfg, state = replay_settled(root / 'congestion_p1_information_s7/simulation', 10)
    actual = json.loads((root / 'congestion_p1_information_s7/simulation/checkpoint.json').read_text(encoding='utf-8'))['state']
    report = {'assessment_round': 10, 'replay_verified': True,
              'current_agents': {i: {k: a[k] for k in ('stock', 'energy', 'alive')}
                                 for i, a in state['agents'].items()},
              'wait': rollout(cfg, state, wait_policy, 50),
              'recovery': rollout(cfg, state, congestion_t10_recovery, 50),
              'actual_living_at_round_20': sum(a['alive'] for a in next(
                  s for s in actual['snapshots'] if s['round'] == 20)['agents'].values())}
    # Negative control: this pressure condition needs no cooperation to survive.
    pg_cfg, pg_state = replay_settled(root / 'public_goods_p1_basic_s17/simulation', 10)
    report['public_goods_wait'] = rollout(pg_cfg, pg_state, wait_policy, 50)
    output = Path('../../refine-logs/STATE_ASSESSMENT_20261007.json')
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: report[k]['feasibility'] for k in ('wait', 'recovery', 'public_goods_wait')}))


if __name__ == '__main__':
    main()
