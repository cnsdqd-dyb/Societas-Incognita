# Society Probe：可控多智能体社会观察原型

## 组合世界证书与数值复现边界（2026-10-10）

当前 Lean 证书证明依赖图上的有理数学程序存活，不能称为整个 Python 仿真器的端到端证明。世界动作编译层仍须独立核对。浮点运行时作为受信边界保留，具体范围和跨设备复现限制见 [FLOAT_TRUST_BOUNDARY.md](FLOAT_TRUST_BOUNDARY.md)，数学证明范围见 [SEMANTIC_CERTIFICATE_V2.md](SEMANTIC_CERTIFICATE_V2.md)。

新证书保存 `float_replay_audit`；仿真保存 `runtime_environments.json`，并在检查点、结果记录环境版本与浮点信息。零区间越界不等于零浮点误差；不同设备或软件版本可能改变阈值附近的分支。准入仍须在实际设备重新重放及检查 Lean，非有限状态和超容差状态拒绝通过。

## 2026-10-05 补充：交叉对照与社会测量

现在支持本地密钥文件，环境变量优先；密钥不会进入配置或请求日志：

```powershell
python sim.py --config configs/real_smoke_20261005.json --api-key-file ../api_key --output runs/new_smoke
python make_matrix.py --output configs/matrix_new
python analyze_runs.py runs/new_smoke --output runs/new_smoke_analysis.json
```

`make_matrix.py` 默认生成36组配置（同质A/同质B/混合 × 有/无压力 × 基础/维修工具 × 3种子），只生成，不付费运行。主矩阵补给总量等于潜在需求，避免结构上必然灭绝；混合席位及结算顺序用配对种子控制。相同种子不等于锁定远端LLM采样。

阶段问卷新增组织存在/描述、组织认可、公平、归属、发言权、自愿继续和自报惊讶。保存 `responses` 原始回答、`effective_responses` 有效回答和 `quality_flags`；未确认存在安排时组织相关分数无效，自我同伴认可项从有效答案剔除。无效结构/范围仍停止，语义不一致保留并标记。

`result.json.metrics` 新增历史工具频率的在线惊异度（bits及相对均匀基线），以及逐回合存活、库存集中、动作集中、转移/私聊网络和边持续性。它们是描述量；行为低惊异和边持续不等于稳定组织，更不等于成员认可。组织形成须按方案审阅持续约定与履行证据。

研究方案见仓库根目录 `refine-logs/EXPERIMENT_PLAN.md`。压力变换、信息工具消融和组织轨迹自动编码尚未实现。Serper密钥未提供给agent，当前对照不含实时网络工具。

以下为原版本说明；其中“未实现惊异和网络指标”“未运行真实模型”属于此前状态，最新验证记录见 `refine-logs/VALIDATION_20261005.md`。

Python 3.11+，仅标准库，无需安装模型或 GPU。不训练模型。每次运行的模型组成、工具、压力条件固定。

## 快速启动

```bash
cd society_probe
python -m unittest discover -s tests -v
python sim.py --config configs/smoke.json --mock --output runs/offline
```

`--mock` 是确定性的工程测试：问卷分数、对话、摘要均为合成数据，不能作为研究结果。随包附有 `examples/generated_smoke`。

真实调用在本地设置密钥（不要把密钥发到聊天或写入配置文件）：

```bash
read -rsp 'OpenRouter API key: ' OPENROUTER_API_KEY
export OPENROUTER_API_KEY
python sim.py --config configs/smoke.json --output runs/real_smoke
```

默认 4 个 Ministral 3B，6 回合，0/3/6 回合独立调查。预计至少 36 次生成调用，压缩另计；美元额度是根据目录价格和返回 usage 的估计约束，不是计费系统保证。账号侧额度也应自行设置。每次请求都校验实时模型目录；未知模型或缺少 JSON 格式支持时停止。模型 IDs 可在配置 models 中逐席位更换。

