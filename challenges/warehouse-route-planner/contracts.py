def endpoints(rows):
    if not rows or not rows[0] or any(len(r)!=len(rows[0]) for r in rows):
        raise ValueError('rectangular grid required')
    if any(c not in '#.SEabcdABCD' for r in rows for c in r):
        raise ValueError('unknown tile')
    start=[(r,c) for r,row in enumerate(rows) for c,x in enumerate(row) if x=='S']
    end=[(r,c) for r,row in enumerate(rows) for c,x in enumerate(row) if x=='E']
    if len(start)!=1 or len(end)!=1: raise ValueError('one start and exit required')
    return start[0],end[0]
