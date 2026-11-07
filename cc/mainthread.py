# Currycaster - podcast playout software
# Copyright (c) 2024 Adam Curry
# SPDX-License-Identifier: MIT
"""Run playback callbacks on the Qt thread that owns the widgets."""
import logging

from cc.qt_compat import QCoreApplication, QObject, QThread, Qt, pyqtSignal


class MainThreadInvoker(QObject):
    trigger = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.trigger.connect(self._run, Qt.ConnectionType.QueuedConnection)

    def _run(self, fn):
        try:
            fn()
        except Exception:
            logging.exception("main-thread callback failed")

    def call(self, fn):
        app = QCoreApplication.instance()
        if app is None or QThread.currentThread() is self.thread():
            fn()
            return
        self.trigger.emit(fn)


def make_invoker():
    if QCoreApplication.instance() is None:
        return None
    try:
        return MainThreadInvoker()
    except Exception:
        logging.exception("failed to create main-thread invoker")
        return None
