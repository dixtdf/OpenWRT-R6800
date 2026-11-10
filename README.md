# OpenWrt R6800 64 MiB

面向 **NETGEAR R6800（MT7621 + 双 MT7615）** 的 OpenWrt 24.10.6 自动构建配置。

## 特点

- OpenWrt `v24.10.6`，使用上游 `mt76` 驱动；
- UBI 从官方 40 MiB 调整为 **64 MiB**；
- 仅回收 `English UI` 和 `ML1-ML11`，不移动 Factory；
- 保留 `sercomm,sc-partitions`、Factory Sercomm ID、双无线 EEPROM 单元及 Factory 只读属性；
- 通过独立内核补丁支持 `sercomm,scpart-size`：SC PART_MAP 继续提供实际偏移，仅 UBI 大小由 DTS 显式覆盖为 64 MiB，无需改写设备分区表；
- 包含 EasyTier 2.7.0 和 LuCI 中文管理页面；
- 不包含 Passwall、Passwall2 或 OpenVPN；
- 包含 dnsmasq-full、DDNS/Cloudflare、SQM、USB 存储、常用文件系统、SFTP 和基础管理工具；
- 构建后自动检查软件包、镜像和最终 DTB。

> **警告：**此布局只能防止后续构建覆盖 Factory，不能恢复已经丢失的无线校准数据。刷机前必须备份当前设备的 Factory 和 SC PART_MAP。不要在未备份的情况下拿另一台路由器的 Factory 直接替换本机数据。

## 分区布局

```text
UBI:     0x00600000 + 0x04000000  (64 MiB)
Factory: 0x04600000 + 0x00200000  (保持原位置，只读)
```

UBI 结束位置恰好是 Factory 的起始位置，不允许越过。对应的 R6800 `IMAGE_SIZE` 同步设置为 `65536k`。

## GitHub Actions

在 **Actions → Build OpenWrt R6800 → Run workflow** 手动启动，或推送构建相关文件自动启动。

构建产物包括：

- `openwrt-ramips-mt7621-netgear_r6800-squashfs-sysupgrade.bin`
- `openwrt-ramips-mt7621-netgear_r6800-squashfs-factory.img`
- `openwrt-ramips-mt7621-netgear_r6800-initramfs-kernel.bin`
- manifest、config.buildinfo、profiles.json 和 sha256sums

## 刷入方式

### 从 OpenWrt LuCI 刷入

进入 **系统 → 备份/升级**，上传 `squashfs-sysupgrade.bin`：

- 勾选“保留配置”：执行普通 sysupgrade；
- 取消“保留配置”：清空旧配置并重新生成 rootfs_data。

`factory.img` 用于原厂或恢复环境，不要把它当作 OpenWrt 日常 sysupgrade 镜像。

### 从 OpenWrt 命令行刷入

先将 `squashfs-sysupgrade.bin` 上传到 `/tmp`，然后执行：

```sh
# 默认尽量保留 /etc/config 等配置
sysupgrade /tmp/openwrt-ramips-mt7621-netgear_r6800-squashfs-sysupgrade.bin
```

不保留配置：

```sh
sysupgrade -n /tmp/openwrt-ramips-mt7621-netgear_r6800-squashfs-sysupgrade.bin
```

### 首次从其他布局迁移

- **旧 40 MiB 官方布局：**先执行一次 `sysupgrade -n`。进入新系统并确认实际为 64 MiB 后，若 overlay 仍是旧容量，再执行一次同一镜像的 `sysupgrade -n`，让数据卷在 64 MiB 几何下重建。
- **旧 76 MiB 自定义布局：不要直接普通 sysupgrade。**旧系统可能按 76 MiB 重建数据卷，超过新 64 MiB MTD。应从恢复环境启动本项目 initramfs，确认 64 MiB 分区已生效后，再使用 factory/sysupgrade 镜像执行不保留配置的刷写。
- **已经是本项目 64 MiB：**网页或命令行普通 sysupgrade 可尝试保留配置；`sysupgrade -n` 则不保留。

本项目不会改写 SC PART_MAP。`sysupgrade -n` 只负责清除配置和重建可写数据区，也不能修复 Factory。刷写过程中不要断电。若当前系统已出现 Factory/随机 MAC/6 dBm 问题，应先备份并解决校准数据，不要期望单纯刷机自动修复。

## 刷后检查

```sh
cat /proc/mtd
ubinfo -a
df -h
dmesg | grep -Ei 'scpart|sercomm|mt7615|mt76|eeprom|MAC address'
iw reg get
iw phy
opkg list-installed | grep -E 'easytier|passwall|openvpn'
```

刷后必须确认 `/proc/mtd` 中 UBI 为 `0x04000000`，Factory 仍为 `0x00200000`；同时读取对应 `/sys/class/mtd/mtdX/offset`，Factory 偏移应为十进制 `73400320`（`0x4600000`）。内核日志应出现类似 `scpart: ID 3 size 0x2800000 -> 0x4000000`。如果 UBI 仍为 40 MiB、Factory 位置异常或仍有随机 MAC，请停止继续写入并恢复备份。

无线默认不预置国家和 SSID，也不强制开启射频。请在 LuCI 中按实际所在国家/地区配置。测试 160MHz 前，先确认 Factory 正常、无线功率不再全部限制为 6 dBm，并先用 VHT80 建立稳定性基线。

## 构建文件

- `config/r6800.config`：目标与软件包种子配置；
- `scripts/apply-r6800-64mib.py`：修改官方 DTSI 和镜像大小；
- `scripts/validate-r6800.py`：检查分区、配置、manifest、镜像和最终 DTB；
- `patches/easytier/`：为 MIPS EasyTier 核心下载增加 SHA256 校验；
- `.github/workflows/build.yml`：可复现的 GitHub Actions 构建。
