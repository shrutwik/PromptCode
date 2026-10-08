"""Candidate-visible behavioral fixtures; independent from server grading probes."""

def test_metadata_digits():
    from contracts import load_case
    import json
    result=load_case(json.dumps({'costs':{'+':12,'-':3,'*':17,'/':4},'totals':[123,12],'program':['# note','','res = x + 1']}))['totals']
    assert result == [123, 12]

def test_per_file_costs():
    from contracts import load_case
    import json
    result=load_case(json.dumps({'costs':{'+':12,'-':3,'*':17,'/':4},'totals':[12,1],'program':['res=x+1']}))['costs']['+']
    assert result == 12

def test_basic():
    from engine import analyze
    result=analyze(['a=x+1','res=a'],{'+':2,'-':2,'*':3,'/':4})
    assert result == [2, 1]

def test_operand_overlap():
    from engine import analyze
    result=analyze(['a=x+1','b=a*2','res=b'],{'+':2,'-':2,'*':3,'/':4})
    assert result == [5, 2]

def test_parallel_liveness():
    from engine import analyze
    result=analyze(['a=x+1','b=y+1','res=a+b'],{'+':2,'-':2,'*':3,'/':4})
    assert result == [6, 3]

def test_dead_code():
    from engine import analyze
    result=analyze(['a=x+1','unused=y*9','res=a'],{'+':2,'-':2,'*':3,'/':4},True)
    assert result == [2, 1]

def test_constant_propagation():
    from engine import analyze
    result=analyze(['a=2+3','res=a*4'],{'+':2,'-':2,'*':3,'/':4},True)
    assert result == [0, 0]

def test_alias_storage():
    from engine import analyze
    result=analyze(['a=x+1','b=a','res=b'],{'+':2,'-':2,'*':3,'/':4})
    assert result == [2, 1]


def test_part_three_pressure_case():
    from engine import analyze
    p=['unused=u/v', 'a=x+y', 'b=a', 'c=b*z', 'res=a+c'];costs={'+': 2, '-': 1, '*': 3, '/': 4};result=[analyze(p,costs),analyze(p,costs,True)]
    assert result == [[11, 3], [7, 3]]
