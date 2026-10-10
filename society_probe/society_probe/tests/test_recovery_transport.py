import hashlib
import json
import tempfile
import threading
import unittest
from unittest.mock import patch
from pathlib import Path
from recovery_transport import install


class RecoveryTransportTests(unittest.TestCase):
    def test_exhausted_survey_is_missing_and_resume_does_not_request_it_again(self):
        from types import SimpleNamespace
        import survey_measurement as measurement
        key='survey-measurement:source_informed_v3:30:a0'
        digest=hashlib.sha256(json.dumps(['model','survey_measurement',measurement.SYSTEM,{}],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
        class Fake:
            def __init__(self,cfg,output,mock=False):
                self.lock=threading.RLock();self.cached={};self.calls=0;self.mock=False
            def request(self,model,kind,system,payload,request_key=None):
                self.calls+=1;self.cached[request_key]={'call':self.calls,'request_hash':digest};return {}
        society=SimpleNamespace(state={'round':30,'agents':{'a0':{'alive':True,'model':'model'}},'surveys':[]},observe=lambda aid:{})
        with tempfile.TemporaryDirectory() as folder, patch.object(measurement,'collect'), \
                patch.object(measurement,'payload',return_value={}), patch.object(measurement,'validate',side_effect=ValueError('Inconsistent object detection')):
            install(Fake,1,skip_exhausted_surveys=True);api=Fake({},folder)
            measurement.collect(society,api)
            self.assertEqual(api.calls,3);self.assertEqual(society.state['surveys'],[])
            self.assertEqual(len(society.state['survey_failures']),1)
            self.assertEqual(society.state['survey_failures'][0]['request_key'],key)
            measurement.collect(society,api);self.assertEqual(api.calls,3)

    def test_semantic_survey_retry_uses_identical_input_and_keeps_budget(self):
        digest=hashlib.sha256(json.dumps(['model','survey_measurement','system',{}],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
        class Fake:
            def __init__(self,cfg,output,mock=False):
                self.cfg=cfg;self.lock=threading.RLock();self.calls=0;self.cost=.1
                self.cached={'key':{'call':1,'request_hash':digest,'response':'original inconsistent answer'}}
                self.raw=[]
            def request(self,model,kind,system,payload,request_key=None):
                self.calls+=1;self.raw.append((model,kind,system,payload,request_key))
                if request_key in self.cached:return {'invalid':True}
                self.cost+=.01;self.cached[request_key]={'call':2,'request_hash':digest}
                return {'valid':True}
        with tempfile.TemporaryDirectory() as folder:
            install(Fake,1)
            api=Fake({},folder)
            with patch('survey_measurement.validate',side_effect=[ValueError('Inconsistent object detection'),[]]):
                self.assertEqual(api.request('model','survey_measurement','system',{},'key'),{'valid':True})
            self.assertEqual(api.raw[0],api.raw[1]);self.assertAlmostEqual(api.cost,.11)
            record=json.loads((Path(folder)/'response_recovery.jsonl').read_text())
            self.assertEqual(record['reason'],'Inconsistent object detection');self.assertEqual(record['failed_call'],1)

    def make_api(self,folder,always_bad=False):
        digest=hashlib.sha256(json.dumps(['model','compress','system',{}],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
        class Fake:
            def __init__(self,cfg,output,mock=False):
                self.cfg=cfg;self.lock=threading.RLock();self.calls=0
                self.cached={'key':{'call':1,'request_hash':digest}}
            def request(self,model,kind,system,payload,request_key=None):
                self.calls+=1
                if always_bad:self.cached[request_key]={'call':self.calls,'request_hash':digest}
                if request_key in self.cached:raise ValueError('Invalid JSON response')
                return {'facts':[]}
        install(Fake,.8)
        return Fake({'max_estimated_cost_usd':.5},folder)

    def test_same_input_retry_preserves_failed_record_and_audits(self):
        with tempfile.TemporaryDirectory() as folder:
            api=self.make_api(folder)
            self.assertEqual(api.request('model','compress','system',{},'key'),{'facts':[]})
            record=json.loads((Path(folder)/'response_recovery.jsonl').read_text())
            self.assertEqual(record['failed_call'],1)
            self.assertEqual(api.calls,2)

    def test_limit_persists_across_resumes(self):
        with tempfile.TemporaryDirectory() as folder:
            api=self.make_api(folder,True)
            with self.assertRaises(ValueError):api.request('model','compress','system',{},'key')
            self.assertEqual(api.calls,3)
            resumed=self.make_api(folder,True)
            with self.assertRaises(ValueError):resumed.request('model','compress','system',{},'key')
            self.assertEqual(resumed.calls,1)
            self.assertEqual(len((Path(folder)/'response_recovery.jsonl').read_text().splitlines()),2)

    def test_input_mismatch_is_never_retried(self):
        with tempfile.TemporaryDirectory() as folder:
            api=self.make_api(folder)
            with self.assertRaises(ValueError):api.request('model','compress','changed',{},'key')
            self.assertEqual(api.calls,1)
            self.assertIn('key',api.cached)

    def test_budget_overlay_does_not_modify_scientific_config(self):
        with tempfile.TemporaryDirectory() as folder:
            api=self.make_api(folder)
            self.assertEqual(api.cfg['max_estimated_cost_usd'],.8)

    def test_resume_catalog_keeps_real_backend_and_preserves_input_config(self):
        class Fake:
            def __init__(self,cfg,output,mock=False):
                self.cfg=cfg;self.mock=mock
            def request(self,*args,**kwargs):
                return {}
        with tempfile.TemporaryDirectory() as folder:
            catalog=[{'id':'model','supported_parameters':['response_format','structured_outputs']}]
            (Path(folder)/'model_catalog.json').write_text(json.dumps(catalog),encoding='utf-8')
            install(Fake,.8,2,True)
            cfg={'models':['model'],'structured_outputs':True,'max_estimated_cost_usd':.5,'network_retries':0}
            with patch.dict('os.environ',{'OPENROUTER_API_KEY':'test-only-placeholder'}):
                api=Fake(cfg,folder,False)
            self.assertFalse(api.mock)
            self.assertEqual(api.catalog['model']['id'],'model')
            self.assertEqual(api.cfg['network_retries'],2)
            self.assertEqual(cfg['network_retries'],0)
