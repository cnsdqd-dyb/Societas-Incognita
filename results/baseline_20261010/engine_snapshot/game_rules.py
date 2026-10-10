"""Bounded Python/XML game rules interpreted as data; never execute host Python."""
import ast
import copy
import json
import operator
import random
import xml.etree.ElementTree as ET

MAX_SOURCE=12000
MAX_STEPS=10000


def bounded(value):
    encoded=json.dumps(value,ensure_ascii=False,allow_nan=False)
    if len(encoded)>16000:
        raise ValueError('Game value exceeds size bound')
    def check(v,depth=0):
        if depth>12:raise ValueError('Game nesting too deep')
        if type(v) in (int,float) and abs(v)>10**12:raise ValueError('Game numeric bound exceeded')
        if isinstance(v,(list,dict)):
            if len(v)>256:raise ValueError('Game container too large')
            for x in (v.values() if isinstance(v,dict) else v):check(x,depth+1)
        elif not isinstance(v,(str,int,float,bool,type(None))):raise ValueError('Non-data game value')
    check(value)
    return value


ALLOWED=(ast.Module,ast.FunctionDef,ast.arguments,ast.arg,ast.Assign,ast.AugAssign,
    ast.Return,ast.If,ast.For,ast.Break,ast.Continue,ast.Pass,ast.Expr,
    ast.Name,ast.Constant,ast.Dict,ast.List,ast.Tuple,ast.Subscript,ast.Slice,
    ast.Load,ast.Store,ast.BinOp,ast.UnaryOp,ast.BoolOp,ast.Compare,ast.IfExp,
    ast.Call,ast.Attribute,ast.keyword,ast.Add,ast.Sub,ast.Mult,ast.Div,ast.FloorDiv,
    ast.Mod,ast.Pow,ast.USub,ast.UAdd,ast.Not,ast.And,ast.Or,ast.Eq,ast.NotEq,
    ast.Lt,ast.LtE,ast.Gt,ast.GtE,ast.In,ast.NotIn,ast.Is,ast.IsNot)


def validate_tree(tree):
    nodes=list(ast.walk(tree))
    if len(nodes)>1800:raise ValueError('Game program too large')
    for n in nodes:
        if not isinstance(n,ALLOWED):raise ValueError('Unsupported game syntax: '+type(n).__name__)
        if isinstance(n,ast.Name) and n.id.startswith('_'):raise ValueError('Private names unavailable')
        if isinstance(n,ast.Attribute) and n.attr not in ('get','append','pop','keys','values'):
            raise ValueError('Only explicit data-container methods are available')
        if isinstance(n,ast.Call) and (any(k.arg is None for k in n.keywords) or any(isinstance(a,ast.Starred) for a in n.args)):
            raise ValueError('Argument expansion unavailable')


