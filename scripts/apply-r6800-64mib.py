#!/usr/bin/env python3
"""Apply the R6800 64 MiB UBI layout without moving factory data."""

from pathlib import Path
import shutil
import sys

DTSI = Path("target/linux/ramips/dts/mt7621_netgear_sercomm_bzv.dtsi")
IMAGE = Path("target/linux/ramips/image/mt7621.mk")
KERNEL_PATCH = Path("target/linux/ramips/patches-6.6/901-scpart-dts-size.patch")
OLD_UBI = "reg = <0x600000 0x2800000>;"
NEW_UBI = "reg = <0x600000 0x4000000>;"


def replace_once(text: str, old: str, new: str, description: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{description}: expected one match, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(f"Usage: {sys.argv[0]} OPENWRT_DIR")

    root = Path(sys.argv[1]).resolve()
    dtsi_path = root / DTSI
    image_path = root / IMAGE

    dtsi = dtsi_path.read_text(encoding="utf-8")
    if 'compatible = "sercomm,sc-partitions", "fixed-partitions";' not in dtsi:
        raise RuntimeError("Sercomm partition parser is missing from the source DTSI")

    dtsi = replace_once(dtsi, OLD_UBI, NEW_UBI, "UBI size")
    dtsi = replace_once(dtsi, NEW_UBI,
                        NEW_UBI + "\n\t\t\tsercomm,scpart-size = <0x4000000>;",
                        "Sercomm UBI size override")

    reclaimed_start = dtsi.find("\t\tpartition@2e00000 {")
    factory_start = dtsi.find("\t\tpartition@4600000 {")
    if reclaimed_start < 0 or factory_start < 0 or reclaimed_start >= factory_start:
        raise RuntimeError("Cannot locate the UI/ML partitions or factory boundary")

    reclaimed = dtsi[reclaimed_start:factory_start]
    if reclaimed.count("sercomm,scpart-id") != 12:
        raise RuntimeError("Expected to reclaim exactly English UI and ML1-ML11")
    dtsi = dtsi[:reclaimed_start] + dtsi[factory_start:]

    if 'label = "factory";' not in dtsi or "sercomm,scpart-id = <16>;" not in dtsi:
        raise RuntimeError("Factory partition or its Sercomm ID was not preserved")
    dtsi_path.write_text(dtsi, encoding="utf-8")

    image = image_path.read_text(encoding="utf-8")
    block_start = image.index("define Device/netgear_r6800")
    block_end = image.index("TARGET_DEVICES += netgear_r6800", block_start)
    block = image[block_start:block_end]
    block = replace_once(block, "IMAGE_SIZE := 40960k", "IMAGE_SIZE := 65536k", "IMAGE_SIZE")
    image = image[:block_start] + block + image[block_end:]
    image_path.write_text(image, encoding="utf-8")

    project = Path(__file__).resolve().parents[1]
    kernel_patch = root / KERNEL_PATCH
    kernel_patch.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(project / "patches/kernel/901-scpart-dts-size.patch", kernel_patch)

    print("R6800 layout applied:")
    print("  UBI:     0x00600000 + 0x04000000 (64 MiB)")
    print("  Factory: 0x04600000 + 0x00200000 (unchanged, read-only)")
    print("  Reclaimed: English UI and ML1-ML11 only")


if __name__ == "__main__":
    main()
