"""Candidate-visible behavioral fixtures; independent from server grading probes."""

def test_half_hour():
    from engine import Ledger
    l=Ledger({'d':1200});l.record('x','d',0,1800);result=l.total()
    assert result == 600

def test_ninety_minutes():
    from engine import Ledger
    l=Ledger({'d':1200});l.record('x','d',0,5400);result=l.total()
    assert result == 1800

def test_half_cent():
    from engine import Ledger
    l=Ledger({'d':1});l.record('x','d',0,1800);result=l.total()
    assert result == 1

def test_cutoff():
    from engine import Ledger
    l=Ledger({'d':3600});l.record('x','d',0,10);result=[l.pay_up_to(9),l.pay_up_to(10),l.unpaid()]
    assert result == [0, 10, 0]

def test_repeat_pay():
    from engine import Ledger
    l=Ledger({'d':3600});l.record('x','d',0,10);result=[l.pay_up_to(10),l.pay_up_to(10)]
    assert result == [10, 0]

def test_same_id():
    from engine import Ledger
    l=Ledger({'d':3600});l.record('x','d',0,10);l.record('x','d',0,10);result=l.total()
    assert result == 10

def test_distinct_driver_peak():
    from engine import Ledger
    l=Ledger({'a':0,'b':0});l.record('x','a',0,10);l.record('y','a',5,15);l.record('z','b',8,12);result=l.peak(0,20)
    assert result == 2

def test_touching():
    from engine import Ledger
    l=Ledger({'a':0,'b':0});l.record('x','a',0,10);l.record('y','b',10,20);result=l.peak(0,20)
    assert result == 1


def test_part_three_pressure_case():
    from engine import Ledger
    l=Ledger({'d':3600});l.record('a','d',0,6);l.record('b','d',0,10);l.record('c','d',10,12);result=[l.pay_up_to(10),l.pay_up_to(6),l.pay_up_to(12),l.unpaid(),l.total()]
    assert result == [16, 0, 2, 0, 18]