def parse(source,kind,max_source=MAX_SOURCE):
    if type(max_source) is not int or not 1 <= max_source <= 100000:
        raise ValueError('Invalid game source capacity')
    if not isinstance(source,str) or not 0<len(source)<=max_source:
        raise ValueError('Invalid game source length')
    if kind=='game_xml':
        if '<!' in source:raise ValueError('XML entities and declarations unavailable')
        try:root=ET.fromstring(source)
        except ET.ParseError as exc:raise ValueError('Invalid game XML') from exc
        if root.tag!='game' or any(c.tag not in ('description','initial','legal','update','done','winner') for c in root):
            raise ValueError('Unsupported game XML element')
        try:initial=json.loads(root.findtext('initial','{}'))
        except json.JSONDecodeError as exc:raise ValueError('Invalid XML initial state') from exc
        rules={k:int(root.attrib.get(k,d)) for k,d in [('min_players','1'),('max_players','2'),('max_moves','20')]}
        rules.update(initial_state=initial,description=root.findtext('description',''),turn_mode=root.attrib.get('turn_mode','alternating'))
        lines=["def transition(state, action, actor, players):"]
        legal=root.findtext('legal','True')
        lines += ['    if not ('+legal+'):', "        return {'valid': False}"]
        for update in root.findall('update'):
            field=update.attrib.get('field');expr=update.attrib.get('expr')
            if not field or expr is None:raise ValueError('XML update needs field and expr')
            lines.append('    state['+repr(field)+'] = ('+expr+')')
        lines.append('    done = bool('+root.findtext('done','False')+')')
        lines.append('    winner = ('+root.findtext('winner','None')+') if done else None')
        lines.append("    return {'state': state, 'done': done, 'winner': winner}")
        program=ast.parse('\n'.join(lines))
        function=program.body[0]
    elif kind=='game_python':
        try:program=ast.parse(source)
        except SyntaxError as exc:raise ValueError('Invalid game Python syntax') from exc
        if len(program.body)!=2 or not isinstance(program.body[0],ast.Assign) or not isinstance(program.body[1],ast.FunctionDef):
            raise ValueError('Python game needs rules = {...}, followed by def transition(state, action, actor, players)')
        assignment=program.body[0]
        if len(assignment.targets)!=1 or not isinstance(assignment.targets[0],ast.Name) or assignment.targets[0].id!='rules':
            raise ValueError('Expected a literal rules dictionary')
        try:rules=ast.literal_eval(assignment.value)
        except (ValueError,TypeError) as exc:raise ValueError('Game rules must be literal data') from exc
        function=program.body[1]
    else:raise ValueError('Not an executable game work')
    validate_tree(program)
    if function.name!='transition' or function.decorator_list or function.returns or function.args.defaults or function.args.kw_defaults or function.args.vararg or function.args.kwarg:
        raise ValueError('Invalid transition signature')
    if [a.arg for a in function.args.args]!=['state','action','actor','players'] or function.args.posonlyargs or function.args.kwonlyargs or any(a.annotation for a in function.args.args):
        raise ValueError('Expected transition(state, action, actor, players)')
    if not isinstance(rules,dict):raise ValueError('Rules must be a dictionary')
    for key,default in [('min_players',1),('max_players',2),('max_moves',20)]:
        rules.setdefault(key,default)
        if type(rules[key]) is not int or not 1<=rules[key]<=100:raise ValueError('Invalid '+key)
    if not rules['min_players']<=rules['max_players']<=8:raise ValueError('Invalid player count')
    rules.setdefault('turn_mode','alternating')
    if rules['turn_mode'] not in ('alternating','any'):raise ValueError('Invalid turn mode')
    rules.setdefault('initial_state',{})
    if not isinstance(rules['initial_state'],dict):raise ValueError('Initial game state must be a dictionary')
    rules.setdefault('description','')
    bounded(rules)
    return rules,function


class Returned(Exception):
    def __init__(self,value):self.value=value
class BreakLoop(Exception):pass
class ContinueLoop(Exception):pass


