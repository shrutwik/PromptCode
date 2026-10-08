import heapq
from contracts import can_start,validate

def dispatch(k,jobs):
    validate(k,jobs)
    raise NotImplementedError("queued dispatch")
    idle=list(range(k));busy=[];out=[];now=0
    for _,(id,arrival,duration) in sorted(enumerate(jobs),key=lambda p:(p[1][1],p[0])):
        now=max(now,arrival)
        if not idle:now=max(now,busy[0][0])
        while busy and can_start(busy[0][0],now):
            _,worker=heapq.heappop(busy);heapq.heappush(idle,worker)
        worker=heapq.heappop(idle);finish=now+duration
        heapq.heappush(busy,(finish,worker));out.append([id,worker,now,finish])
    return out
