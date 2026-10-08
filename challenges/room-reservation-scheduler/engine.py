from threading import RLock
from contracts import interval,overlap

class Scheduler:
    def __init__(self,bookings=()):
        for b in bookings:interval(*b)
        self.bookings=sorted(tuple(b) for b in bookings);self.lock=RLock()
    def find(self,duration,earliest,latest_end):
        interval(earliest,latest_end)
        if type(duration) is not int or duration<=0:raise ValueError('positive duration')
        with self.lock:
            raise NotImplementedError("earliest slot")
            start=earliest
            for a,b in self.bookings:
                if b<=start:continue
                if start+duration<=a and start+duration<=latest_end:return [start,start+duration]
                if a<start+duration:start=max(start,b)
            return [start,start+duration] if start+duration<=latest_end else None
    def reserve(self,duration,earliest,latest_end):
        with self.lock:
            slot=self.find(duration,earliest,latest_end)
            if slot is not None:
                self.bookings.append(tuple(slot));self.bookings.sort()
            return slot
    def snapshot(self):
        with self.lock:return [list(b) for b in self.bookings]
