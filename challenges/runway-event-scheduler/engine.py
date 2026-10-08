def overlaps(a,b,c,d):return a<=d and c<=b
def schedule(flights,closures=(),cancellations=None):
    from copy import deepcopy
    flights=deepcopy(flights);closures=sorted(list(closures));cancellations=dict(cancellations or {})
    ids=[]
    for f in flights:
        if not isinstance(f.get('id'),str) or not f['id'] or f['id'] in ids:raise ValueError('invalid id')
        ids.append(f['id'])
        if type(f.get('arrival')) is not int or f['arrival']<0 or type(f.get('duration')) is not int or f['duration']<=0:raise ValueError('invalid timing')
        if f.get('kind') not in ('landing','takeoff') or type(f.get('emergency',False)) is not bool:raise ValueError('invalid policy')
    if any(k not in ids or type(v) is not int or v<0 for k,v in cancellations.items()):raise ValueError('invalid cancellation')
    if any(len(x)!=2 or any(type(v) is not int for v in x) or not 0<=x[0]<x[1] for x in closures):raise ValueError('invalid closure')
    raise NotImplementedError('implement readiness, priorities and occupancy events')
