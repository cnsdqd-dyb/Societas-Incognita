"""Export configuration equations and a static dependency network, not proofs."""
import argparse
import hashlib
import json
from pathlib import Path

import world_rule_engine


def symbol(value):
    return r'\mathrm{' + str(value).replace('_', r'\_') + '}'


def latex(expr):
    if isinstance(expr, bool):
        return r'\top' if expr else r'\bot'
    if isinstance(expr, (int, float)):
        return str(expr)
    if isinstance(expr, str):
        return symbol(expr)
    if 'ref' in expr:
        return symbol(expr['ref'])
    if 'op' in expr:
        op, args = expr['op'], expr['args']
    else:
        op, args = next(iter(expr.items()))
        if op == 'not':
            args = [args]
    values = [latex(x) for x in args]
    operators = {'add': '+', 'sub': '-', 'mul': r'\cdot', 'and': r'\land',
                 'or': r'\lor', 'eq': '=', 'lt': '<', 'le': r'\le',
                 'gt': '>', 'ge': r'\ge'}
    if op in operators:
        return r'\left(' + (' '+operators[op]+' ').join(values) + r'\right)'
    if op == 'div':
        return r'\frac{' + values[0] + '}{' + values[1] + '}'
    if op == 'pow':
        return '{' + values[0] + '}^{' + values[1] + '}'
    if op == 'not':
        return r'\neg ' + values[0]
    if op == 'exp':
        return r'\exp\left(' + values[0] + r'\right)'
    if op in ('min', 'max', 'clamp'):
        return r'\operatorname{' + op + r'}\left(' + ','.join(values) + r'\right)'
    raise ValueError('Unrendered operator: ' + op)


def references(value):
    if isinstance(value, dict):
        if 'ref' in value:
            yield value['ref']
        elif 'eq' in value and isinstance(value['eq'][0], str):
            yield value['eq'][0]
        else:
            for child in value.values():
                yield from references(child)
    elif isinstance(value, list):
        for child in value:
            yield from references(child)


