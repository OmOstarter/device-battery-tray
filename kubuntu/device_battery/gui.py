import hashlib
import os
import sys
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QLockFile
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPen, QPixmap
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (QApplication, QWidget, QLabel, QPushButton, QFrame,
    QVBoxLayout, QHBoxLayout, QProgressBar, QInputDialog, QLineEdit, QMenu,
    QSystemTrayIcon, QCheckBox, QMessageBox, QDialog, QListWidget, QDialogButtonBox, QScrollArea)
from .protocol import DEFAULT_NAMES, Reading, battery_color, poll
from .profile_dialog import ProfileDialog
from .usb_dialog import UsbMonitor
from .tray import DeviceTray
from .system_devices import discover, read_devices
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
    delete_requested = Signal(int)
    edit_profile_requested = Signal(int)

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
        self.updated = label("等待刷新", "muted")
        bottom.addWidget(self.updated)
        bottom.addStretch()
        rename = QPushButton("重新命名")
        rename.setAccessibleName(f"重新命名第 {slot+1} 個裝置")
        rename.clicked.connect(lambda: self.rename_requested.emit(slot))
        bottom.addWidget(rename)
        self.edit_profile_button = QPushButton("編輯協定代碼")
        self.edit_profile_button.setVisible(slot >= 3)
        self.edit_profile_button.clicked.connect(lambda: self.edit_profile_requested.emit(self.slot))
        bottom.addWidget(self.edit_profile_button)
        self.delete_button = QPushButton("刪除")
        self.delete_button.setAccessibleName(f"刪除第 {slot+1} 個裝置")
        self.delete_button.setVisible(slot >= 3)
        self.delete_button.clicked.connect(lambda: self.delete_requested.emit(self.slot))
        bottom.addWidget(self.delete_button)
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
        self.updated.setText("刷新於 "+reading.time if reading.time else "等待刷新")
        self.setAccessibleName(f"{reading.name} {self.percent.text()} {description}")


class Worker(QThread):
    completed = Signal(list)

    def __init__(self, names, devices=()):
        super().__init__()
        self.names = names.copy()
        self.devices = [dict(d) for d in devices]

    def run(self):
        try:
            readings = poll(self.names)
        except Exception as error:
            readings = [Reading(i, n, status="讀取失敗："+str(error)) for i, n in enumerate(self.names)]
        readings.extend(read_devices(self.devices))
        self.completed.emit(readings)


class ScanWorker(QThread):
    completed = Signal(list, list)

    def run(self):
        errors = []
        try:
            devices = discover(errors=errors)
        except Exception as error:
            devices = []
            errors.append(str(error))
        self.completed.emit(devices, errors)


