def normalize(path):
    if not isinstance(path,str) or not path.startswith('/'):raise ValueError('absolute path required')
    parts=[x for x in path.split('/') if x]
    if any(x in ('.','..') for x in parts):raise ValueError('relative segments forbidden')
    return ('/'+ '/'.join(parts)).rstrip('/')
def ancestor(a,b):
    a,b=normalize(a),normalize(b)
    return a=='/' or a==b or b.startswith(a+'/')
