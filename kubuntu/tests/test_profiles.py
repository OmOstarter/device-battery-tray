import base64
import json
import tempfile
import unittest
from unittest.mock import patch
from device_battery.profiles import EXAMPLE, parse_code, profile_entry, read_profile
from device_battery.settings import Settings
from device_battery.system_devices import read_devices
from device_battery.protocol import request_compact


class ProfileTests(unittest.TestCase):
    def test_code_round_trip_and_settings_rename(self):
        code = 'DBT1:'+base64.urlsafe_b64encode(EXAMPLE.encode()).decode().rstrip('=')
        self.assertEqual(parse_code(code), parse_code(EXAMPLE))
        entry = profile_entry(code)
        entry['name'] = '我的鍵盤'
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(directory)
            settings.devices = [entry]
            settings.save()
            self.assertEqual(Settings(directory).devices, [entry])

    def test_reject_unknown_invalid_and_executable_input(self):
        for code in ['05AC:024F', '__import__("os").system("echo bad")',
                     'DBT1:??', '{}', '[]', EXAMPLE.replace('lofree', 'unknown'),
                     EXAMPLE.replace('05AC', '../bad'), EXAMPLE.replace('024F', '0000')]:
            with self.subTest(code=code), self.assertRaises(ValueError):
                parse_code(code)

    def test_reads_matching_vendor_control_only_and_closes_handle(self):
        entry = profile_entry(EXAMPLE)
        class Device:
            closed = False
            def open_path(self, path): self.path = path
            def close(self): self.closed = True
        device = Device()
        class API:
            @staticmethod
            def enumerate():
                return [{'vendor_id': 0x05AC, 'product_id': 0x024F, 'usage_page': 1, 'path': b'input'},
                        {'vendor_id': 0x05AC, 'product_id': 0x024F, 'usage_page': 0xFF02, 'path': b'control'},
                        {'vendor_id': 0x9999, 'product_id': 0x024F, 'usage_page': 0xFF02, 'path': b'other'}]
            @staticmethod
            def device(): return device
        with patch('device_battery.profiles.exchange', return_value=(68, 'raw')) as exchange:
            reading = read_profile(entry, 3, API)
        self.assertEqual((reading.slot, reading.percent, reading.present), (3, 68, True))
        self.assertEqual(device.path, b'control')
        self.assertTrue(device.closed)
        exchange.assert_called_once_with(device, 0, request_compact(True))

    def test_system_read_dispatches_saved_profile_without_power_supply(self):
        entry = profile_entry(EXAMPLE)
        with patch('device_battery.profiles.read_profile') as read, patch('device_battery.system_devices.discover') as discover:
            read_devices([entry])
        read.assert_called_once_with(entry, 3)
        discover.assert_not_called()

    def test_wrong_interface_never_sends_and_timeout_clears_percent(self):
        entry = profile_entry(EXAMPLE)
        class Device:
            def open_path(self, path): pass
            def close(self): pass
        class API:
            page = 1
            @classmethod
            def enumerate(cls):
                return [{'vendor_id': 0x05AC, 'product_id': 0x024F, 'usage_page': cls.page, 'path': b'control'}]
            @staticmethod
            def device(): return Device()
        with patch('device_battery.profiles.exchange', side_effect=TimeoutError) as exchange:
            self.assertIsNone(read_profile(entry, 3, API).percent)
            exchange.assert_not_called()
            API.page = 0xFF02
            result = read_profile(entry, 3, API)
        self.assertTrue(result.present)
        self.assertIsNone(result.percent)
        self.assertIn('未收到', result.status)
