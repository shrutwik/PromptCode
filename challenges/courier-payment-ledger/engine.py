from contracts import cents_for

class Ledger:
    def __init__(self,rates):
        if any(type(r) is not int or r<0 for r in rates.values()):raise ValueError('invalid rate')
        self.rates=dict(rates);self.deliveries={};self.paid=set()
    def record(self,id,driver,start,end):
        if driver not in self.rates:raise ValueError('unknown driver')
        cents_for(self.rates[driver],start,end)
        item=(driver,start,end)
        if id in self.deliveries and self.deliveries[id]!=item:raise ValueError('conflicting id')
        self.deliveries[id]=item
    def cost(self,item):
        driver,start,end=item
        return self.rates[driver]*((end-start)//3600)
    def total(self):return sum(self.cost(x) for x in self.deliveries.values())
    def unpaid(self):return sum(self.cost(x) for id,x in self.deliveries.items() if id not in self.paid)
    def pay_up_to(self,cutoff):
        raise NotImplementedError("incremental payments")
        due=[id for id,x in self.deliveries.items() if id not in self.paid and x[2]<=cutoff]
        amount=sum(self.cost(self.deliveries[id]) for id in due)
        self.paid.update(due)
        return amount
    def peak(self,window_start,window_end):
        if window_end<=window_start:raise ValueError('invalid window')
        events=[]
        for driver,start,end in self.deliveries.values():
            a=max(start,window_start);b=min(end,window_end)
            if a<b:events.extend([(a,1,driver),(b,-1,driver)])
        counts={};maximum=0
        for _,delta,driver in sorted(events):
            counts[driver]=counts.get(driver,0)+delta
            maximum=max(maximum,sum(v>0 for v in counts.values()))
        return maximum
