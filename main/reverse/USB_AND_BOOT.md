# USB、下载与恢复

## 工作态接口

本机 EC600U 工作态 VID/PID=`2c7c:0901`。Windows 端按 VID/PID+interface 标识查端口，COM 数字会变，不能固定 COM5/COM8。当多个同款设备接入时还需按设备实例/物理拓扑区分；当前 demo 的多设备能力尚未验证。

| Interface | 本机用途 | 说明 |
|---|---|---|
| MI_02 | AT | AT 命令/进入下载状态；旧机曾分配 COM8 |
| MI_20 | QuecPython/native 数据 VCOM | 当前 QDC1 数据流；旧机曾分配 COM5 |
| MI_03 | 诊断 Diag | 不承载 QDC1 |
| MI_04 | MOS | 历史调试研究 |
| MI_05 / MI_06 | CP/AP 日志 | 不是帧传输口 |
| MI_07 | Modem | 与显示数据无关 |
| MI_00 / MI_01 | ECM 相关 | 不同固件描述符可能有变化；本项目不靠蜂窝联网传屏 |

USB 虚拟 COM 调用不是接到一个 115200 bit/s 的实体 UART：baud 参数不能等同于 USB 吞吐。但 USB 2.0 标称 480 Mbit/s 也不能证明本芯片、端点、驱动和任务都能持续跑满。数据传输使用二进制，可独立测 RX、内存复制和 LCD 分别占多少时间。

R03 `Helios_UART3` 映射到内部 VCOM channel **5**；立即发送导入 `ql_uart_write(5,bytes,count)`，避免平台 UART writer 的 1 KiB 定时 Python-console 缓冲。接收使用核心流对象：`0x6020bca1(5)` 返回 channel；对象第4个 u32 是 read 指针，调用前检查对象位于 `0x80980000..0x80ffffff−64`、read 为合法 Thumb AP 指针。channel lock/unlock 指针 `0x6020b4b5` / `0x6020b519`，参数5。只能在完全匹配 R03 中使用，且应用独占 reader、不在任务运行中关闭 channel。通用 `ql_uart_read` 会先清整个请求缓冲，造成大量额外写；这个优化避免该清零。

## 下载状态与 wire format

已成功使用 AT `AT+QDOWNLOAD=1` 进入 RAM 下载；下载态 VID/PID=`0525:a4a7`。PDL/FDL wire 数据的字段和应用 QDC1 不同，不要混用。

FDL 的 BSL frame：`7e | escape(type:u16BE, size:u16BE, payload, checksum:u16) | 7e`；内部 `7e`、`7d` 转 `7d,(byte^20)`。BootROM 与 FDL 的校验模式不同，BootROM CRC16、FDL 16位 one's-complement sum，PDL 握手也独立实现。完整可复核协议实现保留在 [sprdflash](../demo/third_party/sprdflash/protocol.py) 和其 `pdl.py`，MIT 许可；不是把原厂 loader 本体开源。

当前成功 R03 loader 固定身份：

| 文件 | SHA-256 | RAM 装载地址 |
|---|---|---|
| HOST_FDL_fdl1.sign.img | `cfad226ef5d892ee24609e0e3104109d459cd1daf3206357e698a1253ef67968` | `0x008000c0` |
| FDL2_fdl2.sign.img | `61ba99f74ea0614fd5996064670dc1caa705ef044a8acc919a8872557a38309a` | `0x00810000` |

流程：PDL connect→装载FDL1→执行→BSL/SPRD校验connect→装载FDL2→EXEC_DATA→connect。R03 READ_FLASH payload 为 `struct.pack('>III', absolute_address, count, 0)`，回复 type=`0x93`；4 KiB 每块。此 loader 对物理 NOR 忽略第三个字段，必须递增**绝对地址**，否则重复读第一个块。READ_FLASH 命令=`0x06`，NORMAL_RESET=`0x05`，START/MIDST/END_DATA=`1/2/3`、EXEC_DATA=`4`。当前 APP 更新不调用 ERASE_FLASH=`0x0a`、格式化或修改 NV。

## APP 更新和原厂恢复不是一回事

APP2 容器长度从头部 u32@4 读出，必须等于文件实际长度并≤`0xe0000`。偏移32..127每16字节为四u32 `(kind,offset,size,address)`；kind1/2/3为 APP RAM 装载/清零相关、kind4为 APP Flash；任何 address/size 必须在对应所有权范围中，非kind3的文件切片必须在容器内。不能把该 BIN 刷成从地址0开始的裸镜像。

当前工具读核心AP并核对固定SHA，双读APP旧区验证，才发送新APP到 `0x60260000`，随后逐字节读回比较并 reset。核心/loader指纹不符就停止写。只支持上述 R03 核心上更新 APP，**不能直接用于原厂R05板子首次转换**。

上面描述的是维护者旧脚本 `deploy_native_app.py`。新的一键入口和 `setup/qflash.py` 已另外编排 R05 首次转换、R03 APP 更新及本机完整内部备份/恢复；它在写入前双读整个内部 8 MiB，并显示阶段、错误及可选日志。新用户从[一键刷写说明](../demo/SETUP.md)进入，不必手工找 AT 口或安装 Python。尚未用新入口在第二台原厂板完成首次转换实测，不能用模拟测试替代这项验证。

原厂恢复使用自己的完整内部双读备份，包含产品核心/APP/校准等，恢复布局及证据保留在本地 `private/backups/factory_restore/`、`private/backups/internal/`；旧恢复工具在 `junk/archive/scripts/restore_lakala_factory_20261008.py`。换一台设备时不要拿这台的 NV/IMEI/整机 dump 当通用 ROM。首次从原厂转 R03 需要合法来源的匹配官方 PAC、保存新设备本身备份、核对布局；本 demo 不打包完整官方核心/PAC。外部16MiB没有全片备份，原厂内部恢复不能证明外部也已完整恢复。
