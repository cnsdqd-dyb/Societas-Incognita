# 下一阶段：受限真实模型小测试

## GPT-6-Luna low 原生验收（2026-10-10）

### 同世界 GPT-6.1-Sol low 对照

`runs/sol_low_pilot_20261010/` 保持 Luna 的完整世界参数、种子 7 和冻结仿真代码不变，原生完成 4 成员 × 10 轮。4/4 存活、全部活力 5；Luna 最低活力 1。Sol 有 9 次生产尝试、2 次成功产出，Luna 为 1 次尝试、0 次成功。Sol 的 40 次动作中 1 次因材料不足被拒绝：持有 C 已衰减至不足 1，仍请求投入 C 1 装配。另一装配尝试合法但无设备产出，不能计为装配成功。两组均无物品交易和已建成设备。

可核对的知识传播事件：a0 第 8 轮在 F0/combine 用 A 2+B 1 产出 C 1，第 9 轮公开操作及结果；a3 的第 9 轮动作前可见记录包含该消息，随后在同一站点按同一配比成功产出 C。该链条是观察证据，不是通信效果的因果证明，更不能视为稳定社会组织。证据与逐轮指标位于 `reports/luna_sol_matched_20261010/`。

Sol 147 次原生请求完成，无 OpenRouter 调用，8 次经历摘要与 4 次概括完成。以原始回复离线重放 10 轮通过最终状态哈希校验，仅规范化独立压缩日志的完成顺序。以上均为单种子短程结果。

按用户要求更换模型，新建独立运行 `runs/luna_low_pilot_20261010/`，保留旧 Ministral 失败轨迹。4 成员 × 10 轮，有资源压力，世界规则与配方隐藏，通信 1,000 字符，自主提前结束；沿用基础世界与设备接口，不是所有随机组合世界的研究实验。

实际完成 10 轮、4/4 存活，40 次物理动作全部有效：观察 5、采集 26、生产实验 1、材料变现 8。143 次已验证回复包含通信 91、动作 40、经历摘要 8、一句话概括 4，12 次记忆压缩完成。仅支持短程接口和流程可用，不支持稳定组织、文化或跨种子比较结论；合法生产尝试不等于成功发现配方。

本次 OpenRouter 调用为 0；Codex 原生订阅用量另计，未估算美元价格。累计保留 159 个请求尝试，包括前期权限/结构接口失败的 16 个尝试，不能全部算作成功模型回复。首次原生动作接口拒绝 `uniqueItems`，发送结构仅移除该项，本地仍保留原约束；兼容性测试通过。完整成功回复、失败尝试、每轮检查点及汇总分别保存于 `simulation/` 和 `acceptance.json`。世界存活路径先经 Lean 检查，Python 编译和浮点执行仍按已披露的受信边界处理。

## 最新验收结果（2026-10-10）

首批真实轨迹被标记为接口验收失败，排除社会演化分析。JSON 对象模式下，动作阶段几乎只返回通信；两组各 36 次实体动作全部无效。有压力组第 9 轮全灭，后续到 50 轮为空轮；无压力组完成 9 轮，在第 10 轮记忆概括返回不完整 JSON 时停止。不能将这次死亡解读为组织崩溃，也不能将无压力存活解读为有效发展。

修复后保留结构化输出中的 action 必填结构，只投影供应商不兼容的范围/长度/数组约束；实体执行规则仍负责判断动作可用性。同时在提示末尾明确当前实体动作阶段；缺失动作对象时 API 验收立即暂停仿真，不再让协议失败持续消耗生存轮次。新功能 4 项测试通过。

两个独立接口探测返回完整动作；随后做了 4 人 × 1 轮真实验收：4 个完整动作对象中 3 次采集有效，1 次采集没有资源池的 S 材料被正常拒绝。4 人存活。有效采集实际改变库存，状态完成结算并保存。此结果仅支持接口恢复，不支持组织或文化结论。记忆压缩的长期可靠性仍须在下一次流程验证中检查。

全部原试验、诊断和单轮验收共同遵守原 0.50 美元上限，总保守记账约 0.4625 美元。没有重新启动完整 50 轮实验。失败轨迹和修复验收分别保存，不覆盖或拼接；单轮结果位于 `runs/mini_world_pilot_20261010/corrected_one_round_acceptance/acceptance.json`。

