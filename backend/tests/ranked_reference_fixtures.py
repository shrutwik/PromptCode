"""Reviewed test-only repairs and wrong alternatives for missing ranked families."""

REFERENCE_SOURCES = {'extensible-hand-comparison': {'engine.py': 'RANKS={str(n):n for n in range(2,11)} | '
                                             "{'J':11,'Q':12,'K':13,'A':14}\n"
                                             "DEFAULT=('distinct','pair','triple')\n"
                                             'def parse_card(card):\n'
                                             '    if not isinstance(card,str) or len(card)<2 or '
                                             "card[-1] not in 'CDHS' or card[:-1] not in "
                                             "RANKS:raise ValueError('invalid card')\n"
                                             '    return RANKS[card[:-1]],card[-1]\n'
                                             'def hand_key(hand,order=DEFAULT):\n'
                                             '    if not isinstance(order,(list,tuple)) or '
                                             'len(order)!=3 or any(not isinstance(c,str) for c in '
                                             'order) or set(order)!=set(DEFAULT):raise '
                                             "ValueError('invalid rules')\n"
                                             '    if not isinstance(hand,(list,tuple)) or '
                                             "len(hand)!=3:raise ValueError('three cards "
                                             "required')\n"
                                             '    cards=[parse_card(c) for c in hand]\n'
                                             '    if len(set(cards))!=3:raise '
                                             "ValueError('duplicate physical card')\n"
                                             '    ranks=sorted([c[0] for c in '
                                             'cards],reverse=True)\n'
                                             '    if '
                                             "ranks[0]==ranks[2]:category='triple';key=(ranks[0],)\n"
                                             '    elif len(set(ranks))==2:\n'
                                             '        pair=next(r for r in ranks if '
                                             "ranks.count(r)==2);category='pair';key=(pair,next(r "
                                             'for r in ranks if r!=pair))\n'
                                             "    else:category='distinct';key=tuple(ranks)\n"
                                             '    return (order.index(category),*key)\n'
                                             'def compare(left,right,order=DEFAULT):\n'
                                             '    a,b=hand_key(left,order),hand_key(right,order)\n'
                                             '    return (a>b)-(a<b)\n'},
 'runway-event-scheduler': {'engine.py': 'def overlaps(a,b,c,d):return a<d and c<b\n'
                                         'def schedule(flights,closures=(),cancellations=None):\n'
                                         '    from copy import deepcopy\n'
                                         '    '
                                         'flights=deepcopy(flights);closures=sorted(list(closures));cancellations=dict(cancellations '
                                         'or {})\n'
                                         '    ids=[]\n'
                                         '    for f in flights:\n'
                                         "        if not isinstance(f.get('id'),str) or not "
                                         "f['id'] or f['id'] in ids:raise ValueError('invalid "
                                         "id')\n"
                                         "        ids.append(f['id'])\n"
                                         "        if type(f.get('arrival')) is not int or "
                                         "f['arrival']<0 or type(f.get('duration')) is not int or "
                                         "f['duration']<=0:raise ValueError('invalid timing')\n"
                                         "        if f.get('kind') not in ('landing','takeoff') or "
                                         "type(f.get('emergency',False)) is not bool:raise "
                                         "ValueError('invalid policy')\n"
                                         '    if any(k not in ids or type(v) is not int or v<0 for '
                                         "k,v in cancellations.items()):raise ValueError('invalid "
                                         "cancellation')\n"
                                         '    if any(len(x)!=2 or any(type(v) is not int for v in '
                                         'x) or not 0<=x[0]<x[1] for x in closures):raise '
                                         "ValueError('invalid closure')\n"
                                         '    now=0;result=[];waiting=flights[:]\n'
                                         '    while waiting:\n'
                                         '        waiting=[f for f in waiting if '
                                         "cancellations.get(f['id'],float('inf'))>now]\n"
                                         '        if not waiting:break\n'
                                         "        ready=[f for f in waiting if f['arrival']<=now]\n"
                                         "        if not ready:now=min(f['arrival'] for f in "
                                         'waiting);continue\n'
                                         '        f=min(ready,key=lambda f:(0 if '
                                         "f.get('emergency',False) else 1 if f['kind']=='landing' "
                                         "else 2,f['arrival'],f['id']))\n"
                                         '        blocked=next((end for start,end in closures if '
                                         'end>now and '
                                         "overlaps(now,now+f['duration'],start,end)),None)\n"
                                         '        if blocked is not None:now=blocked;continue\n'
                                         '        '
                                         "result.append([f['id'],now,now+f['duration']]);now+=f['duration'];waiting.remove(f)\n"
                                         '    return result\n'},
 'transactional-wallet-transfer': {'engine.py': 'import sqlite3,json\n'
                                                'class TransferError(ValueError):\n'
                                                '    def '
                                                '__init__(self,status,message):super().__init__(message);self.status=status\n'
                                                'class Wallet:\n'
                                                '    def __init__(self,path,accounts=None):\n'
                                                '        self.path=str(path)\n'
                                                '        with self.connection() as db:\n'
                                                "            db.execute('CREATE TABLE IF NOT "
                                                'EXISTS accounts(id TEXT PRIMARY KEY,balance '
                                                "INTEGER NOT NULL CHECK(balance>=0))')\n"
                                                "            db.execute('CREATE TABLE IF NOT "
                                                'EXISTS receipts(id TEXT PRIMARY KEY,payload TEXT '
                                                "NOT NULL,result TEXT NOT NULL)')\n"
                                                '            for id,balance in (accounts or '
                                                '{}).items():\n'
                                                '                if not isinstance(id,str) or not '
                                                'id or type(balance) is not int or balance<0:raise '
                                                "ValueError('invalid seed')\n"
                                                "                db.execute('INSERT OR IGNORE INTO "
                                                "accounts VALUES (?,?)',(id,balance))\n"
                                                '    def connection(self):return '
                                                'sqlite3.connect(self.path,timeout=10)\n'
                                                '    def balances(self):\n'
                                                '        db=self.connection()\n'
                                                "        try:return dict(db.execute('SELECT "
                                                "id,balance FROM accounts ORDER BY id'))\n"
                                                '        finally:db.close()\n'
                                                '    def '
                                                'transfer(self,id,source,destination,amount,fail_at=None):\n'
                                                '        if any(not isinstance(x,str) or not x for '
                                                'x in (id,source,destination)) or '
                                                'source==destination or type(amount) is not int or '
                                                "amount<=0:raise TransferError(400,'invalid "
                                                "transfer')\n"
                                                '        if fail_at not in '
                                                "(None,'after_debit','after_receipt'):raise "
                                                "TransferError(400,'invalid failure hook')\n"
                                                '        '
                                                'payload=json.dumps([source,destination,amount]);db=self.connection()\n'
                                                '        try:\n'
                                                "            db.execute('BEGIN IMMEDIATE')\n"
                                                "            receipt=db.execute('SELECT "
                                                'payload,result FROM receipts WHERE '
                                                "id=?',(id,)).fetchone()\n"
                                                '            if receipt:\n'
                                                '                if receipt[0]!=payload:raise '
                                                "TransferError(409,'id conflict')\n"
                                                '                '
                                                'result=json.loads(receipt[1]);db.commit();return '
                                                'result\n'
                                                "            balances=dict(db.execute('SELECT "
                                                'id,balance FROM accounts WHERE id IN '
                                                "(?,?)',(source,destination)))\n"
                                                '            if len(balances)!=2:raise '
                                                "TransferError(404,'account not found')\n"
                                                '            if balances[source]<amount:raise '
                                                "TransferError(422,'insufficient funds')\n"
                                                "            db.execute('UPDATE accounts SET "
                                                "balance=balance-? WHERE id=?',(amount,source))\n"
                                                "            if fail_at=='after_debit':raise "
                                                "RuntimeError('injected failure')\n"
                                                "            db.execute('UPDATE accounts SET "
                                                'balance=balance+? WHERE '
                                                "id=?',(amount,destination))\n"
                                                '            '
                                                "result={'id':id,'source':source,'destination':destination,'amount':amount,'balances':{source:balances[source]-amount,destination:balances[destination]+amount}}\n"
                                                "            db.execute('INSERT INTO receipts "
                                                "VALUES (?,?,?)',(id,payload,json.dumps(result)))\n"
                                                "            if fail_at=='after_receipt':raise "
                                                "RuntimeError('injected failure')\n"
                                                '            db.commit();return result\n'
                                                '        except Exception:db.rollback();raise\n'
                                                '        finally:db.close()\n',
                                   'app.py': 'from fastapi import FastAPI,Request\n'
                                             'from fastapi.responses import JSONResponse\n'
                                             'from engine import TransferError\n'
                                             '\n'
                                             'def create_app(wallet):\n'
                                             '    app=FastAPI()\n'
                                             "    @app.post('/transfers')\n"
                                             '    async def transfer(request:Request):\n'
                                             '        try:\n'
                                             '            p=await request.json()\n'
                                             '            if not isinstance(p,dict) or '
                                             "set(p)!={'id','source','destination','amount'}:raise "
                                             "TransferError(400,'invalid body')\n"
                                             '            return '
                                             "wallet.transfer(p['id'],p['source'],p['destination'],p['amount'])\n"
                                             '        except TransferError as e:return '
                                             "JSONResponse({'detail':str(e)},status_code=e.status)\n"
                                             '        except (ValueError,TypeError):return '
                                             "JSONResponse({'detail':'invalid "
                                             "JSON'},status_code=400)\n"
                                             '    return app\n'},
 'canvas-document-editor': {'src/designStore.ts': 'export type '
                                                  "Shape={id:string,type:'rect'|'ellipse',x:number,y:number,width:number,height:number,color:string};\n"
                                                  'export type '
                                                  'Design={version:1,shapes:Shape[],selected:string|null};\n'
                                                  'const '
                                                  'clone=<T,>(x:T):T=>JSON.parse(JSON.stringify(x));\n'
                                                  'export function validate(value:any):Design {\n'
                                                  '  '
                                                  'if(!value||value.version!==1||!Array.isArray(value.shapes))throw '
                                                  "new Error('Invalid document');\n"
                                                  '  const ids=new Set<string>();\n'
                                                  '  for(const s of value.shapes){\n'
                                                  '    if(!s||typeof '
                                                  "s.id!=='string'||!s.id||ids.has(s.id)||!['rect','ellipse'].includes(s.type)||!['x','y','width','height'].every(k=>typeof "
                                                  "s[k]==='number'&&Number.isFinite(s[k]))||s.width<=0||s.height<=0||typeof "
                                                  "s.color!=='string'||!s.color)throw new "
                                                  "Error('Invalid shape');\n"
                                                  '    ids.add(s.id);\n'
                                                  '  }\n'
                                                  '  '
                                                  'if(value.selected!==null&&!ids.has(value.selected))throw '
                                                  "new Error('Invalid selection');\n"
                                                  '  return '
                                                  'clone({version:1,shapes:value.shapes,selected:value.selected});\n'
                                                  '}\n'
                                                  'export function createStore(){\n'
                                                  ' let '
                                                  'state:Design={version:1,shapes:[],selected:null};let '
                                                  'past:Design[]=[];let future:Design[]=[];\n'
                                                  ' let '
                                                  'drag:{before:Design,x:number,y:number,zoom:number}|null=null;const '
                                                  'listeners=new Set<()=>void>();\n'
                                                  ' const emit=()=>listeners.forEach(f=>f());\n'
                                                  ' const '
                                                  'commit=(next:Design)=>{past.push(clone(state));future=[];state=next;emit();};\n'
                                                  ' const api={\n'
                                                  '  getSnapshot:()=>state,\n'
                                                  '  '
                                                  'subscribe:(f:()=>void)=>{listeners.add(f);return '
                                                  '()=>{listeners.delete(f);};},\n'
                                                  '  add:(shape:Shape)=>{const '
                                                  'next=validate({...state,shapes:[...state.shapes,shape],selected:shape.id});commit(next);},\n'
                                                  '  '
                                                  'select:(id:string|null)=>{if(id!==null&&!state.shapes.some(s=>s.id===id))throw '
                                                  "new Error('Unknown "
                                                  "shape');state={...state,selected:id};emit();},\n"
                                                  '  color:(color:string)=>{if(typeof '
                                                  "color!=='string'||!color)throw new "
                                                  "Error('Invalid "
                                                  "color');if(state.selected!==null)commit({...state,shapes:state.shapes.map(s=>s.id===state.selected?{...s,color}:s)});},\n"
                                                  '  '
                                                  'remove:()=>{if(state.selected!==null)commit({...state,shapes:state.shapes.filter(s=>s.id!==state.selected),selected:null});},\n'
                                                  '  '
                                                  'beginDrag:(x:number,y:number,zoom:number)=>{if(!Number.isFinite(zoom)||zoom<=0)throw '
                                                  "new Error('Invalid "
                                                  "zoom');if(state.selected!==null)drag={before:clone(state),x,y,zoom};},\n"
                                                  '  '
                                                  'moveDrag:(x:number,y:number)=>{if(!drag)return;const '
                                                  'dx=(x-drag.x)/drag.zoom,dy=(y-drag.y)/drag.zoom;state={...drag.before,shapes:drag.before.shapes.map(s=>s.id===drag!.before.selected?{...s,x:s.x+dx,y:s.y+dy}:s)};emit();},\n'
                                                  '  '
                                                  'endDrag:()=>{if(!drag)return;if(JSON.stringify(state)!==JSON.stringify(drag.before)){past.push(drag.before);future=[];}drag=null;},\n'
                                                  '  '
                                                  'undo:()=>{if(!past.length)return;future.push(clone(state));state=past.pop()!;drag=null;emit();},\n'
                                                  '  '
                                                  'redo:()=>{if(!future.length)return;past.push(clone(state));state=future.pop()!;drag=null;emit();},\n'
                                                  '  save:()=>JSON.stringify(state),\n'
                                                  '  load:(raw:string)=>{const '
                                                  'next=validate(JSON.parse(raw));commit(next);drag=null;}\n'
                                                  ' };return api;\n'
                                                  '}\n'
                                                  'export type Store=ReturnType<typeof '
                                                  'createStore>;\n',
                            'src/CanvasEditor.tsx': 'import '
                                                    'React,{useEffect,useState,useSyncExternalStore} '
                                                    "from 'react';\n"
                                                    'import {createStore,Store} from '
                                                    "'./designStore';\n"
                                                    'export function '
                                                    'CanvasEditor({store:given}:{store?:Store}){\n'
                                                    ' const '
                                                    '[store]=useState(()=>given??createStore());const '
                                                    'state=useSyncExternalStore(store.subscribe,store.getSnapshot);\n'
                                                    ' const [zoom,setZoom]=useState(1);const '
                                                    "[raw,setRaw]=useState('');const "
                                                    "[error,setError]=useState('');\n"
                                                    ' '
                                                    "useEffect(()=>{window.addEventListener('pointerup',store.endDrag);return "
                                                    "()=>window.removeEventListener('pointerup',store.endDrag);},[store]);\n"
                                                    " const add=(type:'rect'|'ellipse')=>{let "
                                                    "n=1;while(state.shapes.some(s=>s.id==='s'+n))n++;store.add({id:'s'+n,type,x:10,y:20,width:40,height:30,color:'#112233'});};\n"
                                                    ' return <main><button '
                                                    "onClick={()=>add('rect')}>Add "
                                                    'rectangle</button><button '
                                                    "onClick={()=>add('ellipse')}>Add "
                                                    'ellipse</button>\n'
                                                    ' <label>Zoom<select aria-label="Zoom" '
                                                    'value={zoom} '
                                                    'onChange={e=>setZoom(Number(e.target.value))}><option '
                                                    'value="1">1</option><option '
                                                    'value="2">2</option></select></label>\n'
                                                    ' <svg data-testid="surface" width="600" '
                                                    'height="400" '
                                                    'onPointerMove={e=>store.moveDrag(e.clientX,e.clientY)} '
                                                    'onPointerUp={store.endDrag}>\n'
                                                    ' <g '
                                                    "transform={'scale('+zoom+')'}>{state.shapes.map(s=>{const "
                                                    "common={key:s.id,'data-testid':'shape-'+s.id,fill:s.color,stroke:state.selected===s.id?'black':'none',onPointerDown:(e:React.PointerEvent)=>{store.select(s.id);store.beginDrag(e.clientX,e.clientY,zoom);e.currentTarget.setPointerCapture?.(e.pointerId);}};\n"
                                                    " return s.type==='rect'?<rect {...common} "
                                                    'x={s.x} y={s.y} width={s.width} '
                                                    'height={s.height}/>:<ellipse {...common} '
                                                    'cx={s.x+s.width/2} cy={s.y+s.height/2} '
                                                    'rx={s.width/2} '
                                                    'ry={s.height/2}/>;})}</g></svg>\n'
                                                    ' <label>Color<input aria-label="Color" '
                                                    "value={state.shapes.find(s=>s.id===state.selected)?.color??''} "
                                                    'onChange={e=>store.color(e.target.value)}/></label>\n'
                                                    ' <button onClick={store.remove}>Delete '
                                                    'selected</button><button '
                                                    'onClick={store.undo}>Undo</button><button '
                                                    'onClick={store.redo}>Redo</button>\n'
                                                    ' <button '
                                                    "onClick={()=>{setRaw(store.save());setError('');}}>Save "
                                                    'document</button>\n'
                                                    ' <textarea aria-label="Document JSON" '
                                                    'value={raw} '
                                                    'onChange={e=>setRaw(e.target.value)}/><button '
                                                    "onClick={()=>{try{store.load(raw);setError('');}catch(e){setError('Invalid "
                                                    "document');}}}>Load document</button>\n"
                                                    ' <div role="alert">{error}</div><output '
                                                    'data-testid="selected">{state.selected??\'\'}</output></main>;\n'
                                                    '}\n'},
 'movie-search-routing': {'src/queryState.ts': 'export type '
                                               'Movie={id:string,title:string,genre:string,year:number};\n'
                                               'export type '
                                               'View={q:string,genre:string,minYear:number|null,page:number};\n'
                                               'export const '
                                               "MOVIES:Movie[]=[{id:'A',title:'Orbit',genre:'drama',year:2020},{id:'B',title:'Orbit',genre:'comedy',year:2022},{id:'C',title:'Other',genre:'drama',year:2023},{id:'D',title:'A&B',genre:'drama',year:2024},{id:'E',title:'100%25',genre:'comedy',year:2019}];\n"
                                               'export function parseQuery(query:string):View{\n'
                                               ' const p=new '
                                               "URLSearchParams(query.startsWith('?')?query.slice(1):query);\n"
                                               " const year=p.get('minYear');const "
                                               "page=p.get('page')??'1';\n"
                                               ' '
                                               'if(!/^[1-9][0-9]*$/.test(page)||!Number.isSafeInteger(Number(page)))throw '
                                               "new Error('Invalid page');\n"
                                               ' '
                                               'if(year!==null&&(!/^[0-9]{4}$/.test(year)||Number(year)<1000))throw '
                                               "new Error('Invalid year');\n"
                                               ' return '
                                               "{q:p.get('q')??'',genre:p.get('genre')??'',minYear:year===null?null:Number(year),page:Number(page)};\n"
                                               '}\n'
                                               'export function toQuery(v:View){const p=new '
                                               "URLSearchParams();if(v.q)p.set('q',v.q);if(v.genre)p.set('genre',v.genre);if(v.minYear!==null)p.set('minYear',String(v.minYear));p.set('page',String(v.page));return "
                                               "'?'+p.toString();}\n"
                                               'export function '
                                               "changeFilters(v:View,patch:Partial<Omit<View,'page'>>):View{return "
                                               '{...v,...patch,page:1};}\n'
                                               'export function search(movies:Movie[],v:View){\n'
                                               ' const '
                                               'rows=movies.filter(m=>(!v.q||m.title.toLowerCase().includes(v.q.toLowerCase()))&&(!v.genre||m.genre===v.genre)&&(v.minYear===null||m.year>=v.minYear)).sort((a,b)=>a.id<b.id?-1:a.id>b.id?1:0);\n'
                                               ' return '
                                               '{rows:rows.slice((v.page-1)*2,v.page*2),total:rows.length};\n'
                                               '}\n',
                          'src/api.ts': "import express from 'express';\n"
                                        'import {MOVIES,Movie,parseQuery,search} from '
                                        "'./queryState';\n"
                                        'export function createApp(movies:Movie[]=MOVIES){const '
                                        'app=express();\n'
                                        ' '
                                        "app.get('/api/movies',(req,res)=>{try{res.json(search(movies,parseQuery(req.originalUrl.split('?')[1]??'')));}catch{res.status(400).json({detail:'Invalid "
                                        "query'});}});\n"
                                        " app.get('/api/movies/:id',(req,res)=>{const "
                                        'm=movies.find(m=>m.id===req.params.id);if(!m)return '
                                        "res.status(404).json({detail:'Not found'});return "
                                        'res.json(m);});\n'
                                        ' '
                                        "app.get(['/movies','/movies/:id'],(_req,res)=>res.type('html').send('<!doctype "
                                        'html><html><head><title>Movies</title></head><body><div '
                                        'id="root"></div><script type="module" '
                                        'src="/src/main.tsx"></script></body></html>\'));\n'
                                        ' return app;}\n',
                          'src/MovieApp.tsx': 'import React,{useEffect,useState,useRef} from '
                                              "'react';\n"
                                              'import '
                                              '{Movie,parseQuery,toQuery,changeFilters,View} from '
                                              "'./queryState';\n"
                                              'export function MovieApp(){\n'
                                              ' const '
                                              '[url,setUrl]=useState(()=>location.pathname+location.search);const '
                                              '[rows,setRows]=useState<Movie[]>([]);const '
                                              '[detail,setDetail]=useState<Movie|null>(null);const '
                                              '[total,setTotal]=useState(0);const '
                                              "[error,setError]=useState('');const "
                                              '[loading,setLoading]=useState(false);const '
                                              'generation=useRef(0);\n'
                                              ' let '
                                              "view:View|null=null;try{view=parseQuery(url.split('?')[1]??'');}catch{}\n"
                                              " const path=url.split('?')[0];\n"
                                              ' useEffect(()=>{const '
                                              "pop=()=>setUrl(location.pathname+location.search);window.addEventListener('popstate',pop);return "
                                              "()=>window.removeEventListener('popstate',pop);},[]);\n"
                                              ' useEffect(()=>{const id=++generation.current;let '
                                              "active=true;setError('');setLoading(true);setDetail(null);setRows([]);\n"
                                              ' let endpoint:string;try{const '
                                              "v=parseQuery(url.split('?')[1]??'');endpoint=path==='/movies'?'/api/movies'+toQuery(v):path.startsWith('/movies/')?'/api/movies/'+encodeURIComponent(decodeURIComponent(path.slice(8))):'';if(!endpoint)throw "
                                              "new Error();}catch{setError('Invalid route or "
                                              "query');setLoading(false);return;}\n"
                                              ' fetch(endpoint).then(async r=>{if(!r.ok)throw new '
                                              "Error(r.status===404?'Not found':'Request "
                                              "failed');return "
                                              "r.json();}).then(data=>{if(!active||id!==generation.current)return;if(path==='/movies'){setRows(data.rows);setTotal(data.total);}else "
                                              'setDetail(data);}).catch(e=>{if(active&&id===generation.current)setError(e.message);}).finally(()=>{if(active&&id===generation.current)setLoading(false);});return '
                                              '()=>{active=false;};\n'
                                              ' },[url]);\n'
                                              ' const '
                                              "navigate=(next:string)=>{history.pushState({},'',next);setUrl(next);};\n"
                                              ' const '
                                              "filter=(patch:Partial<Omit<View,'page'>>)=>{if(view)navigate('/movies'+toQuery(changeFilters(view,patch)));};\n"
                                              ' return '
                                              "<main>{path==='/movies'&&view&&<><label>Search<input "
                                              'aria-label="Search" value={view.q} '
                                              'onChange={e=>filter({q:e.target.value})}/></label><label>Genre<select '
                                              'aria-label="Genre" value={view.genre} '
                                              'onChange={e=>filter({genre:e.target.value})}><option '
                                              'value="">All</option><option '
                                              'value="drama">Drama</option><option '
                                              'value="comedy">Comedy</option></select></label><label>Minimum '
                                              'year<input aria-label="Minimum year" '
                                              "value={view.minYear??''} onChange={e=>{const "
                                              'n=e.target.value;if(!n||/^[0-9]{4}$/.test(n))filter({minYear:n?Number(n):null});}}/></label><output '
                                              'data-testid="total">{total}</output><ul>{rows.map(m=><li '
                                              'key={m.id}><a '
                                              "href={'/movies/'+encodeURIComponent(m.id)} "
                                              "onClick={e=>{e.preventDefault();navigate('/movies/'+encodeURIComponent(m.id));}}>{m.title} "
                                              '({m.id})</a></li>)}</ul><button '
                                              'disabled={view.page*2>=total||loading} '
                                              "onClick={()=>navigate('/movies'+toQuery({...view!,page:view!.page+1}))}>Next "
                                              'page</button></>}\n'
                                              ' '
                                              '{detail&&<article><h1>{detail.title}</h1><p>{detail.genre} '
                                              '{detail.year}</p></article>}{loading&&<p '
                                              'role="status">Loading</p>}<p '
                                              'role="alert">{error}</p></main>;\n'
                                              '}\n'}}

