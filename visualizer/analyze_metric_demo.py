"""Explicit demo-only coding adapter. Does not fill missing research-run metrics."""
import copy
import csv
import hashlib
import json
from collections import Counter
from itertools import combinations
from pathlib import Path
import build_metric_demo as demo
import core_metrics, knowledge_tracking

ROOT=demo.ROOT
FOLDER=ROOT/'results/guided_metric_demo/demo'
LABELS={'active_fraction':'群体存续','ecological_path_retention':'生态路径保有率','verified_rule_coverage':'已验证规律覆盖','knowledge_adoption_coverage':'知识采用覆盖','sustained_cooperation_fulfillment':'到期合作履约率','resource_turnover':'资源流通率','harmful_action_rate':'实际破坏发生率','damage_recovery_rate':'成熟损害恢复率','cultural_production_count':'新作品产生量','cross_member_reuse_count':'跨成员复用量','behavioral_divergence':'行为分化度','expression_divergence':'表达分化度'}

def evidence_point(value,source_ids,method,status='demo_evidence_coded',**extra):
    return {'value':value,'status':status if value is not None else 'not_applicable','source_ids':source_ids,'method':method,**extra}

def ecological_probe(cfg,snapshot):
    """Five predeclared one-action paths; NOT global ecology or a Lean certificate."""
    paths=[('gather_A',demo.action('gather',item='A',amount=1)),('gather_B',demo.action('gather',item='B',amount=1))]+[(f'recipe_r{i}',demo.experiment(i)) for i in range(3)]
    outcomes=[]
    for name,a in paths:
        s=demo.sim.Society(cfg)
        s.state['agents']=copy.deepcopy(snapshot['agents']);s.state['mini_world']=copy.deepcopy(snapshot['mini_world_physics']);s.state['round']=snapshot['round']+1
        for member in s.state['agents'].values():member.update(recent=[],inbox=[])
        # Standalone counterfactual branch excludes the original games/history.
        # Rebase accounting to this branch's actual assets; no resource is added.
        ledger=s.state['mini_world']['ledger'];ledger.update(initial=demo.mini_world.total_energy(cfg,s.state),dissipated=0,external_input=0,loss_by_cause={})
        before=demo.environments.physical_snapshot(s.state)
        result=s.act('a0',a)
        if a['tool']=='gather':produced=result['harvested'];threshold=.75
        else:
            s.settle(before);produced=sum(s.state['mini_world']['discoveries']['a0'][-1]['produced'].values());threshold=.5
        outcomes.append({'path':name,'output':produced,'threshold':threshold,'retained':produced>=threshold,'budget':'one action from snapshot by a0; no endowed resources'})
    return outcomes

