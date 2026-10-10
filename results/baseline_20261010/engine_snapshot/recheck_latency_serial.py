"""Repair missing timing observations under sequential provider calls, same $0.05 cap."""
import json
import statistics
import time
from pathlib import Path
import sim
from hybrid_codex import router_class


def main():
    root=Path('reports/cheap_small_model_plan/latency_probe')
    if (root/'serial_result.json').exists():raise ValueError('Sequential probe already complete')
    prior=json.loads((root/'api_accounting.json').read_text('utf-8'))
    cfg=json.loads(Path('configs/cheap_small8_v4_20261009/M2_cheap_small8_p1.json').read_text('utf-8'))
    cfg.update(max_calls=36,max_output_tokens=128,max_estimated_cost_usd=.05,network_retries=0,temperature=0.)
    cfg['campaign_budget_db']=str(Path('runs/multi_environment_v2_20261009/budget.sqlite3').resolve())
    sim.load_api_key('../api_key')
    api=router_class(sim.API,external_only=True)(cfg,root,False)
    api.calls=prior['calls'];api.cost=prior['cost_usd']
    view=sim.Society(cfg).observe('a0')
    phrase='This is a short timing probe. I can communicate, stop voluntarily, or wait for the next observation.'
    wanted={'communication':{'op':'public','text':phrase}}
    system='This is an isolated transport-speed measurement, not a social simulation. Copy exactly this JSON and add nothing: '+json.dumps(wanted)
    selected=[mid for mid in cfg['models'] if cfg['model_routes'][mid]['parameters']['provider_only']==['DeepInfra']]
    records=[]
    for repeat in range(3):
        for mid in selected if repeat%2==0 else reversed(selected):
            key=f'latency-serial:{repeat}:{mid}';started=time.time()
            try:
                answer=api.request(mid,'communicate',system,view,request_key=key)
                rec=api.cached[key]
                row={'model':mid,'repeat':repeat,'seconds':rec['seconds'],'correct_fixed_output':answer==wanted,'usage':rec.get('usage',{}),'status':'ok'}
            except Exception as exc:
                row={'model':mid,'repeat':repeat,'wall_seconds':time.time()-started,'status':'error','error_type':type(exc).__name__,'error':str(exc)[:200]}
            records.append(row)
            (root/'serial_progress.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),'utf-8')
        print(json.dumps({'serial_repeat_complete':repeat+1,'calls':api.calls,'total_cost_usd':api.cost},ensure_ascii=False),flush=True)
    initial=json.loads((root/'result.json').read_text('utf-8'))
    combined=[r for r in initial['records'] if r['model'] not in selected]+records
    ranking=[]
    for mid in cfg['models']:
        rows=[r for r in combined if r['model']==mid];times=[r['seconds'] for r in rows if r['status']=='ok']
        ranking.append({'model':mid,'successes':len(times),'failures':len(rows)-len(times),'median_seconds':statistics.median(times) if times else None,
                        'timing_source':'serial_provider_recheck' if mid in selected else 'initial_concurrent_wave'})
    # HTTP failures do not establish response speed. Only valid measurements rank.
    ranking.sort(key=lambda r:r['median_seconds'] if r['median_seconds'] is not None else -1,reverse=True)
    report={'ranking_slowest_successful_first':ranking,'records':records,'total_cost_usd':api.cost,'total_calls':api.calls,
            'scope':'Three short-output timings per model. DeepInfra rechecked serially after initial rate limits; others retain concurrent-wave measurements. Exploratory endpoint-speed estimate; concurrency conditions differ. Failures never labeled slowest.',
            'simulations_launched':0,'local_total_usd_cap':.05}
    (root/'serial_result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='records'},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
