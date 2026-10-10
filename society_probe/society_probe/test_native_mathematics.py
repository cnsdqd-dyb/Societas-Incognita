"""Check new analytic certificates against the executable environment."""
import copy
import json
import unittest
from pathlib import Path

from sim import Society
import environments


class MathematicalCertificateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = json.loads(Path('runs/codex_gpt61_sol_low_8x50_20261007/config.json').read_text('utf-8'))

    def test_wait_until_completion_boundary_matches_physics(self):
        for stock in range(6):
            for energy in range(1, 6):
                for remaining in range(1, 11):
                    society = Society(copy.deepcopy(self.cfg))
                    society.state['agents']['a0'].update(stock=stock, energy=energy)
                    society.state['mechanism_state']['jobs']['a0'] = {'facility': 0, 'remaining': remaining, 'started': 0}
                    for t in range(1, remaining+1):
                        society.state['round'] = t
                        society.settle(environments.physical_snapshot(society.state))
                    threshold = stock + min(5, energy+stock)
                    self.assertEqual(society.state['agents']['a0']['alive'], remaining <= threshold,
                                     (stock, energy, remaining))

    def test_batch_delay_matches_all_simultaneous_arrivals(self):
        for old in [(0, 0), (2, 0), (0, 3), (2, 2)]:
            for count in range(1, 9-sum(old)):
                for k0 in range(count+1):
                    society = Society(copy.deepcopy(self.cfg))
                    ids = list(society.state['agents'])
                    offset = 0
                    for facility, n in enumerate(old):
                        for aid in ids[offset:offset+n]:
                            society.state['mechanism_state']['jobs'][aid] = {'facility': facility, 'remaining': 20, 'started': 0}
                        offset += n
                    new = ids[offset:offset+count]
                    society.state['round'] = 1
                    for i, aid in enumerate(new):
                        society.act(aid, {'tool': 'process', 'facility': 0 if i < k0 else 1})
                    society.settle(environments.physical_snapshot(society.state))
                    record = society.state['environment_history'][-1]
                    completed = {j['agent']: j for j in record['completed_jobs']}
                    jobs = society.state['mechanism_state']['jobs']
                    actual = sum((jobs[aid] if aid in jobs else completed[aid])['remaining']+1 for aid in new)
                    analytic = k0*(old[0]+k0)+(count-k0)*(old[1]+count-k0)
                    self.assertEqual(actual, analytic, (old, count, k0))


if __name__ == '__main__':
    unittest.main()
