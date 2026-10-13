"""Render real exported dependence graphs and a readable world overview."""
import argparse
import json
import textwrap
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import networkx as nx

FONT = Path('C:/Windows/Fonts/msyh.ttc')
if FONT.exists():
    font_manager.fontManager.addfont(str(FONT))
    plt.rcParams['font.family'] = font_manager.FontProperties(fname=str(FONT)).get_name()
plt.rcParams.update({'axes.unicode_minus':False, 'svg.fonttype':'none'})
INK='#23334a'
COLORS={'material':'#36a88b','facility':'#7197b7','context':'#9cabc0',
    'logical_rule':'#8b72d2','reaction':'#e9a548','reaction_parameter':'#d4b078',
    'state':'#4382c5','state_update':'#5e9cd2','reaction_effect':'#68a4c4',
    'pool':'#49a596','regeneration':'#70bcae','depletion':'#91aaa4','flow':'#ce7898',
    'byproduct_yield':'#d4b078','material_effect':'#68a4c4','measurement':'#8b98af','energy':'#dd9170'}


def save(fig, root, name):
    for extension in ['png','svg']:
        fig.savefig(root/(name+'.'+extension),dpi=170,facecolor='white',bbox_inches='tight',pad_inches=.2)
    plt.close(fig)


def overview(root, definition, manifest):
    fig,ax=plt.subplots(figsize=(14,8.4))
    ax.set_xlim(0,14);ax.set_ylim(0,8.4);ax.axis('off')
    ax.text(.2,8.02,'世界规律如何连接起来',fontsize=23,weight='bold',color=INK)
    ax.text(.2,7.61,definition['id']+'  ·  属性条件 → 反应 → 状态反馈',fontsize=11,color='#60718b')
    def card(x,y,w,h,title,body,color):
        ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.12,rounding_size=.14',
            facecolor=color+'18',edgecolor=color,linewidth=1.4))
        ax.text(x+.17,y+h-.36,title,fontsize=13,weight='bold',color=color)
        ax.text(x+.17,y+h-.75,body,fontsize=10.2,color=INK,va='top',linespacing=1.6)
    def arrow(a,b,color='#9baabc',curve=0):
        ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=16,color=color,
            linewidth=1.7,connectionstyle='arc3,rad='+str(curve)))
    card(.3,4.6,3.4,2.25,'可观察的物质与设备',
        '材料：光谱响应、偏转、孔隙\n设备：模式通道、校准样片\n初始线索 + 持有后的私有记录',COLORS['material'])
    card(5,4.6,3.5,2.25,'隐藏的逻辑条件',
        '材料条件 ∧ 设备条件 ∧ 状态条件\n条件内部可以包含 ∨ 与 ¬\n满足条件才进入反应结算',COLORS['logical_rule'])
    card(9.8,4.6,3.5,2.25,'实际加工与产出',
        '限制性原料决定反应量\n产率受数学状态与能量预算约束\n产物、副产物、消耗、余料返还',COLORS['reaction'])
    arrow((3.84,5.73),(4.85,5.73));arrow((8.64,5.73),(9.65,5.73))
    card(.3,1.45,3.4,2.1,'资源池与能量账本',
        '再生、耗竭、物质流动、储能\n物理变化反映到下一轮观测\n总能量变化 = 外部输入 − 耗散',COLORS['pool'])
    fields=list(definition['variables'])
    sample='、'.join(fields[:3])+('…' if len(fields)>3 else '')
    card(5,1.45,3.5,2.1,'数学状态随操作演化',
        f"本世界有 {len(fields)} 个动态变量\n"+sample+'\n加工与采集累计量进入状态方程',COLORS['state'])
    recipes=definition['recipes']
    examples=[' + '.join(r['inputs'])+' → '+r['output']+(' + '+','.join(r['byproducts']) if r.get('byproducts') else '') for r in recipes[:3]]
    card(9.8,1.45,3.5,2.1,'本世界的实际生产链',
        '\n'.join(examples),COLORS['reaction'])
    arrow((11.55,4.47),(11.55,3.7));arrow((9.64,2.5),(8.65,2.5))
    arrow((4.84,2.5),(3.85,2.5));arrow((2,3.7),(2,4.45))
    arrow((7.2,3.7),(7.2,4.45),COLORS['state'])
    ax.text(7.38,4.0,'影响下一轮条件',fontsize=9,color=COLORS['state'])
    ax.text(.3,.64,f"{manifest['equations']} 条配置表达式    /    {manifest['nodes']} 个依赖节点    /    {manifest['edges']} 条依赖边",
        fontsize=12,weight='bold',color=INK)
    ax.text(.3,.22,'依据实际世界配置生成 · 示意图压缩了结算阶段 · 依赖关系不等于已证明的因果效应',fontsize=9,color='#77869b')
    save(fig,root,'overview')


