import json
import os
from pathlib import Path
from .protocol import DEFAULT_NAMES


class Settings:
    def __init__(self, root=None):
        self.root = Path(root) if root else Path(os.environ.get("XDG_CONFIG_HOME", Path.home()/".config"))/"device-battery-tray"
        self.path = self.root/"preferences.json"
        self.dark = True
        self.names = DEFAULT_NAMES.copy()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.dark = data.get("dark", True) is not False
            names = data.get("names")
            if isinstance(names, list) and len(names) == 3:
                self.names = [n.strip() if isinstance(n, str) and 0 < len(n.strip()) <= 32 else DEFAULT_NAMES[i] for i, n in enumerate(names)]
        except (OSError, ValueError, TypeError):
            pass

    def save(self):
        self.root.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps({"dark": self.dark, "names": self.names}, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.path)


def autostart_path():
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home()/".config"))/"autostart"/"device-battery-tray.desktop"


def desktop_quote(text):
    return '"' + str(text).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$') + '"'


def desktop_entry(python, script, hidden=False):
    args = " --background" if hidden else ""
    return "\n".join(["[Desktop Entry]", "Type=Application", "Name=Device Battery Tray", "Name[zh_TW]=裝置電量", "Comment=Keyboard and mouse battery monitor", "Exec="+desktop_quote(python)+" "+desktop_quote(script)+args, "Icon=input-mouse", "Terminal=false", "Categories=Utility;", "StartupNotify=false", ""])