def main():
    cp_path=FOLDER/'simulation/checkpoint.json';cfg_path=FOLDER/'simulation/config.json'
    cp=json.loads(cp_path.read_text('utf-8'));s=cp['state'];cfg=json.loads(cfg_path.read_text('utf-8'))
    assert cfg['experiment']['exclude_from_research'] and cp['mock']
    events=s['events'];snapshots=s['snapshots'];evidence=cp['demo_evidence'];base=core_metrics.measure(s,cfg)
    transfers=[];damages=[];claims=[];adoptions=[];obligations=[];reuses=[]
    for index,e in enumerate(events):
        a=e['decision']['action'];o=e['outcome']['action'];tool=a['tool'];t=e['round'];source=f'events:{index}'
        if tool=='give_item':q=o['amount']*(1 if o['item']=='ENERGY' else demo.mini_world.spec(cfg)['resources'][o['item']]['energy_value']);transfers.append({'round':t,'energy':q,'source':source})
        elif tool=='transfer':transfers.append({'round':t,'energy':o['transferred'],'source':source})
        elif tool=='accept_items':transfers.append({'round':t,'energy':demo.mini_world.basket_energy(cfg,o['give'])+demo.mini_world.basket_energy(cfg,o['want']),'source':source})
        elif tool=='accept_work':transfers.append({'round':t,'energy':o['work_purchased']['price'],'source':source})
        elif tool=='game_move' and o.get('settlement'):
            g=s['social_content']['games'][o['game']];paid=sum(v for k,v in g['escrow'].items() if k!=o['settlement']['winner'])
            # Engine may clear escrow at closing: use original agreed stake and participants.
            paid=g['stake']*(len(g['players'])-1)
            transfers.append({'round':t,'energy':paid,'source':source})
        elif tool=='use_function':
            kind=o['outcome']['kind']
            if kind in ('attack','device_corrosion','pool_pollution'):
                repairs={'device_corrosion':17,'pool_pollution':22,'attack':24}
                damages.append({'round':t,'deadline':t+5,'kind':kind,'target':a['target'],'source':source,'candidate_recovery_round':repairs[kind]})
    # Freeze all three production rules, equal weights. Claim checks include
    # low/high stress cases and the closed r1 gate; tests do not prove universality.
    for i,known in enumerate([3,5,7]):
        recipe=demo.mini_world.spec(cfg)['recipes'][i];prediction={recipe['output']:recipe['yield']}
        tests=[]
        for stress in [0,8,11]:
            branch=demo.sim.Society(cfg).state;branch['mini_world']['variables']['stress']=stress
            tests.append({'id':f'stress_{stress}','state':branch,'round':1,'predicted_output':{} if i==1 and stress>=10 else prediction})
        report=knowledge_tracking.verify_claim(cfg,{'type':'experiment_output','action':demo.experiment(i),'predicted_output':prediction,'source':{'demo_message_round':known,'discoverer':'a0','rule':recipe['id']}},tests)
        claims.append({'rule':recipe['id'],'known_at':known,'discoverer':'a0','verification':report,'source_message':next(j for j,m in enumerate(evidence['messages']) if m['round']==known and m['agent']=='a0')})
        if report['status']!='passed_scoped_tests':continue # Incorrect scripted guesses never become verified knowledge.
        for aid in ['a1','a2','a3']:
            matches=[d for d in s['mini_world']['discoveries'].get(aid,[]) if d['round']>known and d['facility']==recipe['facility'] and d['mode']==recipe['mode'] and d['inputs']==recipe['inputs'] and d['produced']==prediction]
            if matches:
                assert aid in evidence['messages'][claims[-1]['source_message']]['recipients']
                adoptions.append({'rule':recipe['id'],'member':aid,'round':matches[0]['round'],'receipt_round':known,'source_discovery':matches[0]})
    for accepted,dues in [(6,[8,9,10,11,12,13]),(25,[26,27,30,31])]:
        confirmations=[j for j,m in enumerate(evidence['messages']) if m['round']==accepted and m['agent'] in ('a0','a1')]
        assert len(confirmations)==2
        for deadline in dues:
            aid='a0' if deadline%2==0 else 'a1';item='A' if aid=='a0' else 'D';qty=2 if aid=='a0' else 1
            matches=[j for j,e in enumerate(events) if accepted<e['round']<=deadline and e['round']==deadline and e['agent']==aid and e['decision']['action'].get('tool')=='give_item' and e['decision']['action'].get('item')==item and e['outcome']['action']['amount']>=qty]
            obligations.append({'accepted_at':accepted,'deadline':deadline,'actor':aid,'item':item,'amount':qty,'fulfilled':bool(matches),'confirmation_messages':confirmations,'source_events':matches})
    novel=next(k for k,w in s['culture']['artifacts'].items() if w['title']=='浮岛短篇')
    sequel=next((j for j,e in enumerate(events) if e['round']==14 and e['agent']=='a3' and e['decision']['action'].get('title')=='读后续篇'),None)
    assert sequel is not None and '浮岛短篇' in events[sequel]['decision']['action']['content']
    reuses.append({'round':14,'artifact':novel,'version':1,'member':'a3','kind':'explicit_rewrite','source':f'events:{sequel}'})
    for j,e in enumerate(events):
        if e['decision']['action']['tool']=='game_move':
            game=s['social_content']['games'][e['decision']['action']['game']];author=s['culture']['artifacts'][game['artifact']]['author']
            if e['agent']!=author:reuses.append({'round':e['round'],'artifact':game['artifact'],'version':game['version'],'member':e['agent'],'kind':'game_rule_execution','source':f'events:{j}'})
    # Require actual device restoration, explicit purification, and both rescue
    # and compensation for attack damage. No credit for mere recovery promises.
    for d in damages:
        r=d['candidate_recovery_round'];snapshot=next(v for v in snapshots if v['round']==r)
        if d['kind']=='device_corrosion':ok=snapshot['mini_world_physics']['devices'][d['target']]['integrity']>=1
        elif d['kind']=='pool_pollution':ok=any(e['round']==r and e['decision']['action'].get('function')=='service_purify' for e in events)
        else:
            baseline=next(v for v in snapshots if v['round']==18)['agents']['a2'];a=snapshot['agents']['a2'];ok=a['alive'] and a['energy']>=baseline['energy'] and a['stock']>=baseline['stock'] and bool(s['rescue_events'])
        assert ok,d
        d['recovered_at']=r
    rows=[];probe_audit=[]
    for row,snapshot in zip(base['round_series'],snapshots):
        t=row['round'];first=max(1,t-4);metrics=copy.deepcopy(row['metrics']);window=[(j,e) for j,e in enumerate(events) if first<=e['round']<=t]
        probes=ecological_probe(cfg,snapshot);probe_audit.append({'round':t,'paths':probes})
        metrics['ecological_path_retention']=evidence_point(sum(p['retained'] for p in probes)/5,[f'probe:{t}'],'Five demo paths, one-action horizon, declared thresholds; engine branch witnesses; not Lean certified')
        verified=[c for c in claims if c['known_at']<=t and c['verification']['status']=='passed_scoped_tests']
        metrics['verified_rule_coverage']=evidence_point(len(verified)/3,[f'claim:{c["rule"]}' for c in verified],'Three frozen equally weighted recipe claims; passed scoped stress tests, not autonomous discovery')
        adopted=[a for a in adoptions if a['round']<=t]
        metrics['knowledge_adoption_coverage']=evidence_point(len(adopted)/(3*len(verified)) if verified else None,[f'adoption:{a["rule"]}:{a["member"]}' for a in adopted],'Actual receipt then independent successful processing; scripted, no causal inference')
        due=[o for o in obligations if first<=o['deadline']<=t]
        metrics['sustained_cooperation_fulfillment']=evidence_point(sum(o['fulfilled'] for o in due)/len(due) if due else None,[f'obligation:{o["deadline"]}' for o in due],'Two explicit confirmations; fixed deadline and matched settled material transfer')
        flow=[f for f in transfers if first<=f['round']<=t];assets=[a for a in evidence['assets'] if first<=a['round']<=t]
        metrics['resource_turnover']=evidence_point(sum(f['energy'] for f in flow)/sum(a['owned_energy_equivalent'] for a in assets),[f['source'] for f in flow],'Actual transfer energy / all-member owned asset energy; storage, devices and escrow included')
        harm=[d for d in damages if first<=d['round']<=t];mature=[d for d in damages if first<=d['deadline']<=t]
        metrics['harmful_action_rate']=evidence_point(len(harm)/len(window),[d['source'] for d in harm],'Complete scripted action catalog; actual vitality, integrity or pollution damage only')
        metrics['damage_recovery_rate']=evidence_point(sum(d['recovered_at']<=d['deadline'] for d in mature)/len(mature) if mature else None,[d['source'] for d in mature],'Five-round maturation; repair, purification, rescue and compensation checked')
        reuse={(r['artifact'],r['version'],r['member'],r['kind']):r for r in reuses if first<=r['round']<=t}
        metrics['cross_member_reuse_count']=evidence_point(len(reuse),[r['source'] for r in reuse.values()],'Non-author rewrite or actual game execution; purchases/reads alone excluded')
        msg=[(j,m) for j,m in enumerate(evidence['messages']) if first<=m['round']<=t];eligible=[aid for aid,a in snapshot['agents'].items() if a['alive'] and sum(m['agent']==aid for _,m in msg)>=3]
        values=[]
        for a,b in combinations(eligible,2):
            values.append(sum(core_metrics.jsd_counts(Counter(m[key] for _,m in msg if m['agent']==a),Counter(m[key] for _,m in msg if m['agent']==b)) for key in ['topic','purpose'])/2)
        metrics['expression_divergence']=evidence_point(sum(values)/len(values) if values else None,[f'messages:{j}' for j,m in msg if m['agent'] in eligible],'Explicit script topic/purpose coding; average two JSD values; not LLM-generated expression')
        rows.append({**row,'metrics':metrics})
    report={'demo_only':True,'exclude_from_research':True,'protocol_version':'core_metrics_v1_demo_coding','labels':LABELS,'dimensions':core_metrics.DIMENSIONS,'round_series':rows,'evidence':{'claims':claims,'adoptions':adoptions,'obligations':obligations,'transfers':transfers,'damage':damages,'reuses':reuses,'ecological_probes':probe_audit},'source_hashes':{'checkpoint':hashlib.sha256(cp_path.read_bytes()).hexdigest(),'config':hashlib.sha256(cfg_path.read_bytes()).hexdigest()},'interpretation':'Guided scripted display only. All supplemented metrics use explicit demo coding; not a general research adapter, autonomous behavior or Lean certificate.'}
    demo.write(FOLDER/'metric_demo.json',report)
    with (FOLDER/'metrics.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f);writer.writerow(['round',*LABELS]);writer.writerows([r['round'],*[r['metrics'][k]['value'] for k in LABELS]] for r in rows)
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif']=['Microsoft YaHei'];plt.rcParams['axes.unicode_minus']=False
    fig,axes=plt.subplots(4,3,figsize=(15,12));fig.set_facecolor('#f7faf5')
    for ax,(key,label) in zip(axes.flat,LABELS.items()):
        ax.plot([r['round'] for r in rows],[float('nan') if r['metrics'][key]['value'] is None else r['metrics'][key]['value'] for r in rows],color='#477d6c',linewidth=2)
        ax.set_title(label);ax.set_xlabel('轮次');ax.grid(alpha=.15)
        if 'count' not in key:ax.set_ylim(0,1.05 if key!='resource_turnover' else max(.01,max(r['metrics'][key]['value'] or 0 for r in rows)*1.2))
    fig.suptitle('示例展示 · 八个维度 / 十二条时间曲线',fontsize=16)
    fig.tight_layout(rect=(0,0,1,.96));fig.savefig(FOLDER.parent/'metric_demo.png',dpi=150);plt.close(fig)
    print(json.dumps({'series':12,'dimensions':8,'rules':len(claims),'adoptions':len(adoptions),'obligations':len(obligations),'damage_episodes':len(damages),'api_cost':0}))

if __name__=='__main__':main()
