# 一键刷写和基础使用

新用户下载 [一键入口 Release](https://github.com/StevenLang233/lakala-display-re/releases/tag/setup-v1.0.0) 的 **QDisplay-Setup-1.0.0.zip**，解压到自己有写权限的文件夹，双击根目录的 **一键刷机.bat**。不要在压缩包预览窗口里直接运行。

入口适用于 **Windows 10/11 x64** 和本文档对应的 **EC600U-CNLB 拉卡拉客显屏**。初次准备需要联网；固件和上位机已放在包内，官方核心、刷写环境、需要的驱动从锁定来源获取。源码 ZIP 也能运行同一个 BAT，但需要另外取得 Release 附件；私有仓库的附件先在登录后的浏览器下载，放进项目根目录的 `offline/`，脚本不会索要 GitHub Token。

## 怎么用

1. 用 USB **数据线**接入一台客显屏，保持供电。暂时只连接这一台待刷设备。
2. 双击 `一键刷机.bat`。入口先检查设备状态、准备独立刷写环境并校验文件。
3. 选 **1：刷写 QDisplay 并安装/打开上位机**。核对设备和核心版本，确认刷写时输入 `y`。默认不刷。
4. Windows 需要安装驱动、注册服务时会出现 UAC。依次等待备份、写入、读回核对和重启完成。
5. 上位机自动打开，入口显示实际连接结果。先选**硬件信息**或**相框**检查基础使用；初次音频默认关闭。
6. 需要 Windows 扩展副屏时，同意安装虚拟屏驱动，再在上位机选择**副屏**。默认准备 800×1280、30/60 Hz 配置。不是把画面预览到上位机窗口，也没有改已有采集/传图逻辑。
7. 结束时，无论成功、失败或取消，都会问是否导出日志。输入 `y` 后在项目根目录生成 `QDisplay-log-时间.zip`。

正常关闭上位机窗口进入托盘；完整退出使用托盘菜单。离开副屏模式时，上位机会撤销虚拟屏连接。配置、USB 重连恢复、滚动图表和音量行为沿用现有 Demo，不在安装入口中重写。

菜单还有 **2：只安装/打开上位机**、**3：只备份内部 Flash**、**4：恢复本机备份**、**0：退出**。仅备份也会短暂进入下载并重启，所以会先确认。只安装上位机时，即使板卡不在，也能完成软件安装；此时明确显示“设备连接尚未确认”，退出码为 3。

## 入口实际做什么

| 阶段 | 行为及成功条件 |
|---|---|
| 环境 | 项目 `.qdisplay/` 内的 Python 3.13.16 + pyserial 3.5；不装全局 pip、不改变 PATH。Python仅用于刷写，日常上位机仍是 C# GUI/服务 |
| 设备 | 按 VID/PID 与 MI_02/MI_20 确认 AT/数据口，按 `0525:a4a7` 识别下载口；拒绝多台设备，不用 COM 编号猜接口 |
| 依赖 | 下载与缓存都核对 SHA-256；PAC 校验 CRC、loader 指纹和关键地址，APP 校验 APP2 长度与描述符范围 |
| 驱动 | 只装签名通过的 `qcser.inf`、`unisoc_iot.inf`。下载口通常使用 Windows 自带驱动；若进入下载后未生成 COM，先补 `rdavcom.inf` 再尝试一次。不会运行厂商整包 `setup.exe`、安装复合过滤组件或调整安全设置 |
| 确认 | 正常模式先只读查 `ATI`。仅接受已核对的原厂 R05 或指定 R03。实际写入前再次从 Flash 验证核心 |
| 备份 | 每次写入前完整读取内部 8 MiB 两遍并逐字节比较；一致才生成 `backup.json` 与正式 BIN。不把未完成的 `.partial` 当有效备份 |
| 原厂 R05 首次转换 | 使用指定官方内置 Flash 版 PAC，写 AP/APPIMG/PS/boot，按 PAC 重建内部文件系统及运行 NV；先启动官方 R03，再更新 QDisplay APP。不使用 EXTFS8M 包 |
| 已有 R03 更新 | 仅更新 `0x60260000` 的 QDisplay APP，不格式化或改写其他分区 |
| 核对 | 每个物理写入区读回比对；NV END 返回错误立即停止。QDisplay 更新后必须收到校验正确的 QDC1 HELLO |
| 软件 | 必要时补 .NET Framework 4.8，安装 MSI/自动服务，在当前用户会话启动 GUI；通过服务进程身份核对状态管道，再检查 Connected |
| 异常 | 给出阶段和错误码；写入未完成不强制重启到残缺固件。没有把“下载成功”“写完”或“服务启动”单独当作整套联动成功 |

核心来源是 [移远官方内置版 V0004](https://developer.quectel.com/wp-content/uploads/2024/09/QPY_OCPU_V0004_EC600U_CNLB_FW.zip)，不是本项目声称拥有的完整系统。原始 ZIP 与其中 PAC 分别锁定为 `8182d7b6…3ab510`、`a85f766d…47ebc8`。完整指纹和所有下载地址在 [dependencies.lock.json](setup/dependencies.lock.json)，不能删除校验来使用其他固件。官方[烧录说明](https://python.quectel.com/doc/quecpython/Getting_started/zh/4G/flash_firmware.html)可用于核对模块版本和下载来源。

## 备份与恢复

备份保存在 `.qdisplay/backups/时间/`。这个目录默认不进入 Git，也不会随诊断日志导出。里面含设备自己的 NV/校准等数据，应独立保存；**外部 16 MiB Flash 没有全片备份**，这里的“完整”只指内部 8 MiB。

失败后先看错误阶段。如果 Flash 未写入，设备可以按提示重试；若写入中断，保留 USB 连接和下载状态。菜单 4 可以选择本入口生成的有效本机备份，恢复前也会双读保存当前内部状态，按变化的 64 KiB 区域恢复，boot 最后写，并核对整个 8 MiB。

下载口没有可依赖的唯一板卡身份，软件不能证明同款板卡到底是哪一台。恢复必须由使用者明确确认“备份属于当前设备”；不能拿作者或其他买家的整机 dump/NV 来刷。恢复原厂 R05 后，原厂界面不会与 QDisplay 上位机联动；需要继续使用 Demo 时重新选菜单 1。

如果设备在写入中断后已经掉电，又完全没有枚举 AT/下载口，软件入口无法凭空控制未连接的 USB 设备；需要先按已确认的板卡下载接入办法使下载口出现。本文不编造未核实的短接点。下载入口及原厂恢复的逆向资料见 [USB、下载与恢复](../reverse/USB_AND_BOOT.md)。

## 看进度与处理报错

下载、两遍备份、FDL 装载、各分区写入/读回会显示阶段和百分比；等待设备和系统安装也有状态提示。USB 后台长时间没有新进度会超时退出并保留资料。备份可能比日常传图慢，不能用传图帧率估算刷写耗时。

| 错误码 | 处理 |
|---|---|
| `NO_DEVICE` / `DATA_PORT_MISSING` | 检查数据线、USB 接口和设备管理器；必要的接口驱动会自动补齐。已写完 APP 但数据口缺驱动时只重新验证握手，不重复刷写 |
| `MULTIPLE_DEVICES` | 只留下待操作的一台客显屏 |
| `PORT_BUSY` / `AT_NO_RESPONSE` | 关闭 QPYcom、串口工具和其他刷写进程，不改其他设备的串口 |
| `HASH_MISMATCH` / `PAC_HASH` / `APP_HASH` | 文件损坏、版本不符或下载源变更；重新取得锁定原包，不能跳过校验 |
| `UNSUPPORTED_CORE` | 核心版本未核对；保留备份，停止写入 |
| `READBACK_MISMATCH` / `SHORT_READ` | USB 读取不完整或内容不一致；不报告成功，保留本机备份和失败日志 |
| `LOADER_REJECTED` / `USB_BOOT_TIMEOUT` / `HELLO_*` | 按失败阶段检查供电、接口和固件身份；写入未完成时不要盲目重启 |
| `UAC_CANCELLED` | 本次管理员步骤没做完；重新运行并允许所需 UAC |
| `REBOOT_REQUIRED` | 安装器要求重启；入口不会自动重启电脑，重启后再次运行 |

退出码：`0` 对应本次所选操作确认完成；`1` 失败；`2` 取消；`3` 软件已装但联动待确认；`3010` Windows 安装器要求重启。成功/失败的本地原始日志都保存在 `.qdisplay/logs/`；可选导出会排除固件备份、NV、配置和媒体，并替换项目/用户目录及 USB 实例路径。分享前仍可自行查看 ZIP 内文本。

## 离线准备与验证范围

离线用户可把 `dependencies.lock.json` 中相同版本的原包放进项目 `offline/`。脚本按原文件名及哈希使用它们，不扫描个人下载/桌面目录。全离线准备需要 Python ZIP、pyserial wheel、官方核心 ZIP、BIN/MSI/许可 ZIP；需要补 USB 驱动时还要官方 USB ZIP、7zr、ISx 包，需要副屏时准备 VDD ZIP，缺 .NET 4.8 时准备微软离线安装器。

维护者可运行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File main/demo/setup/setup.ps1 -CheckOnly -NoPrompt
powershell.exe -NoProfile -ExecutionPolicy Bypass -File main/demo/setup/setup.ps1 -PrepareOnly -NoPrompt
powershell.exe -NoProfile -ExecutionPolicy Bypass -File main/demo/setup/setup.ps1 -PrepareOnly -Offline -NoPrompt
.qdisplay/python-3.13.16/python.exe -m unittest discover -s main/demo/setup/tests -v
```

`CheckOnly` 只准备项目内刷写环境并枚举接口，不停止服务、安装系统驱动或进下载；`PrepareOnly` 下载/解包/校验依赖，不做系统安装或刷写。`NoPrompt` 只能与这两种模式一起使用，不能无提示刷写。

本次验证包括 Windows PowerShell 5.1、实机只读识别 R03/AT/数据口、现有服务身份与连接查询、依赖准备、拒绝刷写、日志导出，以及 22 项 USB/备份/校验/写入故障模拟。**新入口尚未在另一台原厂板上完成首次转换和全新系统安装实测**；首次转换依据已有实机成功记录编排，不能把故障模拟说成全流程硬件验证。

AIDA64 手机 LCD/Odospace 兼容仍未实现，放到后续。本次也不宣称解决旧的闪烁、撕裂或 Windows 音频采集问题。固件和上位机二进制保持 0.3.0 的原始字节。

刷写入口原创部分按仓库 CC BY-NC-SA 4.0；sprdflash、下载到的 Python/pyserial、7zr、ISx、微软/厂商驱动保留各自条款。详情见 [第三方来源](THIRD_PARTY.md)，不存在把这些依赖统一改成非商用许可的授权。
