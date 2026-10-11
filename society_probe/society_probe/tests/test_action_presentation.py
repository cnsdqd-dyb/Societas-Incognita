import copy
import json
import random
import unittest
from pathlib import Path

import action_presentation as presentation
import interaction_controls
import schemas
import sim
import social_content
import world_rule_library


def configuration():
    base = json.loads(Path('configs/functional_services_20261010/native_base.json').read_text('utf-8'))
    candidate = world_rule_library.with_capabilities(world_rule_library.generate(2,
        [k for k, _ in world_rule_library.CANDIDATES_20]))
    cfg = social_content.configure(world_rule_library.configure(base, candidate))
    cfg['open_activities'] = {'version': 'open_activities_v1'}
    cfg['tools'] = sorted(set(cfg['tools']) | social_content.TOOLS | {'read_news', 'damage'})
    return cfg


class ActionPresentationTests(unittest.TestCase):
    def test_every_exposed_action_has_identical_fields_and_exact_parameters(self):
        cfg = configuration(); view = sim.Society(cfg).observe('a0')
        rows = presentation.entries(cfg, view)
        variants = schemas.schema('act', view, cfg)['properties']['action']['anyOf']
        self.assertEqual([row['action'] for row in rows], view['available_tools'])
        self.assertEqual(len(rows), len(set(view['available_tools'])))
        self.assertEqual(set(cfg['tools']) - set(view['available_tools']), {'use_function'})
        for row, variant in zip(rows, variants):
            self.assertEqual(tuple(row), presentation.FIELDS)
            self.assertEqual(row['parameters'], {k:v for k,v in variant['properties'].items() if k != 'tool'})
        self.assertIn('create', [r['action'] for r in rows])
        self.assertIn('experiment', [r['action'] for r in rows])

    def test_shuffle_is_reproducible_and_independent_of_input_and_world_rng(self):
        cfg=configuration(); view={'round': 4, 'self': {'id': 'a0'}}
        names=list(presentation.DESCRIPTIONS)
        before=random.getstate()
        order=presentation.ordered(names,cfg,view,'act')
        self.assertEqual(before,random.getstate())
        self.assertEqual(order,presentation.ordered(list(reversed(names)),copy.deepcopy(cfg),copy.deepcopy(view),'act'))
        for changed in ({'round':5,'self':{'id':'a0'}}, {'round':4,'self':{'id':'a1'}}):
            self.assertNotEqual(order,presentation.ordered(names,cfg,changed,'act'))
        self.assertEqual(set(order),set(names))

    def test_prompt_and_transport_schema_agree_on_communication_order(self):
        cfg=configuration(); view=sim.Society(cfg).observe('a0')
        view.update(round=3, dialogue_turn=2)
        rows=presentation.entries(cfg,view,'communicate')
        schema=schemas.schema('communicate',view,cfg)
        self.assertEqual([r['action'] for r in rows],
            [v['properties']['op']['enum'][0] for v in schema['properties']['communication']['anyOf']])
        for row in rows:self.assertEqual(tuple(row),presentation.FIELDS)
        next_view={**view,'dialogue_turn':3}
        self.assertNotEqual([r['action'] for r in rows],
            [r['action'] for r in presentation.entries(cfg,next_view,'communicate')])

    def test_hidden_prompt_retains_interfaces_without_recipes_or_value_judgments(self):
        cfg=configuration(); view=sim.Society(cfg).observe('a0')
        text=interaction_controls.actor_help(cfg,view,'FORBIDDEN_RESEARCHER_HELP')
        self.assertNotIn('FORBIDDEN_RESEARCHER_HELP',text)
        for phrase in ('no automatic resource or recognition reward','not world payoff rules',
                       'these activities cost','r0'):
            self.assertNotIn(phrase,text.lower())
        self.assertIn('Python game format:',text)
        self.assertIn('XML game format:',text)
        self.assertEqual(text.count('"action":"create"'),1)
        self.assertEqual(text.count('"action":"experiment"'),1)
        self.assertNotIn('生产可能',cfg['actor_system'])
        self.assertEqual(json.loads(next(line for line in text.splitlines()
            if line.startswith('{') and '"action":"create"' in line))['settlement'],
            json.loads(next(line for line in text.splitlines()
            if line.startswith('{') and '"action":"experiment"' in line))['settlement'])

    def test_roundtrip_schema_accepts_same_legal_actions_for_every_order(self):
        import jsonschema
        cfg=configuration(); view=sim.Society(cfg).observe('a0')
        response={'action':{'tool':'wait'},'communication':{'op':'silent'}}
        for t in (1,2,50):
            view['round']=t
            jsonschema.validate(response,schemas.schema('act',view,cfg))


if __name__ == '__main__':
    unittest.main()
