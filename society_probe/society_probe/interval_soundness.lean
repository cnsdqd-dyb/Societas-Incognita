import Std

-- This file is concatenated after composed_checker.lean by the certificate
-- exporter. The statements quantify over all rational inputs, not test cases.
namespace Composed

def QLe (a b : Q) : Prop := a.n * (b.d : Int) ≤ b.n * (a.d : Int)
def QPos (a : Q) : Prop := 0 < a.d
def InBox (b : Box) (x : Q) : Prop := QPos x ∧ QLe b.lo x ∧ QLe x b.hi
instance (a b : Q) : Decidable (QLe a b) :=
  inferInstanceAs (Decidable (a.n * (b.d : Int) ≤ b.n * (a.d : Int)))
instance (a : Q) : Decidable (QPos a) := inferInstanceAs (Decidable (0 < a.d))
instance (b : Box) (x : Q) : Decidable (InBox b x) :=
  inferInstanceAs (Decidable (QPos x ∧ QLe b.lo x ∧ QLe x b.hi))

theorem qle_trans {a b c : Q} (hb : QPos b)
    (hab : QLe a b) (hbc : QLe b c) : QLe a c := by
  have h1 := Int.mul_le_mul_of_nonneg_right hab (Int.natCast_nonneg c.d)
  have h2 := Int.mul_le_mul_of_nonneg_right hbc (Int.natCast_nonneg a.d)
  have hp : (0 : Int) < b.d := by exact_mod_cast hb
  apply Int.le_of_mul_le_mul_right (a := (b.d : Int)) (h := hp)
  simp only [QLe] at hab hbc ⊢
  simp only [Int.mul_assoc, Int.mul_comm, Int.mul_left_comm] at h1 h2 ⊢
  omega

theorem qle_add {a b x y : Q} (hax : QLe a x) (hby : QLe b y) :
    QLe (add a b) (add x y) := by
  have h1 := Int.mul_le_mul_of_nonneg_right hax (Int.mul_nonneg (Int.natCast_nonneg b.d) (Int.natCast_nonneg y.d))
  have h2 := Int.mul_le_mul_of_nonneg_right hby (Int.mul_nonneg (Int.natCast_nonneg a.d) (Int.natCast_nonneg x.d))
  simp only [QLe, add, Int.natCast_mul] at h1 h2 ⊢
  simp only [Int.add_mul, Int.mul_add, Int.mul_assoc, Int.mul_comm, Int.mul_left_comm] at h1 h2 ⊢
  omega

theorem qle_neg {a b : Q} (hab : QLe a b) : QLe (neg b) (neg a) := by
  simp only [QLe, neg, Int.neg_mul] at hab ⊢
  omega

theorem add_positive {a b : Q} (ha : QPos a) (hb : QPos b) : QPos (add a b) := by
  exact Nat.mul_pos ha hb

theorem check_add_sound (a b r : Box) (x y : Q)
    (checked : check ⟨.add, a, b, r⟩ = true)
    (hx : InBox a x) (hy : InBox b y) : InBox r (add x y) := by
  simp only [check, valid, le, Bool.and_eq_true, decide_eq_true_eq] at checked
  rcases hx with ⟨hxp, hxl, hxu⟩
  rcases hy with ⟨hyp, hyl, hyu⟩
  have alo : QPos a.lo := by simp_all [QPos]
  have blo : QPos b.lo := by simp_all [QPos]
  have ahi : QPos a.hi := by simp_all [QPos]
  have bhi : QPos b.hi := by simp_all [QPos]
  have lower : QLe r.lo (add a.lo b.lo) := by simp_all [QLe]
  have upper : QLe (add a.hi b.hi) r.hi := by simp_all [QLe]
  exact ⟨add_positive hxp hyp,
    qle_trans (add_positive alo blo) lower (qle_add hxl hyl),
    qle_trans (add_positive ahi bhi) (qle_add hxu hyu) upper⟩

