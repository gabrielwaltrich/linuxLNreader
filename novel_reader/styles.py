LIGHT_STYLE = """
* {
    font-family: "Inter", "Noto Sans", "DejaVu Sans", sans-serif;
    font-size: 13px;
}
QMainWindow, QWidget#appRoot {
    background: #f4f6f8;
    color: #1d2530;
}
QFrame#topHeader, QFrame#urlCard, QFrame#readerToolbar, QFrame#libraryDetails {
    background: #ffffff;
    border: 1px solid #e2e7ed;
    border-radius: 14px;
}
QLabel#brandTitle {
    color: #17202a;
    font-size: 22px;
    font-weight: 800;
}
QLabel#brandSubtitle, QLabel#mutedLabel {
    color: #74808d;
}
QLabel#sectionTitle {
    color: #17202a;
    font-size: 18px;
    font-weight: 750;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    min-height: 34px;
    background: #f9fafb;
    color: #1d2530;
    border: 1px solid #dce2e8;
    border-radius: 9px;
    padding: 4px 10px;
    selection-background-color: #4f7cff;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #4f7cff;
    background: #ffffff;
}
QPushButton {
    min-height: 34px;
    background: #eef2f6;
    color: #26313e;
    border: 1px solid #dce2e8;
    border-radius: 9px;
    padding: 4px 12px;
    font-weight: 600;
}
QPushButton:hover {
    background: #e5ebf2;
    border-color: #cdd6e0;
}
QPushButton:pressed {
    background: #dbe3ec;
}
QPushButton:disabled {
    color: #a6afb9;
    background: #f4f6f8;
    border-color: #e8ebef;
}
QPushButton#primaryButton {
    background: #4f7cff;
    color: white;
    border: 1px solid #4f7cff;
}
QPushButton#primaryButton:hover {
    background: #416eea;
}
QPushButton#accentButton {
    background: #eef4ff;
    color: #315ed6;
    border: 1px solid #cfdcff;
}
QPushButton#dangerButton {
    background: #fff2f2;
    color: #b52d2d;
    border: 1px solid #ffd5d5;
}
QPushButton#iconButton {
    min-width: 36px;
    max-width: 42px;
    padding-left: 8px;
    padding-right: 8px;
}
QTextBrowser#readerSurface {
    background: #ffffff;
    color: #252d36;
    border: 1px solid #e2e7ed;
    border-radius: 16px;
    padding: 0px;
    selection-background-color: #cdd9ff;
}
QTextBrowser#readerSurface QScrollBar:vertical, QTreeWidget QScrollBar:vertical {
    width: 10px;
    background: transparent;
    margin: 6px 2px 6px 2px;
}
QTextBrowser#readerSurface QScrollBar::handle:vertical, QTreeWidget QScrollBar::handle:vertical {
    min-height: 36px;
    background: #cfd7e1;
    border-radius: 5px;
}
QTextBrowser#readerSurface QScrollBar::add-line:vertical,
QTextBrowser#readerSurface QScrollBar::sub-line:vertical,
QTreeWidget QScrollBar::add-line:vertical,
QTreeWidget QScrollBar::sub-line:vertical {
    height: 0px;
}
QDockWidget {
    color: #27313b;
    font-weight: 700;
}
QDockWidget::title {
    background: #eef2f6;
    border-bottom: 1px solid #dde3e9;
    padding: 10px 12px;
}
QTreeWidget {
    background: #ffffff;
    color: #26313e;
    border: 1px solid #e0e5eb;
    border-radius: 10px;
    outline: none;
    padding: 4px;
}
QTreeWidget::item {
    border-radius: 7px;
    padding: 7px 6px;
}
QTreeWidget::item:hover {
    background: #f2f5fa;
}
QTreeWidget::item:selected {
    background: #e6edff;
    color: #244db7;
}
QPlainTextEdit {
    background: #111820;
    color: #d9e2ec;
    border: 1px solid #293442;
    border-radius: 10px;
    padding: 8px;
}
QTextBrowser#librarySynopsis {
    background: #f8fafc;
    border: 1px solid #e3e8ee;
    border-radius: 9px;
    padding: 6px;
}
QProgressBar {
    height: 8px;
    background: #e8edf3;
    border: none;
    border-radius: 4px;
    text-align: center;
}
QProgressBar::chunk {
    background: #4f7cff;
    border-radius: 4px;
}
QStatusBar {
    background: #eef2f6;
    color: #6e7a86;
    border-top: 1px solid #e0e5ea;
}
QToolTip {
    background: #202833;
    color: white;
    border: none;
    padding: 5px 7px;
}
QDialog {
    background: #f4f6f8;
}
QCheckBox {
    spacing: 8px;
}
"""

