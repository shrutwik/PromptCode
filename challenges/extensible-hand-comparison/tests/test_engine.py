import pytest
from engine import parse_card,compare,hand_key

def test_ten_and_ace():
    assert parse_card('10H')==(10,'H')
    assert parse_card('AS')==(14,'S')
def test_invalid_card():
    for c in ['1H','10X','11S','ah','']:
        with pytest.raises(ValueError):parse_card(c)
def test_duplicate_identity():
    with pytest.raises(ValueError):hand_key(['2H','2H','3S'])
def test_category_precedence():
    assert compare(['2H','2D','2C'],['AH','AD','KS'])==1
def test_pair_kicker():
    assert compare(['7H','7D','AS'],['7C','7S','KH'])==1
def test_distinct_key_and_preservation():
    a=['AH','KD','2S'];b=['AC','QD','JS'];before=a[:]
    assert compare(a,b)==1
    assert a==before
def test_suits_tie():
    assert compare(['AH','KD','2S'],['AC','KS','2D'])==0
def test_rule_variant_and_rejection():
    assert compare(['2H','2D','2C'],['AH','AD','KS'],['triple','distinct','pair'])==-1
    with pytest.raises(ValueError):hand_key(['2H','3H','4H'],['pair','pair','triple'])

    with pytest.raises(ValueError):hand_key(None)
    with pytest.raises(ValueError):hand_key(['2H','3H','4H'],[{},'pair','triple'])

def test_part_three_pressure_case():
    from engine import compare
    a=['2H', '3C', '4D'];b=['2H', '2C', '3D'];c=['2H', '2C', '2D'];result=[compare(a,b),compare(b,c),compare(a,c),compare(c,a)]
    assert result == [-1, -1, -1, 1]
