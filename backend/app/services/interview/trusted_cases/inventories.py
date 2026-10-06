"""Independent requirements-based cases; deliberately not candidate pytest/vitest tests."""
from . import Case

INVENTORIES = {}
def register(slug, rows):
    INVENTORIES[slug] = tuple(Case(*row) for row in rows)

invoice = """import {canTransition} from './src/statusMachine'; import {handleRequest} from './src/api'; import {resetStore,seedInvoice,getInvoice} from './src/store';"""
statuses=['draft','sent','paid','void']
allowed={('draft','sent'),('draft','void'),('sent','paid'),('sent','void'),('paid','void')}
register('invoice-status-transition',[
 ('legal-graph',4, invoice+"return ['draft','sent','paid','void'].flatMap(a=>['draft','sent','paid','void'].map(b=>canTransition(a,b)));",[ (a,b) in allowed for a in statuses for b in statuses]),
 ('illegal-preserves-paid',4,invoice+"resetStore();seedInvoice({id:'probe',status:'paid',amountCents:197,issuedAt:'2026-01-01',updatedAt:'2026-01-01'});return [handleRequest({method:'POST',path:'/invoices/probe/transition',body:{status:'draft'}}).status,getInvoice('probe').status];",[409,'paid']),
 ('legal-api-transition',2,invoice+"resetStore();seedInvoice({id:'probe',status:'sent',amountCents:197,issuedAt:'2026-01-01',updatedAt:'2026-01-01'});const r=handleRequest({method:'POST',path:'/invoices/probe/transition',body:{status:'paid'}});return [r.status,getInvoice('probe').status,getInvoice('probe').amountCents];",[200,'paid',197]),
 ('missing-distinct',1,invoice+"resetStore();return handleRequest({method:'POST',path:'/invoices/missing/transition',body:{status:'sent'}}).status;",404),
])
order="""from fastapi.testclient import TestClient
from app.main import app
from app import db
from app.models import Order
db.reset()
db.seed(Order('probe','buyer',197))
c=TestClient(app)
"""
register('order-hold-reason',[
 ('reason-persists',4,order+"r=c.post('/orders/probe/hold',json={'hold_reason':'warehouse review 73'});g=c.get('/orders/probe'); result=[r.status_code,r.json().get('hold_reason'),g.json().get('hold_reason'),g.json().get('status'),g.json().get('total_cents')]",[200,'warehouse review 73','warehouse review 73','on_hold',197]),
 ('legacy-null',2,order+"result=c.get('/orders/probe').json().get('hold_reason','MISSING')",None),
 ('release-clears',2,order+"c.post('/orders/probe/hold',json={'hold_reason':'review'});r=c.post('/orders/probe/release');result=[r.json().get('status'),c.get('/orders/probe').json().get('hold_reason','MISSING')]",['open',None]),
 ('missing-order',1,order+"result=c.post('/orders/absent/hold',json={'hold_reason':'x'}).status_code",404),
])
suggest="import {suggest} from './src/suggest';"
register('catalog-suggest-latency',[
 ('ranking-ties',4,suggest+"const rows=[{id:'b',title:'B',category:'x',popularity:7,tokens:['phone']},{id:'a',title:'A',category:'x',popularity:7,tokens:['phone']},{id:'z',title:'Z',category:'phone',popularity:99,tokens:[]},{id:'c',title:'C',category:'phone',popularity:1,tokens:['phone']}];return suggest(rows,' PHONE ').map(r=>r.id);",['c','a','b','z']),
 ('no-match-and-limit',2,suggest+"const rows=Array.from({length:31},(_,i)=>({id:String(i).padStart(3,'0'),title:'a',category:'x',popularity:i,tokens:['word']}));return [suggest(rows,'absent'),suggest(rows,'word',{limit:3}).map(r=>r.id)];",[[],['030','029','028']]),
 ('large-catalog-ranking',3,suggest+"const rows=Array.from({length:10000},(_,i)=>({id:String(i).padStart(5,'0'),title:'item',category:'x',popularity:i,tokens:['word']}));return suggest(rows,'word',{limit:3}).map(r=>r.id);",['09999','09998','09997']),
])
feed="import * as api from './src/api';import * as store from './src/feedStore';store.resetStore();api.seedServer([{id:'a',title:'A',read:false},{id:'b',title:'B',read:false},{id:'c',title:'C',read:true}]);await store.loadFeed();"
register('notification-feed-stale',[
 ('loaded-count',2,feed+"return store.unreadCount();",2),
 ('one-mark',2,feed+"await store.markAsRead('a');return [store.unreadCount(),store.getSnapshot().map(x=>x.read)];",[1,[True,False,True]]),
 ('concurrent-marks',4,feed+"await Promise.all([store.markAsRead('a'),store.markAsRead('b')]);return [store.unreadCount(),store.getSnapshot().map(x=>x.read)];",[0,[True,True,True]]),
 ('already-read',1,feed+"await store.markAsRead('c');return store.unreadCount();",2),
])
labels="import request from 'supertest';import {createApp} from './server/app';import * as db from './server/db';db.resetDb();db.seedWorkspace('ours',[{id:'a',name:'Urgent'},{id:'b',name:'Review'}]);db.seedWorkspace('other',[{id:'foreign',name:'Private'}]);db.seedTicket({id:'ticket',workspaceId:'ours',title:'T'});const api=request(createApp());"
register('workspace-label-propagation',[
 ('persist-roundtrip',4,labels+"const put=await api.put('/tickets/ticket/labels').send({labelIds:['b','a']});const get=await api.get('/tickets/ticket');return [put.status,put.body.labelIds,get.body.labelIds];",[200,['b','a'],['b','a']]),
 ('cross-workspace-rejected',3,labels+"const put=await api.put('/tickets/ticket/labels').send({labelIds:['foreign']});return [put.status,db.getTicket('ticket').labelIds];",[400,[]]),
 ('clear-labels',2,labels+"await api.put('/tickets/ticket/labels').send({labelIds:['a']});await api.put('/tickets/ticket/labels').send({labelIds:[]});return (await api.get('/tickets/ticket')).body.labelIds;",[]),
])
shipment="from shipment_merge.models import ShipmentEvent\nfrom shipment_merge.merge import merge_events,total_quantity\n"
register('shipment-csv-merge',[
 ('same-status-distinct-id',4,shipment+"rows=merge_events([[ShipmentEvent('b','ship','scan','2026-01-02',3)],[ShipmentEvent('a','ship','scan','2026-01-01',2)]])\nresult=[[r.event_id for r in rows],total_quantity('ship')]",[['a','b'],5]),
 ('duplicate-id-once',4,shipment+"e=ShipmentEvent('unique','ship','packed','2026-01-01',7)\nrows=merge_events([[e],[e]])\nresult=[len(rows),total_quantity('ship')]",[1,7]),
 ('independent-shipments',1,shipment+"rows=merge_events([[ShipmentEvent('a','s1','x','2026-01-01',2),ShipmentEvent('b','s2','x','2026-01-01',4)]])\nresult=[total_quantity('s1'),total_quantity('s2')]",[2,4]),
 ('empty-clears-state',1,shipment+"merge_events([[ShipmentEvent('a','s1','x','2026-01-01',2)]])\nresult=[merge_events([]),total_quantity('s1')]",[[],0]),
])
acl="""from fastapi.testclient import TestClient
from app.main import app
from app import db
from app.models import Document
db.reset()
db.seed(Document('ours','tenant_acme','Acme','own'))
db.seed(Document('foreign','tenant_globex','SECRET TITLE','SECRET BODY'))
c=TestClient(app)
h={'Authorization':'Bearer tok_acme'}
"""
register('tenant-document-acl',[
 ('cross-tenant-get',4,acl+"r=c.get('/documents/foreign',headers=h)\nresult=[r.status_code,'SECRET' in r.text]",[404,False]),
 ('cross-tenant-patch',4,acl+"r=c.patch('/documents/foreign',headers=h,json={'body':'attacked'})\nresult=[r.status_code,db.get_by_id('foreign').body]",[404,'SECRET BODY']),
 ('own-list-and-get',2,acl+"result=[c.get('/documents/ours',headers=h).status_code,[r['id'] for r in c.get('/documents',headers=h).json()]]",[200,['ours']]),
 ('unauthenticated',2,acl+"result=[c.get('/documents').status_code,c.get('/documents',headers={'Authorization':'Bearer unknown'}).status_code]",[401,401]),
 ('other-tenant-own',1,acl+"result=c.get('/documents/foreign',headers={'Authorization':'Bearer tok_globex'}).status_code",200),
 ('own-patch',2,acl+"r=c.patch('/documents/ours',headers=h,json={'body':'updated own'})\nresult=[r.status_code,c.get('/documents/ours',headers=h).json().get('body')]",[200,'updated own']),
 ('missing-id',1,acl+"result=c.get('/documents/missing',headers=h).status_code",404),
])
webhook="import {deliverOne,deliverAll} from './src/worker';import {chargeCount,resetCharges} from './src/sideEffects';resetCharges();"
register('webhook-delivery-retry',[
 ('retry-charge-once',4,webhook+"let calls=0;const client={post:async()=>({ok:++calls===3,status:calls===3?200:500})};const ok=await deliverOne({id:'job',url:'http://receiver',payload:{},attempts:0},client,{maxAttempts:3,backoffMs:0});return [ok,calls,chargeCount('job')];",[True,3,1]),
 ('repeat-delivery-idempotent',2,webhook+"const job={id:'same',url:'http://receiver',payload:{},attempts:0};const client={post:async()=>({ok:true,status:200})};await deliverOne(job,client,{maxAttempts:1,backoffMs:0});await deliverOne(job,client,{maxAttempts:1,backoffMs:0});return chargeCount('same');",1),
 ('attempts-bounded',3,webhook+"let calls=0;const ok=await deliverOne({id:'job',url:'http://receiver',payload:{},attempts:0},{post:async()=>{calls++;return {ok:false,status:500}}},{maxAttempts:2,backoffMs:0});return [ok,calls];",[False,2]),
 ('flush-concurrency',3,webhook+"let active=0,max=0;const client={post:async()=>{active++;max=Math.max(max,active);await new Promise(r=>setTimeout(r,5));active--;return {ok:true,status:200}}};const jobs=Array.from({length:19},(_,i)=>({id:'j'+i,url:'http://receiver',payload:{},attempts:0}));const results=await deliverAll(jobs,client,{maxAttempts:1,backoffMs:0});return [results.every(Boolean),max<=5,chargeCount()];",[True,True,19]),
])
pricing="import {quote,applyRules} from './src/pricingEngine';"
register('pricing-rule-extract',[
 ('order-and-rounding',4,pricing+"const rules=[{type:'surcharge_percent',pct:5,code:'s'},{type:'amount_off',cents:17,code:'a'},{type:'percent_off',pct:10,code:'p'}];return [applyRules(105,rules),quote({baseCents:105,rules})];",[{'finalCents':81,'applied':['p','a','s']},{'finalCents':81,'applied':['p','a','s']}]),
 ('floor-zero',2,pricing+"return applyRules(5,[{type:'amount_off',cents:9,code:'discount'}]);",{'finalCents':0,'applied':['discount']}),
 ('empty-preserves',2,pricing+"return applyRules(137,[]);",{'finalCents':137,'applied':[]}),
 ('same-type-order',2,pricing+"return applyRules(100,[{type:'amount_off',cents:2,code:'z'},{type:'amount_off',cents:3,code:'a'}]);",{'finalCents':95,'applied':['a','z']}),
])
period="from proration.period import period_from_iso,contains\nfrom proration.timeutil import parse_utc\nfrom proration.billing import Subscription,proration_credit\np=period_from_iso('2026-01-01T00:00:00Z','2026-02-01T00:00:00Z')\ns=Subscription('probe',3100,p)\n"
register('subscription-proration-boundary',[
 ('end-excluded',4,period+"result=[contains(p,p.end),proration_credit(s,'2026-02-01T00:00:00Z')]",[False,0]),
 ('start-included',2,period+"result=[contains(p,p.start),proration_credit(s,'2026-01-01T00:00:00Z')]",[True,3100]),
 ('mid-period-credit',2,period+"result=proration_credit(s,'2026-01-16T00:00:00Z')",1600),
 ('before-period',2,period+"result=proration_credit(s,'2025-12-31T23:59:59Z')",0),
 ('timezone-equivalence',1,period+"result=contains(p,parse_utc('2026-01-31T19:00:00-05:00'))",False),
])
