import copy
import json
import unittest
import sim
import mini_world
import action_presentation
from mode_labels import registry, mapping, public_mode, internal_action
from test_mini_world import config,endow,settle


class ModeLabelTests(unittest.TestCase):
    def test_no_semantic_names_in_visible_modes_or_schema(self):
        c=config();s=sim.Society(c);view=s.observe('a0')
        actual={m for f in view['environment']['stations'] for m in f['modes']}
        self.assertTrue(actual and all(m.startswith('M') for m in actual))
        for tool in ['experiment','assemble_device']:
            c['tools']=sorted(set(c['tools'])|{tool})
            props=mini_world.action_properties(c,tool)
            self.assertEqual(set(props['mode']['enum']),actual)
        help_text=action_presentation.render(c,view)
        self.assertNotIn('"combine"',help_text)
        self.assertNotIn('"compress"',help_text)

    def test_same_recipe_and_physical_transition_after_translation(self):
        c=config(pressure=False);plain=copy.deepcopy(c);plain.pop('mode_labels')
        named,old=sim.Society(c),sim.Society(plain)
        for s in [named,old]:s.state['round']=1;endow(s,A=2,B=1)
        action={'tool':'experiment','facility':'F0','mode':'combine',
                'inputs':[{'item':'A','amount':2},{'item':'B','amount':1}],'batches':1}
        neutral={**action,'mode':public_mode(c,'combine')}
        self.assertEqual(internal_action(c,neutral),action)
        named.act('a0',neutral);old.act('a0',action)
        settle(named);settle(old)
        self.assertEqual(named.state,old.state)
        records=named.observe('a0')['environment']['your_experiment_records']
        self.assertEqual(records[0]['mode'],neutral['mode'])

    def test_seed_reproducibility_no_world_rewrite_and_wrapped_args(self):
        c=config();d=copy.deepcopy(c['world']['mini_world']['definition'])
        self.assertEqual(registry(7,d),registry(7,d))
        self.assertEqual(len(set(mapping(c).values())),len(mapping(c)))
        action={'tool':'experiment','args':{'mode':public_mode(c,'compress')}}
        self.assertEqual(internal_action(c,action)['args']['mode'],'compress')
        self.assertEqual(c['world']['mini_world']['definition'],d)
        self.assertEqual(internal_action({},action),action)

    def test_full_disclosure_uses_same_labels_without_leaking_map(self):
        c=config();c['world_rule_visibility']='full';c['recipe_visibility']='full'
        view=sim.Society(c).observe('a0')
        self.assertNotIn('internal_to_public',json.dumps(view))
        def modes(v):
            if isinstance(v,dict):
                for k,item in v.items():
                    if k=='mode':yield item
                    else:yield from modes(item)
            elif isinstance(v,list):
                for item in v:yield from modes(item)
        self.assertTrue(all(m.startswith('M') for m in modes(view)))


if __name__=='__main__':unittest.main()
