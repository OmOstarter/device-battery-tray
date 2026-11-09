import json
import tempfile
import unittest
import subprocess
from unittest.mock import patch
from pathlib import Path
from device_battery.settings import Settings
from device_battery.system_devices import discover, read_devices, service_devices, hid_devices, bus_call


class SystemDeviceTests(unittest.TestCase):
    def test_discovery_read_failure_unplug_and_reconnect(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            battery = root / 'hid-battery'
            battery.mkdir()
            (battery / 'type').write_text('Battery')
            (battery / 'capacity').write_text('73')
            (battery / 'model_name').write_text('我的滑鼠')
            devices = discover(root)
            self.assertEqual(devices, [{'id': 'hid-battery', 'name': '我的滑鼠'}])
            reading = read_devices(devices, root=root)[0]
            self.assertEqual((reading.slot, reading.percent, reading.present), (3, 73, True))
            (battery / 'capacity').write_text('255')
            reading = read_devices(devices, root=root)[0]
            self.assertTrue(reading.present)
            self.assertIsNone(reading.percent)
            for path in battery.iterdir():
                path.unlink()
            battery.rmdir()
            self.assertFalse(read_devices(devices, root=root)[0].present)
            battery.mkdir()
            (battery / 'capacity').write_text('42')
            self.assertEqual(read_devices(devices, root=root)[0].percent, 42)

    def test_settings_persist_and_reject_invalid_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(directory)
            settings.devices = [{'id': 'mouse', 'name': '滑鼠'}]
            settings.save()
            self.assertEqual(Settings(directory).devices, settings.devices)
            settings.path.write_text(json.dumps({'devices': [
                {'id': '../outside', 'name': 'bad'},
                {'id': 'mouse', 'name': '滑鼠'},
                {'id': 'mouse', 'name': '重複'},
                {'id': 'other', 'name': ''}]}))
            self.assertEqual(Settings(directory).devices, [{'id': 'mouse', 'name': '滑鼠'}])


class GeneralDiscoveryTests(unittest.TestCase):
    def test_bluez_connected_percentage_and_disconnected_no_stale_value(self):
        def call(service, *args):
            if service == "org.freedesktop.UPower":
                return []
            return {"/org/bluez/hci0/dev_AA": {
                "org.bluez.Device1": {"Alias": {"type": "s", "data": "藍牙滑鼠"},
                                      "Connected": {"type": "b", "data": self.connected}},
                "org.bluez.Battery1": {"Percentage": {"type": "y", "data": 63}}}}
        with patch('device_battery.system_devices.bus_call', side_effect=call):
            self.connected = True
            device = service_devices([])[0]
            self.assertEqual(device['percent'], 63)
            self.connected = False
            device = service_devices([])[0]
            self.assertIsNone(device['percent'])
            self.assertFalse(device['present'])

    def test_upower_user_space_device_and_failure_fallback(self):
        def call(service, path, *args):
            if service == 'org.bluez':
                raise FileNotFoundError('no bluetooth')
            if path == '/org/freedesktop/UPower':
                return ['/org/freedesktop/UPower/devices/headset']
            return {'Type': {'type': 'u', 'data': 17},
                    'Model': {'type': 's', 'data': '耳機'},
                    'Percentage': {'type': 'd', 'data': 72.4},
                    'IsPresent': {'type': 'b', 'data': True}}
        errors = []
        with patch('device_battery.system_devices.bus_call', side_effect=call):
            devices = service_devices(errors)
        self.assertEqual(devices[0]['percent'], 72)
        self.assertEqual(devices[0]['source'], 'UPower')
        self.assertTrue(errors)

    def test_unknown_hid_visible_without_battery_protocol(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dev = root / '0003:1234:5678.0001'
            dev.mkdir()
            (dev / 'uevent').write_text('HID_ID=0003:00001234:00005678\nHID_NAME=Unknown Mouse\nHID_UNIQ=serial1\n')
            devices = hid_devices(root)
            self.assertEqual(len(devices), 1)
            self.assertIsNone(devices[0]['percent'])
            saved = {'id': devices[0]['id'], 'name': '我的滑鼠', 'source': 'HID'}
            with patch('device_battery.system_devices.discover', return_value=devices):
                reading = read_devices([saved])[0]
            self.assertTrue(reading.present)
            self.assertIsNone(reading.percent)
            self.assertIn('專用協定', reading.status)
            with patch('device_battery.system_devices.discover', return_value=[]):
                self.assertFalse(read_devices([saved])[0].present)

    def test_missing_busctl_still_discovers_hid(self):
        with patch('device_battery.system_devices.bus_call', side_effect=FileNotFoundError), patch(
                'device_battery.system_devices.discover_power', return_value=[]), patch(
                'device_battery.system_devices.hid_devices', return_value=[{'id': 'hid:test', 'name': 'mouse'}]):
            errors = []
            self.assertEqual(discover(errors=errors)[0]['name'], 'mouse')
            self.assertEqual(len(errors), 2)
