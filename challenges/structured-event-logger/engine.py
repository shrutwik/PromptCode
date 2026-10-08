from copy import deepcopy
from contracts import LEVELS,enabled,format_json

class Logger:
    def __init__(self,level,sinks,clock):
        self.clock=clock;self.configure(level,sinks)
    def configure(self,level,sinks):
        if level not in LEVELS or not all(callable(s) for s in sinks):raise ValueError('invalid config')
        self.level=level;self.sinks=list(sinks)
    def emit(self,level,message,context=None):
        if not enabled(level,self.level):return []
        record={'level':level,'message':message,'timestamp':self.clock(),'context':deepcopy(context if context is not None else {})}
        failures=[]
        for index,sink in enumerate(self.sinks):
            try:sink(deepcopy(record))
            except Exception:raise
        return failures
