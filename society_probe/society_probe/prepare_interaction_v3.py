"""Prepare offline templates only. Does not fetch prices, read keys or start actors."""
import argparse
import json
from pathlib import Path

import interaction_controls as controls
import social_content
import sim
from prepare_environment_review import DESIGNS,MODELS
from prepare_multi_environment_v2 import config


def make(source,design,population,pressure,visibility='full',rescue=True,turns=3):
    c=config(source,design,population,pressure)
    c=controls.configure(c,visibility=visibility,rescue_enabled=rescue,restore_energy=3,
                         cost_per_energy=1.,max_turns_before_action=turns)
    c=social_content.configure(c)
    c.pop('campaign_budget_db',None)
    c['rounds']=50;c['parallel_agents']=8
    c['max_calls']=8*50*(1+turns)+1000
    # New template remains offline while the user's campaign is paused.
    c['max_estimated_cost_usd']=0.
    c['max_output_tokens']=max(1024,c['max_output_tokens'])
    c['survey_rounds']=[]
    c['experiment'].update(stage='interaction_v3_prepared_not_run',
        interaction_version='v3',world_rule_visibility=visibility,rescue_enabled=rescue,
        pre_action_communication_limit=turns,
        comparison_note='New protocol: compare matched v3 cases; old trajectories use a different action/communication space.',
        questionnaire_note='No questionnaire calls in these offline templates; configure historical-view capture before future execution.')
    sim.Society(c)  # Validate schema-independent engine initialization; no API.
    return c


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default='configs/interaction_v3_20261009')
    args=parser.parse_args();out=Path(args.output)
    if out.exists():raise RuntimeError('Refusing to overwrite existing v3 templates')
    source=json.loads(Path('configs/open_contest_mix_v1_20261009/contest_mixed4_p1_s7.json').read_text('utf-8'))
    prepared={}
    for design in DESIGNS:
        for population in ['mixed4',*MODELS]:
            for pressure in (0,1):
                name=f'{design["id"]}_{population}_p{pressure}'
                prepared[name]=make(source,design,population,pressure)
    design=next(d for d in DESIGNS if d['id']=='M5')
    variants={'hidden':{'visibility':'hidden'},'no_rescue':{'rescue':False},
              **{f'comm{k}':{'turns':k} for k in (0,1,2,6)}}
    for label,options in variants.items():
        prepared['M5_mixed4_p1_'+label]=make(source,design,'mixed4',1,**options)
    out.mkdir(parents=True)
    for name,c in prepared.items():
        (out/(name+'.json')).write_text(json.dumps(c,ensure_ascii=False,indent=2)+'\n','utf-8')
    index={'stage':'prepared_not_run','total_configs':len(prepared),'base_configs':70,
        'offline_only':True,'real_api_budget_per_template_usd':0,
        'defaults':{'agents':8,'rounds':50,'world_rule_visibility':'full',
                    'rescue_energy':3,'rescue_cost':3,'pre_action_communication_limit':3},
        'configs':list(prepared),'ablations':variants}
    (out/'index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps({'output':str(out),'templates':len(prepared),'launched_runs':0},ensure_ascii=False))


if __name__=='__main__':main()
