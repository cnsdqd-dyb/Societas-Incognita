import Std

namespace Composed

-- Newest node first. Edges are offsets into previously certified values.
structure GraphNode where
  op : Op
  left : Nat
  right : Nat
  output : Box
  deriving Repr

def Related (boxes : List Box) (values : List Q) : Prop :=
  ∀ (i : Nat) (b : Box), boxes[i]? = some b → ∃ x, values[i]? = some x ∧ InBox b x

theorem related_cons {bs : List Box} {vs : List Q} {b : Box} {x : Q}
    (h : Related bs vs) (hx : InBox b x) : Related (b :: bs) (x :: vs) := by
  intro i bb lookup
  cases i with
  | zero =>
    simp only [List.getElem?_cons_zero] at lookup
    cases lookup
    exact ⟨x, rfl, hx⟩
  | succ n =>
    simp only [List.getElem?_cons_succ] at lookup ⊢
    exact h n bb lookup

def checkGraph (boxes : List Box) : List GraphNode → Option (List Box)
  | [] => some boxes
  | n :: rest => match boxes[n.left]?, boxes[n.right]? with
    | some a, some b =>
      if check ⟨n.op, a, b, n.output⟩ then checkGraph (n.output :: boxes) rest else none
    | _, _ => none

def evalGraph (values : List Q) : List GraphNode → Option (List Q)
  | [] => some values
  | n :: rest => match values[n.left]?, values[n.right]? with
    | some x, some y => evalGraph (evalOp n.op x y :: values) rest
    | _, _ => none

theorem graph_sound (nodes : List GraphNode) (boxes : List Box) (values : List Q)
    (finalBoxes : List Box) (h : Related boxes values)
    (checked : checkGraph boxes nodes = some finalBoxes) :
    ∃ finalValues, evalGraph values nodes = some finalValues ∧ Related finalBoxes finalValues := by
  induction nodes generalizing boxes values finalBoxes with
  | nil =>
    simp only [checkGraph, Option.some.injEq] at checked
    subst finalBoxes
    exact ⟨values, rfl, h⟩
  | cons n rest ih =>
    cases ha : boxes[n.left]? with
    | none => simp [checkGraph, ha] at checked
    | some a =>
      cases hb : boxes[n.right]? with
      | none => simp [checkGraph, ha, hb] at checked
      | some b =>
        by_cases hc : check ⟨n.op, a, b, n.output⟩ = true
        · simp only [checkGraph, ha, hb, hc, ↓reduceIte] at checked
          obtain ⟨x, hxa, hxi⟩ := h n.left a ha
          obtain ⟨y, hyb, hyi⟩ := h n.right b hb
          have result := check_sound n.op a b n.output x y hc hxi hyi
          obtain ⟨fv, evaluated, enclosed⟩ := ih (n.output :: boxes)
            (evalOp n.op x y :: values) finalBoxes (related_cons h result) checked
          exact ⟨fv, by simp [evalGraph, hxa, hyb, evaluated], enclosed⟩
        · simp [checkGraph, ha, hb, hc] at checked

theorem graph_positive_output (nodes : List GraphNode) (boxes : List Box)
    (values : List Q) (finalBoxes : List Box) (index : Nat) (b : Box)
    (h : Related boxes values) (checked : checkGraph boxes nodes = some finalBoxes)
    (lookup : finalBoxes[index]? = some b) (positive : valid b && lt zero b.lo = true) :
    ∃ finalValues x, evalGraph values nodes = some finalValues ∧
      finalValues[index]? = some x ∧ QPos x ∧ 0 < x.n := by
  obtain ⟨fv, evaluated, enclosed⟩ := graph_sound nodes boxes values finalBoxes h checked
  obtain ⟨x, atIndex, inside⟩ := enclosed index b lookup
  have hp := checked_positive_sound b x positive inside
  exact ⟨fv, x, evaluated, atIndex, hp⟩

end Composed
