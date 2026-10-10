import unittest
import tempfile
from unittest.mock import patch
import jsonschema
import schemas
import sim
import interaction_controls
from provider_schema import mistral_transport_schema,validate_phase_response
from test_material_capabilities import device_config


class ProviderContracts(unittest.TestCase):
    def test_api_applies_phase_gate_before_a_world_transition(self):
        cfg=device_config()
        with tempfile.TemporaryDirectory() as directory:
            api=sim.API(cfg,directory,mock=True)
            with patch.object(api,'script',return_value={'communication':{'op':'silent'}}):
                with self.assertRaisesRegex(ValueError,'rollout paused'):
                    api.request(cfg['models'][0],'act','',{},request_key='contract-test')

    def test_missing_physical_action_pauses_instead_of_simulating_starvation(self):
        with self.assertRaisesRegex(ValueError,'rollout paused'):
            validate_phase_response('act',{'communication':{'op':'silent'}})
        good={'action':{'tool':'gather','amount':999},'communication':{'op':'silent'}}
        # Physically illegal choices are evaluated by the world, not repaired.
        self.assertIs(validate_phase_response('act',good),good)

    def test_projection_preserves_required_action_and_silent_communication(self):
        cfg=device_config(); cfg['communication']['budget']={'unit':'characters','limit':1000}
        observation=sim.Society(cfg).observe('a0')
        original=schemas.schema('act',observation,cfg)
        remote=mistral_transport_schema(original)
        jsonschema.Draft202012Validator.check_schema(remote)
        for good in ({'action':{'tool':'wait'},'communication':{'op':'silent'}},
                     {'action':{'tool':'gather','item':'A','amount':1},'communication':{'op':'silent'}}):
            jsonschema.validate(good,remote)
        for bad in ({'communication':{'op':'silent'}},
                    {'action':{'tool':'invented'},'communication':{'op':'silent'}},
                    {'action':{'tool':'gather','item':'A'},'communication':{'op':'silent'}}):
            with self.assertRaises(jsonschema.ValidationError): jsonschema.validate(bad,remote)
        self.assertIn('maxLength',str(original)); self.assertNotIn('maxLength',str(remote))

    def test_physical_prompt_ends_with_current_phase_and_output_contract(self):
        cfg=device_config(); cfg['communication']['budget']={'unit':'characters','limit':1000}
        cfg['world_rule_visibility']='hidden'
        help=interaction_controls.actor_help(cfg,sim.Society(cfg).observe('a0'),'')
        self.assertIn('PHYSICAL_ACTION',help[-400:])
        self.assertTrue(help.endswith('{"action":{"tool":"wait"},"communication":{"op":"silent"}}。'))
