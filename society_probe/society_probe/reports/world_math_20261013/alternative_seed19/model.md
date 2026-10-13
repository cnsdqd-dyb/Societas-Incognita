# candidate_19：世界模型与依赖网络

本文件由实际配置生成。目标是表达同一个完整世界状态的转移与守恒关系，并展开配置中的逻辑条件、反应和动力学方程；不是闭式解或新的证明。

世界定义 SHA256：`e42dc56766ea5f1d13011046a2e86b4db51b73653b7360b0990c34ccc5a9c680`。

## 总转移算子

完整状态包含库存、液态能量、活性、资源池、设备、队列、储存、沟通与作品记录。每轮算子按实际代码顺序组合：轮次初始化、通信、物理动作、物理结算、维护、会话清理。

$$\boxed{\mathcal S_{t+1}=\mathcal C_\theta\circ\mathcal M_\theta\circ\mathcal P_\theta\circ\mathcal A_{\theta,\sigma_t}\circ\mathcal D_\theta\circ\mathcal B_\theta(\mathcal S_t;\mathbf a_t,\mathbf m_t,\boldsymbol\xi_t),\qquad o_{i,t}=\mathcal O_{\theta,i}(\mathcal S_t)}$$

这里的阶段算子是代码定义的转移，不把社会行为假装成预设优化目标。观察发生在对应决策阶段；通信过程中状态和消息也会更新。动作顺序、排队、衰变和噪声不能因写成一个大公式而省略。

## 反应与能量预算

$$\Phi_r(\mathbf p,\mathbf f)\land g_r(c_t)\land\operatorname{served}_r\land\operatorname{funded}_r\ \Longrightarrow\ \operatorname{execute}_r.$$

还需满足未在队列中损坏、设备最低加工量和能力要求。下式是成功结算分支；失败与等待分支保持代码语义。

$$\lambda_r=\min_{k\in I_r}\frac{u_{rk}}{\nu_{rk}},\quad c_{rk}=\nu_{rk}\lambda_r,\quad u^{\mathrm{return}}_{rk}=u_{rk}-c_{rk}.$$

$$K_r=\max\{0,k_r(c_t)\}\lambda_r,\quad B_r=\sum_k e_k c_{rk}+K_r,\quad Y_r=\min\left\{\max\{0,y_r(c_t)\}\lambda_r\xi_r,\frac{B_r}{e_{\mathrm{out}(r)}}\right\}.$$

主产物先结算，副产物依声明顺序使用剩余预算。旧整数语义还要向下取整；等待队列中的材料继续按原规则衰变。

$$Y_{rb}=\min\left\{\max\{0,y_{rb}(c_t)\}\lambda_r,\frac{B_r-e_{\mathrm{out}(r)}Y_r-\sum_{j\prec b}e_jY_{rj}}{e_b}\right\}.$$

副产物式中左侧对应当前副产物，求和仅取此前已结算的副产物。实际系数、条件与效应在下方逐项展开。

## 物理结算顺序

反应累计效应先裁剪到状态边界，再用同一上下文同步更新所有状态变量；随后生态消耗、回收、按声明顺序资源流动、外部补给与储备受限再生，最后衰变和报价到期返还。

$$\bar s_j=\operatorname{clip}_{[l_j,h_j]}\left(s_j+\sum_r\lambda_r\Delta_{rj}(c_t)\right),\quad s_j^+=\operatorname{clip}_{[l_j,h_j]}f_j(\bar{\mathbf s},\mathbf p,\boldsymbol\alpha_t).$$

$$d_k=\min\{p_k,\max(0,\delta_k(c^+))\},\quad \tilde p_k=p_k-d_k,\quad E^{\mathrm{recycle}}=\sum_ke_k\rho_kd_k.$$

$$q_k=e_k\min\{\max(0,g_k(c^{\mathrm{flow}})),P_k-p_k^{\mathrm{flow}}\},\quad \eta=\begin{cases}\min(1,R^{\mathrm{available}}/\sum_kq_k),&\sum_kq_k>0,\\0,&\text{otherwise},\end{cases}\quad p_k^{\mathrm{regen}}=p_k^{\mathrm{flow}}+\eta q_k/e_k.$$

