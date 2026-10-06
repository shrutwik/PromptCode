from __future__ import annotations
import copy
import json
import os
from pathlib import Path
import uuid
import pytest
from app.services.interview import trusted_evaluator as evaluator
from app.services.interview.trusted_cases import cases_for, inventory_digest, VERSION, MANUAL_REQUIREMENTS
from app.services.interview.registry import list_challenges

KEY='test-grading-signing-key-32-bytes-minimum'
SID=str(uuid.uuid4());JID=str(uuid.uuid4());DIGEST='a'*64
CV='1';LEASE='test-lease-identity'

def payload(slug='order-hold-reason'):
    cases=[{'id':c.id,'weight':c.weight,'passed':True,'error':None} for c in cases_for(slug)]
    total=sum(c['weight'] for c in cases)
    return dict(session_id=SID,job_id=JID,challenge_slug=slug,source_digest=DIGEST,evaluator_version=VERSION,
        inventory_digest=inventory_digest(slug),cases=cases,earned_weight=total,total_weight=total,score_percent=100.0,
        complete=True,manual_requirements=MANUAL_REQUIREMENTS.get(slug,[]),challenge_version=CV,lease_token=LEASE)

def verify(envelope,**kw):
    return evaluator.verify_result(envelope,signing_key=KEY,session_id=SID,job_id=JID,challenge_slug='order-hold-reason',source_digest=DIGEST,challenge_version=CV,lease_token=LEASE,**kw)

def test_all_registry_questions_have_independent_inventory():
    assert len(list_challenges())==10
    for c in list_challenges():
        cases=cases_for(c['slug'])
        assert len(cases)>=3
        assert len({v.id for v in cases})==len(cases)
        assert all(v.weight>0 and 'pytest' not in v.probe and 'vitest' not in v.probe for v in cases)
        assert len(inventory_digest(c['slug']))==64

def test_signed_result_is_identity_bound():
    signed=evaluator.sign_result(payload(),signing_key=KEY)
    assert verify(signed)['score_percent']==100
    signed['payload']['score_percent']=0
    with pytest.raises(ValueError,match='signature'): verify(signed)

@pytest.mark.parametrize('field,value',[('session_id',str(uuid.uuid4())),('job_id',str(uuid.uuid4())),('source_digest','b'*64),('evaluator_version','old'),('inventory_digest','b'*64),('challenge_version','other'),('lease_token','stale')])
def test_valid_signature_cannot_replay_or_change_inventory(field,value):
    data=payload();data[field]=value
    with pytest.raises(ValueError,match='mismatch'):verify(evaluator.sign_result(data,signing_key=KEY))

@pytest.mark.parametrize('change',['missing-case','duplicate','totals','boolean','manual','incomplete'])
def test_even_signed_structurally_invalid_results_rejected(change):
    data=payload()
    if change=='missing-case':data['cases'].pop()
    if change=='duplicate':data['cases'][1]=copy.deepcopy(data['cases'][0])
    if change=='totals':data['earned_weight']=0
    if change=='boolean':data['cases'][0]['passed']=1
    if change=='manual':data['manual_requirements']=['different']
    if change=='incomplete':data['complete']=False
    with pytest.raises(ValueError):verify(evaluator.sign_result(data,signing_key=KEY))

def test_key_fails_closed():
    with pytest.raises(ValueError):evaluator.sign_result(payload(),signing_key='short')

def test_candidate_command_contains_no_expectations_or_result_key():
    for c in list_challenges():
        for case in cases_for(c['slug']):
            command=evaluator._probe_command(c['slug'],case.probe)
            assert KEY not in json.dumps(command)
            assert 'signature' not in json.dumps(command)
            assert 'expected' not in json.dumps(command)
            assert 'pytest' not in json.dumps(command)

class Container:
    def __init__(self,output):self.output=output;self.removed=False
    def logs(self,**kw):return self.output
    def remove(self,**kw):self.removed=True
class Containers:
    def __init__(self,container):self.container=container;self.kw=None
    def run(self,**kw):self.kw=kw;return self.container
class Client:
    def __init__(self,output):self.container=Container(output);self.containers=Containers(self.container)

