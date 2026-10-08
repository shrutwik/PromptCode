import express from 'express';
import {MOVIES,Movie,parseQuery,search} from './queryState';
export function createApp(movies:Movie[]=MOVIES){const app=express();
 app.get('/api/movies',(req,res)=>{try{res.json(search(movies,parseQuery(req.originalUrl.split('?')[1]??'')));}catch{res.status(400).json({detail:'Invalid query'});}});
 app.get('/api/movies/:id',(req,res)=>{const m=movies.find(m=>m.id===req.params.id);if(!m)return res.status(404).json({detail:'Not found'});return res.json(m);});
 app.get(['/movies','/movies/:id'],(_req,res)=>res.type('html').send('<!doctype html><html><head><title>Movies</title></head><body><div id="root"></div><script type="module" src="/src/main.tsx"></script></body></html>'));
 return app;}
