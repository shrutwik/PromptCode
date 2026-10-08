def interval(start,end):
    if type(start) is not int or type(end) is not int or end<=start:raise ValueError('positive integer interval')
def overlap(a,b):
    interval(*a);interval(*b)
    return a[0]<=b[1] and b[0]<=a[1]
