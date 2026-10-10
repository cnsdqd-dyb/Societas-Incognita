import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from sim import Society,API,run
import hierarchical_memory


class HierarchicalMemoryTests(unittest.TestCase):
    def config(self):
        cfg=json.loads(Path('configs/core_pilot_v5_20261005/commons_p0_basic_s7.json').read_text(encoding='utf-8'))
        cfg['models']=cfg['models'][:2];cfg['rounds']=18;cfg['survey_rounds']=[0,18]
        cfg['parallel_agents']=1;cfg['memory']['mode']='hierarchical_v1'
        return cfg

    def society(self):
        s=Society(self.config());s.state['round']=15
        s.state['agents']['a0']['recent']=[{'round':i,'agent':'a0','decision':{},'outcome':{},
            'observed_messages':[{'round':i,'from':'a1','channel':'c1','text':'private evidence'}]} for i in range(1,15)]
        return s

    def test_four_round_blocks_and_twelve_round_overview(self):
        s=self.society()
        with tempfile.TemporaryDirectory() as out:
            api=API(s.cfg,out,mock=True);hierarchical_memory.compact(s,'a0',api)
        a=s.state['agents']['a0'];self.assertEqual([r['round'] for r in a['recent']],[13,14])
        self.assertEqual(a['memory']['top']['through_round'],12)
        self.assertEqual(a['memory']['middle']['episodes'],[])
        self.assertEqual(len(s.state['compactions']),4)
        self.assertEqual(s.state['compactions'][0]['records'][0]['observed_messages'][0]['channel'],'c1')

    def test_bad_episode_retains_original_history(self):
        s=self.society();before=copy.deepcopy(s.state['agents']['a0']['recent'])
        with tempfile.TemporaryDirectory() as out,patch.object(API,'script',return_value={'summary':123,'open_items':[]}):
            with self.assertRaisesRegex(ValueError,'original records retained'):
                hierarchical_memory.compact(s,'a0',API(s.cfg,out,mock=True))
        self.assertEqual(s.state['agents']['a0']['recent'],before)

    def test_top_failure_retains_middle_and_retry_does_not_redo_episodes(self):
        s=self.society();original=API.request
        def fail(api,model,kind,system,payload,request_key=None):
            if kind=='memory_overview':raise RuntimeError('Injected overview outage')
            return original(api,model,kind,system,payload,request_key)
        with tempfile.TemporaryDirectory() as out:
            api=API(s.cfg,out,mock=True)
            with patch.object(API,'request',fail),self.assertRaises(RuntimeError):hierarchical_memory.compact(s,'a0',api)
            self.assertEqual(len(s.state['agents']['a0']['memory']['middle']['episodes']),3)
            hierarchical_memory.compact(s,'a0',api)
        self.assertEqual(sum(c['level']=='middle' for c in s.state['compactions']),3)

    def test_checkpoint_resume_and_private_memory(self):
        cfg=self.config()
        with tempfile.TemporaryDirectory() as out:
            run(cfg,out,mock=True)
            before=json.loads((Path(out)/'checkpoint.json').read_text(encoding='utf-8'))
            run(cfg,out,mock=True,resume=True)
            after=json.loads((Path(out)/'checkpoint.json').read_text(encoding='utf-8'))
            self.assertEqual(before,after)
            for agent in after['state']['agents'].values():
                self.assertEqual(agent['memory']['top']['through_round'],12)
                self.assertLessEqual(len(agent['recent']),6)

    def test_mid_overview_failure_resumes_from_durable_episode_commit(self):
        cfg=self.config();original=API.request
        def fail(api,model,kind,system,payload,request_key=None):
            if kind=='memory_overview' and request_key.endswith(':a0'):
                raise RuntimeError('Injected top-level outage')
            return original(api,model,kind,system,payload,request_key)
        with tempfile.TemporaryDirectory() as interrupted,tempfile.TemporaryDirectory() as clean:
            with patch.object(API,'request',fail),self.assertRaises(RuntimeError):run(cfg,interrupted,mock=True)
            run(cfg,interrupted,mock=True,resume=True);run(cfg,clean,mock=True)
            a=json.loads((Path(interrupted)/'checkpoint.json').read_text(encoding='utf-8'))
            b=json.loads((Path(clean)/'checkpoint.json').read_text(encoding='utf-8'))
            # Independent agents can finish compactions in a different order after an outage.
            for checkpoint in (a,b):
                checkpoint['state']['compactions'].sort(key=lambda c:(c['round'],c['agent'],c['level']))
            self.assertEqual(a,b)
