#!/usr/bin/env python3
"""Build a native dependency-based Debian package without root or pip."""
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


def main():
    source = Path(__file__).resolve().parent
    repo = source.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=repo / "dist")
    args = parser.parse_args()
    version = (repo / "VERSION").read_text().strip()
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        parser.error("VERSION must contain a three-part numeric version")
    args.output.mkdir(parents=True, exist_ok=True)
    output = args.output.resolve() / f"device-battery-tray_{version}_all.deb"
    with tempfile.TemporaryDirectory(prefix="device-battery-deb-") as temporary:
        root = Path(temporary)
        root.chmod(0o755)
        app = root / "usr/share/device-battery-tray"
        app.mkdir(parents=True)
        shutil.copy2(source / "device-battery-tray.py", app)
        shutil.copytree(source / "device_battery", app / "device_battery",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        binary = root / "usr/bin/device-battery-tray"
        binary.parent.mkdir(parents=True)
        binary.write_text('#!/bin/sh\nexec /usr/bin/python3 /usr/share/device-battery-tray/device-battery-tray.py "$@"\n')
        binary.chmod(0o755)
        for src, destination in [
            (source / "packaging/device-battery-tray.desktop", "usr/share/applications/device-battery-tray.desktop"),
            (source / "70-device-battery-tray.rules", "usr/lib/udev/rules.d/70-device-battery-tray.rules"),
            (source / "README.md", "usr/share/doc/device-battery-tray/README.md"),
        ]:
            target = root / destination
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
        control = root / "DEBIAN"
        control.mkdir()
        (control / "control").write_text(
            f"Package: device-battery-tray\nVersion: {version}\n"
            "Section: utils\nPriority: optional\nArchitecture: all\n"
            "Maintainer: Andy Lin <j333445ss@gmail.com>\n"
            "Depends: python3 (>= 3.10), python3-hid (>= 0.14), "
            "python3-pyside6.qtwidgets (>= 6.8), python3-pyside6.qtnetwork (>= 6.8), udev\n"
            "Homepage: https://github.com/OmOstarter/device-battery-tray\n"
            "Description: LOFREE and HECATE keyboard and mouse battery tray monitor\n"
            " Qt tray monitor with per-device battery readings and hidraw access rules.\n"
        )
        for name in ("postinst", "postrm"):
            shutil.copy2(source / "packaging" / name, control / name)
            (control / name).chmod(0o755)
        # Do not retain checkout-specific writable/executable bits in package data.
        for path in root.rglob("*"):
            if path.is_dir():
                path.chmod(0o755)
            elif path not in (binary, control / "postinst", control / "postrm"):
                path.chmod(0o644)
        subprocess.run(["dpkg-deb", "--root-owner-group", "--build", str(root), str(output)], check=True)
    print(output)


if __name__ == "__main__":
    main()
