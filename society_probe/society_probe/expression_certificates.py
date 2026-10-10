"""Bind actual Compiler.expr lowering to a universally proved Lean lowering.

This verifies normalized expression structure, not the JSON parser, primitive
interval soundness, state transition adapter, or IEEE arithmetic equivalence.
"""
import hashlib
import json
from fractions import Fraction
from pathlib import Path

from composed_certificates import Compiler, Unsupported


def lit(value):
    q = Fraction(str(value))
    return f'(.lit ({q.numerator}) {q.denominator})'


def binary(op, a, b):
    return f'(.binary .{op} {a} {b})'


def normalized_source(e):
    if type(e) in (int, float):
        return lit(e)
    if 'ref' in e:
        return '(.var ' + json.dumps(e['ref']) + ')'
    op = e['op']; args = [normalized_source(a) for a in e['args']]
    if op in ('add', 'mul', 'min', 'max', 'and', 'or'):
        if op in ('and', 'or'):
            args = [f'(.truth {a})' for a in args]
            op = 'min' if op == 'and' else 'max'
        out = args[0]
        for a in args[1:]:
            out = binary(op, out, a)
        return out
    if op in ('sub', 'div', 'lt', 'le', 'eq'):
        return binary(op, *args)
    if op in ('gt', 'ge', 'clamp', 'not'):
        return f'(.{op} ' + ' '.join(args) + ')'
    if op == 'pow':
        return f'(.power {args[0]} {e["args"][1]})'
    raise Unsupported('Expression structural certificate does not support ' + op)


class Symbol:
    def __init__(self, term): self.term = term


class SymbolicCircuit:
    def __init__(self): self.guards = []
    def const(self, value): return Symbol(lit(value))
    def op(self, op, a, b=None):
        if not isinstance(a, Symbol): a = self.const(a)
        if b is not None and not isinstance(b, Symbol): b = self.const(b)
        if op == 'truth': return Symbol(f'(.truth {a.term})')
        return Symbol(binary(op, a.term, b.term))
    def require(self, a, message): self.guards.append((a.term, message))
    def clip(self, a, lo, hi): return self.op('min', hi, self.op('max', lo, a))


def actual_lowering(e):
    # Invoke the SAME method used by interval trajectory compilation. No second
    # Python implementation of gt/ge/power/clamp lowering is trusted here.
    compiler = object.__new__(Compiler)
    compiler.c = SymbolicCircuit()
    refs = set()
    def visit(x):
        if isinstance(x, dict):
            if 'ref' in x: refs.add(x['ref'])
            for v in x.values(): visit(v)
        elif isinstance(x, list):
            for v in x: visit(v)
    visit(e)
    ctx = {name: Symbol('(.var ' + json.dumps(name) + ')') for name in refs}
    term = compiler.expr(e, ctx).term
    return term, compiler.c.guards


def expressions(definition):
    found = {}
    def visit(x):
        if isinstance(x, dict):
            if set(x) == {'ref'} or set(x) == {'op', 'args'}:
                found[json.dumps(x, sort_keys=True)] = x
            for v in x.values(): visit(v)
        elif isinstance(x, list):
            for v in x: visit(v)
    visit(definition)
    return list(found.values())


def export(definition, path, equations=None):
    equations = expressions(definition) if equations is None else equations
    lines = [Path(__file__).with_name('expression_compiler.lean').read_text('utf-8'),
             'open WorldExpression', 'set_option maxRecDepth 100000',
             'set_option maxHeartbeats 0']
    guard_count = 0
    for i, e in enumerate(equations):
        target, guards = actual_lowering(e); guard_count += len(guards)
        lines += [f'def source{i} : Expr := {normalized_source(e)}',
                  f'def target{i} : Term := {target}',
                  f'theorem structure{i} : target{i} = lower source{i} := by decide',
                  f'theorem semantics{i} (s : Algebra V) (env : String → V) :',
                  f'  evalTerm s env target{i} = evalExpr s env source{i} :=',
                  f'  checked_compilation_correct s env source{i} target{i} structure{i}']
    data = '\n'.join(lines) + '\n'
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding='utf-8')
    return {'source': str(path.resolve()), 'sha256': hashlib.sha256(data.encode()).hexdigest(),
            'world_sha256': hashlib.sha256(json.dumps(definition, sort_keys=True).encode()).hexdigest(),
            'expression_count': len(equations), 'guard_count': guard_count,
            'status': 'exported_not_checked',
            'scope': 'Normalized expression lowering only. JSON normalization, primitive semantics, guards and whole-world transitions are outside this theorem.'}


def check(artifact):
    from survival_certificates import check_lean
    result = check_lean(artifact)
    if result['status'] == 'lean_checked_restricted_projection':
        result['status'] = 'lean_checked_expression_compilation'
    return result
