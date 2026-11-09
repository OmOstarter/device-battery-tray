import json
import os
from pathlib import Path
from .protocol import DEFAULT_NAMES


class Settings:
    def __init__(self, root=None):
        self.root = Path(root) if root else Path(os.environ.get("XDG_CONFIG_HOME", Path.home()/".config"))/"device-battery-tray"
        self.path = self.root/"preferences.json"
        self.dark = True
        self.devices = []
        self.names = DEFAULT_NAMES.copy()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.dark = data.get("dark", True) is not False
            devices = data.get("devices", [])
            if isinstance(devices, list):
                seen = set()
                for item in devices:
                    if not isinstance(item, dict):
                        continue
                    key, name = item.get("id"), item.get("name")
                    if (isinstance(key, str) and key not in ("", ".", "..")
                            and "/" not in key and "\\" not in key and key not in seen
                            and isinstance(name, str) and 0 < len(name.strip()) <= 32):
                        entry = {"id": key, "name": name.strip()}
                        if isinstance(item.get("source"), str):
                            entry["source"] = item["source"]
                        if isinstance(item.get("identity"), str):
                            entry["identity"] = item["identity"]
                        for field in ("vid", "pid", "port", "manufacturer", "product", "detail"):
                            if isinstance(item.get(field), str):
                                entry[field] = item[field][:2048]
                        if isinstance(item.get("analysis"), dict):
                            entry["analysis"] = {k: v[:2048] for k, v in item["analysis"].items()
                                                 if k in ("name", "vid", "pid", "connection", "driver_path", "notes")
                                                 and isinstance(v, str)}
                        if key.startswith("profile:"):
                            from .profiles import profile_entry
                            try:
                                validated = profile_entry(json.dumps(item.get("profile")))
                                if validated["id"] != key:
                                    continue
                                entry["profile"] = validated["profile"]
                            except ValueError:
                                continue
                        self.devices.append(entry)
                        seen.add(key)
            names = data.get("names")
            if isinstance(names, list) and len(names) == 3:
                self.names = [n.strip() if isinstance(n, str) and 0 < len(n.strip()) <= 32 else DEFAULT_NAMES[i] for i, n in enumerate(names)]
        except (OSError, ValueError, TypeError):
            pass

    def save(self):
        self.root.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps({"dark": self.dark, "names": self.names, "devices": self.devices}, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.path)


def autostart_path():
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home()/".config"))/"autostart"/"device-battery-tray.desktop"


def desktop_quote(text):
    return '"' + str(text).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$') + '"'


def desktop_entry(python, script, hidden=False):
    args = " --background" if hidden else ""
    return "\n".join(["[Desktop Entry]", "Type=Application", "Name=Device Battery Tray", "Name[zh_TW]=裝置電量", "Comment=Keyboard and mouse battery monitor", "Exec="+desktop_quote(python)+" "+desktop_quote(script)+args, "Icon=input-mouse", "Terminal=false", "Categories=Utility;", "StartupNotify=false", ""])
