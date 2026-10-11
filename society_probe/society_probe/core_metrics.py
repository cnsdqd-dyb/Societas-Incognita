"""Read-only core-metric adapter; missing evidence is never replaced with scores.

Implements directly observable series from CORE_METRICS_V1.md, with conservative
absence checks. Other series remain unavailable pending their evidence protocols.
No actor calls, questionnaire interpretation, or simulation imports.
"""
import argparse
import hashlib
import json
import math
from collections import Counter
from itertools import combinations
from pathlib import Path

VERSION = 'core_metrics_v1'
# Narrow engine-specific proof of absence, not a classifier for arbitrary tools.
# Ordinary harvesting/decay is not a conflict episode in this protocol.
NON_TRANSFER_NON_CONFLICT = {'gather', 'liquidate', 'read_news', 'experiment', 'wait', 'inspect'}
DIMENSIONS = {
    'population': ['active_fraction'],
    'ecology': ['ecological_path_retention'],
    'knowledge': ['verified_rule_coverage', 'knowledge_adoption_coverage'],
    'organization': ['sustained_cooperation_fulfillment'],
    'circulation': ['resource_turnover'],
    'social_order': ['harmful_action_rate', 'damage_recovery_rate'],
    'culture': ['cultural_production_count', 'cross_member_reuse_count'],
    'differentiation': ['behavioral_divergence', 'expression_divergence'],
}
PENDING = {
    'ecological_path_retention': 'missing_path_catalog_and_reachability_evidence',
    'verified_rule_coverage': 'missing_rule_catalog_and_verified_claims',
    'knowledge_adoption_coverage': 'missing_received_rule_and_application_chain',
    'sustained_cooperation_fulfillment': 'missing_confirmed_arrangements_and_obligations',
    'resource_turnover': 'missing_complete_ownership_transfer_and_asset_ledger',
    'harmful_action_rate': 'missing_complete_damage_classification',
    'damage_recovery_rate': 'missing_mature_damage_and_repair_links',
    'cross_member_reuse_count': 'missing_non_author_reuse_evidence',
    'expression_divergence': 'missing_audited_message_coding',
}


def point(value=None, numerator=None, denominator=None, status='missing_evidence',
          coverage=None, sample_size=0, **extra):
    return dict(value=value, numerator=numerator, denominator=denominator,
                status=status, evidence_coverage=coverage, sample_size=sample_size,
                **extra)


def jsd_counts(left, right):
    """Base-two Jensen-Shannon divergence, without smoothing absent categories."""
    a, b = sum(left.values()), sum(right.values())
    if not a or not b or any(v < 0 for v in list(left.values()) + list(right.values())):
        raise ValueError('Nonnegative counts with positive totals required')
    result = 0.0
    for key in sorted(left.keys() | right.keys()):
        p, q = left.get(key, 0) / a, right.get(key, 0) / b
        mean = (p + q) / 2
        if p:
            result += .5 * p * math.log2(p / mean)
        if q:
            result += .5 * q * math.log2(q / mean)
    return min(1., max(0., result))


