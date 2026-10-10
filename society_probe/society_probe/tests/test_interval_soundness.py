import hashlib
import tempfile
import unittest
from pathlib import Path

import interval_proofs as proof


class RationalIntervalSoundness(unittest.TestCase):
    def test_universal_rational_theorems_and_cross_zero_multiplication(self):
        examples = '''
open Composed
def leftBox : Box := ⟨⟨-2,1⟩,⟨1,1⟩⟩
def rightBox : Box := ⟨⟨-3,1⟩,⟨4,1⟩⟩
def productBox : Box := ⟨⟨-8,1⟩,⟨6,1⟩⟩
def half : Q := ⟨1,2⟩
def minusHalf : Q := ⟨-1,2⟩
theorem rationalProductEnclosed : InBox productBox (mul half minusHalf) :=
  check_mul_sound leftBox rightBox productBox half minusHalf
    (by decide) (by decide) (by decide)
def positiveBox : Box := ⟨⟨1,3⟩,⟨2,1⟩⟩
theorem positiveWitness : QPos half ∧ 0 < half.n :=
  checked_positive_sound positiveBox half (by decide) (by decide)
'''
        with tempfile.TemporaryDirectory() as folder:
            result=proof.check(proof.export(Path(folder)/'proof.lean',examples))
        self.assertEqual(result['status'],'lean_checked_partial_interval_soundness',result)

    def test_removing_product_corners_breaks_generic_soundness_proof(self):
        with tempfile.TemporaryDirectory() as folder:
            artifact=proof.export(Path(folder)/'bad.lean')
            path=Path(artifact['source']); data=path.read_text('utf-8')
            old='[mul c.a.lo c.b.lo, mul c.a.lo c.b.hi, mul c.a.hi c.b.lo, mul c.a.hi c.b.hi].all'
            self.assertIn(old,data)
            data=data.replace(old,'[mul c.a.lo c.b.lo].all',1)
            path.write_text(data,encoding='utf-8'); artifact['sha256']=hashlib.sha256(data.encode()).hexdigest()
            result=proof.check(artifact)
        self.assertEqual(result['status'],'lean_rejected',result)

    def test_zero_denominator_and_false_enclosure_are_rejected(self):
        for claim in ('InBox ⟨⟨0,1⟩,⟨2,1⟩⟩ ⟨1,0⟩',
                      'InBox ⟨⟨0,1⟩,⟨2,1⟩⟩ ⟨3,1⟩'):
            with tempfile.TemporaryDirectory() as folder:
                artifact=proof.export(Path(folder)/'bad.lean',
                    'open Composed\ntheorem falseEnclosure : '+claim+' := by decide\n')
                result=proof.check(artifact)
            self.assertEqual(result['status'],'lean_rejected',result)
