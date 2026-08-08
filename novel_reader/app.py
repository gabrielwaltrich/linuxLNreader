import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from novel_reader.app_config import AppConfigStore
from novel_reader.database import LibraryDatabase
from novel_reader.logging_setup import configure_logging, get_logger
from novel_reader.services.data_safety import DataSafetyManager
from novel_reader.services.instance_lock import InstanceLock, InstanceAlreadyRunningError
from novel_reader.ui.main_window import MainWindow


def run() -> int:
    configure_logging(debug=False)
    logger = get_logger("app")

    app = QApplication(sys.argv)
    app.setApplicationName("Novel Reader")
    app.setOrganizationName("NovelReader")

    lock = InstanceLock()
    try:
        lock.acquire()
    except InstanceAlreadyRunningError as exc:
        QMessageBox.critical(
            None,
            "Novel Reader já está aberto",
            str(exc) + "\n\nFeche a outra instância antes de continuar.",
        )
        return 4

    try:
        config = AppConfigStore().load()
        if config.automatic_backups:
            try:
                DataSafetyManager(
                    LibraryDatabase.default_path(),
                    retention=config.backup_retention,
                    min_interval_hours=config.backup_interval_hours,
                ).auto_backup_if_due()
            except Exception:
                logger.exception(
                    "Backup automático falhou; a GUI continuará abrindo"
                )

        window = MainWindow()
        window.show()
        return app.exec()
    finally:
        lock.release()