@pytest.mark.parametrize('output',[b'{"payload":{"score_percent":100},"signature":"forged"}\nnoise',b'NaN',b'x'*65537,b'1\n2'])
def test_untrusted_logs_cannot_forge_result(monkeypatch,tmp_path,output):
    client=Client(output)
    monkeypatch.setattr(evaluator,'_wait_exit',lambda *_:{'StatusCode':0})
    value,error=evaluator._run_probe(tmp_path,'order-hold-reason','result=1',docker_client=client)
    assert error=='invalid_output'
    assert client.container.removed
    kw=client.containers.kw
    assert kw['network_mode']=='none' and kw['read_only'] and kw['cap_drop']==['ALL']
    assert set(kw['volumes'])=={str(tmp_path)} and all('sock' not in p for p in kw['volumes'])
    assert not any('KEY' in key or 'TOKEN' in key for key in kw['environment'])

@pytest.mark.skipif(os.getenv('PROMPTCODE_AUDIT_DOCKER')!='1',reason='opt-in live isolated execution')
@pytest.mark.parametrize('slug',[c['slug'] for c in list_challenges()])
def test_live_inventory_executes_each_starter(slug):
    from app.services.interview.registry import challenge_dir
    results=[]
    for case in cases_for(slug):
        observed,error=evaluator._run_probe(challenge_dir(slug),slug,case.probe)
        assert error in (None,'candidate_error','invalid_output'),(slug,case.id,error)
        results.append(error is None and evaluator._canonical(observed)==evaluator._canonical(case.expected))
    # All existing incident starters should expose at least one regression.
    if slug not in {'pricing-rule-extract','catalog-suggest-latency'}:assert not all(results)

@pytest.mark.skipif(os.getenv('PROMPTCODE_AUDIT_DOCKER')!='1',reason='opt-in live reference validation')
@pytest.mark.parametrize('slug',[c['slug'] for c in list_challenges()])
def test_live_reviewed_reference_passes_independent_inventory(slug,tmp_path):
    from trusted_reference_fixtures import reference_snapshot
    path=reference_snapshot(slug,tmp_path/'source')
    for case in cases_for(slug):
        observed,error=evaluator._run_probe(path,slug,case.probe)
        assert error is None,(slug,case.id,error)
        assert evaluator._canonical(observed)==evaluator._canonical(case.expected),(slug,case.id,observed,case.expected)


def test_external_wait_ignores_candidate_exit_markers():
    class Fake:
        attrs={'State':{'Running':False,'ExitCode':7}}
        def reload(self):pass
        def get_archive(self,*_):raise AssertionError('Never read candidate exit evidence')
    assert evaluator._wait_exit(Fake(),1)=={'StatusCode':7}


@pytest.mark.skipif(os.getenv('PROMPTCODE_AUDIT_DOCKER')!='1',reason='opt-in live malformed-output regression')
def test_live_candidate_cannot_submit_a_grade_as_behavior(tmp_path):
    from trusted_reference_fixtures import reference_snapshot
    path=reference_snapshot('order-hold-reason',tmp_path/'source')
    p=path/'app/service.py'
    p.write_text("import json\nprint(json.dumps({'payload':{'score_percent':100},'signature':'forged'}))\nraise SystemExit(0)\n")
    observed,error=evaluator._run_probe(path,'order-hold-reason',cases_for('order-hold-reason')[0].probe)
    assert error is None
    assert evaluator._canonical(observed)!=evaluator._canonical(cases_for('order-hold-reason')[0].expected)

