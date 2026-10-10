"""Upgrade prepared templates to volume allowances; never launch model calls."""
import argparse
import copy
import json
from pathlib import Path
import interaction_controls as controls
import sim


def upgrade(c,limit=1000,unit='characters'):
    c=controls.configure(c,visibility=c['world_rule_visibility'],
        rescue_enabled=c['rescue']['enabled'],restore_energy=c['rescue']['restore_energy'],
        cost_per_energy=c['rescue']['cost_per_energy'],communication_budget={'unit':unit,'limit':limit})
    # Message-size syntax limit is independent of the remaining allowance.
    c['communication']['max_message_chars']=4000
    c['experiment'].pop('pre_action_communication_limit',None)
    c['experiment'].update(stage='communication_v4_prepared_not_run',interaction_version='v4',
        communication_budget={'unit':unit,'limit':limit},
        comparison_note='Matched v4 volume budgets; legacy turn-limit trajectories use a different communication intervention.')
    # Positive charge per returned response bounds request count without imposing
    # a separate turn ceiling. Financial limits still independently apply.
    c['max_calls']=len(c['models'])*c['rounds']*(1+limit)+1000
    sim.Society(c)
    return c


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='configs/communication_v4_20261009')
    args=parser.parse_args();out=Path(args.output)
    if out.exists():raise RuntimeError('Refusing to overwrite prepared templates')
    old=Path('configs/interaction_v3_20261009')
    index=json.loads((old/'index.json').read_text('utf-8'))
    prepared={name:upgrade(json.loads((old/(name+'.json')).read_text('utf-8'))) for name in index['configs'][:70]}
    for name in ['M5_mixed4_p1_hidden','M5_mixed4_p1_no_rescue']:
        prepared[name]=upgrade(json.loads((old/(name+'.json')).read_text('utf-8')))
    base=json.loads((old/'M5_mixed4_p1.json').read_text('utf-8'))
    for limit in (0,300,600,2000):prepared[f'M5_mixed4_p1_chars{limit}']=upgrade(copy.deepcopy(base),limit)
    prepared['M5_mixed4_p1_tokens600']=upgrade(copy.deepcopy(base),600,'tokens')
    out.mkdir(parents=True)
    for name,c in prepared.items():(out/(name+'.json')).write_text(json.dumps(c,ensure_ascii=False,indent=2)+'\n','utf-8')
    result={'stage':'prepared_not_run','total_configs':len(prepared),'base_configs':70,'configs':list(prepared),
        'defaults':{'agents':8,'rounds':50,'communication_budget':{'unit':'characters','limit':1000},
                    'budget_scope':'per agent per physical round','final_response':'retained in full',
                    'voluntary_end':True,'max_message_chars':4000},
        'real_api_budget_per_template_usd':0,'launched_runs':0}
    (out/'index.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n','utf-8')
    print(json.dumps({'prepared':len(prepared),'launched_runs':0,'output':str(out)},ensure_ascii=False))


if __name__=='__main__':main()