class Dashboard(QWidget):
    def __init__(self, settings, preview=False):
        super().__init__()
        self.settings = settings
        self.preview = preview
        self.worker = None
        self.scanners = []
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
        self.add_button = QPushButton("新增裝置")
        self.add_button.clicked.connect(self.add_device)
        header.addWidget(self.add_button)
        self.code_button = QPushButton("輸入協定代碼")
        self.code_button.clicked.connect(self.enter_code)
        header.addWidget(self.code_button)
        root.addLayout(header)
        root.addWidget(label("鍵盤與滑鼠的電量，一眼掌握。", "muted"))
        self.banner = label("", "muted")
        self.banner.setWordWrap(True)
        self.banner.hide()
        root.addWidget(self.banner)
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        self.card_layout = QVBoxLayout(container)
        self.card_layout.setContentsMargins(0, 0, 0, 0)
        area.setWidget(container)
        root.addWidget(area, 1)
        self.cards = []
        self.ensure_cards(3 + len(settings.devices))
        self.readings.extend(Reading(i, d["name"], status="讀取中…") for i, d in enumerate(settings.devices, 3))
        self.empty = label("正在偵測裝置…", "muted")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setWordWrap(True)
        root.addWidget(self.empty, 1)
        root.addWidget(label("每 30 秒刷新 · 關閉視窗後仍在系統匣執行", "muted"))
        footer = QHBoxLayout()
        self.startup = QCheckBox("登入時自動啟動")
        self.startup.setChecked(autostart_path().exists() if not preview else False)
        self.startup.toggled.connect(self.set_startup)
        footer.addWidget(self.startup)
        footer.addStretch()
        self.refresh_button = QPushButton("立即刷新")
        self.refresh_button.setObjectName("primary")
        self.refresh_button.clicked.connect(self.refresh)
        footer.addWidget(self.refresh_button)
        root.addLayout(footer)
        self.apply_theme()
        if not preview:
            for slot in range(len(self.cards)):
                self.create_tray(slot)
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.refresh)
            self.timer.start(30000)
            QTimer.singleShot(0, self.refresh)
            QTimer.singleShot(1500, self.check_tray)
        self.render_readings()

    def ensure_cards(self, count):
        while len(self.cards) < count:
            card = Card(len(self.cards))
            card.rename_requested.connect(self.rename)
            card.delete_requested.connect(self.delete_device)
            card.edit_profile_requested.connect(self.edit_profile)
            self.card_layout.addWidget(card)
            self.cards.append(card)

    def delete_device(self, slot):
        if not 3 <= slot < 3 + len(self.settings.devices):
            return
        index = slot - 3
        removed = self.settings.devices.pop(index)
        if not self.save_settings():
            self.settings.devices.insert(index, removed)
            return
        # Rebuild custom slots so all menu and button callbacks use current indices.
        for tray in self.trays[3:]:
            tray.close()
        del self.trays[3:]
        del self.headings[3:]
        for card in self.cards[3:]:
            self.card_layout.removeWidget(card)
            card.hide()
            card.deleteLater()
        del self.cards[3:]
        if slot < len(self.readings):
            self.readings.pop(slot)
        for i, reading in enumerate(self.readings):
            reading.slot = i
        self.ensure_cards(3 + len(self.settings.devices))
        if not self.preview:
            for i in range(3, len(self.cards)):
                self.create_tray(i)
        self.render_readings()

    def create_tray(self, slot):
        name = self.settings.names[slot] if slot < 3 else self.settings.devices[slot-3]["name"]
        tray = DeviceTray(self, slot, name)
        self.headings.append(tray)
        self.trays.append(tray)

    def add_device(self):
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "新增裝置", "正在刷新，請稍後再新增裝置。")
            return
        candidates = []
        dialog = QDialog(self)
        dialog.setWindowTitle("新增裝置")
        dialog.resize(650, 420)
        layout = QVBoxLayout(dialog)
        hint = label("搜尋系統電量、藍牙與 USB／2.4 GHz HID 裝置。\n可加入尚未提供電量的設備；讀不到電量時會顯示狀態。原有三款型號會自動偵測。")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        listing = QListWidget()
        layout.addWidget(listing)
        status = label("正在搜尋裝置…", "muted")
        status.setWordWrap(True)
        layout.addWidget(status)
        rescan = QPushButton("重新掃描")
        layout.addWidget(rescan)
        usb_button = QPushButton("偵測 USB 拔插…")
        def monitor_usb():
            monitor = UsbMonitor(dialog)
            if monitor.exec() == QDialog.DialogCode.Accepted:
                dialog.reject()
                self.add_selected_device(monitor.selected)
        usb_button.clicked.connect(monitor_usb)
        layout.addWidget(usb_button)
        code_button = QPushButton("輸入協定代碼…")
        def enter_from_add():
            dialog.reject()
            self.enter_code()
        code_button.clicked.connect(enter_from_add)
        layout.addWidget(code_button)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        add = buttons.button(QDialogButtonBox.StandardButton.Ok)
        add.setText("新增")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        add.setEnabled(False)
        listing.currentRowChanged.connect(lambda row: add.setEnabled(row >= 0))

        def scanned(devices, errors):
            existing = {d["id"] for d in self.settings.devices}
            identities = {d.get("identity") for d in self.settings.devices if d.get("identity")}
            candidates.clear()
            for device in devices:
                identity = device.get("identity")
                if device["id"] in existing or (identity and identity in identities):
                    continue
                candidates.append(device)
                if identity:
                    identities.add(identity)
            listing.clear()
            for item in candidates:
                state = (f'{item["percent"]}%' if item.get("percent") is not None else
                         "未連線" if item.get("present") is False else "尚未提供電量")
                listing.addItem(f'{item["name"]} · {item.get("source", "系統電量")} · {state}'
                                + (f' · {item["detail"]}' if item.get("detail") else ""))
            if candidates:
                listing.setCurrentRow(0)
            status.setText(f"找到 {len(candidates)} 個可加入項目。" +
                           (" 部分來源無法讀取："+"；".join(errors) if errors else "") +
                           (" 請先連接或配對設備，再按重新掃描。" if not candidates else ""))
            rescan.setEnabled(True)

        def scan():
            rescan.setEnabled(False)
            add.setEnabled(False)
            status.setText("正在搜尋裝置…")
            scanner = ScanWorker(self)
            self.scanners.append(scanner)
            scanner.completed.connect(scanned)
            scanner.finished.connect(lambda: self.scanners.remove(scanner))
            scanner.finished.connect(scanner.deleteLater)
            scanner.start()

        rescan.clicked.connect(scan)
        scan()
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted or listing.currentRow() < 0:
            return
        self.add_selected_device(candidates[listing.currentRow()])

    def add_selected_device(self, selected):
        if any(d["id"] == selected["id"] for d in self.settings.devices):
            QMessageBox.information(self, "裝置已加入", "此設備已在監測清單中。")
            return
        self.settings.devices.append({k: selected[k] for k in ("id", "name", "source", "identity", "vid", "pid", "port", "manufacturer", "product", "detail") if k in selected})
        if not self.save_settings():
            self.settings.devices.pop()
            return
        self.ensure_cards(3 + len(self.settings.devices))
        if not self.preview:
            self.create_tray(len(self.cards)-1)
        self.readings = self.readings[:3] + [Reading(i, d["name"], status="讀取中…", present=True)
                                                    for i, d in enumerate(self.settings.devices, 3)]
        self.render_readings()
        self.refresh()

    def enter_code(self):
        self.open_profile_editor()

    def edit_profile(self, slot):
        if 3 <= slot < 3 + len(self.settings.devices):
            self.open_profile_editor(slot - 3)

    def open_profile_editor(self, index=None):
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "協定代碼", "正在刷新，請稍後再輸入。")
            return
        original = self.settings.devices[index] if index is not None else None
        dialog = ProfileDialog(self, original)
        while dialog.exec():
            entry = dialog.entry
            if original:
                for field in ("port", "manufacturer", "product", "detail"):
                    if field in original:
                        entry[field] = original[field]
            if any(d["id"] == entry["id"] and i != index for i, d in enumerate(self.settings.devices)):
                QMessageBox.warning(dialog, "協定已加入", "另一個項目已使用此設備協定，請修改代碼或編輯該項目。")
                continue
            if index is None:
                self.settings.devices.append(entry)
            else:
                self.settings.devices[index] = entry
            if not self.save_settings():
                if index is None:
                    self.settings.devices.pop()
                else:
                    self.settings.devices[index] = original
                return
            self.ensure_cards(3 + len(self.settings.devices))
            if index is None:
                if not self.preview:
                    self.create_tray(len(self.cards)-1)
                self.readings.append(Reading(len(self.cards)-1, entry["name"], status="等待刷新…", present=True))
            else:
                self.readings[index+3] = Reading(index+3, entry["name"], status="等待刷新…", present=True)
            self.render_readings()
            QTimer.singleShot(0, self.refresh)
            return

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

    def set_name(self, slot, name):
        if slot < 3:
            self.settings.names[slot] = name
        else:
            self.settings.devices[slot-3]["name"] = name

    def rename(self, slot):
        dialog = QInputDialog(self)
        dialog.setWindowTitle("重新命名裝置")
        dialog.setLabelText("裝置名稱（最多 32 個字元）")
        dialog.setTextValue((self.settings.names[slot] if slot < 3 else self.settings.devices[slot-3]["name"]))
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
            previous = (self.settings.names[slot] if slot < 3 else self.settings.devices[slot-3]["name"])
            self.set_name(slot, name)
            if not self.save_settings():
                self.set_name(slot, previous)
            self.render_readings()

    def render_readings(self):
        any_present = any(r.present for r in self.readings) or bool(self.settings.devices)
        self.empty.setVisible(not any_present)
        self.empty.setText("尚未偵測到支援的裝置\n插入鍵盤、滑鼠或接收器後，將自動顯示。" if self.has_polled else "正在偵測裝置…")
        for i, reading in enumerate(self.readings):
            reading.name = self.settings.names[i] if i < 3 else self.settings.devices[i-3]["name"]
            self.cards[i].update_reading(reading)
            self.cards[i].setVisible(reading.present or i >= 3)
            if self.trays:
                self.trays[i].setIcon(device_icon(i == 0, reading.percent))
                detail = f"{reading.percent}% · {reading.connection}" if reading.percent is not None else reading.status
                self.trays[i].setToolTip(reading.name+"\n"+detail)
                self.headings[i].setText(reading.name)
                self.trays[i].setVisible(reading.present)

    def refresh(self):
        if self.preview or QApplication.activeModalWidget() or (self.worker and self.worker.isRunning()):
            return
        self.refresh_button.setEnabled(False)
        self.refresh_button.setText("刷新中…")
        self.add_button.setEnabled(False)
        self.code_button.setEnabled(False)
        self.worker = Worker(self.settings.names, self.settings.devices)
        device_ids = tuple(d["id"] for d in self.settings.devices)
        self.worker.completed.connect(lambda readings: self.updated(readings, device_ids))
        self.worker.finished.connect(self.worker_finished)
        self.worker.start()

    def worker_finished(self):
        self.add_button.setEnabled(True)
        self.code_button.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.refresh_button.setText("立即刷新")

    def updated(self, readings, device_ids=None):
        if device_ids is not None:
            by_id = dict(zip(device_ids, readings[3:]))
            readings = readings[:3] + [by_id.get(d["id"], Reading(i, d["name"]))
                                       for i, d in enumerate(self.settings.devices, 3)]
            for i, reading in enumerate(readings):
                reading.slot = i
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
        for scanner in self.scanners.copy():
            scanner.wait()
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
