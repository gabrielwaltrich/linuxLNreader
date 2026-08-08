from __future__ import annotations

from dataclasses import dataclass
import errno
import fcntl
import os
from pathlib import Path

from novel_reader.logging_setup import state_dir


# flock locks belong to the process. Keep a small registry so repeated
# cli.run() calls or multiple internal components in the same process share
# one descriptor instead of competing with themselves.
_PROCESS_LOCKS: dict[str, tuple[object, int]] = {}


class InstanceAlreadyRunningError(RuntimeError):
    pass


@dataclass(slots=True)
class InstanceLockInfo:
    path: Path
    pid: int


class InstanceLock:
    """Linux advisory process lock for the user data store.

    The lock is intentionally owned by the top-level GUI/CLI process rather
    than by every LibraryDatabase object. This allows multiple DB helper
    objects inside one Reader process while preventing two Reader processes
    from writing concurrently.
    """

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else state_dir() / "instance.lock"
        self._handle = None

    @property
    def acquired(self) -> bool:
        return self._handle is not None

    def acquire(self) -> InstanceLockInfo:
        if self.acquired:
            return InstanceLockInfo(self.path, os.getpid())

        self.path.parent.mkdir(parents=True, exist_ok=True)
        key = str(self.path.resolve())

        existing = _PROCESS_LOCKS.get(key)
        if existing is not None:
            handle, refs = existing
            _PROCESS_LOCKS[key] = (handle, refs + 1)
            self._handle = handle
            self._registry_key = key
            return InstanceLockInfo(self.path, os.getpid())

        handle = self.path.open("a+", encoding="utf-8")

        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            handle.seek(0)
            owner = handle.read().strip()
            handle.close()
            if exc.errno in (errno.EACCES, errno.EAGAIN):
                suffix = f" (PID {owner})" if owner else ""
                raise InstanceAlreadyRunningError(
                    "Outra instância do Novel Reader já está usando a Library"
                    f"{suffix}."
                ) from exc
            raise

        handle.seek(0)
        handle.truncate()
        handle.write(str(os.getpid()))
        handle.flush()
        os.fsync(handle.fileno())
        self._handle = handle
        self._registry_key = key
        _PROCESS_LOCKS[key] = (handle, 1)
        return InstanceLockInfo(self.path, os.getpid())

    def release(self) -> None:
        handle = self._handle
        if handle is None:
            return

        key = getattr(self, "_registry_key", str(self.path.resolve()))
        existing = _PROCESS_LOCKS.get(key)
        if existing is not None:
            shared_handle, refs = existing
            if refs > 1:
                _PROCESS_LOCKS[key] = (shared_handle, refs - 1)
                self._handle = None
                return
            _PROCESS_LOCKS.pop(key, None)

        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            try:
                handle.close()
            finally:
                self._handle = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.release()
        return False
