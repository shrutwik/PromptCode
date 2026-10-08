"""Protect candidate-safe progression, specification parity and part grading boundaries."""
import json

import pytest

from app.schemas.interview import LevelStepResponse
from app.services.interview.levels import level_view
from app.services.interview.question_parts import parts_for
from app.services.interview.registry import (
    CHALLENGES_DIR,
    challenge_dir,
    list_challenges,
)
from scripts.run_interview_publish_gate import CONTRACT_PATH, run_gate

FEATURED=[c['slug'] for c in list_challenges() if c.get('featured_rank')]

@pytest.mark.parametrize('slug',FEATURED)
def test_parts_are_specific_candidate_safe_and_match_readme(slug):
    parts=parts_for(slug)
    assert [p['number'] for p in parts]==[1,2,3,4]
    assert [p['mode'] for p in parts]==['baseline']*3+['discussion']
    assert all(set(p)=={'number','title','task','acceptance','mode'} for p in parts)
    readme=(challenge_dir(slug)/'README.md').read_text()
    for part in parts:
        assert part['title'] in readme and part['task'] in readme
        assert all(line in readme for line in part['acceptance'])
    view=LevelStepResponse(**level_view(slug,0,tests_on_step=1))
    assert [p.model_dump() for p in view.parts]==parts
    assert view.total==1 and not view.can_advance


def test_part_views_are_copied_and_extra_practice_stays_unchanged():
    slug=FEATURED[0];parts=parts_for(slug);parts[0]['acceptance'][0]='mutated'
    assert parts_for(slug)[0]['acceptance'][0]!='mutated'
    for card in list_challenges():
        if not card.get('featured_rank'):assert parts_for(card['slug'])==[]


@pytest.mark.parametrize('regression',['missing-part','duplicate-case','uncovered-case','graded-discussion','empty-baseline'])
def test_part_regressions_block_publication(regression,tmp_path):
    quality=json.loads(CONTRACT_PATH.read_text());parts=quality['questions'][FEATURED[0]]['parts']
    if regression=='missing-part':parts.pop()
    elif regression=='duplicate-case':parts[1]['case_ids'].append(parts[0]['case_ids'][0])
    elif regression=='uncovered-case':parts[0]['case_ids'].pop()
    elif regression=='graded-discussion':parts[3]['case_ids']=[parts[0]['case_ids'][0]]
    else:parts[1]['case_ids']=[]
    path=tmp_path/'quality.json';path.write_text(json.dumps(quality))
    result=run_gate(challenges_dir=CHALLENGES_DIR,contract_path=path)
    assert not result['pass']
    assert any(row['slug']==FEATURED[0] and not row['pass'] for row in result['questions'])
