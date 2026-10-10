"""Empirical all-survive projection; excludes proxy surveys from external API."""
import json
from collections import defaultdict
from pathlib import Path
from native_codex import write_json
ROOT=Path('runs/multi_environment_v2_20261009')
def main():
    groups=defaultdict(lambda:{'calls':0,'billed':0.,'input':0,'output':0})
    files=list(Path('runs/four_model_mix_20261009').glob('*/simulation/openrouter/calls.jsonl'))
    for file in files:
        for line in file.read_text('utf-8').splitlines():
            r=json.loads(line);g=groups[(r['requested_model'],r['kind'])];u=r.get('usage',{})
            g['calls']+=1;g['billed']+=float(u.get('cost') or 0);g['input']+=u.get('prompt_tokens',0);g['output']+=u.get('completion_tokens',0)
    plan={'act':7000,'memory_episode':1680,'memory_overview':840};rows=[]
    for (model,kind),g in groups.items():
        if kind not in plan:continue
        rows.append({'model':model,'kind':kind,'observed_calls':g['calls'],
            'mean_prompt_tokens':g['input']/g['calls'],'mean_output_tokens':g['output']/g['calls'],
            'mean_billed_usd':g['billed']/g['calls'],'planned_full_survival_calls':plan[kind],
            'projected_usd_at_previous_per_kind_average':plan[kind]*g['billed']/g['calls']})
    base=sum(r['projected_usd_at_previous_per_kind_average'] for r in rows)
    write_json(ROOT/'COST_ESTIMATE.json',{'method':'Historical mixed-case mean cost per model/request-kind times full-survival call counts; narrative and new mechanisms may increase context.',
        'historical_source_files':[str(p) for p in files],'details':rows,'base_usd':base,
        'planning_interval_usd':[8,12],'suggested_external_api_cap_usd':15,
        'external_requests_without_retries':28560,'native_requests_without_retries':12880,
        'native_calls_breakdown':{'acts':7000,'episode_memory':1680,'overview_memory':840,'proxy_surveys':3360},
        'first_two_mixed_cases_native_requests_without_retries':368,
        'current_authorized_remaining_api_usd':4.277054114,'native_cost_usd':None,
        'uncertainty':'These are projections, not charges or guaranteed ceilings. Death reduces later calls; retries consume additional budget. Shared budget enforces actual authorized ceiling.'})
    print(json.dumps({'historical_average_projection_usd':base,'planning_interval_usd':[8,12],'native_full_survival_calls':12880,'native_first_two_calls':368}))
if __name__=='__main__':main()
