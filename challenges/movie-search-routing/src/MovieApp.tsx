import React,{useEffect,useState,useRef} from 'react';
import {Movie,parseQuery,toQuery,changeFilters,View} from './queryState';
export function MovieApp(){
 const [url,setUrl]=useState(()=>location.pathname+location.search);const [rows,setRows]=useState<Movie[]>([]);const [detail,setDetail]=useState<Movie|null>(null);const [total,setTotal]=useState(0);const [error,setError]=useState('');const [loading,setLoading]=useState(false);const generation=useRef(0);
 let view:View|null=null;try{view=parseQuery(url.split('?')[1]??'');}catch{}
 const path=url.split('?')[0];
 useEffect(()=>{const pop=()=>setUrl(location.pathname+location.search);window.addEventListener('popstate',pop);return ()=>window.removeEventListener('popstate',pop);},[]);
 useEffect(()=>{const id=++generation.current;let active=true;setError('');setLoading(true);setDetail(null);setRows([]);
 let endpoint:string;try{const v=parseQuery(url.split('?')[1]??'');endpoint=path==='/movies'?'/api/movies'+toQuery(v):path.startsWith('/movies/')?'/api/movies/'+encodeURIComponent(decodeURIComponent(path.slice(8))):'';if(!endpoint)throw new Error();}catch{setError('Invalid route or query');setLoading(false);return;}
 fetch(endpoint).then(async r=>{if(!r.ok)throw new Error(r.status===404?'Not found':'Request failed');return r.json();}).then(data=>{if(path==='/movies'){setRows(data.rows);setTotal(data.total);}else setDetail(data);}).catch(e=>{if(active&&id===generation.current)setError(e.message);}).finally(()=>{if(active&&id===generation.current)setLoading(false);});return ()=>{active=false;};
 },[url]);
 const navigate=(next:string)=>{history.pushState({},'',next);setUrl(next);};
 const filter=(patch:Partial<Omit<View,'page'>>)=>{if(view)navigate('/movies'+toQuery(changeFilters(view,patch)));};
 return <main>{path==='/movies'&&view&&<><label>Search<input aria-label="Search" value={view.q} onChange={e=>filter({q:e.target.value})}/></label><label>Genre<select aria-label="Genre" value={view.genre} onChange={e=>filter({genre:e.target.value})}><option value="">All</option><option value="drama">Drama</option><option value="comedy">Comedy</option></select></label><label>Minimum year<input aria-label="Minimum year" value={view.minYear??''} onChange={e=>{const n=e.target.value;if(!n||/^[0-9]{4}$/.test(n))filter({minYear:n?Number(n):null});}}/></label><output data-testid="total">{total}</output><ul>{rows.map(m=><li key={m.id}><a href={'/movies/'+encodeURIComponent(m.id)} onClick={e=>{e.preventDefault();navigate('/movies/'+encodeURIComponent(m.id));}}>{m.title} ({m.id})</a></li>)}</ul><button disabled={view.page*2>=total||loading} onClick={()=>navigate('/movies'+toQuery({...view!,page:view!.page+1}))}>Next page</button></>}
 {detail&&<article><h1>{detail.title}</h1><p>{detail.genre} {detail.year}</p></article>}{loading&&<p role="status">Loading</p>}<p role="alert">{error}</p></main>;
}