容量裁剪、衰变和流动损失计入耗散；储存保护可能修改某个容器的实际衰变率。

$$\boxed{\mathcal E_{t+1}-\mathcal E_t=I_t-D_t,\quad D_t\ge0,\quad \mathcal E_t=\mathcal E_{\mathrm{liquid}}+\mathcal E_{\mathrm{materials}}+\mathcal E_{\mathrm{reserve}}+\mathcal E_{\mathrm{escrow}}+\mathcal E_{\mathrm{devices}}.}$$

总能量账本涵盖活跃与不活跃成员、储存、交易与游戏托管、等待加工材料及设备嵌入能量；活性不是物理能量。守恒残差允许浮点误差。该账本不等于社会福利或组织最优。

## 配置方程完整展开

以下引用符号取其所在结算阶段的上下文，不应把所有 state/pool 引用机械解释为同一时刻。

### next.stress

$$\mathrm{next.stress}=\operatorname{max}\left(0,\left(\mathrm{state.stress} - 0.5\right)\right)$$

### next.delay_0

$$\mathrm{next.delay\_0}=\mathrm{activity.harvested.A}$$

### next.delay_1

$$\mathrm{next.delay\_1}=\mathrm{state.delay\_0}$$

### next.delay_2

$$\mathrm{next.delay\_2}=\mathrm{state.delay\_1}$$

### next.damage

$$\mathrm{next.damage}=\operatorname{clamp}\left(\left(\mathrm{state.damage} + \left(0.1 \cdot \mathrm{activity.produced.C}\right)\right),0,2\right)$$

### next.buffer_capacity

$$\mathrm{next.buffer\_capacity}=\operatorname{max}\left(0,\left(\mathrm{state.buffer\_capacity} - \operatorname{min}\left(\mathrm{pool.P},\mathrm{state.buffer\_capacity}\right)\right)\right)$$

### next.buffer_applied

$$\mathrm{next.buffer\_applied}=\operatorname{min}\left(\mathrm{pool.P},\mathrm{state.buffer\_capacity}\right)$$

### next.storage_phase

$$\mathrm{next.storage\_phase}=\left(1 - \mathrm{state.storage\_phase}\right)$$

### next.calibration

$$\mathrm{next.calibration}=\mathrm{state.calibration}$$

### regeneration.A

$$\mathrm{regeneration.A}=\left(\left(0.1 \cdot \frac{\left(0.25 \cdot \mathrm{pool.A} \cdot \operatorname{max}\left(0,\left(1 - \frac{\mathrm{pool.A}}{60}\right)\right)\right)}{\left(1 + \left(0.1 \cdot \mathrm{state.delay\_2}\right)\right)}\right) + \left(0.25 \cdot \operatorname{max}\left(0,\left(1 - \frac{\mathrm{pool.A}}{60}\right)\right)\right)\right)$$

### depletion.A

$$\mathrm{depletion.A}=0$$

### regeneration.B

$$\mathrm{regeneration.B}=\left(0.1 \cdot \left(0.25 \cdot \mathrm{pool.B} \cdot \operatorname{max}\left(0,\left(1 - \frac{\mathrm{pool.B}}{60}\right)\right)\right)\right)$$

### depletion.B

$$\mathrm{depletion.B}=0$$

### regeneration.W

$$\mathrm{regeneration.W}=0$$

### depletion.W

$$\mathrm{depletion.W}=0$$

### regeneration.P

$$\mathrm{regeneration.P}=0$$

### depletion.P

$$\mathrm{depletion.P}=0$$

### regeneration.P_neutral

$$\mathrm{regeneration.P\_neutral}=0$$

### depletion.P_neutral

$$\mathrm{depletion.P\_neutral}=0$$

### regeneration.BAT

$$\mathrm{regeneration.BAT}=0$$

### depletion.BAT

$$\mathrm{depletion.BAT}=0$$

### reaction.pr0.condition

$$\mathrm{reaction.pr0.condition}=\left(1 \land \left(\mathrm{state.damage} < 1\right)\right)$$

### reaction.pr0.yield

$$\mathrm{reaction.pr0.yield}=\frac{\left(2 \cdot \frac{1}{\left(1 + \left(0.1 \cdot \mathrm{pool.P}\right)\right)}\right)}{2}$$

