import json
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialog
from device_battery.profile_dialog import ProfileDialog, agent_prompt
from device_battery.profiles import EXAMPLE, profile_entry
from device_battery.gui import Dashboard
from device_battery.protocol import Reading
from device_battery.settings import Settings


class ProfileEditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_form_generates_valid_code_and_prompt_updates_and_copies(self):
        dialog = ProfileDialog(device={'name': '小順 84 鍵', 'vid': '05AC', 'pid': '024F', 'port': '3-2'})
        dialog.fields['driver_path'].setText('/tmp/vendor/HIDUsb.dll')
        dialog.fields['notes'].setText('84 鍵、接收器模式')
        self.assertIn('/tmp/vendor/HIDUsb.dll', dialog.prompt.toPlainText())
        self.assertIn('3-2', dialog.prompt.toPlainText())
        dialog.copy_prompt()
        self.assertEqual(self.app.clipboard().text(), dialog.prompt.toPlainText())
        dialog.protocol.setCurrentIndex(dialog.protocol.findData('lofree'))
        self.assertTrue(dialog.generate_code())
        self.assertEqual(json.loads(dialog.code.toPlainText())['name'], '小順 84 鍵')
        dialog.accept()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(dialog.entry['analysis']['driver_path'], '/tmp/vendor/HIDUsb.dll')
        dialog.deleteLater()

    def test_unknown_protocol_prompts_analysis_instead_of_generating_fake_code(self):
        dialog = ProfileDialog(device={'name': '未知鍵盤', 'vid': '1234', 'pid': '5678'})
        with patch('device_battery.profile_dialog.QMessageBox.warning') as warning:
            self.assertFalse(dialog.generate_code())
        warning.assert_called_once()
        self.assertEqual(dialog.code.toPlainText(), '')
        self.assertIn('不可把未知協定硬套', dialog.prompt.toPlainText())
        dialog.deleteLater()

    def test_edit_usb_device_replaces_in_place_and_restores_on_save_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(directory)
            settings.devices = [{'id': 'usb:3-2', 'source': 'USB', 'name': '我的 84 鍵', 'vid': '05AC', 'pid': '024F'}]
            window = Dashboard(settings, preview=True)
            def edit():
                dialog = QApplication.activeModalWidget()
                self.assertIsInstance(dialog, ProfileDialog)
                self.assertEqual(dialog.fields['vid'].text(), '05AC')
                dialog.protocol.setCurrentIndex(dialog.protocol.findData('lofree'))
                dialog.accept()
            QTimer.singleShot(0, edit)
            window.cards[3].edit_profile_button.click()
            self.assertEqual(len(settings.devices), 1)
            saved = Settings(directory).devices[0]
            self.assertEqual(saved['profile']['protocol'], 'lofree')
            self.assertEqual(len(window.cards), 4)
            self.assertIsNone(window.readings[3].percent)
            def change_again():
                dialog = QApplication.activeModalWidget()
                dialog.fields['pid'].setText('9999')
                dialog.accept()
            QTimer.singleShot(0, change_again)
            with patch.object(window, 'save_settings', return_value=False):
                window.edit_profile(3)
            self.assertEqual(settings.devices[0], saved)
            window.close()
            window.deleteLater()
            self.app.processEvents()

    def test_edit_existing_profile_prefills_latest_name_and_can_cancel(self):
        item = profile_entry(EXAMPLE)
        item['name'] = '重新命名的鍵盤'
        item['analysis'] = {'name': '舊名稱', 'driver_path': '/tmp/driver'}
        dialog = ProfileDialog(device=item)
        self.assertEqual(dialog.fields['name'].text(), '重新命名的鍵盤')
        self.assertEqual(dialog.fields['driver_path'].text(), '/tmp/driver')
        self.assertEqual(json.loads(dialog.code.toPlainText())['name'], '重新命名的鍵盤')
        dialog.reject()
        self.assertIsNone(dialog.entry)
        dialog.deleteLater()
