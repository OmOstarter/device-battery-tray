"""USB hotplug identification using physical sysfs devices, without HID writes."""
from pathlib import Path

USB_ROOT = Path('/sys/bus/usb/devices')


def usb_snapshot(root=None):
    root = Path(root) if root is not None else USB_ROOT
    if not root.is_dir():
        raise OSError('無法存取 USB 裝置目錄：'+str(root))
    devices = {}
    for path in sorted(root.iterdir()):
        if ':' in path.name:  # Composite USB interfaces are not separate receivers.
            continue
        try:
            vid = f'{int((path / "idVendor").read_text().strip(), 16):04X}'
            pid = f'{int((path / "idProduct").read_text().strip(), 16):04X}'
            def text(name):
                try:
                    return (path / name).read_text().strip()
                except OSError:
                    return ''
            manufacturer, product = text('manufacturer'), text('product')
            devices[path.name] = {'id': 'usb:'+path.name, 'name': (product or manufacturer or f'USB {vid}:{pid}')[:32],
                                  'source': 'USB', 'vid': vid, 'pid': pid, 'port': path.name,
                                  'manufacturer': manufacturer, 'product': product,
                                  'generation': text('busnum')+':'+text('devnum'),
                                  'present': True, 'percent': None, 'path': str(path)}
        except (OSError, ValueError):
            continue  # A device may disappear while its attributes are being read.
    return devices


def usb_changes(previous, current):
    def signature(item):
        return item['vid'], item['pid'], item.get('generation')
    removed = [('拔除', dict(item, present=False)) for key, item in previous.items()
               if key not in current or signature(item) != signature(current[key])]
    added = [('插入', item) for key, item in current.items()
             if key not in previous or signature(item) != signature(previous[key])]
    return removed + added
