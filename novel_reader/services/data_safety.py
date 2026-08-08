from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import time


@dataclass(slots=True)
class DatabaseHealth:
    ok: bool
    integrity: str
    path: Path
    size_bytes: int


@dataclass(slots=True)
class BackupRecord:
    sqlite_path: Path
    json_path: Path | None
    created_at: float


class DataSafetyManager:
    def __init__(
        self,
        database_path: str | Path,
        *,
        backup_dir: str | Path | None = None,
        retention: int = 5,
        min_interval_hours: int = 12,
    ):
        self.database_path = Path(database_path).expanduser()
        self.backup_dir = (
            Path(backup_dir).expanduser()
            if backup_dir
            else self.database_path.parent / "backups"
        )
        self.retention = max(1, min(int(retention), 20))
        self.min_interval_hours = max(1, int(min_interval_hours))

    def check_database(self) -> DatabaseHealth:
        if not self.database_path.exists():
            return DatabaseHealth(
                ok=True,
                integrity="novo banco (ainda não existe)",
                path=self.database_path,
                size_bytes=0,
            )

        size = self.database_path.stat().st_size
        try:
            with sqlite3.connect(
                f"file:{self.database_path}?mode=ro",
                uri=True,
            ) as db:
                row = db.execute("PRAGMA integrity_check").fetchone()
                integrity = str(row[0] if row else "sem resultado")
            return DatabaseHealth(
                ok=integrity.casefold() == "ok",
                integrity=integrity,
                path=self.database_path,
                size_bytes=size,
            )
        except sqlite3.DatabaseError as exc:
            return DatabaseHealth(
                ok=False,
                integrity=f"{type(exc).__name__}: {exc}",
                path=self.database_path,
                size_bytes=size,
            )

    def backup_now(self, *, include_json: bool = True) -> BackupRecord | None:
        if not self.database_path.exists():
            return None

        health = self.check_database()
        if not health.ok:
            raise RuntimeError(
                "O banco atual falhou no integrity_check; backup automático "
                "foi interrompido para não substituir cópias saudáveis."
            )

        self.backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        sqlite_target = self.backup_dir / f"library-backup-{stamp}.sqlite3"

        # sqlite3.backup() creates a consistent snapshot even if WAL is active.
        with sqlite3.connect(self.database_path) as source:
            with sqlite3.connect(sqlite_target) as target:
                source.backup(target)

        json_target = None
        if include_json:
            json_target = self.backup_dir / f"library-backup-{stamp}.json"
            self._write_portable_json(json_target)

        record = BackupRecord(
            sqlite_path=sqlite_target,
            json_path=json_target,
            created_at=sqlite_target.stat().st_mtime,
        )
        self.prune()
        return record

    def auto_backup_if_due(self) -> BackupRecord | None:
        if not self.database_path.exists():
            return None

        newest = self.latest_backup()
        if newest is not None:
            age = time.time() - newest.created_at
            interval = self.min_interval_hours * 3600
            if age < interval:
                return None

        return self.backup_now(include_json=True)

    def list_backups(self) -> list[BackupRecord]:
        if not self.backup_dir.exists():
            return []

        records: list[BackupRecord] = []
        for sqlite_path in self.backup_dir.glob("library-backup-*.sqlite3"):
            stem = sqlite_path.stem
            json_path = sqlite_path.with_suffix(".json")
            try:
                created = sqlite_path.stat().st_mtime
            except OSError:
                continue
            records.append(
                BackupRecord(
                    sqlite_path=sqlite_path,
                    json_path=json_path if json_path.exists() else None,
                    created_at=created,
                )
            )
        records.sort(key=lambda item: item.created_at, reverse=True)
        return records

    def latest_backup(self) -> BackupRecord | None:
        records = self.list_backups()
        return records[0] if records else None

    def prune(self) -> int:
        records = self.list_backups()
        removed = 0
        for record in records[self.retention:]:
            for path in (record.sqlite_path, record.json_path):
                if path is None:
                    continue
                try:
                    path.unlink()
                    removed += 1
                except FileNotFoundError:
                    pass
        return removed

    def validate_backup(self, path: str | Path) -> DatabaseHealth:
        target = Path(path).expanduser()
        if target.suffix.casefold() != ".sqlite3":
            raise ValueError("a recuperação completa exige um backup .sqlite3")
        if not target.exists():
            raise FileNotFoundError(target)

        manager = DataSafetyManager(
            target,
            backup_dir=self.backup_dir,
            retention=self.retention,
            min_interval_hours=self.min_interval_hours,
        )
        return manager.check_database()

    def restore_database(self, backup_path: str | Path) -> Path:
        backup = Path(backup_path).expanduser().resolve()
        health = self.validate_backup(backup)
        if not health.ok:
            raise RuntimeError(
                f"Backup inválido/corrompido: {health.integrity}"
            )

        self.database_path.parent.mkdir(parents=True, exist_ok=True)

        # Preserve the current healthy DB before replacing it.
        if self.database_path.exists():
            current_health = self.check_database()
            if current_health.ok:
                self.backup_now(include_json=True)

        fd, temp_name = tempfile.mkstemp(
            prefix=".library-restore-",
            suffix=".sqlite3",
            dir=self.database_path.parent,
        )
        import os
        os.close(fd)
        Path(temp_name).unlink(missing_ok=True)
        try:
            shutil.copy2(backup, temp_name)
            restored_health = DataSafetyManager(temp_name).check_database()
            if not restored_health.ok:
                raise RuntimeError(
                    f"Cópia restaurada falhou na validação: "
                    f"{restored_health.integrity}"
                )
            Path(temp_name).replace(self.database_path)
        finally:
            Path(temp_name).unlink(missing_ok=True)

        # Remove stale WAL/SHM files after an offline restore.
        for suffix in ("-wal", "-shm"):
            Path(str(self.database_path) + suffix).unlink(missing_ok=True)

        return self.database_path

    def _write_portable_json(self, target: Path) -> None:
        """Write a portable emergency export without importing Qt/UI code."""
        payload = {
            "format": "novel-reader-safety-backup",
            "version": 1,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "books": [],
        }

        with sqlite3.connect(self.database_path) as db:
            db.row_factory = sqlite3.Row
            tables = {
                row["name"]
                for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            if "books" not in tables:
                target.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                return

            book_columns = {
                row["name"]
                for row in db.execute("PRAGMA table_info(books)").fetchall()
            }
            history_columns = (
                {
                    row["name"]
                    for row in db.execute(
                        "PRAGMA table_info(reading_history)"
                    ).fetchall()
                }
                if "reading_history" in tables
                else set()
            )

            books = db.execute("SELECT * FROM books ORDER BY id").fetchall()
            for book in books:
                entry = {key: book[key] for key in book.keys()}
                entry["chapters"] = []
                if "reading_history" in tables and "book_id" in history_columns:
                    chapters = db.execute(
                        "SELECT * FROM reading_history WHERE book_id = ? "
                        "ORDER BY last_opened",
                        (book["id"],),
                    ).fetchall()
                    entry["chapters"] = [
                        {key: chapter[key] for key in chapter.keys()}
                        for chapter in chapters
                    ]
                payload["books"].append(entry)

        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
