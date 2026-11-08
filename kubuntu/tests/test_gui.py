import tempfile
import unittest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QInputDialog
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
