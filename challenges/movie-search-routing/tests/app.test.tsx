import React from 'react';
import {it,expect,beforeEach,afterEach,vi} from 'vitest';
import {render,screen,fireEvent,waitFor,cleanup} from '@testing-library/react';
import request from 'supertest';
import {createApp} from '../src/api';
import {MovieApp} from '../src/MovieApp';
import {MOVIES,parseQuery,search} from '../src/queryState';
afterEach(()=>{cleanup();vi.unstubAllGlobals();});beforeEach(()=>{history.replaceState({},'','/movies');vi.stubGlobal('fetch',vi.fn(async (url:string)=>{const u=new URL(url,'http://localhost');const id=u.pathname.slice('/api/movies/'.length);const detail=MOVIES.find(m=>m.id===decodeURIComponent(id));if(u.pathname==='/api/movies')return {ok:true,json:async()=>search(MOVIES,parseQuery(u.search))};return {ok:!!detail,status:detail?200:404,json:async()=>detail};}));});
it('combines search and genre at the HTTP boundary',async()=>{const r=await request(createApp()).get('/api/movies?q=orbit&genre=drama');expect(r.body.rows.map((m:any)=>m.id)).toEqual(['A']);expect(r.body.total).toBe(1);});
it('combines year and search and filters before paging',async()=>{expect((await request(createApp()).get('/api/movies?q=orbit&minYear=2021')).body.rows.map((m:any)=>m.id)).toEqual(['B']);expect((await request(createApp()).get('/api/movies?page=2')).body.rows.map((m:any)=>m.id)).toEqual(['C','D']);});
it('decodes literal special characters exactly once',async()=>{expect((await request(createApp()).get('/api/movies?q=A%26B')).body.rows[0].id).toBe('D');expect(parseQuery('?q=100%2525').q).toBe('100%25');});
it('rejects invalid HTTP query and unknown detail',async()=>{expect((await request(createApp()).get('/api/movies?page=0')).status).toBe(400);expect((await request(createApp()).get('/api/movies/missing')).status).toBe(404);});
it('hydrates refreshed filter state from the URL',async()=>{history.replaceState({},'','/movies?q=orbit&genre=drama');render(<MovieApp/>);await screen.findByText('Orbit (A)');expect((screen.getByLabelText('Search') as HTMLInputElement).value).toBe('orbit');expect(screen.queryByText('Orbit (B)')).toBeNull();});
it('loads direct detail and renders not found',async()=>{history.replaceState({},'','/movies/D');render(<MovieApp/>);await screen.findByRole('heading',{name:'A&B'});cleanup();history.replaceState({},'','/movies/missing');render(<MovieApp/>);await waitFor(()=>expect(screen.getByRole('alert').textContent).toBe('Not found'));expect((await request(createApp()).get('/movies/D')).text).toContain('id="root"');});
it('resets page on filter changes and supports browser back',async()=>{history.replaceState({},'','/movies?page=3');render(<MovieApp/>);await screen.findByText('100%25 (E)');fireEvent.change(screen.getByLabelText('Search'),{target:{value:'orbit'}});await screen.findByText('Orbit (A)');expect(new URLSearchParams(location.search).get('page')).toBe('1');history.replaceState({},'','/movies?q=Other&page=1');fireEvent.popState(window);await screen.findByText('Other (C)');expect((screen.getByLabelText('Search') as HTMLInputElement).value).toBe('Other');});
it('ignores stale results from an earlier URL',async()=>{const pending:((x:any)=>void)[]=[];vi.stubGlobal('fetch',vi.fn(()=>new Promise(resolve=>pending.push(resolve))));render(<MovieApp/>);await waitFor(()=>expect(pending.length).toBe(1));fireEvent.change(screen.getByLabelText('Search'),{target:{value:'Other'}});await waitFor(()=>expect(pending.length).toBe(2));pending[1]({ok:true,json:async()=>({rows:[MOVIES[2]],total:1})});await screen.findByText('Other (C)');pending[0]({ok:true,json:async()=>({rows:[MOVIES[0]],total:1})});await new Promise(r=>setTimeout(r,0));expect(screen.queryByText('Orbit (A)')).toBeNull();});

it('Part 3: combined-filter-page-http',async()=>{
const {default:request}=await import('supertest');
const {createApp}=await import('../src/api');
const result=await (async()=>{const rows=[{"id": "F", "title": "Item", "genre": "drama", "year": 2018}, {"id": "E", "title": "Item", "genre": "drama", "year": 2020}, {"id": "D", "title": "Item", "genre": "drama", "year": 2024}, {"id": "C", "title": "Item", "genre": "drama", "year": 2023}, {"id": "B", "title": "Item", "genre": "other", "year": 2022}, {"id": "A", "title": "Item", "genre": "drama", "year": 2022}];const before=JSON.stringify(rows);const r=await request(createApp(rows)).get('/api/movies?q=item&genre=drama&minYear=2020&page=2');return [r.status,r.body.rows.map((m:any)=>m.id),r.body.total,JSON.stringify(rows)===before];})();
expect(result).toEqual([200, ["D", "E"], 4, true]);
});
