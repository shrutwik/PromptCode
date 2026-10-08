def cents_for(rate,start,end):
    if any(type(x) is not int for x in (rate,start,end)) or rate<0 or end<=start:
        raise ValueError('invalid rate or interval')
    numerator=rate*(end-start)
    return (2*numerator+3600)//7200
