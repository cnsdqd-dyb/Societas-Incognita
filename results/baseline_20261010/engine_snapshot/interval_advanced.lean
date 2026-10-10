import Std

-- Concatenate after composed_checker.lean and interval_soundness.lean.
namespace Composed

def QLt (a b : Q) : Prop := a.n * (b.d : Int) < b.n * (a.d : Int)
def QEq (a b : Q) : Prop := a.n * (b.d : Int) = b.n * (a.d : Int)
instance (a b : Q) : Decidable (QLt a b) := inferInstanceAs (Decidable (a.n * (b.d : Int) < b.n * (a.d : Int)))
instance (a b : Q) : Decidable (QEq a b) := inferInstanceAs (Decidable (a.n * (b.d : Int) = b.n * (a.d : Int)))
def qbool (p : Bool) : Q := if p then one else zero
def qfloor (x : Q) : Q := ⟨x.n / (x.d : Int), 1⟩

theorem qle_lt_trans {a b c : Q} (ha : QPos a) (_hb : QPos b)
    (hab : QLe a b) (hbc : QLt b c) : QLt a c := by
  have ap : (0 : Int) < a.d := by exact_mod_cast ha
  have bp : (0 : Int) ≤ b.d := Int.natCast_nonneg _
  have h1 := Int.mul_le_mul_of_nonneg_right hab (Int.natCast_nonneg c.d)
  have h2 := Int.mul_lt_mul_of_pos_right hbc ap
  apply Int.lt_of_mul_lt_mul_right (a := (b.d : Int)) (h := bp)
  simp only [QLt] at hbc ⊢
  simp only [Int.mul_assoc, Int.mul_comm, Int.mul_left_comm] at h1 h2 ⊢
  omega

theorem qlt_le_trans {a b c : Q} (_hb : QPos b) (hc : QPos c)
    (hab : QLt a b) (hbc : QLe b c) : QLt a c := by
  have cp : (0 : Int) < c.d := by exact_mod_cast hc
  have h1 := Int.mul_lt_mul_of_pos_right hab cp
  have h2 := Int.mul_le_mul_of_nonneg_right hbc (Int.natCast_nonneg a.d)
  apply Int.lt_of_mul_lt_mul_right (a := (b.d : Int)) (h := Int.natCast_nonneg _)
  simp only [QLt] at hab ⊢
  simp only [Int.mul_assoc, Int.mul_comm, Int.mul_left_comm] at h1 h2 ⊢
  omega

theorem qeq_le {a b : Q} (h : QEq a b) : QLe a b := by simp_all [QEq, QLe]
theorem qeq_symm {a b : Q} (h : QEq a b) : QEq b a := by simp_all [QEq]
theorem qeq_of_le {a b : Q} (h1 : QLe a b) (h2 : QLe b a) : QEq a b := by
  simp only [QEq, QLe] at *; omega
theorem singleton_sound (r : Box) (x : Q) (hp : QPos x)
    (h : singleton r x = true) : InBox r x := by
  simp only [singleton, eq, Bool.and_eq_true, beq_iff_eq] at h
  exact ⟨hp, by simp_all [QLe], by simp_all [QLe]⟩

theorem floor_mono {a b : Q} (ha : QPos a) (hb : QPos b) (h : QLe a b) :
    a.n / (a.d : Int) ≤ b.n / (b.d : Int) := by
  have ap : (0 : Int) < a.d := by exact_mod_cast ha
  have bp : (0 : Int) < b.d := by exact_mod_cast hb
  have bound : QLe (qfloor a) a := by
    simpa [QLe, qfloor] using Int.ediv_mul_le a.n (by omega : (a.d : Int) ≠ 0)
  have next := qle_trans ha bound h
  apply Int.le_ediv_of_mul_le bp
  simpa [QLe, qfloor] using next

theorem check_floor_sound (a b r : Box) (x : Q)
    (checked : check ⟨.floor, a, b, r⟩ = true) (hx : InBox a x) :
    InBox r (qfloor x) := by
  have alo : QPos a.lo := by simp_all [check, valid, QPos]
  have ahi : QPos a.hi := by simp_all [check, valid, QPos]
  have same : a.lo.n / (a.lo.d : Int) = a.hi.n / (a.hi.d : Int) := by
    simp_all [check, valid, beq_iff_eq]
  have sl : singleton r (qfloor a.lo) = true := by simp_all [check, qfloor]
  have lower := floor_mono alo hx.1 hx.2.1
  have upper := floor_mono hx.1 ahi hx.2.2
  have samex : qfloor x = qfloor a.lo := by
    unfold qfloor; congr 1; omega
  rw [samex]
  exact singleton_sound r _ (by simp [QPos, qfloor]) sl

