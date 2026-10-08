"""Candidate-visible behavioral fixtures; independent from server grading probes."""

def test_touching():
    from contracts import overlap
    result=overlap([0,10],[10,20])
    assert result == False

def test_nested():
    from contracts import overlap
    result=overlap([0,20],[5,10])
    assert result == True

def test_earliest_gap():
    from engine import Scheduler
    result=Scheduler([(0,5),(10,15)]).find(5,0,20)
    assert result == [5, 10]

def test_no_gap():
    from engine import Scheduler
    result=Scheduler([(0,5),(10,15)]).find(6,0,20)
    assert result == None

def test_empty_room():
    from engine import Scheduler
    result=Scheduler().find(3,2,10)
    assert result == [2, 5]

def test_occupied_union():
    from engine import Scheduler
    result=Scheduler([(5,10),(0,8)]).find(2,0,20)
    assert result == [10, 12]

def test_reserve_inserts():
    from engine import Scheduler
    s=Scheduler();result=[s.reserve(3,0,3),s.reserve(3,0,3),s.snapshot()]
    assert result == [[0, 3], None, [[0, 3]]]

def test_invalid_preserves():
    from engine import Scheduler
    s=Scheduler([(0,5)])
    try:s.reserve(0,0,10)
    except ValueError:result=s.snapshot()
    else:result=None
    assert result == [[0, 5]]


def test_part_three_pressure_case():
    from engine import Scheduler
    s=Scheduler([(2,4)]);before=s.snapshot();miss=s.reserve(2,3,5);same=s.snapshot()==before;hit=s.reserve(2,0,2);result=[miss,same,hit,s.snapshot()]
    assert result == [None, True, [0, 2], [[0, 2], [2, 4]]]
