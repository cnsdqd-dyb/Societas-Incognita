"""Emit dependency-preserving, kernel-checked rational DAG witnesses.

Hash-consing shares only identical operations, operand identities and boxes.
Physical lowering from the world interpreter is still a separate obligation.
"""
from pathlib import Path


def fragment(circuit, box_ref, qsource):
    # These witnesses are logical certificates, never executable runtime data.
    # Disable code generation, retaining elaboration and full kernel checking.
    # Otherwise the compiler can expand large exact-rational witness programs.
    lines=['noncomputable section', Path(__file__).with_name('graph_soundness.lean').read_text('utf-8').removeprefix('import Std\n'),
           'open Composed', 'def graphSeedBox : Box := ⟨zero,zero⟩',
           'def graphSeedValue : Q := zero',
           'theorem graphSeedEnclosed : InBox graphSeedBox graphSeedValue := by decide']
    # Check all closed arithmetic constraints before the dependent witness DAG.
    # This keeps reflection independent of the large witness environment while
    # retaining exactly the same equations, operand identities and enclosures.
    prelude_length = len(lines)
    constraint_lines = []
    canonical={}; originals={}; constraints={}; records=[]; seen={}
    for position,(op,a,b,w,constant) in enumerate(circuit.nodes):
        if w.index != position:
            raise ValueError('Graph output identity does not match node position')
        for operand in (a,b):
            if operand is not None and (operand.index not in seen or seen[operand.index] is not operand):
                raise ValueError('Graph operand is forward, missing or a counterfeit wire')
        seen[w.index]=w
        left=originals[a.index] if a is not None else None
        right=originals[b.index] if b is not None else None
        key=(op,left,right,constant,w.lo,w.hi)
        if key in canonical:
            originals[w.index]=canonical[key]
            continue
        index=len(records); canonical[key]=index; originals[w.index]=index
        operator=f'(.constant {qsource(constant)})' if op=='constant' else '.'+op
        abox=box_ref(a) if a is not None else 'graphSeedBox'
        bbox=box_ref(b) if b is not None else 'graphSeedBox'
        rbox=box_ref(w)
        instruction=f'check ⟨{operator}, {abox}, {bbox}, {rbox}⟩'
        if instruction not in constraints:
            checked='graphConstraint'+str(len(constraints))
            constraints[instruction]=checked
            constraint_lines.append(f'theorem {checked} : {instruction} = true := by decide')
        checked=constraints[instruction]
        av=f'actual{left}' if left is not None else 'graphSeedValue'
        bv=f'actual{right}' if right is not None else 'graphSeedValue'
        ah=f'enclosed{left}' if left is not None else 'graphSeedEnclosed'
        bh=f'enclosed{right}' if right is not None else 'graphSeedEnclosed'
        # An opaque, kernel-checked dependent witness prevents elaboration from
        # eagerly evaluating enormous exact rationals in nonlinear recurrences.
        # Its type exposes BOTH enclosure and the exact defining equation.
        value=f'evalOp {operator} {av} {bv}'
        enclosure=f'check_sound {operator} {abox} {bbox} {rbox} {av} {bv} {checked} {ah} {bh}'
        lines.append(f'opaque witness{index} : {{q : Q // InBox {rbox} q ∧ q = {value}}} := '
                     f'⟨{value}, ⟨{enclosure}, rfl⟩⟩')
        lines.append(f'def actual{index} : Q := witness{index}.val')
        lines.append(f'theorem enclosed{index} : InBox {rbox} actual{index} := witness{index}.property.1')
        lines.append(f'theorem equation{index} : actual{index} = {value} := witness{index}.property.2')
        records.append({'id':index,'op':op,'left':left,'right':right,'wire':w.index})
    alive=[]
    for w in circuit.live:
        index=originals[w.index]
        if index in alive: continue
        alive.append(index)
        lines.append(f'theorem actualAlive{index} : QPos actual{index} ∧ 0 < actual{index}.n := '
                     f'checked_positive_sound {box_ref(w)} actual{index} (by decide) enclosed{index}')
    guards=[]
    for w in circuit.guards:
        index=originals[w.index]
        if index in guards: continue
        guards.append(index)
        box=box_ref(w)
        lines.append(f'theorem actualGuard{index} : QEq actual{index} one := '
                     f'singleton_value {box} actual{index} one (by decide) (by decide) enclosed{index} (by decide)')
    if alive:
        claim=' ∧ '.join(f'(QPos actual{i} ∧ 0 < actual{i}.n)' for i in alive)
        term=f'actualAlive{alive[-1]}'
        for i in reversed(alive[:-1]): term=f'⟨actualAlive{i}, {term}⟩'
        lines.append('def semanticSurvival : Prop := '+claim)
        lines.append('theorem certified_semantic_survival : semanticSurvival := '+term)
        trace=', '.join(f'actual{originals[w.index]}' for w in circuit.live)
        lines.append('def actualVitalityTrace : List Q := ['+trace+']')
        lines.append(f'theorem certified_semantic_population_time : actualVitalityTrace.length = {len(circuit.live)} := by decide')
    lines[prelude_length:prelude_length] = constraint_lines
    lines.append('end')
    return '\n'.join(lines),{
        'graph_nodes':len(records),'original_graph_nodes':len(circuit.nodes),
        'graph_constraints':len(constraints),'semantic_live_outputs':len(circuit.live),
        'unique_semantic_live_outputs':len(alive),'semantic_guard_outputs':len(guards),
        'graph_semantics':'kernel_checked_dependency_preserving_rational_DAG',
        'graph_records':records}