theorem check_neg_sound (a b r : Box) (x : Q)
    (checked : check ⟨.neg, a, b, r⟩ = true)
    (hx : InBox a x) : InBox r (neg x) := by
  simp only [check, valid, le, Bool.and_eq_true, decide_eq_true_eq] at checked
  rcases hx with ⟨hxp, hxl, hxu⟩
  have ahi : QPos (neg a.hi) := by simp_all [QPos, neg]
  have alo : QPos (neg a.lo) := by simp_all [QPos, neg]
  have lower : QLe r.lo (neg a.hi) := by simp_all [QLe]
  have upper : QLe (neg a.lo) r.hi := by simp_all [QLe]
  exact ⟨hxp, qle_trans ahi lower (qle_neg hxu),
    qle_trans alo (qle_neg hxl) upper⟩

theorem check_sub_sound (a b r : Box) (x y : Q)
    (checked : check ⟨.sub, a, b, r⟩ = true)
    (hx : InBox a x) (hy : InBox b y) : InBox r (sub x y) := by
  simp only [check, valid, le, Bool.and_eq_true, decide_eq_true_eq] at checked
  rcases hx with ⟨hxp, hxl, hxu⟩
  rcases hy with ⟨hyp, hyl, hyu⟩
  have alo : QPos a.lo := by simp_all [QPos]
  have blo : QPos (neg b.lo) := by simp_all [QPos, neg]
  have ahi : QPos a.hi := by simp_all [QPos]
  have bhi : QPos (neg b.hi) := by simp_all [QPos, neg]
  have lower : QLe r.lo (sub a.lo b.hi) := by simp_all [QLe]
  have upper : QLe (sub a.hi b.lo) r.hi := by simp_all [QLe]
  exact ⟨add_positive hxp hyp,
    qle_trans (add_positive alo bhi) lower (qle_add hxl (qle_neg hyu)),
    qle_trans (add_positive ahi blo) (qle_add hxu (qle_neg hyl)) upper⟩

def qmin (a b : Q) : Q := if le a b then a else b
def qmax (a b : Q) : Q := if le a b then b else a

theorem qmin_positive {a b : Q} (ha : QPos a) (hb : QPos b) : QPos (qmin a b) := by
  unfold qmin; split <;> assumption
theorem qmax_positive {a b : Q} (ha : QPos a) (hb : QPos b) : QPos (qmax a b) := by
  unfold qmax; split <;> assumption
theorem qmin_le_left (a b : Q) : QLe (qmin a b) a := by
  unfold qmin; split <;> simp_all [le, QLe] <;> omega
theorem qmin_le_right (a b : Q) : QLe (qmin a b) b := by
  unfold qmin; split <;> simp_all [le, QLe] <;> omega
theorem qmax_ge_left (a b : Q) : QLe a (qmax a b) := by
  unfold qmax; split <;> simp_all [le, QLe] <;> omega
theorem qmax_ge_right (a b : Q) : QLe b (qmax a b) := by
  unfold qmax; split <;> simp_all [le, QLe] <;> omega
theorem qmin_lower {a b x : Q} (ha : QLe x a) (hb : QLe x b) : QLe x (qmin a b) := by
  unfold qmin; split <;> assumption
theorem qmin_upper {a b x : Q} (ha : QLe a x) (hb : QLe b x) : QLe (qmin a b) x := by
  unfold qmin; split <;> assumption
theorem qmax_lower {a b x : Q} (ha : QLe x a) (hb : QLe x b) : QLe x (qmax a b) := by
  unfold qmax; split <;> assumption
theorem qmax_upper {a b x : Q} (ha : QLe a x) (hb : QLe b x) : QLe (qmax a b) x := by
  unfold qmax; split <;> assumption

theorem qmin_mono {a b x y : Q} (ha : QPos a) (hb : QPos b)
    (_hx : QPos x) (_hy : QPos y) (hax : QLe a x) (hby : QLe b y) :
    QLe (qmin a b) (qmin x y) := by
  exact qmin_lower (qle_trans ha (qmin_le_left a b) hax)
    (qle_trans hb (qmin_le_right a b) hby)

theorem qmax_mono {a b x y : Q} (_ha : QPos a) (_hb : QPos b)
    (hx : QPos x) (hy : QPos y) (hax : QLe a x) (hby : QLe b y) :
    QLe (qmax a b) (qmax x y) := by
  exact qmax_upper (qle_trans hx hax (qmax_ge_left x y))
    (qle_trans hy hby (qmax_ge_right x y))

