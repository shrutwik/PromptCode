"""Test-only original reference sources and wrong-repair fixtures; never candidate content."""

REFERENCE_SOURCES = {'warehouse-route-planner': {'engine.py': 'from collections import deque\n'
                                          'from contracts import endpoints\n'
                                          '\n'
                                          'def render_route(rows,route):\n'
                                          '    endpoints(rows)\n'
                                          '    cells=[list(r) for r in rows]\n'
                                          '    for r,c in route or []:\n'
                                          "        if cells[r][c] == '.': cells[r][c]='*'\n"
                                          "    return [''.join(r) for r in cells]\n"
                                          '\n'
                                          'def shortest_route(rows,forbidden=()):\n'
                                          '    start,end=endpoints(rows)\n'
                                          '    blocked={(tuple(a),tuple(b)) for a,b in forbidden}\n'
                                          '    '
                                          'queue=deque([(start,0,[list(start)])]);seen={(start,0)}\n'
                                          '    while queue:\n'
                                          '        (r,c),mask,path=queue.popleft()\n'
                                          '        if (r,c)==end:return path\n'
                                          '        for dr,dc in [(-1,0),(0,1),(1,0),(0,-1)]:\n'
                                          '            nr,nc=r+dr,c+dc\n'
                                          '            if not (0<=nr<len(rows) and '
                                          '0<=nc<len(rows[0])):continue\n'
                                          '            if ((r,c),(nr,nc)) in blocked:continue\n'
                                          '            tile=rows[nr][nc]\n'
                                          "            if tile=='#':continue\n"
                                          "            if tile in 'ABCD' and not mask & (1 << "
                                          '(ord(tile)-65)):continue\n'
                                          '            next_mask=mask | (1 << (ord(tile)-97)) if '
                                          "tile in 'abcd' else mask\n"
                                          '            state=((nr,nc),next_mask)\n'
                                          '            if state in seen:continue\n'
                                          '            '
                                          'seen.add(state);queue.append(((nr,nc),next_mask,path+[[nr,nc]]))\n'
                                          '    return None\n',
                             'contracts.py': 'def endpoints(rows):\n'
                                             '    if not rows or not rows[0] or '
                                             'any(len(r)!=len(rows[0]) for r in rows):\n'
                                             "        raise ValueError('rectangular grid "
                                             "required')\n"
                                             "    if any(c not in '#.SEabcdABCD' for r in rows for "
                                             'c in r):\n'
                                             "        raise ValueError('unknown tile')\n"
                                             '    start=[(r,c) for r,row in enumerate(rows) for '
                                             "c,x in enumerate(row) if x=='S']\n"
                                             '    end=[(r,c) for r,row in enumerate(rows) for c,x '
                                             "in enumerate(row) if x=='E']\n"
                                             '    if len(start)!=1 or len(end)!=1: raise '
                                             "ValueError('one start and exit required')\n"
                                             '    return start[0],end[0]\n'},
 'courier-payment-ledger': {'engine.py': 'from contracts import cents_for\n'
                                         '\n'
                                         'class Ledger:\n'
                                         '    def __init__(self,rates):\n'
                                         '        if any(type(r) is not int or r<0 for r in '
                                         "rates.values()):raise ValueError('invalid rate')\n"
                                         '        '
                                         'self.rates=dict(rates);self.deliveries={};self.paid=set()\n'
                                         '    def record(self,id,driver,start,end):\n'
                                         '        if driver not in self.rates:raise '
                                         "ValueError('unknown driver')\n"
                                         '        cents_for(self.rates[driver],start,end)\n'
                                         '        item=(driver,start,end)\n'
                                         '        if id in self.deliveries and '
                                         "self.deliveries[id]!=item:raise ValueError('conflicting "
                                         "id')\n"
                                         '        self.deliveries[id]=item\n'
                                         '    def cost(self,item):\n'
                                         '        driver,start,end=item\n'
                                         '        return cents_for(self.rates[driver],start,end)\n'
                                         '    def total(self):return sum(self.cost(x) for x in '
                                         'self.deliveries.values())\n'
                                         '    def unpaid(self):return sum(self.cost(x) for id,x in '
                                         'self.deliveries.items() if id not in self.paid)\n'
                                         '    def pay_up_to(self,cutoff):\n'
                                         '        due=[id for id,x in self.deliveries.items() if '
                                         'id not in self.paid and x[2]<=cutoff]\n'
                                         '        amount=sum(self.cost(self.deliveries[id]) for id '
                                         'in due)\n'
                                         '        self.paid.update(due)\n'
                                         '        return amount\n'
                                         '    def peak(self,window_start,window_end):\n'
                                         '        if window_end<=window_start:raise '
                                         "ValueError('invalid window')\n"
                                         '        events=[]\n'
                                         '        for driver,start,end in '
                                         'self.deliveries.values():\n'
                                         '            '
                                         'a=max(start,window_start);b=min(end,window_end)\n'
                                         '            if '
                                         'a<b:events.extend([(a,1,driver),(b,-1,driver)])\n'
                                         '        counts={};maximum=0\n'
                                         '        for _,delta,driver in sorted(events):\n'
                                         '            counts[driver]=counts.get(driver,0)+delta\n'
                                         '            maximum=max(maximum,sum(v>0 for v in '
                                         'counts.values()))\n'
                                         '        return maximum\n',
                            'contracts.py': 'def cents_for(rate,start,end):\n'
                                            '    if any(type(x) is not int for x in '
                                            '(rate,start,end)) or rate<0 or end<=start:\n'
                                            "        raise ValueError('invalid rate or interval')\n"
                                            '    numerator=rate*(end-start)\n'
                                            '    return (2*numerator+3600)//7200\n'},
 'worker-job-dispatch': {'engine.py': 'import heapq\n'
                                      'from contracts import can_start,validate\n'
                                      '\n'
                                      'def dispatch(k,jobs):\n'
                                      '    validate(k,jobs)\n'
                                      '    idle=list(range(k));busy=[];out=[];now=0\n'
                                      '    for _,(id,arrival,duration) in '
                                      'sorted(enumerate(jobs),key=lambda p:(p[1][1],p[0])):\n'
                                      '        now=max(now,arrival)\n'
                                      '        if not idle:now=max(now,busy[0][0])\n'
                                      '        while busy and can_start(busy[0][0],now):\n'
                                      '            '
                                      '_,worker=heapq.heappop(busy);heapq.heappush(idle,worker)\n'
                                      '        worker=heapq.heappop(idle);finish=now+duration\n'
                                      '        '
                                      'heapq.heappush(busy,(finish,worker));out.append([id,worker,now,finish])\n'
                                      '    return out\n',
                         'contracts.py': 'def can_start(finish,arrival):return finish<=arrival\n'
                                         'def validate(k,jobs):\n'
                                         '    if type(k) is not int or k<=0:raise '
                                         "ValueError('positive worker count')\n"
                                         '    if len({j[0] for j in jobs})!=len(jobs):raise '
                                         "ValueError('duplicate job id')\n"
                                         '    if any(type(t) is not int or type(d) is not int or '
                                         't<0 or d<=0 for _,t,d in jobs):\n'
                                         "        raise ValueError('invalid job')\n"},
 'bounded-recency-cache': {'engine.py': 'from collections import OrderedDict\n'
                                        'from threading import RLock\n'
                                        'from contracts import validate_capacity\n'
                                        '\n'
                                        'class Cache:\n'
                                        '    def __init__(self,capacity):\n'
                                        '        '
                                        'validate_capacity(capacity);self.capacity=capacity;self.data=OrderedDict();self.lock=RLock()\n'
                                        '    def get(self,key):\n'
                                        '        with self.lock:\n'
                                        '            if key not in self.data:return None\n'
                                        '            self.data.move_to_end(key)\n'
                                        '            return self.data[key]\n'
                                        '    def put(self,key,value):\n'
                                        '        with self.lock:\n'
                                        '            '
                                        'self.data[key]=value;self.data.move_to_end(key)\n'
                                        '            while '
                                        'len(self.data)>self.capacity:self.data.popitem(last=False)\n'
                                        '    def resize(self,capacity):\n'
                                        '        validate_capacity(capacity)\n'
                                        '        with self.lock:\n'
                                        '            self.capacity=capacity\n'
                                        '            while '
                                        'len(self.data)>self.capacity:self.data.popitem(last=False)\n'
                                        '    def get_or_put(self,key,factory):\n'
                                        '        with self.lock:\n'
                                        '            if key in self.data:\n'
                                        '                self.data.move_to_end(key);return '
                                        'self.data[key]\n'
                                        '            value=factory();self.put(key,value);return '
                                        'value\n'
                                        '    def keys(self):\n'
                                        '        with self.lock:return list(self.data)\n',
                           'contracts.py': 'def validate_capacity(capacity):\n'
                                           '    if type(capacity) is not int or capacity<0:raise '
                                           "ValueError('invalid capacity')\n"},
 'service-impact-analysis': {'engine.py': 'from contracts import normalize,ancestor\n'
                                          '\n'
                                          'def impacted(watched,depends,changes):\n'
                                          '    paths={s:[normalize(p) for p in ps] for s,ps in '
                                          'watched.items()}\n'
                                          '    edits=[(normalize(p),deleted) for p,deleted in '
                                          'changes]\n'
                                          '    if any(s not in paths or any(d not in paths for d '
                                          'in ds) for s,ds in depends.items()):\n'
                                          "        raise ValueError('unknown service')\n"
                                          '    result={s for s,ps in paths.items() if '
                                          'any(ancestor(w,p) or (deleted and ancestor(p,w)) for w '
                                          'in ps for p,deleted in edits)}\n'
                                          '    reverse={s:set() for s in paths}\n'
                                          '    for s,ds in depends.items():\n'
                                          '        for d in ds:reverse[d].add(s)\n'
                                          '    queue=list(result)\n'
                                          '    while queue:\n'
                                          '        node=queue.pop()\n'
                                          '        for dependent in reverse[node]-result:\n'
                                          '            '
                                          'result.add(dependent);queue.append(dependent)\n'
                                          '    return sorted(result)\n',
                             'contracts.py': 'def normalize(path):\n'
                                             '    if not isinstance(path,str) or not '
                                             "path.startswith('/'):raise ValueError('absolute path "
                                             "required')\n"
                                             "    parts=[x for x in path.split('/') if x]\n"
                                             "    if any(x in ('.','..') for x in parts):raise "
                                             "ValueError('relative segments forbidden')\n"
                                             "    return '/'+ '/'.join(parts)\n"
                                             'def ancestor(a,b):\n'
                                             '    a,b=normalize(a),normalize(b)\n'
                                             "    return a=='/' or a==b or b.startswith(a+'/')\n"},
 'unique-word-selection': {'engine.py': 'from contracts import masks\n'
                                        '\n'
                                        'def valid(words,indices):\n'
                                        '    ms=masks(words)\n'
                                        '    if any(type(i) is not int or i<0 or i>=len(words) for '
                                        'i in indices) or len(set(indices))!=len(indices):return '
                                        'False\n'
                                        '    used=0\n'
                                        '    for i in indices:\n'
                                        '        if ms[i] is None or used&ms[i]:return False\n'
                                        '        used|=ms[i]\n'
                                        '    return True\n'
                                        '\n'
                                        'def choose(words):\n'
                                        '    ms=masks(words);states={0:[]}\n'
                                        '    for i,mask in enumerate(ms):\n'
                                        '        if mask is None:continue\n'
                                        '        for used,selection in list(states.items()):\n'
                                        '            if used&mask:continue\n'
                                        '            combined=used|mask;candidate=selection+[i]\n'
                                        '            if combined not in states or '
                                        '(len(candidate),candidate)<(len(states[combined]),states[combined]):states[combined]=candidate\n'
                                        '    return min(states.items(),key=lambda '
                                        'item:(-item[0].bit_count(),len(item[1]),item[1]))[1]\n',
                           'contracts.py': 'def masks(words):\n'
                                           '    out=[]\n'
                                           '    for word in words:\n'
                                           '        if not isinstance(word,str) or any(not '
                                           "'a'<=c<='z' for c in word):raise ValueError('lowercase "
                                           "words required')\n"
                                           '        mask=0;valid=True\n'
                                           '        for c in word:\n'
                                           '            bit=1<<(ord(c)-97)\n'
                                           '            if mask&bit:valid=False\n'
                                           '            mask|=bit\n'
                                           '        out.append(mask if valid else None)\n'
                                           '    return out\n'},
 'expression-cost-analysis': {'engine.py': 'from contracts import '
                                           'parse,validate_costs,calculate,load_case\n'
                                           '\n'
                                           'def analyze(program,costs,optimize=False):\n'
                                           '    validate_costs(costs);rows=parse(program)\n'
                                           '    if optimize:\n'
                                           "        needed={'res'};kept=[]\n"
                                           '        for row in reversed(rows):\n'
                                           '            name,op,args=row\n'
                                           '            if name not in needed:continue\n'
                                           '            needed.update(x for x in args if '
                                           'isinstance(x,str));kept.append(row)\n'
                                           '        rows=list(reversed(kept))\n'
                                           '        constants={};folded=[]\n'
                                           '        for name,op,args in rows:\n'
                                           '            args=[constants.get(x,x) if '
                                           'isinstance(x,str) else x for x in args]\n'
                                           '            if all(type(x) is int for x in args):\n'
                                           '                value=calculate(op,*args) if op else '
                                           'args[0]\n'
                                           '                '
                                           'constants[name]=value;op=None;args=[value]\n'
                                           '            folded.append((name,op,args))\n'
                                           '        rows=folded\n'
                                           '    locations={};uses={};plan=[];time=0\n'
                                           '    for index,(name,op,args) in enumerate(rows):\n'
                                           '        roots={locations[x] for x in args if '
                                           'isinstance(x,str) and x in locations and locations[x] '
                                           'is not None}\n'
                                           '        for root in roots:uses[root]=index\n'
                                           '        root=name if op else (locations.get(args[0]) '
                                           'if isinstance(args[0],str) else None)\n'
                                           '        '
                                           'locations[name]=root;plan.append((index,op,root))\n'
                                           '        if op:time+=costs[op]\n'
                                           "    output=locations['res'];live=set();peak=0\n"
                                           '    for index,op,root in plan:\n'
                                           '        if op:live.add(root)\n'
                                           '        peak=max(peak,len(live))\n'
                                           '        live={r for r in live if r==output or '
                                           'uses.get(r,index)>index}\n'
                                           '    return [time,peak]\n',
                              'contracts.py': 'import ast\n'
                                              'import json\n'
                                              '\n'
                                              "OPS={ast.Add:'+',ast.Sub:'-',ast.Mult:'*',ast.Div:'/'}\n"
                                              'def atom(node):\n'
                                              '    if isinstance(node,ast.Name):return node.id\n'
                                              '    if isinstance(node,ast.Constant) and '
                                              'type(node.value) is int:return node.value\n'
                                              '    if isinstance(node,ast.UnaryOp) and '
                                              'isinstance(node.op,ast.USub) and '
                                              'isinstance(node.operand,ast.Constant) and '
                                              'type(node.operand.value) is int:return '
                                              '-node.operand.value\n'
                                              "    raise ValueError('simple integer or name "
                                              "required')\n"
                                              'def parse(program):\n'
                                              '    rows=[];defined=set()\n'
                                              '    for line in program:\n'
                                              '        if not line.strip() or '
                                              "line.lstrip().startswith('#'):continue\n"
                                              '        try:tree=ast.parse(line.strip())\n'
                                              '        except SyntaxError as error:raise '
                                              "ValueError('invalid assignment') from error\n"
                                              '        if len(tree.body)!=1 or not '
                                              'isinstance(tree.body[0],ast.Assign):raise '
                                              "ValueError('assignment required')\n"
                                              '        statement=tree.body[0]\n'
                                              '        if len(statement.targets)!=1 or not '
                                              'isinstance(statement.targets[0],ast.Name):raise '
                                              "ValueError('one named target required')\n"
                                              '        name=statement.targets[0].id\n'
                                              "        if name in defined:raise ValueError('single "
                                              "assignment required')\n"
                                              '        defined.add(name);value=statement.value\n'
                                              '        if isinstance(value,ast.BinOp) and '
                                              'type(value.op) in OPS:\n'
                                              '            '
                                              'op=OPS[type(value.op)];args=[atom(value.left),atom(value.right)]\n'
                                              "            if op=='/' and args[1]==0:raise "
                                              "ValueError('division by zero')\n"
                                              '        else:op=None;args=[atom(value)]\n'
                                              '        rows.append((name,op,args))\n'
                                              "    if 'res' not in defined:raise ValueError('res "
                                              "required')\n"
                                              '    available=set()\n'
                                              '    for name,_,args in rows:\n'
                                              '        if any(isinstance(x,str) and x in defined '
                                              'and x not in available for x in args):raise '
                                              "ValueError('forward reference')\n"
                                              '        available.add(name)\n'
                                              '    return rows\n'
                                              'def validate_costs(costs):\n'
                                              "    if set(costs)!=set('+-*/') or any(type(v) is "
                                              'not int or v<0 for v in costs.values()):raise '
                                              "ValueError('operator costs required')\n"
                                              'def load_case(text):\n'
                                              '    '
                                              "data=json.loads(text);costs=data['costs'];totals=data['totals']\n"
                                              '    validate_costs(costs)\n'
                                              '    if len(totals)!=2 or any(type(v) is not int or '
                                              "v<0 for v in totals):raise ValueError('totals "
                                              "totals required')\n"
                                              "    program=[x.strip() for x in data['program'] if "
                                              "x.strip() and not x.lstrip().startswith('#')]\n"
                                              '    parse(program)\n'
                                              '    return '
                                              "{'costs':dict(costs),'totals':list(totals),'program':program}\n"
                                              'def calculate(op,a,b):\n'
                                              "    if op=='+':return a+b\n"
                                              "    if op=='-':return a-b\n"
                                              "    if op=='*':return a*b\n"
                                              "    if b==0:raise ValueError('division by zero')\n"
                                              '    return (abs(a)//abs(b))*(-1 if (a<0)!=(b<0) '
                                              'else 1)\n'},
 'room-reservation-scheduler': {'engine.py': 'from threading import RLock\n'
                                             'from contracts import interval,overlap\n'
                                             '\n'
                                             'class Scheduler:\n'
                                             '    def __init__(self,bookings=()):\n'
                                             '        for b in bookings:interval(*b)\n'
                                             '        self.bookings=sorted(tuple(b) for b in '
                                             'bookings);self.lock=RLock()\n'
                                             '    def find(self,duration,earliest,latest_end):\n'
                                             '        interval(earliest,latest_end)\n'
                                             '        if type(duration) is not int or '
                                             "duration<=0:raise ValueError('positive duration')\n"
                                             '        with self.lock:\n'
                                             '            start=earliest\n'
                                             '            for a,b in self.bookings:\n'
                                             '                if b<=start:continue\n'
                                             '                if start+duration<=a and '
                                             'start+duration<=latest_end:return '
                                             '[start,start+duration]\n'
                                             '                if '
                                             'a<start+duration:start=max(start,b)\n'
                                             '            return [start,start+duration] if '
                                             'start+duration<=latest_end else None\n'
                                             '    def reserve(self,duration,earliest,latest_end):\n'
                                             '        with self.lock:\n'
                                             '            '
                                             'slot=self.find(duration,earliest,latest_end)\n'
                                             '            if slot is not None:\n'
                                             '                '
                                             'self.bookings.append(tuple(slot));self.bookings.sort()\n'
                                             '            return slot\n'
                                             '    def snapshot(self):\n'
                                             '        with self.lock:return [list(b) for b in '
                                             'self.bookings]\n',
                                'contracts.py': 'def interval(start,end):\n'
                                                '    if type(start) is not int or type(end) is not '
                                                "int or end<=start:raise ValueError('positive "
                                                "integer interval')\n"
                                                'def overlap(a,b):\n'
                                                '    interval(*a);interval(*b)\n'
                                                '    return a[0]<b[1] and b[0]<a[1]\n'},
 'card-triple-strategy': {'engine.py': 'from itertools import combinations\n'
                                       'from contracts import validate_table\n'
                                       '\n'
                                       'def legal(cards,ids):\n'
                                       '    validate_table(cards)\n'
                                       '    if len(ids)!=3 or len(set(ids))!=3:return False\n'
                                       "    amounts={c['id']:c['amount'] for c in cards}\n"
                                       '    return all(id in amounts for id in ids) and '
                                       'sum(amounts[id] for id in ids)==15\n'
                                       'def choose(cards):\n'
                                       '    validate_table(cards)\n'
                                       '    return next((list(ids) for ids in '
                                       "combinations(sorted(c['id'] for c in cards),3) if "
                                       'legal(cards,ids)),None)\n'
                                       'def remove(cards,ids):\n'
                                       "    if not legal(cards,ids):raise ValueError('illegal "
                                       "move')\n"
                                       '    chosen=set(ids)\n'
                                       "    return [dict(c) for c in cards if c['id'] not in "
                                       'chosen]\n',
                          'contracts.py': 'def validate_table(cards):\n'
                                          "    if any(not isinstance(c['id'],str) or "
                                          "type(c['amount']) is not int or not 1<=c['amount']<=9 "
                                          "for c in cards):raise ValueError('invalid card')\n"
                                          "    if len({c['id'] for c in cards})!=len(cards):raise "
                                          "ValueError('duplicate physical id')\n"},
 'structured-event-logger': {'engine.py': 'from copy import deepcopy\n'
                                          'from contracts import LEVELS,enabled,format_json\n'
                                          '\n'
                                          'class Logger:\n'
                                          '    def __init__(self,level,sinks,clock):\n'
                                          '        self.clock=clock;self.configure(level,sinks)\n'
                                          '    def configure(self,level,sinks):\n'
                                          '        if level not in LEVELS or not all(callable(s) '
                                          "for s in sinks):raise ValueError('invalid config')\n"
                                          '        self.level=level;self.sinks=list(sinks)\n'
                                          '    def emit(self,level,message,context=None):\n'
                                          '        if not enabled(level,self.level):return []\n'
                                          '        '
                                          "record={'level':level,'message':message,'timestamp':self.clock(),'context':deepcopy(context "
                                          'if context is not None else {})}\n'
                                          '        failures=[]\n'
                                          '        for index,sink in enumerate(self.sinks):\n'
                                          '            try:sink(deepcopy(record))\n'
                                          '            except Exception:failures.append(index)\n'
                                          '        return failures\n',
                             'contracts.py': 'import json\n'
                                             "LEVELS={'DEBUG':0,'INFO':1,'WARN':2,'ERROR':3}\n"
                                             'def enabled(level,threshold):\n'
                                             '    if level not in LEVELS or threshold not in '
                                             "LEVELS:raise ValueError('unknown level')\n"
                                             '    return LEVELS[level]>=LEVELS[threshold]\n'
                                             'def format_json(record):return '
                                             'json.dumps(record,sort_keys=True,ensure_ascii=False)\n'}}

