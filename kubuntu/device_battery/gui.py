import hashlib
import os
import sys
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QLockFile
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPen, QPixmap
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (QApplication, QWidget, QLabel, QPushButton, QFrame,
    QVBoxLayout, QHBoxLayout, QProgressBar, QInputDialog, QLineEdit, QMenu,
    QSystemTrayIcon, QCheckBox, QMessageBox)
from .protocol import DEFAULT_NAMES, Reading, battery_color, poll
from .settings import Settings, autostart_path, desktop_entry


def device_icon(keyboard, percent):
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    color = QColor(battery_color(percent))
    painter.setPen(QPen(color, 4))
    if keyboard:
        painter.drawRoundedRect(4, 15, 56, 36, 4, 4)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        for row in range(2):
            for col in range(6):
                painter.drawRoundedRect(10+col*8, 23+row*9, 4, 4, 1, 1)
        painter.drawRoundedRect(19, 43, 27, 3, 1, 1)
    else:
        painter.drawRoundedRect(13, 4, 38, 56, 19, 19)
        painter.drawLine(32, 5, 32, 28)
        painter.drawLine(14, 28, 50, 28)
    painter.end()
    return QIcon(pixmap)


def label(text="", object_name=""):
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    if object_name:
        widget.setObjectName(object_name)
    return widget


class Card(QFrame):
    rename_requested = Signal(int)

    def __init__(self, slot):
        super().__init__()
        self.slot = slot
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 17)
        layout.setSpacing(12)
        top = QHBoxLayout()
        self.icon = label()
        self.icon.setFixedSize(46, 46)
        top.addWidget(self.icon)
        details = QVBoxLayout()
        self.name = label("", "deviceName")
        self.name.setWordWrap(True)
        self.connection = label("", "muted")
        self.connection.setWordWrap(True)
        details.addWidget(self.name)
        details.addWidget(self.connection)
        top.addLayout(details, 1)
        self.percent = label("—", "percent")
        self.percent.setMinimumWidth(106)
        self.percent.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        top.addWidget(self.percent)
        layout.addLayout(top)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(5)
        layout.addWidget(self.progress)
        bottom = QHBoxLayout()
        self.updated = label("等待更新", "muted")
        bottom.addWidget(self.updated)
        bottom.addStretch()
        rename = QPushButton("重新命名")
        rename.setAccessibleName(f"重新命名第 {slot+1} 個裝置")
        rename.clicked.connect(lambda: self.rename_requested.emit(slot))
        bottom.addWidget(rename)
        layout.addLayout(bottom)

    def update_reading(self, reading):
        self.name.setText(reading.name)
        self.percent.setText(f"{reading.percent}%" if reading.percent is not None else "—")
        self.percent.setStyleSheet("color:"+battery_color(reading.percent))
        description = reading.connection if reading.percent is not None else reading.status
        self.connection.setText(description)
        self.connection.setToolTip(description)
        self.progress.setValue(reading.percent or 0)
        self.progress.setStyleSheet("QProgressBar::chunk{background:"+battery_color(reading.percent)+";border-radius:2px;}")
        self.icon.setPixmap(device_icon(self.slot == 0, reading.percent).pixmap(42, 42))
        self.updated.setText("更新於 "+reading.time if reading.time else "等待更新")
        self.setAccessibleName(f"{reading.name} {self.percent.text()} {description}")


class Worker(QThread):
    completed = Signal(list)

    def __init__(self, names):
        super().__init__()
        self.names = names.copy()

    def run(self):
        try:
            readings = poll(self.names)
        except Exception as error:
            readings = [Reading(i, n, status="讀取失敗："+str(error)) for i, n in enumerate(self.names)]
        self.completed.emit(readings)


