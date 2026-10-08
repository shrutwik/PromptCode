RANKS={str(n):n for n in range(2,11)} | {'J':11,'Q':12,'K':13,'A':14}
DEFAULT=('distinct','pair','triple')
def parse_card(card):
    if not isinstance(card,str) or len(card)<2 or card[-1] not in 'CDHS' or card[:-1] not in RANKS:raise ValueError('invalid card')
    return RANKS.get(card[0],1),card[-1]
def hand_key(hand,order=DEFAULT):
    if not isinstance(order,(list,tuple)) or len(order)!=3 or any(not isinstance(c,str) for c in order) or set(order)!=set(DEFAULT):raise ValueError('invalid rules')
    if not isinstance(hand,(list,tuple)) or len(hand)!=3:raise ValueError('three cards required')
    cards=[parse_card(c) for c in hand]
    if len(set(cards))!=3:raise ValueError('duplicate physical card')
    ranks=sorted([c[0] for c in cards],reverse=True)
    if ranks[0]==ranks[2]:category='triple';key=(ranks[0],)
    elif len(set(ranks))==2:
        pair=next(r for r in ranks if ranks.count(r)==2);category='pair';key=(pair,next(r for r in ranks if r!=pair))
    else:category='distinct';key=tuple(ranks)
    return (order.index(category),*key)
def compare(left,right,order=DEFAULT):
    raise NotImplementedError('implement the complete comparison key')
