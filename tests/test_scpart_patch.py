#!/usr/bin/env python3
"""Check the Sercomm size-override patch against Linux 6.6."""

from pathlib import Path
from tempfile import TemporaryDirectory
import shutil
import subprocess

REPO = Path(__file__).resolve().parents[1]
PATCH = REPO / "patches/kernel/901-scpart-dts-size.patch"


def main() -> None:
    with TemporaryDirectory(dir=REPO) as temporary:
        root = Path(temporary)
        source = root / "drivers/mtd/parsers/scpart.c"
        source.parent.mkdir(parents=True)
        shutil.copy(REPO / "tests/fixtures/scpart.c", source)
        subprocess.run(["git", "apply", "--check", PATCH], cwd=root, check=True)
        subprocess.run(["git", "apply", PATCH], cwd=root, check=True)
        patched = source.read_text(encoding="utf-8")
        assert 'of_property_read_u32(pp, "sercomm,scpart-size"' in patched
        assert "parts[nr_parts].offset = scpart_map[n].part_offs;" in patched
        assert "parts[nr_parts].size = scpart_map[n].part_bytes;" in patched
        assert patched.count('"sercomm,scpart-size"') == 1
        assert patched.index("parts[nr_parts].size = scpart_map[n].part_bytes;") < \
            patched.index("parts[nr_parts].size = scpart_size;")
    print("Sercomm parser patch test passed")


if __name__ == "__main__":
    main()
