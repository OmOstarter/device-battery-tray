import tempfile
import unittest
from unittest.mock import patch, Mock
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QInputDialog, QDialog
from device_battery.gui import Dashboard
from device_battery.protocol import Reading
from device_battery.settings import Settings


class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = Settings(self.temp.name)
        self.window = Dashboard(self.settings, preview=True)

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.temp.cleanup()

    def test_theme_toggle_saved_and_real_rename_dialog(self):
        self.window.theme_button.click()
        self.assertFalse(Settings(self.temp.name).dark)
        def fill_dialog():
            dialog = QApplication.activeModalWidget()
            self.assertIsInstance(dialog, QInputDialog)
            dialog.setTextValue("我的 Kubuntu 鍵盤")
            dialog.accept()
        QTimer.singleShot(0, fill_dialog)
        self.window.rename(0)
        self.assertEqual(self.window.cards[0].name.text(), "我的 Kubuntu 鍵盤")
        self.assertEqual(Settings(self.temp.name).names[0], "我的 Kubuntu 鍵盤")

    def test_add_device_dialog_and_persistence(self):
        def accept():
            dialog = QApplication.activeModalWidget()
            self.assertIsInstance(dialog, QDialog)
            from PySide6.QtWidgets import QListWidget
            if dialog.findChild(QListWidget).count():
                dialog.accept()
            else:
                QTimer.singleShot(10, accept)
        QTimer.singleShot(10, accept)
        with patch("device_battery.gui.discover", return_value=[{"id": "mouse", "name": "新滑鼠"}]):
            self.window.add_device()
        self.assertEqual(len(self.window.cards), 4)
        self.assertEqual(Settings(self.temp.name).devices, [{"id": "mouse", "name": "新滑鼠"}])
        self.assertEqual(self.window.cards[3].name.text(), "新滑鼠")

    def test_enter_protocol_code_and_persist(self):
        from device_battery.profiles import EXAMPLE
        def fill():
            dialog = QApplication.activeModalWidget()
            from device_battery.profile_dialog import ProfileDialog
            self.assertIsInstance(dialog, ProfileDialog)
            dialog.code.setPlainText(EXAMPLE)
            dialog.tabs.setCurrentIndex(1)
            dialog.accept()
        QTimer.singleShot(0, fill)
        self.window.enter_code()
        self.assertEqual(len(self.window.cards), 4)
        saved = Settings(self.temp.name).devices[0]
        self.assertEqual(saved["profile"]["protocol"], "lofree")
        self.assertTrue(saved["id"].startswith("profile:"))

    def add_test_devices(self):
        self.settings.devices = [{"id": "first", "name": "滑鼠"}, {"id": "second", "name": "鍵盤"}]
        self.settings.save()
        self.window.ensure_cards(5)
        readings = self.window.readings[:3] + [Reading(i, d["name"], 50+i, present=True)
                                               for i, d in enumerate(self.settings.devices, 3)]
        self.window.updated(readings)
        return readings

    def test_delete_middle_reindexes_and_old_refresh_does_not_restore_it(self):
        old_readings = self.add_test_devices().copy()
        self.assertTrue(self.window.cards[0].delete_button.isHidden())
        self.assertFalse(self.window.cards[3].delete_button.isHidden())
        self.window.cards[3].delete_button.click()
        self.assertEqual([d["id"] for d in Settings(self.temp.name).devices], ["second"])
        self.assertEqual(len(self.window.cards), 4)
        self.assertEqual(self.window.cards[3].name.text(), "鍵盤")
        self.window.updated(old_readings, ("first", "second"))
        self.assertEqual(len(self.window.readings), 4)
        self.assertEqual(self.window.readings[3].slot, 3)
        self.assertEqual(self.window.readings[3].percent, 54)
        self.window.cards[3].delete_button.click()
        self.assertEqual(Settings(self.temp.name).devices, [])
        self.assertEqual(len(self.window.cards), 3)

    def test_delete_failed_save_preserves_device_and_builtin_is_protected(self):
        self.add_test_devices()
        with patch.object(self.window, "save_settings", return_value=False):
            self.window.delete_device(3)
        self.window.delete_device(0)
        self.assertEqual(len(self.settings.devices), 2)
        self.assertEqual(len(self.window.cards), 5)

    def test_delete_closes_custom_tray_hosts(self):
        self.add_test_devices()
        self.window.delete_device(4)
        trays = [Mock() for _ in range(4)]
        self.window.trays = trays.copy()
        self.window.headings = [Mock() for _ in range(4)]
        self.window.delete_device(3)
        trays[3].close.assert_called_once()
        self.assertEqual(len(self.window.trays), 3)
        self.assertEqual(len(self.window.headings), 3)

    def test_readout_and_offline_clear(self):
        readings = [Reading(i, n, 73, "已連線", "2.4 GHz 接收器", "12:34:56", present=True) for i, n in enumerate(self.settings.names)]
        self.window.updated(readings)
        self.assertEqual(self.window.cards[0].percent.text(), "73%")
        readings[0].percent = None
        readings[0].status = "未收到電量回應"
        self.window.updated(readings)
        self.assertEqual(self.window.cards[0].percent.text(), "—")
        self.assertEqual(self.window.cards[0].progress.value(), 0)
        self.assertEqual(self.window.cards[0].connection.text(), "未收到電量回應")

    def test_unplug_hides_card_and_tray_but_sleeping_receiver_stays(self):
        class Tray:
            def setIcon(self, icon): pass
            def setToolTip(self, tip): pass
            def setVisible(self, value): self.visible = value
        class Heading:
            def setText(self, text): pass
        self.window.trays = [Tray() for _ in range(3)]
        self.window.headings = [Heading() for _ in range(3)]
        readings = [Reading(i, n) for i, n in enumerate(self.settings.names)]
        readings[1].present = True
        readings[1].status = "未收到電量回應"
        self.window.updated(readings)
        self.assertEqual([t.visible for t in self.window.trays], [False, True, False])
        self.assertFalse(self.window.cards[1].isHidden())
        readings[1].present = False
        self.window.updated(readings)
        self.assertEqual([t.visible for t in self.window.trays], [False, False, False])
        self.assertFalse(self.window.empty.isHidden())


if __name__ == "__main__":
    unittest.main()
