"""Offline replay of recorded model decisions; never invokes a model or API."""
import argparse
import copy
import hashlib
import json
import os
import sys
import threading
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def canonical_state(state):
    state = copy.deepcopy(state)
    # Independent private compactions can finish in a different thread order.
    # Keep every record and compare its content, while ignoring completion order.
    state['compactions'] = sorted(state.get('compactions', []), key=lambda row: json.dumps(row, ensure_ascii=False, sort_keys=True))
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    root, output = Path(args.run).resolve(), Path(args.output).resolve()
    if output.exists():
        raise ValueError('Replay output already exists; use a fresh directory')
    from native_codex import find_local_lean
    lean = find_local_lean()
    if lean:
        os.environ['PATH'] = str(Path(lean).parent) + os.pathsep + os.environ.get('PATH', '')
    engine = root / 'engine_snapshot'
    if not engine.exists():
        engine = root.parent / 'engine_snapshot'
    sys.path.insert(0, str(engine))
    import sim
    import schemas
    import jsonschema
    records = {}
    for line in (root / 'simulation/calls.jsonl').read_text('utf-8').splitlines():
        row = json.loads(line)
        key = row['request_key']
        external = isinstance(row.get('response'), str)
        if external:
            try:
                value, _ = sim.decode_response(row['response'])
                from provider_schema import validate_phase_response
                validate_phase_response(row['kind'], value)
            except ValueError:
                # Failed paid outputs were never accepted into the trajectory.
                continue
            row = {**row, 'response': value, 'external_record': True}
        if key in records and records[key]['request_hash'] != row['request_hash']:
            raise ValueError('Conflicting inputs for a stable request key')
        records[key] = row

    class RecordedAPI:
        def __init__(self, cfg, folder, mock=False):
            self.cfg, self.calls, self.cost, self.reserved = cfg, 0, 0.0, 0.0
            self.lock = threading.RLock()
            self.used = set()

        def request(self, model, kind, system, payload, request_key=None):
            if request_key not in records:
                raise ValueError('Replay has no recorded reply: ' + str(request_key))
            record = records[request_key]
            if digest([model, kind, system, payload]) != record['request_hash']:
                raise ValueError('Replay observation/prompt differs: ' + request_key)
            if record.get('external_record'):
                from provider_schema import validate_phase_response
                validate_phase_response(kind, record['response'])
            else:
                jsonschema.validate(record['response'], schemas.schema(kind, payload, self.cfg))
            with self.lock:
                if request_key not in self.used:
                    self.calls += 1
                    self.used.add(request_key)
            return copy.deepcopy(record['response'])

    sim.API = RecordedAPI
    cfg = json.loads((root / 'config.json').read_text('utf-8'))
    if cfg.get('experiment', {}).get('stage') == 'small_functional_natural_inventory_pilot':
        from functional_pilot_admission import install
        install(root)
    elif cfg.get('experiment', {}).get('stage') == 'functional_homogeneous_4x50_runtime_comparison':
        from functional_comparison_admission import install
        install(root)
    sim.run(cfg, output, mock=False, resume=False)
    original = json.loads((root / 'simulation/checkpoint.json').read_text('utf-8'))['state']
    replay = json.loads((output / 'checkpoint.json').read_text('utf-8'))['state']
    original_hash, replay_hash = digest(canonical_state(original)), digest(canonical_state(replay))
    report = {'status': 'matched' if original_hash == replay_hash else 'mismatch',
              'seed': cfg['seed'], 'completed_rounds': replay['round'],
              'source_run': str(root), 'original_state_sha256': original_hash,
              'replayed_state_sha256': replay_hash, 'raw_state_equal': original == replay,
              'normalization': 'Only independent compaction log completion order is ignored; all contents retained',
              'external_api_calls': 0, 'native_model_calls': 0,
              'scope': 'Same frozen engine and runtime, recorded model replies, exact request-input hashes. Cross-platform floating point equality is not guaranteed.'}
    (output / 'replay_verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False), flush=True)
    if report['status'] != 'matched':
        raise ValueError('Recorded trajectory failed state reproduction')


if __name__ == '__main__':
    main()
