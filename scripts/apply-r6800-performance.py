#!/usr/bin/env python3
"""Apply the R6800 performance options to the OpenWrt kernel configuration.

The MT7621 target is built with the mainline mtk_eth_soc driver, so the only
kernel-level throughput knob that measurably helps is the congestion control
algorithm.  BBR is built in (not a module) and made the default; everything
else lives in the userspace overlay (sysctl + uci-defaults + r6800-perf).
"""

from pathlib import Path
import sys

KERNEL_CONFIG = Path("target/linux/ramips/mt7621/config-6.6")
BEGIN = "# --- R6800 performance options (managed) ---"
END = "# --- end R6800 performance options ---"
OPTIONS = [
    "CONFIG_TCP_CONG_BBR=y",
    'CONFIG_DEFAULT_TCP_CONG="bbr"',
]


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(f"Usage: {sys.argv[0]} OPENWRT_DIR")

    config_path = Path(sys.argv[1]).resolve() / KERNEL_CONFIG
    if not config_path.is_file():
        raise SystemExit(f"Missing kernel config: {config_path}")

    lines = config_path.read_text(encoding="utf-8").splitlines()

    # Drop a previous managed block so the operation is idempotent.
    cleaned: list[str] = []
    skipping = False
    for line in lines:
        if line.strip() == BEGIN:
            skipping = True
            continue
        if line.strip() == END:
            skipping = False
            continue
        if not skipping:
            cleaned.append(line)

    # Remove any pre-existing definitions of the managed symbols.
    managed = {option.split("=")[0] for option in OPTIONS}
    cleaned = [line for line in cleaned
               if line.split("=")[0].strip() not in managed]

    block = [BEGIN, *OPTIONS, END]
    config_path.write_text("\n".join(cleaned + block) + "\n", encoding="utf-8")

    print("R6800 performance kernel options applied:")
    for option in OPTIONS:
        print(f"  {option}")


if __name__ == "__main__":
    main()