class Interpreter:
    def __init__(self,env,seed):self.env=env;self.steps=0;self.rng=random.Random(seed)
    def tick(self):
        self.steps+=1
        if self.steps>MAX_STEPS:raise ValueError('Game execution limit exceeded')
    def expr(self,n):
        self.tick()
        if isinstance(n,ast.Constant):return bounded(n.value)
        if isinstance(n,ast.Name):
            if n.id not in self.env:raise ValueError('Unknown game variable: '+n.id)
            return self.env[n.id]
        if isinstance(n,(ast.List,ast.Tuple)):return bounded([self.expr(v) for v in n.elts])
        if isinstance(n,ast.Dict):
            if any(k is None for k in n.keys):raise ValueError('Dictionary expansion unavailable')
            return bounded({self.expr(k):self.expr(v) for k,v in zip(n.keys,n.values)})
        if isinstance(n,ast.Subscript):return self.expr(n.value)[self.expr(n.slice)]
        if isinstance(n,ast.Slice):return slice(*(self.expr(v) if v else None for v in (n.lower,n.upper,n.step)))
        if isinstance(n,ast.BinOp):
            a,b=self.expr(n.left),self.expr(n.right)
            if isinstance(n.op,ast.Pow) and (type(b) not in (int,float) or abs(b)>10):raise ValueError('Exponent bound exceeded')
            if isinstance(n.op,ast.Mult) and (isinstance(a,(list,str)) or isinstance(b,(list,str))):
                seq,times=(a,b) if isinstance(a,(list,str)) else (b,a)
                if type(times) is not int or len(seq)*max(times,0)>256:raise ValueError('Sequence multiplication bound exceeded')
            ops={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,ast.FloorDiv:operator.floordiv,ast.Mod:operator.mod,ast.Pow:operator.pow}
            return bounded(ops[type(n.op)](a,b))
        if isinstance(n,ast.UnaryOp):return {ast.Not:operator.not_,ast.USub:operator.neg,ast.UAdd:operator.pos}[type(n.op)](self.expr(n.operand))
        if isinstance(n,ast.BoolOp):
            value=self.expr(n.values[0])
            for v in n.values[1:]:
                if isinstance(n.op,ast.And) and not value or isinstance(n.op,ast.Or) and value:break
                value=self.expr(v)
            return value
        if isinstance(n,ast.Compare):
            a=self.expr(n.left)
            ops={ast.Eq:operator.eq,ast.NotEq:operator.ne,ast.Lt:operator.lt,ast.LtE:operator.le,ast.Gt:operator.gt,ast.GtE:operator.ge,ast.In:lambda a,b:a in b,ast.NotIn:lambda a,b:a not in b,ast.Is:operator.is_,ast.IsNot:operator.is_not}
            for op,right in zip(n.ops,n.comparators):
                b=self.expr(right)
                if not ops[type(op)](a,b):return False
                a=b
            return True
        if isinstance(n,ast.IfExp):return self.expr(n.body if self.expr(n.test) else n.orelse)
        if isinstance(n,ast.Call):
            args=[self.expr(a) for a in n.args];kw={k.arg:self.expr(k.value) for k in n.keywords}
            if isinstance(n.func,ast.Name):
                funcs={'len':len,'min':min,'max':max,'sum':sum,'abs':abs,'int':int,'float':float,'bool':bool,'str':str,'randint':self.rng.randint}
                if n.func.id=='range':
                    result=list(range(*args,**kw)) if all(type(a) is int and abs(a)<=256 for a in args) else None
                    if result is None or len(result)>256:raise ValueError('Range bound exceeded')
                    return result
                if n.func.id not in funcs:raise ValueError('Unavailable game function')
                return bounded(funcs[n.func.id](*args,**kw))
            if isinstance(n.func,ast.Attribute):
                value=self.expr(n.func.value);method=n.func.attr
                allowed={'get','keys','values','pop'} if isinstance(value,dict) else {'append','pop'} if isinstance(value,list) else set()
                if method not in allowed:raise ValueError('Unavailable data method')
                if method=='append' and len(value)>=256:raise ValueError('List bound exceeded')
                result=getattr(value,method)(*args,**kw)
                return bounded(list(result) if method in ('keys','values') else result)
        raise ValueError('Unsupported game expression')
    def assign(self,target,value):
        bounded(value)
        if isinstance(target,ast.Name):self.env[target.id]=value
        elif isinstance(target,ast.Subscript):self.expr(target.value)[self.expr(target.slice)]=value
        else:raise ValueError('Unsupported assignment target')
    def block(self,body):
        for n in body:
            self.tick()
            if isinstance(n,ast.Assign):
                value=self.expr(n.value)
                for target in n.targets:self.assign(target,value)
            elif isinstance(n,ast.AugAssign):self.assign(n.target,self.expr(ast.BinOp(left=n.target,op=n.op,right=n.value)))
            elif isinstance(n,ast.Return):raise Returned(self.expr(n.value) if n.value else None)
            elif isinstance(n,ast.If):self.block(n.body if self.expr(n.test) else n.orelse)
            elif isinstance(n,ast.For):
                values=self.expr(n.iter)
                if not isinstance(values,(list,dict,str)) or len(values)>256:raise ValueError('Invalid game iteration')
                broke=False
                for value in list(values):
                    self.assign(n.target,value)
                    try:self.block(n.body)
                    except ContinueLoop:continue
                    except BreakLoop:broke=True;break
                if not broke:self.block(n.orelse)
            elif isinstance(n,ast.Break):raise BreakLoop()
            elif isinstance(n,ast.Continue):raise ContinueLoop()
            elif isinstance(n,ast.Expr):self.expr(n.value)
            elif not isinstance(n,ast.Pass):raise ValueError('Unsupported game statement')


def transition(source,kind,state,action,actor,players,seed,max_source=MAX_SOURCE):
    _,function=parse(source,kind,max_source)
    env={'state':copy.deepcopy(state),'action':copy.deepcopy(action),'actor':actor,'players':list(players)}
    bounded(env)
    runner=Interpreter(env,seed)
    try:runner.block(function.body)
    except Returned as r:result=r.value
    except (KeyError,IndexError,TypeError,ZeroDivisionError,OverflowError,BreakLoop,ContinueLoop) as exc:
        raise ValueError('Invalid game move or rule evaluation') from exc
    else:raise ValueError('Transition must return a result')
    if not isinstance(result,dict) or result.get('valid',True) is not True:
        raise ValueError('Move rejected by game rules')
    if not isinstance(result.get('state'),dict) or type(result.get('done')) is not bool:
        raise ValueError('Transition must return state dictionary and done boolean')
    winner=result.get('winner')
    if winner is not None and winner not in players:raise ValueError('Winner must be a participant or null')
    if not result['done'] and winner is not None:raise ValueError('Unfinished game cannot declare a winner')
    bounded(result)
    return result