theorem check_min_sound (a b r : Box) (x y : Q)
    (checked : check ⟨.min, a, b, r⟩ = true)
    (hx : InBox a x) (hy : InBox b y) : InBox r (qmin x y) := by
  simp only [check, valid, le, Bool.and_eq_true, decide_eq_true_eq] at checked
  rcases hx with ⟨hxp, hxl, hxu⟩
  rcases hy with ⟨hyp, hyl, hyu⟩
  have alo : QPos a.lo := by simp_all [QPos]
  have blo : QPos b.lo := by simp_all [QPos]
  have ahi : QPos a.hi := by simp_all [QPos]
  have bhi : QPos b.hi := by simp_all [QPos]
  have lower : QLe r.lo (qmin a.lo b.lo) := by simp_all [QLe, qmin, le]
  have upper : QLe (qmin a.hi b.hi) r.hi := by simp_all [QLe, qmin, le]
  exact ⟨qmin_positive hxp hyp,
    qle_trans (qmin_positive alo blo) lower (qmin_mono alo blo hxp hyp hxl hyl),
    qle_trans (qmin_positive ahi bhi) (qmin_mono hxp hyp ahi bhi hxu hyu) upper⟩

theorem check_max_sound (a b r : Box) (x y : Q)
    (checked : check ⟨.max, a, b, r⟩ = true)
    (hx : InBox a x) (hy : InBox b y) : InBox r (qmax x y) := by
  simp only [check, valid, le, Bool.and_eq_true, decide_eq_true_eq] at checked
  rcases hx with ⟨hxp, hxl, hxu⟩
  rcases hy with ⟨hyp, hyl, hyu⟩
  have alo : QPos a.lo := by simp_all [QPos]
  have blo : QPos b.lo := by simp_all [QPos]
  have ahi : QPos a.hi := by simp_all [QPos]
  have bhi : QPos b.hi := by simp_all [QPos]
  have lower : QLe r.lo (qmax a.lo b.lo) := by simp_all [QLe, qmax, le]
  have upper : QLe (qmax a.hi b.hi) r.hi := by simp_all [QLe, qmax, le]
  exact ⟨qmax_positive hxp hyp,
    qle_trans (qmax_positive alo blo) lower (qmax_mono alo blo hxp hyp hxl hyl),
    qle_trans (qmax_positive ahi bhi) (qmax_mono hxp hyp ahi bhi hxu hyu) upper⟩

theorem mul_positive {a b : Q} (ha : QPos a) (hb : QPos b) : QPos (mul a b) := by
  exact Nat.mul_pos ha hb

theorem mul_comm (a b : Q) : mul a b = mul b a := by
  cases a; cases b; simp [mul, Int.mul_comm, Nat.mul_comm]

theorem qle_mul_nonneg {a b c : Q} (hab : QLe a b) (hc : 0 ≤ c.n) :
    QLe (mul a c) (mul b c) := by
  have h := Int.mul_le_mul_of_nonneg_right hab (Int.mul_nonneg hc (Int.natCast_nonneg c.d))
  simp only [QLe, mul, Int.natCast_mul] at h ⊢
  simpa only [Int.mul_assoc, Int.mul_comm, Int.mul_left_comm] using h

theorem qle_mul_nonpos {a b c : Q} (hab : QLe a b) (hc : c.n ≤ 0) :
    QLe (mul b c) (mul a c) := by
  have h := Int.mul_le_mul_of_nonpos_right hab (Int.mul_nonpos_of_nonpos_of_nonneg hc (Int.natCast_nonneg c.d))
  simp only [QLe, mul, Int.natCast_mul] at h ⊢
  simpa only [Int.mul_assoc, Int.mul_comm, Int.mul_left_comm] using h

