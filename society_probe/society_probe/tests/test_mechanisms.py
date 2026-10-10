import copy,json,tempfile,unittest
from pathlib import Path
from sim import Society,run,entropy
from generate_env import generate,solve_reference
BASE=json.loads(Path('configs/smoke.json').read_text())
class Mechanisms(unittest.TestCase):
    def test_private_membership_and_closure(self):
        s=Society(BASE);s.state['round']=1
        s.communicate('a0',{'op':'invite','targets':['a1','a2']})
        with self.assertRaises(ValueError):s.communicate('a1',{'op':'send','chat':'c1','text':'x'})
        s.communicate('a1',{'op':'accept','chat':'c1'})
        s.communicate('a2',{'op':'reject','chat':'c1'})
        for a in s.state['agents'].values():a['inbox']=[]
        s.communicate('a0',{'op':'send','chat':'c1','text':'secret'})
        self.assertEqual(s.state['agents']['a1']['inbox'][0]['text'],'secret')
        self.assertEqual(s.state['agents']['a2']['inbox'],[])
        self.assertEqual(s.state['agents']['a3']['inbox'],[])
        s.communicate('a0',{'op':'close','chat':'c1'})
        self.assertNotIn('c1',s.observe('a1')['chats'])
        with self.assertRaises(ValueError):s.communicate('a0',{'op':'send','chat':'c1','text':'x'})
    def test_resources_and_tools(self):
        s=Society(BASE)
        total=lambda:sum(s.state['zones'])+sum(a['stock'] for a in s.state['agents'].values())
        before=total();s.act('a0',{'tool':'harvest','zone':0,'amount':3})
        s.act('a0',{'tool':'transfer','target':'a1','amount':1})
        self.assertEqual(before,total())
        with self.assertRaises(ValueError):s.act('a0',{'tool':'repair'})
    def test_pressure_and_expiry(self):
        cfg=copy.deepcopy(BASE);cfg['world']['survival_pressure']=True
        s=Society(cfg);s.state['agents']['a0']['stock']=0
        s.communicate('a0',{'op':'invite','targets':['a1']})
        for t in range(1,6):s.state['round']=t;s.settle()
        self.assertFalse(s.state['agents']['a0']['alive'])
        self.assertFalse(s.state['chats']['c1']['open'])
    def test_paired_hidden_mechanisms(self):
        a=generate(BASE,'supply',7,False);b=generate(BASE,'supply',7,True)
        self.assertEqual(a['world']['regeneration'],b['world']['regeneration'])
        observed=Society(a).observe('a0')
        self.assertNotIn('regeneration',observed['world_rules'])
        self.assertNotIn('research_reference',observed)
        self.assertLessEqual(solve_reference(a['world'],4)['base_sustainable_throughput'],sum(a['world']['regeneration']))
    def test_mock_compaction_survey_resume(self):
        cfg=copy.deepcopy(BASE);cfg['memory']['trigger_chars']=200
        with tempfile.TemporaryDirectory() as out:
            run(cfg,out,mock=True)
            result=json.loads((Path(out)/'result.json').read_text(encoding='utf-8'))
            self.assertTrue(result['synthetic']);self.assertGreater(result['compactions'],0)
            cp=json.loads((Path(out)/'checkpoint.json').read_text(encoding='utf-8'))
            for a in cp['state']['agents'].values():self.assertFalse(any('responses' in x for x in a['recent']))
            run(cfg,out,mock=True,resume=True)
            self.assertEqual(result,json.loads((Path(out)/'result.json').read_text(encoding='utf-8')))
    def test_entropy_is_not_approval(self):self.assertEqual(entropy([1,1,1]),entropy([5,5,5]))
if __name__=='__main__':unittest.main()

class Transport(unittest.TestCase):
    def test_openrouter_adapter_and_secret_free_logs(self):
        from unittest.mock import patch
        import io
        from sim import API
        model=BASE['models'][0]
        catalog={'data':[{'id':model,'supported_parameters':['response_format'],
                         'pricing':{'prompt':'0.0000001','completion':'0.0000001'}}]}
        response={'choices':[{'message':{'content':'{"ok":true}'}}],
                  'usage':{'prompt_tokens':10,'completion_tokens':3,'cost':0.0000013},
                  'model':model,'provider':'test-provider'}
        captured=[]
        def fake_open(req,timeout):
            captured.append(req)
            return io.BytesIO(json.dumps(catalog if len(captured)==1 else response).encode())
        with tempfile.TemporaryDirectory() as out, patch.dict('os.environ',{'OPENROUTER_API_KEY':'test-secret'}), patch('urllib.request.urlopen',side_effect=fake_open):
            api=API(BASE,out)
            self.assertEqual(api.request(model,'act','test',{'input':'test'}),{'ok':True})
            body=json.loads(captured[-1].data)
            self.assertEqual(body['response_format'],{'type':'json_object'})
            self.assertFalse(body['provider']['allow_fallbacks'])
            self.assertNotIn('test-secret',(Path(out)/'calls.jsonl').read_text())
            self.assertAlmostEqual(api.cost,0.0000013)
