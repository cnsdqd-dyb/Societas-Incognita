"""Researcher-only descriptive metrics. These are not organization diagnoses."""
import math
from collections import Counter, defaultdict


def gini(values):
    n, total = len(values), sum(values)
    if not n or not total:
        return None  # No holdings: inequality is not identifiable.
    return sum(abs(a-b) for a in values for b in values)/(2*n*total)


def graph_summary(edges, members):
    members = set(members)
    edges = {(a,b) for a,b in edges if a in members and b in members and a != b}
    adjacent = {a:set() for a in members}
    for a,b in edges:
        adjacent[a].add(b); adjacent[b].add(a)
    unseen, sizes = set(members), []
    while unseen:
        stack = [unseen.pop()]; size = 0
        while stack:
            a = stack.pop(); size += 1
            new = adjacent[a] & unseen
            unseen -= new; stack.extend(new)
        sizes.append(size)
    return {'directed_edges': [list(x) for x in sorted(edges)],
            'density': len(edges)/(len(members)*(len(members)-1)) if len(members)>1 else None,
            'reciprocity': sum((b,a) in edges for a,b in edges)/len(edges) if edges else None,
            'component_sizes': sorted(sizes, reverse=True),
            'isolated_members': sum(not adjacent[a] for a in members)}


def measure(state, cfg, window=5):
    """Laplace prequential surprisal; each score uses only that agent's earlier tools."""
    history = defaultdict(Counter)
    surprise = []
    k = len(cfg['tools'])
    for event in sorted(state['events'], key=lambda e:e['round']):
        action = event['decision'].get('action')
        aid, tool = event['agent'], action.get('tool') if isinstance(action,dict) else None
        if 'action_error' in event['outcome'] or tool not in cfg['tools']:
            continue
        counts = history[aid]
        probability = (counts[tool]+1)/(sum(counts.values())+k)
        surprise.append({'round': event['round'], 'agent': aid, 'tool': tool,
                         'probability': probability, 'bits': -math.log2(probability),
                         'relative_to_uniform_bits': -math.log2(probability)-math.log2(k)})
        counts[tool] += 1
    series, previous = [], None
    environment = {e['round']:e for e in state.get('environment_history', [])}
    original = list(state['agents'])
    for snapshot in state.get('snapshots', []):
        t = snapshot['round']
        alive = [i for i,a in snapshot['agents'].items() if a['alive']]
        stocks = [snapshot['agents'][i]['stock'] for i in alive]
        transfers, private, actions = set(), set(), []
        invalid_action = invalid_comm = 0
        for event in state['events']:
            if not t-window < event['round'] <= t: continue
            decision, outcome, aid = event['decision'], event['outcome'], event['agent']
            invalid_action += 'action_error' in outcome
            invalid_comm += 'communication_error' in outcome
            if 'action_error' not in outcome:
                actions.append(decision['action']['tool'])
                if outcome.get('action', {}).get('transferred', 0)>0:
                    transfers.add((aid, outcome['action']['target']))
            if 'communication_error' not in outcome:
                private.update((aid,b) for b in outcome.get('private_recipients', []))
        dialogue = [e for e in state.get('communication_events', []) if t-window < e['round'] <= t]
        for event in dialogue:
            outcome = event['outcome']
            invalid_comm += 'communication_error' in outcome
            if 'communication_error' not in outcome:
                private.update((event['agent'], b) for b in outcome.get('private_recipients', []))
        trades = [e for e in state.get('social_content', {}).get('transactions', []) if t-window < e['round'] <= t]
        trade_edges = {(e['buyer'],e['author']) for e in trades}
        edges = transfers | private | trade_edges
        union = edges | previous if previous is not None else set()
        bits = [s['bits'] for s in surprise if t-window < s['round'] <= t]
        series.append({'round':t, 'window_rounds':window, 'original_members':len(original),
            'alive_members':len(alive), 'alive_fraction':len(alive)/len(original),
            'stock_gini_alive':gini(stocks),
            'largest_stock_share_alive':max(stocks)/sum(stocks) if stocks and sum(stocks) else None,
            'dominant_tool_share':max(Counter(actions).values())/len(actions) if actions else None,
            'mean_behavior_surprisal_bits':sum(bits)/len(bits) if bits else None,
            'invalid_actions':invalid_action, 'invalid_communications':invalid_comm,
            'transfer_graph':graph_summary(transfers, original),
            'private_message_graph':graph_summary(private, original),
            # Empty-edge agreement is undefined, rather than perfect "stability".
            'interaction_edge_jaccard_previous_window':len(edges & previous)/len(union) if union else None})
        previous = edges
        if cfg['world'].get('mechanism') == 'mini_world':
            material = snapshot.get('mini_world_metrics', {})
            series[-1]['material_economy'] = material
            holdings = [material.get('energy_equivalent_by_member', {}).get(a, 0) for a in alive]
            series[-1]['energy_equivalent_gini_alive'] = gini(holdings)
            item_trades = [e for e in state['mini_world']['events'] if t-window < e['round'] <= t and e['tool'] == 'accept_items']
            transfers_items = [e for e in state['mini_world']['events'] if t-window < e['round'] <= t and e['tool'] == 'give_item']
            series[-1]['item_trade_graph'] = graph_summary({(e['agent'], e['target']) for e in item_trades}, original)
            series[-1]['item_transfer_graph'] = graph_summary({(e['agent'], e['target']) for e in transfers_items}, original)
        if any(k in cfg['communication'] for k in ('max_turns_before_action','budget')):
            series[-1]['pre_action_communication_counts'] = dict(Counter(
                e['communication']['op'] for e in dialogue if 'communication_error' not in e['outcome']))
            if 'budget' in cfg['communication']:
                consumption=defaultdict(int)
                for event in dialogue:consumption[event['agent']]+=event['budget_charge']
                series[-1].update(communication_budget_unit=cfg['communication']['budget']['unit'],
                    communication_output_consumed=dict(consumption),
                    communication_end_reasons=dict(Counter(e['end_reason'] for e in dialogue if e.get('end_reason'))),
                    communication_final_overrun=sum(e.get('budget_overrun',0) for e in dialogue if e.get('end_reason')))
        if cfg.get('rescue', {}).get('enabled'):
            rescues = [e for e in state.get('rescue_events', []) if t-window < e['round'] <= t]
            series[-1].update(rescue_attempts=len(rescues), rescue_cost=sum(e['paid'] for e in rescues),
                rescue_graph=graph_summary({(e['rescuer'],e['target']) for e in rescues}, original),
                revived_members_this_round=sum(e['activate_round']==t for e in state.get('rescue_events', [])))
        if cfg.get('social_content'):
            social=state['social_content']
            works=[e for e in social['work_events'] if t-window < e['round'] <= t]
            games=[e for e in social['game_events'] if t-window < e['round'] <= t]
            successful=[e for e in state['events'] if t-window < e['round'] <= t and 'action_error' not in e['outcome']]
            wealth=[snapshot['agents'][i]['stock']+snapshot['agents'][i].get('vault',0)+snapshot['agents'][i].get('game_escrow',0) for i in alive]
            series[-1].update(work_creation_by_kind=dict(Counter(e['kind'] for e in works if e['op']=='create')),
                work_revisions=sum(e['op']=='revise' for e in works), work_sales=len(trades),
                paid_work_sales=sum(e['price']>0 for e in trades), free_work_licenses=sum(e['price']==0 for e in trades),
                work_trade_volume=sum(e['price'] for e in trades),work_trade_graph=graph_summary(trade_edges,original),
                work_reads=sum(e['decision']['action']['tool']=='read_artifact' for e in successful),
                informal_play=sum(e['decision']['action']['tool']=='play' for e in successful),
                game_moves=sum(e.get('op')=='move' for e in games),
                game_closures=dict(Counter(e['status'] for e in games if 'status' in e)),
                game_payouts=sum(sum(e['payouts'].values()) for e in games if 'payouts' in e),
                total_game_escrow_alive=sum(snapshot['agents'][i].get('game_escrow',0) for i in alive),
                total_wealth_alive=sum(wealth),wealth_gini_alive=gini(wealth))
        if cfg.get('resource_seizure'):
            attempts=[e for e in state.get('seizure_events',[]) if t-window<e['round']<=t]
            series[-1].update(seizure_attempts=len(attempts),
                seizure_successes=sum(e['success'] for e in attempts),
                seized_stock=sum(e['seized'] for e in attempts),
                seizure_cost=sum(e['paid'] for e in attempts),
                seizure_graph=graph_summary({(e['actor'],e['target']) for e in attempts if e['success']},original))
            if cfg['resource_seizure']['version']=='seizure_v2':
                wealth=[snapshot['agents'][i]['stock']+snapshot['agents'][i].get('vault',0)+snapshot['agents'][i].get('game_escrow',0) for i in alive]
                defense_events=[e for e in state['events'] if t-window<e['round']<=t and 'action_error' not in e['outcome'] and e['decision']['action']['tool']=='defend']
                series[-1].update(wealth_gini_alive=gini(wealth),total_vault_alive=sum(snapshot['agents'][i].get('vault',0) for i in alive),
                    defense_cost=sum(e['outcome'].get('action',{}).get('paid',0) for e in defense_events))
        if cfg.get('mixed_world') or cfg.get('open_contest') or cfg.get('open_activities'):
            series[-1]['activity_counts']=dict(Counter(actions))
        physical = environment.get(t)
        if physical:
            maintenance = list(physical['maintenance'].values())
            met = [m['demand_met'] for m in maintenance if m['demand_met'] is not None]
            series[-1]['maintenance_satisfaction_fraction'] = sum(met)/len(met) if met else None
            series[-1]['recovered_members_this_round'] = sum(m['recovered'] for m in maintenance)
            series[-1]['mean_energy_alive'] = sum(snapshot['agents'][i]['energy'] for i in alive)/len(alive) if alive else None
            series[-1]['physical_diagnostics'] = {key:physical[key] for key in (
                'pool','growth','capacity_loss','shared_return_per_member','converted_output',
                'exogenous_private_inflow','exogenous_inflow','dissipated_cost',
                'unfinished_jobs','exogenous_output','shared_pool','pool_growth','pool_contribution_input',
                'pool_converted_inflow','pool_harvested','pool_capacity_loss','facility_health',
                'interference_targets','maintenance_input','damage_input','available_artifacts',
                'seizure_attempt_cost','seized_stock','vault_storage_loss','threshold_activated','rescue_cost',
                'production_transactions','physical_edges','gross_service_inflows','edge_upkeep',
                'insolvency_removed_edges') if key in physical}
    return {'behavior_surprisal':surprise, 'round_series':series,
            'interpretation': 'Surprisal is an online tool-frequency baseline, not LLM belief or social recognition. '
            'Edge persistence uses overlapping rolling windows and is descriptive, not evidence of an organization. '
            'Graphs retain original members including deaths. Stock concentration uses living members only.'}
