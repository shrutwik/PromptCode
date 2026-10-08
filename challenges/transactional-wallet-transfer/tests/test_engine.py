import pytest
from concurrent.futures import ThreadPoolExecutor
from engine import Wallet,TransferError
from app import create_app
from fastapi.testclient import TestClient

def wallet(tmp_path):return Wallet(tmp_path/'ledger.db',{'A':100,'B':0,'C':0})
def test_transfer(tmp_path):
    w=wallet(tmp_path);r=w.transfer('r','A','B',30)
    assert r['balances']=={'A':70,'B':30}
    assert w.balances()=={'A':70,'B':30,'C':0}
def test_durable_replay(tmp_path):
    w=wallet(tmp_path);r=w.transfer('r','A','B',30);w.transfer('s','A','B',10)
    other=Wallet(tmp_path/'ledger.db');assert other.transfer('r','A','B',30)==r
    assert other.balances()=={'A':60,'B':40,'C':0}
def test_conflict_preserves(tmp_path):
    w=wallet(tmp_path);w.transfer('r','A','B',30)
    with pytest.raises(TransferError) as e:w.transfer('r','A','B',40)
    assert e.value.status==409;assert w.balances()['A']==70
def test_insufficient(tmp_path):
    w=wallet(tmp_path)
    with pytest.raises(TransferError) as e:w.transfer('r','A','B',101)
    assert e.value.status==422;assert w.balances()['A']==100
def test_rollback_both_failure_points(tmp_path):
    for point in ['after_debit','after_receipt']:
        w=wallet(tmp_path)
        with pytest.raises(RuntimeError):w.transfer('r','A','B',30,point)
        assert w.balances()=={'A':100,'B':0,'C':0}
    assert w.transfer('r','A','B',30)['balances']=={'A':70,'B':30}
def test_parallel_independent_connections(tmp_path):
    wallet(tmp_path)
    def send(dest):
        try:return Wallet(tmp_path/'ledger.db').transfer(dest,'A',dest,70)['amount']
        except TransferError as e:return e.status
    with ThreadPoolExecutor(2) as pool:r=list(pool.map(send,['B','C']))
    assert sorted(r)==[70,422];assert sum(Wallet(tmp_path/'ledger.db').balances().values())==100
    assert Wallet(tmp_path/'ledger.db').balances()['A']==30
def test_validation(tmp_path):
    w=wallet(tmp_path)
    for amount in [0,-1,True,1.5]:
        with pytest.raises(TransferError) as e:w.transfer('r','A','B',amount)
        assert e.value.status==400
    with pytest.raises(TransferError) as e:w.transfer('r','A','missing',10)
    assert e.value.status==404
    assert w.balances()['A']==100
def test_http_error_and_replay(tmp_path):
    w=wallet(tmp_path);c=TestClient(create_app(w));p=dict(id='r',source='A',destination='B',amount=30)
    assert c.post('/transfers',json=p).status_code==200
    assert c.post('/transfers',json=p).json()['balances']=={'A':70,'B':30}
    assert c.post('/transfers',json={**p,'amount':31}).status_code==409
    assert c.post('/transfers',json={**p,'id':'s','amount':True}).status_code==400

def test_part_three_pressure_case():
    from engine import Wallet,TransferError
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as d:
     w=Wallet(d+'/ledger.db',{'a':100,'b':0})
     try:w.transfer('r','a','b',30,'after_receipt')
     except RuntimeError:pass
     r=w.transfer('r','a','b',20);other=Wallet(d+'/ledger.db');again=other.transfer('r','a','b',20)
     try:other.transfer('r','a','b',30)
     except TransferError as e:status=e.status
     result=[r==again,other.balances(),status]
    assert result == [True, {'a': 80, 'b': 20}, 409]
