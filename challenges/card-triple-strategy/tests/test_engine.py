"""Candidate-visible behavioral fixtures; independent from server grading probes."""

def test_legal_triple():
    from engine import legal
    result=legal([{'id':'a','amount':4},{'id':'b','amount':5},{'id':'c','amount':6}],['a','b','c'])
    assert result == True

def test_repeated_id():
    from engine import legal
    result=legal([{'id':'a','amount':5},{'id':'b','amount':5},{'id':'c','amount':5}],['a','a','b'])
    assert result == False

def test_missing_id():
    from engine import legal
    result=legal([{'id':'a','amount':4},{'id':'b','amount':5},{'id':'c','amount':6}],['a','b','x'])
    assert result == False

def test_equal_amount_identities():
    from engine import legal
    result=legal([{'id':'a','amount':5},{'id':'b','amount':5},{'id':'c','amount':5}],['a','b','c'])
    assert result == True

def test_choose():
    from engine import choose
    result=choose([{'id':'c','amount':6},{'id':'a','amount':4},{'id':'b','amount':5}])
    assert result == ['a', 'b', 'c']

def test_none():
    from engine import choose
    result=choose([{'id':'a','amount':1},{'id':'b','amount':2},{'id':'c','amount':3}])
    assert result == None

def test_remove_copy():
    from engine import remove
    cs=[{'id':x,'amount':5} for x in 'abcd'];out=remove(cs,['a','b','c']);out[0]['amount']=8;result=cs[3]['amount']
    assert result == 5

def test_invalid_table():
    from engine import choose
    try:choose([{'id':'a','amount':10}])
    except ValueError:result=True
    else:result=False
    assert result == True
