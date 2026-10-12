"""Completed version cohorts; attempts, actual settlements and successes separated."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'society_probe/society_probe'
OUT=ROOT/'results/version_comparison_20261012'


def read(p):return json.loads(p.read_text('utf-8'))


def summarize(label,version,folder):
    folder=Path(folder);cp=read(folder/'simulation/checkpoint.json');s=cp['state']
    cfg=read(folder/'config.json') if (folder/'config.json').exists() else read(folder/'simulation/config.json')
    horizon=s['round'];events=[e for e in s['events'] if e['round']<=horizon]
    valid=[e for e in events if not e['outcome'].get('action_error')]
    productions=[e for h in s.get('environment_history',[]) if h.get('round',0)<=horizon for e in h.get('completed_experiments',[])]
    physical=[e for e in s.get('mini_world',{}).get('events',[]) if e.get('round',0)<=horizon]
    works=list(s.get('culture',{}).get('artifacts',{}).values())
    assembly=[e for e in events if e['decision']['action']['tool']=='assemble_device']
    successes=[e for e in assembly if e['outcome'].get('action',{}).get('assembled') is True]
    actions=Counter(e['decision']['action']['tool'] for e in events)
    snapshots=s.get('snapshots',[])
    row={'label':label,'version':version,'rounds':horizon,'members':len(s['agents']),
        'pressure':cfg['world'].get('survival_pressure',False),'world_sha256':hashlib.sha256(json.dumps(cfg['world'],sort_keys=True).encode()).hexdigest(),
        'alive':sum(a['alive'] for a in s['agents'].values()),'alive_person_rounds':sum(sum(a['alive'] for a in snap['agents'].values()) for snap in snapshots),
        'action_attempts':len(events),'valid_actions':len(valid),'invalid_actions':len(events)-len(valid),
        'invalid_fraction':(len(events)-len(valid))/len(events) if events else None,
        'experiment_attempts':actions.get('experiment',0),'settled_experiments':len(productions),
        'productive_experiments':sum(any(v>0 for v in e.get('produced',{}).values()) for e in productions),
        'assembly_attempts':len(assembly),'successful_assemblies':len(successes),
        'positive_material_transfers':sum(e['tool']=='give_item' and e.get('amount',0)>0 for e in physical),
        'material_trades':sum(e['tool']=='accept_items' for e in physical),
        'works':len(works),'works_at_most_8_chars':sum(len(w.get('content',''))<=8 for w in works),
        'informal_play_valid':sum(e['decision']['action']['tool']=='play' for e in valid),
        'games_created':len(s.get('social_content',{}).get('games',{})),
        'native':cfg.get('backend')=='codex_native_cli','external_api_usd':cp.get('cost_usd'),
        'native_cost_usd':None if cfg.get('backend')=='codex_native_cli' else 0,
        'mode_labels':cfg.get('mode_labels',{}).get('version','semantic'),
        'names':cfg.get('identity_names',{}).get('version','IDs'),
        'detailed_feedback':any('action_feedback' in e['outcome'] for e in events) or bool(cfg.get('experiment',{}).get('feedback_protocol')),
        'actions':dict(actions),'accepted_actions':dict(Counter(e['decision']['action']['tool'] for e in valid)),
        'source':folder.relative_to(ROOT).as_posix(),'checkpoint_sha256':hashlib.sha256((folder/'simulation/checkpoint.json').read_bytes()).hexdigest()}
    return row


def main():
    rows=[]
    baseline=ROOT/'results/baseline_20261010'
    for label,name in [('GPT-OSS','gptoss20b'),('Qwen-7B','qwen7b'),('Luna low','luna_low'),('DeepSeek','deepseek_flash'),('Sol low','sol_low'),('Mixed','mixed4')]:
        folder=baseline/name
        if (folder/'simulation/checkpoint.json').exists():rows.append(summarize(label,'2026-10-10 pressure / old world',folder))
    rows.append(summarize('Luna low','2026-10-11 no pressure / revised world',SOURCE/'runs/uniform_luna_low_no_pressure_4x50_20261011/luna_low_no_pressure'))
    campaign=SOURCE/'runs/openrouter_population_4x50_20261012'
    for label,name in [('GPT-OSS','gptoss20b_p0_s7'),('Qwen-7B','qwen7b_p0_s7'),('Ministral-8B','ministral8b_p0_s7'),('DeepSeek','deepseek_flash_p0_s7_sail'),('Mixed','mixed4_p0_s7_sail')]:
        rows.append(summarize(label,'2026-10-12 semantic modes / coarse feedback',campaign/name))
    rows.append(summarize('GPT-OSS feedback','2026-10-12 semantic modes / detailed feedback',SOURCE/'runs/openrouter_gptoss_feedback_v2_4x50_20261012/gptoss20b_feedback_v2_p0_s7'))
    rows.append(summarize('Luna neutral','2026-10-12 neutral modes / names / detailed feedback',SOURCE/'runs/native_luna_neutral_modes_4x50_20261012/luna_low_p0_s7'))
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'summary.json').write_text(json.dumps({'scope':'Completed free runs only; scripted demo and goal-directed diagnostics excluded','limitations':'Single seed. Pressure, ecology, quantities, feedback, labels, models/providers and memory repair differ across cohorts. No model-only causal or significance claims. Missing culture/organization evidence is not replaced with questionnaire ratings. Native USD is unknown.','runs':rows},ensure_ascii=False,indent=2),encoding='utf-8')
    cols=[k for k in rows[0] if k not in ['actions','accepted_actions']]
    with (OUT/'summary.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore');w.writeheader();w.writerows(rows)
    for r in rows:print(json.dumps({k:r[k] for k in ['label','version','alive','invalid_actions','settled_experiments','productive_experiments','successful_assemblies','material_trades','positive_material_transfers','works','works_at_most_8_chars']},ensure_ascii=False))
    plot(rows)


def plot(rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    recent=[r for r in rows if r['version'].startswith('2026-10-12')]
    labels=[r['label'] for r in recent];y=np.arange(len(labels))
    fig,ax=plt.subplots(figsize=(10,5.3));fig.patch.set_facecolor('white')
    ax.barh(y,[r['valid_actions'] for r in recent],color='#73b0a2',label='Accepted action')
    ax.barh(y,[r['invalid_actions'] for r in recent],left=[r['valid_actions'] for r in recent],color='#db9b82',label='Rejected action')
    for i,r in enumerate(recent):ax.text(203,i,str(r['invalid_actions'])+' rejected',va='center',fontsize=9)
    ax.set(yticks=y,yticklabels=labels,xlim=(0,245),xlabel='Action attempts (4 members x 50 rounds)')
    ax.invert_yaxis();ax.legend(loc='upper center',bbox_to_anchor=(.5,-.15),ncol=2,frameon=False);ax.spines[['top','right']].set_visible(False)
    ax.set_title('Completed runs: interface acceptance is not production success',loc='left',pad=15)
    fig.text(.02,.015,'One seed; Luna neutral also changes model, names and mode labels. Memory-format repair differed across runs.',fontsize=8,color='#647078')
    fig.tight_layout(rect=(0,.08,1,1));fig.savefig(OUT/'action_validity.png',dpi=180);fig.savefig(OUT/'action_validity.svg');plt.close(fig)
    cats=[('Gather',{'gather'}),('Liquidate',{'liquidate'}),('Experiment',{'experiment'}),('Trade / transfer',{'give_item','offer_items','accept_items','cancel_items','transfer'}),('Assembly',{'assemble_device'}),('Work / game',{'create','play','start_game','join_game','game_move','inspect_social','write_note'}),('Wait',{'wait'})]
    fig,ax=plt.subplots(figsize=(11,5.2));left=np.zeros(len(recent));palette=['#78ad8e','#d6bb74','#8ea2cf','#69a8ba','#af95c7','#dba0b3','#b7c1c4','#88939c']
    for (name,tools),color in zip(cats,palette):
        values=np.array([sum(r['actions'].get(k,0) for k in tools) for r in recent]);ax.barh(y,values,left=left,label=name,color=color);left+=values
    other=np.array([r['action_attempts'] for r in recent])-left;ax.barh(y,other,left=left,label='Other',color=palette[-1])
    ax.set(yticks=y,yticklabels=labels,xlim=(0,200),xlabel='Attempted actions, including rejected operations');ax.invert_yaxis();ax.spines[['top','right']].set_visible(False)
    ax.set_title('Behavior profiles across completed interface versions',loc='left',pad=15);ax.legend(loc='upper center',bbox_to_anchor=(.5,-.13),ncol=4,frameon=False,fontsize=9)
    fig.tight_layout(rect=(0,.10,1,1));fig.savefig(OUT/'behavior_profiles.png',dpi=180);fig.savefig(OUT/'behavior_profiles.svg');plt.close(fig)


if __name__=='__main__':main()
