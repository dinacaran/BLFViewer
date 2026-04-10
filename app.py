from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from gui.main_window import MainWindow


APP_NAME = "BLF Viewer"
APP_VERSION = "v0.1.0"


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)

    icon_path = Path(__file__).resolve().parent / "resources" / "app_icon.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = MainWindow(app_name=APP_NAME, version=APP_VERSION)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
