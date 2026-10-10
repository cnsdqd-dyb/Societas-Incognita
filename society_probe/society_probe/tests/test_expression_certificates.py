import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import expression_certificates as ec
from composed_certificates import Compiler, Unsupported


class ExpressionCompilation(unittest.TestCase):
    def kernel_check(self, equations):
        with tempfile.TemporaryDirectory() as folder:
            a = ec.export({}, Path(folder)/'expressions.lean', equations)
            return ec.check(a)

    def test_every_supported_operator_and_nested_composition(self):
        x = {'ref': 'state.x'}; y = {'ref': 'pool.B'}
        equations = [{'op': op, 'args': [x, y]} for op in
                     ('add','sub','mul','div','min','max','lt','le','eq','gt','ge','and','or')]
        equations += [{'op': 'not', 'args': [x]},
                      {'op': 'clamp', 'args': [x, -2, 3]}]
        equations += [{'op': 'pow', 'args': [x, n]} for n in range(5)]
        equations += [{'op': op, 'args': [x,y,0,2]} for op in ('add','mul','min','max','and','or')]
        equations += [{'op':'clamp','args':[{'op':'pow','args':[{'op':'sub','args':[x,y]},3]},0,20]}]
        result = self.kernel_check(equations)
        self.assertEqual(result['status'], 'lean_checked_expression_compilation', result)
        self.assertEqual(result['expression_count'], 27)

    def test_wrong_actual_comparison_lowering_is_rejected(self):
        original = Compiler.expr
        def broken(self, e, ctx):
            if isinstance(e, dict) and e.get('op') == 'gt':
                e = copy.deepcopy(e); e['op'] = 'lt'
            return original(self, e, ctx)
        with patch.object(Compiler, 'expr', broken):
            result = self.kernel_check([{'op':'gt','args':[{'ref':'x'}, {'ref':'y'}]}])
        self.assertEqual(result['status'], 'lean_rejected')

    def test_tampered_power_and_clamp_structure_are_rejected(self):
        for e in ({'op':'pow','args':[{'ref':'x'},3]},
                  {'op':'clamp','args':[{'ref':'x'},0,2]}):
            with tempfile.TemporaryDirectory() as folder:
                a = ec.export({}, Path(folder)/'proof.lean', [e])
                path = Path(a['source']); source = path.read_text('utf-8')
                start = source.index('def target0 : Term := ')
                end = source.index('\n', start)
                source = source[:start] + 'def target0 : Term := (.lit 999 1)' + source[end:]
                path.write_text(source,encoding='utf-8'); a['sha256'] = hashlib.sha256(source.encode()).hexdigest()
                self.assertEqual(ec.check(a)['status'], 'lean_rejected')

    def test_six_module_source_is_bound_and_all_equations_checked(self):
        cfg=json.loads(Path('reports/composed_lean_20261010/all_six_modules_config.json').read_text('utf-8'))
        d=cfg['world']['mini_world']['definition']
        result=self.kernel_check(ec.expressions(d))
        self.assertEqual(result['status'], 'lean_checked_expression_compilation', result)
        self.assertEqual(result['expression_count'],53)

    def test_transcendental_operator_has_no_fabricated_certificate(self):
        with self.assertRaises(Unsupported):
            self.kernel_check([{'op':'exp','args':[1]}])
