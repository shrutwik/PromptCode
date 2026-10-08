"""Candidate-visible behavioral fixtures; independent from server grading probes."""

def test_suboptimal_valid():
    from engine import valid
    result=valid(['ab','cd'],[0])
    assert result == True

def test_internal_repeat():
    from engine import valid
    result=valid(['aa','b'],[0])
    assert result == False

def test_overlap():
    from engine import valid
    result=valid(['ab','bc'],[0,1])
    assert result == False

def test_greedy_counterexample():
    from engine import choose
    result=choose(['abc','ad','be','cf'])
    assert result == [1, 2, 3]

def test_duplicate_occurrence():
    from engine import choose
    result=choose(['ab','ab'])
    assert result == [0]

def test_empty():
    from engine import choose
    result=choose([])
    assert result == []

def test_invalid_index():
    from engine import valid
    result=valid(['ab'],[2])
    assert result == False

def test_all_disjoint():
    from engine import choose
    result=choose(['ab','cd','ef'])
    assert result == [0, 1, 2]


def test_part_three_pressure_case():
    from engine import choose,valid
    words=['ab', 'cd', 'ace', 'fg', ''];before=words[:];indices=choose(words);result=[indices,valid(words,indices),words==before]
    assert result == [[0, 1, 3], True, True]
