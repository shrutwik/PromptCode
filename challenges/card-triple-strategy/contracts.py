def validate_table(cards):
    if any(not isinstance(c['id'],str) or type(c['amount']) is not int or not 1<=c['amount']<=9 for c in cards):raise ValueError('invalid card')
    if len({c['id'] for c in cards})!=len(cards):raise ValueError('duplicate physical id')
