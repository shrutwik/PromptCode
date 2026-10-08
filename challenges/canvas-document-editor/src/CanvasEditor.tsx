import React,{useEffect,useState,useSyncExternalStore} from 'react';
import {createStore,Store} from './designStore';
export function CanvasEditor({store:given}:{store?:Store}){
 const [store]=useState(()=>given??createStore());const state=useSyncExternalStore(store.subscribe,store.getSnapshot);
 const [zoom,setZoom]=useState(1);const [raw,setRaw]=useState('');const [error,setError]=useState('');
 useEffect(()=>{window.addEventListener('pointerup',store.endDrag);return ()=>window.removeEventListener('pointerup',store.endDrag);},[store]);
 const add=(type:'rect'|'ellipse')=>{let n=1;while(state.shapes.some(s=>s.id==='s'+n))n++;store.add({id:'s'+n,type,x:10,y:20,width:40,height:30,color:'#112233'});};
 return <main><button onClick={()=>add('rect')}>Add rectangle</button><button onClick={()=>add('ellipse')}>Add ellipse</button>
 <label>Zoom<select aria-label="Zoom" value={zoom} onChange={e=>setZoom(Number(e.target.value))}><option value="1">1</option><option value="2">2</option></select></label>
 <svg data-testid="surface" width="600" height="400" onPointerMove={e=>store.moveDrag(e.clientX,e.clientY)} onPointerUp={store.endDrag}>
 <g transform={'scale('+zoom+')'}>{state.shapes.map(s=>{const common={key:s.id,'data-testid':'shape-'+s.id,fill:s.color,stroke:state.selected===s.id?'black':'none',onPointerDown:(e:React.PointerEvent)=>{store.select(s.id);store.beginDrag(e.clientX,e.clientY,zoom);e.currentTarget.setPointerCapture?.(e.pointerId);}};
 return s.type==='rect'?<rect {...common} x={s.x} y={s.y} width={s.width} height={s.height}/>:<ellipse {...common} cx={s.x+s.width/2} cy={s.y+s.height/2} rx={s.width/2} ry={s.height/2}/>;})}</g></svg>
 <label>Color<input aria-label="Color" value={state.shapes.find(s=>s.id===state.selected)?.color??''} onChange={e=>store.color(e.target.value)}/></label>
 <button onClick={store.remove}>Delete selected</button><button onClick={store.undo}>Undo</button><button onClick={store.redo}>Redo</button>
 <button onClick={()=>{setRaw(store.save());setError('');}}>Save document</button>
 <textarea aria-label="Document JSON" value={raw} onChange={e=>setRaw(e.target.value)}/><button onClick={()=>{try{store.load(raw);setError('');}catch(e){setError('Invalid document');}}}>Load document</button>
 <div role="alert">{error}</div><output data-testid="selected">{state.selected??''}</output></main>;
}
