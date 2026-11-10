#!/usr/bin/env python3
"""Check that the EasyTier integrity patch applies to the pinned source."""

from pathlib import Path
from tempfile import TemporaryDirectory
import shutil
import subprocess

REPO = Path(__file__).resolve().parents[1]
PATCH = REPO / "patches/easytier/0001-verify-mipsel-core-sha256.patch"


def main() -> None:
    with TemporaryDirectory(dir=REPO) as temporary:
        root = Path(temporary)
        makefile = root / "easytier/Makefile"
        makefile.parent.mkdir(parents=True)
        shutil.copy(REPO / "tests/fixtures/easytier-Makefile", makefile)
        subprocess.run(["git", "apply", "--check", PATCH], cwd=root, check=True)
        subprocess.run(["git", "apply", PATCH], cwd=root, check=True)
        patched = makefile.read_text(encoding="utf-8")
        assert "65281c45ff62cc3be6efdeabd2e5c6bfd11b00545c8df3e940704a47fb72f97b" in patched
        assert "sha256sum -c" in patched
    print("EasyTier patch test passed")


if __name__ == "__main__":
    main()
