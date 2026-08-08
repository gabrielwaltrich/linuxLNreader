from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
import tempfile

from novel_reader.app_config import AppConfigStore
from novel_reader.database import LibraryDatabase
from novel_reader.models import Chapter
from novel_reader.services.cache_manager import CacheManager
from novel_reader.services.chapter_cache import ChapterCache
from novel_reader.services.data_safety import DataSafetyManager
from novel_reader.services.instance_lock import InstanceLock
from novel_reader.services.search_service import fuzzy_match
from novel_reader.system_diagnostics import run_diagnostics, overall_ok


@dataclass(slots=True)
class SelfTestItem:
    name: str
    ok: bool
    detail: str = ""


def _run(name, func):
    try:
        return SelfTestItem(name, True, str(func() or "OK"))
    except Exception as exc:
        return SelfTestItem(name, False, f"{type(exc).__name__}: {exc}")


def run_self_test() -> list[SelfTestItem]:
    items=[]
    def diagnostics():
        _, results = run_diagnostics()
        missing = [x.label for x in results if x.required and not x.ok]
        if missing:
            # --doctor is the authoritative dependency gate. Self-test focuses
            # on internal data paths and remains useful in headless CI.
            return "ambiente incompleto; rode --doctor: " + ", ".join(missing)
        return "dependências obrigatórias OK"
    items.append(_run("Diagnóstico básico", diagnostics))

    with tempfile.TemporaryDirectory(prefix="novel-reader-selftest-") as temp:
        root=Path(temp)
        def db_test():
            path=root/'library.sqlite3'; db=LibraryDatabase(path)
            db.record_chapter(Chapter(source='SelfTest',url='https://self.test/book/1/ch1',book_title='Self Test Book',chapter_title='Chapter 1',text='hello'),42)
            with sqlite3.connect(path) as conn: value=conn.execute('SELECT progress FROM reading_history LIMIT 1').fetchone()[0]
            if value!=42: raise RuntimeError('progresso não persistiu')
            return 'SQLite leitura/escrita OK'
        items.append(_run('SQLite roundtrip', db_test))

        def backup_test():
            path=root/'backup.sqlite3'; db=LibraryDatabase(path)
            db.record_chapter(Chapter(source='SelfTest',url='https://self.test/book/2/ch1',book_title='Backup',chapter_title='One',text='hello'),88)
            mgr=DataSafetyManager(path,backup_dir=root/'backups',retention=2); rec=mgr.backup_now()
            if rec is None or not rec.sqlite_path.exists() or not mgr.validate_backup(rec.sqlite_path).ok: raise RuntimeError('backup inválido')
            return 'backup + integrity_check OK'
        items.append(_run('Backup SQLite', backup_test))

        def cache_test():
            cache=ChapterCache(cache_dir=root/'cache/chapters'); ch=Chapter(source='SelfTest',url='https://self.test/cache/ch1',book_title='Cache',chapter_title='One',text='cached')
            cache.save(ch); loaded=cache.load(ch.url)
            if loaded is None or loaded.text!='cached': raise RuntimeError('cache não retornou capítulo')
            if CacheManager(cache.cache_root).stats().total_bytes<=0: raise RuntimeError('cache vazio')
            return 'cache leitura/escrita OK'
        items.append(_run('Cache roundtrip', cache_test))

        def cfg_test():
            store=AppConfigStore(root/'config.json'); store.update(theme='dark',prefetch_count=4,cache_limit_mb=600); loaded=store.load()
            if loaded.theme!='dark' or loaded.prefetch_count!=4: raise RuntimeError('configuração não persistiu')
            return 'configuração atômica OK'
        items.append(_run('Configuração', cfg_test))

        def lock_test():
            a=InstanceLock(root/'instance.lock'); b=InstanceLock(root/'instance.lock'); a.acquire(); b.acquire(); b.release(); a.release(); return 'lock reentrante OK'
        items.append(_run('Lock de instância', lock_test))

        def search_test():
            if not fuzzy_match('harry poter','Harry Potter Fanfiction',threshold=55): raise RuntimeError('fuzzy search falhou')
            return 'busca fuzzy OK'
        items.append(_run('Busca fuzzy', search_test))
    return items


def self_test_ok(items): return all(x.ok for x in items)

def format_self_test(items):
    width=max((len(x.name) for x in items),default=0); lines=['Novel Reader Self-Test','']
    for x in items: lines.append(f"{x.name:<{width}}  {'✓' if x.ok else '✗'}  {x.detail}")
    lines += ['', 'Resultado: OK' if self_test_ok(items) else 'Resultado: FALHOU']
    return '\n'.join(lines)
