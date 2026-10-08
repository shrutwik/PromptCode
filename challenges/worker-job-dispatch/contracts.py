def can_start(finish,arrival):return finish<arrival
def validate(k,jobs):
    if type(k) is not int or k<=0:raise ValueError('positive worker count')
    if len({j[0] for j in jobs})!=len(jobs):raise ValueError('duplicate job id')
    if any(type(t) is not int or type(d) is not int or t<0 or d<=0 for _,t,d in jobs):
        raise ValueError('invalid job')
