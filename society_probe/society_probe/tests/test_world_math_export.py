import json
import tempfile
import unittest
from pathlib import Path

import property_rules
import world_math_export as export
from test_mini_world import config


class MathExportTests(unittest.TestCase):
    def test_expression_preserves_boolean_and_numeric_structure(self):
        self.assertIn(r'\land', export.latex({'and':[{'eq':['x',1]},{'not':{'eq':['y',2]}}]}))
        self.assertIn(r'\frac', export.latex({'op':'div','args':[{'ref':'pool.A'},2]}))
        with self.assertRaises(ValueError):
            export.latex({'op':'mystery','args':[1]})

    def test_export_has_no_dangling_edges_and_preserves_every_state_equation(self):
        cfg=config(pressure=False)
        cfg['world']['mini_world']['definition']=property_rules.install(cfg['world']['mini_world']['definition'],19)[0]
        with tempfile.TemporaryDirectory() as temporary:
            export.export(cfg,temporary)
            root=Path(temporary)
            graph=json.loads((root/'network.json').read_text('utf-8'))
            nodes={n['id'] for n in graph['nodes']}
            self.assertTrue(all(e['source'] in nodes and e['target'] in nodes for e in graph['edges']))
            equations=json.loads((root/'equations.json').read_text('utf-8'))
            mapping={e['target']:e['expression'] for e in equations}
            d=cfg['world']['mini_world']['definition']
            for key,state in d['variables'].items():
                self.assertEqual(mapping['next.'+key],state['next'])
            logical_edges=[e for e in graph['edges'] if e['relation']=='structural_eligibility']
            self.assertEqual(len(logical_edges),len(d['recipes']))
            self.assertEqual(json.loads((root/'definition.json').read_text('utf-8')),d)
            self.assertTrue((root/'equations.tex').exists())


if __name__=='__main__':
    unittest.main()
