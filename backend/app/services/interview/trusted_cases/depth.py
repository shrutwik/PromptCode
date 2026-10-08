"""Independent pressure cases for the featured twenty; no candidate test execution."""
from . import Case

_ROWS = {'warehouse-route-planner': [('badge-revisit',
                              2,
                              'from engine import shortest_route\n'
                              "result=shortest_route(['S.BE','.b##'])",
                              [[0, 0], [0, 1], [1, 1], [0, 1], [0, 2], [0, 3]])],
 'webhook-delivery-retry': [('duplicate-batch-identity',
                             2,
                             "import {deliverAll} from './src/worker';import "
                             '{resetCharges,chargeCount} from '
                             "'./src/sideEffects';resetCharges();let posts=0;const "
                             'ids=["repeat", "repeat", "second", "repeat", "third"];const '
                             "jobs=ids.map(id=>({id,url:'https://test/'+id,payload:{id},attempts:0}));const "
                             'client={post:async()=>{posts++;return {ok:true,status:200};}};const '
                             'outcomes=await '
                             'deliverAll(jobs,client,{maxAttempts:1,backoffMs:0});return '
                             '[outcomes,posts,chargeCount(),chargeCount(ids[0])];',
                             [[True, True, True, True, True], 5, 3, 1])],
 'courier-payment-ledger': [('nonmonotonic-cutoffs',
                             2,
                             'from engine import Ledger\n'
                             "l=Ledger({'d':3600});l.record('a','d',0,4);l.record('b','d',0,9);l.record('c','d',9,11);result=[l.pay_up_to(9),l.pay_up_to(4),l.pay_up_to(11),l.unpaid(),l.total()]",
                             [13, 0, 2, 0, 15])],
 'tenant-document-acl': [('interleaved-scoped-writes',
                          2,
                          'from fastapi.testclient import TestClient\n'
                          'from app.main import app\n'
                          'from app import db\n'
                          'from app.models import Document\n'
                          "db.reset();db.seed(Document('a','tenant_acme','A','original'));db.seed(Document('b','tenant_globex','B','foreign'));c=TestClient(app)\n"
                          "ac={'Authorization':'Bearer tok_acme'};other={'Authorization':'Bearer "
                          "tok_globex'}\n"
                          "first=c.patch('/documents/a',headers=other,json={'body':'attack'}).status_code\n"
                          "own=c.patch('/documents/a',headers=ac,json={'body':'reviewed "
                          "edit'}).status_code\n"
                          "last=c.patch('/documents/a',headers=other,json={'title':'attack'}).status_code\n"
                          "result=[first,own,last,c.get('/documents/a',headers=ac).json()['body'],db.get_by_id('a').title,db.get_by_id('b').body]",
                          [404, 200, 404, 'reviewed edit', 'A', 'foreign'])],
 'worker-job-dispatch': [('queued-permutation',
                          2,
                          'from engine import dispatch\n'
                          "jobs=[['a', 3, 6], ['b', 4, 2], ['c', 5, 1], ['d', 6, 1]];before=[j[:] "
                          'for j in '
                          'jobs];a=dispatch(1,jobs);b=dispatch(1,list(reversed(jobs)));result=[a,b==a,jobs==before]',
                          [[['a', 0, 3, 9], ['b', 0, 9, 11], ['c', 0, 11, 12], ['d', 0, 12, 13]],
                           True,
                           True])],
 'catalog-suggest-latency': [('changed-catalog-parity',
                              2,
                              'import {suggest} from \'./src/suggest\';const rows=[{"id": "b", '
                              '"title": "B", "category": "x", "popularity": 10, "tokens": '
                              '["garden"]}, {"id": "a", "title": "A", "category": "x", '
                              '"popularity": 10, "tokens": ["garden"]}];const '
                              'first=suggest(rows,"garden",{limit:2}).map(p=>p.id);const '
                              'changed=[...rows,{id:\'winner\',title:\'W\',category:"garden",popularity:0,tokens:["garden"]}];const '
                              'second=suggest(changed,"garden",{limit:2}).map(p=>p.id);const '
                              'prefix=suggest(changed,"garden",{limit:1}).map(p=>p.id);return '
                              '[first,second,prefix,rows.length];',
                              [['a', 'b'], ['winner', 'a'], ['winner'], 2])],
 'bounded-recency-cache': [('invalid-resize-preserves',
                            2,
                            'from engine import Cache\n'
                            'c=Cache(3)\n'
                            "for i,k in enumerate(['a', 'b', 'c']):c.put(k,i+1)\n"
                            "c.get('b');before=c.keys()\n"
                            'try:c.resize(-1)\n'
                            'except ValueError:pass\n'
                            "else:raise RuntimeError('accepted invalid size')\n"
                            "unchanged=c.keys()==before;c.put('d',9);result=[unchanged,c.keys(),c.get('b'),c.get('a')]",
                            [True, ['c', 'b', 'd'], 2, None])],
 'unique-word-selection': [('overlap-trap',
                            2,
                            'from engine import choose,valid\n'
                            "words=['xy', 'za', 'xzw', 'bc', "
                            "''];before=words[:];indices=choose(words);result=[indices,valid(words,indices),words==before]",
                            [[0, 1, 3], True, True])],
 'service-impact-analysis': [('normalized-delete-closure',
                              2,
                              'from engine import impacted\n'
                              "w={'api':['/project/api/src'],'apis':['/project/apis'],'worker':['/project/worker']};d={'worker':['api']};edits=[('/project/api/',True),('/project//api/',True)]\n"
                              "a=impacted(w,d,edits);b=impacted(w,d,list(reversed(edits)));result=[a,b,impacted(w,d,[('/',True)])]",
                              [['api', 'worker'], ['api', 'worker'], ['api', 'apis', 'worker']])],
 'canvas-document-editor': [('branch-clears-redo',
                             2,
                             "import {createStore} from './src/designStore';const "
                             "s=createStore();s.add({id:'a',type:'rect',x:3,y:2,width:3,height:4,color:'red'});s.beginDrag(0,0,1);s.moveDrag(7,0);s.endDrag();s.undo();s.color('green');s.redo();return "
                             's.getSnapshot().shapes.map(v=>[v.x,v.color]);',
                             [[3, 'green']])],
 'shipment-csv-merge': [('unrelated-shipment-invariance',
                         2,
                         'from shipment_merge.models import ShipmentEvent\n'
                         'from shipment_merge.merge import merge_events,total_quantity\n'
                         "a=ShipmentEvent('a','one','scan','2026-01-01',5);b=ShipmentEvent('b','one','scan','2026-01-02',-1);c=ShipmentEvent('c','two','scan','2026-01-01',11)\n"
                         "base=merge_events([[a,b]]);before=total_quantity('one');merged=merge_events([[c,a],[b,a]]);result=[[e.event_id "
                         'for e in merged if '
                         "e.shipment_id=='one'],before,total_quantity('one'),total_quantity('two')]",
                         [['a', 'b'], 4, 4, 11])],
 'expression-cost-analysis': [('alias-dead-work',
                               2,
                               'from engine import analyze\n'
                               "p=['unused=u/v', 'a=x+y', 'b=a', 'c=b*z', 'res=a+c'];costs={'+': "
                               "3, '-': 1, '*': 5, '/': "
                               '7};result=[analyze(p,costs),analyze(p,costs,True)]',
                               [[18, 3], [11, 3]])],
 'structured-event-logger': [('rejected-config-clock',
                              2,
                              'from engine import Logger\n'
                              'records=[];ticks=[]\n'
                              'def clock():ticks.append(1);return 88\n'
                              "l=Logger('WARN',[records.append],clock)\n"
                              "try:l.configure('DEBUG',[None])\n"
                              'except ValueError:pass\n'
                              "else:raise RuntimeError('accepted invalid config')\n"
                              "l.emit('DEBUG','hidden');failures=l.emit('ERROR','visible');result=[len(ticks),[r['level'] "
                              "for r in records],[r['timestamp'] for r in records],failures]",
                              [1, ['ERROR'], [88], []])],
 'extensible-hand-comparison': [('comparison-order-laws',
                                 2,
                                 'from engine import compare\n'
                                 "a=['AH', 'KD', 'QS'];b=['9H', '9C', '2D'];c=['3H', '3C', "
                                 "'3D'];result=[compare(a,b),compare(b,c),compare(a,c),compare(c,a)]",
                                 [-1, -1, -1, 1])],
 'room-reservation-scheduler': [('failed-reserve-preserves',
                                 2,
                                 'from engine import Scheduler\n'
                                 's=Scheduler([(7,9)]);before=s.snapshot();miss=s.reserve(2,8,10);same=s.snapshot()==before;hit=s.reserve(2,5,7);result=[miss,same,hit,s.snapshot()]',
                                 [None, True, [5, 7], [[5, 7], [7, 9]]])],
 'notification-feed-stale': [('mixed-success-failure',
                              2,
                              "import {seedServer} from './src/api';import "
                              '{resetStore,loadFeed,markAsRead,getSnapshot,unreadCount} from '
                              '\'./src/feedStore\';resetStore();seedServer([{"id": "left", '
                              '"title": "left", "read": false}, {"id": "right", "title": "right", '
                              '"read": false}]);await loadFeed();const settled=await '
                              "Promise.allSettled([markAsRead('left'),markAsRead('missing'),markAsRead('right')]);return "
                              '[unreadCount(),getSnapshot().map(n=>n.read),settled.map(r=>r.status)];',
                              [0, [True, True], ['fulfilled', 'rejected', 'fulfilled']])],
 'runway-event-scheduler': [('cancel-during-closure',
                             2,
                             'from engine import schedule\n'
                             "result=schedule([{'id': 'A', 'arrival': 3, 'duration': 4, 'kind': "
                             "'takeoff'}, {'id': 'B', 'arrival': 3, 'duration': 4, 'kind': "
                             "'landing'}],[(4, 9)],{'B':7})",
                             [['A', 9, 13]])],
 'movie-search-routing': [('combined-filter-page-http',
                           2,
                           "import request from 'supertest';import {createApp} from "
                           '\'./src/api\';const rows=[{"id": "n", "title": "Report", "genre": '
                           '"action", "year": 2018}, {"id": "m", "title": "Report", "genre": '
                           '"action", "year": 2020}, {"id": "k", "title": "Report", "genre": '
                           '"action", "year": 2024}, {"id": "i", "title": "Report", "genre": '
                           '"action", "year": 2023}, {"id": "h", "title": "Report", "genre": '
                           '"other", "year": 2022}, {"id": "g", "title": "Report", "genre": '
                           '"action", "year": 2022}];const before=JSON.stringify(rows);const '
                           'r=await '
                           "request(createApp(rows)).get('/api/movies?q=report&genre=action&minYear=2020&page=2');return "
                           '[r.status,r.body.rows.map((m:any)=>m.id),r.body.total,JSON.stringify(rows)===before];',
                           [200, ['k', 'm'], 4, True])],
 'invoice-status-transition': [('terminal-sequence-preserves',
                                2,
                                "import {handleRequest} from './src/api';import "
                                '{resetStore,seedInvoice,getInvoice} from '
                                "'./src/store';resetStore();seedInvoice({id:'chain',customerId:'c',status:'draft',amountCents:1703,issuedAt:'2026-01-01',updatedAt:'2026-01-01'});const "
                                "statuses=['sent','paid','void'].map(status=>handleRequest({method:'POST',path:'/invoices/chain/transition',body:{status}}).status);const "
                                "before=JSON.stringify(getInvoice('chain'));const "
                                "denied=handleRequest({method:'POST',path:'/invoices/chain/transition',body:{status:'paid'}}).status;return "
                                "[statuses,denied,getInvoice('chain').status,getInvoice('chain').amountCents,JSON.stringify(getInvoice('chain'))===before];",
                                [[200, 200, 200], 409, 'void', 1703, True])],
 'transactional-wallet-transfer': [('failed-receipt-reusable',
                                    2,
                                    'from engine import Wallet,TransferError\n'
                                    'from tempfile import TemporaryDirectory\n'
                                    'with TemporaryDirectory() as d:\n'
                                    " w=Wallet(d+'/ledger.db',{'a':120,'b':0})\n"
                                    " try:w.transfer('r','a','b',40,'after_receipt')\n"
                                    ' except RuntimeError:pass\n'
                                    ' '
                                    "r=w.transfer('r','a','b',23);other=Wallet(d+'/ledger.db');again=other.transfer('r','a','b',23)\n"
                                    " try:other.transfer('r','a','b',40)\n"
                                    ' except TransferError as e:status=e.status\n'
                                    ' result=[r==again,other.balances(),status]',
                                    [True, {'a': 97, 'b': 23}, 409])]}
INVENTORIES = {slug:tuple(Case(*row) for row in rows) for slug,rows in _ROWS.items()}
