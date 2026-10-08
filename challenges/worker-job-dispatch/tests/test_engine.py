"""Candidate-visible behavioral fixtures; independent from server grading probes."""

def test_boundary_helper():
    from contracts import can_start
    result=can_start(5,5)
    assert result == True

def test_one_worker():
    from engine import dispatch
    result=dispatch(1,[('a',0,2),('b',2,1)])
    assert result == [['a', 0, 0, 2], ['b', 0, 2, 3]]

def test_queued():
    from engine import dispatch
    result=dispatch(2,[('a',0,5),('b',0,2),('c',0,1)])
    assert result == [['a', 0, 0, 5], ['b', 1, 0, 2], ['c', 1, 2, 3]]

def test_all_release_before_choice():
    from engine import dispatch
    result=dispatch(2,[('a',0,2),('b',0,2),('c',2,1)])
    assert result == [['a', 0, 0, 2], ['b', 1, 0, 2], ['c', 0, 2, 3]]

def test_fifo():
    from engine import dispatch
    result=dispatch(1,[('a',0,3),('b',1,1),('c',1,1)])
    assert result == [['a', 0, 0, 3], ['b', 0, 3, 4], ['c', 0, 4, 5]]

def test_empty():
    from engine import dispatch
    result=dispatch(3,[])
    assert result == []

def test_invalid_workers():
    from engine import dispatch
    try:dispatch(0,[])
    except ValueError:result=True
    else:result=False
    assert result == True

def test_input_order_retained():
    from engine import dispatch
    jobs=[('b',2,1),('a',0,1)];dispatch(1,jobs);result=jobs
    assert result == [('b', 2, 1), ('a', 0, 1)]


def test_part_three_pressure_case():
    from engine import dispatch
    jobs=[['a', 0, 6], ['b', 1, 2], ['c', 2, 1], ['d', 3, 1]];before=[j[:] for j in jobs];a=dispatch(1,jobs);b=dispatch(1,list(reversed(jobs)));result=[a,b==a,jobs==before]
    assert result == [[['a', 0, 0, 6], ['b', 0, 6, 8], ['c', 0, 8, 9], ['d', 0, 9, 10]], True, True]
