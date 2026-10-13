# 快速上手

需要 Python 3.10 或更新版本。在仓库根目录运行：

```bash
git clone https://github.com/cnsdqd-dyb/Societas-Incognita.git
cd Societas-Incognita
python -m pip install -r requirements.txt
python quickstart.py
```

默认运行 **4 个成员 × 8 轮的脚本演示**，使用更新后的 20 机制组合世界。无需 API 密钥或 Lean，不调用模型。演示中的生存行为由脚本指定，不能当作大模型发现规律或社会涌现的结果。

输出位于 `output/quickstart/`：配置在 `config.json`，状态、调用记录和结果在 `simulation/`。每个完成的轮次都保存检查点，当前未完成轮次另存 `in_progress.json`。中断后续跑：

```bash
python quickstart.py --resume
```

查看本地演示：

```bash
python visualizer/server.py --runs-root output
```

浏览器打开 **http://127.0.0.1:8776/**。查看已公开的六组旧环境实验：

```bash
python visualizer/server.py --runs-root results/baseline_20261010
```

查看器只读，不调用模型。原始配置、统计表、曲线、轨迹和冻结引擎见 [实验结果](results/baseline_20261010/README.zh-CN.md)。

## 小规模真实模型调用

先在当前 shell 的环境变量中设置 `OPENROUTER_API_KEY`，密钥不要提交 Git。指定你的账户可用的真实模型 ID：

```bash
python quickstart.py --mode openrouter --model YOUR_MODEL_ID --rounds 8 --api-cap 0.25 --output output/my_model
```

`--api-cap` 设置每组的保守美元费用上限，包含待完成请求的预留费用；平台返回的实际费用可能不同。遇到预算或传输异常会停止。续跑原配置：

```bash
python quickstart.py --mode openrouter --output output/my_model --resume
```

如果已经安装、登录 Codex CLI，且账户支持相应模型，可用原生 low 推理：

```bash
python quickstart.py --mode native --model gpt-6.1-sol --rounds 8 --output output/sol
python quickstart.py --mode native --output output/sol --resume
```

原生调用使用你的 Codex 额度，记录的外部 `cost_usd=0` 不表示原生推理免费。调用器要求模型仅处理仿真请求，不操作仓库。真实试验启动前会用冻结配置检查一条全员存活的脚本路径；这是**运行时检查，不是 Lean 证书，也不保证智能体能存活或发现规律**。脚本规划失败也不等于世界无解。

新生成世界支持正的小数材料量和能量量；批次数、攻击力度保留整数。生态变化放慢，关键原料补充由有限世界能量储备支付。已公开的历史实验保持旧整数接口与旧世界规则。种子可复现世界定义，浮点与设备差异属于受信边界；模型轨迹仍须靠保存的回复回放，不能只靠种子重现。

更多参数：`python quickstart.py --help`。只生成配置、不运行：`python society_probe/society_probe/prepare_functional_world.py --output output/world_config.json`。

## 属性规则与数学模型导出

启用新版规则层，运行不调用模型的脚本演示：

```bash
python quickstart.py --property-rules --output output/property_demo
python society_probe/society_probe/world_math_export.py --config output/property_demo/config.json --output output/property_math
```

该选项提供由真实属性生成的描述，并启用限制性原料结算。脚本演示仍使用生存策略，不代表智能体自主发现规律。导出目录包含 `model.md`、`equations.tex`、`network.mmd`、表达式与依赖边JSON及完整物理定义；这些研究者文件不提供给成员。

可选的PNG/SVG渲染需要安装绘图依赖：

```bash
python -m pip install -r requirements-figures.txt
python society_probe/society_probe/render_world_math.py --root output/property_math
```

有限一致性检查和当前Lean边界见[属性规则说明](society_probe/society_probe/PROPERTY_RULES.md)。该选项仅在创建新世界时生效，续跑使用冻结配置。
