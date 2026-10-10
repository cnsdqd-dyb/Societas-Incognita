import copy
import json
import tempfile
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import environments
from sim import Society
from prepare_multi_environment_v2 import config,witness
from prepare_environment_review import DESIGNS
from shared_budget import SharedBudget

SOURCE=json.loads(Path('configs/open_contest_mix_v1_20261009/contest_mixed4_p1_s7.json').read_text('utf-8'))
def society(family):
    d=next(d for d in DESIGNS if d['family']==family)
    return Society(config(SOURCE,d,'mixed4',1))
class AdditionalMechanismTests(unittest.TestCase):
    def test_all_seven_actual_engine_witnesses_both_pressures(self):
        for d in DESIGNS:
            for p in (0,1):self.assertEqual(witness(config(SOURCE,d,'mixed4',p))['person_rounds'],400)
    def test_threshold_failure_no_refund_and_no_current_round_leak(self):
        s=society('threshold');s.state['round']=1
        s.act('a0',{'tool':'contribute','amount':2})
        self.assertEqual(environments.observation(s.cfg,s.state,'a1')['previous_contributions'],{})
        s.settle(environments.physical_snapshot(s.state))
        self.assertEqual(s.state['agents']['a0']['stock'],1.5)
        self.assertFalse(s.state['environment_history'][-1]['threshold_activated'])
    def test_production_atomicity_visibility_and_busy_constraint(self):
        s=society('complementary');s.state['round']=1
        s.act('a0',{'tool':'propose','target':'a1','own_input':1,'other_input':1,'share':50})
        before=copy.deepcopy(s.state)
        with self.assertRaises(ValueError):s.act('a1',{'tool':'accept_offer','offer':'offer1'})
        self.assertEqual(before,s.state)
        s.state['round']=2;s.state['agents']['a0']['stock']=0
        before=copy.deepcopy(s.state)
        with self.assertRaises(ValueError):s.act('a1',{'tool':'accept_offer','offer':'offer1'})
        self.assertEqual(before,s.state)
        s.state['agents']['a0']['stock']=4
        s.act('a1',{'tool':'accept_offer','offer':'offer1'})
        self.assertEqual(s.state['agents']['a0']['stock'],3)
        self.assertEqual(s.state['agents']['a1']['stock'],3)
        s.settle(environments.physical_snapshot(s.state))
        self.assertEqual(s.state['agents']['a0']['stock'],5.5)
        self.assertEqual(s.state['agents']['a1']['stock'],5.5)
    def test_network_distance_externality_and_unilateral_removal(self):
        s=society('network');s.state['round']=1;s.act('a1',{'tool':'request_link','target':'a0'})
        before=copy.deepcopy(s.state)
        with self.assertRaises(ValueError):s.act('a0',{'tool':'accept_link','target':'a1'})
        self.assertEqual(before,s.state)
        s.state['round']=2;s.act('a0',{'tool':'accept_link','target':'a1'})
        s.settle(environments.physical_snapshot(s.state))
        r=s.state['environment_history'][-1]
        self.assertAlmostEqual(r['gross_service_inflows']['a0'],.8)
        self.assertAlmostEqual(r['edge_upkeep']['a0'],.2)
        s.act('a1',{'tool':'disconnect','target':'a0'})
        self.assertEqual(s.state['mechanism_state']['edges'],[])
    def test_network_insolvency_clearing_terminates_and_keeps_balances_nonnegative(self):
        s=society('network');s.cfg['world']['edge_cost_per_endpoint']=10
        s.state['mechanism_state']['edges']=[['a0','a1'],['a1','a2']]
        s.settle(environments.physical_snapshot(s.state))
        self.assertEqual(s.state['mechanism_state']['edges'],[])
        self.assertTrue(all(a['stock']>=0 for a in s.state['agents'].values()))
    def test_optional_arts_are_real_content_without_resource_bonus(self):
        s=society('threshold');s.act('a0',{'tool':'create','title':'test','content':'real content'})
        r=s.act('a1',{'tool':'read_artifact','artifact':'work1'})
        self.assertEqual(r['artifact']['content'],'real content')
        self.assertEqual(s.state['agents']['a0']['stock'],4)
        s.act('a1',{'tool':'damage','target':'artifact:work1'})
        self.assertEqual(s.state['agents']['a1']['stock'],3)
        with self.assertRaises(ValueError):s.act('a0',{'tool':'read_artifact','artifact':'work1'})
    def test_shared_budget_parallel_reservation_and_restart(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'budget.sqlite3';b=SharedBudget.create(path,1.)
            def attempt(i):
                try:b.reserve(str(i),.3);return True
                except RuntimeError:return False
            with ThreadPoolExecutor(max_workers=8) as p:self.assertEqual(sum(p.map(attempt,range(8))),3)
            self.assertAlmostEqual(SharedBudget(path).status()['conservative_committed_usd'],.9)
            import sqlite3
            with sqlite3.connect(path) as db:winner=db.execute('SELECT key FROM requests LIMIT 1').fetchone()[0]
            db.close()
            b.finish(winner,.1,'billed');self.assertAlmostEqual(b.status()['conservative_committed_usd'],.7)
            with self.assertRaises(RuntimeError):b.reserve_native('no-authorization')
if __name__=='__main__':unittest.main()
