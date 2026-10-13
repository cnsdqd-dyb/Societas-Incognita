# Quick start

Python 3.10 or newer. Run commands from the repository root.

```bash
git clone https://github.com/cnsdqd-dyb/Societas-Incognita.git
cd Societas-Incognita
python -m pip install -r requirements.txt
python quickstart.py
```

The default is an **8-round, four-member scripted demo** of the revised 20-mechanism world. It makes no model calls and needs no API key or Lean installation. Scripted survival choices demonstrate the engine; they are not evidence of LLM discovery or social emergence.

Inspect `output/quickstart/config.json`, `simulation/checkpoint.json`, `simulation/calls.jsonl`, and `simulation/result.json`. Each completed round is saved; an interrupted round has an `in_progress.json` journal. Resume with:

```bash
python quickstart.py --resume
```

View your demo:

```bash
python visualizer/server.py --runs-root output
```

Open **http://127.0.0.1:8776/**. To view the six published pre-adjustment model trials instead:

```bash
python visualizer/server.py --runs-root results/baseline_20261010
```

The viewer is read-only and does not call a model. See [results](results/baseline_20261010/README.md) for the original world, measurements, limitations and the frozen engine.

## Opt in to a small real-model trial

For OpenRouter, set `OPENROUTER_API_KEY` in your environment using your shell's environment-variable support. Keep credentials outside Git. Then specify an actual model identifier available to your account:

```bash
python quickstart.py --mode openrouter --model YOUR_MODEL_ID --rounds 8 --api-cap 0.25 --output output/my_model
```

`--api-cap` is a conservative per-run USD ceiling, including pending reservations; a provider response may report a different actual cost. The runner stops on budget or transport failures. This command uses your account and may incur charges. Resume the same saved configuration with:

```bash
python quickstart.py --mode openrouter --output output/my_model --resume
```

For an authenticated local Codex CLI supporting this model, use native low effort:

```bash
python quickstart.py --mode native --model gpt-6.1-sol --rounds 8 --output output/sol
python quickstart.py --mode native --output output/sol --resume
```

Native usage is charged or quota-counted by your Codex plan; `cost_usd=0` is **not** a claim that native inference is free. The native adapter isolates requests from repository actions. Real pilots are admitted only after checking a deterministic scripted survival path against their frozen configuration. This is a **runtime check, not a Lean certificate, a guarantee of actor survival, or proof of discoverability**. A planner failure does not prove the world infeasible.

The default revised generator permits positive decimal material/energy amounts, keeps batches and attack effort integral, slows ecological turnover, and funds precursor reseeding from the finite reserve. Historical results keep their original integer interface and original world rules. Seeds reproduce the mathematical definition; floating runtime/device differences remain a trusted boundary, and model responses require recorded replay rather than just reseeding.

Further options: `python quickstart.py --help`. Prepare a config without running anything with `python society_probe/society_probe/prepare_functional_world.py --output output/world_config.json`.

## Property rules and mathematical exports

Opt into the new rule layer without making model calls:

```bash
python quickstart.py --property-rules --output output/property_demo
python society_probe/society_probe/world_math_export.py --config output/property_demo/config.json --output output/property_math
```

The flag enables grounded descriptive observations and limiting-reagent processing. The scripted demo still uses a survival policy; it does not demonstrate autonomous scientific discovery. The exporter writes `model.md`, `equations.tex`, `network.mmd`, JSON equations/edges, and a complete physical definition. These are researcher artifacts and are not supplied to actors.

Optional PNG/SVG rendering requires the figure dependencies:

```bash
python -m pip install -r requirements-figures.txt
python society_probe/society_probe/render_world_math.py --root output/property_math
```

See [property rules](society_probe/society_probe/PROPERTY_RULES.en.md) for finite consistency checks and the current Lean boundary. The flag applies when creating a world; resume uses the frozen configuration.
