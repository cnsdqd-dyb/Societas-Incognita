# Inferable property rules

This optional layer extends the existing world engine. Frozen runs and legacy
configurations keep their original laws.

```python
from world_rule_library import generate, with_capabilities, with_property_rules

candidate = with_property_rules(with_capabilities(generate(19, [
    'renewable_ecology', 'cross_feeding', 'explicit_delay', 'shared_queue',
    'fatigue_repair', 'finite_buffer', 'power_limited_storage',
    'calibrated_measurement',
])))
```

Apply the property layer after the physical and capability layers. It retains
the original yields, costs, state guards, feedback equations, and energy budget.
The first implementation compiles the existing production graph into shared
property predicates; it does not generate an arbitrary scientific theory.

## Observations and reactions

Materials have a spectral response band, field-deflection direction, and porous
response. Equipment modes have channel readings and calibration-sample records.
These are artificial-world properties, not claims about natural physics.
Descriptions are deterministic templates generated from the same facts used by
the reaction compiler. Environmental specimens provide initial evidence;
possession discloses private material records. Combination functions retain
their separate ownership-gated discovery rules.

Hidden predicates use `and`, `or`, `not`, and `eq`:

`material predicates AND equipment predicates AND current state guard -> reaction`.

The compiler enumerates the declared materials and equipment modes to produce
executable reactions. Materials satisfying the same predicate can substitute;
different disjunctive branches can trigger the same rule. Agents receive
observations, rather than these formulas, ratios, output identities, or the
researcher dependency network. Their statements never overwrite physical facts.

Initial probe descriptions are idealized readings without modeled acquisition
actions or costs. Existing production noise and device measurement errors keep
their original semantics. Observable dynamic fields are shown as per-round probe
descriptions; hidden fields remain hidden.

## Limiting reagents

New property worlds use `limiting_reagent_v1`. Once the material set and equipment
mode match, reaction extent is `min(input_i / stoichiometry_i)`. Excess inputs
are returned. Feedback records `consumed_inputs` and `returned_inputs`; only
consumed material and paid operating energy fund products. Queue decay, device
minimums, state guards, and manufacturing requirements still apply.

Legacy `proportional_v1` retains its exact-ratio behavior. The new semantics
require an explicit opt-in.

## Consistency and proof scope

Validation exhaustively checks the declared finite material/device domain. It
rejects unsatisfiable rules, unknown properties, overlapping reaction candidates,
and disagreements among rules, executable recipes, and equipment descriptions.
Overlap is conservatively rejected even when continuous guards might be mutually
exclusive. After researcher edits, explicitly call `property_rules.refresh(d)`
and revalidate; validation never silently repairs a world.

Finite consistency does not prove discoverability, exploration affordability,
survival, or optimality. The new limiting-reagent settlement is not covered by
the composed Lean compiler, which explicitly rejects it. Existing supported Lean
certificates remain scoped to their original semantics. Python floating-point
execution remains a trusted boundary.

See the [Chinese specification](PROPERTY_RULES.md), the [offline model examples](reports/world_math_20261013/README.en.md),
and `tests/test_property_rules.py` for executable checks.
