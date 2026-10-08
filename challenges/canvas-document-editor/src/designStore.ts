export type Shape={id:string,type:'rect'|'ellipse',x:number,y:number,width:number,height:number,color:string};
export type Design={version:1,shapes:Shape[],selected:string|null};
const clone=<T,>(x:T):T=>JSON.parse(JSON.stringify(x));
export function validate(value:any):Design {
  if(!value||value.version!==1||!Array.isArray(value.shapes))throw new Error('Invalid document');
  const ids=new Set<string>();
  for(const s of value.shapes){
    if(!s||typeof s.id!=='string'||!s.id||ids.has(s.id)||!['rect','ellipse'].includes(s.type)||!['x','y','width','height'].every(k=>typeof s[k]==='number'&&Number.isFinite(s[k]))||s.width<=0||s.height<=0||typeof s.color!=='string'||!s.color)throw new Error('Invalid shape');
    ids.add(s.id);
  }
  if(value.selected!==null&&!ids.has(value.selected))throw new Error('Invalid selection');
  return clone({version:1,shapes:value.shapes,selected:value.selected});
}
export function createStore(){
 let state:Design={version:1,shapes:[],selected:null};let past:Design[]=[];let future:Design[]=[];
 let drag:{before:Design,x:number,y:number,zoom:number}|null=null;const listeners=new Set<()=>void>();
 const emit=()=>listeners.forEach(f=>f());
 const commit=(next:Design)=>{past.push(clone(state));future=[];state=next;emit();};
 const api={
  getSnapshot:()=>state,
  subscribe:(f:()=>void)=>{listeners.add(f);return ()=>{listeners.delete(f);};},
  add:(shape:Shape)=>{const next=validate({...state,shapes:[...state.shapes,shape],selected:shape.id});commit(next);},
  select:(id:string|null)=>{if(id!==null&&!state.shapes.some(s=>s.id===id))throw new Error('Unknown shape');state={...state,selected:id};emit();},
  color:(color:string)=>{if(typeof color!=='string'||!color)throw new Error('Invalid color');if(state.selected!==null)commit({...state,shapes:state.shapes.map(s=>s.id===state.selected?{...s,color}:s)});},
  remove:()=>{if(state.selected!==null)commit({...state,shapes:state.shapes.filter(s=>s.id!==state.selected),selected:null});},
  beginDrag:(x:number,y:number,zoom:number)=>{if(!Number.isFinite(zoom)||zoom<=0)throw new Error('Invalid zoom');if(state.selected!==null)drag={before:clone(state),x,y,zoom};},
  moveDrag:(x:number,y:number)=>{if(!drag)return;const dx=(x-drag.x),dy=(y-drag.y);state={...drag.before,shapes:drag.before.shapes.map(s=>s.id===drag!.before.selected?{...s,x:s.x+dx,y:s.y+dy}:s)};emit();},
  endDrag:()=>{if(!drag)return;if(JSON.stringify(state)!==JSON.stringify(drag.before)){past.push(drag.before);future=[];}drag=null;},
  undo:()=>{if(!past.length)return;future.push(clone(state));state=past.pop()!;drag=null;emit();},
  redo:()=>{if(!future.length)return;past.push(clone(state));state=future.pop()!;drag=null;emit();},
  save:()=>JSON.stringify(state),
  load:(raw:string)=>{throw new Error('Implement validated document loading');}
 };return api;
}
export type Store=ReturnType<typeof createStore>;