本次检查目录存在：`mistralai/ministral-3b-2512`、`google/gemma-3-4b-it`、`qwen/qwen3-8b`。上线时目录、价格与供应商可能变化；运行时保留目录快照和返回模型/供应商元数据。不自动切换模型或供应商，不自动重试计费请求。小模型失败也是需要报告的工程结果，不能把无效操作直接当作真实社会行为。

## 机制先行环境生成（借鉴 VHD，非完整复现）

```bash
python generate_env.py --family supply --seed 7 --pressure off --output configs/supply_off.json
python generate_env.py --family supply --seed 7 --pressure on --output configs/supply_on.json
python generate_env.py --family shock --seed 7 --pressure on --output configs/shock_on.json
python generate_env.py --family perishable --seed 7 --pressure on --output configs/perishable_on.json
python sim.py --config configs/supply_on.json --output runs/supply_on
```

流程：采样数学参数 → 枚举求解基础稳态资源流 → 生成场景配置 → 三种参照策略回放核对 → agent 交互。参考值和 admission 结果不提供给 agent。`hidden_dynamics` 隐藏精确供给、损耗和危机参数，仍显示工具参数范围及生存规则。

三个机制族：稳定补给；指定回合公共库存减半；公共库存每回合损耗。相同 seed 的有/无压力条件使用相同补给参数。默认中性场景模板可直接使用。增加 `--llm-skin` 可通过 OpenRouter 生成名称与描述：生成模型不能写状态转移代码，也不能改变参数。语义上仍可能引入目标暗示，生成配置标记 `skin_review_required`，正式实验前应人工复核。

**范围声明**：精确参考只覆盖不含维修、损耗和冲击的基础稳态流子问题，不是整个世界的有限时域最优生存解；回放检验覆盖三种策略，不是穷尽验证。此版本是机制先行的试验框架，不能称为完整 VHD-Play 管线复现。要增加新机制，应先添加独立状态转移与参考求解器，再编写回放驱动；不能仅改场景名称就声称新环境。

## 通信与记忆规则

- 一个公共频道，支持邀请一个或多个成员到临时私聊；接受前不可发言，允许拒绝和退出；只有发起者能主动关闭。
- 每回合每人一次环境操作、一次通信操作；所有决策读取回合开始时的快照。种子决定结算顺序，避免固定身份永远先取资源；仍有有限库存下的结算顺序效应，应在多种子实验中报告。
- 新消息下一回合可见。私聊仅当前成员收到消息；加入者不会收到加入前内容。会话关闭后无历史查询接口，但已看过内容可留在私有记忆中。
- 邀请 3 回合过期、私聊 4 回合无活动关闭（配置可改，但正式条件间固定）。发起者退出或死亡会关闭会话。
- 当前观察＋私有摘要＋最近记录。超过统一**字符数**阈值触发模型自我压缩，保留最近两回合；这是简化的共同文本预算，不是精确 token 预算。超长单次工具结果、真正大规模上下文、跨模型 tokenizer 差异需后续完善。
- 摘要区分 facts/others/commitments/intentions/uncertainties，指示保留回合、说话者、私聊归属。严格结构和长度检查失败时停止，旧记忆不会被清除。
- 阶段问卷走独立调用，答案不反馈日常上下文；只向存活成员调查。报告存活率与原始成员数，避免把退出者消失误解为一致性提升。

## 条件对照

`configs/no_pressure.json` 与 `pressure.json` 比较压力；`pressure.json` 与 `pressure_repair.json` 比较维修工具；`pressure.json` 与 `mixed_models.json` 比较模型组成。均为 4 人 20 回合，每次独立初始化。修改回合数须同步调整调查点和 max_calls。先做 6 回合接口验证，再做20–50回合探索测试；不把单个随机种子的结果作为科学结论。

## 输出与恢复

- `config.json`：完整配置。
- `model_catalog.json`：实时模型元数据（真实运行）。
- `calls.jsonl`：研究者专用完整请求与响应、usage、模型、供应商、耗时；含私聊与个人记忆，应限制访问。
- `checkpoint.json`：每个完整回合后保存全部状态，包含完整行为、问卷和压缩日志。
- `result.json`：行为频率熵、存活率、调用数、成本估计、问卷；此版没有实现惊异、网络指标或有效性验证后的总社会指标。
- `failed_state.json`：异常现场，不等同于完整回合检查点。

