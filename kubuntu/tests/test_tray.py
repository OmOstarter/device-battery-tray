import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch, Mock
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import QEvent, QPoint
from PySide6.QtGui import QHelpEvent
from device_battery.tray import DeviceTray, HoverTrayIcon, automatic_refresh_interval


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


    def test_tooltip_event_requests_hover_refresh(self):
        tray = HoverTrayIcon()
        callback = Mock()
        tray.hovered.connect(callback)
        QApplication.sendEvent(tray, QHelpEvent(QEvent.Type.ToolTip, QPoint(), QPoint()))
        callback.assert_called_once()

    def test_hover_action_reaches_parent_and_manual_refresh_still_works(self):
        parent = Mock()
        with patch('device_battery.tray.QProcess') as process:
            tray = DeviceTray(parent, 0, '鍵盤')
            process.return_value.readAllStandardOutput.return_value = b'hover\nrefresh\n'
            tray.receive(parent, 0)
            parent.hover_refresh.assert_called_once()
            parent.refresh.assert_called_once()
            tray.hide()

    def test_kde_uses_short_automatic_refresh_when_hover_is_unavailable(self):
        with patch.dict(os.environ, {'XDG_CURRENT_DESKTOP': 'KDE', 'KDE_FULL_SESSION': ''}):
            self.assertEqual(automatic_refresh_interval(), 5000)
        with patch.dict(os.environ, {'XDG_CURRENT_DESKTOP': 'XFCE', 'KDE_FULL_SESSION': ''}):
            self.assertEqual(automatic_refresh_interval(), 30000)
