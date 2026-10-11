**前端可视化**

![四种浮岛星球中的 2、4、6、8 位小成员动态行走示例](docs/images/planet-populations-v5.gif)

**八个指标维度随时间的变化。**

![四成员示例中的八个维度与十二条时间曲线](docs/images/demo-metrics-v5.gif)

**文化**

<table>
<tr>
<td width="50%"><img src="docs/images/rainy-post-office-preview-v4.png" alt="排版后的邮局短篇节选"><br><a href="docs/demo-works/rainy-post-office.md">雨停之前的邮局 · 故事全文</a></td>
<td width="50%"><img src="docs/images/research-report-preview-v4.png" alt="含十三次加工记录、结果与局限的研究报告"><br><a href="docs/demo-works/research-report.md">加工复现报告 · 13 次试验、结果与待解问题</a></td>
</tr>
<tr>
<td width="50%"><img src="docs/images/moon-stones-preview-v4.gif" alt="XML 取石游戏渲染为棋盘，石子逐步取走并显示胜者"><br><a href="docs/demo-works/moon-stones.xml">月下取石 · 可执行 XML</a></td>
<td width="50%"><img src="docs/images/lighthouse-relay-preview-v4.gif" alt="Python 游戏渲染为海岸路线，棋子逐步走向灯塔终点"><br><a href="docs/demo-works/lighthouse-relay.py">灯塔接力 · 可执行 Python</a></td>
</tr>
</table>

其它作品：[日常笑话](docs/demo-works/everyday-jokes.md) · [读者续篇](docs/demo-works/post-office-sequel.md) · [傍晚随笔](docs/demo-works/evening-sounds.md)。

**发现规律时，他们说了什么？**

| 成员 / 轮次 | 记录中的发言节选 |
| --- | --- |
| a0 · R3 | “F0 combine 的 2A+1B 生成1C；轮1、2已重复，请你们独立复现。” |
| a0 · R5 | “stress<10时，F1 combine 的2A+3C生成2D，请按相同条件验证。” |
| a1 · R14 | “2D 压缩仍没有产物。我暂不接受 r2；材料数量相同不代表加工权限也相同。” |

[示例记录与指标数据](results/guided_metric_demo/README.md) · [动画参数](docs/images/planet-populations-v5.json)。运行 `python visualizer/server.py --port 8789 --runs-root results/guided_metric_demo`，然后打开 <http://127.0.0.1:8789/replay>。
