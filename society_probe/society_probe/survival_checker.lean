import Std

-- Small deterministic physical checker. A false transition returns none.
structure Member where
  stock : Nat
  vitality : Nat
  inventory : List Nat
  deriving DecidableEq, Repr

structure Physical where
  members : List Member
  pools : List Nat
  reserve : Nat
  deriving DecidableEq, Repr

structure World where
  densities : List Nat
  capacity : List Nat
  regeneration : List Nat
  reserveCapacity : Nat
  externalInput : Nat
  consumption : Nat
  pressure : Bool

inductive Action where
  | idle
  | gather (item amount : Nat)
  | convert (item amount : Nat)
  deriving DecidableEq, Repr

abbrev Joint := List (Nat × Action)

def applyAction (w : World) (s : Physical) (aid : Nat) (action : Action) : Option Physical := do
  let m ← s.members[aid]?
  if m.vitality == 0 then none else
    match action with
    | .idle => some s
    | .gather item amount => do
      let available ← s.pools[item]?
      let held ← m.inventory[item]?
      let removed := min amount available
      let changed := { m with inventory := m.inventory.set item (held + removed) }
      some { s with members := s.members.set aid changed, pools := s.pools.set item (available - removed) }
    | .convert item amount => do
      let held ← m.inventory[item]?
      let value ← w.densities[item]?
      if amount > held then none else do
        let changed := { m with stock := m.stock + amount * value, inventory := m.inventory.set item (held - amount) }
        some { s with members := s.members.set aid changed }

def applyJoint (w : World) (s : Physical) : Joint → Option Physical
  | [] => some s
  | (aid, action) :: rest => do
    let next ← applyAction w s aid action
    applyJoint w next rest

def maintain (w : World) (m : Member) : Member :=
  if !w.pressure || m.vitality == 0 then m else
    let paid := min w.consumption m.stock
    let vitality := if paid == w.consumption then min 5 (m.vitality + 1) else m.vitality - 1
    { m with stock := m.stock - paid, vitality := vitality }

def settle (w : World) (s : Physical) : Option Physical := do
  let increments := List.zipWith (fun (pair : Nat × Nat) (rate : Nat) => min rate (pair.2 - pair.1))
    (s.pools.zip w.capacity) w.regeneration
  let required := (List.zipWith (fun (n value : Nat) => n * value) increments w.densities).foldl (· + ·) 0
  let available := min w.reserveCapacity (s.reserve + w.externalInput)
  if required > available then none else
    some { members := s.members.map (maintain w),
           pools := List.zipWith (· + ·) s.pools increments, reserve := available - required }

def roundStep (w : World) (s : Physical) (joint : Joint) : Option Physical := do
  if joint.map Prod.fst != List.range s.members.length then none else
    let acted ← applyJoint w s joint
    settle w acted

def runPlan (w : World) (s : Physical) : List Joint → Option (List Physical)
  | [] => some []
  | joint :: rest => do
    let next ← roundStep w s joint
    let later ← runPlan w next rest
    some (next :: later)

def survives (w : World) (s : Physical) (plan : List Joint) : Bool :=
  match runPlan w s plan with
  | none => false
  | some states => states.all (fun state => state.members.all (fun m => m.vitality > 0))

def survivalScore (w : World) (s : Physical) (plan : List Joint) : Option Nat := do
  let states ← runPlan w s plan
  some ((states.map (fun state => (state.members.filter (fun m => m.vitality > 0)).length)).foldl (· + ·) 0)
