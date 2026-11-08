"""Read-only battery commands recovered from the installed vendor software."""
from dataclasses import dataclass, asdict
from datetime import datetime
import importlib
import os
import sys
import time

DEFAULT_NAMES = ["LOFREE 小順青春版(100鍵)", "HECATE G3M PRO", "HECATE G3M PRO 升級版"]
MODEL_IDS = {(0x05AC, 0x024F): 0, (0x320F, 0x706B): 1,
             (0x320F, 0x706E): 1, (0x35BB, 0xD3FB): 2, (0x35BB, 0xD3FC): 2}


def load_hid_api():
    # Linux wheels expose libusb as `hid` and the kernel backend as `hidraw`.
    # Our udev rules grant access to hidraw, not to libusb's USB device nodes.
    if sys.platform.startswith("linux"):
        try:
            return importlib.import_module("hidraw")
        except ModuleNotFoundError as error:
            if error.name != "hidraw":
                raise
            # Source builds with only the hidraw backend call that module `hid`.
    return importlib.import_module("hid")


def path_access_error(path):
    path = os.fsdecode(path)
    if not path.startswith("/dev/hidraw"):
        return ""
    if not os.path.exists(path):
        return f"裝置節點不存在：{path}；請確認裝置未拔除，且執行環境可存取主機的 HID 裝置"
    if not os.access(path, os.R_OK | os.W_OK):
        return f"無權限存取 {path}；請安裝 udev 規則後重新插拔接收器"
    return ""


def list_devices(api=None):
    api = api if api is not None else load_hid_api()
    result = []
    for info in api.enumerate():
        if model_slot(info) is None:
            continue
        entry = {k: os.fsdecode(v) if isinstance(v, bytes) else v for k, v in info.items()}
        entry["control_interface"] = identify(info) is not None
        entry["backend"] = getattr(api, "__name__", "custom")
        entry["access_error"] = path_access_error(info["path"])
        result.append(entry)
    return result


def model_slot(info):
    """Physical presence is independent of the battery control collection."""
    return MODEL_IDS.get((info.get("vendor_id"), info.get("product_id")))


def battery_color(percent):
    if percent is None:
        return "#929fb5"
    return "#28c25d" if percent > 70 else "#ff9e23" if percent >= 30 else "#ef4141"


def request_compact(read_flag=True):
    packet = bytearray(17)
    packet[0:2] = b"\x08\x04"
    packet[5] = 0x80 if read_flag else 0
    packet[16] = (0x55 - sum(packet[:16])) & 255
    return bytes(packet)


def request_original():
    packet = bytearray(64)
    packet[:8] = bytes.fromhex("04 20 00 1a 06 00 00 00")
    return bytes(packet)


def parse_response(slot, packet):
    packet = bytes(packet)
    if slot == 1:
        if len(packet) != 64 or packet[:8] != request_original()[:8]:
            raise ValueError("原版滑鼠回應標頭或長度不符")
        value = packet[8]
    else:
        if len(packet) != 17 or packet[:2] != b"\x08\x04":
            raise ValueError("電量回應標頭或長度不符")
        if sum(packet) & 255 != 0x55:
            raise ValueError("電量回應校驗失敗")
        value = packet[6]
    if not 0 <= value <= 100:
        raise ValueError("電量百分比不在有效範圍")
    return value


def identify(info):
    """Match known product IDs AND their vendor control usage, not input nodes."""
    vid, pid, page = (info.get(k) for k in ("vendor_id", "product_id", "usage_page"))
    if (vid, pid, page) == (0x05AC, 0x024F, 0xFF02):
        # Wired Air100 has two FF02 collections on Windows; Col05 carries queries.
        path = os.fsdecode(info.get("path", b"")).lower()
        if "#" in path and "col05" not in path:
            return None
        return 0
    if vid == 0x320F and pid in (0x706B, 0x706E) and page == 0xFF1C:
        return 1
    if vid == 0x35BB and pid in (0xD3FB, 0xD3FC) and page == 0xFF02:
        return 2
    return None


def connection(slot, info):
    if slot == 0:
        wireless = "wireless receiver" in (info.get("product_string") or "").lower()
    else:
        wireless = info.get("product_id") == (0x706E if slot == 1 else 0xD3FB)
    return "2.4 GHz 接收器" if wireless else "USB 有線"


@dataclass
class Reading:
    slot: int
    name: str
    percent: int | None = None
    status: str = "未連線"
    connection: str = ""
    time: str = ""
    raw: str = ""
    present: bool = False
    backend: str = ""
    path: str = ""

    def to_dict(self):
        return asdict(self)


def exchange(device, slot, request, timeout=0.8):
    # Drain queued vendor status reports so an old percentage is never reused.
    for _ in range(32):
        if not device.read(64, 1):
            break
    if device.write(request) != len(request):
        raise OSError("電量查詢未完整寫入")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = device.read(64, min(150, max(1, int((deadline-time.monotonic())*1000))))
        if response:
            try:
                return parse_response(slot, response), bytes(response).hex(" ")
            except ValueError:
                continue
    raise TimeoutError("未收到電量回應")


def poll(names=None, api=None):
    if api is None:
        api = load_hid_api()
    names = names or DEFAULT_NAMES
    readings = [Reading(i, names[i], time=datetime.now().strftime("%H:%M:%S")) for i in range(3)]
    for reading in readings:
        reading.backend = getattr(api, "__name__", "custom")
    seen = set()
    for info in api.enumerate():
        model = model_slot(info)
        if model is not None:
            readings[model].present = True
            if readings[model].status == "未連線":
                readings[model].status = "已插入，未找到電量控制介面"
        slot = identify(info)
        if slot is None or readings[slot].percent is not None:
            continue
        key = (slot, info["path"])
        if key in seen:
            continue
        seen.add(key)
        result = readings[slot]
        result.connection = connection(slot, info)
        result.path = os.fsdecode(info["path"])
        device = api.device()
        try:
            device.open_path(info["path"])
            # New compact firmware uses bit 7 for read requests. The upgraded
            # mouse's vendor DLL defaults to the legacy flag, so try that first.
            requests = [request_original()] if slot == 1 else [request_compact(slot == 0), request_compact(slot != 0)]
            for request in requests:
                try:
                    result.percent, result.raw = exchange(device, slot, request)
                    result.status = "已連線"
                    break
                except TimeoutError:
                    result.status = "未收到電量回應"
        except OSError as error:
            result.status = path_access_error(info["path"]) or "無法存取裝置：" + str(error)
        finally:
            device.close()
    return readings
