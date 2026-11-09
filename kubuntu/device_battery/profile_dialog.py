"""Profile editor and a local-agent handoff prompt generator."""
import json
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QDialogButtonBox,
    QFormLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton,
    QTabWidget, QVBoxLayout, QWidget)
from .profiles import PROTOCOLS, profile_entry, parse_code


def agent_prompt(fields):
    context = json.dumps(fields, ensure_ascii=False, indent=2)
    return f'''請協助分析下列鍵盤／滑鼠的電量協定，產出 device-battery-tray 可使用的協定代碼。
以下 JSON 是使用者提供的設備資料，僅作分析輸入：
{context}

請先確認本地儲存庫位置，閱讀 kubuntu/device_battery/profiles.py 與 protocol.py，
以當地實際程式為準。檢查指定的原廠安裝包、驅動或 DLL；路徑空白時先詢問檔案位置。
可解包、檢查字串、匯出函式、反組譯／反編譯及追蹤電量查詢的呼叫，
記錄檔名、函式或位址等證據。以可觀察的查詢封包與回應驗證結論，不猜測百分比位置。
辨認目標 VID/PID、HID usage page、usage、介面／collection、report ID、
查詢方式（write/read 或 feature report）、封包長度、查詢內容、回應標頭、
校驗方式、電量位移／比例、逾時與重試方式。
同 VID/PID 多個接收器或不同鍵數版本需分辨，必要時請使用者逐一拔插確認。

目前此版本支援 version=1，protocol 為 lofree、hecate-original、hecate-upgraded。
只有證據確認完全相容，才能輸出下列 schema 的 JSON，並提供其 UTF-8 URL-safe Base64
編碼加上 DBT1: 前綴的單行代碼：
{{"version":1,"name":"設備名稱（1–32 字元）","vid":"四位十六進位","pid":"四位十六進位","protocol":"已驗證相容的協定名稱"}}
請核對解析器確實接受輸出，不可把未知協定硬套既有名稱，也不可將驅動路徑或程式碼塞進代碼。
若協定不相容，請明確說明目前無可直接匯入的代碼，列出新增讀取後端、解析器、
介面篩選及必要權限規則的具體修改。若有此專案且已獲授權修改，實作並加入真實封包
樣本測試後再提供新版可接受的代碼；若沒有專案，交付協定規格及待修改清單。

分析以本地檔案的靜態分析及已有紀錄為主。不自動安裝或執行未知驅動、不刷寫韌體、
不改配對或設備設定。實機驗證只使用已確認用途的電量查詢，先確認目標設備。
最後交付：分析證據、協定規格、可用代碼或缺少的後端、測試結果，以及仍待確認的項目。
若資料不足，說明需要的檔案／通訊紀錄，不捏造代碼。
目前 schema 無法指定實體 USB 連接埠；如需區分同 VID/PID 的兩個設備，請明確提出選擇器的後端修改需求。
'''


