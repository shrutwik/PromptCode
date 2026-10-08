"""Independent behavioral observation cases for ranked library additions."""

_ROWS = {'extensible-hand-comparison': [('ten-rank',
                                 2,
                                 "from engine import parse_card\nresult=parse_card('10D')",
                                 [10, 'D']),
                                ('ace-rank',
                                 2,
                                 "from engine import parse_card\nresult=parse_card('AC')",
                                 [14, 'C']),
                                ('category',
                                 2,
                                 'from engine import compare\n'
                                 "result=compare(['3S','3H','3D'],['AS','AH','KC'])",
                                 1),
                                ('kicker',
                                 2,
                                 'from engine import compare\n'
                                 "result=compare(['8S','8H','QC'],['8D','8C','JS'])",
                                 1),
                                ('suit-neutral',
                                 2,
                                 'from engine import compare\n'
                                 "result=compare(['10S','9H','2D'],['10C','9D','2H'])",
                                 0),
                                ('variant',
                                 2,
                                 'from engine import compare\n'
                                 "result=compare(['3S','3H','3D'],['AS','AH','KC'],['triple','distinct','pair'])",
                                 -1),
                                ('duplicate',
                                 2,
                                 'from engine import hand_key\n'
                                 "try:hand_key(['AH','AH','2D'])\n"
                                 'except ValueError:result=True\n'
                                 'else:result=False',
                                 True),
                                ('invalid-order',
                                 2,
                                 'from engine import hand_key\n'
                                 "try:hand_key(['AH','KH','2D'],['pair','triple','pair'])\n"
                                 'except ValueError:result=True\n'
                                 'else:result=False',
                                 True)],
 'runway-event-scheduler': [('boundary',
                             2,
                             'from engine import overlaps\nresult=overlaps(2,5,5,10)',
                             False),
                            ('priority',
                             2,
                             'from engine import schedule\n'
                             "result=schedule([dict(id='T',arrival=0,duration=1,kind='takeoff'),dict(id='L',arrival=0,duration=2,kind='landing')])",
                             [['L', 0, 2], ['T', 2, 3]]),
                            ('emergency',
                             2,
                             'from engine import schedule\n'
                             "result=schedule([dict(id='L',arrival=0,duration=2,kind='landing'),dict(id='X',arrival=0,duration=1,kind='takeoff',emergency=True)])",
                             [['X', 0, 1], ['L', 1, 3]]),
                            ('no-preemption',
                             2,
                             'from engine import schedule\n'
                             "result=schedule([dict(id='A',arrival=0,duration=4,kind='takeoff'),dict(id='X',arrival=1,duration=1,kind='landing',emergency=True)])",
                             [['A', 0, 4], ['X', 4, 5]]),
                            ('closure-fit',
                             2,
                             'from engine import schedule\n'
                             "result=schedule([dict(id='A',arrival=3,duration=3,kind='landing')],[(5,9)])",
                             [['A', 9, 12]]),
                            ('closure-touch',
                             2,
                             'from engine import schedule\n'
                             "result=schedule([dict(id='A',arrival=2,duration=3,kind='landing')],[(5,9)])",
                             [['A', 2, 5]]),
                            ('cancel-at-dispatch',
                             2,
                             'from engine import schedule\n'
                             "result=schedule([dict(id='A',arrival=0,duration=3,kind='landing'),dict(id='B',arrival=0,duration=2,kind='takeoff')],cancellations={'B':3})",
                             [['A', 0, 3]]),
                            ('reselect',
                             2,
                             'from engine import schedule\n'
                             "result=schedule([dict(id='A',arrival=3,duration=4,kind='takeoff'),dict(id='X',arrival=6,duration=1,kind='landing',emergency=True)],[(5,9)])",
                             [['X', 9, 10], ['A', 10, 14]])],
 'transactional-wallet-transfer': [('move',
                                    2,
                                    'from engine import Wallet\n'
                                    'from tempfile import TemporaryDirectory\n'
                                    'with TemporaryDirectory() as d:\n'
                                    ' '
                                    "w=Wallet(d+'/l.db',{'x':90,'y':0});w.transfer('m','x','y',20);result=w.balances()",
                                    {'x': 70, 'y': 20}),
                                   ('durable-replay',
                                    2,
                                    'from engine import Wallet\n'
                                    'from tempfile import TemporaryDirectory\n'
                                    'with TemporaryDirectory() as d:\n'
                                    ' '
                                    "w=Wallet(d+'/l.db',{'x':90,'y':0});a=w.transfer('m','x','y',20);w.transfer('n','x','y',5);v=Wallet(d+'/l.db');result=[v.transfer('m','x','y',20)==a,v.balances()]",
                                    [True, {'x': 65, 'y': 25}]),
                                   ('conflict',
                                    2,
                                    'from engine import Wallet,TransferError\n'
                                    'from tempfile import TemporaryDirectory\n'
                                    'with TemporaryDirectory() as d:\n'
                                    ' '
                                    "w=Wallet(d+'/l.db',{'x':90,'y':0});w.transfer('m','x','y',20)\n"
                                    " try:w.transfer('m','x','y',21)\n"
                                    ' except TransferError as e:result=[e.status,w.balances()]',
                                    [409, {'x': 70, 'y': 20}]),
                                   ('insufficient',
                                    2,
                                    'from engine import Wallet,TransferError\n'
                                    'from tempfile import TemporaryDirectory\n'
                                    'with TemporaryDirectory() as d:\n'
                                    " w=Wallet(d+'/l.db',{'x':9,'y':0})\n"
                                    " try:w.transfer('m','x','y',10)\n"
                                    ' except TransferError as e:result=[e.status,w.balances()]',
                                    [422, {'x': 9, 'y': 0}]),
                                   ('rollback-debit',
                                    2,
                                    'from engine import Wallet\n'
                                    'from tempfile import TemporaryDirectory\n'
                                    'with TemporaryDirectory() as d:\n'
                                    " w=Wallet(d+'/l.db',{'x':90,'y':0})\n"
                                    " try:w.transfer('m','x','y',20,'after_debit')\n"
                                    ' except RuntimeError:pass\n'
                                    ' result=w.balances()',
                                    {'x': 90, 'y': 0}),
                                   ('rollback-receipt',
                                    2,
                                    'from engine import Wallet\n'
                                    'from tempfile import TemporaryDirectory\n'
                                    'with TemporaryDirectory() as d:\n'
                                    " w=Wallet(d+'/l.db',{'x':90,'y':0})\n"
                                    " try:w.transfer('m','x','y',20,'after_receipt')\n"
                                    ' except RuntimeError:pass\n'
                                    " result=[w.transfer('m','x','y',20)['balances'],w.balances()]",
                                    [{'x': 70, 'y': 20}, {'x': 70, 'y': 20}]),
                                   ('no-overdraw',
                                    2,
                                    'from engine import Wallet,TransferError\n'
                                    'from tempfile import TemporaryDirectory\n'
                                    'from concurrent.futures import ThreadPoolExecutor\n'
                                    'with TemporaryDirectory() as d:\n'
                                    " Wallet(d+'/l.db',{'x':90,'y':0,'z':0})\n"
                                    ' def send(dest):\n'
                                    "  try:Wallet(d+'/l.db').transfer(dest,'x',dest,70);return "
                                    '200\n'
                                    '  except TransferError as e:return e.status\n'
                                    ' with ThreadPoolExecutor(2) as '
                                    "p:statuses=list(p.map(send,['y','z']))\n"
                                    " result=[sorted(statuses),Wallet(d+'/l.db').balances()['x']]",
                                    [[200, 422], 20]),
                                   ('http-status',
                                    2,
                                    'from engine import Wallet\n'
                                    'from app import create_app\n'
                                    'from tempfile import TemporaryDirectory\n'
                                    'from fastapi.testclient import TestClient\n'
                                    'with TemporaryDirectory() as d:\n'
                                    ' '
                                    "c=TestClient(create_app(Wallet(d+'/l.db',{'x':90,'y':0})));p=dict(id='m',source='x',destination='y',amount=20);result=[c.post('/transfers',json=p).status_code,c.post('/transfers',json={**p,'amount':21}).status_code]",
                                    [200, 409])],
 'canvas-document-editor': [('zoom-drag',
                             2,
                             "import {createStore} from './src/designStore';const "
                             "s=createStore();s.add({id:'a',type:'rect',x:1,y:2,width:3,height:4,color:'red'});s.beginDrag(0,0,2);s.moveDrag(20,10);s.endDrag();return "
                             's.getSnapshot().shapes.map(x=>[x.x,x.y]);',
                             [[11, 7]]),
                            ('only-selection',
                             2,
                             "import {createStore} from './src/designStore';const "
                             's=createStore();for(const id of '
                             "['a','b'])s.add({id,type:'rect',x:0,y:0,width:3,height:4,color:'red'});s.beginDrag(0,0,1);s.moveDrag(5,2);s.endDrag();return "
                             's.getSnapshot().shapes.map(x=>[x.id,x.x,x.y]);',
                             [['a', 0, 0], ['b', 5, 2]]),
                            ('drag-history',
                             2,
                             "import {createStore} from './src/designStore';const "
                             "s=createStore();s.add({id:'a',type:'rect',x:0,y:0,width:3,height:4,color:'red'});s.beginDrag(0,0,1);s.moveDrag(2,0);s.moveDrag(5,0);s.endDrag();s.undo();const "
                             'a=s.getSnapshot().shapes[0].x;s.redo();return '
                             '[a,s.getSnapshot().shapes[0].x];',
                             [0, 5]),
                            ('round-trip',
                             2,
                             "import {createStore} from './src/designStore';const "
                             "s=createStore();s.add({id:'z',type:'ellipse',x:2,y:3,width:7,height:9,color:'blue'});const "
                             'v=createStore();v.load(s.save());return v.getSnapshot();',
                             {'version': 1,
                              'shapes': [{'id': 'z',
                                          'type': 'ellipse',
                                          'x': 2,
                                          'y': 3,
                                          'width': 7,
                                          'height': 9,
                                          'color': 'blue'}],
                              'selected': 'z'}),
                            ('invalid-preserves',
                             2,
                             "import {createStore} from './src/designStore';const "
                             "s=createStore();s.add({id:'a',type:'rect',x:0,y:0,width:3,height:4,color:'red'});const "
                             "before=s.save();try{s.load(JSON.stringify({version:1,shapes:[{id:'x',type:'rect',x:0,y:0,width:0,height:2,color:'red'}],selected:null}));}catch{}return "
                             's.save()===before;',
                             True),
                            ('delete-selection',
                             2,
                             "import {createStore} from './src/designStore';const "
                             "s=createStore();s.add({id:'a',type:'rect',x:0,y:0,width:3,height:4,color:'red'});s.remove();return "
                             '[s.getSnapshot().shapes.length,s.getSnapshot().selected];',
                             [0, None]),
                            ('style-isolated',
                             2,
                             "import {createStore} from './src/designStore';const "
                             's=createStore();for(const id of '
                             "['a','b'])s.add({id,type:'rect',x:0,y:0,width:3,height:4,color:'red'});s.color('blue');return "
                             's.getSnapshot().shapes.map(x=>x.color);',
                             ['red', 'blue']),
                            ('duplicate-reject',
                             2,
                             "import {createStore} from './src/designStore';const "
                             "s=createStore();const a={id:'a',type:'rect' as "
                             "const,x:0,y:0,width:3,height:4,color:'red'};s.add(a);try{s.add(a);return "
                             'false;}catch{return s.getSnapshot().shapes.length===1;}',
                             True)],
 'movie-search-routing': [('and-filters',
                           2,
                           "import {search,parseQuery,MOVIES} from './src/queryState';return "
                           "search(MOVIES,parseQuery('?q=orbit&genre=drama'));",
                           {'rows': [{'id': 'A', 'title': 'Orbit', 'genre': 'drama', 'year': 2020}],
                            'total': 1}),
                          ('year',
                           2,
                           "import {search,parseQuery,MOVIES} from './src/queryState';return "
                           "search(MOVIES,parseQuery('?q=orbit&minYear=2021')).rows.map(m=>m.id);",
                           ['B']),
                          ('literal-query',
                           2,
                           "import {parseQuery,toQuery} from './src/queryState';const "
                           "a=parseQuery('?q=100%2525');return [a.q,parseQuery(toQuery(a)).q];",
                           ['100%25', '100%25']),
                          ('page-after-filter',
                           2,
                           "import {search,parseQuery,MOVIES} from './src/queryState';return "
                           "search([...MOVIES].reverse(),parseQuery('?page=2')).rows.map(m=>m.id);",
                           ['C', 'D']),
                          ('reset-page',
                           2,
                           "import {changeFilters,parseQuery} from './src/queryState';return "
                           "changeFilters(parseQuery('?q=x&page=9'),{genre:'drama'});",
                           {'q': 'x', 'genre': 'drama', 'minYear': None, 'page': 1}),
                          ('invalid-page',
                           2,
                           'import {parseQuery} from '
                           "'./src/queryState';try{parseQuery('?page=0');return "
                           'false;}catch{return true;}',
                           True),
                          ('detail-http',
                           2,
                           "import request from 'supertest';import {createApp} from "
                           "'./src/api';const app=createApp();return [(await "
                           "request(app).get('/api/movies/D')).body.title,(await "
                           "request(app).get('/api/movies/nope')).status];",
                           ['A&B', 404]),
                          ('direct-shell',
                           2,
                           "import request from 'supertest';import {createApp} from "
                           "'./src/api';const r=await request(createApp()).get('/movies/A');return "
                           '[r.status,r.text.includes(\'id="root"\'),r.headers[\'content-type\'].startsWith(\'text/html\')];',
                           [200, True, True])]}

from . import Case

INVENTORIES = {slug:tuple(Case(*row) for row in rows) for slug,rows in _ROWS.items()}
