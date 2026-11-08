#!/usr/bin/env bash
set -euo pipefail
if [[ ${EUID} -eq 0 ]]; then echo '請以一般使用者執行。' >&2; exit 1; fi
app_dir="${XDG_DATA_HOME:-$HOME/.local/share}/device-battery-tray"
echo '請先從任一電量圖示右鍵選擇「結束全部圖示」。'
python3 - "$app_dir" <<'PY'
import os, shutil, sys
from pathlib import Path
data = Path(os.environ.get('XDG_DATA_HOME', Path.home()/'.local/share'))
config = Path(os.environ.get('XDG_CONFIG_HOME', Path.home()/'.config'))
target = Path(sys.argv[1])
if target.name != 'device-battery-tray' or target.resolve() != (data/'device-battery-tray').resolve():
    raise SystemExit('拒絕移除非預期的安裝路徑')
(data/'applications/device-battery-tray.desktop').unlink(missing_ok=True)
(config/'autostart/device-battery-tray.desktop').unlink(missing_ok=True)
if target.is_symlink():
    target.unlink()
elif target.exists():
    shutil.rmtree(target)
print('已移除應用程式，保留自訂名稱及主題設定。')
PY
if [[ -f /etc/udev/rules.d/70-device-battery-tray.rules ]]; then
    echo '移除此工具的 udev 規則（需要 sudo）。'
    sudo rm -- /etc/udev/rules.d/70-device-battery-tray.rules
    sudo udevadm control --reload-rules
fi
