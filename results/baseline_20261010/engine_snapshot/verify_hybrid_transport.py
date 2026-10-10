"""Offline checks: routing isolation, shared budget, restart and private views."""
import copy
import json
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from hybrid_codex import router_class
from native_codex import write_json
from sim import Society

ROOT = Path('runs/four_model_mix_20261009')

class OfflineExternal:
    def __init__(self, cfg, output, mock=False):
        self.cfg, self.output = cfg, output
        self.calls = 0
        self.cost = self.reserved = 0.0
        self.cached = {}
        self.lock = threading.RLock()
        self.usage = {}
        self.recovery_attempts = {}
    def accounting(self):
        write_json(self.output/'api_accounting.json', {'calls': self.calls, 'cost_usd': self.cost, 'reserved_usd': self.reserved})
    def request(self, model, kind, system, payload, request_key=None):
        if request_key in self.cached:
            return self.cached[request_key]['response']
        barrier = payload.get('barrier')
        if barrier:
            barrier.wait(timeout=10)
        # Reading settings after concurrent requests entered catches shared-config races.
        result = {'model': model, 'reasoning': self.cfg.get('reasoning'), 'only': self.cfg.get('provider_only')}
        with self.lock:
            assert self.calls < self.cfg['max_calls']
            self.calls += 1
            self.cost += .01
            self.cached[request_key] = {'request_key': request_key, 'response': result}
            with (self.output/'calls.jsonl').open('a', encoding='utf-8') as handle:
                handle.write(json.dumps(self.cached[request_key])+'\n')
            self.accounting()
        return result

class OfflineNative(OfflineExternal):
    def __init__(self, cfg, output, mock=False):
        super().__init__(cfg, output, mock)
        saved = output/'api_accounting.json'
        if saved.exists():
            self.calls = json.loads(saved.read_text('utf-8'))['calls']
    def request(self, model, kind, system, payload, request_key=None):
        result = super().request(model, kind, system, payload, request_key)
        self.cost = 0
        return result

def main():
    cfg = json.loads((ROOT/'mixed4_p1/config.json').read_text('utf-8'))
    original = copy.deepcopy(cfg)
    output = ROOT/'offline_transport_validation'
    # This explicit scratch directory contains synthetic transport records only.
    if output.exists():
        resolved = output.resolve()
        assert resolved.parent == ROOT.resolve() and resolved.name == 'offline_transport_validation'
        shutil.rmtree(output)
    output.mkdir()
    factory = router_class(OfflineExternal, OfflineNative)
    api = factory(cfg, output)
    external = [m for m,r in cfg['model_routes'].items() if r['backend']=='openrouter']
    barrier = threading.Barrier(len(external))
    with ThreadPoolExecutor(max_workers=3) as pool:
        answers = list(pool.map(lambda m: api.request(m,'act','private',{'barrier':barrier},request_key=m), external))
    for answer in answers:
        expected = cfg['model_routes'][answer['model']].get('parameters',{})
        assert answer['reasoning'] == expected.get('reasoning')
        assert answer['only'] == expected.get('provider_only')
    assert cfg == original
    api.request('gpt-6.1-sol','act','private',{},request_key='native')
    assert api.calls == 4 and abs(api.cost-.03)<1e-9
    assert api.external.cfg['max_calls'] + api.native.cfg['max_calls'] == cfg['max_calls']
    # Simulate an uncertain in-flight external charge; resume reserves it conservatively.
    api.external.reserved = .02
    api.external.accounting()
    resumed = factory(cfg, output)
    assert resumed.calls == 4 and abs(resumed.cost-.05)<1e-9
    society = Society(cfg)
    for aid in society.state['agents']:
        view = society.observe(aid)
        assert view['self']['id'] == aid
        assert all(set(member)=={'alive'} for member in view['members'].values())
        assert 'model_routes' not in view
    write_json(ROOT/'offline_validation.json', {'status':'passed', 'synthetic_transport_only':True,
        'checks':['concurrent provider/reasoning isolation','native/external dispatch','global call cap partition',
                  'external charge aggregation','conservative uncertain-charge recovery','model labels hidden'],
        'real_mixed_model_calls':0})
    print('Hybrid transport offline validation passed; no real model calls.')

if __name__ == '__main__':
    main()
