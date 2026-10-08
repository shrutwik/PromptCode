import React from 'react';
import {it,expect,afterEach,beforeEach,vi} from 'vitest';
import {render,screen,fireEvent,cleanup} from '@testing-library/react';
import {CanvasEditor} from '../src/CanvasEditor';
import {createStore} from '../src/designStore';
afterEach(()=>{cleanup();vi.unstubAllGlobals();});beforeEach(()=>vi.stubGlobal('PointerEvent',MouseEvent));
function add(){fireEvent.click(screen.getByText('Add rectangle'));}
it('inserts and selects distinct shapes in the rendered editor',()=>{render(<CanvasEditor/>);add();add();expect(screen.getByTestId('shape-s1')).toBeTruthy();expect(screen.getByTestId('selected').textContent).toBe('s2');});
it('drags only the selected rendered shape in canvas coordinates',()=>{render(<CanvasEditor/>);add();add();fireEvent.change(screen.getByLabelText('Zoom'),{target:{value:'2'}});fireEvent.pointerDown(screen.getByTestId('shape-s1'),{clientX:0,clientY:0});fireEvent.pointerMove(screen.getByTestId('surface'),{clientX:20,clientY:10});fireEvent.pointerUp(window);expect(screen.getByTestId('shape-s1').getAttribute('x')).toBe('20');expect(screen.getByTestId('shape-s1').getAttribute('y')).toBe('25');expect(screen.getByTestId('shape-s2').getAttribute('x')).toBe('10');});
it('styles only the selected shape',()=>{render(<CanvasEditor/>);add();add();fireEvent.change(screen.getByLabelText('Color'),{target:{value:'#abcdef'}});expect(screen.getByTestId('shape-s2').getAttribute('fill')).toBe('#abcdef');expect(screen.getByTestId('shape-s1').getAttribute('fill')).toBe('#112233');});
it('round trips a saved document through a fresh editor',()=>{render(<CanvasEditor/>);add();fireEvent.click(screen.getByText('Save document'));const raw=(screen.getByLabelText('Document JSON') as HTMLTextAreaElement).value;cleanup();render(<CanvasEditor/>);fireEvent.change(screen.getByLabelText('Document JSON'),{target:{value:raw}});fireEvent.click(screen.getByText('Load document'));expect(screen.getByTestId('shape-s1').getAttribute('x')).toBe('10');});
it('rejects invalid loads without replacing the design',()=>{render(<CanvasEditor/>);add();fireEvent.change(screen.getByLabelText('Document JSON'),{target:{value:JSON.stringify({version:1,shapes:[{id:'bad',type:'rect',x:0,y:0,width:-1,height:1,color:'red'}],selected:null})}});fireEvent.click(screen.getByText('Load document'));expect(screen.getByRole('alert').textContent).toBe('Invalid document');expect(screen.getByTestId('shape-s1')).toBeTruthy();});
it('clears selection when deleting',()=>{render(<CanvasEditor/>);add();fireEvent.click(screen.getByText('Delete selected'));expect(screen.queryByTestId('shape-s1')).toBeNull();expect(screen.getByTestId('selected').textContent).toBe('');});
it('records one completed drag and supports redo',()=>{const store=createStore();render(<CanvasEditor store={store}/>);add();fireEvent.pointerDown(screen.getByTestId('shape-s1'),{clientX:0,clientY:0});fireEvent.pointerMove(screen.getByTestId('surface'),{clientX:5,clientY:2});fireEvent.pointerMove(screen.getByTestId('surface'),{clientX:10,clientY:4});fireEvent.pointerUp(window);fireEvent.click(screen.getByText('Undo'));expect(screen.getByTestId('shape-s1').getAttribute('x')).toBe('10');fireEvent.click(screen.getByText('Redo'));expect(screen.getByTestId('shape-s1').getAttribute('x')).toBe('20');});
it('validates duplicate ids and keeps prior state',()=>{const s=createStore();s.add({id:'a',type:'rect',x:0,y:0,width:2,height:2,color:'red'});const before=s.save();expect(()=>s.add({id:'a',type:'ellipse',x:1,y:1,width:2,height:2,color:'blue'})).toThrow();expect(s.save()).toBe(before);});

it('Part 3: branch-clears-redo',async()=>{
const {createStore}=await import('../src/designStore');
const result=await (async()=>{const s=createStore();s.add({id:'a',type:'rect',x:10,y:2,width:3,height:4,color:'red'});s.beginDrag(0,0,1);s.moveDrag(10,0);s.endDrag();s.undo();s.color('blue');s.redo();return s.getSnapshot().shapes.map(v=>[v.x,v.color]);})();
expect(result).toEqual([[10, "blue"]]);
});
