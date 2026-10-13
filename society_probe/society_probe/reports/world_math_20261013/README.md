# 世界数学模型与依赖网络

由实际配置自动导出；仅做离线表达与验证，没有调用模型。

| 世界 | 机制数 | 配置表达式 | 网络节点 | 网络边 |
|---|---:|---:|---:|---:|
| [alternative_seed19](alternative_seed19/model.md) | 8 | 44 | 89 | 117 |
| [ecology_interdependence_seed31](ecology_interdependence_seed31/model.md) | 4 | 26 | 61 | 83 |
| [catalysis_repair_seed47](catalysis_repair_seed47/model.md) | 5 | 29 | 61 | 104 |
| [full20_seed23](full20_seed23/model.md) | 20 | 93 | 167 | 327 |

每个目录提供模型说明与总方程、逐项展开的LaTeX、Mermaid依赖网络、机器可读节点/边与表达式、完整物理定义及哈希。总算子涵盖完整状态，社会工具分支仍采用代码定义；展开网络是配置依赖图，不是已验证的因果图、最优解或Lean证明图。

导出任意已验证配置：

```powershell
python world_math_export.py --config <config.json> --output <output_directory>
```
