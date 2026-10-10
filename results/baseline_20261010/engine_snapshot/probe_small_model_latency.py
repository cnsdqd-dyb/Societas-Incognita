"""Uniform short-output timing probe, charged within the existing shared ceiling."""
import json
import statistics
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import sim
from hybrid_codex import router_class


def main():
    root=Path('reports/cheap_small_model_plan/latency_probe')
    if root.exists():raise ValueError('Refusing to repeat a paid timing probe')
    root.mkdir(parents=True)
    cfg=json.loads(Path('configs/cheap_small8_v4_20261009/M2_cheap_small8_p1.json').read_text('utf-8'))
    cfg.update(max_calls=24,max_output_tokens=128,max_estimated_cost_usd=.05,network_retries=0,temperature=0.)
    cfg['campaign_budget_db']=str(Path('runs/multi_environment_v2_20261009/budget.sqlite3').resolve())
    sim.load_api_key('../api_key')
    api=router_class(sim.API,external_only=True)(cfg,root,False)
    view=sim.Society(cfg).observe('a0')
    phrase='This is a short timing probe. I can communicate, stop voluntarily, or wait for the next observation.'
    wanted={'communication':{'op':'public','text':phrase}}
    system='This is an isolated transport-speed measurement, not a social simulation. Copy exactly this JSON and add nothing: '+json.dumps(wanted)
    records=[]
    for repeat in range(3):
        def run(mid):
            key=f'latency:{repeat}:{mid}';started=time.time()
            try:
                answer=api.request(mid,'communicate',system,view,request_key=key)
                rec=api.cached[key]
                return {'model':mid,'repeat':repeat,'seconds':rec['seconds'],'wall_seconds':time.time()-started,
                        'correct_fixed_output':answer==wanted,'usage':rec.get('usage',{}),'status':'ok'}
            except Exception as exc:
                return {'model':mid,'repeat':repeat,'wall_seconds':time.time()-started,'status':'error',
                        'error_type':type(exc).__name__,'error':str(exc)[:250]}
        with ThreadPoolExecutor(max_workers=8) as pool:
            records.extend(pool.map(run,cfg['models']))
        (root/'progress.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),'utf-8')
        print(json.dumps({'repeat_complete':repeat+1,'calls':api.calls,'cost_usd':api.cost,'errors':sum(r['status']=='error' for r in records)},ensure_ascii=False),flush=True)
    ranking=[]
    for mid in cfg['models']:
        rows=[r for r in records if r['model']==mid]
        seconds=[r['seconds'] for r in rows if r['status']=='ok']
        ranking.append({'model':mid,'successful_calls':len(seconds),'failures':len(rows)-len(seconds),
                        'median_seconds':statistics.median(seconds) if seconds else None,
                        'max_seconds':max(seconds) if seconds else None,
                        'fixed_output_successes':sum(r.get('correct_fixed_output',False) for r in rows)})
    ranking.sort(key=lambda r:(r['failures'],r['median_seconds'] or float('inf')),reverse=True)
    result={'calls':api.calls,'cost_usd':api.cost,'ranking_slowest_first':ranking,'records':records,
            'scope':'3 identical-context short-output calls per selected model/provider, concurrent waves of 8. End-to-end response timing, not intrinsic model speed or long-run performance. Failed calls ranked before successful calls; no automatic retries.',
            'simulations_launched':0,'output_token_cap':128,'local_usd_cap':.05}
    (root/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='records'},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