MUTATIONS = {'warehouse-route-planner': ('engine.py',
                             "if tile=='#':continue",
                             "if tile in '#ABCD':continue",
                             'two-badges'),
 'courier-payment-ledger': ('engine.py', 'x[2]<=cutoff', 'x[2]<cutoff', 'incremental-pay'),
 'worker-job-dispatch': ('engine.py',
                         'while busy and can_start(busy[0][0],now):',
                         'if busy and can_start(busy[0][0],now):',
                         'simultaneous-release'),
 'bounded-recency-cache': ('engine.py',
                           '            self.data.move_to_end(key)\n'
                           '            return self.data[key]',
                           '            return self.data[key]',
                           'read-recency'),
 'service-impact-analysis': ('engine.py',
                             'reverse[d].add(s)',
                             'reverse[s].add(d)',
                             'reverse-closure'),
 'unique-word-selection': ('engine.py',
                           'return min(states.items(),key=lambda '
                           'item:(-item[0].bit_count(),len(item[1]),item[1]))[1]',
                           'return max(states.items(),key=lambda '
                           'item:(item[0].bit_count(),item[1]))[1]',
                           'tie-by-index'),
 'expression-cost-analysis': ('engine.py',
                              '        peak=max(peak,len(live))',
                              '        peak=max(peak,max(0,len(live)-1))',
                              'custom-cost'),
 'room-reservation-scheduler': ('engine.py',
                                'start+duration<=latest_end',
                                'start+duration<latest_end',
                                'atomic-reserve'),
 'card-triple-strategy': ('engine.py',
                          'len(ids)!=3 or len(set(ids))!=3',
                          'len(ids)!=3',
                          'physical-multiplicity'),
 'structured-event-logger': ('engine.py',
                             '            except Exception:failures.append(index)',
                             '            except Exception:break',
                             'continue-sinks')}

