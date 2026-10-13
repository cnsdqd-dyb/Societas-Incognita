# candidate_31：世界模型与依赖网络

本文件由实际配置生成。目标是表达同一个完整世界状态的转移与守恒关系，并展开配置中的逻辑条件、反应和动力学方程；不是闭式解或新的证明。

世界定义 SHA256：`a4269d0e3006b41311cc65eb5c3f87f1cc171e0e59fbcd398b29948cf0c9f109`。

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

### regeneration.A

$$\mathrm{regeneration.A}=\left(\left(0.1 \cdot \frac{\left(\left(0.25 \cdot \mathrm{pool.A} \cdot \operatorname{max}\left(0,\left(1 - \frac{\mathrm{pool.A}}{80}\right)\right)\right) \cdot \left(\frac{\mathrm{pool.B}}{\left(\mathrm{pool.B} + 10\right)} \cdot 4 \cdot \frac{\mathrm{pool.A}}{80} \cdot \operatorname{max}\left(0,\left(1 - \frac{\mathrm{pool.A}}{80}\right)\right)\right)\right)}{\left(1 + \left(0.1 \cdot \mathrm{state.delay\_2}\right)\right)}\right) + \left(0.25 \cdot \operatorname{max}\left(0,\left(1 - \frac{\mathrm{pool.A}}{80}\right)\right)\right)\right)$$

### depletion.A

$$\mathrm{depletion.A}=\left(0.1 \cdot \left(0.05 \cdot \mathrm{pool.A} \cdot \frac{10}{\left(\mathrm{pool.B} + 10\right)}\right)\right)$$

### regeneration.B

$$\mathrm{regeneration.B}=\left(0.1 \cdot \left(0.25 \cdot \mathrm{pool.B} \cdot \operatorname{max}\left(0,\left(1 - \frac{\mathrm{pool.B}}{80}\right)\right)\right)\right)$$

### depletion.B

$$\mathrm{depletion.B}=\left(0.1 \cdot \left(0.1 \cdot \mathrm{pool.A} \cdot \frac{\mathrm{pool.B}}{\left(\mathrm{pool.B} + 10\right)}\right)\right)$$

### regeneration.W

$$\mathrm{regeneration.W}=0$$

### depletion.W

$$\mathrm{depletion.W}=0$$

### reaction.pr0.condition

$$\mathrm{reaction.pr0.condition}=1$$

### reaction.pr0.yield

$$\mathrm{reaction.pr0.yield}=2$$

### reaction.pr0.operating_cost

$$\mathrm{reaction.pr0.operating\_cost}=2$$

### reaction.pr0.byproduct.W

$$\mathrm{reaction.pr0.byproduct.W}=2$$

### reaction.pr1.condition

$$\mathrm{reaction.pr1.condition}=\left(\mathrm{state.stress} < 10\right)$$

### reaction.pr1.yield

$$\mathrm{reaction.pr1.yield}=\frac{2}{4}$$

### reaction.pr1.operating_cost

$$\mathrm{reaction.pr1.operating\_cost}=1.0$$

### reaction.pr1.effect.stress

$$\mathrm{reaction.pr1.effect.stress}=\frac{1}{4}$$

### reaction.pr2.condition

$$\mathrm{reaction.pr2.condition}=1$$

### reaction.pr2.yield

$$\mathrm{reaction.pr2.yield}=0.875$$

### reaction.pr2.operating_cost

$$\mathrm{reaction.pr2.operating\_cost}=2$$

### logical.r0

$$\mathrm{logical.r0}=\left(\left(\mathrm{device.channel} = 982\right) \land \left(\left(\mathrm{slot0.band} = 19\right) \land \left(\left(\mathrm{slot0.direction} = 1\right) \lor \left(\left(\mathrm{slot0.direction} = 0\right) \land \left(\mathrm{slot0.porous} = \top\right)\right)\right)\right) \land \left(\left(\mathrm{slot1.band} = 19\right) \land \left(\left(\mathrm{slot1.direction} = -1\right) \lor \left(\left(\mathrm{slot1.direction} = 0\right) \land \left(\mathrm{slot1.porous} = \top\right)\right)\right)\right)\right)$$

### logical.r1

$$\mathrm{logical.r1}=\left(\left(\mathrm{device.channel} = 982\right) \land \left(\left(\mathrm{slot0.band} = 20\right) \land \left(\left(\mathrm{slot0.direction} = 1\right) \lor \left(\left(\mathrm{slot0.direction} = 0\right) \land \left(\mathrm{slot0.porous} = \top\right)\right)\right)\right) \land \left(\left(\mathrm{slot1.band} = 20\right) \land \left(\left(\mathrm{slot1.direction} = -1\right) \lor \left(\left(\mathrm{slot1.direction} = 0\right) \land \left(\mathrm{slot1.porous} = \top\right)\right)\right)\right)\right)$$

### logical.r2

$$\mathrm{logical.r2}=\left(\left(\mathrm{device.channel} = 5077\right) \land \left(\left(\mathrm{slot0.band} = 23\right) \land \left(\left(\mathrm{slot0.direction} = 1\right) \lor \left(\left(\mathrm{slot0.direction} = 0\right) \land \left(\mathrm{slot0.porous} = \top\right)\right)\right)\right) \land \left(\left(\mathrm{slot1.band} = 19\right) \land \left(\left(\mathrm{slot1.direction} = -1\right) \lor \left(\left(\mathrm{slot1.direction} = 0\right) \land \left(\mathrm{slot1.porous} = \top\right)\right)\right)\right)\right)$$

### external_inflow

$$\mathrm{external\_inflow}=32$$

### use.C.stress

$$\mathrm{use.C.stress}=-1$$