theorem separated_lt (a b : Box) (x y : Q)
    (hx : InBox a x) (hy : InBox b y)
    (ahi : QPos a.hi) (blo : QPos b.lo) (h : QLt a.hi b.lo) : QLt x y :=
  qlt_le_trans blo hy.1 (qle_lt_trans hx.1 ahi hx.2.2 h) hy.2.1

theorem separated_le (a b : Box) (x y : Q)
    (hx : InBox a x) (hy : InBox b y)
    (ahi : QPos a.hi) (blo : QPos b.lo) (h : QLe a.hi b.lo) : QLe x y :=
  qle_trans blo (qle_trans ahi hx.2.2 h) hy.2.1

theorem check_lt_sound (a b r : Box) (x y : Q)
    (checked : check ⟨.lt, a, b, r⟩ = true) (hx : InBox a x) (hy : InBox b y) :
    InBox r (qbool (lt x y)) := by
  have ahi : QPos a.hi := by simp_all [check, valid, QPos]
  have alo : QPos a.lo := by simp_all [check, valid, QPos]
  have bhi : QPos b.hi := by simp_all [check, valid, QPos]
  have blo : QPos b.lo := by simp_all [check, valid, QPos]
  have cases : (QLt a.hi b.lo ∧ singleton r one = true) ∨
      (QLe b.hi a.lo ∧ singleton r zero = true) := by
    simp_all [check, valid, lt, le, QLt, QLe]
  rcases cases with h | h
  · have hxy := separated_lt a b x y hx hy ahi blo h.1
    have flag : lt x y = true := by simpa [lt, QLt] using hxy
    simp only [qbool, flag] 
    exact singleton_sound r one (by decide) h.2
  · have hyx := separated_le b a y x hy hx bhi alo h.1
    have flag : lt x y = false := by simp [lt, QLe] at *; omega
    simp only [qbool, flag]
    exact singleton_sound r zero (by decide) h.2

theorem check_le_sound (a b r : Box) (x y : Q)
    (checked : check ⟨.le, a, b, r⟩ = true) (hx : InBox a x) (hy : InBox b y) :
    InBox r (qbool (le x y)) := by
  have ahi : QPos a.hi := by simp_all [check, valid, QPos]
  have alo : QPos a.lo := by simp_all [check, valid, QPos]
  have bhi : QPos b.hi := by simp_all [check, valid, QPos]
  have blo : QPos b.lo := by simp_all [check, valid, QPos]
  have cases : (QLe a.hi b.lo ∧ singleton r one = true) ∨
      (QLt b.hi a.lo ∧ singleton r zero = true) := by
    simp_all [check, valid, lt, le, QLt, QLe]
  rcases cases with h | h
  · have hxy := separated_le a b x y hx hy ahi blo h.1
    have flag : le x y = true := by simpa [le, QLe] using hxy
    simp only [qbool, flag]
    exact singleton_sound r one (by decide) h.2
  · have hyx := separated_lt b a y x hy hx bhi alo h.1
    have flag : le x y = false := by simp [le, QLt] at *; omega
    simp only [qbool, flag]
    exact singleton_sound r zero (by decide) h.2

theorem qeq_trans {a b c : Q} (hb : QPos b) (h1 : QEq a b) (h2 : QEq b c) : QEq a c :=
  qeq_of_le (qle_trans hb (qeq_le h1) (qeq_le h2))
    (qle_trans hb (qeq_le (qeq_symm h2)) (qeq_le (qeq_symm h1)))

theorem singleton_value (a : Box) (x v : Q) (alo : QPos a.lo) (ahi : QPos a.hi)
    (hx : InBox a x) (h : singleton a v = true) : QEq x v := by
  have h1 : QEq a.lo v := by simp_all [singleton, eq, QEq]
  have h2 : QEq a.hi v := by simp_all [singleton, eq, QEq]
  exact qeq_of_le (qle_trans ahi hx.2.2 (qeq_le h2))
    (qle_trans alo (qeq_le (qeq_symm h1)) hx.2.1)

