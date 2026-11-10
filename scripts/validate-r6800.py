#!/usr/bin/env python3
"""Validate R6800 configuration, partition layout, DTB and generated images."""

import argparse
from pathlib import Path
import re
import shutil
import subprocess

DTSI = Path("target/linux/ramips/dts/mt7621_netgear_sercomm_bzv.dtsi")
IMAGE = Path("target/linux/ramips/image/mt7621.mk")
OUTPUT = Path("bin/targets/ramips/mt7621")
UBI_START = 0x600000
UBI_SIZE = 0x4000000
FACTORY_START = 0x4600000
FACTORY_SIZE = 0x200000

REQUIRED_PACKAGES = {
    "easytier",
    "luci-app-easytier",
    "kmod-tun",
    "luci",
    "luci-app-ddns",
    "luci-app-sqm",
    "luci-app-firewall",
    "luci-app-package-manager",
    "ddns-scripts-cloudflare",
    "dnsmasq-full",
    "block-mount",
    "openssh-sftp-server",
    "kmod-usb-storage",
    "kmod-fs-ext4",
    "kmod-fs-vfat",
    "kmod-fs-exfat",
    "kmod-fs-ntfs3",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def partitions(dts: str):
    found = []
    for match in re.finditer(r"\bpartition@([0-9a-f]+)\b", dts):
        brace = dts.find("{", match.end())
        if brace < 0:
            continue
        depth = 0
        end = brace
        for end in range(brace, len(dts)):
            if dts[end] == "{":
                depth += 1
            elif dts[end] == "}":
                depth -= 1
                if depth == 0:
                    break
        require(depth == 0, f"Unclosed partition node at 0x{match.group(1)}")
        body = dts[brace + 1:end]
        reg = re.search(r"reg = <(0x[0-9a-f]+) (0x[0-9a-f]+)>;", body)
        if reg:
            found.append((int(match.group(1), 16), int(reg.group(1), 16),
                          int(reg.group(2), 16), body))
    return found


def validate_layout_text(dts: str, decompiled: bool = False) -> None:
    require('compatible = "sercomm,sc-partitions", "fixed-partitions";' in dts,
            "Sercomm parser is missing")
    parts = partitions(dts)
    require(len(parts) == 17, f"Expected 17 partitions, found {len(parts)}")

    ids = sorted(int(value, 0) for _, _, _, body in parts
                 for value in re.findall(r"sercomm,scpart-id = <([^>]+)>;", body))
    require(ids == [0, 1, 2, 3] + list(range(16, 29)),
            f"Unexpected Sercomm partition IDs: {ids}")

    previous_end = 0
    for node_offset, offset, size, _ in sorted(parts, key=lambda item: item[1]):
        require(offset == node_offset, f"Node offset mismatch at 0x{node_offset:x}")
        require(offset >= previous_end, f"Overlapping partition at 0x{offset:x}")
        previous_end = offset + size

    ubi = [part for part in parts if part[1] == UBI_START]
    require(len(ubi) == 1 and ubi[0][2] == UBI_SIZE, "UBI is not 64 MiB")
    factory = [part for part in parts if part[1] == FACTORY_START]
    require(len(factory) == 1 and factory[0][2] == FACTORY_SIZE,
            "Factory offset or size changed")
    require("read-only;" in factory[0][3], "Factory must be read-only")
    require(UBI_START + UBI_SIZE <= FACTORY_START, "UBI overlaps factory")
    require("sercomm,scpart-size = <0x4000000>;" in dts,
            "Sercomm runtime UBI size override is missing")
    require("eeprom@0" in dts and "eeprom@8000" in dts,
            "Wireless EEPROM cells are missing")
    if not decompiled:
        require("English UI" not in dts and not re.search(r"ML(?:[1-9]|10|11)", dts),
                "UI/ML partitions were not fully reclaimed")


def validate_image_definition(root: Path) -> None:
    image = (root / IMAGE).read_text(encoding="utf-8")
    start = image.index("define Device/netgear_r6800")
    end = image.index("TARGET_DEVICES += netgear_r6800", start)
    require("IMAGE_SIZE := 65536k" in image[start:end],
            "R6800 IMAGE_SIZE is not 64 MiB")


def validate_config(root: Path) -> None:
    config = (root / ".config").read_text(encoding="utf-8")
    enabled = set(re.findall(r"^(CONFIG_PACKAGE_[^=]+)=y$", config, re.MULTILINE))
    for package in sorted(REQUIRED_PACKAGES):
        require(f"CONFIG_PACKAGE_{package}" in enabled,
                f"Required package is not enabled: {package}")

    require("CONFIG_TARGET_ramips_mt7621_DEVICE_netgear_r6800=y" in config,
            "Wrong target device")
    require("CONFIG_TARGET_ROOTFS_INITRAMFS=y" in config,
            "Initramfs image is disabled")
    require("# CONFIG_PACKAGE_dnsmasq is not set" in config,
            "dnsmasq-full did not replace dnsmasq")

    forbidden = re.compile(r"^CONFIG_PACKAGE_.*(?:passwall|openvpn).*?=y$",
                           re.MULTILINE | re.IGNORECASE)
    match = forbidden.search(config)
    require(not match, f"Forbidden package found: {match.group(0) if match else ''}")


def validate_artifacts(root: Path) -> None:
    output = root / OUTPUT
    prefix = "openwrt-ramips-mt7621-netgear_r6800"
    required_files = [
        output / f"{prefix}-squashfs-factory.img",
        output / f"{prefix}-squashfs-sysupgrade.bin",
        output / f"{prefix}-initramfs-kernel.bin",
        output / f"{prefix}.manifest",
        output / "config.buildinfo",
    ]
    for path in required_files:
        require(path.is_file() and path.stat().st_size > 0, f"Missing artifact: {path}")

    manifest = (output / f"{prefix}.manifest").read_text(encoding="utf-8")
    require(re.search(r"^easytier - 2\.7\.0(?:-|$)", manifest, re.MULTILINE) is not None,
            "EasyTier 2.7.0 is absent from the manifest")
    require(re.search(r"^luci-app-easytier - 2\.7\.0(?:-|$)", manifest, re.MULTILINE) is not None,
            "EasyTier LuCI 2.7.0 is absent from the manifest")
    require(re.search(r"(?:passwall|openvpn)", manifest, re.IGNORECASE) is None,
            "Passwall/OpenVPN found in the manifest")

    require(shutil.which("dtc") is not None, "dtc is required for DTB validation")
    dtbs = list((root / "build_dir").rglob("image-mt7621_netgear_r6800.dtb"))
    if not dtbs:
        dtbs = list((root / "build_dir").rglob("mt7621_netgear_r6800.dtb"))
    require(dtbs, "No R6800 DTB found")
    for dtb in dtbs:
        result = subprocess.run(["dtc", "-I", "dtb", "-O", "dts", str(dtb)],
                                check=True, text=True, capture_output=True)
        validate_layout_text(result.stdout, decompiled=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("openwrt_dir", type=Path)
    parser.add_argument("--skip-config", action="store_true")
    parser.add_argument("--artifacts", action="store_true")
    args = parser.parse_args()
    root = args.openwrt_dir.resolve()

    require((root / "target/linux/ramips/patches-6.6/901-scpart-dts-size.patch").is_file(),
            "Sercomm runtime size-override kernel patch is missing")
    dtsi = (root / DTSI).read_text(encoding="utf-8")
    validate_layout_text(dtsi)
    validate_image_definition(root)
    if not args.skip_config:
        validate_config(root)
    if args.artifacts:
        validate_artifacts(root)
    print("R6800 validation passed: 64 MiB UBI, protected factory, valid configuration")


if __name__ == "__main__":
    main()