EDGE_MUTATIONS = {'warehouse-route-planner': ('engine.py',
                             "if tile in 'ABCD' and not mask & (1 << (ord(tile)-65)):continue",
                             'if False:continue',
                             'gate-before-badge'),
 'courier-payment-ledger': ('engine.py',
                            'sum(v>0 for v in counts.values())',
                            'sum(counts.values())',
                            'peak-distinct'),
 'worker-job-dispatch': ('contracts.py', 'finish<=arrival', 'finish<arrival', 'exact-boundary'),
 'bounded-recency-cache': ('engine.py',
                           'self.data.popitem(last=False)',
                           'self.data.popitem(last=True)',
                           'shrink-oldest'),
 'service-impact-analysis': ('engine.py',
                             '(deleted and ancestor(p,w))',
                             '(False and ancestor(p,w))',
                             'deleted-watch-descendant'),
 'unique-word-selection': ('engine.py',
                           'if ms[i] is None or used&ms[i]:return False',
                           'if ms[i] is None:continue',
                           'validator-legality'),
 'expression-cost-analysis': ('contracts.py', 'abs(a)//abs(b)', 'a//b', 'division-rule'),
 'room-reservation-scheduler': ('contracts.py',
                                'a[0]<b[1] and b[0]<a[1]',
                                'a[0]<=b[1] and b[0]<=a[1]',
                                'boundary-helper'),
 'card-triple-strategy': ('engine.py',
                          "sorted(c['id'] for c in cards)",
                          "[c['id'] for c in cards]",
                          'deterministic-choice'),
 'structured-event-logger': ('contracts.py',
                             'LEVELS[level]>=LEVELS[threshold]',
                             'LEVELS[level]>LEVELS[threshold]',
                             'level-boundaries')}

from ranked_reference_fixtures import EDGE_MUTATIONS as RANKED_EDGE_MUTATIONS
from ranked_reference_fixtures import MUTATIONS as RANKED_MUTATIONS
from ranked_reference_fixtures import REFERENCE_SOURCES as RANKED_SOURCES

REFERENCE_SOURCES.update(RANKED_SOURCES)
MUTATIONS.update(RANKED_MUTATIONS)
EDGE_MUTATIONS.update(RANKED_EDGE_MUTATIONS)