“世界编译层尚未形式化”指 Python 将世界动作、配方和结算规则转成数学计算图的过程，没有整体 Lean 正确性定理。这不意味着动作尚未实现，也不意味着必须先证明整个 Python 解释器才能测试。

## 必需检查已补齐

- 每个动作后，对照原仿真器与证书编译器的库存、能量、活性、环境变量、材料池、储备、设备权限/费用、笔记长度和待结算生产。轮末继续对照存活、整数产物及数值状态。
- 修复无附加效果材料的 `use_item` 缺少持有量检查的问题；未持有该材料不能执行有效使用动作。
- 八条 50 轮设备路径，以及六种数学模块各自的 2 个种子 × 有/无压力（24 个实例）通过逐动作差分检查；故意注入中间状态偏差会被拒绝。
- 数学证书仍由实际 Lean 核检查，不接受自称通过的报告。准入在付费调用之前完成。
- 冻结实验代码，每轮检查点与轮内日志、缓存响应、配置/代码哈希、数值环境记录和共享费用限额均保留。

## 本轮明确保留的限制

JSON 解码和 Python 世界动作编译器为受信实现，使用独立重放与差分检查验证；这不是通用的编译正确性证明。IEEE 浮点运行时也保留为受信边界，见 FLOAT_TRUST_BOUNDARY.md。整体 Python/IEEE 形式化不作为本轮小测试的阻塞条件。

证书只证明给定全知动作计划的有限时域存活，不能保证未知规则的成员能发现它。随机扰动、抢夺、防守、救援、交易托管没有纳入当前存活证书。小测试可使用已经实现的物品交易接口，但证书的全知存活计划不使用托管交易；不能把实验中任意行为解释为已获 Lean 认证。

## 启动配置

两个组，每组 4 成员 × 50 轮；同为 `mistralai/ministral-3b-2512`，隐藏世界规则、隐藏配方，材料性质按持有情况获取。仅压力条件不同；生产噪声关闭，社会/抢夺/救援扩展关闭。通信按原 1,000 字符预算，可自主提前结束，最后一次输出完整保留。无指定外部任务，无问卷调用。每组预算 0.25 美元，共享总预算 0.50 美元；4 个成员的模型调用并发执行。

这是基础世界与人工能力层的流程试验，不是全部随机组合世界的因果实验。先检查真实模型能否合法行动、探索、沟通，是否出现意外信息泄漏、费用/状态不一致，再决定后续跨机制与模型实验。结论需要更多种子和知识等量等因果对照。

配置、数学证书、冻结代码和共享账本位于 `runs/mini_world_pilot_20261010/`。启动/续跑使用 `run_small_world_pilot.py --pressure 0` 或 `--pressure 1`；旧轮次按冻结代码衔接，不切换到后续修改的实现。

## 真实接口发现及恢复

Mistral 能处理通信结构，但拒绝复合动作的严格 JSON Schema，返回 HTTP 400 / 3051（`Invalid structured output syntax`）。动作调用现通过受审计的传输适配器改用 `json_object`；模型、供应商、提示词、已收到的通信、世界状态、实体动作规则和预算不变。供应商不再对动作施加严格语法约束，因此可能产生更多语法或参数错误；这些错误按仿真器规则拒绝并记录，不能当作有效动作。

每次格式调整记录于 `transport_overrides.jsonl`，包含实际传输正文哈希与适配器源码哈希；错误细节保存于 `http_errors.jsonl`。两组均使用同一适配器。该操作性差异应在实验报告中披露，后续模型对比也须控制输出格式。恢复保留此前通信缓存和费用记录，不从头重跑。


## 2026-10-10 proportional production update

New generated worlds use compositional_v3_proportional: small normalized input ratios, scaled processing costs/effects, and fractional outputs retained in ordinary inventory. Explicit station minima remain optional. See PROPORTIONAL_PRODUCTION.md for formulas, tests and trusted boundaries. The frozen six-mechanism Sol 4-agent, 20-round run retains its original exact-input rules; its zero advanced-product result is confounded by blind recipe search and the former quantity threshold. No new paid calls were made for this update.

The updated full 20-mechanism composition has a kernel-checked four-round survival witness and a separate kernel-checked three-round active-action witness with endowed materials. These are finite-horizon checks, not discoverability or optimality guarantees. The previous 20-round large graph still encountered kernel recursion limits; short certificates do not certify that longer graph.