DARK_STYLE = """
* {
    font-family: "Inter", "Noto Sans", "DejaVu Sans", sans-serif;
    font-size: 13px;
}
QMainWindow, QWidget#appRoot {
    background: #0f141a;
    color: #e8edf3;
}
QFrame#topHeader, QFrame#urlCard, QFrame#readerToolbar, QFrame#libraryDetails {
    background: #171d24;
    border: 1px solid #28313b;
    border-radius: 14px;
}
QLabel#brandTitle {
    color: #f4f7fb;
    font-size: 22px;
    font-weight: 800;
}
QLabel#brandSubtitle, QLabel#mutedLabel {
    color: #8f9ba8;
}
QLabel#sectionTitle {
    color: #f4f7fb;
    font-size: 18px;
    font-weight: 750;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    min-height: 34px;
    background: #11171d;
    color: #edf2f7;
    border: 1px solid #303b47;
    border-radius: 9px;
    padding: 4px 10px;
    selection-background-color: #567dff;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #6388ff;
    background: #151c23;
}
QPushButton {
    min-height: 34px;
    background: #222a33;
    color: #e9eef4;
    border: 1px solid #333e49;
    border-radius: 9px;
    padding: 4px 12px;
    font-weight: 600;
}
QPushButton:hover {
    background: #2b3540;
    border-color: #43505d;
}
QPushButton:pressed {
    background: #303b47;
}
QPushButton:disabled {
    color: #65717d;
    background: #171d23;
    border-color: #252d35;
}
QPushButton#primaryButton {
    background: #5b7fff;
    color: white;
    border: 1px solid #5b7fff;
}
QPushButton#primaryButton:hover {
    background: #6a8aff;
}
QPushButton#accentButton {
    background: #1b2a4b;
    color: #9db6ff;
    border: 1px solid #30497e;
}
QPushButton#dangerButton {
    background: #3a2023;
    color: #ffb5b9;
    border: 1px solid #633036;
}
QPushButton#iconButton {
    min-width: 36px;
    max-width: 42px;
    padding-left: 8px;
    padding-right: 8px;
}
QTextBrowser#readerSurface {
    background: #171d24;
    color: #dfe5ec;
    border: 1px solid #29323c;
    border-radius: 16px;
    padding: 0px;
    selection-background-color: #3d5388;
}
QTextBrowser#readerSurface QScrollBar:vertical, QTreeWidget QScrollBar:vertical {
    width: 10px;
    background: transparent;
    margin: 6px 2px 6px 2px;
}
QTextBrowser#readerSurface QScrollBar::handle:vertical, QTreeWidget QScrollBar::handle:vertical {
    min-height: 36px;
    background: #3b4754;
    border-radius: 5px;
}
QTextBrowser#readerSurface QScrollBar::add-line:vertical,
QTextBrowser#readerSurface QScrollBar::sub-line:vertical,
QTreeWidget QScrollBar::add-line:vertical,
QTreeWidget QScrollBar::sub-line:vertical {
    height: 0px;
}
QDockWidget {
    color: #e6ebf1;
    font-weight: 700;
}
QDockWidget::title {
    background: #161c23;
    border-bottom: 1px solid #28313a;
    padding: 10px 12px;
}
QTreeWidget {
    background: #151b22;
    color: #e0e6ec;
    border: 1px solid #29333d;
    border-radius: 10px;
    outline: none;
    padding: 4px;
}
QTreeWidget::item {
    border-radius: 7px;
    padding: 7px 6px;
}
QTreeWidget::item:hover {
    background: #202832;
}
QTreeWidget::item:selected {
    background: #26375d;
    color: #dce6ff;
}
QPlainTextEdit {
    background: #0a0e12;
    color: #cfd8e3;
    border: 1px solid #2c3742;
    border-radius: 10px;
    padding: 8px;
}
QTextBrowser#librarySynopsis {
    background: #11171d;
    border: 1px solid #29333e;
    border-radius: 9px;
    padding: 6px;
}
QStatusBar {
    background: #141a20;
    color: #87939f;
    border-top: 1px solid #252e37;
}
QToolTip {
    background: #edf2f7;
    color: #1d2530;
    border: none;
    padding: 5px 7px;
}
QDialog {
    background: #10161c;
}
QCheckBox {
    spacing: 8px;
}
"""