### reaction.pr0.operating_cost

$$\mathrm{reaction.pr0.operating\_cost}=1.0$$

### reaction.pr0.byproduct.W

$$\mathrm{reaction.pr0.byproduct.W}=\frac{2}{2}$$

### reaction.pr1.condition

$$\mathrm{reaction.pr1.condition}=\left(\left(\mathrm{state.stress} < 10\right) \land \left(\mathrm{state.damage} < 1\right)\right)$$

### reaction.pr1.yield

$$\mathrm{reaction.pr1.yield}=\frac{2}{4}$$

### reaction.pr1.operating_cost

$$\mathrm{reaction.pr1.operating\_cost}=1.0$$

### reaction.pr1.effect.stress

$$\mathrm{reaction.pr1.effect.stress}=\frac{1}{4}$$

### reaction.pr2.condition

$$\mathrm{reaction.pr2.condition}=\left(1 \land \left(\mathrm{state.damage} < 1\right)\right)$$

### reaction.pr2.yield

$$\mathrm{reaction.pr2.yield}=\frac{1.75}{2}$$

### reaction.pr2.operating_cost

$$\mathrm{reaction.pr2.operating\_cost}=0.0$$

### flow.neutralize

$$\mathrm{flow.neutralize}=\mathrm{state.buffer\_applied}$$

### flow.charge

$$\mathrm{flow.charge}=\left(0.1 \cdot \left(2 \cdot \mathrm{state.storage\_phase}\right)\right)$$

### flow.discharge

$$\mathrm{flow.discharge}=\left(1 - \mathrm{state.storage\_phase}\right)$$

### logical.r0

$$\mathrm{logical.r0}=\left(\left(\mathrm{device.channel} = 7939\right) \land \left(\left(\mathrm{slot0.band} = 19\right) \land \left(\left(\mathrm{slot0.direction} = -1\right) \lor \left(\left(\mathrm{slot0.direction} = 0\right) \land \left(\mathrm{slot0.porous} = \top\right)\right)\right)\right) \land \left(\left(\mathrm{slot1.band} = 19\right) \land \left(\left(\mathrm{slot1.direction} = 1\right) \lor \left(\left(\mathrm{slot1.direction} = 0\right) \land \left(\mathrm{slot1.porous} = \top\right)\right)\right)\right)\right)$$

### logical.r1

$$\mathrm{logical.r1}=\left(\left(\mathrm{device.channel} = 4674\right) \land \left(\left(\mathrm{slot0.band} = 5\right) \land \left(\left(\mathrm{slot0.direction} = -1\right) \lor \left(\left(\mathrm{slot0.direction} = 0\right) \land \left(\mathrm{slot0.porous} = \top\right)\right)\right)\right) \land \left(\left(\mathrm{slot1.band} = 5\right) \land \left(\left(\mathrm{slot1.direction} = 1\right) \lor \left(\left(\mathrm{slot1.direction} = 0\right) \land \left(\mathrm{slot1.porous} = \top\right)\right)\right)\right)\right)$$

### logical.r2

$$\mathrm{logical.r2}=\left(\left(\mathrm{device.channel} = 4674\right) \land \left(\left(\mathrm{slot0.band} = 14\right) \land \left(\left(\mathrm{slot0.direction} = -1\right) \lor \left(\left(\mathrm{slot0.direction} = 0\right) \land \left(\mathrm{slot0.porous} = \top\right)\right)\right)\right) \land \left(\left(\mathrm{slot1.band} = 19\right) \land \left(\left(\mathrm{slot1.direction} = 1\right) \lor \left(\left(\mathrm{slot1.direction} = 0\right) \land \left(\mathrm{slot1.porous} = \top\right)\right)\right)\right)\right)$$

### external_inflow

$$\mathrm{external\_inflow}=48$$

### measurement_bias.stress

$$\mathrm{measurement\_bias.stress}=\left(0.4 \cdot \left(1 - \mathrm{state.calibration}\right)\right)$$

### use.C.calibration

$$\mathrm{use.C.calibration}=1$$

### use.S.stress

$$\mathrm{use.S.stress}=-1$$

### use.S.damage

