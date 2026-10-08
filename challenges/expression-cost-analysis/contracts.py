import ast
import json

OPS={ast.Add:'+',ast.Sub:'-',ast.Mult:'*',ast.Div:'/'}
def atom(node):
    if isinstance(node,ast.Name):return node.id
    if isinstance(node,ast.Constant) and type(node.value) is int:return node.value
    if isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.USub) and isinstance(node.operand,ast.Constant) and type(node.operand.value) is int:return -node.operand.value
    raise ValueError('simple integer or name required')
def parse(program):
    rows=[];defined=set()
    for line in program:
        if not line.strip() or line.lstrip().startswith('#'):continue
        try:tree=ast.parse(line.strip())
        except SyntaxError as error:raise ValueError('invalid assignment') from error
        if len(tree.body)!=1 or not isinstance(tree.body[0],ast.Assign):raise ValueError('assignment required')
        statement=tree.body[0]
        if len(statement.targets)!=1 or not isinstance(statement.targets[0],ast.Name):raise ValueError('one named target required')
        name=statement.targets[0].id
        if name in defined:raise ValueError('single assignment required')
        defined.add(name);value=statement.value
        if isinstance(value,ast.BinOp) and type(value.op) in OPS:
            op=OPS[type(value.op)];args=[atom(value.left),atom(value.right)]
            if op=='/' and args[1]==0:raise ValueError('division by zero')
        else:op=None;args=[atom(value)]
        rows.append((name,op,args))
    if 'res' not in defined:raise ValueError('res required')
    available=set()
    for name,_,args in rows:
        if any(isinstance(x,str) and x in defined and x not in available for x in args):raise ValueError('forward reference')
        available.add(name)
    return rows
def validate_costs(costs):
    if set(costs)!=set('+-*/') or any(type(v) is not int or v<0 for v in costs.values()):raise ValueError('operator costs required')
def load_case(text):
    data=json.loads(text);costs=data['costs'];totals=data['totals']
    validate_costs(costs)
    if len(totals)!=2 or any(type(v) is not int or v<0 for v in totals):raise ValueError('totals totals required')
    program=[x.strip() for x in data['program'] if x.strip() and not x.lstrip().startswith('#')]
    parse(program)
    return {'costs':{op:int(str(v)[0]) for op,v in costs.items()},'totals':[int(str(v)[0]) for v in totals],'program':program}
def calculate(op,a,b):
    if op=='+':return a+b
    if op=='-':return a-b
    if op=='*':return a*b
    if b==0:raise ValueError('division by zero')
    return (abs(a)//abs(b))*(-1 if (a<0)!=(b<0) else 1)
