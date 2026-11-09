import json
from datetime import datetime
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout,
                              QLabel, QListWidget, QListWidgetItem, QPushButton)
from .usb_devices import usb_snapshot, usb_changes


class UsbMonitor(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('偵測 USB 拔插')
        self.resize(740, 450)
        self.selected = None
        self.snapshot = None
        layout = QVBoxLayout(self)
        hint = QLabel('先拔掉要辨認的鍵盤、滑鼠或 2.4 GHz 接收器，再插回。\n'
                      '下方會標出拔除／插入的設備；選取後可複製資料或加入監測。\n'
                      '同一接收器的多個 USB 介面會合併。辨認到設備不代表已支援讀取電量。')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.listing = QListWidget()
        self.listing.setObjectName('usbChanges')
        layout.addWidget(self.listing)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        row = QHBoxLayout()
        reset = QPushButton('清除紀錄並重新開始')
        reset.clicked.connect(self.reset)
        row.addWidget(reset)
        copy = QPushButton('複製所選設備資料')
        copy.clicked.connect(self.copy_selected)
        row.addWidget(copy)
        self.add = QPushButton('新增所選設備')
        self.add.clicked.connect(self.choose)
        row.addWidget(self.add)
        close = QPushButton('關閉')
        close.clicked.connect(self.reject)
        row.addWidget(close)
        layout.addLayout(row)
        self.listing.currentRowChanged.connect(self.update_selection)
        self.timer = QTimer(self)
        self.timer.setInterval(700)
        self.timer.timeout.connect(self.poll)
        self.finished.connect(self.timer.stop)
        self.poll()
        self.timer.start()

    def append(self, state, device):
        item = QListWidgetItem(f'{datetime.now():%H:%M:%S} · {state} · {device["name"]} · '
                              f'{device["vid"]}:{device["pid"]} · USB {device["port"]}')
        item.setData(Qt.ItemDataRole.UserRole, dict(device))
        self.listing.insertItem(0, item)
        self.listing.setCurrentRow(0)
        while self.listing.count() > 200:
            self.listing.takeItem(self.listing.count()-1)

    def poll(self):
        try:
            current = usb_snapshot()
        except OSError as error:
            self.snapshot = None
            self.status.setText(str(error))
            self.add.setEnabled(False)
            return False
        if self.snapshot is None:
            for device in current.values():
                self.append('目前已連接', device)
        else:
            for state, device in usb_changes(self.snapshot, current):
                self.append(state, device)
        self.snapshot = current
        self.status.setText(f'正在偵測，每 0.7 秒檢查一次。目前 {len(current)} 個 USB 設備。')
        self.update_selection()
        return True

    def current_device(self):
        item = self.listing.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def update_selection(self):
        device = self.current_device()
        current = (self.snapshot or {}).get(device['port']) if device else None
        self.add.setEnabled(bool(current and device.get('present') and
                                 (current['vid'], current['pid'], current.get('generation')) ==
                                 (device['vid'], device['pid'], device.get('generation'))))

    def copy_selected(self):
        device = self.current_device()
        if device:
            details = {k: device[k] for k in ('name', 'vid', 'pid', 'port', 'manufacturer', 'product')}
            QApplication.clipboard().setText(json.dumps(details, ensure_ascii=False, indent=2))

    def choose(self):
        selected = self.current_device()
        if not self.poll():
            return
        current = (self.snapshot or {}).get(selected['port']) if selected else None
        if (current and selected.get('present') and
                all(current.get(k) == selected.get(k) for k in ('vid', 'pid', 'generation'))):
            self.selected = current
            self.accept()

    def reset(self):
        self.snapshot = None
        self.listing.clear()
        self.poll()
