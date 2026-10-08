"""Independent observation cases for original expansion questions, not visible-test execution."""
from . import Case

_ROWS = {'warehouse-route-planner': [('endpoint-markers',
                              2,
                              'from engine import render_route\n'
                              "result=render_route(['S..E'],[[0,0],[0,1],[0,2],[0,3]])",
                              ['S**E']),
                             ('short-path',
                              2,
                              "from engine import shortest_route\nresult=shortest_route(['S..E'])",
                              [[0, 0], [0, 1], [0, 2], [0, 3]]),
                             ('two-badges',
                              2,
                              'from engine import shortest_route\n'
                              "result=shortest_route(['SaAbBE'])",
                              [[0, 0], [0, 1], [0, 2], [0, 3], [0, 4], [0, 5]]),
                             ('reusable-badge',
                              2,
                              "from engine import shortest_route\nresult=shortest_route(['SaAAE'])",
                              [[0, 0], [0, 1], [0, 2], [0, 3], [0, 4]]),
                             ('unreachable',
                              2,
                              'from engine import shortest_route\n'
                              "result=shortest_route(['S#E','###','a..'])",
                              None),
                             ('gate-before-badge',
                              2,
                              "from engine import shortest_route\nresult=shortest_route(['SAE'])",
                              None),
                             ('reverse-edge-allowed',
                              2,
                              'from engine import shortest_route\n'
                              "result=shortest_route(['S.E'],[([0,1],[0,0])])",
                              [[0, 0], [0, 1], [0, 2]]),
                             ('invalid-grid',
                              2,
                              'from engine import shortest_route\n'
                              "try:shortest_route(['S.','E'])\n"
                              'except ValueError:result=True\n'
                              'else:result=False',
                              True)],
 'courier-payment-ledger': [('payout-precision',
                             2,
                             'from engine import Ledger\n'
                             "l=Ledger({'a':2400});l.record('q','a',0,2700);result=l.total()",
                             1800),
                            ('per-record-rounding',
                             2,
                             'from engine import Ledger\n'
                             "l=Ledger({'a':1});l.record('x','a',0,1800);l.record('y','a',1800,3600);result=l.total()",
                             2),
                            ('incremental-pay',
                             2,
                             'from engine import Ledger\n'
                             "l=Ledger({'a':3600});l.record('x','a',0,7);l.record('y','a',0,13);result=[l.pay_up_to(7),l.unpaid(),l.pay_up_to(13),l.pay_up_to(99)]",
                             [7, 13, 13, 0]),
                            ('unknown-driver',
                             2,
                             'from engine import Ledger\n'
                             "l=Ledger({'a':3600})\n"
                             "try:l.record('q','missing',0,1)\n"
                             'except ValueError:result=l.total()\n'
                             'else:result=-1',
                             0),
                            ('conflict-preserves',
                             2,
                             'from engine import Ledger\n'
                             "l=Ledger({'a':3600});l.record('q','a',0,7)\n"
                             "try:l.record('q','a',0,8)\n"
                             'except ValueError:result=l.total()\n'
                             'else:result=-1',
                             7),
                            ('peak-distinct',
                             2,
                             'from engine import Ledger\n'
                             "l=Ledger({'a':0});l.record('x','a',0,20);l.record('y','a',2,18);result=l.peak(5,10)",
                             1),
                            ('window-clipping',
                             2,
                             'from engine import Ledger\n'
                             "l=Ledger({'a':0,'b':0});l.record('x','a',0,10);l.record('y','b',10,20);result=l.peak(10,15)",
                             1),
                            ('invalid-preserves',
                             2,
                             'from engine import Ledger\n'
                             "l=Ledger({'a':3600})\n"
                             "try:l.record('q','a',4,4)\n"
                             'except ValueError:result=[l.total(),l.unpaid()]\n'
                             'else:result=None',
                             [0, 0])],
 'worker-job-dispatch': [('exact-boundary',
                          2,
                          "from engine import dispatch\nresult=dispatch(1,[('x',1,4),('y',5,2)])",
                          [['x', 0, 1, 5], ['y', 0, 5, 7]]),
                         ('fifo-queue',
                          2,
                          'from engine import dispatch\n'
                          "result=dispatch(1,[('x',0,4),('y',1,2),('z',1,3)])",
                          [['x', 0, 0, 4], ['y', 0, 4, 6], ['z', 0, 6, 9]]),
                         ('simultaneous-release',
                          2,
                          'from engine import dispatch\n'
                          "result=dispatch(2,[('x',0,3),('y',0,2),('z',3,1)])",
                          [['x', 0, 0, 3], ['y', 1, 0, 2], ['z', 0, 3, 4]]),
                         ('sorted-arrivals',
                          2,
                          'from engine import dispatch\n'
                          "result=dispatch(1,[('late',8,1),('early',0,1)])",
                          [['early', 0, 0, 1], ['late', 0, 8, 9]]),
                         ('idle-gap',
                          2,
                          'from engine import dispatch\n'
                          "result=dispatch(2,[('x',10,1),('y',10,1),('z',12,1)])",
                          [['x', 0, 10, 11], ['y', 1, 10, 11], ['z', 0, 12, 13]]),
                         ('invalid-duration',
                          2,
                          'from engine import dispatch\n'
                          "try:dispatch(1,[('x',0,0)])\n"
                          'except ValueError:result=True\n'
                          'else:result=False',
                          True),
                         ('duplicate-id',
                          2,
                          'from engine import dispatch\n'
                          "try:dispatch(1,[('x',0,1),('x',1,1)])\n"
                          'except ValueError:result=True\n'
                          'else:result=False',
                          True),
                         ('empty-jobs',
                          2,
                          'from engine import dispatch\nresult=dispatch(2,[])',
                          [])],
 'bounded-recency-cache': [('read-recency',
                            2,
                            'from engine import Cache\n'
                            "c=Cache(2);c.put('x',4);c.put('y',5);c.get('x');c.put('z',6);result=[c.keys(),c.get('y')]",
                            [['x', 'z'], None]),
                           ('shrink-oldest',
                            2,
                            'from engine import Cache\n'
                            'c=Cache(4);[c.put(x,x) for x in '
                            "'wxyz'];c.get('w');c.resize(2);result=c.keys()",
                            ['z', 'w']),
                           ('grow-keeps-order',
                            2,
                            'from engine import Cache\n'
                            "c=Cache(1);c.put('x',1);c.resize(3);c.put('y',2);result=c.keys()",
                            ['x', 'y']),
                           ('zero-capacity',
                            2,
                            'from engine import Cache\n'
                            "c=Cache(2);c.put('x',1);c.resize(0);c.put('y',2);result=c.keys()",
                            []),
                           ('none-is-cached',
                            2,
                            'from engine import Cache\n'
                            "c=Cache(1);calls=[];c.get_or_put('x',lambda:(calls.append(1) or "
                            "None));c.get_or_put('x',lambda:(calls.append(1) or "
                            '9));result=[len(calls),c.keys()]',
                            [1, ['x']]),
                           ('concurrent-factory',
                            2,
                            'from engine import Cache\n'
                            'from threading import Barrier\n'
                            'from concurrent.futures import ThreadPoolExecutor\n'
                            'c=Cache(2);gate=Barrier(2);calls=[]\n'
                            'def work():\n'
                            '    gate.wait(timeout=2)\n'
                            "    return c.get_or_put('x',lambda:(calls.append(1) or 42))\n"
                            'with ThreadPoolExecutor(max_workers=2) as '
                            'pool:values=list(pool.map(lambda _:work(),range(2)))\n'
                            'result=[values,len(calls),c.keys()]',
                            [[42, 42], 1, ['x']]),
                           ('invalid-construction',
                            2,
                            'from engine import Cache\n'
                            'try:Cache(True)\n'
                            'except ValueError:result=True\n'
                            'else:result=False',
                            True),
                           ('factory-retry',
                            2,
                            'from engine import Cache\n'
                            'c=Cache(1)\n'
                            "def bad():raise RuntimeError('x')\n"
                            "try:c.get_or_put('x',bad)\n"
                            'except RuntimeError:pass\n'
                            "result=[c.get_or_put('x',lambda:8),c.get('x')]",
                            [8, 8])],
 'service-impact-analysis': [('prefix-boundary',
                              2,
                              'from contracts import ancestor\n'
                              "result=[ancestor('/api','/apiv2/x'),ancestor('/api/','//api//x'),ancestor('/','/x')]",
                              [False, True, True]),
                             ('root-normalized',
                              2,
                              'from contracts import normalize\n'
                              "result=[normalize('///'),normalize('//a///b//')]",
                              ['/', '/a/b']),
                             ('reverse-closure',
                              2,
                              'from engine import impacted\n'
                              "result=impacted({'web':['/web'],'api':['/api'],'db':['/data']},{'web':['api'],'api':['db']},[('/data/a',False)])",
                              ['api', 'db', 'web']),
                             ('dependency-direction',
                              2,
                              'from engine import impacted\n'
                              "result=impacted({'a':['/a'],'b':['/b']},{'a':['b']},[('/a/x',False)])",
                              ['a']),
                             ('deleted-watch-descendant',
                              2,
                              'from engine import impacted\n'
                              "result=impacted({'a':['/tree/leaf'],'b':['/other']},{},[('/tree',True)])",
                              ['a']),
                             ('ordinary-file-not-parent-delete',
                              2,
                              'from engine import impacted\n'
                              "result=impacted({'a':['/tree/leaf']},{},[('/tree',False)])",
                              []),
                             ('cycle-terminates',
                              2,
                              'from engine import impacted\n'
                              "result=impacted({'a':['/a'],'b':['/b'],'c':['/c']},{'a':['b'],'b':['c'],'c':['a']},[('/c/z',False)])",
                              ['a', 'b', 'c']),
                             ('unknown-service',
                              2,
                              'from engine import impacted\n'
                              "try:impacted({'a':['/a']},{'a':['missing']},[])\n"
                              'except ValueError:result=True\n'
                              'else:result=False',
                              True)],
 'unique-word-selection': [('validator-legality',
                            2,
                            'from engine import valid\n'
                            "result=[valid(['xy','z'],[0]),valid(['xx','z'],[0]),valid(['xy','yz'],[0,1])]",
                            [True, False, False]),
                           ('optimum-not-greedy',
                            2,
                            "from engine import choose\nresult=choose(['wxy','wa','xb','yc'])",
                            [1, 2, 3]),
                           ('tie-by-index',
                            2,
                            "from engine import choose\nresult=choose(['ab','bc'])",
                            [0]),
                           ('occurrence-identity',
                            2,
                            'from engine import valid\n'
                            "result=[valid(['ab','ab'],[0,1]),valid(['a'],[0,0])]",
                            [False, False]),
                           ('empty-word-tie',
                            2,
                            "from engine import choose\nresult=choose(['','ab'])",
                            [1]),
                           ('no-clean-words',
                            2,
                            "from engine import choose\nresult=choose(['aa','bb'])",
                            []),
                           ('alphabet-contract',
                            2,
                            'from engine import choose\n'
                            "try:choose(['A'])\n"
                            'except ValueError:result=True\n'
                            'else:result=False',
                            True),
                           ('all-26',
                            2,
                            'from engine import choose\n'
                            "words=['ab','cd','ef','gh','ij','kl','mn','op','qr','st','uv','wx','yz'];before=list(words);result=[choose(words),words==before]",
                            [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], True])],
 'expression-cost-analysis': [('metadata-values',
                               2,
                               'from contracts import load_case\n'
                               'import json\n'
                               "x=load_case(json.dumps({'costs':{'+':21,'-':2,'*':19,'/':4},'totals':[321,14],'program':['# "
                               "header','','res=q+3']}));result=[x['costs']['+'],x['totals'],x['program']]",
                               [21, [321, 14], ['res=q+3']]),
                              ('custom-cost',
                               2,
                               'from engine import analyze\n'
                               "result=analyze(['a=q*2','res=a+4'],{'+':7,'-':2,'*':11,'/':4})",
                               [18, 2]),
                              ('dead-branch',
                               2,
                               'from engine import analyze\n'
                               "result=analyze(['junk=q*2','a=r+4','res=a'],{'+':7,'-':2,'*':11,'/':4},True)",
                               [7, 1]),
                              ('folded-program',
                               2,
                               'from engine import analyze\n'
                               "result=analyze(['a=8/3','b=a*7','res=b-1'],{'+':7,'-':2,'*':11,'/':4},True)",
                               [0, 0]),
                              ('division-rule',
                               2,
                               'from contracts import calculate\n'
                               "result=[calculate('/',-7,2),calculate('/',7,-2),calculate('/',-7,-2)]",
                               [-3, -3, 3]),
                              ('alias-liveness',
                               2,
                               'from engine import analyze\n'
                               "result=analyze(['a=q+1','alias=a','b=alias*2','res=b'],{'+':3,'-':2,'*':5,'/':4})",
                               [8, 2]),
                              ('invalid-ssa',
                               2,
                               'from engine import analyze\n'
                               "try:analyze(['a=q+1','a=q+2','res=a'],{'+':1,'-':1,'*':1,'/':1})\n"
                               'except ValueError:result=True\n'
                               'else:result=False',
                               True),
                              ('division-zero',
                               2,
                               'from engine import analyze\n'
                               "try:analyze(['res=1/0'],{'+':1,'-':1,'*':1,'/':1},True)\n"
                               'except ValueError:result=True\n'
                               'else:result=False',
                               True)],
 'room-reservation-scheduler': [('boundary-helper',
                                 2,
                                 'from contracts import overlap\n'
                                 'result=[overlap([2,7],[7,9]),overlap([2,8],[7,9])]',
                                 [False, True]),
                                ('gap-exact-fit',
                                 2,
                                 'from engine import Scheduler\n'
                                 'result=Scheduler([(0,4),(9,15)]).find(5,0,20)',
                                 [4, 9]),
                                ('overlapping-union',
                                 2,
                                 'from engine import Scheduler\n'
                                 'result=Scheduler([(3,12),(0,7),(5,9)]).find(4,1,20)',
                                 [12, 16]),
                                ('upper-bound',
                                 2,
                                 'from engine import Scheduler\n'
                                 'result=Scheduler([(0,8)]).find(3,0,10)',
                                 None),
                                ('sorted-insert',
                                 2,
                                 'from engine import Scheduler\n'
                                 's=Scheduler([(8,10)]);s.reserve(3,0,20);result=s.snapshot()',
                                 [[0, 3], [8, 10]]),
                                ('atomic-reserve',
                                 2,
                                 'from engine import Scheduler\n'
                                 'from threading import Barrier\n'
                                 'from concurrent.futures import ThreadPoolExecutor\n'
                                 's=Scheduler();gate=Barrier(2)\n'
                                 'def work():\n'
                                 '    gate.wait(timeout=2)\n'
                                 '    return s.reserve(10,0,10)\n'
                                 'with ThreadPoolExecutor(max_workers=2) as '
                                 'pool:values=list(pool.map(lambda _:work(),range(2)))\n'
                                 'result=[values.count([0,10]),values.count(None),s.snapshot()]',
                                 [1, 1, [[0, 10]]]),
                                ('invalid-window',
                                 2,
                                 'from engine import Scheduler\n'
                                 's=Scheduler()\n'
                                 'try:s.reserve(1,4,4)\n'
                                 'except ValueError:result=s.snapshot()\n'
                                 'else:result=None',
                                 []),
                                ('input-copy',
                                 2,
                                 'from engine import Scheduler\n'
                                 'rows=[[8,10],[0,3]];s=Scheduler(rows);s.reserve(2,3,8);result=rows',
                                 [[8, 10], [0, 3]])],
 'card-triple-strategy': [('physical-multiplicity',
                           2,
                           'from engine import legal\n'
                           "cs=[{'id':x,'amount':5} for x in "
                           "'xyz'];result=[legal(cs,['x','x','y']),legal(cs,['x','y','z'])]",
                           [False, True]),
                          ('absent-card',
                           2,
                           'from engine import legal\n'
                           "cs=[{'id':'x','amount':4},{'id':'y','amount':5},{'id':'z','amount':6}];result=legal(cs,['x','y','absent'])",
                           False),
                          ('deterministic-choice',
                           2,
                           'from engine import choose\n'
                           "result=choose([{'id':x,'amount':5} for x in 'dcba'])",
                           ['a', 'b', 'c']),
                          ('sum-constraint',
                           2,
                           'from engine import legal\n'
                           "result=legal([{'id':'x','amount':4},{'id':'y','amount':5},{'id':'z','amount':7}],['x','y','z'])",
                           False),
                          ('table-order-independent',
                           2,
                           'from engine import choose\n'
                           "cs=[{'id':'x','amount':3},{'id':'y','amount':5},{'id':'z','amount':7}];result=[choose(cs),choose(list(reversed(cs)))]",
                           [['x', 'y', 'z'], ['x', 'y', 'z']]),
                          ('safe-removal',
                           2,
                           'from engine import remove\n'
                           "cs=[{'id':x,'amount':5} for x in "
                           "'wxyz'];result=[remove(cs,['x','y','z']),len(cs)]",
                           [[{'id': 'w', 'amount': 5}], 4]),
                          ('invalid-removal',
                           2,
                           'from engine import remove\n'
                           "cs=[{'id':x,'amount':5} for x in 'xyz']\n"
                           "try:remove(cs,['x','x','y'])\n"
                           'except ValueError:result=len(cs)\n'
                           'else:result=-1',
                           3),
                          ('empty-table', 2, 'from engine import choose\nresult=choose([])', None)],
 'structured-event-logger': [('level-boundaries',
                              2,
                              'from contracts import enabled\n'
                              "result=[enabled('WARN','WARN'),enabled('DEBUG','INFO'),enabled('ERROR','WARN')]",
                              [True, False, True]),
                             ('continue-sinks',
                              2,
                              'from engine import Logger\n'
                              'rows=[]\n'
                              "def fail(_):raise RuntimeError('fail')\n"
                              "l=Logger('INFO',[fail,rows.append,fail],lambda:7);result=[l.emit('INFO','event'),len(rows)]",
                              [[0, 2], 1]),
                             ('sink-copies',
                              2,
                              'from engine import Logger\n'
                              'rows=[]\n'
                              "def mutate(r):r['context']['a'].append(2)\n"
                              "Logger('INFO',[mutate,rows.append],lambda:0).emit('INFO','x',{'a':[1]});result=rows[0]['context']",
                              {'a': [1]}),
                             ('original-context-copy',
                              2,
                              'from engine import Logger\n'
                              "rows=[];ctx={'a':[3]};Logger('INFO',[rows.append],lambda:0).emit('INFO','x',ctx);ctx['a'].append(4);result=rows[0]['context']",
                              {'a': [3]}),
                             ('config-atomic',
                              2,
                              'from engine import Logger\n'
                              "rows=[];l=Logger('WARN',[rows.append],lambda:0)\n"
                              "try:l.configure('DEBUG',[None])\n"
                              'except ValueError:pass\n'
                              "l.emit('INFO','skip');l.emit('WARN','keep');result=[l.level,[r['message'] "
                              'for r in rows]]',
                              ['WARN', ['keep']]),
                             ('unknown-emission',
                              2,
                              'from engine import Logger\n'
                              "rows=[];l=Logger('INFO',[rows.append],lambda:0)\n"
                              "try:l.emit('TRACE','x')\n"
                              'except ValueError:result=rows\n'
                              'else:result=None',
                              []),
                             ('clock-record',
                              2,
                              'from engine import Logger\n'
                              "rows=[];l=Logger('DEBUG',[rows.append],lambda:123);l.emit('ERROR','x',{'user':'é'});result=[rows[0]['timestamp'],rows[0]['context']]",
                              [123, {'user': 'é'}]),
                             ('configuration-next-call',
                              2,
                              'from engine import Logger\n'
                              "a=[];b=[];l=Logger('INFO',[a.append],lambda:0);l.emit('INFO','old');l.configure('ERROR',[b.append]);l.emit('INFO','skip');l.emit('ERROR','new');result=[[r['message'] "
                              "for r in a],[r['message'] for r in b]]",
                              [['old'], ['new']])]}

INVENTORIES = {slug: tuple(Case(*row) for row in rows) for slug, rows in _ROWS.items()}
