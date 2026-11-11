# R6800 无线校准（Factory）丢失与恢复

## 现象

```
mt7615e 0000:01:00.0: Invalid MAC address, using random address aa:49:59:11:fe:a1
iw dev: txpower 6.00 dBm
iwinfo phy0-ap0: Tx-Power: 6 dBm
```

`iw phy` 的每个信道都显示 `(6.0 dBm)`，`txpowerlist` 最大值也是 6 dBm，即使 `uci txpower=20` 也无效。

## 根因

R6800 的 MT7615 校准数据位于 **factory 分区**（原厂 mtd6，2 MiB）：

```
0x0000  MT7615 eeprom slot 0（2.4GHz）
0x8000  MT7615 eeprom slot 1（5GHz）
```

原厂机（factory 完好）的两个 slot 开头均为 `15 76 a0 00 ...`，无线 MAC 取自 eeprom：

```
ra0   00:0C:43:28:05:00
rai0  00:0C:43:28:05:E8
```

而本机（OpenWrt）的 factory 分区开头是 `55 42 49 23`（`"UBI#"`），说明**旧布局的 76 MiB UBI 覆盖了整个 factory 区**（0x00600000 + 0x04C00000 = 0x05200000，与 factory 0x04600000 重叠 2 MiB）。

驱动读不到有效 eeprom，回退默认：随机 MAC + 6 dBm 功率表。

## 影响

- 2.4G/5G 发射功率只有 6 dBm（约 4 mW），穿墙与远距离稳定性明显不足；
- 无线 MAC 每次启动随机变化；
- 与驱动无关：原厂 `mt_7615e`（MTK SDK）与 OpenWrt 的 `mt76` 都读同一份 factory，换驱动不能解决。

## 恢复步骤

1. **先刷 64 MiB 布局固件**（本仓库产物），使 UBI 结束于 0x04600000，不再覆盖 factory；
2. 准备一份有效 eeprom 镜像（两 slot，2 MiB），并将 slot0/slot1 的 MAC 改为本机可用地址：
   ```
   slot0 (2.4G) offset 0x0004 : 6 字节 MAC
   slot1 (5G)   offset 0x8004 : 6 字节 MAC
   ```
3. 解除 factory 只读（`kmod-mtd-rw`，本仓库固件已内置）：
   ```
   insmod mtd-rw i_want_a_brick=1
   ```
4. 备份并写入：
   ```
   r6800-factory dump /root/factory-before.bin
   r6800-factory write /root/factory-new.bin
   ```
5. 重启，验证：
   ```
   r6800-factory verify        # 期望 txpower ≈ 20 dBm，MAC 固定
   iw dev | grep -e ssid -e channel -e txpower
   ```

## 风险与合规

- eeprom 中的功率/频偏校准是**逐台**的，跨机使用不保证射频指标合规；仅在本机校准已彻底丢失时作为恢复手段。
- 写入前必须备份当前 factory（即使已是 UBI 垃圾），以便回滚。
- 若写入后无线异常，可写回备份并重启。

## 构建器相关改动

- `config/r6800.config` 增加 `CONFIG_PACKAGE_kmod-mtd-rw=y` 与 `CONFIG_PACKAGE_mtd-utils=y`；
- 新增 `files/usr/sbin/r6800-factory`（verify / dump / write）；
- CI 将 `files/` 覆盖进 rootfs，并将 sysupgrade 镜像发布到 Release。