theorem fixed_mul_enclosure (a r : Box) (x c : Q)
    (alo : QPos a.lo) (ahi : QPos a.hi) (hc : QPos c) (hx : InBox a x)
    (ll : QLe r.lo (mul a.lo c)) (lh : QLe r.lo (mul a.hi c))
    (ul : QLe (mul a.lo c) r.hi) (uh : QLe (mul a.hi c) r.hi) :
    InBox r (mul x c) := by
  rcases hx with ⟨xp, xl, xu⟩
  by_cases hn : 0 ≤ c.n
  · exact ⟨mul_positive xp hc,
      qle_trans (mul_positive alo hc) ll (qle_mul_nonneg xl hn),
      qle_trans (mul_positive ahi hc) (qle_mul_nonneg xu hn) uh⟩
  · have hn' : c.n ≤ 0 := by omega
    exact ⟨mul_positive xp hc,
      qle_trans (mul_positive ahi hc) lh (qle_mul_nonpos xu hn'),
      qle_trans (mul_positive alo hc) (qle_mul_nonpos xl hn') ul⟩

theorem check_mul_sound (a b r : Box) (x y : Q)
    (checked : check ⟨.mul, a, b, r⟩ = true)
    (hx : InBox a x) (hy : InBox b y) : InBox r (mul x y) := by
  simp only [check, valid, List.all_cons, List.all_nil, contains, le,
    Bool.and_eq_true, decide_eq_true_eq] at checked
  have alo : QPos a.lo := by simp_all [QPos]
  have ahi : QPos a.hi := by simp_all [QPos]
  have blo : QPos b.lo := by simp_all [QPos]
  have bhi : QPos b.hi := by simp_all [QPos]
  have low : InBox r (mul x b.lo) := by
    apply fixed_mul_enclosure a r x b.lo alo ahi blo hx <;> simp_all [QLe]
  have high : InBox r (mul x b.hi) := by
    apply fixed_mul_enclosure a r x b.hi alo ahi bhi hx <;> simp_all [QLe]
  rcases hx with ⟨xp, xl, xu⟩
  rcases hy with ⟨yp, yl, yu⟩
  by_cases hn : 0 ≤ x.n
  · have lower : QLe (mul x b.lo) (mul x y) := by
      simpa only [mul_comm] using qle_mul_nonneg (c := x) yl hn
    have upper : QLe (mul x y) (mul x b.hi) := by
      simpa only [mul_comm] using qle_mul_nonneg (c := x) yu hn
    exact ⟨mul_positive xp yp, qle_trans low.1 low.2.1 lower,
      qle_trans high.1 upper high.2.2⟩
  · have hn' : x.n ≤ 0 := by omega
    have lower : QLe (mul x b.hi) (mul x y) := by
      simpa only [mul_comm] using qle_mul_nonpos (c := x) yu hn'
    have upper : QLe (mul x y) (mul x b.lo) := by
      simpa only [mul_comm] using qle_mul_nonpos (c := x) yl hn'
    exact ⟨mul_positive xp yp, qle_trans high.1 high.2.1 lower,
      qle_trans low.1 upper low.2.2⟩

theorem check_constant_sound (a b r : Box) (q : Q)
    (checked : check ⟨.constant q, a, b, r⟩ = true) : InBox r q := by
  simp only [check, valid, singleton, eq, le, Bool.and_eq_true,
    decide_eq_true_eq, beq_iff_eq] at checked
  constructor
  · simp_all [QPos]
  · constructor <;> simp_all [QLe] <;> omega

theorem checked_positive_sound (b : Box) (x : Q)
    (checked : valid b && lt zero b.lo = true) (hx : InBox b x) :
    QPos x ∧ 0 < x.n := by
  simp only [valid, lt, le, zero, Bool.and_eq_true, decide_eq_true_eq,
    Int.zero_mul] at checked
  rcases hx with ⟨xp, xl, xu⟩
  have lop : (0 : Int) < b.lo.n := by simp_all
  have xdp : (0 : Int) < x.d := by exact_mod_cast xp
  have product_pos := Int.mul_pos lop xdp
  have rhs_pos : 0 < x.n * (b.lo.d : Int) := by
    simp only [QLe] at xl
    omega
  constructor
  · exact xp
  · by_cases h : 0 < x.n
    · exact h
    · have hn : x.n ≤ 0 := by omega
      have bad := Int.mul_nonpos_of_nonpos_of_nonneg hn (Int.natCast_nonneg b.lo.d)
      omega

end Composed
