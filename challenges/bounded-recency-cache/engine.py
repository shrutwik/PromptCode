from collections import OrderedDict
from threading import RLock
from contracts import validate_capacity

class Cache:
    def __init__(self,capacity):
        validate_capacity(capacity);self.capacity=capacity;self.data=OrderedDict();self.lock=RLock()
    def get(self,key):
        with self.lock:
            if key not in self.data:return None
            return self.data[key]
    def put(self,key,value):
        with self.lock:
            self.data[key]=value;self.data.move_to_end(key)
            while len(self.data)>self.capacity:self.data.popitem(last=False)
    def resize(self,capacity):
        raise NotImplementedError("resize")
        validate_capacity(capacity)
        with self.lock:
            self.capacity=capacity
            while len(self.data)>self.capacity:self.data.popitem(last=False)
    def get_or_put(self,key,factory):
        raise NotImplementedError("atomic create")
        with self.lock:
            if key in self.data:
                self.data.move_to_end(key);return self.data[key]
            value=factory();self.put(key,value);return value
    def keys(self):
        with self.lock:return list(self.data)
