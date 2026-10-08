"""Candidate-visible behavioral fixtures; independent from server grading probes."""

def test_get_promotes():
    from engine import Cache
    c=Cache(2);c.put('a',1);c.put('b',2);c.get('a');c.put('c',3);result=c.keys()
    assert result == ['a', 'c']

def test_miss_does_not_promote():
    from engine import Cache
    c=Cache(2);c.put('a',1);c.put('b',2);c.get('x');c.put('c',3);result=c.keys()
    assert result == ['b', 'c']

def test_replace_promotes():
    from engine import Cache
    c=Cache(2);c.put('a',1);c.put('b',2);c.put('a',9);result=[c.keys(),c.get('a')]
    assert result == [['b', 'a'], 9]

def test_resize():
    from engine import Cache
    c=Cache(3);[c.put(x,x) for x in 'abc'];c.resize(1);result=c.keys()
    assert result == ['c']

def test_zero():
    from engine import Cache
    c=Cache(0);c.put('a',1);result=[c.keys(),c.get('a')]
    assert result == [[], None]

def test_factory_once():
    from engine import Cache
    c=Cache(1);calls=[];f=lambda:(calls.append(1) or 7);result=[c.get_or_put('a',f),c.get_or_put('a',f),len(calls)]
    assert result == [7, 7, 1]

def test_factory_failure():
    from engine import Cache
    c=Cache(1)
    def f():raise RuntimeError('fail')
    try:c.get_or_put('a',f)
    except RuntimeError:result=c.keys()
    else:result=None
    assert result == []

def test_invalid_resize():
    from engine import Cache
    c=Cache(1);c.put('a',1)
    try:c.resize(-1)
    except ValueError:result=[c.capacity,c.keys()]
    else:result=None
    assert result == [1, ['a']]


def test_part_three_pressure_case():
    from engine import Cache
    c=Cache(2)
    for i,k in enumerate(['a', 'b']):c.put(k,i+1)
    c.get('a');before=c.keys()
    try:c.resize(-1)
    except ValueError:pass
    else:raise RuntimeError('accepted invalid size')
    unchanged=c.keys()==before;c.put('c',9);result=[unchanged,c.keys(),c.get('a'),c.get('b')]
    assert result == [True, ['a', 'c'], 1, None]
