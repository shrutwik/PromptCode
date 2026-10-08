from contracts import masks

def valid(words,indices):
    ms=masks(words)
    if any(type(i) is not int or i<0 or i>=len(words) for i in indices) or len(set(indices))!=len(indices):return False
    used=0
    for i in indices:
        if ms[i] is None:continue
        used|=ms[i]
    return True

def choose(words):
    raise NotImplementedError("optimal selector")
    ms=masks(words);states={0:[]}
    for i,mask in enumerate(ms):
        if mask is None:continue
        for used,selection in list(states.items()):
            if used&mask:continue
            combined=used|mask;candidate=selection+[i]
            if combined not in states or (len(candidate),candidate)<(len(states[combined]),states[combined]):states[combined]=candidate
    return min(states.items(),key=lambda item:(-item[0].bit_count(),len(item[1]),item[1]))[1]
