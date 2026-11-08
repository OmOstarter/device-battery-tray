#!/usr/bin/env python3
"""Kubuntu tray utility; --diagnose/--list-devices work without Qt."""
import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="LOFREE / HECATE 電量系統匣工具")
    parser.add_argument("--background", action="store_true", help="只顯示系統匣圖示")
    parser.add_argument("--diagnose", action="store_true", help="讀取真實電量並輸出 JSON")
    parser.add_argument("--list-devices", action="store_true", help="列出支援裝置的全部 HID 介面、後端及存取狀態")
    parser.add_argument("--preview-ui", type=Path, help="輸出示例介面 PNG，不查詢硬體")
    args = parser.parse_args()
    try:
        if args.list_devices:
            from device_battery.protocol import list_devices
            print(json.dumps(list_devices(), ensure_ascii=False, indent=2))
            return 0
        if args.diagnose:
            from device_battery.protocol import poll
            from device_battery.settings import Settings
            readings = poll(Settings().names)
            print(json.dumps([r.to_dict() for r in readings], ensure_ascii=False, indent=2))
            return 0 if all(r.percent is not None for r in readings) else 2
        from device_battery.gui import run
        return run(args.background, args.preview_ui)
    except ImportError as error:
        print("缺少相依套件，請先執行 bash install.sh："+str(error), file=sys.stderr)
        return 1
    except Exception as error:
        print("執行失敗："+str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
