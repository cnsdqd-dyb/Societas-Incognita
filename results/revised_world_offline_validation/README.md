# Revised world: offline checks only

No LLM trials were run on this revision. Seed 2, all 20 mechanisms, 50 rounds.

The generator now multiplies A/B ecological regeneration, depletion and source flows by **0.1**, converts their inventory/pool decay to the same slower time scale, and adds an A reseeding demand of `0.25 × max(0, 1 − A/capacity)` per round. Ordinary reserve-limited replenishment pays for it, with no free energy. Overharvesting and shortage remain possible. Fresh certificates/screening are required; old results and old certificates do not certify this revision.

| Scenario | Old A at round 25 | Revised A at round 25 | Old A at round 50 | Revised A at round 50 |
|---|---:|---:|---:|---:|
| No extraction | 53.34 | 46.41 | 54.18 | 51.87 |
| Three members each extract 8 A at round 2 | 0.00 | 9.18 | 0.038 | 12.34 |

The revised early-extraction trace stays above 6.69 A; maximum absolute conservation residual is below `3e-13`. These are two deterministic checks, not guarantees over arbitrary extraction, noise, seeds or actor policies. Old A is near zero rather than necessarily irreversibly extinct because storage discharge can return material.

`revised_config.json`, `validation.json` and `ecology_trajectories.csv` preserve the tested setup and numbers. Reproduce from the repository root:

```bash
cd society_probe/society_probe
python validate_exploration_window.py --baseline ../../results/baseline_20261010/luna_low/config.json
```

Continuous worlds additionally accept positive finite decimal quantities for material processing, collection, liquidation, transfer, trading and storage. Batches and attack effort remain integers. Recipes still require the specified ratios; only relative roundoff at `1e-12` is tolerated, with output funded by the limiting input. An empty wallet cannot spend a tiny quantity through a payment epsilon. Device assembly remains an explicit fixed material requirement; a smaller basket does not make a fractional device. Station minima still apply when explicitly modeled.

Validation: 7 new continuous-quantity tests, 6 proportional-production tests, 24 mini-world tests, 9 mechanism tests, and 16 material-function tests passed (62 total), including existing Lean checks and checkpoint/resume checks. The default eight-round scripted quick start and its completed-run resume also passed; this is engine validation rather than model behavior.
