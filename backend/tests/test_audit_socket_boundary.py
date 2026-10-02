"""The public API must not inherit Docker daemon authority."""
from pathlib import Path


def test_public_backend_has_no_docker_socket_mount():
    source = (Path(__file__).resolve().parents[2] / 'docker-compose.yml').read_text()
    backend = source.split('\n  backend:\n', 1)[1].split('\n  worker:', 1)[0]
    assert '/var/run/docker.sock' not in backend
