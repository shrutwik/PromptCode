"""Host-wide execution slots. All workers must share this private lock directory."""
from contextlib import contextmanager
import fcntl
from pathlib import Path
from app.core.config import get_settings


class RunnerBusy(RuntimeError):
    pass


@contextmanager
def execution_slot():
    settings = get_settings()
    base = Path(settings.interview_workspace_root) if settings.interview_workspace_root else Path(__file__).resolve().parents[2] / 'data' / 'interview_workspaces'
    root = base / '.execution-slots'
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    for index in range(settings.max_runners):
        slot = (root / str(index)).open('a')
        try:
            fcntl.flock(slot, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            slot.close()
            continue
        try:
            yield
        finally:
            slot.close()
        return
    raise RunnerBusy('Execution capacity reached. Retry shortly.')