MUTATIONS = {'extensible-hand-comparison': ('engine.py',
                                'return (order.index(category),*key)',
                                'return (order.index(category),*key,*sorted(c[1] for c in cards))',
                                'suit-neutral'),
 'runway-event-scheduler': ('engine.py', 'a<d and c<b', 'a<=d and c<=b', 'closure-touch'),
 'transactional-wallet-transfer': ('engine.py',
                                   'except Exception:db.rollback();raise',
                                   'except Exception:db.commit();raise',
                                   'rollback-debit'),
 'canvas-document-editor': ('src/designStore.ts',
                            's.width<=0||s.height<=0',
                            's.width<0||s.height<0',
                            'invalid-preserves'),
 'movie-search-routing': ('src/queryState.ts',
                          '&&(!v.genre||m.genre===v.genre)',
                          '||(!v.genre||m.genre===v.genre)',
                          'and-filters')}

EDGE_MUTATIONS = {'extensible-hand-comparison': ('engine.py',
                                'key=(pair,next(r for r in ranks if r!=pair))',
                                'key=(pair,)',
                                'kicker'),
 'runway-event-scheduler': ('engine.py',
                            "cancellations.get(f['id'],float('inf'))>now",
                            "cancellations.get(f['id'],float('inf'))>=now",
                            'cancel-at-dispatch'),
 'transactional-wallet-transfer': ('engine.py',
                                   "if receipt[0]!=payload:raise TransferError(409,'id conflict')",
                                   "if False:raise TransferError(409,'id conflict')",
                                   'conflict'),
 'canvas-document-editor': ('src/designStore.ts',
                            's.id===state.selected?{...s,color}:s',
                            'true?{...s,color}:s',
                            'style-isolated'),
 'movie-search-routing': ('src/queryState.ts',
                          "q:p.get('q')??''",
                          "q:decodeURIComponent(p.get('q')??'')",
                          'literal-query')}
