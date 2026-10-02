"""Local offline npm attacks; disposable bounded mounts and test fixtures only."""
import json
import os
import pytest
from app.services.interview.runner import restore_node_manifests

pytestmark=pytest.mark.skipif(os.getenv('PROMPTCODE_AUDIT_DOCKER')!='1',reason='Live local Docker audit opt-in required')


def test_live_npm_scripts_manifest_config_and_node_privileges(tmp_path):
    import docker
    workspace=tmp_path/'candidate';workspace.mkdir()
    starter=tmp_path/'candidate.starter';starter.mkdir()
    trusted={'name':'audit-fixture','version':'1.0.0','dependencies':{'audit-dep':'file:./dependency'},'scripts':{'preinstall':'touch /workspace/ROOT_SCRIPT'}}
    (starter/'package.json').write_text(json.dumps(trusted))
    (workspace/'package.json').write_text(json.dumps({'scripts':{'preinstall':'touch /workspace/REWRITTEN_MANIFEST'}}))
    (workspace/'.npmrc').write_text('ignore-scripts=false\nregistry=http://169.254.169.254\n')
    dependency=workspace/'dependency';dependency.mkdir()
    (dependency/'package.json').write_text(json.dumps({'name':'audit-dep','version':'1.0.0','scripts':{'install':'touch /workspace/DEP_SCRIPT'}}))
    assert restore_node_manifests(workspace)
    assert json.loads((workspace/'package.json').read_text())==trusted
    assert not (workspace/'.npmrc').exists()
    # Try hostile project config again: CLI/env controls must still win.
    (workspace/'.npmrc').write_text('ignore-scripts=false\nregistry=http://169.254.169.254\n')
    before={str(p.relative_to(workspace)):p.read_bytes() for p in workspace.rglob('*') if p.is_file()}
    client=docker.from_env(timeout=10);container=None
    probe="""const fs=require('fs'),assert=require('assert');
assert(process.getuid()!==0);
assert(!fs.existsSync('/var/run/docker.sock'));
assert(!Object.keys(process.env).some(k=>k.startsWith('PROMPTCODE_')||k==='OPENAI_API_KEY'));
const status=fs.readFileSync('/proc/self/status','utf8');
assert(/CapEff:\\s*0+\\s/.test(status));assert(/NoNewPrivs:\\s*1/.test(status));
assert(!fs.existsSync('/workspace/ROOT_SCRIPT'));assert(!fs.existsSync('/workspace/DEP_SCRIPT'));assert(!fs.existsSync('/workspace/REWRITTEN_MANIFEST'));
assert(fs.existsSync('/workspace/node_modules/audit-dep/package.json'));
let blocked=false;try{fs.writeFileSync('/etc/audit-marker','x')}catch(e){blocked=true}assert(blocked);
console.log('NODE_NPM_ATTACKS_BLOCKED');"""
    (workspace/'probe.js').write_text(probe)
    try:
        container=client.containers.run('promptcode-runner-node:latest',
            ['sh','-c',': > /tmp/promptcode-global.npmrc && cp -R /source/. /workspace/ && npm install --offline --ignore-scripts --no-audit --no-fund --userconfig=/dev/null --globalconfig=/tmp/promptcode-global.npmrc && node /workspace/probe.js'],
            volumes={str(workspace):{'bind':'/source','mode':'ro'}},working_dir='/workspace',
            tmpfs={'/workspace':'rw,nosuid,nodev,size=64m,uid=10001,gid=10001,mode=0700','/tmp':'rw,nosuid,size=32m'},
            network_disabled=True,read_only=True,cap_drop=['ALL'],security_opt=['no-new-privileges'],
            mem_limit='256m',nano_cpus=500000000,pids_limit=32,detach=True,
            environment={'HOME':'/tmp','npm_config_cache':'/tmp/cache','npm_config_ignore_scripts':'true'},
            labels={'promptcode.audit':'test-only'})
        result=container.wait(timeout=20)
        assert result['StatusCode']==0,container.logs().decode()
        assert b'NODE_NPM_ATTACKS_BLOCKED' in container.logs()
        assert {name:(workspace/name).read_bytes() for name in before}==before
        assert not (workspace/'node_modules').exists()
    finally:
        if container is not None: container.remove(force=True,v=True)
        client.close()
