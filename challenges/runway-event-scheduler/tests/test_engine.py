import pytest
from engine import schedule,overlaps

def f(id,arrival=0,duration=2,kind='landing',emergency=False):return dict(id=id,arrival=arrival,duration=duration,kind=kind,emergency=emergency)
def test_landing_priority():assert schedule([f('T',kind='takeoff'),f('L')])==[['L',0,2],['T',2,4]]
def test_emergency_and_id():assert schedule([f('B',emergency=True),f('A',emergency=True)])==[['A',0,2],['B',2,4]]
def test_non_preemptive():assert schedule([f('T',0,5,'takeoff'),f('X',1,2,'landing',True)])==[['T',0,5],['X',5,7]]
def test_finish_arrival():assert schedule([f('A',0,5),f('B',5)])==[['A',0,5],['B',5,7]]
def test_waiting_cancel():assert schedule([f('A',0,5),f('B',1)],cancellations={'B':3})==[['A',0,5]]
def test_closure_and_boundary():
    assert schedule([f('A',4,3)],[(5,10)])==[['A',10,13]]
    assert schedule([f('A',2,3)],[(5,10)])==[['A',2,5]]
def test_reselect_after_closure_and_preserve():
    fs=[f('A',4,3,'takeoff'),f('X',6,2,'landing',True)];before=[x.copy() for x in fs]
    assert schedule(fs,[(5,10)])==[['X',10,12],['A',12,15]]
    assert fs==before
def test_cancel_boundary_and_invalid():
    assert schedule([f('A')],cancellations={'A':0})==[]
    with pytest.raises(ValueError):schedule([f('A',duration=0)])

def test_part_three_pressure_case():
    from engine import schedule
    result=schedule([{'id': 'A', 'arrival': 4, 'duration': 3, 'kind': 'takeoff'}, {'id': 'B', 'arrival': 4, 'duration': 3, 'kind': 'landing'}],[(5, 10)],{'B':8})
    assert result == [['A', 10, 13]]
