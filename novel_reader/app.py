import sys

from PySide6.QtWidgets import QApplication

from novel_reader.ui.main_window import MainWindow


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Novel Reader")
    app.setOrganizationName("NovelReader")

    window = MainWindow()
    window.show()

    return app.exec()