class Dashboard(QWidget):
    def __init__(self, settings, preview=False):
        super().__init__()
        self.settings = settings
        self.preview = preview
        self.worker = None
        self.trays = []
        self.headings = []
        self.has_polled = False
        self.setWindowTitle("裝置電量")
        self.setWindowIcon(device_icon(True, 100))
        self.resize(710, 740)
        self.setMinimumSize(620, 650)
        self.readings = [Reading(i, n, status="讀取中…") for i, n in enumerate(settings.names)]
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)
        header = QHBoxLayout()
        header.addWidget(label("裝置電量", "heading"), 1)
        self.theme_button = QPushButton()
        self.theme_button.clicked.connect(self.toggle_theme)
        header.addWidget(self.theme_button)
        root.addLayout(header)
        root.addWidget(label("鍵盤與滑鼠的電量，一眼掌握。", "muted"))
        self.banner = label("", "muted")
        self.banner.setWordWrap(True)
        self.banner.hide()
        root.addWidget(self.banner)
        self.cards = [Card(i) for i in range(3)]
        for card in self.cards:
            root.addWidget(card, 1)
            card.rename_requested.connect(self.rename)
        self.empty = label("正在偵測裝置…", "muted")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setWordWrap(True)
        root.addWidget(self.empty, 1)
        root.addWidget(label("每 30 秒更新 · 關閉視窗後仍在系統匣執行", "muted"))
        footer = QHBoxLayout()
        self.startup = QCheckBox("登入時自動啟動")
        self.startup.setChecked(autostart_path().exists() if not preview else False)
        self.startup.toggled.connect(self.set_startup)
        footer.addWidget(self.startup)
        footer.addStretch()
        self.refresh_button = QPushButton("立即更新")
        self.refresh_button.setObjectName("primary")
        self.refresh_button.clicked.connect(self.refresh)
        footer.addWidget(self.refresh_button)
        root.addLayout(footer)
        self.apply_theme()
        if not preview:
            for slot in range(3):
                tray = QSystemTrayIcon(device_icon(slot == 0, None), self)
                menu = QMenu(self)
                title = menu.addAction(settings.names[slot])
                title.setEnabled(False)
                self.headings.append(title)
                menu.addAction("開啟裝置總覽", self.show_dashboard)
                menu.addAction("立即更新", self.refresh)
                menu.addAction("重新命名", lambda checked=False, i=slot: self.rename(i))
                menu.addSeparator()
                menu.addAction("結束全部圖示", self.quit_app)
                tray.setContextMenu(menu)
                tray.activated.connect(self.tray_activated)
                self.trays.append(tray)
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.refresh)
            self.timer.start(30000)
            QTimer.singleShot(0, self.refresh)
            QTimer.singleShot(1500, self.check_tray)
        self.render_readings()

    def apply_theme(self):
        dark = self.settings.dark
        bg, surface, fg, muted, button, track = ("#11151e", "#1c212c", "#ebf0f9", "#929fb5", "#2c3548", "#313948") if dark else ("#f4f7fb", "#ffffff", "#1e283c", "#66768b", "#e1e9f6", "#e4eaf2")
        QApplication.instance().setStyleSheet(f"""
            QWidget {{background:{bg};color:{fg};font-size:14px;}}
            QLabel {{background:transparent;}}
            QLabel#heading {{font-size:30px;font-weight:700;}}
            QLabel#muted {{color:{muted};font-size:12px;}}
            QLabel#deviceName {{font-weight:600;font-size:15px;}}
            QLabel#percent {{font-size:32px;font-weight:700;}}
            QFrame#card {{background:{surface};border-radius:16px;}}
            QFrame#card QLabel {{background:transparent;}}
            QPushButton {{background:{button};border:0;border-radius:7px;padding:9px 15px;}}
            QPushButton:hover {{border:1px solid #7292f8;padding:8px 14px;}}
            QPushButton#primary {{background:#4c73f5;color:white;}}
            QPushButton:disabled {{color:{muted};}}
            QProgressBar {{border:0;background:{track};border-radius:2px;}}
            QLineEdit {{background:{surface};border:1px solid {muted};border-radius:5px;padding:8px;}}
            QMenu {{background:{surface};border:1px solid {track};padding:5px;}}
            QMenu::item {{padding:8px 18px;}}
            QMenu::item:selected {{background:{button};}}
            QMenu::item:disabled {{color:{muted};}}
            QCheckBox {{background:transparent;}}
        """)
        self.theme_button.setText("切換淺色模式" if dark else "切換深色模式")

    def save_settings(self):
        try:
            self.settings.save()
            return True
        except OSError as error:
            QMessageBox.warning(self, "無法儲存設定", str(error))
            return False

    def toggle_theme(self):
        self.settings.dark = not self.settings.dark
        self.save_settings()
        self.apply_theme()

    def rename(self, slot):
        dialog = QInputDialog(self)
        dialog.setWindowTitle("重新命名裝置")
        dialog.setLabelText("裝置名稱（最多 32 個字元）")
        dialog.setTextValue(self.settings.names[slot])
        dialog.setOkButtonText("儲存")
        dialog.setCancelButtonText("取消")
        field = dialog.findChild(QLineEdit)
        if field:
            field.setMaxLength(32)
        if dialog.exec():
            name = dialog.textValue().strip()
            if not name or len(name) > 32:
                QMessageBox.warning(self, "重新命名", "名稱需為 1 至 32 個字元。")
                return
            previous = self.settings.names[slot]
            self.settings.names[slot] = name
            if not self.save_settings():
                self.settings.names[slot] = previous
            self.render_readings()

    def render_readings(self):
        any_present = any(r.present for r in self.readings)
        self.empty.setVisible(not any_present)
        self.empty.setText("尚未偵測到支援的裝置\n插入鍵盤、滑鼠或接收器後，將自動顯示。" if self.has_polled else "正在偵測裝置…")
        for i, reading in enumerate(self.readings):
            reading.name = self.settings.names[i]
            self.cards[i].update_reading(reading)
            self.cards[i].setVisible(reading.present)
            if self.trays:
                self.trays[i].setIcon(device_icon(i == 0, reading.percent))
                detail = f"{reading.percent}% · {reading.connection}" if reading.percent is not None else reading.status
                self.trays[i].setToolTip(reading.name+"\n"+detail)
                self.headings[i].setText(reading.name)
                self.trays[i].setVisible(reading.present)

    def refresh(self):
        if self.preview or (self.worker and self.worker.isRunning()):
            return
        self.refresh_button.setEnabled(False)
        self.refresh_button.setText("更新中…")
        self.worker = Worker(self.settings.names)
        self.worker.completed.connect(self.updated)
        self.worker.finished.connect(self.worker_finished)
        self.worker.start()

    def worker_finished(self):
        self.refresh_button.setEnabled(True)
        self.refresh_button.setText("立即更新")

    def updated(self, readings):
        self.has_polled = True
        self.readings = readings
        self.render_readings()

    def tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.show_dashboard()

    def show_dashboard(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def check_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.banner.setText("尚未找到系統匣，請確認 KDE 系統匣已啟用。")
            self.banner.show()
            self.show_dashboard()

    def set_startup(self, enabled):
        if self.preview:
            return
        path = autostart_path()
        try:
            if enabled:
                path.parent.mkdir(parents=True, exist_ok=True)
                script = Path(__file__).resolve().parent.parent/"device-battery-tray.py"
                path.write_text(desktop_entry(sys.executable, script, hidden=True), encoding="utf-8")
            else:
                path.unlink(missing_ok=True)
        except OSError as error:
            self.startup.blockSignals(True)
            self.startup.setChecked(not enabled)
            self.startup.blockSignals(False)
            QMessageBox.warning(self, "無法設定自動啟動", str(error))

    def closeEvent(self, event):
        if self.preview:
            event.accept()
        elif QSystemTrayIcon.isSystemTrayAvailable():
            self.hide()
            event.ignore()
        else:
            self.quit_app()
            event.accept()

    def quit_app(self):
        self.stop_worker()
        for tray in self.trays:
            tray.hide()
        QApplication.instance().quit()

    def stop_worker(self):
        if self.worker:
            self.worker.wait(8000)


def run(background=False, preview_path=None):
    app = QApplication([sys.argv[0]])
    app.setApplicationName("Device Battery Tray")
    app.setQuitOnLastWindowClosed(False)
    # Windows offscreen preview has no system font discovery on some Qt builds.
    # Load only a locally installed font; no proprietary font is redistributed.
    if sys.platform == "win32":
        font = Path(os.environ.get("WINDIR", "C:/Windows"))/"Fonts/msjh.ttc"
        if font.exists():
            QFontDatabase.addApplicationFont(str(font))
    families = QFontDatabase.families()
    family = next((f for f in ("Noto Sans CJK TC", "Noto Sans TC", "Noto Sans CJK SC", "Microsoft JhengHei", "Noto Sans", "DejaVu Sans") if f in families), app.font().family())
    app.setFont(QFont(family, 10))
    settings = Settings()
    lock = server = None
    if not preview_path:
        settings.root.mkdir(parents=True, exist_ok=True)
        server_name = "device-battery-"+hashlib.sha256(str(settings.root).encode()).hexdigest()[:16]
        socket = QLocalSocket()
        socket.connectToServer(server_name)
        if socket.waitForConnected(300):
            socket.write(b"show")
            socket.waitForBytesWritten(300)
            return 0
        lock = QLockFile(str(settings.root/"instance.lock"))
        if not lock.tryLock(0):
            QMessageBox.information(None, "裝置電量", "程式正在執行，請從系統匣開啟。")
            return 0
        QLocalServer.removeServer(server_name)
        server = QLocalServer()
        if not server.listen(server_name):
            QMessageBox.warning(None, "裝置電量", server.errorString())
            return 1
    window = Dashboard(settings, preview=bool(preview_path))
    app.aboutToQuit.connect(window.stop_worker)
    if preview_path:
        window.readings = [Reading(i, n, p, "已連線" if p is not None else "未收到電量回應", "2.4 GHz 接收器", "12:34:56", present=True) for i, (n, p) in enumerate(zip(settings.names, (85, 48, None)))]
        window.render_readings()
        window.show()
        app.processEvents()
        if not window.grab().save(str(preview_path)):
            raise OSError("無法儲存介面預覽")
        return 0
    def connected():
        peer = server.nextPendingConnection()
        if peer:
            peer.close()
            peer.deleteLater()
        window.show_dashboard()
    server.newConnection.connect(connected)
    if not background:
        window.show()
    result = app.exec()
    server.close()
    lock.unlock()
    return result
