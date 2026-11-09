"""A separate Qt tray host gives each device its own KDE item title."""
import base64
import json
import os
from pathlib import Path
import sys
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QProcess, QSocketNotifier
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon


class DeviceTray:
    def __init__(self, parent, slot, name):
        self.process = QProcess(parent)
        self.process.setProgram(sys.executable)
        self.process.setArguments([str(Path(__file__).resolve()), name])
        self.closed = False
        self.buffer = b""
        self.process.readyReadStandardOutput.connect(lambda: self.receive(parent, slot))
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.ForwardedErrorChannel)
        self.process.start()
        QApplication.instance().aboutToQuit.connect(self.hide)

    def receive(self, parent, slot):
        self.buffer += bytes(self.process.readAllStandardOutput())
        if self.closed:
            self.buffer = b""
            return
        actions = {"open": parent.show_dashboard, "refresh": parent.refresh,
                   "add": parent.add_device, "rename": lambda: parent.rename(slot),
                   "quit": parent.quit_app}
        while b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            action = actions.get(line.decode("utf-8"))
            if action:
                action()

    def send(self, **data):
        self.process.write((json.dumps(data, ensure_ascii=False)+"\n").encode("utf-8"))

    def setIcon(self, icon):
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        icon.pixmap(64, 64).save(buffer, "PNG")
        self.send(icon=base64.b64encode(bytes(data)).decode("ascii"))

    def setToolTip(self, tip):
        self.send(tooltip=tip)

    def setText(self, name):
        self.send(name=name)

    def setVisible(self, visible):
        self.send(visible=visible)

    def close(self):
        self.closed = True
        QApplication.instance().aboutToQuit.disconnect(self.hide)
        self.hide()
        self.process.deleteLater()

    def hide(self):
        self.process.closeWriteChannel()
        if not self.process.waitForFinished(1000):
            self.process.terminate()
            self.process.waitForFinished(1000)


def main():
    app = QApplication([sys.argv[0]])
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName(sys.argv[1])
    tray = QSystemTrayIcon()
    menu = QMenu()
    title = menu.addAction(sys.argv[1])
    title.setEnabled(False)
    for text, action in [("開啟裝置總覽", "open"), ("新增裝置", "add"),
                         ("立即刷新", "refresh"), ("重新命名", "rename"),
                         ("結束全部圖示", "quit")]:
        menu.addAction(text, lambda checked=False, value=action: print(value, flush=True))
    tray.setContextMenu(menu)
    tray.activated.connect(lambda reason: print("open", flush=True) if reason in (
        QSystemTrayIcon.ActivationReason.Trigger,
        QSystemTrayIcon.ActivationReason.DoubleClick) else None)
    pending = b""

    def receive():
        nonlocal pending
        chunk = os.read(0, 65536)
        if not chunk:
            notifier.setEnabled(False)
            tray.hide()
            app.quit()
            return
        pending += chunk
        while b"\n" in pending:
            line, pending = pending.split(b"\n", 1)
            data = json.loads(line)
            if "name" in data and data["name"] != app.applicationName():
                visible = tray.isVisible()
                tray.hide()
                app.setApplicationName(data["name"])
                title.setText(data["name"])
                tray.setVisible(visible)
            if "icon" in data:
                pixmap = QPixmap()
                pixmap.loadFromData(base64.b64decode(data["icon"]), "PNG")
                tray.setIcon(QIcon(pixmap))
            if "tooltip" in data:
                tray.setToolTip(data["tooltip"])
            if "visible" in data:
                tray.setVisible(data["visible"])

    notifier = QSocketNotifier(0, QSocketNotifier.Type.Read)
    notifier.activated.connect(receive)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