def network(root, data, manifest, definition):
    graph=nx.DiGraph()
    graph.add_nodes_from(n['id'] for n in data['nodes'])
    graph.add_edges_from((e['source'],e['target']) for e in data['edges'])
    kinds={n['id']:n['kind'] for n in data['nodes']}
    # Fixed columns keep all labels separate, including disconnected constants.
    layers={i:[] for i in range(8)}
    def layer(key):
        kind=kinds[key]
        if kind in ('material','facility'): return 0
        if kind=='context': return 4 if key.startswith('activity.') else 1
        if kind=='logical_rule': return 1
        if kind in ('reaction_parameter','byproduct_yield'): return 2
        if kind=='reaction': return 3
        if kind in ('material_effect','reaction_effect'): return 4
        if kind=='state': return 5
        if kind in ('state_update','measurement'): return 6
        return 7
    for key in graph: layers[layer(key)].append(key)
    for values in layers.values(): values.sort()
    rows=max(map(len,layers.values()))
    positions={key:(col*3,-i*1.15) for col,values in layers.items() for i,key in enumerate(values)}
    fig,ax=plt.subplots(figsize=(24,max(10,rows*.52)))
    ax.set_facecolor('white');ax.axis('off')
    nx.draw_networkx_edges(graph,positions,ax=ax,arrows=True,arrowstyle='-|>',arrowsize=7,
        width=.8,alpha=.28,edge_color='#72849d',connectionstyle='arc3,rad=.05',node_size=400)
    for n in data['nodes']:
        x,y=positions[n['id']]; color=COLORS.get(n['kind'],'#9cabc0')
        ax.add_patch(FancyBboxPatch((x-1.14,y-.38),2.28,.76,
            boxstyle='round,pad=.03,rounding_size=.08',facecolor='white',edgecolor=color,linewidth=1,zorder=3))
        label=n['label'].replace(' · material','').replace(' · state','').replace(' · pool','')
        label=label.replace('reaction.','').replace('activity.','').replace('measurement_bias.','bias.')
        label='\n'.join(textwrap.wrap(label,width=23,break_long_words=True,break_on_hyphens=False))
        ax.text(x,y,label,ha='center',va='center',fontsize=8,color=INK,zorder=4)
    headings=['物质 / 设备','属性 / 逻辑','反应参数','反应','操作累计 / 效应','世界状态','更新 / 测量','生态 / 流动']
    for col,heading in enumerate(headings):
        ax.text(col*3,1.2,heading,ha='center',fontsize=12,weight='bold',color=INK)
    ax.set_xlim(-1.5,22.5);ax.set_ylim(-rows*1.15,1.8)
    ax.set_title(definition['id']+' · 完整配置依赖网络\n'+
        f"{manifest['nodes']} nodes / {manifest['edges']} edges · 箭头表示静态依赖，反馈环跨结算阶段",
        loc='left',fontsize=18,pad=24,color=INK)
    import matplotlib.lines as lines
    legend=[('材料与资源池','#36a88b'),('逻辑条件','#8b72d2'),('反应及数量参数','#e9a548'),
            ('状态与反馈','#4382c5'),('物质流动','#ce7898'),('其它上下文','#9cabc0')]
    ax.legend(handles=[lines.Line2D([],[],marker='o',linestyle='',color=c,label=name) for name,c in legend],
        loc='lower center',bbox_to_anchor=(.5,-.045),ncol=6,frameon=False,fontsize=10)
    save(fig,root,'network')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True)
    root=Path(parser.parse_args().root)
    read=lambda name:json.loads((root/name).read_text('utf-8'))
    definition,manifest=read('definition.json'),read('manifest.json')
    overview(root,definition,manifest)
    network(root,read('network.json'),manifest,definition)
    print(str(root/'overview.png'))


if __name__=='__main__':
    main()
