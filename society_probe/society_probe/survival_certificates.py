"""Replay witnesses and export a small, deliberately restricted Lean checker.

Python replay is not a formal proof. The initial Lean projection accepts only
integer, noiseless gather/convert/wait worlds with constant pool regeneration,
unit harvesting/liquidation efficiency, no decay, and no binding energy reserve.
Other worlds remain uncertified; never silently project away their dynamics.
"""
import copy
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import environments
import interaction_controls
import mini_world
from world_rule_library import digest


def replay(cfg, plan, initial_state=None):
    from sim import Society
    s = Society(cfg)
    if initial_state is not None: s.state = copy.deepcopy(initial_state)
    if s.state['mini_world']['pending']: raise ValueError('Witness starts after settlement')
    trace = []; all_alive = True; n = len(cfg['models']); start = s.state['round']
    for index, joint in enumerate(plan, start+1):
        s.state['round'] = index; interaction_controls.start_round(cfg, s.state)
        if cfg.get('resource_seizure', {}).get('version') == 'seizure_v2':
            import resource_seizure
            resource_seizure.start_round(s.state)
        before = environments.physical_snapshot(s.state)
        if set(joint) != {a for a, v in s.state['agents'].items() if v['alive']}:
            raise ValueError('Witness provides exactly one action per active member')
        for aid in sorted(joint): s.act(aid, copy.deepcopy(joint[aid]))
        s.settle(before)
        alive = sum(a['alive'] for a in s.state['agents'].values()); all_alive &= alive == n
        trace.append({'round': index, 'alive': alive,
                      'agents': {aid: {k: copy.deepcopy(a[k]) for k in ('stock', 'energy', 'alive', 'inventory')} for aid, a in s.state['agents'].items()},
                      'pools': copy.deepcopy(s.state['mini_world']['pools']), 'reserve': s.state['mini_world']['reserve'],
                      'energy_accounting': mini_world.accounting(cfg, s.state)})
    return {'status': 'replayed_full_survival' if all_alive else 'replayed_deaths',
            'formal_status': 'not_lean_verified', 'world_sha256': digest(mini_world.spec(cfg)),
            'start_round': start, 'horizon': len(plan), 'members': n, 'score': sum(t['alive'] for t in trace),
            'population_time_upper_bound': n*len(plan), 'plan': copy.deepcopy(plan), 'trace': trace,
            'noise_scope': 'deterministic' if mini_world.spec(cfg)['noise']['distribution'] == 'none' else 'fixed_seed_trajectory_only',
            'information_scope': 'omniscient_action_witness; not an unknown-rule exploration certificate'}


def alternating_plan(cfg, horizon=None, amount=2, item='A'):
    n = len(cfg['models']); horizon = cfg['rounds'] if horizon is None else horizon
    return [{f'a{i}': {'tool': 'gather' if t % 2 else 'liquidate', 'item': item, 'amount': amount}
             for i in range(n)} for t in range(1, horizon+1)]


def integer(value):
    if type(value) not in (int, float) or value < 0 or int(value) != value:
        raise ValueError('Restricted Lean projection requires nonnegative integers')
    return int(value)


def lean_projection(cfg, witness):
    d = mini_world.spec(cfg); w = cfg['world']
    if witness['start_round'] != 0 or d['noise']['distribution'] != 'none':
        raise ValueError('First checker supports initial-state deterministic witnesses only')
    keys = list(d['resources']); initial = d.get('initial_inventory', {})
    for r in d['resources'].values():
        if r['decay'] != 0 or r['liquidation_efficiency'] != 1: raise ValueError('Decay/efficiency is outside initial Lean checker')
    for p in d['pools'].values():
        if p.get('harvest_efficiency', 1) != 1: raise ValueError('Non-unit harvest efficiency is outside checker')
        if p.get('depletion', 0) != 0: raise ValueError('Ecological depletion is outside initial checker')
    scalar_names = ('initial_reserve', 'reserve_capacity', 'external_inflow')
    params = {k: integer(d[k]) for k in scalar_names}
    params.update(densities=[integer(d['resources'][k]['energy_value']) for k in keys],
        capacity=[integer(d['pools'][k]['capacity']) if k in d['pools'] else 0 for k in keys],
        regeneration=[integer(d['pools'][k]['regeneration']) if k in d['pools'] else 0 for k in keys],
        pools=[integer(d['pools'][k]['initial']) if k in d['pools'] else 0 for k in keys],
        inventory=[integer(initial.get(k, 0)) for k in keys],
        initial_stock=integer(w.get('initial_personal_stock', 4)), consumption=integer(w['consumption']),
        pressure=bool(w['survival_pressure']), members=len(cfg['models']))
    for joint in witness['plan']:
        if sorted(joint) != [f'a{i}' for i in range(params['members'])]: raise ValueError('Unsupported agent order')
        for a in joint.values():
            if a['tool'] not in ('wait', 'gather', 'liquidate'): raise ValueError('Action outside Lean subset')
            if a['tool'] != 'wait':
                integer(a['amount'])
                if a['item'] not in keys: raise ValueError('Unknown material')
                if a['tool'] == 'gather' and a['item'] not in d['pools']: raise ValueError('No material pool')
    # The Lean step checks nonbinding reserve independently. The projection does
    # not authorize opaque dynamics: all regeneration and inflow above are literal.
    return params, keys


