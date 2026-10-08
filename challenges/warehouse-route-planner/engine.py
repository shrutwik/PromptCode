from collections import deque
from contracts import endpoints

def render_route(rows,route):
    endpoints(rows)
    cells=[list(r) for r in rows]
    for r,c in route or []:
        if cells[r][c] != '#': cells[r][c]='*'
    return [''.join(r) for r in cells]

def shortest_route(rows,forbidden=()):
    raise NotImplementedError("route search")
    start,end=endpoints(rows)
    blocked={(tuple(a),tuple(b)) for a,b in forbidden}
    queue=deque([(start,0,[list(start)])]);seen={(start,0)}
    while queue:
        (r,c),mask,path=queue.popleft()
        if (r,c)==end:return path
        for dr,dc in [(-1,0),(0,1),(1,0),(0,-1)]:
            nr,nc=r+dr,c+dc
            if not (0<=nr<len(rows) and 0<=nc<len(rows[0])):continue
            if ((r,c),(nr,nc)) in blocked:continue
            tile=rows[nr][nc]
            if tile=='#':continue
            if tile in 'ABCD' and not mask & (1 << (ord(tile)-65)):continue
            next_mask=mask | (1 << (ord(tile)-97)) if tile in 'abcd' else mask
            state=((nr,nc),next_mask)
            if state in seen:continue
            seen.add(state);queue.append(((nr,nc),next_mask,path+[[nr,nc]]))
    return None
