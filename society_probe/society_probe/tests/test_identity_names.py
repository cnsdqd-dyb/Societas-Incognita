import copy
import json
import unittest
from identity_names import registry, name_map, display_name


class IdentityNameTests(unittest.TestCase):
    def test_stable_unique_and_order_independent(self):
        a=registry(7,['A','B','C'],['a0','a1','a2','a3'])
        self.assertEqual(a,registry(7,['C','A','B'],['a3','a0','a2','a1']))
        self.assertEqual(len(set(a['members'].values())),4)
        self.assertEqual(len(set(a['materials'].values())),3)
        self.assertNotEqual(a,registry(8,['A','B','C'],['a0','a1','a2','a3']))

    def test_large_catalog_and_replay_roundtrip(self):
        r=registry(42,[str(i) for i in range(100)],['a'+str(i) for i in range(64)])
        self.assertEqual(len(set(r['materials'].values())),100)
        self.assertEqual(len(set(r['members'].values())),64)
        self.assertEqual(json.loads(json.dumps(r)),r)

    def test_old_configs_keep_old_names(self):
        self.assertEqual(display_name({},'members','a0'),'a0')
        self.assertEqual(display_name({},'materials','A','material A'),'material A')

    def test_observation_names_dont_change_materials_or_private_discovery(self):
        import sim
        from test_mini_world import config
        c=config(pressure=False);old=copy.deepcopy(c);old.pop('identity_names')
        named,unnamed=sim.Society(c),sim.Society(old)
        before=named.observe('a0');other=unnamed.observe('a0')
        self.assertEqual(before['environment']['your_inventory'],other['environment']['your_inventory'])
        self.assertEqual(before['environment']['your_material_knowledge'],{})
        self.assertEqual(before['environment']['material_pools'],other['environment']['material_pools'])
        self.assertEqual(before['self']['id'],'a0')
        self.assertEqual(before['self']['name'],c['identity_names']['members']['a0'])
        self.assertTrue(all('properties' not in v for v in before['environment']['material_catalog']))
        named.state['round']=9
        self.assertEqual(named.observe('a0')['self']['name'],before['self']['name'])


if __name__=='__main__':unittest.main()
