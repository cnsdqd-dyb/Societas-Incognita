import unittest
from analyze_open_campaign import certificates
from prepare_open_campaign import configuration


class OpenCertificates(unittest.TestCase):
    def test_pressure_extrema_have_distinct_attainable_lower_witnesses(self):
        c=certificates(configuration('mistralai/ministral-3b-2512',True))
        self.assertEqual(c['lower'][:7],[8,8,8,8,1,0,0])
        self.assertEqual(c['policy_witnesses']['extinct6'][:7],[8,8,8,8,8,0,0])
        self.assertEqual(c['policy_witnesses']['one5'][4],1)
        self.assertEqual(c['policy_witnesses']['balanced'],[8]*50)
        # Pointwise minima have different witnesses. Neither lower witness attains
        # their sum, so the algorithm does not label that sum a trajectory optimum.
        self.assertLess(sum(c['lower']),sum(c['policy_witnesses']['extinct6']))
        self.assertLess(sum(c['lower']),sum(c['policy_witnesses']['one5']))

    def test_no_pressure_has_flat_survival_bounds_for_all_witnesses(self):
        c=certificates(configuration('openai/gpt-oss-20b',False))
        self.assertEqual(c['lower'],c['upper'])
        for alive in c['policy_witnesses'].values():self.assertEqual(alive,[8]*50)

    def test_changed_initialization_cannot_reuse_this_certificate(self):
        cfg=configuration('gpt-6.1-sol',True);cfg['world']['initial_personal_stock']=3
        with self.assertRaisesRegex(ValueError,'parameters changed'):certificates(cfg)


if __name__=='__main__':unittest.main()
