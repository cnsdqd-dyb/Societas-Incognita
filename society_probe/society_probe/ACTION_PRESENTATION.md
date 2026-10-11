# 统一动作说明与可复现随机顺序

新生成的 mini-world 使用 `uniform_actions_v1`。每个可用实体动作和通信操作
都按同样的六个字段描述：`action`、`parameters`、`conditions`、`execution`、
`settlement`、`feedback`。参数直接取自运行时的 JSON Schema；条件与过程描述
接口事实，不比较行为价值，也不提供隐藏配方或收益系数。

实体动作使用完全相同的结算句：占用本轮一个实体动作，材料、支付和状态变化
按可见合同及执行反馈结算。通信操作同样共享一条通信结算句；通信子轮不推进
物理时间。不同动作真实的条件、影响和生效时间仍分别说明。

每次实体动作决策重新排列动作说明、`available_tools` 与 Schema 的动作分支。
每次通信决策重新排列通信说明与 Schema 的通信分支。顺序由以下上下文决定：

```text
SHA256([presentation_version, simulation_seed, round, member_id, phase, dialogue_turn])
→ independent Random instance → shuffle(sorted(unique action names))
```

因此相同请求重试或断点续跑得到同一顺序；轮次、成员或通信子轮变化时重新抽取。
随机抽样可能偶然重复，不保证每个动作在有限轮次中占据每个位置相同次数。
排列不使用世界 RNG，也不改变配方、材料噪声或动作结算顺序。

只有当时可用的动作出现在说明里。尚未发现的材料组合功能不会因此提前暴露。
游戏的 Python/XML 数据格式作为公共协议附录提供，避免丢失创建合法游戏所需
的接口信息。原来的长通信说明和文化行为价值评价不再拼接进 mini-world 动作提示。
开场也不再单独突出生产；材料之间的关系和新物质的可能性放入加工动作条目。

旧实验 `runs/**/engine_snapshot` 与已发布历史结果不修改。历史提示词仍由其
冻结引擎决定。旧数学场景保留原语义说明，仅统一随机排列 Schema 和动作清单。
本次没有启动新的真实模型实验，也不能据此断言提示词调整会增加创作。

验证：

```bash
cd society_probe/society_probe
python -m unittest discover -s tests -p test_action_presentation.py
python -m unittest discover -s tests -p test_interaction_controls.py
python -m unittest discover -s tests -p test_social_content.py
python -m unittest discover -s tests -p test_mini_world.py
```

可查看 [提示词样例](../../docs/prompt_examples/uniform_actions_v1.json)。样例只生成
初始观察、接口说明与排序记录，不调用模型。