theorem check_eq_sound (a b r : Box) (x y : Q)
    (checked : check ⟨.eq, a, b, r⟩ = true) (hx : InBox a x) (hy : InBox b y) :
    InBox r (qbool (eq x y)) := by
  have ahi : QPos a.hi := by simp_all [check, valid, QPos]
  have alo : QPos a.lo := by simp_all [check, valid, QPos]
  have bhi : QPos b.hi := by simp_all [check, valid, QPos]
  have blo : QPos b.lo := by simp_all [check, valid, QPos]
  have cases : (QEq a.lo a.hi ∧ QEq b.lo b.hi ∧ QEq a.lo b.lo ∧ singleton r one = true) ∨
      ((QLt a.hi b.lo ∨ QLt b.hi a.lo) ∧ singleton r zero = true) := by
    simp_all [check, valid, lt, le, eq, QLt, QEq, and_assoc]
  rcases cases with h | h
  · have sa : singleton a a.lo = true := by simp_all [singleton, eq, QEq]
    have sb : singleton b b.lo = true := by simp_all [singleton, eq, QEq]
    have xv := singleton_value a x a.lo alo ahi hx sa
    have yv := singleton_value b y b.lo blo bhi hy sb
    have xy := qeq_trans blo (qeq_trans alo xv h.2.2.1) (qeq_symm yv)
    have flag : eq x y = true := by simpa [eq, QEq] using xy
    simp only [qbool, flag]
    exact singleton_sound r one (by decide) h.2.2.2
  · have flag : eq x y = false := by
      rcases h.1 with sep | sep
      · have xy := separated_lt a b x y hx hy ahi blo sep
        simp [eq, QLt] at *; omega
      · have yx := separated_lt b a y x hy hx bhi alo sep
        simp [eq, QLt] at *; omega
    simp only [qbool, flag]
    exact singleton_sound r zero (by decide) h.2

def qtruth (x : Q) : Q := if x.n = 0 then zero else one

theorem check_truth_sound (a b r : Box) (x : Q)
    (checked : check ⟨.truth, a, b, r⟩ = true) (hx : InBox a x) :
    InBox r (qtruth x) := by
  have ahi : QPos a.hi := by simp_all [check, valid, QPos]
  have alo : QPos a.lo := by simp_all [check, valid, QPos]
  have cases : ((QLt a.hi zero ∨ QLt zero a.lo) ∧ singleton r one = true) ∨
      (singleton a zero = true ∧ singleton r zero = true) := by
    simp_all [check, valid, lt, le, QLt, QLe]
  rcases cases with h | h
  · have hn : x.n ≠ 0 := by
      rcases h.1 with below | above
      · have bound := qle_lt_trans hx.1 ahi hx.2.2 below
        simp [QLt, zero] at bound; omega
      · have bound := qlt_le_trans alo hx.1 above hx.2.1
        simp [QLt, zero] at bound; omega
    simp only [qtruth, hn, ↓reduceIte]
    exact singleton_sound r one (by decide) h.2
  · have value := singleton_value a x zero alo ahi hx h.1
    have hn : x.n = 0 := by simpa [QEq, zero] using value
    simp only [qtruth, hn, ↓reduceIte]
    exact singleton_sound r zero (by decide) h.2

def recip (q : Q) : Q :=
  if q.n < 0 then ⟨-(q.d : Int), q.n.natAbs⟩ else ⟨q.d, q.n.natAbs⟩

theorem recip_positive {q : Q} (h : q.n ≠ 0) : QPos (recip q) := by
  unfold QPos recip; split <;> exact Int.natAbs_pos.mpr h

theorem div_as_mul (a b : Q) : div a b = mul a (recip b) := by
  unfold div recip mul; split <;> simp_all [Int.mul_neg, Int.neg_mul]

theorem recip_antitone_pos (a b : Q) (ha : 0 < a.n) (hb : 0 < b.n)
    (h : QLe a b) : QLe (recip b) (recip a) := by
  have an := Int.natAbs_of_nonneg (by omega : 0 ≤ a.n)
  have bn := Int.natAbs_of_nonneg (by omega : 0 ≤ b.n)
  have ra : recip a = ⟨a.d, a.n.natAbs⟩ := by
    unfold recip; exact if_neg (by omega)
  have rb : recip b = ⟨b.d, b.n.natAbs⟩ := by
    unfold recip; exact if_neg (by omega)
  rw [ra, rb]
  change (b.d : Int) * (a.n.natAbs : Int) ≤ (a.d : Int) * (b.n.natAbs : Int)
  rw [an, bn]
  simp only [QLe] at h
  simpa only [Int.mul_comm] using h

theorem recip_antitone_neg (a b : Q) (ha : a.n < 0) (hb : b.n < 0)
    (h : QLe a b) : QLe (recip b) (recip a) := by
  have an := Int.ofNat_natAbs_of_nonpos (by omega : a.n ≤ 0)
  have bn := Int.ofNat_natAbs_of_nonpos (by omega : b.n ≤ 0)
  simp only [QLe] at h
  simpa [QLe, recip, ha, hb, an, bn, Int.mul_comm, Int.neg_mul, Int.mul_neg] using h

