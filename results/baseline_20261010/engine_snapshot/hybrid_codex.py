"""Mixed native/OpenRouter routing with private requests and durable accounting."""
import argparse
import copy
import json
import math
import threading
import time
import sys
from pathlib import Path
from native_codex import NativeCodexAPI, write_json
import recovery_transport


def routed_config(cfg, model):
    route = cfg['model_routes'][model]
    result = copy.deepcopy(cfg)
    for key in ('reasoning', 'provider_only'):
        result.pop(key, None)
    result.update(route.get('parameters', {}))
    return result


def router_class(external_class, native_class=NativeCodexAPI, external_only=False):
    class RoutedExternal(external_class):
        @property
        def cfg(self):
            return getattr(self.local, 'cfg', self.base_cfg)

        @cfg.setter
        def cfg(self, value):
            self.base_cfg = value

        def __init__(self, cfg, output, mock=False):
            self.local = threading.local()
            super().__init__(cfg, output, mock)
            for model,prices in cfg.get('planning_prices',{}).items():
                if model in self.catalog:self.catalog[model]['pricing']=prices

        def request(self, model, kind, system, payload, request_key=None):
            self.local.cfg = routed_config(self.base_cfg, model)
            try:
                return super().request(model, kind, system, payload, request_key)
            finally:
                del self.local.cfg

    class HybridAPI:
        def __init__(self, cfg, output, mock=False):
            if mock:
                raise ValueError('Hybrid transport requires real backends; use sim --mock for mechanics checks')
            self.cfg, self.output, self.mock = cfg, Path(output), False
            self.lock = threading.RLock()
            self.call_floor = self.cost_floor = 0
            routes = cfg['model_routes']
            requested=set(cfg['models'])|({cfg['survey_proxy_model']} if cfg.get('survey_proxy_model') else set())
            if set(routes) != requested:
                raise ValueError('Exactly one backend route is required per model')
            external_models = sorted(m for m in requested if routes[m]['backend'] == 'openrouter')
            native_models = sorted(m for m in requested if routes[m]['backend'] == 'codex_native_cli')
            if set(native_models) != {'gpt-6.1-sol'}:
                raise ValueError('Native evaluator/actor must be GPT-6.1-sol')
            self.external_dir = self.output / 'openrouter'
            self.native_dir = self.output / 'native'
            for directory in (self.external_dir, self.native_dir):
                directory.mkdir(parents=True, exist_ok=True)
            external_cfg = copy.deepcopy(cfg)
            external_cfg['models'] = external_models
            external_cfg['max_calls'] = cfg['max_calls']
            self.external = RoutedExternal(external_cfg, self.external_dir, not external_models)
            # Catalog only contains external models; schemas still see all eight actors.
            self.external.base_cfg = copy.deepcopy(cfg)
            self.external.base_cfg['max_calls'] = external_cfg['max_calls']
            self.external.base_cfg['network_retries'] = 2
            accounting = self.external_dir / 'api_accounting.json'
            if accounting.exists():
                prior = json.loads(accounting.read_text('utf-8'))
                self.external.calls = prior['calls']
                self.external.cost = prior['cost_usd'] + prior.get('reserved_usd', 0)
            native_cfg = copy.deepcopy(cfg)
            native_cfg['max_calls'] = cfg['max_calls']
            self.native = native_class(native_cfg, self.native_dir, False)
            self.accounting()

        @property
        def calls(self):
            return max(self.call_floor, self.external.calls + self.native.calls)

        @calls.setter
        def calls(self, value):
            self.call_floor = value

        @property
        def cost(self):
            return max(self.cost_floor, self.external.cost)

        @cost.setter
        def cost(self, value):
            self.cost_floor = value
            # Restore any global conservative amount into the charged backend too.
            self.external.cost = max(self.external.cost, value)

        @property
        def reserved(self):
            return self.external.reserved

        @property
        def cached(self):
            return {**self.external.cached, **self.native.cached}

        @property
        def recovery_attempts(self):
            return getattr(self.external, 'recovery_attempts', {})

        def accounting(self):
            with self.lock:
                write_json(self.output / 'api_accounting.json', {
                    'calls': self.calls, 'cost_usd': self.cost, 'reserved_usd': self.reserved,
                    'backend': 'hybrid_codex_openrouter', 'external_api_calls': self.external.calls,
                    'native_calls': self.native.calls, 'native_cost_usd': None,
                    'reported_native_usage': self.native.usage})
                records = []
                for directory, backend in ((self.external_dir, 'openrouter'), (self.native_dir, 'codex_native_cli')):
                    log = directory / 'calls.jsonl'
                    for line in log.read_text('utf-8').splitlines() if log.exists() else []:
                        try:
                            record = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        records.append({**record, 'backend': backend})
                # Child logs are authoritative. Rebuild this derived combined view on resume.
                temporary = self.output / 'calls.jsonl.tmp'
                temporary.write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in records), 'utf-8')
                for attempt in range(40):
                    try:
                        temporary.replace(self.output / 'calls.jsonl')
                        break
                    except PermissionError:
                        if attempt == 39:
                            raise
                        time.sleep(.05)

        def request(self, model, kind, system, payload, request_key=None):
            backend = self.cfg['model_routes'][model]['backend']
            target = self.native if backend == 'codex_native_cli' else self.external
            try:
                return target.request(model, kind, system, payload, request_key)
            finally:
                self.accounting()

    return RoutedExternal if external_only else HybridAPI


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    parser.add_argument('--api-key-file', default='../api_key')
    args = parser.parse_args()
    root = Path(args.run).resolve()
    # A runner restart may leave a native child finishing its already-paid reply.
    # Let that child finish so NativeCodexAPI recovers the reply instead of duplicating it.
    import psutil
    pending=[]
    for p in (root/'simulation'/'native'/'native_requests').glob('*/process.json'):
        info=json.loads(p.read_text('utf-8'));pid=info['pid']
        if not psutil.pid_exists(pid):continue
        try:
            process=psutil.Process(pid)
            if str(p.parent.resolve()).lower() in ' '.join(process.cmdline()).lower():pending.append(process)
        except (psutil.NoSuchProcess,psutil.AccessDenied):pass
    for process in pending:
        try:process.wait(timeout=60)
        except psutil.TimeoutExpired:raise RuntimeError('Native CLI failed: previous isolated request still finishing; preserved for recovery')
    sys.path.insert(0, str(root / 'engine_snapshot'))
    import sim
    cfg = json.loads((root / 'config.json').read_text('utf-8'))
    sim.load_api_key(args.api_key_file)
    recovery_transport.install(sim.API, cfg['max_estimated_cost_usd'], 2, True, True)
    native_class=NativeCodexAPI
    if cfg.get('campaign_budget_db'):
        import native_gate
        class GatedNative(NativeCodexAPI):
            def request(self,*args,**kwargs):
                with native_gate.slot(cfg['campaign_budget_db'],32):return super().request(*args,**kwargs)
        native_class=GatedNative
        executor=sim.ThreadPoolExecutor
        sim.ThreadPoolExecutor=lambda max_workers,*a,**kw:executor(max_workers=8,*a,**kw)
        import survey_measurement as measurement
        def deferred_collect(society,api,persist=None):
            t=society.state['round']
            done={x['agent'] for x in society.state['surveys']+society.state.get('survey_failures',[]) if x['round']==t}
            directory=root/'deferred_surveys';directory.mkdir(exist_ok=True)
            for aid,a in society.state['agents'].items():
                if not a['alive'] or aid in done:continue
                model,system,payload=measurement.request_spec(society,aid)
                key=f'survey-measurement:{measurement.VERSION}:{t}:{aid}'
                path=directory/f'round_{t:03d}_{aid}.json'
                entry={'round':t,'agent':aid,'model':model,'system':system,'payload':payload,'request_key':key,
                    'provenance':measurement.provenance(society,aid),'source':'personal_visible_information_at_original_survey_round',
                    'policy':'deferred_external_evidence_proxy; no later trajectory access; not fed to actors'}
                if path.exists():
                    if json.loads(path.read_text('utf-8'))!=entry:raise RuntimeError('Deferred survey snapshot inputs changed')
                else:write_json(path,entry)
                with society.lock:
                    pending=society.state.setdefault('deferred_surveys',[])
                    if not any(x['request_key']==key for x in pending):pending.append({'round':t,'agent':aid,'request_key':key,'snapshot':str(path.relative_to(root))})
                    if persist:persist()
        measurement.collect=deferred_collect
        write_json(root/'operational_concurrency.json',{'agent_workers':8,'survey_policy':'capture_snapshot_then_defer','native_global_concurrency':32,
            'note':'Concurrency override only; frozen config, prompts, physical engine and cached request inputs unchanged.'})
    sim.API = router_class(sim.API,native_class)
    output = root / 'simulation'
    if output.exists() and not (output/'checkpoint.json').exists():
        # Startup can fail in API initialization after writing config but before checkpoint.
        # Preserve that empty attempt; never discard a paid log or an executed state.
        if any(p.stat().st_size for p in output.rglob('calls.jsonl')) or list(output.rglob('response.json')):
            raise RuntimeError('Missing checkpoint alongside model replies; manual recovery required')
        output.rename(root/('startup_failure_archive_'+str(time.time_ns())))
    sim.run(cfg, output, mock=False, resume=(output / 'checkpoint.json').exists())
    result = json.loads((output / 'result.json').read_text('utf-8'))
    accounting = json.loads((output / 'api_accounting.json').read_text('utf-8'))
    state = json.loads((output / 'checkpoint.json').read_text('utf-8'))['state']
    result.update(backend='hybrid_codex_openrouter', external_api_calls=accounting['external_api_calls'],
                  native_calls=accounting['native_calls'], native_cost_usd=None,
                  survey_failures=state.get('survey_failures', []),deferred_surveys=state.get('deferred_surveys',[]),
                  survey_completion_note='Captured personal views await offline proxy; actor trajectory completion is independent of questionnaire completion.')
    write_json(output / 'result.json', result)


if __name__ == '__main__':
    main()
