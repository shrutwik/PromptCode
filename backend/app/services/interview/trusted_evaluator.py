"""Compare untrusted sandbox outputs outside the candidate interpreter and sign evidence.

Only the isolated executor calls evaluate_snapshot. A completed result proves the
listed behavioral checks, not that all requirements or human rubric dimensions pass.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from pathlib import Path
from typing import Any

from .trusted_cases import MANUAL_REQUIREMENTS, VERSION, cases_for, inventory_digest

MAX_OUTPUT_BYTES = 65536
PROBE_TIMEOUT_SECONDS = 12

def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def _key(signing_key: str) -> bytes:
    if not isinstance(signing_key, str) or len(signing_key.encode()) < 32:
        raise ValueError('Trusted grading signing key must contain at least 32 bytes')
    return signing_key.encode()

def sign_result(payload: dict[str, Any], *, signing_key: str) -> dict[str, Any]:
    return {'payload':payload,'signature':hmac.new(_key(signing_key),_canonical(payload),hashlib.sha256).hexdigest()}

def verify_result(envelope: dict[str, Any], *, signing_key: str, session_id: str,
                  job_id: str, challenge_slug: str, source_digest: str,
                  challenge_version: str, lease_token: str) -> dict[str, Any]:
    """Return authenticated payload; reject tampering, replay, inventory drift/incomplete results."""
    if not isinstance(envelope,dict) or set(envelope) != {'payload','signature'}:
        raise ValueError('Malformed trusted grading result')
    payload = envelope['payload']
    if not isinstance(payload,dict) or not isinstance(envelope['signature'],str):
        raise ValueError('Malformed trusted grading result')
    expected = hmac.new(_key(signing_key),_canonical(payload),hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected,envelope['signature']):
        raise ValueError('Invalid trusted grading signature')
    bindings={'session_id':str(session_id),'job_id':str(job_id),'challenge_slug':challenge_slug,'source_digest':source_digest,
              'evaluator_version':VERSION,'inventory_digest':inventory_digest(challenge_slug),
              'challenge_version':str(challenge_version),'lease_token':lease_token}
    if any(payload.get(k) != v for k,v in bindings.items()):
        raise ValueError('Trusted grading result identity or inventory mismatch')
    inventory=cases_for(challenge_slug)
    results=payload.get('cases')
    if not isinstance(results,list) or len(results)!=len(inventory):
        raise ValueError('Incomplete trusted grading inventory')
    earned=0
    for result,case in zip(results,inventory):
        if not isinstance(result,dict) or result.get('id')!=case.id or type(result.get('weight')) is not int or result.get('weight')!=case.weight or type(result.get('passed')) is not bool:
            raise ValueError('Invalid trusted grading case')
        if result.get('error') not in (None,'invalid_output','timeout','candidate_error'):
            raise ValueError('Invalid trusted grading error')
        if result['passed'] and result.get('error') is not None:
            raise ValueError('Invalid trusted grading success')
        earned += case.weight if result['passed'] else 0
    total=sum(c.weight for c in inventory)
    if (type(payload.get('earned_weight')) is not int or type(payload.get('total_weight')) is not int
            or type(payload.get('score_percent')) not in (int, float)
            or payload.get('earned_weight') != earned or payload.get('total_weight')!=total
            or payload.get('score_percent') != round(100*earned/total,2)):
        raise ValueError('Invalid trusted grading totals')
    if payload.get('manual_requirements') != MANUAL_REQUIREMENTS.get(challenge_slug,[]):
        raise ValueError('Invalid trusted grading coverage')
    if payload.get('complete') is not True:
        raise ValueError('Incomplete trusted grading execution')
    return payload


def _probe_command(slug: str, probe: str) -> list[str]:
    is_python=slug in {'order-hold-reason','shipment-csv-merge','tenant-document-acl','subscription-proration-boundary'}
    if is_python:
        # This adapter is not trusted grading logic: candidate imports may alter it.
        # Only its JSON output is observed. It contains no expectation or credentials.
        bootstrap="import os,sys,shutil,json;shutil.copytree('/source','/workspace',dirs_exist_ok=True,ignore=shutil.ignore_patterns('.venv','venv','node_modules','__pycache__'));os.chmod('/workspace',0o700);os.chdir('/workspace');sys.path.insert(0,'/workspace');ns={};exec("+repr(probe)+",ns);sys.stdout.write(json.dumps(ns['result'],allow_nan=False))"
        return ['python','-I','-c',bootstrap]
    # Transform only the probe and candidate sources; never execute package scripts.
    # esbuild and dependencies come from locked image content, not submitted files.
    imports=[]
    # All imports are service-owned one-line clauses at beginning. Split them out
    # since esbuild requires imports at module scope, outside the async function.
    import re
    rest=probe
    while rest.startswith('import '):
        m=re.match(r"import\s+.*?;",rest)
        if not m: raise ValueError('Malformed service probe')
        imports.append(m.group());rest=rest[m.end():].lstrip()
    source='\n'.join(imports)+'\nasync function main(){'+rest+'}\nmain().then(result=>process.stdout.write(JSON.stringify(result))).catch(()=>process.exit(3));'
    dep='/opt/promptcode-deps/'+slug+'/node_modules'
    bootstrap="const fs=require('fs');fs.cpSync('/source','/workspace',{recursive:true,filter:p=>!['node_modules','.venv','venv','__pycache__'].includes(require('path').basename(p))});fs.chmodSync('/workspace',0o700);fs.symlinkSync("+json.dumps(dep)+",'/workspace/node_modules','dir');const esbuild=require("+json.dumps(dep+'/esbuild')+");const out=esbuild.buildSync({stdin:{contents:"+json.dumps(source)+",resolveDir:'/workspace',loader:'ts'},bundle:true,platform:'node',format:'cjs',packages:'external',write:false});fs.writeFileSync('/workspace/probe.cjs',out.outputFiles[0].contents);require('/workspace/probe.cjs');"
    return ['node','-e',bootstrap]


def _wait_exit(container, timeout_seconds: int) -> dict[str, int]:
    # Unlike advisory test execution, never trust a candidate-written exit marker.
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        container.reload()
        state = container.attrs.get('State', {})
        if state.get('Running') is False:
            return {'StatusCode': int(state.get('ExitCode', 1))}
        time.sleep(.05)
    raise TimeoutError('Candidate execution deadline exceeded')


def _observe_probe_result(exit_code: int, raw: bytes) -> tuple[object,str|None]:
    """Map a probe process result onto the fixed observation contract.

    Shared by the docker and Modal paths so the grading taxonomy
    (``None``/``'timeout'``/``'candidate_error'``/``'invalid_output'``) cannot
    drift between substrates.
    """
    if int(exit_code) != 0: return None,'candidate_error'
    if len(raw)>MAX_OUTPUT_BYTES: return None,'invalid_output'
    try:
        value=json.loads(raw.decode('utf-8'),parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if len(_canonical(value))>MAX_OUTPUT_BYTES: return None,'invalid_output'
        return value,None
    except (ValueError,UnicodeError,TypeError,RecursionError): return None,'invalid_output'


def _run_probe_container(snapshot_path: Path, argv: list[str], *, image: str,
                         timeout_seconds: int = PROBE_TIMEOUT_SECONDS, docker_client=None) -> tuple[int,bytes]:
    """Run one probe argv in the locked-down Docker container.

    This is the existing self-managed path, unchanged; only the deadline is now
    reported to the caller as :class:`TimeoutError` instead of a return value.
    """
    import docker
    client=docker_client or docker.from_env()
    container=None
    try:
        container=client.containers.run(image=image,command=list(argv),
            user='10001:10001',working_dir='/workspace',volumes={str(snapshot_path):{'bind':'/source','mode':'ro'}},
            environment={'HOME':'/tmp','PYTHONDONTWRITEBYTECODE':'1'},
            network_mode='none',extra_hosts={'localhost':'127.0.0.1'},read_only=True,
            tmpfs={'/tmp':'rw,noexec,nosuid,nodev,size=64m','/workspace':'rw,nosuid,nodev,size=256m,uid=10001,gid=10001,mode=0700'},
            mem_limit='768m',nano_cpus=1500000000,pids_limit=128,cap_drop=['ALL'],security_opt=['no-new-privileges'],
            detach=True,stdout=True,stderr=True,remove=False,
            log_config={'type':'local','config':{'max-size':'64k','max-file':'1','compress':'false'}},
            labels={'promptcode.role':'interview-runner','promptcode.component':'trusted-grading','promptcode.expires_at':str(time.time()+timeout_seconds+30)})
        try:
            status=_wait_exit(container,timeout_seconds)
        except TimeoutError:
            container.kill()
            raise
        code=int(status.get('StatusCode',1))
        return code,(container.logs(stdout=True,stderr=False) if code == 0 else b'')
    finally:
        if container is not None:
            try: container.remove(force=True)
            except Exception: pass
        if docker_client is None: client.close()


def _run_probe(snapshot_path: Path, slug: str, probe: str, *, docker_client=None, image=None) -> tuple[object,str|None]:
    """Run one independent probe through the configured execution backend.

    ``docker`` keeps the existing container path; ``modal`` runs the identical
    argv in a Modal Sandbox. The returned observation contract is the same for
    both, which is what ``_run_probe_sweep`` and grading depend on.
    """
    from .registry import get_runner_config
    cfg=get_runner_config(slug)
    argv=_probe_command(slug,probe)
    resolved_image=str(image or cfg['image'])
    if docker_client is not None:
        from app.services.execution.backend import DockerExecutionBackend
        backend=DockerExecutionBackend(docker_client)
    else:
        from app.services.execution.backend import get_execution_backend
        backend=get_execution_backend()
    from app.services.execution.modal_backend import SandboxTimeout
    try:
        # Ask for one byte more than the accepted maximum: the Docker path rejects
        # oversized observations instead of truncating them, so the backend must be
        # able to report overflow rather than silently capping it.
        exit_code,raw=backend.run_probe(source_dir=snapshot_path,argv=argv,image=resolved_image,
            timeout_seconds=PROBE_TIMEOUT_SECONDS,output_limit_bytes=MAX_OUTPUT_BYTES+1)
    except (TimeoutError,SandboxTimeout):
        return None,'timeout'
    return _observe_probe_result(exit_code,raw)


def evaluate_snapshot(snapshot_path: str|Path, *, session_id: str, job_id: str,
                      challenge_slug: str, source_digest: str, signing_key: str,
                      challenge_version: str, lease_token: str) -> dict[str,Any]:
    """Synchronous executor entrypoint. Infrastructure failures propagate for durable retry."""
    _key(signing_key)
    if not challenge_version or not lease_token or len(lease_token)>256:
        raise ValueError('Missing trusted grading execution identity')
    uuid.UUID(str(session_id));uuid.UUID(str(job_id))
    from .snapshot import verify_snapshot
    path=Path(snapshot_path).resolve()
    verify_snapshot(path,source_digest)
    inventory=cases_for(challenge_slug)
    from app.core.config import get_settings
    settings = get_settings()
    remote = None
    if getattr(settings, "execution_broker_url", ""):
        import httpx

        from .execution_transfer import bundle_source
        bundle = bundle_source(path)
        if bundle.digest != source_digest:
            raise ValueError("Submitted source integrity check failed")
        import random

        from app.core.execution_transport import broker_json, broker_tls_context
        retry_deadline = time.monotonic() + min(30, settings.grading_job_timeout_seconds / 2)
        with httpx.Client(timeout=settings.grading_job_timeout_seconds, trust_env=False, verify=broker_tls_context(settings)) as client:
            while True:
                try:
                    body = broker_json(client, 'POST', settings.execution_broker_url.rstrip('/') + '/v1/interview/probes',
                        headers={'Authorization': 'Bearer ' + settings.sandbox_executor_token},
                        json={'challenge_slug': challenge_slug, 'source': bundle.model_dump(), 'evaluator_version': VERSION})
                    break
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code != 503 or time.monotonic() >= retry_deadline:
                        raise
                    # Admission rejection did not run candidate code. Preserve the
                    # durable job's retry allowance while existing slots drain.
                    time.sleep(random.uniform(.20, .35))
        remote = body.get('observations')
        if body.get('digest') != source_digest or not isinstance(remote, list) or len(remote) != len(inventory):
            raise ValueError("Invalid execution observations")
    results=[]
    for index, case in enumerate(inventory):
        if remote is None:
            observed,error=_run_probe(path,challenge_slug,case.probe)
        else:
            item = remote[index]
            if (not isinstance(item, dict) or set(item) != {'id', 'observed', 'error'}
                    or item['id'] != case.id or item['error'] not in (None, 'timeout', 'candidate_error', 'invalid_output')):
                raise ValueError("Invalid execution observation")
            observed, error = item['observed'], item['error']
        # Type-sensitive canonical comparison prevents Python True == 1 surprises.
        passed=error is None and _canonical(observed)==_canonical(case.expected)
        results.append({'id':case.id,'weight':case.weight,'passed':passed,'error':error})
    verify_snapshot(path,source_digest)
    earned=sum(c['weight'] for c in results if c['passed']);total=sum(c.weight for c in inventory)
    payload={'session_id':str(session_id),'job_id':str(job_id),'challenge_slug':challenge_slug,'source_digest':source_digest,
             'evaluator_version':VERSION,'inventory_digest':inventory_digest(challenge_slug),'cases':results,
             'earned_weight':earned,'total_weight':total,'score_percent':round(100*earned/total,2),'complete':True,
             'manual_requirements':MANUAL_REQUIREMENTS.get(challenge_slug,[]),
             'challenge_version':str(challenge_version),'lease_token':lease_token}
    return sign_result(payload,signing_key=signing_key)