$$\mathrm{use.S.damage}=-0.5$$

### use.S.buffer_capacity

$$\mathrm{use.S.buffer\_capacity}=2$$

## 反应投料及边界

| 反应 | 设备 / 模式 | 投料系数 | 主产物 |
|---|---|---|---|
| pr0 | F1 / combine | {"A": 1, "B": 1} | C |
| pr1 | F1 / compress | {"C": 1, "W": 1} | D |
| pr2 | F1 / compress | {"D": 1, "B": 1} | S |

精确初始值、状态上下界、资源容量、衰减率、全部功能与设备配置见 [definition.json](definition.json)。

## 依赖网络

下面展示实际配置的静态依赖关系。边不代表已证明的因果效应；反馈环允许存在。

```mermaid
flowchart LR
  n0["A · material"]
  n1["B · material"]
  n2["C · material"]
  n3["D · material"]
  n4["S · material"]
  n5["W · material"]
  n6["P · material"]
  n7["P_neutral · material"]
  n8["BAT · material"]
  n9["next.stress"]
  n10["stress · state"]
  n11["next.delay_0"]
  n12["activity.harvested.A"]
  n13["delay_0 · state"]
  n14["next.delay_1"]
  n15["delay_1 · state"]
  n16["next.delay_2"]
  n17["delay_2 · state"]
  n18["next.damage"]
  n19["damage · state"]
  n20["activity.produced.C"]
  n21["next.buffer_capacity"]
  n22["buffer_capacity · state"]
  n23["P · pool"]
  n24["next.buffer_applied"]
  n25["buffer_applied · state"]
  n26["next.storage_phase"]
  n27["storage_phase · state"]
  n28["next.calibration"]
  n29["calibration · state"]
  n30["A · pool"]
  n31["regeneration.A"]
  n32["depletion.A"]
  n33["B · pool"]
  n34["regeneration.B"]
  n35["depletion.B"]
  n36["W · pool"]
  n37["regeneration.W"]
  n38["depletion.W"]
  n39["regeneration.P"]
  n40["depletion.P"]
  n41["P_neutral · pool"]
  n42["regeneration.P_neutral"]
  n43["depletion.P_neutral"]
  n44["BAT · pool"]
  n45["regeneration.BAT"]
  n46["depletion.BAT"]
  n47["pr0 @ F1/combine"]
  n48["F1"]
  n49["activity.consumed.A"]
  n50["activity.consumed.B"]
  n51["activity.produced.W"]
  n52["reaction.pr0.condition"]
  n53["reaction.pr0.yield"]
  n54["reaction.pr0.operating_cost"]
  n55["reaction.pr0.byproduct.W"]
  n56["pr1 @ F1/compress"]
  n57["activity.consumed.C"]
  n58["activity.consumed.W"]
  n59["activity.produced.D"]
  n60["reaction.pr1.condition"]
  n61["reaction.pr1.yield"]
  n62["reaction.pr1.operating_cost"]
  n63["reaction.pr1.effect.stress"]
  n64["pr2 @ F1/compress"]
  n65["activity.consumed.D"]
  n66["activity.produced.S"]
  n67["reaction.pr2.condition"]
  n68["reaction.pr2.yield"]
  n69["reaction.pr2.operating_cost"]
  n70["flow.neutralize"]
  n71["flow.charge"]
  n72["flow.discharge"]
  n73["logical.r0"]
  n74["device.channel"]
  n75["slot0.band"]
  n76["slot0.direction"]
  n77["slot0.porous"]
  n78["slot1.band"]
  n79["slot1.direction"]
  n80["slot1.porous"]
  n81["logical.r1"]
  n82["logical.r2"]
  n83["external_inflow"]
  n84["measurement_bias.stress"]
  n85["use.C.calibration"]
  n86["use.S.stress"]
  n87["use.S.damage"]
  n88["use.S.buffer_capacity"]
  n12 -->|dependency| n11
  n20 -->|dependency| n18
  n32 -->|settlement| n30
  n35 -->|settlement| n33
  n46 -->|settlement| n44
  n40 -->|settlement| n23
  n43 -->|settlement| n41
  n38 -->|settlement| n36
  n74 -->|dependency| n73
  n74 -->|dependency| n81
  n74 -->|dependency| n82
  n48 -->|equipment| n47
  n48 -->|equipment| n56
  n48 -->|equipment| n64
  n71 -->|transfer| n44
  n72 -->|transfer| n30
  n70 -->|transfer| n41
  n73 -->|structural_eligibility| n47
  n81 -->|structural_eligibility| n56
  n82 -->|structural_eligibility| n64
  n0 -->|input| n47
  n1 -->|input| n47
  n1 -->|input| n64
  n2 -->|input| n56
  n2 -->|use| n85
  n3 -->|input| n64
  n4 -->|use| n88
  n4 -->|use| n87
  n4 -->|use| n86
  n5 -->|input| n56
  n24 -->|next_round| n25
  n21 -->|next_round| n22
  n28 -->|next_round| n29
  n18 -->|next_round| n19
  n11 -->|next_round| n13
  n14 -->|next_round| n15
  n16 -->|next_round| n17
  n26 -->|next_round| n27
  n9 -->|next_round| n10
  n30 -->|source| n71
  n30 -->|dependency| n31
  n33 -->|dependency| n34
  n44 -->|source| n72
  n23 -->|source| n70
  n23 -->|dependency| n24
  n23 -->|dependency| n21
  n23 -->|dependency| n53
  n47 -->|activity| n49
  n47 -->|activity| n50
  n47 -->|activity| n20
  n47 -->|activity| n51
  n47 -->|output| n2
  n47 -->|output| n5
  n52 -->|condition| n47
  n54 -->|operating_cost| n47
  n53 -->|yield| n47
  n56 -->|activity| n57
  n56 -->|activity| n58
  n56 -->|activity| n59
  n56 -->|output| n3
  n56 -->|extent_scaled_effect| n63
  n60 -->|condition| n56
  n63 -->|pre_update_effect| n10
  n62 -->|operating_cost| n56
  n61 -->|yield| n56
  n64 -->|activity| n50
  n64 -->|activity| n65
  n64 -->|activity| n66
  n64 -->|output| n4
  n67 -->|condition| n64
  n69 -->|operating_cost| n64
  n68 -->|yield| n64
  n31 -->|settlement| n30
  n34 -->|settlement| n33
  n45 -->|settlement| n44
  n39 -->|settlement| n23
  n42 -->|settlement| n41
  n37 -->|settlement| n36
  n75 -->|dependency| n73
  n75 -->|dependency| n81
  n75 -->|dependency| n82
  n76 -->|dependency| n73
  n76 -->|dependency| n81
  n76 -->|dependency| n82
  n77 -->|dependency| n73
  n77 -->|dependency| n81
  n77 -->|dependency| n82
  n78 -->|dependency| n73
  n78 -->|dependency| n81
  n78 -->|dependency| n82
  n79 -->|dependency| n73
  n79 -->|dependency| n81
  n79 -->|dependency| n82
  n80 -->|dependency| n73
  n80 -->|dependency| n81
  n80 -->|dependency| n82
  n25 -->|dependency| n70
  n22 -->|dependency| n24
  n22 -->|dependency| n21
  n29 -->|dependency| n84
  n29 -->|dependency| n28
  n19 -->|dependency| n18
  n19 -->|dependency| n52
  n19 -->|dependency| n60
  n19 -->|dependency| n67
  n13 -->|dependency| n14
  n15 -->|dependency| n16
  n17 -->|dependency| n31
  n27 -->|dependency| n71
  n27 -->|dependency| n72
  n27 -->|dependency| n26
  n10 -->|dependency| n9
  n10 -->|dependency| n60
  n85 -->|bounded_state_effect| n29
  n88 -->|bounded_state_effect| n22
  n87 -->|bounded_state_effect| n19
  n86 -->|bounded_state_effect| n10
```

## 覆盖边界

已展开：全部状态更新、资源池再生/消耗、反应条件/产率/成本/副产物/状态效应、材料使用效应、测量偏差、资源流动速率与逻辑前提。噪声、储存、组合功能、设备和调度参数保留在机器可读完整定义中；社会动作与每种工具的分支转移通过实际阶段实现定义，没有逐条改写成闭式标量方程。属性逻辑图是条件网络，不是Lean证明网络。
