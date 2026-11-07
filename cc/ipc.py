# Currycaster - podcast playout software
# Copyright (c) 2024 Adam Curry
# SPDX-License-Identifier: MIT
"""Local TCP loader. Send a file path to 127.0.0.1:9876."""
import logging
import socket
import threading

from cc.qt_compat import QObject, pyqtSignal


class IpcServer(QObject):
    file_received = pyqtSignal(str)

    def __init__(self, load_func, host="127.0.0.1", port=9876):
        super().__init__()
        self.file_received.connect(load_func)
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False

    def start(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.port = self.server_socket.getsockname()[1]
        self.server_socket.listen(5)
        self.server_socket.settimeout(0.5)
        self.running = True
        thread = threading.Thread(target=self._accept_loop, name="currycaster-ipc", daemon=True)
        thread.start()
        logging.info("IPC Server listening on %s:%s", self.host, self.port)

    def _accept_loop(self):
        while self.running:
            try:
                client_socket, _addr = self.server_socket.accept()
                try:
                    data = client_socket.recv(4096).decode("utf-8").strip()
                    if data:
                        logging.info("IPC received: %s", data)
                        self.file_received.emit(data)
                finally:
                    client_socket.close()
            except socket.timeout:
                continue
            except Exception as exc:
                if not self.running:
                    break
                logging.error("IPC accept error: %s", exc)

    def stop(self):
        self.running = False
        if self.server_socket is not None:
            try:
                self.server_socket.close()
            except OSError:
                pass
            self.server_socket = None
