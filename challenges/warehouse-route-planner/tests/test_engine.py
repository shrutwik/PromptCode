"""Candidate-visible behavioral fixtures; independent from server grading probes."""

def test_render_endpoints():
    from engine import render_route
    result=render_route(['S.E'],[[0,0],[0,1],[0,2]])
    assert result == ['S*E']

def test_straight_route():
    from engine import shortest_route
    result=shortest_route(['S.E'])
    assert result == [[0, 0], [0, 1], [0, 2]]

def test_blocked_route():
    from engine import shortest_route
    result=shortest_route(['S#E'])
    assert result == None

def test_deterministic_tie():
    from engine import shortest_route
    result=shortest_route(['S.','.E'])
    assert result == [[0, 0], [0, 1], [1, 1]]

def test_revisit_with_badge():
    from engine import shortest_route
    result=shortest_route(['aS.AE'])
    assert result == [[0, 1], [0, 0], [0, 1], [0, 2], [0, 3], [0, 4]]

def test_wrong_badge():
    from engine import shortest_route
    result=shortest_route(['SbAE'])
    assert result == None

def test_directed_block():
    from engine import shortest_route
    result=shortest_route(['SaAE'],[([0,1],[0,2])])
    assert result == None

def test_input_unchanged():
    from engine import render_route
    rows=['S.E'];render_route(rows,[[0,1]]);result=rows
    assert result == ['S.E']


def test_part_three_pressure_case():
    from engine import shortest_route
    result=shortest_route(['S.AE','.a##'])
    assert result == [[0, 0], [0, 1], [1, 1], [0, 1], [0, 2], [0, 3]]
