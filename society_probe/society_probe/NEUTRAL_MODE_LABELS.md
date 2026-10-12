# Neutral processing-mode labels

New world configurations store a seeded `mode_labels` registry. Member-facing
modes are `M1`, `M2`, etc., rather than semantic labels such as `combine`,
`compress` and `seed`. The mapping is shuffled using an independent hash
namespace, fixed for the world, and shared across its stations. A given public
code therefore maps to the same internal mode at every station that has it.

The actor sees neutral labels in station lists, action-schema enumerations,
uniform action descriptions, its observed experiment history, and fully
disclosed mode fields when full-rule disclosure is requested. The internal
mapping itself is not included in observations. Free-form speech is preserved.

Actions submitted with neutral labels are translated before execution, including
the optional `args` wrapper. Researchers' mathematical definitions, recipes,
certificate IDs and internal physical records retain their original mode names.
No mode is renamed during a running experiment. Existing configurations without
the registry and current frozen paid runs remain unchanged.

This changes mode presentation, not reaction ratios, yields, costs, permissions
or physics. Direct programmatic execution with internal IDs remains supported for
existing planners/certificates. Model-facing schemas offer only the neutral IDs.

Validation covers observation/schema consistency, input translation, identical
physical transitions, visible settlement records, reproducibility, wrapped
arguments and full-disclosure handling (`tests/test_mode_labels.py`). A neutral
label removes one semantic cue; it does not guarantee successful exploration.
