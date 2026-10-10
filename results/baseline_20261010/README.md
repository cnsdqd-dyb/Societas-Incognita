# Six pre-adjustment material-world trials

[中文](README.zh-CN.md) · [Quick start](../../QUICKSTART.md)

All six trials completed **4 agents × 50 rounds**. They share the original seed-2, 20-mechanism world, simulation seed 7, hidden rules/recipes, survival pressure, and 1,000-character pre-action communication allowance per member per round. The last output may cross the allowance intact; members may stop earlier. No questionnaire calls were made. Model identities were hidden from actors.

**These data precede the decimal-input and ecological-window changes.** Their frozen configuration and physics are preserved here; do not analyze them as runs of the revised generator.

| Population | Final alive | Alive member-rounds / 200 | Productive experiments / completed | Built devices / attempts | Rejected actions | External API USD |
|---|---:|---:|---:|---:|---:|---:|
| GPT-OSS-20B | 0/4 | 32 / 200 | 0 / 0 | 0 / 2 | 6 | 0.080223 |
| Qwen2.5-7B | 0/4 | 32 / 200 | 0 / 0 | 0 / 0 | 0 | 0.052343 |
| GPT Luna low | 2/4 | 159 / 200 | 0 / 0 | 0 / 0 | 13 | 0; native unpriced |
| DeepSeek V4.1 Flash, reasoning disabled | 0/4 | 79 / 200 | 0 / 0 | 0 / 0 | 35 | 0.105035 |
| GPT-6.1-sol low | 4/4 | 200 / 200 | 0 / 16 | 0 / 18 | 3 | 0; native unpriced |
| Mixed: one of OSS, Qwen, DeepSeek, Sol | 2/4 | 116 / 200 | 0 / 1 | 0 / 1 | 15 | 0.111737 |

External API figures describe the successful trajectories, including their request accounting; failed startup/diagnostic costs are separately retained in `comparison_analysis.json`. Native monetary usage is unknown, not free. Native token totals include host context and cannot be treated as only the simulator-visible observation length.

![Alive members, liquid energy, and function discoveries](comparison_curves.png)

## What the data show

1. **Survival and rule discovery separate.** Sol kept all four alive and accumulated 304.6 liquid energy, but all 16 completed production trials returned no product, and all 18 assemblies failed. Legal execution or a queued experiment is not a successful discovery.
2. **Communication does not ensure exploration coverage.** OSS proposed A+B and attempted it, but its five A+B actions were rejected and used `combine`, whereas the entry production mode was `compress`. Sol completed experiments with B+Q, B+BAT, and the two P variants; it did not submit A+B. The same frozen world's entry recipe produced C and W in an isolated, adequately funded positive control.
3. **The environment has an exploration bottleneck.** Early A extraction can push it below its ecological recovery threshold; its small fractional holdings cannot be submitted through the original integer interface. A is not necessarily permanently extinct: storage discharge can return tiny amounts. Existing data do not separate actor limitations from this bottleneck.
4. **Mixed survival is descriptive.** DeepSeek and Sol survived in the mixed population. Final survival was 50%, versus 25% averaged over these four corresponding homogeneous populations, a +25 percentage-point difference. One seed, one actor per model, different transport contexts, and no causal intervention cannot establish a diversity benefit or cooperation mechanism.
5. **Creative activity is limited.** There were no `play` or game actions in these six trials. The mixed Sol member created one **knowledge work** at round 48; this is not evidence of recreational art. Notes and news reads are reported separately in `actions.csv`. No material-combination functions were used. Stable organization and institutional acceptance have not been established.

## Files and interpretation

- `summary.csv` / `summary.json`: final statistics, including population-time survival attainment.
- `actions.csv`: attempted, legally executed, and rejected action counts. “Legally executed” does **not** mean useful output.
- `agents.csv` / `agent_trajectories.csv`: per-member outcomes and roundwise vitality/stock.
- `trajectories.csv` / `comparison_analysis.json`: group curves and extended descriptive metrics.
- Each model folder: original world/configuration, final `simulation/checkpoint.json`, result, production records, and runtime survival witness. Checkpoints include simulator-visible decisions, dialogue, memories, inventories and snapshots; external host prompts, authentication files and private budget databases are excluded.
- `engine_snapshot/` and its SHA-256 index: original engine, distinct from current source. Use it for original-world physical replay. This archive does not by itself establish that all full model-response replays have passed: only Qwen's complete recorded-response replay was previously verified.
- `recipe_diagnosis.json`: read-only audit and isolated diagnostic traces; not actor outcomes.
- [Revised-world offline validation](../revised_world_offline_validation/README.md): separate new-parameter tests, no new model calls.

The legal runtime survival witness attains 200 member-rounds, the trivial population-time upper bound for 4×50, **only for survival**. It is not a Lean certificate, wealth optimum, fairness optimum, or discoverability proof. Runs continue to round 50 after all actors die; those remaining rounds contain environmental evolution rather than actor decisions. Tool-choice entropy is behavioral and is not physical thermodynamic entropy. No statistical significance or cross-world/model-size causation is claimed.

View locally: `python visualizer/server.py --runs-root results/baseline_20261010`. Re-exporting from private original logs requires those logs and optional plotting dependencies (`requirements-visual.txt`). Published paths replace local workspace references and omit the private shared budget location; provenance retains hashes of both original and public configurations.
