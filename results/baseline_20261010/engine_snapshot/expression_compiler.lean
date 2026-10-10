import Std

namespace WorldExpression

-- Parameterized semantics: correctness does not depend on particular numeric inputs.
structure Algebra (V : Type) where
  literal : Int → Nat → V
  add : V → V → V
  sub : V → V → V
  mul : V → V → V
  div : V → V → V
  min : V → V → V
  max : V → V → V
  lt : V → V → V
  le : V → V → V
  eq : V → V → V
  truth : V → V

inductive Bin where
  | add | sub | mul | div | min | max | lt | le | eq | and | or
  deriving BEq, DecidableEq
inductive Expr where
  | lit (n : Int) (d : Nat)
  | var (name : String)
  | binary (op : Bin) (a b : Expr)
  | gt (a b : Expr)
  | ge (a b : Expr)
  | clamp (a lo hi : Expr)
  | not (a : Expr)
  | truth (a : Expr)
  | power (a : Expr) (n : Nat)
  deriving BEq, DecidableEq
inductive Term where
  | lit (n : Int) (d : Nat)
  | var (name : String)
  | binary (op : Bin) (a b : Term)
  | truth (a : Term)
  deriving BEq, DecidableEq

def binary (s : Algebra V) : Bin → V → V → V
  | .add => s.add | .sub => s.sub | .mul => s.mul | .div => s.div
  | .min => s.min | .max => s.max | .lt => s.lt | .le => s.le | .eq => s.eq
  | .and => fun a b => s.min (s.truth a) (s.truth b)
  | .or => fun a b => s.max (s.truth a) (s.truth b)

def repeated (s : Algebra V) (a : V) : Nat → V
  | 0 => s.literal 1 1
  | n+1 => s.mul (repeated s a n) a
def repeatTerm (a : Term) : Nat → Term
  | 0 => .lit 1 1
  | n+1 => .binary .mul (repeatTerm a n) a
def evalTerm (s : Algebra V) (env : String → V) : Term → V
  | .lit n d => s.literal n d
  | .var x => env x
  | .binary op a b => binary s op (evalTerm s env a) (evalTerm s env b)
  | .truth a => s.truth (evalTerm s env a)
def evalExpr (s : Algebra V) (env : String → V) : Expr → V
  | .lit n d => s.literal n d
  | .var x => env x
  | .binary op a b => binary s op (evalExpr s env a) (evalExpr s env b)
  | .gt a b => s.lt (evalExpr s env b) (evalExpr s env a)
  | .ge a b => s.le (evalExpr s env b) (evalExpr s env a)
  | .clamp a lo hi => s.min (evalExpr s env hi) (s.max (evalExpr s env lo) (evalExpr s env a))
  | .not a => s.sub (s.literal 1 1) (s.truth (evalExpr s env a))
  | .truth a => s.truth (evalExpr s env a)
  | .power a n => repeated s (evalExpr s env a) n
def lower : Expr → Term
  | .lit n d => .lit n d
  | .var x => .var x
  | .binary op a b => match op with
    | .and => .binary .min (.truth (lower a)) (.truth (lower b))
    | .or => .binary .max (.truth (lower a)) (.truth (lower b))
    | other => .binary other (lower a) (lower b)
  | .gt a b => .binary .lt (lower b) (lower a)
  | .ge a b => .binary .le (lower b) (lower a)
  | .clamp a lo hi => .binary .min (lower hi) (.binary .max (lower lo) (lower a))
  | .not a => .binary .sub (.lit 1 1) (.truth (lower a))
  | .truth a => .truth (lower a)
  | .power a n => repeatTerm (lower a) n

theorem repeat_correct (s : Algebra V) (env : String → V) (a : Term) (n : Nat) :
    evalTerm s env (repeatTerm a n) = repeated s (evalTerm s env a) n := by
  induction n with
  | zero => rfl
  | succ n ih => simp [repeatTerm, evalTerm, binary, repeated, ih]

theorem compile_correct (s : Algebra V) (env : String → V) (e : Expr) :
    evalTerm s env (lower e) = evalExpr s env e := by
  induction e with
  | lit n d => rfl
  | var x => rfl
  | binary op a b ia ib => cases op <;> simp [lower, evalTerm, evalExpr, binary, ia, ib]
  | gt a b ia ib => simp [lower, evalTerm, evalExpr, binary, ia, ib]
  | ge a b ia ib => simp [lower, evalTerm, evalExpr, binary, ia, ib]
  | clamp a lo hi ia il ih => simp [lower, evalTerm, evalExpr, binary, ia, il, ih]
  | not a ia => simp [lower, evalTerm, evalExpr, binary, ia]
  | truth a ia => simp [lower, evalTerm, evalExpr, ia]
  | power a n ia => simp [lower, evalExpr, repeat_correct, ia]

theorem checked_compilation_correct (s : Algebra V) (env : String → V)
    (e : Expr) (t : Term) (checked : t = lower e) :
    evalTerm s env t = evalExpr s env e := by
  rw [checked]
  exact compile_correct s env e
end WorldExpression
