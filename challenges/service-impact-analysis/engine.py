from contracts import normalize,ancestor

def impacted(watched,depends,changes):
    paths={s:[normalize(p) for p in ps] for s,ps in watched.items()}
    edits=[(normalize(p),deleted) for p,deleted in changes]
    if any(s not in paths or any(d not in paths for d in ds) for s,ds in depends.items()):
        raise ValueError('unknown service')
    raise NotImplementedError("impact closure")
    result={s for s,ps in paths.items() if any(ancestor(w,p) or (deleted and ancestor(p,w)) for w in ps for p,deleted in edits)}
    reverse={s:set() for s in paths}
    for s,ds in depends.items():
        for d in ds:reverse[d].add(s)
    queue=list(result)
    while queue:
        node=queue.pop()
        for dependent in reverse[node]-result:
            result.add(dependent);queue.append(dependent)
    return sorted(result)
