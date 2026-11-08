import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from device_battery.protocol import (request_compact, request_original, parse_response,
    identify, connection, battery_color, poll, exchange, load_hid_api,
    list_devices, path_access_error)
from device_battery.settings import Settings, desktop_entry


def compact_reply(percent):
    packet = bytearray(request_compact())
    packet[6] = percent
    packet[16] = (0x55 - sum(packet[:16])) & 255
    return bytes(packet)


def info(vid=0x05AC, pid=0x024F, page=0xFF02, path=b"/dev/hidraw5", product="2.4G Wireless Receiver"):
    return dict(vendor_id=vid, product_id=pid, usage_page=page, path=path, product_string=product)


class FakeDevice:
    def __init__(self, reply):
        self.reply = reply
        self.sent = False
        self.closed = False

    def open_path(self, path):
        pass

    def write(self, packet):
        self.sent = True
        return len(packet)

    def read(self, size, timeout):
        if self.sent:
            self.sent = False
            return list(self.reply)
        return []

    def close(self):
        self.closed = True


class ProtocolTests(unittest.TestCase):
    def test_linux_prefers_hidraw_over_libusb(self):
        raw_api = object()
        with patch("device_battery.protocol.sys.platform", "linux"), patch(
            "device_battery.protocol.importlib.import_module", return_value=raw_api
        ) as importer:
            self.assertIs(load_hid_api(), raw_api)
            importer.assert_called_once_with("hidraw")

    def test_source_build_fallback_and_broken_import(self):
        missing = ModuleNotFoundError("No module named hidraw", name="hidraw")
        api = object()
        with patch("device_battery.protocol.sys.platform", "linux"), patch(
            "device_battery.protocol.importlib.import_module", side_effect=[missing, api]
        ) as importer:
            self.assertIs(load_hid_api(), api)
            self.assertEqual([c.args[0] for c in importer.call_args_list], ["hidraw", "hid"])
        with patch("device_battery.protocol.sys.platform", "linux"), patch(
            "device_battery.protocol.importlib.import_module",
            side_effect=ModuleNotFoundError("missing dependency", name="dependency")
        ):
            with self.assertRaises(ModuleNotFoundError):
                load_hid_api()

    def test_diagnostics_include_noncontrol_interfaces(self):
        class API:
            @staticmethod
            def enumerate(): return [info(page=1), info(), info(vid=0x1234)]
        with patch("device_battery.protocol.os.path.exists", return_value=False):
            entries = list_devices(API)
        self.assertEqual(len(entries), 2)
        self.assertFalse(entries[0]["control_interface"])
        self.assertTrue(entries[1]["control_interface"])
        self.assertIn("裝置節點不存在", entries[1]["access_error"])
        self.assertEqual(entries[1]["path"], "/dev/hidraw5")

    def test_access_failures_keep_device_present(self):
        class DeniedDevice(FakeDevice):
            def open_path(self, path): raise OSError("open failed")
        dev = DeniedDevice(b"")
        class API:
            @staticmethod
            def enumerate(): return [info()]
            @staticmethod
            def device(): return dev
        with patch("device_battery.protocol.os.path.exists", return_value=False):
            result = poll(api=API)[0]
        self.assertTrue(result.present)
        self.assertIsNone(result.percent)
        self.assertIn("裝置節點不存在", result.status)
        self.assertEqual(result.path, "/dev/hidraw5")
        self.assertTrue(dev.closed)
        with patch("device_battery.protocol.os.path.exists", return_value=True), patch(
            "device_battery.protocol.os.access", return_value=False
        ):
            self.assertIn("udev", path_access_error(b"/dev/hidraw5"))

    def test_real_vendor_samples(self):
        self.assertEqual(parse_response(0, bytes.fromhex("0804000000845f0130cb0000000000006a")), 95)
        self.assertEqual(parse_response(0, bytes.fromhex("0804000000846400118b000000000000c5")), 100)
        self.assertEqual(parse_response(2, bytes.fromhex("0804000000026400101b000000000000b8")), 100)
        packet = bytearray(request_original())
        packet[8:10] = bytes([98, 0])
        self.assertEqual(parse_response(1, packet), 98)

    def test_corrupt_wrong_and_out_of_range_responses(self):
        bad = bytearray(compact_reply(50))
        bad[10] ^= 1
        for packet in (bad, compact_reply(101), b"\0"*17, compact_reply(50)[:-1]):
            with self.assertRaises(ValueError):
                parse_response(0, packet)
        bad = bytearray(request_original())
        bad[7] = 0xFF
        with self.assertRaises(ValueError):
            parse_response(1, bad)
        self.assertEqual(parse_response(2, compact_reply(0)), 0)

    def test_receiver_ids_and_vendor_collections(self):
        self.assertEqual(identify(info()), 0)
        self.assertIsNone(identify(info(page=1)))
        self.assertIsNone(identify(info(path=b"\\\\?\\HID#VID_05AC&PID_024F&Col04")))
        self.assertEqual(identify(info(path=b"\\\\?\\HID#VID_05AC&PID_024F&Col05")), 0)
        self.assertEqual(identify(info(0x320F, 0x706E, 0xFF1C)), 1)
        self.assertEqual(identify(info(0x35BB, 0xD3FB)), 2)
        self.assertIsNone(identify(info(0x320F, 0x9999, 0xFF1C)))
        self.assertEqual(connection(0, info()), "2.4 GHz 接收器")
        self.assertEqual(connection(0, info(product="Air100@Lofree")), "USB 有線")

    def test_color_boundaries(self):
        self.assertEqual(battery_color(29), "#ef4141")
        self.assertEqual(battery_color(30), "#ff9e23")
        self.assertEqual(battery_color(70), "#ff9e23")
        self.assertEqual(battery_color(71), "#28c25d")
        self.assertNotEqual(battery_color(None), battery_color(0))

    def test_poll_closes_handles_and_never_reuses_missing_devices(self):
        dev = FakeDevice(compact_reply(73))
        class API:
            @staticmethod
            def enumerate(): return [info(), info()]
            @staticmethod
            def device(): return dev
        results = poll(api=API)
        self.assertEqual(results[0].percent, 73)
        self.assertTrue(results[0].present)
        self.assertFalse(results[1].present)
        self.assertIsNone(results[1].percent)
        self.assertTrue(dev.closed)
        API.enumerate = staticmethod(lambda: [])
        self.assertIsNone(poll(api=API)[0].percent)
        self.assertFalse(poll(api=API)[0].present)

    def test_receiver_without_control_collection_is_still_present(self):
        class API:
            @staticmethod
            def enumerate(): return [info(0x35BB, 0xD3FB, page=1)]
            @staticmethod
            def device(): raise AssertionError("Never query ordinary input collections")
        result = poll(api=API)
        self.assertTrue(result[2].present)
        self.assertIsNone(result[2].percent)
        self.assertFalse(result[0].present)

    def test_rename_and_theme_survive_restart(self):
        with tempfile.TemporaryDirectory() as root:
            settings = Settings(root)
            settings.names[0] = "我的鍵盤"
            settings.dark = False
            settings.save()
            again = Settings(root)
            self.assertEqual(again.names[0], "我的鍵盤")
            self.assertFalse(again.dark)
            settings.path.write_text("broken", encoding="utf-8")
            self.assertTrue(Settings(root).dark)

    def test_desktop_entry_handles_space_and_background(self):
        entry = desktop_entry("/home/test user/python", "/home/test user/app.py", hidden=True)
        self.assertIn('Exec="/home/test user/python" "/home/test user/app.py" --background', entry)


if __name__ == "__main__":
    unittest.main()
