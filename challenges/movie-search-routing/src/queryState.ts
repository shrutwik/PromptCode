export type Movie={id:string,title:string,genre:string,year:number};
export type View={q:string,genre:string,minYear:number|null,page:number};
export const MOVIES:Movie[]=[{id:'A',title:'Orbit',genre:'drama',year:2020},{id:'B',title:'Orbit',genre:'comedy',year:2022},{id:'C',title:'Other',genre:'drama',year:2023},{id:'D',title:'A&B',genre:'drama',year:2024},{id:'E',title:'100%25',genre:'comedy',year:2019}];
export function parseQuery(query:string):View{
 const p=new URLSearchParams(query.startsWith('?')?query.slice(1):query);
 const year=p.get('minYear');const page=p.get('page')??'1';
 if(!/^[1-9][0-9]*$/.test(page)||!Number.isSafeInteger(Number(page)))throw new Error('Invalid page');
 if(year!==null&&(!/^[0-9]{4}$/.test(year)||Number(year)<1000))throw new Error('Invalid year');
 return {q:p.get('q')??'',genre:p.get('genre')??'',minYear:year===null?null:Number(year),page:Number(page)};
}
export function toQuery(v:View){const p=new URLSearchParams();if(v.q)p.set('q',v.q);if(v.genre)p.set('genre',v.genre);if(v.minYear!==null)p.set('minYear',String(v.minYear));p.set('page',String(v.page));return '?'+p.toString();}
export function changeFilters(v:View,patch:Partial<Omit<View,'page'>>):View{return {...v,...patch,page:1};}
export function search(movies:Movie[],v:View){
 const rows=movies.filter(m=>(!v.q||m.title.toLowerCase().includes(v.q.toLowerCase()))||(!v.genre||m.genre===v.genre)&&(v.minYear===null||m.year>=v.minYear)).sort((a,b)=>a.id<b.id?-1:a.id>b.id?1:0);
 return {rows:rows.slice((v.page-1)*2,v.page*2),total:rows.length};
}
