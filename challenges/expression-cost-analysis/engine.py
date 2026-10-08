from contracts import parse,validate_costs,calculate,load_case

def analyze(program,costs,optimize=False):
    raise NotImplementedError("cost and liveness")
    validate_costs(costs);rows=parse(program)
    if optimize:
        needed={'res'};kept=[]
        for row in reversed(rows):
            name,op,args=row
            if name not in needed:continue
            needed.update(x for x in args if isinstance(x,str));kept.append(row)
        rows=list(reversed(kept))
        constants={};folded=[]
        for name,op,args in rows:
            args=[constants.get(x,x) if isinstance(x,str) else x for x in args]
            if all(type(x) is int for x in args):
                value=calculate(op,*args) if op else args[0]
                constants[name]=value;op=None;args=[value]
            folded.append((name,op,args))
        rows=folded
    locations={};uses={};plan=[];time=0
    for index,(name,op,args) in enumerate(rows):
        roots={locations[x] for x in args if isinstance(x,str) and x in locations and locations[x] is not None}
        for root in roots:uses[root]=index
        root=name if op else (locations.get(args[0]) if isinstance(args[0],str) else None)
        locations[name]=root;plan.append((index,op,root))
        if op:time+=costs[op]
    output=locations['res'];live=set();peak=0
    for index,op,root in plan:
        if op:live.add(root)
        peak=max(peak,len(live))
        live={r for r in live if r==output or uses.get(r,index)>index}
    return [time,peak]
