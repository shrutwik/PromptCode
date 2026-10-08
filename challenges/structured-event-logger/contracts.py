import json
LEVELS={'DEBUG':0,'INFO':1,'WARN':2,'ERROR':3}
def enabled(level,threshold):
    if level not in LEVELS or threshold not in LEVELS:raise ValueError('unknown level')
    return LEVELS[level]>LEVELS[threshold]
def format_json(record):return json.dumps(record,sort_keys=True,ensure_ascii=False)
