import pytest
from app.services.interview.execution_feedback import complete_report, advisory_scoring


def report(ids=('tests/test_a.py::test_a',)):
    return {'version':1,'complete':True,'exit_code':0,'records':[
        {'id':i,'phase':p,'outcome':'passed'} for i in ids for p in ('setup','call','teardown')]}


def test_complete_inventory_is_required():
    assert complete_report(report(), ['tests/test_a.py::test_a'])
    assert not complete_report(report(), [])
    assert not complete_report(report(), ['tests/test_a.py::test_a','tests/test_a.py::test_b'])


@pytest.mark.parametrize('mode', ['missing','short','duplicate','skipped','failed','unfinished','exit','unexpected'])
def test_incomplete_or_invalid_report_fails(mode):
    data=report()
    if mode=='missing': data=None
    if mode=='short': data['records'].pop()
    if mode=='duplicate': data['records'].append(data['records'][0])
    if mode in ('skipped','failed'): data['records'][1]['outcome']=mode
    if mode=='unfinished': data['complete']=False
    if mode=='exit': data['exit_code']=1
    if mode=='unexpected': data['records'][0]['id']='other'
    assert not complete_report(data, ['tests/test_a.py::test_a'])


def test_no_execution_input_can_authorize_a_score():
    scored=advisory_scoring({'total_score':100,'rubric':{'A_correctness':{'score':25,'max':25}},'test_summary':{'ok':True}})
    assert scored['total_score']==0
    assert scored['rubric']['A_correctness']['score']==0
    assert scored['metrics']['authoritative'] is False
    assert scored['test_summary']['authoritative'] is False
    assert scored['test_summary']['correctness_visible'] is None


def test_public_scorers_do_not_grade_forged_passes():
    from app.services.interview.rubric import score_session, score_session_v2
    for scorer in (score_session,score_session_v2):
        scored=scorer(events=[],test_summary={'ok':True,'counts':{'passed':999}},ai_prompts=[])
        assert scored['total_score']==0
        assert all(v['score']==0 for v in scored['rubric'].values())