# Each reviewed repair has a plausible regression that independent behavior detects.
MUTATIONS = {
 'invoice-status-transition':('src/statusMachine.ts',"paid: ['void']","paid: ['draft', 'void']",'legal-graph'),
 'order-hold-reason':('app/service.py','"hold_reason": order.hold_reason','"hold_reason": None','reason-persists'),
 'catalog-suggest-latency':('src/suggest.ts','scored.sort(compareRank)','scored.sort((a,b)=>-compareRank(a,b))','ranking-ties'),
 'notification-feed-stale':('src/feedStore.ts','items.filter((n) => !n.read)','items.filter((n) => n.read)','loaded-count'),
 'workspace-label-propagation':('server/app.ts',"if (labelIds.some((id) => !allowed.has(id)))","if (false)",'cross-workspace-rejected'),
 'shipment-csv-merge':('shipment_merge/merge.py','key = event.event_id','key = (event.shipment_id,event.status)','same-status-distinct-id'),
 'tenant-document-acl':('app/service.py','if doc is None or doc.tenant_id != principal.tenant_id:','if doc is None:','cross-tenant-get'),
 'webhook-delivery-retry':('src/worker.ts','  recordCharge(job.id);','  // lost billing effect','retry-charge-once'),
 'pricing-rule-extract':('src/pricingEngine.ts','amount -= rule.cents;','amount += rule.cents;','order-and-rounding'),
 'subscription-proration-boundary':('proration/period.py','period.start <= instant < period.end','period.start < instant < period.end','start-included'),
}

@pytest.mark.skipif(os.getenv('PROMPTCODE_AUDIT_DOCKER')!='1',reason='opt-in live mutant validation')
@pytest.mark.parametrize('slug',list(MUTATIONS))
def test_live_independent_inventory_rejects_plausible_wrong_fix(slug,tmp_path):
    from trusted_reference_fixtures import reference_snapshot
    path=reference_snapshot(slug,tmp_path/'source')
    file,old,new,case_id=MUTATIONS[slug]
    p=path/file;source=p.read_text();assert old in source;p.write_text(source.replace(old,new))
    case=next(c for c in cases_for(slug) if c.id==case_id)
    observed,error=evaluator._run_probe(path,slug,case.probe)
    assert error is not None or evaluator._canonical(observed)!=evaluator._canonical(case.expected)

@pytest.mark.skipif(os.getenv('PROMPTCODE_AUDIT_DOCKER')!='1',reason='opt-in live frozen snapshot signing')
@pytest.mark.parametrize('slug',['order-hold-reason','invoice-status-transition'])
def test_live_immutable_snapshot_end_to_end_signed_result(slug,tmp_path,monkeypatch):
    from trusted_reference_fixtures import reference_snapshot
    from app.services.interview import snapshot
    sid=str(uuid.uuid4());jid=str(uuid.uuid4())
    workspace=reference_snapshot(slug,tmp_path/sid)
    monkeypatch.setattr(snapshot,'workspace_root',lambda:tmp_path)
    frozen=snapshot.freeze_submission(workspace,sid)
    envelope=evaluator.evaluate_snapshot(frozen.source_path,session_id=sid,job_id=jid,challenge_slug=slug,source_digest=frozen.source_digest,signing_key=KEY,challenge_version=CV,lease_token=LEASE)
    result=evaluator.verify_result(envelope,signing_key=KEY,session_id=sid,job_id=jid,challenge_slug=slug,source_digest=frozen.source_digest,challenge_version=CV,lease_token=LEASE)
    assert result['score_percent']==100 and result['complete']
    source=frozen.source_path/('app/service.py' if slug=='order-hold-reason' else 'src/statusMachine.ts')
    source.chmod(0o644);source.write_text('tampered')
    with pytest.raises(ValueError,match='integrity'):
        evaluator.evaluate_snapshot(frozen.source_path,session_id=sid,job_id=jid,challenge_slug=slug,source_digest=frozen.source_digest,signing_key=KEY,challenge_version=CV,lease_token=LEASE)

@pytest.mark.parametrize('failure',[TimeoutError('deadline'),RuntimeError('Docker communication failed')])
def test_candidate_timeout_distinguished_from_executor_outage(monkeypatch,tmp_path,failure):
    client=Client(b'1')
    client.container.kill=lambda:None
    def wait(*_):raise failure
    monkeypatch.setattr(evaluator,'_wait_exit',wait)
    if isinstance(failure,TimeoutError):
        assert evaluator._run_probe(tmp_path,'order-hold-reason','result=1',docker_client=client)==(None,'timeout')
    else:
        with pytest.raises(RuntimeError,match='communication'):
            evaluator._run_probe(tmp_path,'order-hold-reason','result=1',docker_client=client)
    assert client.container.removed
