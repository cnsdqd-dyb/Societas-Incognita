"""Audited operational recovery; never modify prompts, world rules or decisions."""
import copy
import hashlib
import json
import os
from pathlib import Path


def install(api_class, cost_cap=None, network_retries=None, reuse_catalog=False, skip_exhausted_surveys=False):
    original_init=api_class.__init__
    original_request=api_class.request
    adapter_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

    def initialize(self,cfg,output,mock=False):
        operational=copy.deepcopy(cfg)
        if cost_cap is not None:operational['max_estimated_cost_usd']=cost_cap
        if network_retries is not None:operational['network_retries']=network_retries
        catalog_path=Path(output)/'model_catalog.json'
        if reuse_catalog and not mock and catalog_path.exists():
            if not os.getenv('OPENROUTER_API_KEY'):
                raise RuntimeError('Local API credential is required')
            # Reuse this run's already verified catalog during short-term resume.
            # Actual per-response billed usage remains authoritative for costs.
            original_init(self,operational,output,True)
            self.mock=False
            self.catalog={m['id']:m for m in json.loads(catalog_path.read_text(encoding='utf-8'))}
            for model in set(cfg['models']):
                m=self.catalog.get(model,{})
                if 'response_format' not in m.get('supported_parameters',[]):
                    raise ValueError('Cached model catalog lacks required output support')
                if cfg.get('structured_outputs') and 'structured_outputs' not in m.get('supported_parameters',[]):
                    raise ValueError('Cached model catalog lacks strict output support')
        else:
            original_init(self,operational,output,mock)
        self.recovery_log=Path(output)/'response_recovery.jsonl'
        self.recovery_attempts={}
        if self.recovery_log.exists():
            for line in self.recovery_log.read_text(encoding='utf-8').splitlines():
                record=json.loads(line)
                key=record['request_key']
                self.recovery_attempts[key]=self.recovery_attempts.get(key,0)+1

    def request(self,model,kind,system,payload,request_key=None):
        while True:
            measurement_error=False
            try:
                value=original_request(self,model,kind,system,payload,request_key)
                if kind=='survey_measurement':
                    from survey_measurement import validate
                    try:validate(value,payload)
                    except ValueError:
                        measurement_error=True
                        raise
                return value
            except ValueError as exc:
                if not measurement_error and str(exc) not in ('Invalid JSON response','Mismatched JSON delimiters',
                    'Non-JSON response; raw response saved in calls.jsonl.',
                    'Cached response is not an object','Response must be a JSON object.'):
                    raise
                if request_key is None or request_key not in self.cached:raise
                with self.lock:
                    if self.recovery_attempts.get(request_key,0)>=2:raise
                    record=self.cached[request_key]
                    # Validate identity again before discarding only the in-memory cache.
                    expected=hashlib.sha256(json.dumps([model,kind,system,payload],
                        ensure_ascii=False,sort_keys=True).encode()).hexdigest()
                    if record['request_hash']!=expected:raise
                    with self.recovery_log.open('a',encoding='utf-8') as handle:
                        handle.write(json.dumps({'request_key':request_key,
                            'failed_call':record['call'],'request_hash':expected,
                            'adapter_hash':adapter_hash,'reason':str(exc)})+'\n')
                        handle.flush();os.fsync(handle.fileno())
                    self.recovery_attempts[request_key]=self.recovery_attempts.get(request_key,0)+1
                    self.cached.pop(request_key)
                # Same model, system, input, key and API accounting; original raw log remains.

    api_class.__init__=initialize
    api_class.request=request
    if skip_exhausted_surveys:
        import survey_measurement as measurement
        def collect_with_missing(society,api,persist=None):
            missing=society.state.setdefault('survey_failures',[])
            for aid,agent in society.state['agents'].items():
                t=society.state['round']
                if not agent['alive'] or any(x['round']==t and x['agent']==aid for x in society.state['surveys']+missing):continue
                model,system,payload=measurement.request_spec(society,aid)
                key=f'survey-measurement:{measurement.VERSION}:{t}:{aid}'
                try:
                    value=api.request(model,'survey_measurement',system,payload,request_key=key)
                    flags=measurement.validate(value,payload)
                except ValueError as exc:
                    if api.recovery_attempts.get(key,0)<2 or key not in api.cached:raise
                    missing.append({'round':t,'agent':aid,'protocol':measurement.VERSION,'request_key':key,
                        'reason':str(exc),'status':'missing_after_two_identical_retries','last_failed_call':api.cached[key]['call'],
                        'adapter_hash':adapter_hash,'note':'No response or rating is imputed. Original requests/replies remain in calls.jsonl.'})
                else:
                    society.state['surveys'].append({'round':t,'agent':aid,'protocol':measurement.VERSION,
                        'responses':value,'effective_responses':measurement.effective(value,payload),
                        **measurement.provenance(society,aid),
                        'quality_flags':flags,'synthetic':api.mock,'scale_validation':'unvalidated_llm_adaptation'})
                if persist:persist()
        measurement.collect=collect_with_missing
