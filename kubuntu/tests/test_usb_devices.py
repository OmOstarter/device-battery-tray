import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from device_battery.usb_devices import usb_snapshot, usb_changes
from device_battery.usb_dialog import UsbMonitor
from device_battery.system_devices import read_devices


def sample(pid='024F', generation='1:5'):
    return {'id': 'usb:1-2', 'name': '84 鍵鍵盤', 'vid': '05AC', 'pid': pid,
            'generation': generation, 'port': '1-2', 'manufacturer': 'LOFREE',
            'product': '84 鍵鍵盤', 'source': 'USB', 'present': True, 'percent': None}


class UsbTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_sysfs_ignores_composite_interfaces_and_missing_nodes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('1-2', '1-2:1.0', '1-2:1.1'):
                device = root / name
                device.mkdir()
                (device/'idVendor').write_text('05ac')
                (device/'idProduct').write_text('024f')
                (device/'product').write_text('84 鍵鍵盤')
            (root/'removed').mkdir()
            devices = usb_snapshot(root)
            self.assertEqual(list(devices), ['1-2'])
            self.assertEqual(devices['1-2']['vid'], '05AC')
            self.assertEqual(devices['1-2']['name'], '84 鍵鍵盤')

    def test_unplug_replug_same_port_and_identical_receivers(self):
        before = {'1-2': sample()}
        self.assertEqual(usb_changes(before, before), [])
        removed = usb_changes(before, {})
        self.assertEqual(removed[0][0], '拔除')
        self.assertFalse(removed[0][1]['present'])
        after = {'1-2': sample(generation='1:6')}
        self.assertEqual([state for state, _ in usb_changes(before, after)], ['拔除', '插入'])
        after['1-3'] = dict(sample(), id='usb:1-3', port='1-3')
        self.assertEqual(len(usb_changes(before, after)), 3)

    def test_monitor_tracks_removal_replug_copy_and_choose(self):
        with patch('device_battery.usb_dialog.usb_snapshot', return_value={'1-2': sample()}) as snapshot:
            dialog = UsbMonitor()
            self.assertTrue(dialog.add.isEnabled())
            snapshot.return_value = {}
            dialog.poll()
            self.assertIn('拔除', dialog.listing.item(0).text())
            self.assertFalse(dialog.add.isEnabled())
            dialog.copy_selected()
            self.assertEqual(json.loads(self.app.clipboard().text())['vid'], '05AC')
            snapshot.return_value = {'1-2': sample(generation='1:6')}
            dialog.poll()
            self.assertIn('插入', dialog.listing.item(0).text())
            self.assertTrue(dialog.add.isEnabled())
            dialog.choose()
            self.assertEqual(dialog.selected['id'], 'usb:1-2')
            self.assertFalse(dialog.timer.isActive())
            dialog.deleteLater()

    def test_usb_added_reading_and_unplug_never_fabricates_battery(self):
        entry = {'id': 'usb:1-2', 'name': '我的 84 鍵鍵盤', 'source': 'USB'}
        with patch('device_battery.usb_devices.usb_snapshot', return_value={'1-2': sample()}), patch(
                'device_battery.system_devices.discover') as discover:
            reading = read_devices([entry])[0]
        self.assertTrue(reading.present)
        self.assertIsNone(reading.percent)
        discover.assert_not_called()
        with patch('device_battery.usb_devices.usb_snapshot', return_value={}):
            self.assertFalse(read_devices([entry])[0].present)

    def test_unavailable_sysfs_shows_error(self):
        with patch('device_battery.usb_dialog.usb_snapshot', side_effect=OSError('USB 權限不足')):
            dialog = UsbMonitor()
            self.assertIn('權限不足', dialog.status.text())
            self.assertFalse(dialog.add.isEnabled())
            dialog.reject()
            dialog.deleteLater()