def measure(state, cfg, window=5, minimum_actions=3):
    if window < 1 or minimum_actions < 1:
        raise ValueError('Positive window and sample threshold required')
    original = sorted(state['agents'])
    if not original:
        raise ValueError('Original member population must be nonempty')
    # Fixed before looking at actions: identity classification at tool level.
    catalog = sorted(set(cfg.get('tools', [])))
    snapshots = state.get('snapshots', [])
    rounds = [s['round'] for s in snapshots]
    if len(set(rounds)) != len(rounds):
        raise ValueError('Duplicate round snapshots')
    rows = []
    for snapshot in sorted(snapshots, key=lambda s: s['round']):
        t = snapshot['round']
        if t > state['round']:
            continue
        first = max(1, t-window+1)
        row = {'round': t, 'window_start': first,
               'window_length': max(0, t-first+1), 'metrics': {}}
        for metric, reason in PENDING.items():
            row['metrics'][metric] = point(reason=reason)
        agents = snapshot['agents']
        complete = all(i in agents and 'alive' in agents[i] for i in original)
        alive = [i for i in original if agents.get(i, {}).get('alive', False)]
        row['active_members'] = alive
        row['original_members'] = original
        row['metrics']['active_fraction'] = (
            point(len(alive)/len(original), len(alive), len(original), 'observed',
                  1., len(original), source=f'snapshots:round:{t}') if complete
            else point(status='incomplete_snapshot'))

        valid = []
        if 'events' in state:
            for index, event in enumerate(state['events']):
                if not first <= event['round'] <= t:
                    continue
                action = event.get('decision', {}).get('action', {})
                outcome = event.get('outcome', {})
                if isinstance(action, dict) and action.get('tool') and 'action_error' not in outcome:
                    valid.append((index, event, action['tool']))
        counts = {i: Counter() for i in alive}
        unknown = Counter()
        for _, event, tool in valid:
            if event['agent'] in counts:
                key = tool if tool in catalog else 'other'
                counts[event['agent']][key] += 1
                if tool not in catalog:
                    unknown[tool] += 1
        eligible = [i for i, c in counts.items() if sum(c.values()) >= minimum_actions]
        distances = [jsd_counts(counts[i], counts[j]) for i, j in combinations(eligible, 2)]
        row['metrics']['behavioral_divergence'] = point(
            sum(distances)/len(distances) if distances else None,
            sum(distances) if distances else None, len(distances),
            'observed' if distances else 'insufficient_sample',
            1. if 'events' in state else None,
            sum(sum(counts[i].values()) for i in eligible),
            participant_ids=eligible, action_distributions={i: dict(c) for i, c in counts.items()},
            uncatalogued_valid_tools=dict(unknown),
            source_event_indices=[n for n, e, _ in valid if e['agent'] in eligible],
            classification='tool_identity_from_config_other_for_uncatalogued',
            opportunity_adjusted=False)
        if 'events' not in state:
            row['metrics']['behavioral_divergence'] = point(status='missing_action_log')

        social = state.get('social_content', {})
        if 'work_events' in social:
            creations = [(n, e) for n, e in enumerate(social['work_events'])
                         if first <= e['round'] <= t and e.get('op') == 'create']
            row['metrics']['cultural_production_count'] = point(
                len(creations), len(creations), None, 'observed', 1., len(creations),
                by_kind=dict(Counter(e['kind'] for _, e in creations)),
                source_work_event_indices=[n for n, _ in creations],
                scope='New work objects including game-rule works; revisions and game sessions excluded')
        else:
            row['metrics']['cultural_production_count'] = point(status='missing_work_creation_log')
        # Certify zeros only with one physical-action record per original member
        # and round. This deliberately abstains for runs with deaths, missing
        # events, new tools or possible transfer/conflict actions.
        history = [e for e in state.get('events', []) if 1 <= e['round'] <= t]
        pairs = Counter((e['round'], e['agent']) for e in history)
        complete_actions = (len(pairs) == t * len(original) and
                            all(pairs[(r, i)] == 1 for r in range(1, t+1) for i in original))
        safe = complete_actions and all(
            e.get('decision', {}).get('action', {}).get('tool') in NON_TRANSFER_NON_CONFLICT
            for e in history)
        native_world = 'mini_world' in state and 'mini_world' in cfg.get('world', {})
        if safe and native_world:
            row['metrics']['harmful_action_rate'] = point(
                0. if valid else None, 0, len(valid), 'absence_verified' if valid else 'undefined',
                1., len(valid), classification='no_conflict_capable_valid_action_in_complete_log',
                scope='Direct conflict; ordinary harvesting and environmental decay excluded')
            row['metrics']['damage_recovery_rate'] = point(
                status='not_applicable', coverage=1., reason='no_direct_conflict_damage_episodes')
            # A zero numerator is proved without claiming that a complete
            # positive-flow ledger or owned-asset reconstruction is implemented.
            positive_assets = all(sum(float(a.get('stock', 0)) for a in s['agents'].values()) > 0
                                  for s in snapshots if first <= s['round'] <= t)
            row['metrics']['resource_turnover'] = point(
                0. if positive_assets else None, 0, None,
                'absence_verified' if positive_assets else 'missing_asset_denominator',
                1., len(valid), denominator_method='positive_lower_bound_from_liquid_stock',
                scope='Zero transfers only; full positive-flow asset ledger not implemented')
        # No created work in the complete history means there is no object for
        # non-author reuse. Existing initial artifacts/games invalidate this.
        if (complete_actions and 'work_events' in social and
                not any(e.get('op') == 'create' and e['round'] <= t for e in social['work_events'])
                and not state.get('culture', {}).get('artifacts') and not social.get('games') and
                not state.get('culture', {}).get('play_records') and not social.get('game_events')):
            row['metrics']['cross_member_reuse_count'] = point(
                0, 0, None, 'absence_verified', 1., 0, reason='no_reusable_work_or_game_objects')
        rows.append(row)
    return {'protocol_version': VERSION, 'dimensions': DIMENSIONS,
            'parameters': {'window': window, 'minimum_actions': minimum_actions,
                           'action_catalog': catalog}, 'round_series': rows,
            'implemented_series': ['active_fraction', 'cultural_production_count', 'behavioral_divergence',
                                   'resource_turnover:zero_only', 'harmful_action_rate:zero_only',
                                   'cross_member_reuse_count:absence_only', 'damage_recovery_rate:no_episode_only'],
            'pending_series': {k: v for k, v in PENDING.items()
                               if not rows or all(r['metrics'][k]['status'] == 'missing_evidence' for r in rows)},
            'questionnaires_used': False,
            'interpretation': 'Descriptive measures, not a society rating. Semantic/physical evidence gaps are null, not zero.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--window', type=int, default=5)
    args = parser.parse_args()
    if args.output.resolve() in {args.checkpoint.resolve(), args.config.resolve()}:
        raise ValueError('Analysis output must not replace a source file')
    source = args.checkpoint.read_bytes()
    config = args.config.read_bytes()
    loaded = json.loads(source)
    report = measure(loaded.get('state', loaded), json.loads(config), args.window)
    report['source_hashes'] = {'checkpoint_sha256': hashlib.sha256(source).hexdigest(),
                              'config_sha256': hashlib.sha256(config).hexdigest()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps({'output': str(args.output), 'rounds': len(report['round_series']),
                      'implemented_adapters': len(report['implemented_series'])}))


if __name__ == '__main__':
    main()
