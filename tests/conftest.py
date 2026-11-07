import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="session")
def qapp():
    from cc.qt_compat import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app
