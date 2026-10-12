# Seeded material and member names

The built-in generator uses SHA-256 and a versioned fictional vocabulary. It
needs no model calls, network service or extra package. Material syllables and
member names do not depend on resource tiers, properties, recipes, model names,
roles or behavior. Names are unique within each namespace of a world.

```python
from identity_names import registry

names = registry(7, ['A', 'B', 'C'], ['a0', 'a1', 'a2', 'a3'])
# materials: A = 珞塔岚, B = 莫维瑟, C = 娅塔露
# members: a0 = 莱琳, a1 = 伊娜, a2 = 伊亚, a3 = 米雅
cfg['identity_names'] = names
```

New configurations made by `world_rule_library.configure` include this registry.
It is serialized into the configuration and saved with the checkpoint. Existing
configurations without the registry keep their original labels. The currently
running paid groups retain their frozen engines and names.

In actor observations, `self.name` and each visible member's `name` supplement
their IDs. `environment.material_catalog` contains each material's `item` and
`name`. The naming note explicitly says action/communication parameters still
use stable IDs such as `A` and `a0`; aliases are for dialogue and descriptions,
not replacement identifiers. Quantities stay in `your_inventory`.

Inventory, ownership, certificates, recipes and transactions continue to use
IDs. The naming registry adds no new materials or members and reveals no hidden
properties. Possession-triggered property disclosure remains unchanged. The
generator computes names over the complete world's ID set before execution;
adding members or materials requires a new configuration rather than renaming
entities during a running experiment.

Names improve reference and readability; whether they improve state-grounded
decisions is an empirical question. Do not interpret a naming change as a
solution to ignoring fractional balances or failing to learn from feedback.
