import hashlib
import tempfile
import unittest
from pathlib import Path

import interval_proofs as proof


class CompleteIntervalSoundness(unittest.TestCase):
    def kernel(self, examples):
        with tempfile.TemporaryDirectory() as folder:
            artifact=proof.export(Path(folder)/'proof.lean','open Composed\n'+examples,include_advanced=True)
            return proof.check(artifact)

    def test_all_thirteen_operators_have_generic_soundness(self):
        result=self.kernel('')
        self.assertEqual(result['status'],'lean_checked_interval_soundness',result)
        self.assertEqual(len(result['proved_operators']),13)

    def test_negative_floor_and_rejection_of_integer_crossing(self):
        result=self.kernel('''
def a : Box := ⟨⟨-19,10⟩,⟨-11,10⟩⟩
def r : Box := ⟨⟨-2,1⟩,⟨-2,1⟩⟩
theorem negativeFloor : InBox r (qfloor ⟨-3,2⟩) :=
  check_floor_sound a a r ⟨-3,2⟩ (by decide) (by decide)
def crossing : Box := ⟨⟨-21,10⟩,⟨-19,10⟩⟩
theorem ambiguousFloorRejected : check ⟨.floor,crossing,a,r⟩ = false := by decide
''')
        self.assertEqual(result['status'],'lean_checked_interval_soundness',result)

    def test_comparison_branches_and_noncanonical_fraction_equality(self):
        result=self.kernel('''
def small : Box := ⟨⟨1,3⟩,⟨2,3⟩⟩
def large : Box := ⟨⟨2,1⟩,⟨3,1⟩⟩
def yes : Box := ⟨one,one⟩
def no : Box := ⟨zero,zero⟩
theorem less : InBox yes (qbool (lt ⟨1,2⟩ ⟨5,2⟩)) :=
  check_lt_sound small large yes ⟨1,2⟩ ⟨5,2⟩ (by decide) (by decide) (by decide)
theorem notLess : InBox no (qbool (lt ⟨5,2⟩ ⟨1,2⟩)) :=
  check_lt_sound large small no ⟨5,2⟩ ⟨1,2⟩ (by decide) (by decide) (by decide)
theorem notLessEqual : InBox no (qbool (le ⟨5,2⟩ ⟨1,2⟩)) :=
  check_le_sound large small no ⟨5,2⟩ ⟨1,2⟩ (by decide) (by decide) (by decide)
def halfBox : Box := ⟨⟨1,2⟩,⟨2,4⟩⟩
def halfAgain : Box := ⟨⟨3,6⟩,⟨4,8⟩⟩
theorem sameValue : InBox yes (qbool (eq ⟨5,10⟩ ⟨6,12⟩)) :=
  check_eq_sound halfBox halfAgain yes ⟨5,10⟩ ⟨6,12⟩ (by decide) (by decide) (by decide)
theorem differentValue : InBox no (qbool (eq ⟨1,2⟩ ⟨5,2⟩)) :=
  check_eq_sound small large no ⟨1,2⟩ ⟨5,2⟩ (by decide) (by decide) (by decide)
theorem overlappingComparisonRejected : check ⟨.lt,small,small,yes⟩ = false := by decide
''')
        self.assertEqual(result['status'],'lean_checked_interval_soundness',result)

    def test_truth_negative_zero_and_positive(self):
        result=self.kernel('''
def below : Box := ⟨⟨-3,1⟩,⟨-1,1⟩⟩
def above : Box := ⟨⟨1,1⟩,⟨3,1⟩⟩
def yes : Box := ⟨one,one⟩
def no : Box := ⟨zero,zero⟩
theorem negativeTruth : InBox yes (qtruth ⟨-3,2⟩) :=
  check_truth_sound below below yes ⟨-3,2⟩ (by decide) (by decide)
theorem positiveTruth : InBox yes (qtruth ⟨3,2⟩) :=
  check_truth_sound above above yes ⟨3,2⟩ (by decide) (by decide)
theorem zeroTruth : InBox no (qtruth ⟨0,17⟩) :=
  check_truth_sound no no no ⟨0,17⟩ (by decide) (by decide)
''')
        self.assertEqual(result['status'],'lean_checked_interval_soundness',result)

    def test_positive_and_negative_divisors_and_cross_zero_numerators(self):
        result=self.kernel('''
def numerator : Box := ⟨⟨-2,1⟩,⟨3,1⟩⟩
def pos : Box := ⟨⟨2,1⟩,⟨4,1⟩⟩
def neg : Box := ⟨⟨-4,1⟩,⟨-2,1⟩⟩
def rp : Box := ⟨⟨-1,1⟩,⟨3,2⟩⟩
def rn : Box := ⟨⟨-3,2⟩,⟨1,1⟩⟩
theorem positiveDivisor : InBox rp (div ⟨-1,2⟩ ⟨6,2⟩) :=
  check_div_sound numerator pos rp ⟨-1,2⟩ ⟨6,2⟩ (by decide) (by decide) (by decide)
theorem negativeDivisor : InBox rn (div ⟨-1,2⟩ ⟨-6,2⟩) :=
  check_div_sound numerator neg rn ⟨-1,2⟩ ⟨-6,2⟩ (by decide) (by decide) (by decide)
def crossing : Box := ⟨⟨-1,1⟩,⟨1,1⟩⟩
theorem zeroCrossingRejected : check ⟨.div,numerator,crossing,rp⟩ = false := by decide
def touch : Box := ⟨zero,one⟩
theorem zeroEndpointRejected : check ⟨.div,numerator,touch,rp⟩ = false := by decide
''')
        self.assertEqual(result['status'],'lean_checked_interval_soundness',result)

    def test_dropped_floor_stability_guard_breaks_the_proof(self):
        with tempfile.TemporaryDirectory() as folder:
            artifact=proof.export(Path(folder)/'bad.lean',include_advanced=True)
            path=Path(artifact['source']); text=path.read_text('utf-8')
            guard='c.a.lo.n / (Int.ofNat c.a.lo.d) == c.a.hi.n / (Int.ofNat c.a.hi.d)'
            self.assertIn(guard,text)
            text=text.replace(guard,'true',1); path.write_text(text,encoding='utf-8')
            artifact['sha256']=hashlib.sha256(text.encode()).hexdigest()
            result=proof.check(artifact)
        self.assertEqual(result['status'],'lean_rejected',result)
