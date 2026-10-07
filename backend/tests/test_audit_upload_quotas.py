from concurrent.futures import ThreadPoolExecutor

import pytest

from app.services.interview import workspace_quota as quota
from app.services.interview.workspace import write_file


def test_upload_bytes_and_files_are_bounded(tmp_path, monkeypatch):
    monkeypatch.setattr(quota,'SOURCE_BYTES',10)
    monkeypatch.setattr(quota,'SOURCE_FILES',2)
    write_file(tmp_path,'a.py','12345')
    write_file(tmp_path,'b.py','12345')
    with pytest.raises(ValueError): write_file(tmp_path,'c.py','x')
    with pytest.raises(ValueError): write_file(tmp_path,'a.py','123456')
    assert (tmp_path/'a.py').read_text()=='12345'
    write_file(tmp_path,'a.py','x')
    assert quota.usage(tmp_path)==(6,2)


def test_concurrent_uploads_cannot_overcommit(tmp_path,monkeypatch):
    monkeypatch.setattr(quota,'SOURCE_BYTES',10)
    def upload(i):
        try: write_file(tmp_path,f'file{i}.py','123456');return True
        except ValueError: return False
    with ThreadPoolExecutor(2) as pool: assert sum(pool.map(upload,range(2)))==1
    assert quota.usage(tmp_path)==(6,1)


def test_installed_dependencies_have_separate_budget(tmp_path,monkeypatch):
    monkeypatch.setattr(quota,'DEPENDENCY_BYTES',8)
    modules=tmp_path/'node_modules';modules.mkdir()
    (modules/'dep.js').write_bytes(b'x'*8)
    assert quota.usage(tmp_path)==(0,0)
    (modules/'dep2.js').write_bytes(b'x')
    with pytest.raises(ValueError): quota.usage(tmp_path)


def test_dependencies_cannot_be_uploaded(tmp_path):
    with pytest.raises(PermissionError): write_file(tmp_path,'node_modules/dep.js','x')


def test_path_depth_is_bounded(tmp_path):
    with pytest.raises(ValueError): write_file(tmp_path,'/'.join(['dir']*17)+ '/file.py','x')
