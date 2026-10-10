import json
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

from numerical_audit import FloatReplayAudit, runtime_environment


class NumericalAudit(unittest.TestCase):
    def test_reports_interval_violation_and_location(self):
        audit = FloatReplayAudit()
        audit.compare(Fraction(1), Fraction(2), 1.5, 'inside')
        audit.compare(Fraction(1), Fraction(1), 1+1e-8, 'round=3/a0/stock')
        report = audit.report()
        self.assertEqual(report['comparisons'], 2)
        self.assertGreater(report['max_interval_violation'], 0)
        self.assertEqual(report['worst_scaled_violation_location'], 'round=3/a0/stock')
        self.assertFalse(report['formal_ieee_equivalence'])
        json.dumps(report, allow_nan=False)

    def test_nonfinite_states_and_excessive_errors_fail_closed(self):
        for value in (float('nan'), float('inf'), -float('inf'), 1.01):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    FloatReplayAudit().compare(Fraction(1), Fraction(1), value, 'stock')

    def test_runtime_record_contains_numeric_platform_without_personal_identifiers(self):
        report = runtime_environment()
        self.assertIn('float_mantissa_bits', report)
        self.assertIn('machine_architecture', report)
        self.assertFalse({'hostname', 'username', 'executable', 'api_key'} & report.keys())
        json.dumps(report, allow_nan=False)

    def test_checkpoint_resume_keeps_environment_changes(self):
        import sim
        from test_mini_world import PhysicalAPI, config
        cfg = config(); cfg['rounds'] = 1
        initial = runtime_environment()
        changed = dict(initial, os_release='test-environment-change')
        PhysicalAPI.fail_key = None
        with tempfile.TemporaryDirectory() as folder, patch.object(sim, 'API', PhysicalAPI):
            with patch('numerical_audit.runtime_environment', return_value=initial):
                sim.run(cfg, folder, mock=True)
            with patch('numerical_audit.runtime_environment', return_value=changed):
                sim.run(cfg, folder, mock=True, resume=True)
            history = json.loads((Path(folder)/'runtime_environments.json').read_text('utf-8'))
            self.assertEqual([row['environment'] for row in history], [initial, changed])
            self.assertTrue(history[1]['resumed'])
            result = json.loads((Path(folder)/'result.json').read_text('utf-8'))
            self.assertEqual(result['runtime_environment'], changed)