def export(cfg, output):
    d = cfg['world']['mini_world']['definition']
    world_rule_engine.validate(d)
    root = Path(output); root.mkdir(parents=True, exist_ok=True)
    dump = lambda name,value: (root/name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    canonical = json.dumps(d, sort_keys=True, separators=(',', ':')).encode()
    sha = hashlib.sha256(canonical).hexdigest()
    nodes, edges = {}, set()
    def node(key, label, kind):
        nodes[key] = {'id':key, 'label':label, 'kind':kind}
        return key
    def edge(source, target, relation):
        if source not in nodes:
            node(source, source, 'context')
        if target not in nodes:
            node(target, target, 'context')
        edges.add((source,target,relation))
    equations = []
    def equation(name, expr, kind):
        node(name, name, kind)
        equations.append({'target':name, 'expression':expr, 'latex':latex(expr), 'kind':kind})
        for ref in references(expr):
            edge(ref,name,'dependency')
    for key,r in d['resources'].items():
        node('material.'+key,key+' · material','material')
    for key,v in d['variables'].items():
        equation('next.'+key,v['next'],'state_update')
        node('state.'+key,key+' · state','state')
        edge('next.'+key,'state.'+key,'next_round')
    for key,p in d['pools'].items():
        node('pool.'+key,key+' · pool','pool')
        equation('regeneration.'+key,p['regeneration'],'regeneration')
        equation('depletion.'+key,p.get('depletion',0),'depletion')
        edge('regeneration.'+key,'pool.'+key,'settlement')
        edge('depletion.'+key,'pool.'+key,'settlement')
    for r in d['recipes']:
        reaction = node('reaction.'+r['id'],r['id']+' @ '+r['facility']+'/'+r['mode'],'reaction')
        node('facility.'+r['facility'],r['facility'],'facility')
        edge('facility.'+r['facility'],reaction,'equipment')
        for item in r['inputs']:
            edge('material.'+item,reaction,'input')
            edge(reaction,'activity.consumed.'+item,'activity')
        for item in [r['output'],*r.get('byproducts', {})]:
            edge(reaction,'material.'+item,'output')
            edge(reaction,'activity.produced.'+item,'activity')
        for field in ('condition','yield','operating_cost'):
            expr=r.get(field,r['energy_cost'] if field=='operating_cost' else 1)
            target='reaction.'+r['id']+'.'+field
            equation(target,expr,'reaction_parameter')
            edge(target,reaction,field)
        for field,expr in r.get('effects',{}).items():
            target='reaction.'+r['id']+'.effect.'+field
            equation(target,expr,'reaction_effect')
            edge(reaction,target,'extent_scaled_effect')
            edge(target,'state.'+field,'pre_update_effect')
        for item,expr in r.get('byproducts',{}).items():
            equation('reaction.'+r['id']+'.byproduct.'+item,expr,'byproduct_yield')
    for f in d.get('pool_flows',[]):
        equation('flow.'+f['id'],f['rate'],'flow')
        edge('pool.'+f['source'],'flow.'+f['id'],'source')
        edge('flow.'+f['id'],'pool.'+f['target'],'transfer')
    for rule in d.get('property_rules',{}).get('reactions',[]):
        equation('logical.'+rule['id'],rule['when'],'logical_rule')
        # A rule can bind more than one concrete material tuple.
        for r in d['recipes']:
            if r.get('property_rule_id') == rule['id']:
                edge('logical.'+rule['id'],'reaction.'+r['id'],'structural_eligibility')
    equation('external_inflow',d['external_inflow'],'energy')
    for field,expr in d.get('measurement_biases',{}).items():
        equation('measurement_bias.'+field,expr,'measurement')
    for item,r in d['resources'].items():
        for field,expr in r.get('use_effects',{}).items():
            target='use.'+item+'.'+field
            equation(target,expr,'material_effect')
            edge('material.'+item,target,'use')
            edge(target,'state.'+field,'bounded_state_effect')
    dump('definition.json',d)
    dump('equations.json',equations)
    graph={'nodes':list(nodes.values()),'edges':[{'source':s,'target':t,'relation':r} for s,t,r in sorted(edges)],
           'interpretation':'Static configuration dependence; cycles can represent temporal feedback, not a Lean proof DAG'}
    dump('network.json',graph)
    ids={key:'n'+str(i) for i,key in enumerate(nodes)}
    diagram=['flowchart LR']
    for key,value in nodes.items():
        label=value['label'].replace('"', "'")
        diagram.append(f'  {ids[key]}["{label}"]')
    for source,target,relation in sorted(edges):
        diagram.append(f'  {ids[source]} -->|{relation}| {ids[target]}')
    diagram='\n'.join(diagram)+'\n'
    (root/'network.mmd').write_text(diagram,encoding='utf-8')
    lines=['# '+d['id']+'：世界模型与依赖网络','',
        '本文件由实际配置生成。目标是表达同一个完整世界状态的转移与守恒关系，'+
        '并展开配置中的逻辑条件、反应和动力学方程；不是闭式解或新的证明。','',
        f'世界定义 SHA256：`{sha}`。','',
        '## 总转移算子','',
        '完整状态包含库存、液态能量、活性、资源池、设备、队列、储存、沟通与作品记录。'+
        '每轮算子按实际代码顺序组合：轮次初始化、通信、物理动作、物理结算、维护、会话清理。','',
        r'$$\boxed{\mathcal S_{t+1}=\mathcal C_\theta\circ\mathcal M_\theta\circ\mathcal P_\theta\circ\mathcal A_{\theta,\sigma_t}\circ\mathcal D_\theta\circ\mathcal B_\theta(\mathcal S_t;\mathbf a_t,\mathbf m_t,\boldsymbol\xi_t),\qquad o_{i,t}=\mathcal O_{\theta,i}(\mathcal S_t)}$$','',
        '这里的阶段算子是代码定义的转移，不把社会行为假装成预设优化目标。观察发生在对应决策阶段；'+
        '通信过程中状态和消息也会更新。动作顺序、排队、衰变和噪声不能因写成一个大公式而省略。','',
        '## 反应与能量预算','',
        r'$$\Phi_r(\mathbf p,\mathbf f)\land g_r(c_t)\land\operatorname{served}_r\land\operatorname{funded}_r\ \Longrightarrow\ \operatorname{execute}_r.$$','',
        '还需满足未在队列中损坏、设备最低加工量和能力要求。下式是成功结算分支；失败与等待分支保持代码语义。','']
    if d.get('production_semantics')=='limiting_reagent_v1':
        lines += [r'$$\lambda_r=\min_{k\in I_r}\frac{u_{rk}}{\nu_{rk}},\quad c_{rk}=\nu_{rk}\lambda_r,\quad u^{\mathrm{return}}_{rk}=u_{rk}-c_{rk}.$$','']
    else:
        lines += ['当前配置使用旧匹配语义：比例或整数投料必须先按配置匹配，不能套用限制性原料返还公式。','']
    lines += [r'$$K_r=\max\{0,k_r(c_t)\}\lambda_r,\quad B_r=\sum_k e_k c_{rk}+K_r,\quad Y_r=\min\left\{\max\{0,y_r(c_t)\}\lambda_r\xi_r,\frac{B_r}{e_{\mathrm{out}(r)}}\right\}.$$','',
        '主产物先结算，副产物依声明顺序使用剩余预算。旧整数语义还要向下取整；等待队列中的材料继续按原规则衰变。','',
        r'$$Y_{rb}=\min\left\{\max\{0,y_{rb}(c_t)\}\lambda_r,\frac{B_r-e_{\mathrm{out}(r)}Y_r-\sum_{j\prec b}e_jY_{rj}}{e_b}\right\}.$$','',
        '副产物式中左侧对应当前副产物，求和仅取此前已结算的副产物。实际系数、条件与效应在下方逐项展开。','',
        '## 物理结算顺序','',
        '反应累计效应先裁剪到状态边界，再用同一上下文同步更新所有状态变量；'+
        '随后生态消耗、回收、按声明顺序资源流动、外部补给与储备受限再生，最后衰变和报价到期返还。','',
        r'$$\bar s_j=\operatorname{clip}_{[l_j,h_j]}\left(s_j+\sum_r\lambda_r\Delta_{rj}(c_t)\right),\quad s_j^+=\operatorname{clip}_{[l_j,h_j]}f_j(\bar{\mathbf s},\mathbf p,\boldsymbol\alpha_t).$$','',
        r'$$d_k=\min\{p_k,\max(0,\delta_k(c^+))\},\quad \tilde p_k=p_k-d_k,\quad E^{\mathrm{recycle}}=\sum_ke_k\rho_kd_k.$$','',
        r'$$q_k=e_k\min\{\max(0,g_k(c^{\mathrm{flow}})),P_k-p_k^{\mathrm{flow}}\},\quad \eta=\begin{cases}\min(1,R^{\mathrm{available}}/\sum_kq_k),&\sum_kq_k>0,\\0,&\text{otherwise},\end{cases}\quad p_k^{\mathrm{regen}}=p_k^{\mathrm{flow}}+\eta q_k/e_k.$$','',
        '容量裁剪、衰变和流动损失计入耗散；储存保护可能修改某个容器的实际衰变率。','',
        r'$$\boxed{\mathcal E_{t+1}-\mathcal E_t=I_t-D_t,\quad D_t\ge0,\quad \mathcal E_t=\mathcal E_{\mathrm{liquid}}+\mathcal E_{\mathrm{materials}}+\mathcal E_{\mathrm{reserve}}+\mathcal E_{\mathrm{escrow}}+\mathcal E_{\mathrm{devices}}.}$$','',
        '总能量账本涵盖活跃与不活跃成员、储存、交易与游戏托管、等待加工材料及设备嵌入能量；活性不是物理能量。'+
        '守恒残差允许浮点误差。该账本不等于社会福利或组织最优。','',
        '## 配置方程完整展开','',
        '以下引用符号取其所在结算阶段的上下文，不应把所有 state/pool 引用机械解释为同一时刻。','']
    for eq in equations:
        lines += ['### '+eq['target'],'', '$$'+symbol(eq['target'])+'='+eq['latex']+'$$','']
    lines += ['## 反应投料及边界','', '| 反应 | 设备 / 模式 | 投料系数 | 主产物 |','|---|---|---|---|']
    for r in d['recipes']:
        lines.append(f"| {r['id']} | {r['facility']} / {r['mode']} | {json.dumps(r['inputs'],ensure_ascii=False)} | {r['output']} |")
    lines += ['', '精确初始值、状态上下界、资源容量、衰减率、全部功能与设备配置见 [definition.json](definition.json)。','',
        '## 依赖网络','', '下面展示实际配置的静态依赖关系。边不代表已证明的因果效应；反馈环允许存在。','',
        '```mermaid',diagram.rstrip(),'```','',
        '## 覆盖边界','',
        '已展开：全部状态更新、资源池再生/消耗、反应条件/产率/成本/副产物/状态效应、材料使用效应、测量偏差、资源流动速率与逻辑前提。'+
        '噪声、储存、组合功能、设备和调度参数保留在机器可读完整定义中；'+
        '社会动作与每种工具的分支转移通过实际阶段实现定义，没有逐条改写成闭式标量方程。'+
        '属性逻辑图是条件网络，不是Lean证明网络。','']
    (root/'model.md').write_text('\n'.join(lines),encoding='utf-8')
    (root/'equations.tex').write_text('\n'.join(r'\['+symbol(eq['target'])+'='+eq['latex']+r'\]' for eq in equations)+'\n',encoding='utf-8')
    sources=['mini_world.py','property_rules.py','production_semantics.py','mechanism_extensions.py',
             'sim.py','environments.py','functional_effects.py','capability_devices.py',
             'material_combinations.py','social_content.py','interaction_controls.py']
    base=Path(__file__).resolve().parent
    dump('manifest.json',{'world_sha256':sha,'equations':len(equations),'nodes':len(nodes),'edges':len(edges),
        'status':'configuration_export_not_formal_proof','semantics':d.get('production_semantics','exact_integer_v1'),
        'engine_sha256':{name:hashlib.sha256((base/name).read_bytes()).hexdigest() for name in sources}})
    return {'output':str(root),'equations':len(equations),'nodes':len(nodes),'edges':len(edges)}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    cfg=json.loads(Path(args.config).read_text('utf-8'))
    print(json.dumps(export(cfg,args.output),ensure_ascii=False))


if __name__=='__main__':
    main()
