#!/usr/bin/env bash
set -euo pipefail
if [[ ${EUID} -eq 0 ]]; then
    echo '請以一般使用者執行 bash install.sh；僅 udev 規則安裝時會使用 sudo。' >&2
    exit 1
fi
skip_udev=false
if [[ ${1:-} == --no-udev ]]; then skip_udev=true; elif [[ $# -gt 0 ]]; then
    echo '用法：bash install.sh [--no-udev]' >&2; exit 1
fi
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
app_dir="${XDG_DATA_HOME:-$HOME/.local/share}/device-battery-tray"
command -v python3 >/dev/null || { echo '請先安裝 python3。' >&2; exit 1; }
python3 -c 'import sys; assert sys.version_info >= (3, 10), "需要 Python 3.10 或更新版本"'
mkdir -p -- "$app_dir"
if [[ "$source_dir" != "$app_dir" ]]; then
    cp -- "$source_dir/device-battery-tray.py" "$source_dir/requirements.txt" "$app_dir/"
    mkdir -p -- "$app_dir/device_battery"
    cp -- "$source_dir"/device_battery/*.py "$app_dir/device_battery/"
fi
venv_python="$app_dir/.venv/bin/python"
# Reuse a working environment during updates. Re-running venv rewrites its
# activation scripts, which may be read-only even when Python works normally.
if [[ -x "$venv_python" ]] && "$venv_python" -c 'import sys, pip; assert sys.version_info >= (3, 10); assert sys.prefix != sys.base_prefix' 2>/dev/null; then
    echo '沿用既有 Python 虛擬環境。'
else
    if ! python3 -m venv "$app_dir/.venv"; then
        printf '無法建立虛擬環境：%s\n' "$app_dir/.venv" >&2
        echo '請依上方原始錯誤排查：Permission denied 表示檔案／目錄權限問題；只有缺少 venv 或 ensurepip 時才需安裝 python3-venv。' >&2
        exit 1
    fi
fi
"$app_dir/.venv/bin/python" -m pip install -r "$app_dir/requirements.txt"
"$app_dir/.venv/bin/python" - "$app_dir" <<'PY'
import os, sys
from pathlib import Path
root = Path(sys.argv[1])
sys.path.insert(0, str(root))
from device_battery.settings import desktop_entry
applications = Path(os.environ.get('XDG_DATA_HOME', Path.home()/'.local/share'))/'applications'
applications.mkdir(parents=True, exist_ok=True)
(applications/'device-battery-tray.desktop').write_text(desktop_entry(root/'.venv/bin/python', root/'device-battery-tray.py'), encoding='utf-8')
PY
if [[ "$skip_udev" == false ]]; then
    echo '將安裝此工具專用的裝置權限規則（需要 sudo）。'
    sudo install -m 0644 -- "$source_dir/70-device-battery-tray.rules" /etc/udev/rules.d/70-device-battery-tray.rules
    sudo udevadm control --reload-rules
    sudo udevadm trigger --subsystem-match=hidraw
fi
echo '安裝完成。請重新插拔接收器／USB 線，從應用程式選單搜尋「裝置電量」。'
printf '命令列啟動："%s/.venv/bin/python" "%s/device-battery-tray.py"\n' "$app_dir" "$app_dir"