```bash
python sim.py --config configs/smoke.json --output runs/real_smoke --resume
```

恢复从最后完整回合重跑；不保证 API 返回一致，也可能重复花费一个未完成回合的调用。失败现场中的花费累计计入预算。若 API 已计费但本地没有收到响应，无法准确核算该花费。非空输出目录默认拒绝覆盖。

## 来源与复用判断

实现为原创轻量代码，没有复制上游源码。

- GovSim（MIT）：https://github.com/giorgiopiatti/GovSim 。可借鉴固定阶段、资源结算、不同模型配置；上游 README 明确支持混合模型与 OpenRouter 后端，但默认完整安装包含较多推理依赖，原始提示含收益目标，不能直接用作无任务条件。
- AgentSociety（Apache-2.0，commercial 目录例外）：https://github.com/tsinghua-fib-lab/agentsociety 。可借鉴调查和日志；当前 v2 有 Ray 等平台组件，原型无需整套依赖。
- Concordia（Apache-2.0）：https://github.com/google-deepmind/concordia 。可复用 LLM 包装及组件设计；默认 GM 的自然语言裁决需替换为确定数学机制，才符合此实验目标。
- MemGPT：https://arxiv.org/abs/2310.08560 。借鉴容量触发、递归摘要，不引入复杂外部记忆系统。
- VHD-Play：https://arxiv.org/abs/2609.27321 。借鉴机制先行及同源验证原则，不使用任务奖励或训练流程。
- OpenRouter 官方接口：https://openrouter.ai/docs/quickstart 。JSON 协议＋本地执行校验，不依赖模型原生 function calling。真实 API 兼容性尚需用户本地密钥 smoke test。

本次验证：7 项机制与接口测试通过，生成的危机环境完成 6 回合 mock；无 OpenRouter 密钥，未运行真实模型实验。
# 2026-10-05: four-mechanism long pilot

The core implementation now includes logistic common-pool extraction, linear public goods,
costly proportional contest allocation, and load-dependent processing queues. These are
different coupled dynamics; threshold coordination, complementary bargaining production,
and endogenous network formation remain specifications.

From this directory:

```powershell
python -m unittest discover -s tests -v
python make_core_matrix.py --output configs/core_pilot_v5_20261005 --rounds 100 --agents 8
python run_campaign.py --budget-usd 10 --api-key-file ../api_key
```

The generation command refuses a nonempty directory; skip it if configurations already exist.
The campaign waits for all four real interface gates, then launches the 48-run pilot
(four mechanisms, pressure off/on, basic/information tools, three seeds, one model population).
The 10 USD allowance includes this session's earlier interface batches. No GPU training is used.

Each completed round saves `checkpoint.json`; `in_progress.json` saves received decisions
and survey progress within a round. Completed API responses are cached by request identity
and input hash. Resource settlement is deterministic and replayed from the journal if its
commit was interrupted. `engine_snapshot` pins the code used by that batch. Process locks
prevent concurrent resumes of the same run. Atomic writes flush files and tolerate brief
Windows replacement locks. Unknown transport charges consume a conservative allowance;
up to two retries apply only to transient transport failures, never malformed responses.

To continue after stopping the campaign, repeat its command. To resume an individual run,
use that batch's frozen `engine_snapshot/sim.py`, its `launch_config.json`, and the nested
`simulation` directory with `--resume`. Keep the original configuration and frozen engine.

Track `runs/core_campaign_v5_20261005/campaign_status.json` and
`runs/core_campaign_v5_20261005/long_pilot/batch_status.json`. Results live under
`long_pilot/<run_name>/simulation/result.json`, and full trajectories in the checkpoint.
The summaries are descriptive: survival, resource concentration and repeated actions do
not automatically diagnose social organization, development or legitimacy.