## 反应投料及边界

| 反应 | 设备 / 模式 | 投料系数 | 主产物 |
|---|---|---|---|
| pr0 | F0 / combine | {"A": 3, "B": 1} | C |
| pr1 | F0 / combine | {"C": 1, "W": 1} | D |
| pr2 | F1 / combine | {"D": 1, "B": 2} | S |

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
  n6["next.stress"]
  n7["stress · state"]
  n8["next.delay_0"]
  n9["activity.harvested.A"]
  n10["delay_0 · state"]
  n11["next.delay_1"]
  n12["delay_1 · state"]
  n13["next.delay_2"]
  n14["delay_2 · state"]
  n15["A · pool"]
  n16["regeneration.A"]
  n17["B · pool"]
  n18["depletion.A"]
  n19["regeneration.B"]
  n20["depletion.B"]
  n21["W · pool"]
  n22["regeneration.W"]
  n23["depletion.W"]
  n24["pr0 @ F0/combine"]
  n25["F0"]
  n26["activity.consumed.A"]
  n27["activity.consumed.B"]
  n28["activity.produced.C"]
  n29["activity.produced.W"]
  n30["reaction.pr0.condition"]
  n31["reaction.pr0.yield"]
  n32["reaction.pr0.operating_cost"]
  n33["reaction.pr0.byproduct.W"]
  n34["pr1 @ F0/combine"]
  n35["activity.consumed.C"]
  n36["activity.consumed.W"]
  n37["activity.produced.D"]
  n38["reaction.pr1.condition"]
  n39["reaction.pr1.yield"]
  n40["reaction.pr1.operating_cost"]
  n41["reaction.pr1.effect.stress"]
  n42["pr2 @ F1/combine"]
  n43["F1"]
  n44["activity.consumed.D"]
  n45["activity.produced.S"]
  n46["reaction.pr2.condition"]
  n47["reaction.pr2.yield"]
  n48["reaction.pr2.operating_cost"]
  n49["logical.r0"]
  n50["device.channel"]
  n51["slot0.band"]
  n52["slot0.direction"]
  n53["slot0.porous"]
  n54["slot1.band"]
  n55["slot1.direction"]
  n56["slot1.porous"]
  n57["logical.r1"]
  n58["logical.r2"]
  n59["external_inflow"]
  n60["use.C.stress"]
  n9 -->|dependency| n8
  n18 -->|settlement| n15
  n20 -->|settlement| n17
  n23 -->|settlement| n21
  n50 -->|dependency| n49
  n50 -->|dependency| n57
  n50 -->|dependency| n58
  n25 -->|equipment| n24
  n25 -->|equipment| n34
  n43 -->|equipment| n42
  n49 -->|structural_eligibility| n24
  n57 -->|structural_eligibility| n34
  n58 -->|structural_eligibility| n42
  n0 -->|input| n24
  n1 -->|input| n24
  n1 -->|input| n42
  n2 -->|input| n34
  n2 -->|use| n60
  n3 -->|input| n42
  n5 -->|input| n34
  n8 -->|next_round| n10
  n11 -->|next_round| n12
  n13 -->|next_round| n14
  n6 -->|next_round| n7
  n15 -->|dependency| n18
  n15 -->|dependency| n20
  n15 -->|dependency| n16
  n17 -->|dependency| n18
  n17 -->|dependency| n20
  n17 -->|dependency| n16
  n17 -->|dependency| n19
  n24 -->|activity| n26
  n24 -->|activity| n27
  n24 -->|activity| n28
  n24 -->|activity| n29
  n24 -->|output| n2
  n24 -->|output| n5
  n30 -->|condition| n24
  n32 -->|operating_cost| n24
  n31 -->|yield| n24
  n34 -->|activity| n35
  n34 -->|activity| n36
  n34 -->|activity| n37
  n34 -->|output| n3
  n34 -->|extent_scaled_effect| n41
  n38 -->|condition| n34
  n41 -->|pre_update_effect| n7
  n40 -->|operating_cost| n34
  n39 -->|yield| n34
  n42 -->|activity| n27
  n42 -->|activity| n44
  n42 -->|activity| n45
  n42 -->|output| n4
  n46 -->|condition| n42
  n48 -->|operating_cost| n42
  n47 -->|yield| n42
  n16 -->|settlement| n15
  n19 -->|settlement| n17
  n22 -->|settlement| n21
  n51 -->|dependency| n49
  n51 -->|dependency| n57
  n51 -->|dependency| n58
  n52 -->|dependency| n49
  n52 -->|dependency| n57
  n52 -->|dependency| n58
  n53 -->|dependency| n49
  n53 -->|dependency| n57
  n53 -->|dependency| n58
  n54 -->|dependency| n49
  n54 -->|dependency| n57
  n54 -->|dependency| n58
  n55 -->|dependency| n49
  n55 -->|dependency| n57
  n55 -->|dependency| n58
  n56 -->|dependency| n49
  n56 -->|dependency| n57
  n56 -->|dependency| n58
  n10 -->|dependency| n11
  n12 -->|dependency| n13
  n14 -->|dependency| n16
  n7 -->|dependency| n6
  n7 -->|dependency| n38
  n60 -->|bounded_state_effect| n7
```

## 覆盖边界

已展开：全部状态更新、资源池再生/消耗、反应条件/产率/成本/副产物/状态效应、材料使用效应、测量偏差、资源流动速率与逻辑前提。噪声、储存、组合功能、设备和调度参数保留在机器可读完整定义中；社会动作与每种工具的分支转移通过实际阶段实现定义，没有逐条改写成闭式标量方程。属性逻辑图是条件网络，不是Lean证明网络。
