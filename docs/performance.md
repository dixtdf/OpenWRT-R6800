# R6800 性能调优与实测上限

本文记录本固件为“把 MT7621 拉满”所做的所有改动、实测数据，以及**做不到的部分**和原因。

## 1. 先说结论

| 场景 | 上限 | 原因 |
| --- | --- | --- |
| **LAN ↔ LAN（两台有线设备互传）** | **~940 Mbps（线速）** | MT7530 交换机硬件转发，不经过 CPU |
| LAN → WAN / WAN → LAN（NAT 转发） | **800–940 Mbps** | 软件 flow offloading；MT7621 没有主线硬件 NAT 驱动 |
| PC ↔ 路由器自身（iperf3 / SMB） | **~470–650 Mbps** | `mtk_eth_soc` 只有 1 个 RX 队列，收包靠单核 NAPI + 逐包 cache 维护 |
| 5 GHz Wi-Fi | ~350–380 Mbps | mt7615 AP + 2x2 客户端，约为协商速率的 40% |
| 2.4 GHz Wi-Fi | ~75–120 Mbps | HT20/HT40，受同频干扰限制 |

> 用 iperf3 打 `192.168.1.1` 得到的数字**不代表局域网速度**，它测的是路由器 CPU 的处理能力。真正的局域网文件传输走交换机，和这个数字无关。

## 2. 本固件包含的性能改动

1. **内核内置 BBR**（`CONFIG_TCP_CONG_BBR=y`，默认拥塞控制改为 `bbr`）
   - 对 Wi-Fi 这类有随机丢包的链路比 cubic 更稳（实测有提升，波动更小）。
2. **sysctl 调优**（`/etc/sysctl.d/10-r6800-perf.conf`）
   - `netdev_budget=1000`、`dev_weight=128`、`netdev_max_backlog=2000`
   - TCP 窗口上限 4 MiB，`tcp_slow_start_after_idle=0`，`tcp_mtu_probing=1`，TFO
3. **默认开启软件 flow offloading**（`firewall.flow_offloading=1`）
   - 只加速 **转发** 流量；打到路由器自身的流量不受影响。
   - **与 SQM/QoS 冲突**：启用 SQM 前执行 `r6800-perf sqm`。
4. **irqbalance**：把网卡/PHY 中断从 CPU0（timer 所在核）分散开。
5. **packet steering**（RPS）保持开启，4 核分担 softirq。
6. **iperf3 + ethtool** 预装，方便在设备上直接复测。
7. **country=CN**（仅在未设置时写入）：解锁 5 GHz 149–165 信道，5G 可到 31 dBm。

运行时可用：

```sh
r6800-perf status   # 查看当前状态
r6800-perf max      # 开启 flow offloading + BBR + sysctl
r6800-perf sqm      # 关闭 flow offloading（用 SQM 时）
```

## 3. 已经试过但没有收益的项（避免重复折腾）

在真机上逐项测试，均在 ±3% 以内，已全部还原：

- RPS 掩码从单核改为 4 核（`rps_cpus=0xf`）+ `rps_flow_cnt=4096`
- `net.core.rmem_max/wmem_max` 放大到 16 MiB
- GRO 关闭 / `rx-gro-list` 关闭 / `rx-udp-gro-forwarding` 开启
- 以太网 IRQ 亲和从 CPU0 移到 CPU1
- `taskset` 绑定 `napi/mtk_eth-5/-6` 到不同核心
- `echo 1 > /sys/class/net/eth0/threaded`（驱动不支持）
- 巨型帧 9000：`eth0 maxmtu=2030`，硬件不支持
- 关闭 Wi-Fi / 卸载 mt76 模块：对有线无影响

## 4. 为什么不再高

- **单 RX 队列**：`ethtool -S`/`ip -d link` 显示 `numrxqueues 1`，所有收包只能在一个 NAPI 上处理。
- **无硬件 NAT**：主线 OpenWrt 没有 MT7621 的 HNAT/PPE 驱动（`lsmod` 无 `mtk_hnat`），只有软件 flow offloading。
- **固定 880 MHz、无 cpufreq/thermal zone**：无法超频或调频。
- **RGMII 1 Gbps**：CPU 口和交换机之间就是 1 Gbps。

## 5. 如果想继续突破

唯一现实路径是移植 MediaTek SDK 的厂商以太网驱动（多队列 RX + HNAT），这需要：

1. 用厂商 `mt7621-vendor` 驱动替换主线 `mtk_eth_soc`；
2. 用厂商 `mt753x` + swconfig 替换 DSA，重写 R6800 的 DTS；
3. 重新验证 64 MiB 分区布局与 factory 保护。

这与“确保稳定性”直接冲突：它是非主线、无上游维护的整套替换，且收益主要落在转发而非本机吞吐。本固件因此保留主线驱动，只做可验证、可回退的调优。

## 6. 如何验证

两台有线设备（例如 PC 与 NAS）接到 LAN 口，互跑：

```sh
iperf3 -s          # 一台
iperf3 -c <ip> -P 4 -t 30
```

应得到 ~900 Mbps 以上，且路由器 CPU 基本空闲——这才说明局域网是满速的。