theorem inverse_box_sound (b : Box) (y : Q) (hy : InBox b y)
    (bp : QPos b.lo) (bq : QPos b.hi)
    (side : QLt b.hi zero ∨ QLt zero b.lo) :
    InBox ⟨recip b.hi, recip b.lo⟩ (recip y) := by
  rcases side with negative | positive
  · have hn : b.hi.n < 0 := by simpa [QLt, zero] using negative
    have yn : y.n < 0 := by
      have h := qle_lt_trans hy.1 bq hy.2.2 negative
      simpa [QLt, zero] using h
    have ln : b.lo.n < 0 := by
      have h := qle_lt_trans bp hy.1 hy.2.1 (show QLt y zero from by simpa [QLt, zero] using yn)
      simpa [QLt, zero] using h
    exact ⟨recip_positive (by omega),
      recip_antitone_neg y b.hi yn hn hy.2.2,
      recip_antitone_neg b.lo y ln yn hy.2.1⟩
  · have ln : 0 < b.lo.n := by simpa [QLt, zero] using positive
    have yn : 0 < y.n := by
      have h := qlt_le_trans bp hy.1 positive hy.2.1
      simpa [QLt, zero] using h
    have hn : 0 < b.hi.n := by
      have h := qlt_le_trans hy.1 bq (show QLt zero y from by simpa [QLt, zero] using yn) hy.2.2
      simpa [QLt, zero] using h
    exact ⟨recip_positive (by omega),
      recip_antitone_pos y b.hi yn hn hy.2.2,
      recip_antitone_pos b.lo y ln yn hy.2.1⟩

theorem check_div_sound (a b r : Box) (x y : Q)
    (checked : check ⟨.div, a, b, r⟩ = true) (hx : InBox a x) (hy : InBox b y) :
    InBox r (div x y) := by
  have bp : QPos b.lo := by simp_all [check, valid, QPos]
  have bq : QPos b.hi := by simp_all [check, valid, QPos]
  have bbound : QLe b.lo b.hi := by simp_all [check, valid, QLe, le]
  have side : QLt b.hi zero ∨ QLt zero b.lo := by simp_all [check, valid, QLt, lt]
  have inverse := inverse_box_sound b y hy bp bq side
  have ln : b.lo.n ≠ 0 := by
    rcases side with h | h
    · have neg := qle_lt_trans bp bq bbound h
      simp [QLt, zero] at neg; omega
    · simp [QLt, zero] at h; omega
  have hn : b.hi.n ≠ 0 := by
    rcases side with h | h
    · simp [QLt, zero] at h; omega
    · have pos := qlt_le_trans bp bq h bbound
      simp [QLt, zero] at pos; omega
  have invbound : QLe (recip b.hi) (recip b.lo) := by
    rcases side with h | h
    · have low := qle_lt_trans bp bq bbound h
      apply recip_antitone_neg b.lo b.hi <;> simp_all [QLt, zero]
    · have high := qlt_le_trans bp bq h bbound
      apply recip_antitone_pos b.lo b.hi <;> simp_all [QLt, zero]
  have iv : valid ⟨recip b.hi, recip b.lo⟩ = true := by
    have h1 := recip_positive ln
    have h2 := recip_positive hn
    simp_all [valid, QPos, QLe, le]
  have mc : check ⟨.mul, a, ⟨recip b.hi, recip b.lo⟩, r⟩ = true := by
    simp_all [check, div_as_mul, List.all_cons, List.all_nil, and_assoc]
  rw [div_as_mul]
  exact check_mul_sound a _ r x _ mc hx inverse

def evalOp : Op → Q → Q → Q
  | .constant q, _, _ => q
  | .add, x, y => add x y
  | .sub, x, y => sub x y
  | .mul, x, y => mul x y
  | .div, x, y => div x y
  | .min, x, y => qmin x y
  | .max, x, y => qmax x y
  | .floor, x, _ => qfloor x
  | .lt, x, y => qbool (lt x y)
  | .le, x, y => qbool (le x y)
  | .eq, x, y => qbool (eq x y)
  | .truth, x, _ => qtruth x
  | .neg, x, _ => neg x

theorem check_sound (op : Op) (a b r : Box) (x y : Q)
    (checked : check ⟨op, a, b, r⟩ = true) (hx : InBox a x) (hy : InBox b y) :
    InBox r (evalOp op x y) := by
  cases op with
  | constant q => exact check_constant_sound a b r q checked
  | add => exact check_add_sound a b r x y checked hx hy
  | sub => exact check_sub_sound a b r x y checked hx hy
  | mul => exact check_mul_sound a b r x y checked hx hy
  | div => exact check_div_sound a b r x y checked hx hy
  | min => exact check_min_sound a b r x y checked hx hy
  | max => exact check_max_sound a b r x y checked hx hy
  | floor => exact check_floor_sound a b r x checked hx
  | lt => exact check_lt_sound a b r x y checked hx hy
  | le => exact check_le_sound a b r x y checked hx hy
  | eq => exact check_eq_sound a b r x y checked hx hy
  | truth => exact check_truth_sound a b r x checked hx
  | neg => exact check_neg_sound a b r x checked hx

end Composed
