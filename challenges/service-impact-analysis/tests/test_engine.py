"""Candidate-visible behavioral fixtures; independent from server grading probes."""

def test_normalize():
    from contracts import normalize
    result=normalize('//app///src/')
    assert result == '/app/src'

def test_root():
    from contracts import normalize
    result=normalize('////')
    assert result == '/'

def test_boundary():
    from contracts import ancestor
    result=ancestor('/app','/apple/x')
    assert result == False

def test_file():
    from engine import impacted
    result=impacted({'a':['/lib']},{},[('/lib/x',False)])
    assert result == ['a']

def test_dependents():
    from engine import impacted
    result=impacted({'a':['/app'],'b':['/lib']},{'a':['b']},[('/lib/x',False)])
    assert result == ['a', 'b']

def test_delete_subtree():
    from engine import impacted
    result=impacted({'b':['/lib/sub/x']},{},[('/lib',True)])
    assert result == ['b']

def test_cycle():
    from engine import impacted
    result=impacted({'a':['/a'],'b':['/b']},{'a':['b'],'b':['a']},[('/b/x',False)])
    assert result == ['a', 'b']

def test_invalid_path():
    from engine import impacted
    try:impacted({'a':['/x/../y']},{},[])
    except ValueError:result=True
    else:result=False
    assert result == True


def test_part_three_pressure_case():
    from engine import impacted
    w={'api':['/repo/api/src'],'apis':['/repo/apis'],'worker':['/repo/worker']};d={'worker':['api']};edits=[('/repo/api/',True),('/repo//api/',True)]
    a=impacted(w,d,edits);b=impacted(w,d,list(reversed(edits)));result=[a,b,impacted(w,d,[('/',True)])]
    assert result == [['api', 'worker'], ['api', 'worker'], ['api', 'apis', 'worker']]
