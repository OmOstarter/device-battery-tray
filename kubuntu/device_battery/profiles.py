"""Declarative battery profiles. Codes contain data, never executable code."""
import base64
import hashlib
import json
from datetime import datetime
from .protocol import (Reading, load_hid_api, exchange, request_compact,
                       request_original, path_access_error)

PROTOCOLS = {"lofree": (0, 0xFF02), "hecate-original": (1, 0xFF1C),
             "hecate-upgraded": (2, 0xFF02)}
EXAMPLE = '{"version":1,"name":"LOFREE 小順青春版","vid":"05AC","pid":"024F","protocol":"lofree"}'


def parse_code(code):
    if not isinstance(code, str) or len(code) > 8192:
        raise ValueError("代碼過長或格式錯誤")
    try:
        text = code.strip()
        if text.startswith("DBT1:"):
            payload = text[5:]
            text = base64.b64decode(payload + "=" * (-len(payload) % 4), altchars=b'-_', validate=True).decode('utf-8')
        data = json.loads(text)
        if not isinstance(data, dict) or data.get("version") != 1:
            raise ValueError("需要 version: 1 的協定設定")
        name, protocol = data.get("name"), data.get("protocol")
        if not isinstance(name, str) or not 0 < len(name.strip()) <= 32:
            raise ValueError("裝置名稱需為 1 至 32 個字元")
        if not isinstance(protocol, str) or protocol not in PROTOCOLS:
            raise ValueError("不支援的協定；目前可用 lofree、hecate-original、hecate-upgraded")
        def usb_id(key):
            value = data.get(key)
            if not isinstance(value, str) or not 1 <= len(value.removeprefix('0x')) <= 4:
                raise ValueError(key+" 必須是 1 至 4 位十六進位字串")
            value = int(value, 16)
            if not 1 <= value <= 0xFFFF:
                raise ValueError(key+" 超出有效範圍")
            return value
        return {"version": 1, "name": name.strip(), "vid": f'{usb_id("vid"):04X}',
                "pid": f'{usb_id("pid"):04X}', "protocol": protocol}
    except (ValueError, TypeError, UnicodeError) as error:
        raise ValueError("無效協定代碼："+str(error)) from error


def profile_entry(code):
    profile = parse_code(code)
    identity = ':'.join(profile[k] for k in ('vid', 'pid', 'protocol'))
    return {"id": "profile:"+hashlib.sha256(identity.encode()).hexdigest()[:24],
            "name": profile['name'], "source": "協定代碼", "profile": profile}


def read_profile(item, slot, api=None):
    reading = Reading(slot, item['name'], backend='profile', time=datetime.now().strftime('%H:%M:%S'))
    try:
        profile = parse_code(json.dumps(item['profile']))
        codec, page = PROTOCOLS[profile['protocol']]
        api = api if api is not None else load_hid_api()
        matches = [info for info in api.enumerate()
                   if (info.get('vendor_id'), info.get('product_id')) ==
                   (int(profile['vid'], 16), int(profile['pid'], 16))]
        reading.present = bool(matches)
        if matches:
            reading.status = '已找到裝置，未找到協定指定的控制介面'
        for info in matches:
            if info.get('usage_page') != page:
                continue
            path = info['path']
            # Restrict Windows compact keyboard access to its control collection.
            decoded = path.decode(errors='replace') if isinstance(path, bytes) else str(path)
            if codec == 0 and '#' in decoded and 'col05' not in decoded.lower():
                continue
            reading.path = decoded
            reading.connection = 'HID · '+profile['protocol']
            device = api.device()
            try:
                device.open_path(path)
                requests = [request_original()] if codec == 1 else [request_compact(codec == 0), request_compact(codec != 0)]
                for request in requests:
                    try:
                        reading.percent, reading.raw = exchange(device, codec, request)
                        reading.status = '已連線'
                        return reading
                    except TimeoutError:
                        reading.status = '未收到電量回應；請確認協定代碼與設備相符'
            except OSError as error:
                reading.status = path_access_error(path) or '無法存取裝置：'+str(error)
            finally:
                device.close()
    except (ImportError, OSError, ValueError, KeyError, TypeError) as error:
        reading.status = '協定讀取失敗：'+str(error)
    return reading