def export_lean(cfg, witness, path):
    checked = replay(cfg, witness['plan'])
    if checked['status'] != 'replayed_full_survival' or checked['world_sha256'] != witness['world_sha256'] or checked['trace'] != witness['trace']:
        raise ValueError('Witness must match independent simulator replay before export')
    p, keys = lean_projection(cfg, witness)
    natlist = lambda xs: '['+', '.join(str(integer(x)) for x in xs)+']'
    rounds = []
    for joint in witness['plan']:
        actions = []
        for aid, a in sorted(joint.items()):
            action = '.idle' if a['tool'] == 'wait' else f".{'gather' if a['tool']=='gather' else 'convert'} {keys.index(a['item'])} {integer(a['amount'])}"
            actions.append(f'({int(aid[1:])}, {action})')
        rounds.append('['+', '.join(actions)+']')
    checker = Path(__file__).with_name('survival_checker.lean').read_text('utf-8')
    instance = f'''\n-- World definition SHA256: {witness['world_sha256']}
def certifiedWorld : World := {{
  densities := {natlist(p['densities'])}, capacity := {natlist(p['capacity'])},
  regeneration := {natlist(p['regeneration'])}, reserveCapacity := {p['reserve_capacity']},
  externalInput := {p['external_inflow']}, consumption := {p['consumption']},
  pressure := {'true' if p['pressure'] else 'false'} }}
def certifiedInitial : Physical := {{
  members := List.replicate {p['members']} {{ stock := {p['initial_stock']}, vitality := 5, inventory := {natlist(p['inventory'])} }},
  pools := {natlist(p['pools'])}, reserve := {p['initial_reserve']} }}
def certifiedPlan : List Joint := [{', '.join(rounds)}]
set_option maxRecDepth 100000
set_option maxHeartbeats 0
theorem certified_survival : survives certifiedWorld certifiedInitial certifiedPlan = true := by decide
theorem certified_survival_score : survivalScore certifiedWorld certifiedInitial certifiedPlan = some {p['members']*len(rounds)} := by decide
'''
    source = checker+instance; target = Path(path); target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, 'utf-8')
    return {'source': str(target.resolve()), 'sha256': hashlib.sha256(source.encode()).hexdigest(),
            'status': 'exported_not_checked', 'scope': 'Restricted deterministic integer physical projection; no proof of unknown-rule discoverability or full social simulator.'}


def find_lean():
    binary = shutil.which('lean')
    if binary: return binary
    root = Path(__file__).resolve().parent/'.tools'
    manifest = root/'lean-install.json'
    if manifest.exists():
        binary = Path(json.loads(manifest.read_text('utf-8'))['executable']).resolve()
        if binary.is_relative_to(root.resolve()) and binary.exists(): return str(binary)
    return None


def check_lean(artifact, executable=None, timeout=120):
    binary = executable or find_lean()
    if not binary: return {**artifact, 'status': 'lean_unavailable'}
    path = Path(artifact['source']); source = path.read_text('utf-8')
    if hashlib.sha256(source.encode()).hexdigest() != artifact['sha256']:
        raise ValueError('Lean source changed after export')
    # This checker accepts only our generated, sorry-free source.
    if any(token in source for token in ('sorry', 'axiom ', 'unsafe ', 'native_decide', 'set_option debug.skipKernelTC')):
        raise ValueError('Untrusted proof construct')
    # Large closed certificates need predictable worker/stack resources on
    # Windows. This changes scheduling only, never proof trust or kernel checks.
    try:
        result = subprocess.run([binary, '-j2', '-s65536', '-DElab.async=false', str(path)], capture_output=True, text=True, encoding='utf-8', timeout=timeout)
    except subprocess.TimeoutExpired:
        return {**artifact,'status':'lean_timeout','timeout_seconds':timeout,
                'diagnostics':'Lean exceeded the time limit; this is not a proof of impossibility.'}
    status = 'lean_checked_restricted_projection' if result.returncode == 0 else 'lean_rejected'
    if result.returncode != 0 and not (result.stdout+result.stderr).strip():
        status = 'lean_process_failed'
    return {**artifact, 'status': status,
            'returncode': result.returncode, 'diagnostics': (result.stdout+result.stderr)[-8000:]}


def validate_admission(cfg):
    """No paid mini-world experiment is admitted from a replay-only certificate."""
    if cfg.get('require_end_to_end_world_proof'):
        raise ValueError('End-to-end world proof is not implemented: world lowering and IEEE runtime equivalence remain trusted boundaries')
    reference = cfg.get('survival_certificate')
    if not reference:
        raise ValueError('Mini-world research runs require a checked survival certificate; offline/mock runs remain available')
    path = Path(reference['path']); raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != reference['sha256']:
        raise ValueError('Survival certificate document changed')
    bundle = json.loads(raw.decode('utf-8'))
    if bundle.get('version') in ('composed_interval_survival_v1','composed_semantic_survival_v2'):
        import composed_certificates
        return composed_certificates.validate_admission(cfg,bundle)
    witness = bundle['witness']
    if bundle['lean']['status'] != 'lean_checked_restricted_projection':
        raise ValueError('Survival certificate has not passed Lean')
    if witness['horizon'] != cfg['rounds'] or witness['members'] != len(cfg['models']):
        raise ValueError('Certificate horizon/population mismatch')
    # Regenerate the proof from this configuration; a detached source hash or
    # self-reported verification status cannot substitute for matching equations.
    with tempfile.TemporaryDirectory() as directory:
        expected = export_lean(cfg, witness, Path(directory)/'certificate.lean')
        if expected['sha256'] != bundle['lean']['sha256']:
            raise ValueError('Certificate does not match current checker/world')
        checked = check_lean(expected)
    if checked['status'] != 'lean_checked_restricted_projection':
        raise ValueError('Lean verification unavailable or rejected for this world')
    return checked
