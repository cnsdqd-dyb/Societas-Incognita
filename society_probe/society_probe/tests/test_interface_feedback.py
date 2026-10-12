import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from interface_feedback import InterfaceError, feedback, record_error, experiment_feedback
import mini_world


def config():
    return {'world':{'mini_world':{'definition':{'quantity_semantics':'continuous_v1',
        'max_quantity':8,'resources':{'A':{},'B':{}}}}}}


class InterfaceFeedbackTests(unittest.TestCase):
    def test_duplicate_has_specific_hint_without_mutating_input(self):
        basket=[{'item':'A','amount':8},{'item':'A','amount':2}]
        original=json.dumps(basket)
        with self.assertRaises(InterfaceError) as caught:mini_world.parse_basket(config(),basket)
        detail=feedback(caught.exception)
        self.assertEqual(detail['code'],'DUPLICATE_MATERIAL')
        self.assertEqual(detail['details'],{'item':'A'})
        self.assertIn('合并',detail['hint'])
        self.assertEqual(json.dumps(basket),original)

    def test_fractional_shortage_reports_exact_own_balance(self):
        a={'stock':4,'inventory':{'A':.9918688392825664}}
        with self.assertRaises(InterfaceError) as caught:mini_world.check_payment(a,{'A':1})
        d=feedback(caught.exception)['details']['shortages'][0]
        self.assertEqual(d['available'],a['inventory']['A'])
        self.assertAlmostEqual(d['shortfall'],1-a['inventory']['A'])
        self.assertEqual(a['stock'],4)

    def test_decimal_remains_legal_but_batches_integer(self):
        self.assertEqual(mini_world.quantity(config(),.5),.5)
        for bad in [0,-1,float('inf'),float('nan'),True,'1']:
            with self.assertRaises(InterfaceError):mini_world.quantity(config(),bad)
        with self.assertRaises(InterfaceError) as caught:mini_world.quantity(config(),.5,integer=True)
        self.assertEqual(feedback(caught.exception)['code'],'INTEGER_QUANTITY')

    def test_legacy_flags_still_work_and_private_internal_errors_are_hidden(self):
        outcome={};record_error(outcome,'action',KeyError('secret recipe coefficient'))
        self.assertIn('action_error',outcome)
        self.assertIn('action_feedback',outcome)
        self.assertNotIn('secret',json.dumps(outcome))
        self.assertNotIn('secret',json.dumps(feedback(ValueError('secret hidden rule'))))

    def test_known_permission_and_id_errors_are_distinct(self):
        self.assertEqual(feedback(ValueError('Chat not visible at decision time'),'communication')['code'],'CHAT_NOT_VISIBLE')
        self.assertEqual(feedback(ValueError('Game unavailable'))['code'],'GAME_UNAVAILABLE')
        self.assertEqual(feedback(ValueError('Not eligible to accept offer'))['code'],'ITEM_OFFER_PERMISSION')

    def test_no_output_is_execution_not_interface_rejection(self):
        record={'result':'no_product','produced':{}}
        d=experiment_feedback(record)
        self.assertEqual(d['status'],'executed_no_output')
        self.assertEqual(d['code'],'NO_OUTPUT')
        self.assertNotIn('recipe',json.dumps(d))

    def test_feedback_reaches_next_agent_observation_and_checkpoint(self):
        import sim
        from test_mini_world import config as world_config
        c=world_config(pressure=False);c['rounds']=2
        observations=[]
        class BadBasketAPI(sim.API):
            def script(self,kind,payload):
                if kind=='act':
                    observations.append(payload)
                    return {'action':{'tool':'experiment','facility':'F0','mode':'combine',
                        'inputs':[{'item':'A','amount':1},{'item':'A','amount':1}],'batches':1},
                        'communication':{'op':'silent'}}
                return super().script(kind,payload)
        with tempfile.TemporaryDirectory() as folder,patch.object(sim,'API',BadBasketAPI):
            sim.run(c,folder,mock=True)
            state=json.loads((Path(folder)/'checkpoint.json').read_text('utf-8'))['state']
        self.assertTrue(all(e['outcome']['action_feedback']['code']=='DUPLICATE_MATERIAL' for e in state['events']))
        previous=[o['recent'][-1]['outcome']['action_feedback']['code'] for o in observations if o['recent']]
        self.assertEqual(previous,['DUPLICATE_MATERIAL']*4)


if __name__=='__main__':unittest.main()
