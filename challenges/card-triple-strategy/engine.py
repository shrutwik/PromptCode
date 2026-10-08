from itertools import combinations
from contracts import validate_table

def legal(cards,ids):
    validate_table(cards)
    if len(ids)!=3:return False
    amounts={c['id']:c['amount'] for c in cards}
    return all(id in amounts for id in ids) and sum(amounts[id] for id in ids)==15
def choose(cards):
    validate_table(cards)
    raise NotImplementedError("chooser")
    return next((list(ids) for ids in combinations(sorted(c['id'] for c in cards),3) if legal(cards,ids)),None)
def remove(cards,ids):
    if not legal(cards,ids):raise ValueError('illegal move')
    chosen=set(ids)
    return [dict(c) for c in cards if c['id'] not in chosen]
