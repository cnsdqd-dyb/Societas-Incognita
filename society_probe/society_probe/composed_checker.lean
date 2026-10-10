import Std

namespace Composed

-- Untrusted numeric witnesses. Denominator positivity is checked, never assumed.
structure Q where
  n : Int
  d : Nat
  deriving Repr
structure Box where
  lo : Q
  hi : Q
  deriving Repr
def le (a b : Q) : Bool := a.n * b.d ≤ b.n * a.d
def lt (a b : Q) : Bool := a.n * b.d < b.n * a.d
def eq (a b : Q) : Bool := a.n * b.d == b.n * a.d
def zero : Q := ⟨0, 1⟩
def one : Q := ⟨1, 1⟩
def add (a b : Q) : Q := ⟨a.n * b.d + b.n * a.d, a.d * b.d⟩
def neg (a : Q) : Q := ⟨-a.n, a.d⟩
def sub (a b : Q) : Q := add a (neg b)
def mul (a b : Q) : Q := ⟨a.n * b.n, a.d * b.d⟩
def div (a b : Q) : Q :=
  if b.n < 0 then ⟨-a.n * b.d, a.d * b.n.natAbs⟩
  else ⟨a.n * b.d, a.d * b.n.natAbs⟩
def valid (a : Box) : Bool := a.lo.d > 0 && a.hi.d > 0 && le a.lo a.hi
def contains (r : Box) (a : Q) : Bool := le r.lo a && le a r.hi
def singleton (r : Box) (a : Q) : Bool := eq r.lo a && eq r.hi a

inductive Op where
  | constant (q : Q)
  | add | sub | mul | div | min | max | floor | lt | le | eq | truth | neg
  deriving Repr
structure Constraint where
  op : Op
  a : Box
  b : Box
  result : Box
  deriving Repr

def check (c : Constraint) : Bool :=
  valid c.a && valid c.b && valid c.result &&
  match c.op with
  | .constant q => q.d > 0 && singleton c.result q
  | .add => le c.result.lo (add c.a.lo c.b.lo) && le (add c.a.hi c.b.hi) c.result.hi
  | .sub => le c.result.lo (sub c.a.lo c.b.hi) && le (sub c.a.hi c.b.lo) c.result.hi
  | .neg => le c.result.lo (neg c.a.hi) && le (neg c.a.lo) c.result.hi
  | .mul => [mul c.a.lo c.b.lo, mul c.a.lo c.b.hi, mul c.a.hi c.b.lo, mul c.a.hi c.b.hi].all (contains c.result)
  | .div => (lt c.b.hi zero || lt zero c.b.lo) &&
      [div c.a.lo c.b.lo, div c.a.lo c.b.hi, div c.a.hi c.b.lo, div c.a.hi c.b.hi].all (contains c.result)
  | .min => le c.result.lo (if le c.a.lo c.b.lo then c.a.lo else c.b.lo) &&
      le (if le c.a.hi c.b.hi then c.a.hi else c.b.hi) c.result.hi
  | .max => le c.result.lo (if le c.a.lo c.b.lo then c.b.lo else c.a.lo) &&
      le (if le c.a.hi c.b.hi then c.b.hi else c.a.hi) c.result.hi
  | .floor => singleton c.result ⟨c.a.lo.n / (Int.ofNat c.a.lo.d), 1⟩ &&
      c.a.lo.n / (Int.ofNat c.a.lo.d) == c.a.hi.n / (Int.ofNat c.a.hi.d)
  | .lt => (lt c.a.hi c.b.lo && singleton c.result one) ||
      (le c.b.hi c.a.lo && singleton c.result zero)
  | .le => (le c.a.hi c.b.lo && singleton c.result one) ||
      (lt c.b.hi c.a.lo && singleton c.result zero)
  | .eq => (eq c.a.lo c.a.hi && eq c.b.lo c.b.hi && eq c.a.lo c.b.lo && singleton c.result one) ||
      ((lt c.a.hi c.b.lo || lt c.b.hi c.a.lo) && singleton c.result zero)
  | .truth => ((lt c.a.hi zero || lt zero c.a.lo) && singleton c.result one) ||
      (singleton c.a zero && singleton c.result zero)

def checkBlock (cs : List Constraint) : Bool := cs.all check
def allPositive (states : List Box) : Bool := states.all (fun b => valid b && lt zero b.lo)
end Composed