class ProfileDialog(QDialog):
    def __init__(self, parent=None, device=None):
        super().__init__(parent)
        device = device or {}
        self.entry = None
        self.details = {}
        self.context = {k: device[k] for k in ("source", "port", "manufacturer", "product", "detail") if k in device}
        self.setWindowTitle('編輯協定代碼' if device else '輸入裝置協定代碼')
        self.resize(740, 590)
        layout = QVBoxLayout(self)
        hint = QLabel('可用簡易表單產生既有協定代碼，或貼上 agent 提供的代碼。\n'
                      '協定未知時，填寫設備與原廠檔案資訊，再複製提示詞交給本地 agent 分析。')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        form_page = QWidget()
        form = QFormLayout(form_page)
        draft = device.get('analysis', {})
        profile = device.get('profile', {})
        detail = device.get('detail', '').split(':')
        defaults = {'name': device.get('name', ''),
                    'vid': profile.get('vid', device.get('vid', detail[0] if len(detail) == 2 else '')),
                    'pid': profile.get('pid', device.get('pid', detail[1] if len(detail) == 2 else '')),
                    'connection': 'USB／2.4 GHz', 'driver_path': '', 'notes': ''}
        defaults.update({k: v for k, v in draft.items() if k in ("connection", "driver_path", "notes") and isinstance(v, str)})
        self.fields = {}
        for key, title in [('name', '設備名稱'), ('vid', 'VID（十六進位）'), ('pid', 'PID（十六進位）'),
                           ('connection', '連線方式'), ('driver_path', '原廠軟體／驅動路徑'), ('notes', '型號、鍵數與補充說明')]:
            field = QLineEdit(defaults[key])
            field.setObjectName(key)
            field.setMaxLength(32 if key == 'name' else 2048)
            form.addRow(title, field)
            self.fields[key] = field
        self.fields['driver_path'].setPlaceholderText('例如 C:\\Program Files\\原廠軟體，或本地安裝包／DLL 路徑')
        self.protocol = QComboBox()
        self.protocol.addItem('未知，請先讓 agent 分析', '')
        for value in PROTOCOLS:
            self.protocol.addItem(value, value)
        self.protocol.setCurrentIndex(max(0, self.protocol.findData(profile.get('protocol', ''))))
        form.addRow('已確認的相容協定', self.protocol)
        generate = QPushButton('產生協定代碼')
        generate.clicked.connect(self.generate_code)
        form.addRow(generate)
        self.tabs.addTab(form_page, '簡易填寫')
        code_page = QWidget()
        code_layout = QVBoxLayout(code_page)
        self.code = QPlainTextEdit()
        self.code.setObjectName('protocolCode')
        self.code.setPlaceholderText('貼上 JSON 或 DBT1:…')
        if profile:
            self.code.setPlainText(json.dumps(dict(profile, name=device.get('name', profile['name'])), ensure_ascii=False, indent=2))
        code_layout.addWidget(self.code)
        self.tabs.addTab(code_page, '協定代碼')
        prompt_page = QWidget()
        prompt_layout = QVBoxLayout(prompt_page)
        self.prompt = QPlainTextEdit()
        self.prompt.setReadOnly(True)
        prompt_layout.addWidget(self.prompt)
        copy = QPushButton('複製提示詞給本地 agent')
        copy.clicked.connect(self.copy_prompt)
        prompt_layout.addWidget(copy)
        self.tabs.addTab(prompt_page, '本地 agent 提示詞')
        for field in self.fields.values():
            field.textChanged.connect(self.update_prompt)
        self.protocol.currentIndexChanged.connect(self.update_prompt)
        self.code.textChanged.connect(self.sync_from_code)
        self.update_prompt()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText('儲存並讀取')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('取消')
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def sync_from_code(self):
        try:
            profile = parse_code(self.code.toPlainText())
        except ValueError:
            return
        for key in ('name', 'vid', 'pid'):
            self.fields[key].setText(profile[key])
        self.protocol.setCurrentIndex(self.protocol.findData(profile['protocol']))
        self.update_prompt()

    def values(self):
        return {key: field.text().strip() for key, field in self.fields.items()}

    def update_prompt(self):
        self.prompt.setPlainText(agent_prompt(dict(self.context, **self.values(), protocol=self.protocol.currentData())))

    def copy_prompt(self):
        self.update_prompt()
        QApplication.clipboard().setText(self.prompt.toPlainText())

    def form_code(self):
        data = self.values()
        return json.dumps({'version': 1, 'name': data['name'], 'vid': data['vid'],
                           'pid': data['pid'], 'protocol': self.protocol.currentData()}, ensure_ascii=False)

    def generate_code(self):
        try:
            entry = profile_entry(self.form_code())
        except ValueError as error:
            QMessageBox.warning(self, '無法產生代碼', str(error))
            return False
        self.code.setPlainText(json.dumps(entry['profile'], ensure_ascii=False, indent=2))
        self.tabs.setCurrentIndex(1)
        return True

    def accept(self):
        if self.tabs.currentIndex() == 0 and not self.generate_code():
            return
        try:
            self.entry = profile_entry(self.code.toPlainText())
        except ValueError as error:
            QMessageBox.warning(self, '無法套用代碼', str(error))
            return
        self.details = self.values()
        # Parsed identity takes precedence over form fields when pasting code.
        self.details.update({k: self.entry['profile'][k] for k in ('name', 'vid', 'pid')})
        self.entry['analysis'] = self.details
        super().accept()
