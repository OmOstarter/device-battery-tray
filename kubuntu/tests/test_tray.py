import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication, QWidget
from device_battery.tray import DeviceTray


class TrayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_each_device_starts_with_its_own_title_and_rename_is_sent(self):
        parent = QWidget()
        with patch('device_battery.tray.QProcess') as process:
            tray = DeviceTray(parent, 0, '我的鍵盤')
            self.assertEqual(process.return_value.setArguments.call_args.args[0][1], '我的鍵盤')
            tray.setText('新名稱')
            self.assertIn('新名稱', process.return_value.write.call_args.args[0].decode())
            tray.hide()

    def test_host_accepts_rename_and_exits_on_parent_eof(self):
        script = Path(__file__).resolve().parents[1] / 'device_battery' / 'tray.py'
        result = subprocess.run([sys.executable, str(script), '我的鍵盤'],
                                input='{"name":"新名稱"}\n{"tooltip":"電量 50%"}\n{"visible":false}\n',
                                text=True, capture_output=True, timeout=10,
                                env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('Traceback', result.stderr)
