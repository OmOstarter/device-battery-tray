"""Read battery information published by Linux; never send vendor commands."""
import hashlib
import json
import math
import re
import subprocess
from datetime import datetime
from pathlib import Path
from .protocol import Reading

POWER_SUPPLY = Path("/sys/class/power_supply")


def discover_power(root=None):
    root = Path(root) if root is not None else POWER_SUPPLY
    devices = []
    for path in sorted(root.glob("*")):
        try:
            if (path / "type").read_text().strip() != "Battery":
                continue
            model = path / "model_name"
            name = model.read_text().strip() if model.exists() else path.name
            devices.append({"id": path.name, "name": (name or path.name)[:32]})
        except (OSError, ValueError):
            continue
    return devices


def read_power(devices, start=3, root=None):
    root = Path(root) if root is not None else POWER_SUPPLY
    readings = []
    for slot, item in enumerate(devices, start):
        path = root / item["id"]
        reading = Reading(slot, item["name"], time=datetime.now().strftime("%H:%M:%S"),
                          connection="系統電量", backend="power_supply", path=str(path))
        reading.present = path.exists()
        if reading.present:
            try:
                present = path / "present"
                if present.exists() and present.read_text().strip() == "0":
                    reading.present = False
                else:
                    value = int((path / "capacity").read_text().strip())
                    if not 0 <= value <= 100:
                        raise ValueError("電量超出範圍")
                    reading.percent, reading.status = value, "已連線"
            except (OSError, ValueError):
                reading.status = "無法讀取系統電量"
        readings.append(reading)
    return readings


def bus_call(service, path, interface, method, *args):
    result = subprocess.run(["busctl", "--system", "--timeout=2", "--json=short", "call",
                             service, path, interface, method, *args],
                            capture_output=True, text=True, timeout=3, check=True)
    return json.loads(result.stdout)["data"][0]


def unbox(value):
    if isinstance(value, dict) and "type" in value and "data" in value:
        return unbox(value["data"])
    if isinstance(value, dict):
        return {k: unbox(v) for k, v in value.items()}
    if isinstance(value, list):
        return [unbox(v) for v in value]
    return value


def percent(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and 0 <= value <= 100:
        return round(value)
    return None


def bluetooth_identity(value):
    match = re.search(r"(?:[0-9a-f]{2}[:_]){5}[0-9a-f]{2}", value, re.I)
    return match.group().replace("_", ":").upper() if match else ""


def service_devices(errors):
    devices = []
    try:
        paths = bus_call("org.freedesktop.UPower", "/org/freedesktop/UPower",
                         "org.freedesktop.UPower", "EnumerateDevices")
        for path in paths:
            props = unbox(bus_call("org.freedesktop.UPower", path,
                                  "org.freedesktop.DBus.Properties", "GetAll", "s",
                                  "org.freedesktop.UPower.Device"))
            if props.get("Type") in (0, 1):
                continue
            # Kernel battery devices are already available through power_supply.
            native = props.get("NativePath", "")
            if native and (POWER_SUPPLY / Path(native).name).exists():
                continue
            devices.append({"id": "upower:"+path.rsplit("/", 1)[-1],
                            "name": str(props.get("Model") or path.rsplit("/", 1)[-1])[:32],
                            "identity": bluetooth_identity(str(props.get("Serial") or native)),
                            "source": "UPower", "percent": percent(props.get("Percentage")),
                            "present": props.get("IsPresent", True), "path": path})
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        errors.append("UPower 無法讀取："+str(error))
    try:
        objects = unbox(bus_call("org.bluez", "/", "org.freedesktop.DBus.ObjectManager", "GetManagedObjects"))
        for path, interfaces in objects.items():
            props = interfaces.get("org.bluez.Device1")
            if not props:
                continue
            battery = interfaces.get("org.bluez.Battery1", {})
            devices.append({"id": "bluez:"+path.replace("/", "|"),
                            "name": str(props.get("Alias") or props.get("Name") or props.get("Address", "藍牙裝置"))[:32],
                            "identity": bluetooth_identity(str(props.get("Address") or path)),
                            "source": "藍牙", "percent": percent(battery.get("Percentage")) if props.get("Connected") else None,
                            "present": bool(props.get("Connected")), "path": path})
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        errors.append("藍牙服務無法讀取："+str(error))
    return devices


def hid_devices(root=Path("/sys/bus/hid/devices")):
    from .protocol import MODEL_IDS
    devices = []
    seen = set()
    for path in sorted(root.glob("*")):
        try:
            props = dict(line.split("=", 1) for line in (path / "uevent").read_text().splitlines() if "=" in line)
            bus, vid, pid = (int(n, 16) for n in props["HID_ID"].split(":"))
            if (vid, pid) in MODEL_IDS:
                continue
            identity = f'{vid:04x}:{pid:04x}:'+ (props.get("HID_UNIQ") or props.get("HID_PHYS") or path.name)
            key = "hid:"+hashlib.sha256(identity.encode()).hexdigest()[:24]
            if key in seen:
                continue
            seen.add(key)
            devices.append({"id": key, "name": props.get("HID_NAME", f"HID {vid:04X}:{pid:04X}")[:32],
                            "source": "HID", "percent": None, "present": True,
                            "vid": f"{vid:04X}", "pid": f"{pid:04X}",
                            "path": str(path), "detail": f"{vid:04X}:{pid:04X}"})
        except (OSError, ValueError, KeyError):
            continue
    return devices


def discover(root=None, errors=None):
    devices = discover_power(root)
    if root is not None:
        return devices
    for item in devices:
        reading = read_power([item])[0]
        item.update(source="系統電量", percent=reading.percent, present=reading.present)
    devices.extend(service_devices(errors if errors is not None else []))
    devices.extend(hid_devices())
    return devices


def read_devices(devices, start=3, root=None):
    external = [d for d in devices if d["id"].startswith(("bluez:", "upower:", "hid:", "usb:"))]
    errors = []
    snapshot = {d["id"]: d for d in discover(errors=errors)} if any(
        not d["id"].startswith("usb:") for d in external) else {}
    if any(d["id"].startswith("usb:") for d in devices):
        from .usb_devices import usb_snapshot
        try:
            snapshot.update((d["id"], d) for d in usb_snapshot().values())
        except OSError as error:
            errors.append(str(error))
    readings = []
    for slot, item in enumerate(devices, start):
        if item["id"].startswith("profile:"):
            from .profiles import read_profile
            readings.append(read_profile(item, slot))
            continue
        if item not in external:
            readings.extend(read_power([item], slot, root))
            continue
        found = snapshot.get(item["id"])
        reading = Reading(slot, item["name"], time=datetime.now().strftime("%H:%M:%S"),
                          backend=item.get("source", "系統裝置"))
        if found:
            reading.present = found.get("present", True)
            reading.percent = found.get("percent")
            reading.connection = found.get("source", "系統裝置")
            reading.path = found.get("path", "")
            reading.status = "已連線" if reading.percent is not None else "已找到裝置，尚未提供電量；可能需要專用協定"
        elif errors and item["id"].startswith(("bluez:", "upower:")):
            reading.present = True
            reading.status = "無法讀取系統服務，請重新刷新"
        readings.append(reading)
    return readings
