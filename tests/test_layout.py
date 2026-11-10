#!/usr/bin/env python3
"""Apply the layout to pristine upstream fixtures and validate the result."""

from pathlib import Path
from tempfile import TemporaryDirectory
import importlib.util
import re
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
FILES = {
    "target/linux/ramips/dts/mt7621_netgear_sercomm_bzv.dtsi":
        "mt7621_netgear_sercomm_bzv.dtsi",
    "target/linux/ramips/image/mt7621.mk": "mt7621.mk",
}


def main() -> None:
    with TemporaryDirectory(dir=REPO) as temporary:
        root = Path(temporary)
        for name, fixture in FILES.items():
            destination = root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(REPO / "tests/fixtures" / fixture, destination)
        subprocess.run([sys.executable, REPO / "scripts/apply-r6800-64mib.py", root], check=True)
        shutil.copy(REPO / "config/r6800.config", root / ".config")
        subprocess.run([sys.executable, REPO / "scripts/validate-r6800.py", root], check=True)

        spec = importlib.util.spec_from_file_location(
            "validator", REPO / "scripts/validate-r6800.py")
        validator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(validator)
        dts = (root / "target/linux/ramips/dts/mt7621_netgear_sercomm_bzv.dtsi").read_text()
        dts = re.sub(r"sercomm,scpart-id = <(\d+)>;",
                     lambda match: f"sercomm,scpart-id = <{int(match.group(1)):#x}>;", dts)
        dts = dts.replace("partition@4600000", "factory: partition@4600000")
        validator.validate_layout_text(dts, decompiled=True)
    print("Official-source transformation test passed")


if __name__ == "__main__":
    main()
