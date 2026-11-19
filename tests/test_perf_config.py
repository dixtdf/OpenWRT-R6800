#!/usr/bin/env python3
"""Check the R6800 performance configuration and overlay files."""

from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts/apply-r6800-performance.py"


def test_kernel_config() -> None:
    with TemporaryDirectory(dir=REPO) as temporary:
        root = Path(temporary)
        config = root / "target/linux/ramips/mt7621/config-6.12"
        config.parent.mkdir(parents=True)
        config.write_text(
            "CONFIG_NET_MEDIATEK_SOC=y\n"
            "CONFIG_TCP_CONG_ADVANCED=y\n"
            "CONFIG_DEFAULT_CUBIC=y\n"
            'CONFIG_DEFAULT_TCP_CONG="cubic"\n',
            encoding="utf-8",
        )

        subprocess.run([sys.executable, str(SCRIPT), str(root)], check=True)
        first = config.read_text(encoding="utf-8")
        assert "CONFIG_TCP_CONG_BBR=y" in first
        assert "CONFIG_DEFAULT_BBR=y" in first
        assert "# CONFIG_DEFAULT_CUBIC is not set" in first
        assert "CONFIG_DEFAULT_CUBIC=y" not in first
        assert "CONFIG_DEFAULT_TCP_CONG" not in first
        assert "CONFIG_NET_MEDIATEK_SOC=y" in first

        # Running twice must not duplicate the managed block.
        subprocess.run([sys.executable, str(SCRIPT), str(root)], check=True)
        second = config.read_text(encoding="utf-8")
        assert second == first, "apply-r6800-performance.py is not idempotent"
        assert second.count("CONFIG_TCP_CONG_BBR=y") == 1


def test_overlay() -> None:
    sysctl = (REPO / "files/etc/sysctl.d/10-r6800-perf.conf").read_text(encoding="utf-8")
    assert "net.ipv4.tcp_congestion_control = bbr" in sysctl
    assert "net.core.netdev_budget = 1000" in sysctl

    defaults = (REPO / "files/etc/uci-defaults/90-r6800-perf").read_text(encoding="utf-8")
    assert "flow_offloading='1'" in defaults
    assert "packet_steering='1'" in defaults
    assert "country='CN'" in defaults

    helper = (REPO / "files/usr/sbin/r6800-perf").read_text(encoding="utf-8")
    assert "flow_offloading" in helper
    assert "tcp_congestion_control" in helper


def main() -> None:
    test_kernel_config()
    test_overlay()
    print("R6800 performance configuration test passed")


if __name__ == "__main__":
    main()
