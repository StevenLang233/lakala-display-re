# Lakala Display RE

拉卡拉客显屏音响逆向及 Demo。

这是个纯 **Vibe Coding / VibeRE** 项目。VibeRE 指 Vibe Reverse Engineering，也就是 AI 辅助逆向。

**作者的话**

> 我是个废物，但是废物也想给大家做点贡献，所以就选择了点燃token照亮大家的行为，希望大家可以用我抽ai生成出来的屎山代码做出很牛逼的项目！
>
> 我甚至废物到文档都是ai生成的，如果有人机味很重的话希望大家别骂我，因为我真的是纯废物呜呜呜呜呜呜呜TAT

折腾的是一台用 Quectel **EC600U-CN** 的拉卡拉客显屏音响。引脚、地址、显示、音频、USB 协议和编译方法都在下面，资料截至 **2026-10-09**。

实机测过的、从固件里分析出的、还不确定的内容，分别标成 **实机确认**、**静态逆向** 和 **候选／地址不确定**。屏幕闪烁、撕裂和电脑声音采集还没完全解决，具体看对应章节。

固件 BIN、Windows MSI 和运行文件包从 [GitHub Releases](https://github.com/StevenLang233/lakala-display-re/releases) 下载。参考实现源码在 [C 固件](main/demo/firmware/src) 与 [C# 上位机](main/demo/desktop/src)。

## 使用限制与商家授权声明

**本项目禁止商用，仅限个人使用。**

没给任何卖这个终端的商家授权。

> 本项目仅限个人使用，任何贩卖此终端的商家禁止使用，包括但不限于，告诉买家有这个项目可以刷，直接附带本项目链接等。如有发现，乐意的话可以向我举报，我会感激不尽。

这些限制针对本项目原创内容。第三方部分仍按各自许可证使用，见[第三方来源与许可](#第三方来源与许可)。

## 目录

- [使用限制与商家授权声明](#使用限制与商家授权声明)
- [板卡与信号映射](#板卡与信号映射)
- [内存、版本与 ABI](#内存版本与-abi)
- [R03 已解析导入表](#r03-已解析导入表)
- [主屏显示路径](#主屏显示路径)
- [原厂 R05 主屏初始化字节](#原厂-r05-主屏初始化字节)
- [喇叭、原厂增益与播放](#喇叭原厂增益与播放)
- [USB、下载与恢复](#usb下载与恢复)
- [QDC1 二进制协议](#qdc1-二进制协议)
- [地址不确定及待验证项](#地址不确定及待验证项)
- [证据与原始资料位置](#证据与原始资料位置)
- [QDisplay Demo](#qdisplay-demo)
- [重建与更新 Demo](#重建与更新-demo)
- [第三方来源与许可](#第三方来源与许可)
- [源码和安装包分别发布](#源码和安装包分别发布)
- [首个 Demo 版本说明](#首个-demo-版本说明)

## 板卡与信号映射

研究对象：拉卡拉屏显音响类设备，通信模组 Quectel **EC600U-CN**。原厂报告版本 `EC600UCNLBR05A01M08_OCPU_BETA1215`。当前原生 demo 的核心为 `EC600UCNLBR03A04M08_OCPU_QPY`。

主屏原生为 **800×1280、16 bpp、两条 MIPI 数据 lane**。柔性排线丝印 `H.101.001B02 V00` / `2023.02.17 SST`；背板丝印 `YBT 20230307 CHE-GI`、`H.101.001B02-20230307-HBS-A1`。照片在 [photos](main/reverse/evidence/photos)。初始化与 SC7705 路径相符，丝印本身不能证明内部驱动芯片型号。

### 编号空间

“物理脚”是 EC600U 模组焊盘编号，不是 FPC 接口针号。“公开 GPIO”是 QuecPython/Helios 的板级 API 编号；“QL GPIO”是核心内部 GPIO 编号；旧 Logicrom `GPIO_*` 又是另一套枚举。例：背光 **物理 118 = 公开 GPIO8 = 硬件 GPIO7**，喇叭 PA 的 **QL GPIO22** 不能写成 Python `Pin.GPIO22`。

| 功能/位置 | 模组物理脚 | 公开 GPIO / 其他编号 | 状态与证据 |
|---|---|---|---|
| 主屏背光使能 | **118** | **GPIO8；硬件 GPIO7** | 实机调亮/调暗成功；原厂 MIPI 任务亦初始化此脚 |
| 主屏辅助控制 | **53** | **GPIO27** | 原厂/原生初始化配置输出低；未独立证实该脚是 reset 还是电源控制，勿另取功能名 |
| 后部右上 `+` | **99** | **GPIO47** | 已用于调亮度；低有效、上拉输入 |
| 后部右下 `−` | **13** | **GPIO46** | 已用于调亮度；低有效、上拉输入 |
| 后部左下“菜单” | **14** | **GPIO44** | 长按待机/唤醒和实机反馈；低有效、上拉输入 |
| 后部左上“查询” | **地址/脚号不确定** | 旧记录曾试 `misc.PowerKey`，不能视为确认映射 | 排线故障可能影响验证；当前固件不猜 GPIO |
| 印刷/段码小液晶屏 | **地址/连线不确定** | FG00 候选：SCK 57/GPIO15、SDA 56/GPIO16、RST 52/GPIO28、EN 4/GPIO11 | 仅静态逆向候选；见 [UNCERTAIN](#地址不确定及待验证项) |
| RGB 灯的三个通道 | **33 / 12 / 54** | **GPIO18 / GPIO17 / GPIO14** | 历史代码及原厂路径记录；颜色次序/极性需独立核验，当前 demo 不靠它判断状态 |
| 喇叭 PA 使能 | 模组物理脚未单独确认 | **QL pinmux 15 / function 4；QL GPIO22** | 从原厂 `0x602a43e4`、`0x602a4324` 恢复；加入后喇叭和低音量调节实机成功 |
| 主屏 MIPI 引脚组 | 本研究未测出板级 FPC 针号 | 数据 lane=2；连接由模组 MIPI 硬件控制 | 使用官方模组手册/实际 PCB 连通测量，不将 GPIO11 当成 MIPI 专用脚 |
| 硬件 PWM0 | **70** | 与本板背光 GPIO8 无同一连线证明 | 未用于当前背光；GPIO8 采用软件定时 PWM |

### 背光及按键行为

当前 R03 通过 GPIO7 原子置位寄存器 `0x50107010`、清零寄存器 `0x50107014` 的 bit 7 控制背光；仅对匹配核心使用。`100%` 常亮 DC，`5%..95%` 用 1 kHz 定时器 PWM，高电平时长 `亮度×10 µs`、低电平时长 `(100−亮度)×10 µs`。软件边沿计数已验证，未用示波器量出实际占空比/光输出。

R03 单次微秒定时启动指针 `0x601c621f`、停止指针 `0x601c62e5`（均为 Thumb 指针）；`osiTimerCreate` 从核心导入。ISR 只切换已知脚，不分配内存、不渲染、不忙等。

当前按键消抖 40 ms；`+ / −` 步进 5%，保持 400 ms 后每 120 ms 重复。亮度范围 5..100%；即使已在上下限，按键仍显示亮度条。菜单按住 2 s 切待机/唤醒；待机是背光关闭和应用状态变化，**不是整机断电**，USB 保持运行。亮度条释放后 1.8 s 消失。小屏/查询键未启用。

### 存储

内部 NOR **8 MiB**，已对 `0x60000000..0x607fffff` 独立双读并比较。原厂整机 SHA-256：`3984567d4d7a1c892fd408dfc0feafa965586cf629818e768f9d60f0bfe8b9f9`。外部 Flash 记录为 **16 MiB**，尚无完整 16 MiB 原始备份；外部文件系统导出不能冒充物理 Flash dump。

外部 Flash 是存储容量，不能直接作为 LCD 扫描缓冲 RAM。当前 APP 的 RAM 区只有 1 MiB，屏幕扫描缓冲由核心分配；同一堆再分配第二张 2,048,000 字节帧缓冲会失败。相册文件保存和副屏帧缓冲是两类资源。


## 内存、版本与 ABI

### 镜像身份和地址换算

| 来源 | 版本/指纹 | 用途 |
|---|---|---|
| 原厂内部 NOR 双读 | R05 BETA1215；整机 SHA `3984567d4d7a1c892fd408dfc0feafa965586cf629818e768f9d60f0bfe8b9f9` | 产品显示任务、FG00、按键、PA、工厂音量逆向 |
| 当前核心 AP | R03A04M08；AP SHA `187abb282fd089e6c3fb9d8bb75b837826b1a726e943fe961e5bf052da433ca9` | 当前 demo 的所有绝对核心地址 |
| Helios SDK | 固定 commit `de3b7eb84c4523957ab21a3a0488d9246fe5e361` | 命名导入 stub、声明及链接脚本；SDK 核心为 R01，不能直接照抄枚举/ABI |

完整内部 dump 的 `文件偏移 = NOR 地址 − 0x60000000`；裁切 region 则减去该 region 的 base。原厂 APP 所在裁切文件的 base 为 `0x60230000`，所以 `0x602a43e4` 位于该 region 文件偏移 `0x743e4`。反汇编表中的偶数地址是指令地址；在 Thumb 下作为函数指针调用要置 bit 0。数据指针和 MMIO 不能置 bit 0。

原厂结构划分来自 PAC 参考布局和 dump 结构识别，**不代表当前 R03 分区表**：

| 原厂 R05 范围 | 长度 | 识别/限制 |
|---|---|---|
| `0x60000000` | `0x10000` | Bootloader，uImage 校验记录可复核 |
| `0x60010000` | `0x220000` | AP 参考区域，含 uImage |
| `0x60230000` | `0x270000` | 原参考布局间隙，里面实际存在 APP/资源；`gap_filesystem_candidate` 是旧分类名，不是整个区都为 FS |
| `0x604a0000` | `0x340000` | PS 参考区域 |
| `0x607e0000` | `0x20000` | 顶部 NV/工厂候选，不擅自重新分区 |

结构、各 region SHA 及基址见 [structure.json](main/reverse/evidence/r05/structure.json)。

### 当前 R03 应用所有权

| 项 | 地址/长度 |
|---|---|
| 核心 AP 映射起点 | `0x60010000` |
| APPIMG Flash 区 | `0x60260000`，长度 `0x000e0000`（896 KiB） |
| APP RAM 区 | `0x80f00000..0x80ffffff`（1 MiB） |
| LCD 核心扫描指针的全局变量 | `0x809dd390`，内容为缓冲地址 |
| LCD 宽高全局变量 | `0x809dd37c` 起两个 u32，应为 800、1280 |
| 合法扫描缓冲约束 | 四字节对齐、地址 ≥`0x809e0000` 且 ≤`0x80f00000−2048000` |

APPIMG 为 `APP2` 容器，magic `0x41505032`；开头 128 字节含装载描述符。`qdisplay_native.bin` 保留容器字节，**不是**从 `0x60000000` 起的完整固件。编译指令为 Cortex-A5、Thumb、NEON-VFPv4 hard-float；主程序限制未对齐访问；LZ4 的 RAM 快路径需 SCTLR.A=0。内核是否保存 NEON 状态尚无充分证据，因此当前帧复制只用通用寄存器。

当前独立 APPIMG 导出入口为 `int appimg_enter(void *arg)`、退出符号为 `void appimg_exit(void)`，由 SDK 的 Unisoc linker script/mkappimg 保留入口，不通过 Python `main.py` 启动。入口仅创建任务并返回，不能在核心调用入口的线程无限循环。当前接收任务属性为名称 `qd-usb`、栈 8192、优先级105，应用建立自己的接收/渲染队列；这是 demo 的任务分配，不是模组固定限制。官方SDK高层 sample 的 `application_init` 宏属于另一层封装，使用它时须同时保留上游启动包装，不能混用两种入口。

### 导入绑定

SDK 的 `.text.core_stub.<name>` 包含 `df f8 00 f0` 和 4 字节导入哈希。应用最终 `.corestub` 留下所需 stub；在固定 AP 中搜索该 4 字节，取后续 little-endian u32，要求唯一匹配、目标 bit0=1、目标在 `0x60010000..0x6025ffff`。这是现有导入审计方法，不把扫描任意固件得到的偶然字节匹配当成通用 resolver。

全部已使用导入列在 [IMPORTS_R03.md](#r03-已解析导入表) / [imports.json](main/reverse/evidence/r03/imports.json)，函数声明见 [SDK ABI 快照](main/reverse/evidence/abi)。自写程序应保留 SDK 链接/启动流程，再绑定命名 stub；对内部定时器、USB 流对象、LCD 变量等未公开地址，加完整核心指纹门禁。

SDK GPIO 配置里的 enum 字段不能直接传给本 R03：R03 `Helios_GPIO_Init` 实际读取三个 **u8**：`direction, pull, initial_level`。使用三字节布局；相关枚举数值从对应声明取，不拿 R01 大结构按猜测传入。

R03 MIPI 结构的重要字段偏移（32 位 ARM，常规四字节对齐）：`init_data=0`、`init_data_len=4`、`width=8`、`hight=12`、`bpp=u16@16`、`lcd_interface=u16@18`、`data_lane=u8@20`、`mipi_mode@21`、`pixel_format@22`、`dsi_format@23`、`trans_mode@24`、`rgb_order@25`、`bllp_enable@26`、水平 sync/back/front `u32@28/32/36`、垂直 sync/back/front `u32@40/44/48`、`frame_rate@52`、`te_sel@53`、`rst_Polarity@54`、`dsi_pclk_rate=u32@56`，结构总长 60 字节。使用前以编译器 offsetof/static_assert 和 ABI 证据复核。


## R03 已解析导入表

AP SHA-256：`187abb282fd089e6c3fb9d8bb75b837826b1a726e943fe961e5bf052da433ca9`。仅适用于此核心。

表中目标是可调用的 Thumb 指针，已含 bit 0。哈希是 SDK stub 中原样的 4 字节，不是函数名的 SHA-256。

| 名称 | 哈希字节 | AP 文件偏移 | Thumb 目标 |
|---|---|---|---|
| `Helios_Audio_FilePlayStart` | `1b3b5945` | `0x6670c` | `0x6013cce9` |
| `Helios_Audio_FilePlayStop` | `37a97933` | `0x66444` | `0x6013cd09` |
| `Helios_Audio_GetVolume` | `6a439b9d` | `0x6732c` | `0x6013d4dd` |
| `Helios_Audio_Init` | `545aad64` | `0x66c14` | `0x6013cbb9` |
| `Helios_Audio_SetAudioChannle` | `b968cb86` | `0x67024` | `0x6013cc6b` |
| `Helios_Audio_SetPaCallback` | `d28eba61` | `0x66b64` | `0x6013d58d` |
| `Helios_Audio_SetVolume` | `64360235` | `0x66484` | `0x6013d4cd` |
| `Helios_Audio_StreamPlayStart` | `697cefe7` | `0x67dfc` | `0x6013cd25` |
| `Helios_Audio_StreamPlayStop` | `e069fd88` | `0x67074` | `0x6013ce01` |
| `Helios_Critical_Enter` | `fe6abb0d` | `0x65ef4` | `0x60147351` |
| `Helios_Critical_Exit` | `8e032f5c` | `0x66a64` | `0x60147355` |
| `Helios_GPIO_GetDirection` | `64886a58` | `0x669b4` | `0x60144d81` |
| `Helios_GPIO_GetLevel` | `b317a6b2` | `0x67684` | `0x60144d11` |
| `Helios_GPIO_Init` | `83fc8e1c` | `0x66134` | `0x60144b3d` |
| `Helios_GetAvailableMemorySize` | `ef2563b7` | `0x6773c` | `0x60147331` |
| `Helios_LCD_MIPIInit` | `ca6846df` | `0x67c84` | `0x60145f19` |
| `Helios_MsgQ_Create` | `49354ac6` | `0x67964` | `0x6014722f` |
| `Helios_MsgQ_Get` | `3596c41e` | `0x66174` | `0x60147245` |
| `Helios_MsgQ_Put` | `853b9ec0` | `0x678a4` | `0x60147233` |
| `Helios_Semaphore_Acquire` | `a3ab6a16` | `0x6603c` | `0x601471f5` |
| `Helios_Semaphore_Create` | `d697c570` | `0x66d74` | `0x601471f1` |
| `Helios_Semaphore_Release` | `bc04f25f` | `0x66ae4` | `0x60147205` |
| `Helios_Thread_Create` | `a63fe9e6` | `0x67dbc` | `0x60147185` |
| `Helios_Thread_Exit` | `e1b8827f` | `0x66f3c` | `0x601471d1` |
| `Helios_UART_Init` | `42881b64` | `0x66bdc` | `0x60149a15` |
| `Helios_UART_Read` | `009a38fd` | `0x6810c` | `0x60149c31` |
| `Helios_fclose` | `e1b01271` | `0x66d84` | `0x60143ef9` |
| `Helios_fopen` | `7a4f1e89` | `0x6707c` | `0x60143e89` |
| `Helios_fread` | `fcde96e6` | `0x67d8c` | `0x60143ee5` |
| `Helios_frename` | `8277f442` | `0x666c4` | `0x60143e1d` |
| `Helios_fs_free_size` | `a206361e` | `0x66164` | `0x60143f01` |
| `Helios_fsize` | `67259075` | `0x66dec` | `0x60143efd` |
| `Helios_fwrite` | `de0638ea` | `0x67e64` | `0x60143ee1` |
| `Helios_msleep` | `1a2f5d6a` | `0x66cac` | `0x6014732d` |
| `Helios_remove` | `2701a989` | `0x670a4` | `0x60143eb1` |
| `free` | `fad595ad` | `0x675bc` | `0x601c5865` |
| `malloc` | `bf2ec5e3` | `0x67d1c` | `0x601c5719` |
| `osiTimerCreate` | `17ad0bca` | `0x679ac` | `0x601c6085` |
| `osiUpTimeUS` | `b7470176` | `0x66dfc` | `0x60157247` |
| `ql_aud_get_icvolume_level_gain` | `e8fdf63d` | `0x665cc` | `0x601e2eb1` |
| `ql_aud_get_output_type` | `b92c020c` | `0x65ebc` | `0x601dfb45` |
| `ql_aud_get_pa_type` | `f92bfa5a` | `0x66a34` | `0x601df7d9` |
| `ql_aud_get_play_state` | `ea52d0c1` | `0x678bc` | `0x601dfc51` |
| `ql_aud_set_icvolume_level_gain` | `fc9ae48b` | `0x67104` | `0x601e2d51` |
| `ql_gpio_deinit` | `5a439d3f` | `0x66614` | `0x601f62f5` |
| `ql_gpio_init` | `bbd44ee5` | `0x67d5c` | `0x601f6449` |
| `ql_gpio_set_level` | `9588b8a3` | `0x673ec` | `0x601f6079` |
| `ql_pin_set_func` | `5f640714` | `0x65fcc` | `0x601f682d` |
| `ql_uart_write` | `75432b56` | `0x66974` | `0x6020bfa5` |


## 主屏显示路径

### 可复现初始化

R03 调用 `Helios_LCD_MIPIInit` 前，把 GPIO27、GPIO8 配置输出低。按 [PANEL_INIT](#原厂-r05-主屏初始化字节) 发送原厂初始化数据，数据流编码为 `命令,u8延时ms,u8数据长度,数据`；唤醒末尾为 `11 250 0`、`29 50 0`。

| 参数 | 值 |
|---|---|
| width / hight / bpp | 800 / 1280 / 16 |
| **lcd_interface** | **2**（R03 硬件枚举） |
| data_lane / trans_mode | 2 / 2 |
| mipi_mode / pixel_format / dsi_format / rgb_order | 0 / 0 / 0 / 0 |
| bllp_enable | true |
| h_sync_active / h_back_porch / h_front_porch | 20 / 40 / 40 |
| v_sync_active / v_back_porch / v_front_porch | 3 / 11 / 16 |
| frame_rate / te_sel / rst_Polarity | 60 / 0 / 1 |
| dsi_pclk_rate | 100（驱动参数单位照核心使用，不擅自换算 PLL 频率） |

SDK R01 `HELIOS_LCD_TYPE_MIPI=3` **不是**当前 R03 的 `lcd_interface` 值。R03 `Helios_LCD_MIPIInit` 指令入口 `0x601f94ae` 的硬件启动分支 `0x600fb108..0x600fb10e` 只接受 2。错误传 3 会分配缓冲但未启动正确显示，曾出现有背光、黑屏/角落颜色异常；改 2 后用户确认四条色带正常。GPIO ABI 的修正也保留，不能单独断言它是黑屏原因。

### 像素与提交

缓冲按行从左上开始：stride=800 像素=1600 字节，一帧 2,048,000 字节，无行填充。16 位字：`((B & 248)<<8) | ((G & 252)<<3) | (R>>3)`，little-endian。红色 `0x001f`（`1f 00`），绿色 `0x07e0`（`e0 07`），蓝色 `0xf800`（`00 f8`），白色 `0xffff`。本文称它 **BGR565**，不要套另一个项目的标准 RGB565 色序。

读取核心扫描缓冲指针前检查宽高、范围、对齐。写完真实像素后，调用 R03 cache-clean Thumb 指针 `0x60137213`，参数 `(buffer,length)`；随后 `0x08807038 |= 1` 并执行 `dsb sy`。这是当前复现 R03 提交流程的方法，要求核心 SHA 匹配。**提交返回/ACK 不是 vblank，也不是所有像素已经显示的证明。**

原生 SDK 的整屏写函数会 DMA 复制参数缓冲到核心扫描缓冲。把扫描缓冲自身作为它的输入曾造成实机内存损坏；另一独立 64 KiB DMA 实验也有损坏。因此当前 demo 采用 CPU 复制/受边界约束的 LZ4 像素写入，避免 DMA 自拷贝。LZ4 通用快速 decoder 会进行临时 wild-copy，直接在扫描缓冲上使用它可能被 LCD 扫描成雪花横条；必须保证只发布最终完整像素，或先在分块 staging 中解码。

接收缓存为两块 508 KiB，**不是**两张完整屏幕缓冲。亮度 OSD 有 480×112 的区域备份；OSD 开着时更新该区域的底图备份，再叠加条形图，避免恢复旧画面。整帧 LZ4 仅在压缩后 ≤508 KiB 且 OSD 无冲突时使用，其余分块。

### 原厂 R05 合成链

以下为原厂指令地址，不可直接在 R03 调用：

| 地址 | 恢复用途 |
|---|---|
| `0x60281bd8` | MipiLcdTaskInit，包含背光相关初始化 |
| `0x60281e74` | MIPI 配置，800×1280 |
| `0x6028193c` | 显示任务，队列长度 20，元素 72 字节 |
| `0x60310850` | MIPI 初始化导入 veneer |
| `0x602803ec` | 合成缓冲 getter |
| `0x80fe3340` | 保存合成缓冲地址的全局变量；初始化申请 `0x1f4000` 字节 |
| `0x80de0000` | 原厂整屏拷贝的扫描目标 |
| `0x602813cc` | 整屏 CPU 拷贝到扫描目标 |
| `0x6028183c` | 矩形拷贝，stride 800 |
| `0x60281398` | 开背光、等待 200 ms、失败重试等待 100 ms；**不是帧 flush/vsync** |
| `0x6028fe80` | `jpg_to_rgb565(path,height,width,stride_pixels,destination)` wrapper |
| `0x60298f38` / `0x60299340` | TJpgDec `jd_prepare` / `jd_decomp` |
| `0x6028ed80` / `0x6028ed38` | 文件读入回调 / 矩形像素输出回调 |

JPEG wrapper 栈约 `0x10ac`，含 4 KiB workspace；TJpgDec 矩形坐标为含端点，每像素 2 字节，输出按传入 stride 落入合成帧。另有 `0x19000` 字节工作区。原厂有“合成帧+扫描目标+拷贝”，这并不能证明硬件双缓冲 page flip。

### 帧率和现存问题

面板扫描 60 Hz 与 Windows 虚拟桌面 30 Hz、USB 交付帧率是三个数；少交付帧只应保持前一幅图，并不必然黑一下。现在还没有可靠的持续 vblank/TE 同步或无撕裂扫描提交机制。用户报告静态灰色/蓝绿混色闪烁，以及动态雪花横条，**尚未完全解决，也未证明是屏幕物理损坏**。

早期软件计时曾约 28 fps 简单原生 UI、约 10.6 fps 某复杂图片；场景、压缩率、模式和版本影响很大，不能作为“任意 1280×800 12 Hz”保证。测试应分别记录捕获/转换、编码、USB、解码、提交、整帧哈希及光学结果。已有可复核状态寄存器：LCD `0x08807008/0x0880700c`、DSI `0x08807454`；变化位不等于 vblank，W1C 不能随便清驱动已启用的中断位。


## 原厂 R05 主屏初始化字节

顺序发送下表；等待时间在该条命令发送后执行。没有等待的命令填 0。

| DCS 命令 | 数据（十六进制） | 等待 ms |
|---|---|---|
| `B9` | `F1 12 84` | 0 |
| `BA` | `31 81 05 F9 0E 0E 02 00 00 00 00 00 00 00 44 25 00 91 0A 00 00 00 4F 01 00 00 37` | 0 |
| `B8` | `A8` | 0 |
| `B3` | `00 00 00 00 07 0B 1E 1E` | 0 |
| `C0` | `73 73 50 50 80 00 08 70 00` | 0 |
| `CC` | `0B` | 0 |
| `BF` | `02 10 82` | 0 |
| `BC` | `46` | 0 |
| `B4` | `80` | 0 |
| `B2` | `40 08` | 0 |
| `E3` | `03 03 00 00 03 03 00 00 00 C0` | 0 |
| `B1` | `43 54 23 1E 1E 22 77 04 DB 4C` | 0 |
| `B5` | `0A 0A` | 0 |
| `B6` | `44 44` | 0 |
| `E9` | `02 00 04 05 0F 80 81 12 31 23 4F 06 80 28 47 08 00 00 0F 00 00 00 00 00 0F 00 00 00 11 44 FF 88 8B BA A3 31 17 75 58 00 44 FF 88 8B BA A2 20 06 64 48 00 00 00 00 00 00 00 00 00 00 00 00 00` | 0 |
| `EA` | `96 12 00 00 00 70 00 00 00 00 00 00 11 44 88 FF 8B BA A4 46 60 02 28 00 44 88 FF 8B BA A5 57 71 13 38 23 10 00 00 01 40 00 00 00 00 00 00 00 00 00 00 00 00 00 00 40 80 81 00 00 00 00 00 00` | 0 |
| `E0` | `01 13 19 27 2F 39 4A 3C 07 0C 0E 13 14 12 13 11 1A 01 13 19 27 2F 39 4A 3C 07 0C 0E 13 14 12 13 11 1A` | 0 |
| `11` | `无` | 250 |
| `29` | `无` | 50 |


## 喇叭、原厂增益与播放

原厂刷回后用户确认喇叭本身能响。原生固件无声的一个已复现原因是缺少本板 PA 使能；按照原厂引脚链路补齐后，独立 MP3 播放恢复。通用 EVB 的 GPIO11 PA 示例不适用本板。

| R05 指令地址 | 静态恢复的行为 |
|---|---|
| `0x602a43e4` | 选择 speaker；`ql_pin_set_func(15,4)`；`ql_gpio_deinit(22)`；`ql_gpio_init(22,1,255,0)` |
| `0x602a4324` | 播放电源回调调用 `ql_gpio_set_level(22,event!=0)` |
| `0x6027be58` | 原厂音量夹在 1..9，缺省 9 |
| `0x602a4330` | 音量/增益设置路径 |
| `0x602a4380` | 工厂最大档对应 DAC=75、algorithm=7 的增益配置 |
| `0x60310348` | `ql_set_audio_path_speaker` 导入 veneer |
| `0x60310258` / `0x60310428` | `ql_aud_set_volume` / `ql_aud_set_icvolume_level_gain` 导入 veneer |

R03 导入目标/哈希从 [IMPORTS_R03](#r03-已解析导入表) 查询，不把这些 R05 地址复制过去。R03 PA 回调注册 `Helios_Audio_SetPaCallback` 只记录请求；渲染任务拥有 GPIO22，按请求、speaker 路由、非零音量、增益就绪决定物理 PA。当前独立播放采用 `HELIOS_AUDIO_PLAY_TYPE_LOCAL` + `HELIOS_OUTPUT_SPEAKER`。低层文件 ABI 为 `UFS:文件名`；Python 的 `U:/` 别名不等于 C API 路径。

### 不突然放大的音量实现

原始百分比误映射到硬件高增益，10% 也很吵。恢复工厂上限以后，在 decoder 停止期间预设 9 档校准，播放中只调用 `Helios_Audio_SetVolume(LOCAL,level)` 并读回。**播放中不重写 gain table、不先静音、不关闭 PA、不重启音轨。** 用户已确认 6%..10% 正常连续变大/变小，没有瞬间大声和额外断声。

| 软件百分比区间 | 硬件档 | 预设锚点 |
|---|---|---|
| 0 | 0 | 静音 |
| 1..2 | 1 | 1% |
| 3..5 | 2 | 3% |
| 6..9 | 3 | 6% |
| 10..19 | 4 | 10% |
| 20..34 | 5 | 20% |
| 35..49 | 6 | 35% |
| 50..74 | 7 | 50% |
| 75..99 | 8 | 75% |
| 100 | 9 | 工厂最大增益 |

校准算法以工厂 DAC75/algorithm7 为上限。百分比 p 的衰减取 `ceil(−80*log10(p/100))` 半 dB 步；algorithm 每级 3 dB，先减最多 6 级，剩余衰减由 DAC 承担、DAC 不低于 0。对锚点计算后固定表，在板上不做每采样浮点运算。10% 档 DAC31/algorithm1；50% DAC74/algorithm3；100% DAC75/algorithm7。R03 algorithm 读回含义来自反汇编，约 `3*value−45 dB`。

百分比按较安静锚点向下取档，**不是 101 个独立硬件增益档**。10% 实际小声且未听到破音；最大档声学质量尚未再次确认。软件增益不能确定扬声器的额定瓦数、长期安全功率或消除任何硬件失真，需要仪器/声学测量。

### MP3 和电脑 PCM

MP3 上传到 `UFS:qdisplay_audio.part`，最大 4 MiB；按块写、全文件 XXH32 验证完成后才更名 `UFS:qdisplay_audio.mp3`。文件大小上限是当前 demo 设定，不是硬件存储容量。目录播放由电脑逐曲上传，设备没有复制整个电脑目录。

电脑采集流：**16 kHz、单声道、signed 16-bit little-endian PCM**。开始流后第一块加 44 字节 WAVPCM 头，以显式指定格式；R03 PCM 参数 setter `0x601e3084` 是 `bx lr`，不能靠调用它改变采样率。R03 `0x6013cd19`（Thumb 指针）控制 keep-open，避免每块流写入被当 EOS。2 s 没 PCM 会停流并关闭 PA；它不是 USB 音频声卡枚举，Windows 端需 loopback/capture 转发。

**当前本机 Windows 音频采集尚有问题**：WASAPI `IAudioClient.Initialize` 报 `0x800706cc`，重启音频服务后未恢复；旧 DLL 对照也同样失败。已有 Audiosrv/audiodg 关联挂起记录，但原因未确证。独立 MP3 可响，不等于电脑声音桥当前可用。完整证据在本地 `private/logs/auto_restore_20261009/`。


## USB、下载与恢复

### 工作态接口

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

### 下载状态与 wire format

已成功使用 AT `AT+QDOWNLOAD=1` 进入 RAM 下载；下载态 VID/PID=`0525:a4a7`。PDL/FDL wire 数据的字段和应用 QDC1 不同，不要混用。

FDL 的 BSL frame：`7e | escape(type:u16BE, size:u16BE, payload, checksum:u16) | 7e`；内部 `7e`、`7d` 转 `7d,(byte^20)`。BootROM 与 FDL 的校验模式不同，BootROM CRC16、FDL 16位 one's-complement sum，PDL 握手也独立实现。完整可复核协议实现保留在 [sprdflash](main/demo/third_party/sprdflash/protocol.py) 和其 `pdl.py`，MIT 许可；不是把原厂 loader 本体开源。

当前成功 R03 loader 固定身份：

| 文件 | SHA-256 | RAM 装载地址 |
|---|---|---|
| HOST_FDL_fdl1.sign.img | `cfad226ef5d892ee24609e0e3104109d459cd1daf3206357e698a1253ef67968` | `0x008000c0` |
| FDL2_fdl2.sign.img | `61ba99f74ea0614fd5996064670dc1caa705ef044a8acc919a8872557a38309a` | `0x00810000` |

流程：PDL connect→装载FDL1→执行→BSL/SPRD校验connect→装载FDL2→EXEC_DATA→connect。R03 READ_FLASH payload 为 `struct.pack('>III', absolute_address, count, 0)`，回复 type=`0x93`；4 KiB 每块。此 loader 对物理 NOR 忽略第三个字段，必须递增**绝对地址**，否则重复读第一个块。READ_FLASH 命令=`0x06`，NORMAL_RESET=`0x05`，START/MIDST/END_DATA=`1/2/3`、EXEC_DATA=`4`。当前 APP 更新不调用 ERASE_FLASH=`0x0a`、格式化或修改 NV。

### APP 更新和原厂恢复不是一回事

APP2 容器长度从头部 u32@4 读出，必须等于文件实际长度并≤`0xe0000`。偏移32..127每16字节为四u32 `(kind,offset,size,address)`；kind1/2/3为 APP RAM 装载/清零相关、kind4为 APP Flash；任何 address/size 必须在对应所有权范围中，非kind3的文件切片必须在容器内。不能把该 BIN 刷成从地址0开始的裸镜像。

当前工具读核心AP并核对固定SHA，双读APP旧区验证，才发送新APP到 `0x60260000`，随后逐字节读回比较并 reset。核心/loader指纹不符就停止写。只支持上述 R03 核心上更新 APP，**不能直接用于原厂R05板子首次转换**。

原厂恢复使用自己的完整内部双读备份，包含产品核心/APP/校准等，恢复布局及证据保留在本地 `private/backups/factory_restore/`、`private/backups/internal/`；旧恢复工具在 `junk/archive/scripts/restore_lakala_factory_20261008.py`。换一台设备时不要拿这台的 NV/IMEI/整机 dump 当通用 ROM。首次从原厂转 R03 需要合法来源的匹配官方 PAC、保存新设备本身备份、核对布局；本 demo 不打包完整官方核心/PAC。外部16MiB没有全片备份，原厂内部恢复不能证明外部也已完整恢复。


## QDC1 二进制协议

这是本项目应用层协议，**不是原厂协议，也不是 AIDA64/Odospace 协议**。跨语言电脑端只需按本页序列化；USB VCOM 是字节流，读写可能拆包。所有多字节数为 little-endian，无 Base64、换行或 JSON。传的是最终 BGR565 像素，设备不解 PNG/JPEG；可用原始块或无 frame/container 的 LZ4 block。

### 32 字节头部

| 字节偏移 | 类型 | 字段 | 约束 |
|---|---|---|---|
| 0 | u32 | magic | `0x31434451`，线上 `51 44 43 31` = QDC1 |
| 4 | u8 | version | 1 |
| 5 | u8 | type | 1..10；回复 128 |
| 6 | u16 | flags | 按命令解释 |
| 8 | u32 | seq | 主机序号，回复原样返回；每发一命令递增 |
| 12 | u32 | offset | 字节偏移/参数，按命令解释 |
| 16 | u32 | length | 随后的线上 payload 长度，最大 520192 |
| 20 | u32 | raw_length | 解压后长度/参数；无载荷命令也可有参数 |
| 24 | u32 | payload_hash | XXH32(payload,seed=0)；无载荷也是空串 XXH32=`0x02cc5d05`，不能填 0 |
| 28 | u32 | header_hash | XXH32(头部前 28 字节,seed=0) |

XXH32 不是 CRC32，也不是 xxh3。LZ4 为 raw block，不带原始长度前缀。空载荷头、ACK 和校验向量见 [fixtures](main/reverse/evidence/protocol)。首次建议 `HELLO(seq=1)`，只做协议查询；不能直接向未知 AT 或诊断端口发送整帧。

### 回复

回复头 type=128、flags=0、offset=0、length=raw_length=24、seq=请求 seq，头和载荷分别校验。载荷六个 u32：`status, receive_us, decode_us, draw_us, free_heap, detail`。时间通常是微秒；HELLO 诊断及音频复用这些字段为状态数据，不按时间处理。

status：0 OK、1 BAD_HEADER、2 BAD_LENGTH、3 BAD_HASH、4 BAD_STATE、5 DECODE_ERROR、6 DISPLAY_ERROR、7 NO_MEMORY、8 TIMEOUT。接收错误导致组装失效，重发完整 BEGIN/帧；不要对失败状态盲目 PATCH。软件 COMMIT ACK 不等于 vblank。

| type | 名称 | 常规用途 |
|---|---|---|
| 1 | HELLO | 能力/诊断/保活 |
| 2 | BEGIN | 开始全帧 |
| 3 | DATA | 像素分块，原始或 LZ4 |
| 4 | COMMIT | 提交全帧及逻辑帧哈希 |
| 5 | BENCH | 设备本地写帧计时，诊断而非普通播放 |
| 6 | VERIFY | 读回帧/区域 XXH32 |
| 7 | AUDIO | 播放、音量、上传和流控制 |
| 8 | AUDIO_DATA | MP3 上传块 |
| 9 | AUDIO_PCM | 实时 PCM 块 |
| 10 | PATCH | 基于已确认帧的绝对像素 tile 更新 |

### 握手和超时

`HELLO(flags=0,offset=0,raw_length=0,payload空)` 的 detail=接收块上限：当前 **508×1024=520192**。`HELLO(flags=2)` 的 detail 当前 **0x023f**：bit0 延迟 DATA ACK、bit1 UI 状态、bit2 文件音频、bit3 PCM、bit4 整帧 LZ4、bit5 PATCH；bits8..11 为窗口数 **2**。以后以协商结果为准，旧版本可能只有 128 KiB 或不支持这些功能。

无有效命令 5 s，固件使帧失效并显示等待连接；静态画面也需发送保活 HELLO。板卡重启、链路重连、等待页出现或 PATCH 失效后，要清主机参考帧并发完整帧。

`HELLO(flags=7)`：receive 为 UI bits（bit0 awake、bit1 frame_valid、bit2 host_recent）；decode 为按键 raw bits 0..2 及可用键 mask<<16；draw 为距最后有效主机命令的 ms；detail 为 UI magic `0x31534451`（QDS1）。`flags=10`：receive=亮度%，decode=PWM运行，draw=边沿计数，detail bits0awake/1OSD已绘制/2OSD请求。`flags=11,offset=5..100且5的倍数` 设置亮度并请求条；其余诊断 flags 不作为稳定公共控制 API。

### 最小整帧实现

1. 将 800×1280 画面转换为 [DISPLAY](#主屏显示路径) 的 BGR565，得到 2,048,000 字节。计算最终完整像素 XXH32。
2. 发 BEGIN：flags=0、offset=0、raw_length=2048000、payload 空；等 ACK。
3. 从 offset=0 顺序发 DATA。每块 raw_length≤520192，最后一块为余数；codec flags=0 表示原始块（length 必须等于 raw_length），flags=1 表示 LZ4 block。offset 是解压后在帧中的累计**字节**偏移；原始和解压长度都必须偶数，以保持像素边界。
4. 最简单的可靠实现是每块等待 ACK，detail 必须等于累计 raw 字节数。优化时，每组最多 2 块，组内前块 flags|=0x0100 可省成功 ACK，组末正常等 ACK；错误即使 defer 也回复。不无限流水发送，USB/R03 RX 缓冲可能溢出。
5. 发 COMMIT：flags=1、offset=最终完整像素哈希、raw_length=0、payload 空。ACK detail=2048000。flags=1 告诉固件该帧可作为 PATCH 基准。此处哈希是逻辑帧身份，并未自动重新扫描校验整帧；要验证真实像素再发 VERIFY。

全帧原始方式为 4 个 DATA，长度 `520192,520192,520192,487424`。不需要高压缩实现即可互通。整帧 LZ4 另允许一个 DATA：offset=0、raw_length=2048000、flags=1，**压缩长度仍≤520192**。BEGIN ACK detail=1 表示当前 OSD 冲突，应改分块；复杂图压缩不够也回退分块。

VERIFY flags=0 计算完整底图哈希；flags=1 用 offset/raw_length 指定区域，允许组装中检查；ACK detail 是 XXH32，OSD 区以底图备份替代亮度条像素。最小空白帧的哈希和合法序列见 fixtures。

### PATCH

必须在成功 COMMIT(flags=1) 或成功 PATCH 后发；与其他帧命令串行。头 type=10、flags=1、offset=**上一确认帧的 hash**、raw_length=补丁解压大小、payload=LZ4(block)。解压格式：

```
u32 target_full_frame_hash
u32 tile_count
repeat tile_count:
  u16 x, y, width=32, height=16
  u8 pixels[1024]    // 16 行，每行 32 个 BGR565 像素
```

x 是 32 倍数且 <800；y 是 16 倍数且 <1280；tile=1032 字节；raw_length 必须等于 `8+1032*count` 且≤520192（最多504个 tile）。这是**绝对像素**，不是 XOR；目标完整哈希由主机计算。ACK detail 返回 target hash。基准不匹配 status4 则发完整帧；高变化图超过补丁空间也用完整帧。设备没有第二张参考全帧，仅保存已确认哈希。

### 音频命令

type=7 为空载荷，flags 为子命令：

| flags | offset / raw_length | 行为、ACK 关键字段 |
|---|---|---|
| 0 | 0 / 0 | 查询：receive=百分比，decode=播放状态，draw=事件，detail=`0x31445541`（AUD1） |
| 1 | 0 / 0 | 终止上传及停止播放 |
| 2 | 0..100 / 0 | 调音量，detail=百分比 |
| 3 | 文件总字节 / 文件XXH32 | 开始 MP3 上传；最大4MiB，detail=文件大小 |
| 4 | 0 / 0 | 完成上传并检查文件哈希、更名；detail=文件哈希 |
| 5 | 0 / 0 | 从 UFS 播放；receive=百分比、decode=硬件档、draw=路由、detail=文件字节数 |
| 6 | 0 / 0 | 实际保存文件读回：receive=字节数、detail=XXH32 |
| 7 | 16000 / 1 | 开始16kHz单声道PCM，等待首块 |
| 8 | 0 / 0 | 只读路由/档位/PA/增益诊断 |
| 9 | 0..2 / 0 | 停止后变更路由，限诊断，正常使用speaker |
| 10 | 0 / 0 | 只读：receive=音量档变更次数、decode=预设写次数、draw=失败次数 |

type=8：flags=0、offset=MP3累计字节、length=raw_length=块长（1..16384），每块等 ACK，detail=累计字节。上传成功后 type7/4、7/6 验证，再 type7/5 播放。

type=9：flags=offset=0、length=raw_length=偶数且1..16384；payload 为 signed PCM16LE，ACK detail=接受字节。连接/状态失败时停音并重新建立流，不能重放迟到的音频队列。显示和音频共用同一命令流，主机必须串行协调，否则帧组装/ACK 序号冲突。


## 地址不确定及待验证项

### 印刷/段码小液晶屏：地址不确定

用户刷回拉卡拉原厂固件后，主喇叭正常，而印刷小屏仍不亮，提示后部排线可能损坏。没有完成排线连通测量/更换，因此“不亮”不能否定静态逆向候选，也不能证明小屏控制器坏了。

| 项 | 候选值 | 确认程度 |
|---|---|---|
| 控制器/原厂路径 | `led_fg00` / FG00 风格四线时序 | 原厂字符串与反汇编候选；实物芯片型号未测确认 |
| SCK | 物理 57 / QuecPython GPIO15 | **地址/连线不确定** |
| SDA | 物理 56 / QuecPython GPIO16 | **地址/连线不确定** |
| RST | 物理 52 / QuecPython GPIO28 | **地址/连线不确定** |
| EN / PWM | 物理 4 / QuecPython GPIO11 | **地址/连线不确定**；不是大主屏背光 |
| R03 控制函数/寄存器 | 未确认 | **地址不确定**，不臆造可调用函数地址 |

候选原厂协议，供更换排线后复核：MSB first，SCK 每位低→设置 SDA→高→低；字节后 SDA 高再发送第九个 latch/ACK 时钟。START 为 SCK 高、SDA 高→低；STOP 为 SCK 高、SDA 低→高。事务地址字节 `0x7e`；命令写法为 `0x80,command`。这是恢复的串行协议，不能仅因地址看似 I²C 就用标准 I²C 驱动替代。

候选初始化命令：`2f b1 40 34 68 a0 94 b2 4c 10 40 50 00 10 c0 88 88 88 88 61 e3`。候选开/关命令 `3d / 3c`。刷新命令 `40 50 10 00 c0`；之后每个数据字节独立 START、`7e c0 data`、STOP，一帧 72 字节=4×18 字节平面。旧程序建议边沿约 10 µs，但 Python 平台短延时曾被放大到约 20 ms，**不是已经确认的本板最佳时钟**。

候选第一行数字段位 a..g 坐标 `(1,0),(1,4),(2,4),(3,0),(2,0),(0,0),(0,4)`；数字掩码 `3f 06 5b 4f 66 6d 7d 07 7f 6f`。不能将候选坐标当成所有印刷图案的已确认 segment map。原始重建代码保留在 `junk/archive/firmware/product_beta/rear_display.py` 及 `junk/archive/firmware/ec600u_c_bringup/src/fg00.c`；底层证据在 [disasm_led_key_head](main/reverse/evidence/r05/disasm_led_key_head.txt) 和 [hardware_xrefs](main/reverse/evidence/r05/hardware_xrefs.json)。

### 查询键：地址不确定

后部左上“查询”键没有可靠的 GPIO/物理脚/事件来源映射。历史 `misc.PowerKey` 尝试和其他平台 PowerKey 行为只是线索，不构成该键映射确认。当前只读三个已知键 47/46/44，未扫描输出脚去试探。更换/测通排线后，先测开关两端电平，再关联输入 GPIO/原厂中断事件，单独记录有效极性。

### 其他未确认事实

外部 16 MiB Flash 全片未备份，物理总线/完整分区未确认；主屏辅助 GPIO27 的精确电气用途、PA 物理模组焊盘与功放芯片型号未单独测得；RGB 三个通道颜色次序/极性还需复核。原厂和 R03 的显示资料不证明真硬件 page flip、稳定 vblank 或任何场景无撕裂。静态灰/蓝绿闪烁原因未确定，不根据手机 240 fps 的滚动条单独判定屏幕损坏。新工厂上限音量的声学无失真也未确认。


## 证据与原始资料位置

公开资料和本地原件分开存放。公开目录允许重新核对指令、函数地址、字段和初始化数据；原始 dump、PAC、NV、用户路径和完整运行记录保留在 `private/` 并被 Git 忽略。这不是删掉逆向资料。

| 内容 | 路径 |
|---|---|
| R05 主显示、按键、LED、外部NOR/分区函数反汇编 | [evidence/r05](main/reverse/evidence/r05) |
| R05 硬件字符串引用和指令地址 | [hardware_xrefs.json](main/reverse/evidence/r05/hardware_xrefs.json) |
| R05 镜像区域基址、长度、SHA、uImage校验 | [structure.json](main/reverse/evidence/r05/structure.json) |
| R03 全部当前命名导入及目标 | [imports.json](main/reverse/evidence/r03/imports.json) / [IMPORTS_R03](#r03-已解析导入表) |
| R03 MIPI配置、寄存器、提交 helpers | [evidence/r03](main/reverse/evidence/r03) |
| R03/R05 音频调用、导入及增益反汇编 | [native_audio_20261005](main/reverse/evidence/native_audio_20261005)、[20261008](main/reverse/evidence/native_audio_20261008)、[20261009](main/reverse/evidence/native_audio_20261009) |
| SDK 声明原文与许可 | [evidence/abi](main/reverse/evidence/abi)，它们是上游声明，不是本项目AI重建函数 |
| 主屏 DCS 完整参数 | [panel_init_r05.json](main/reverse/evidence/panel_init_r05.json) / [PANEL_INIT](#原厂-r05-主屏初始化字节) |
| 用户提供的屏幕丝印 | [evidence/photos](main/reverse/evidence/photos) |
| 实际部署 demo 哈希、大小和基址 | [manifest](main/demo/releases/manifest.json) |
| 每个公开文件大小/哈希 | [PUBLIC_FILES.json](main/PUBLIC_FILES.json)（清理结束生成） |

仅在本机存在、不进 Git 的原始资料：

| 旧位置 | 新位置 |
|---|---|
| `analysis/` | `main/reverse/private/analysis/`；原结构完整保留 |
| `backups/` | `main/reverse/private/backups/`；含内部原厂8MiB、文件系统导出、APP读回、恢复记录 |
| `raw/` | `main/reverse/private/raw/`；USB描述符、AT/MOS及电脑系统抓取 |
| `logs/` | `main/reverse/private/logs/`；刷写、帧校验、性能、音量和重连验证原记录 |
| `references/` | `main/reverse/private/references/`；原PDF/下载资料 |
| `doc/`、`migration/` | `main/reverse/private/history/doc/`、`history/migration/`；完整旧结论和会话移交，日期早的不是当前状态 |
| 老工具、旧源码、候选固件、旧发布包 | `junk/archive/`，保持原目录名称；详细收纳清单在本地 `junk/inventory.json` |

每次迁移逐文件检查 SHA-256；本地 `main/reverse/private/INVENTORY.json` 记录原相对路径、新路径、字节数和SHA。别把历史“device_tested=false”构建字段当成后来刷写失败，也别把后来软件ACK通过当成光学缺陷已经修复。

### 重新定位地址

持有自己的合法镜像后，可用 [reverse/tools](main/reverse/tools) 离线重跑结构分析、ARM字符串交叉引用和指定范围反汇编。需要 Python、Capstone，PAC抽取还需 [sprdflash](main/demo/third_party/sprdflash)。例如对原厂完整dump：

```powershell
python main/reverse/tools/disassemble_arm_range.py own_factory.bin 0x602a43e4 0x100 --base 0x60000000 --out pa.txt
```

引用的上游：[Helios SDK 固定版本](https://github.com/QuecPython/Helios-SDK/tree/de3b7eb84c4523957ab21a3a0488d9246fe5e361)、[sprdflash](https://github.com/ajsb85/sprdflash)、[官方 QuecPython 文档](https://python.quectel.com/doc/quecpython/)。第三方不同型号的应用笔记只能作背景，不能替代本板映射证据。


## QDisplay Demo

参考实现快照：2026-10-09。固件为原生 **C**，桌面为 **C#/.NET Framework 4.8**；不是 Python/CMD 产品启动器。固件以 APPIMG 方式在指定官方 R03 核心上运行，无 Logicrom 激活/SIM 授权步骤。官方核心和厂商 loader 自行获取，未声明其全部源码开源。安装包见 [GitHub Releases](https://github.com/StevenLang233/lakala-display-re/releases)。

| 保留内容 | 路径 |
|---|---|
| 已刷入版本源码 | [firmware/src](main/demo/firmware/src) |
| 与固件匹配的生成头/图片 | [firmware/assets](main/demo/firmware/assets) |
| 固件 BIN，154400字节 | GitHub Releases 附件 `qdisplay_native.bin`（APP2容器，原 `.img` 字节未修改） |
| 当前上位机源码，含诊断检查 | [desktop/src](main/demo/desktop/src) |
| 实际已安装的 MSI | GitHub Releases 附件 `QDisplay-0.3.0-x64.msi` |
| GUI/服务及依赖原包文件 | Releases 附件 `QDisplay-0.3.0-Windows-files.zip`；服务须通过 MSI 注册，单拷 EXE 不是完整安装 |
| 版本/基址/二进制哈希 | [releases/manifest.json](main/demo/releases/manifest.json) |
| 源码逐文件指纹 | [SOURCE_SNAPSHOT.json](main/demo/SOURCE_SNAPSHOT.json) |
| 构建与APP更新 | [BUILD.md](#重建与更新-demo) |
| 创建仓库与发布版本 | [PUBLISH.md](#源码和安装包分别发布) |

发布包的本地副本在 `junk/publish/v0.3.0-demo.20261009/`，不进入源码 Git 历史。这些文件作为同一 demo 版本的 Release 附件分发，下载后以 `SHA256SUMS.txt` 核验。版本说明在 [releases/v0.3.0-demo.20261009.md](#首个-demo-版本说明)。

固件 SHA-256：`4e6da49fcff0628532ed325b7c722db4e83971015b4f6783a0655c4f099fb437`。
MSI SHA-256：`129e947933e041bf0e93c482c4d8bd9cb6e66e3fd28ba6d4f43c9f40bd4efa07`。

MSI 安装 LocalSystem 自动启动服务 `QDisplayDevice`、图形界面和系统托盘启动项。每用户配置在 `%LOCALAPPDATA%/QDisplay/ui.json`；板卡重启/USB重连时恢复所选显示/相框/硬件模式及音频意图。运行稳定时不重启采集流水线。虚拟副屏依赖独立的 **MikeTheTech Virtual Display Driver**（`ROOT\MTTVDD`），MSI 本身不包含该驱动；当前实现期望唯一虚拟设备，不改真实主显示器配置。请从 [上游项目](https://github.com/VirtualDrivers/Virtual-Display-Driver) 获取匹配驱动，本机历史使用25.7.23版本。

已知限制：部分颜色静态闪烁、动态撕裂仍有用户反馈；任意复杂画面12Hz未保证；本机当前WASAPI loopback报 `0x800706cc`，电脑声音桥未恢复，独立MP3已实机验证；小屏/查询键地址不确定，未启用。Linux/macOS尚无适配，不称跨平台成品；AIDA64手机LCD/Odospace兼容尚未完成。

历史上旧构建曾被卡巴斯基拦截，本目录保留的是之后实际安装且2026-10-09本机扫描未检出的版本；这不是数字签名，也不能承诺所有杀毒软件都不会误报。没有要求关闭杀毒/添加排除。

本项目原创源码、固件、上位机软件和文档**禁止商用，仅限个人使用**。未授权任何贩卖此商品的商家；完整商家授权与举报声明见[仓库 README](#使用限制与商家授权声明)。已有第三方许可保留，见 [THIRD_PARTY](#第三方来源与许可)，对应组件和上游资料仍遵循各自许可证。


## 重建与更新 Demo

所有脚本以自身位置确定目录，可从任意工作目录调用。构建不会自动安装上位机、刷写硬件或改变 Windows 显示配置。`releases/` 只保存实际部署版本的元数据和说明；BIN/MSI通过GitHub Releases分发，本机待上传快照在 `junk/publish/`。重建输出在忽略的 `build/`，不要覆盖快照来冒充同一次验证。

### Windows C# 上位机

需要 Windows x64、.NET Framework 4.8 及系统自带 Framework64 C# 编译器。本仓库保留NuGet依赖的版本、下载地址、包/DLL指纹和许可；构建脚本会恢复缺失依赖并核对SHA-256。DLL和下载缓存不进入Git，不需要原项目的虚拟环境。

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File main/demo/scripts/build_desktop.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File main/demo/scripts/build_desktop_msi.ps1
```

输出 `main/demo/build/windows/QDisplay.exe`、`QDisplay.Service.exe` 和 `QDisplay-0.3.0-x64.msi`。MSI使用Windows Installer标准表注册服务、快捷方式和启动项，不使用自安装/自提权代码。makecab只使用本次创建的ASCII临时目录；它的路径会打印，避免与源码中文目录混淆。ExecutionPolicy Bypass仅在当前脚本进程生效，不更改系统策略。

核对原快照源文件、BIN、MSI和依赖可运行 `python main/demo/scripts/verify_snapshot.py`。重建固件已复现与发布BIN完全相同的SHA-256；C# PE/MSI包含构建时间/包标识，重新构建不要求字节哈希相同，不要把“编译成功”表述为已再次做完硬件验收。

原快照MSI是0.3.0；为公开发布新版本，请同步修改程序集和MSI版本/ProductCode并完成升级验证。本整理没有制造一个行为改变的新版本。现有代码没有Linux/macOS UI/USB实现，仅Core协议层可复用。

已有无硬件检查在 `desktop/src/Checks`；例如恢复策略：

```powershell
$demo = (Resolve-Path main/demo).Path
$out = Join-Path $demo 'build\windows'
$csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$exe = Join-Path $out 'RecoveryPolicyCheck.exe'
$core = Join-Path $out 'QDisplay.Core.dll'
$source = Join-Path $demo 'desktop\src\Checks\RecoveryPolicyCheck.cs'
& $csc /nologo /target:exe "/out:$exe" "/r:$core" $source
& $exe (Join-Path $out 'recovery_check.json')
```

### 原生 C APPIMG

需要自行获取：固定 [Helios SDK](https://github.com/QuecPython/Helios-SDK/tree/de3b7eb84c4523957ab21a3a0488d9246fe5e361)、匹配 Cortex-A5 hard-float 的 ARM GCC、厂商 `dtools.exe`（mkappimg）、匹配 R03 的 `AP_8915DM_cat1_open.sign.img` 和 `APPIMG_EC600UCNLBR03A04M08_OCPU_QPY.img`。此处没有打包完整官方核心和编译器；许可证与来源请按上游处理。

Python仅作为离线构建/刷写工具，固件和上位机产品运行均不依赖Python。安装 `requirements-build.txt`，生成等待页与亮度条不需要重新装字体/图像库：使用 `firmware/assets/` 已部署的生成头，减少重建差异。

```powershell
python -m pip install -r main/demo/requirements-build.txt
powershell.exe -NoProfile -ExecutionPolicy Bypass -File main/demo/scripts/build_firmware.ps1 `
  -SdkRoot C:/sdk/Helios-SDK -ToolchainBin C:/sdk/gcc/bin `
  -QpyInputs C:/sdk/r03-pac-extracted -DTools C:/sdk/dtools.exe
```

输入必须为ASCII路径；脚本为demo源码创建检查过目标的临时junction以适配旧GCC。输出 `build/firmware/qdisplay_native.img`、ELF、map、导入审计manifest。`.img` 与发布 `.bin` 同为APP2容器；没有转换成整机raw镜像。脚本强制R03 AP SHA，检查导入唯一性，并以固定APP Flash/RAM区链接；不会运行SDK的整包烧录或格式化目标。默认保持原厂panel初始化，试验性关闭dither不混入快照。

### 在已经是匹配 R03 核心的板卡更新 APP

先确认工作态端口身份和AP版本，停止占用数据口的服务/客户端。`--at-port`必须显式填写本次MI_02 AT端口，不固定COM数字。工具无 `--image` 时只备份/检查；有该参数才更新APP：

```powershell
python main/demo/scripts/deploy_native_app.py --at-port COM8 --qpy-inputs C:/sdk/r03-pac-extracted
python main/demo/scripts/deploy_native_app.py --at-port COM8 --qpy-inputs C:/sdk/r03-pac-extracted `
  --image C:/Downloads/qdisplay_native.bin
```

loader也必须匹配 [USB_AND_BOOT](#usb下载与恢复) 指纹。备份和读回写入 `main/reverse/private/backups/demo_app_updates/`，不进入Git。工具双读验证备份，只更新APPIMG区、读回比对、reset；不提供此板原厂R05首次转R03的自动操作。R05原厂地址、其他PAC或整机dump不能拿来配当前APP。


## 第三方来源与许可

本项目原创内容的非商业个人使用限制及商家授权声明见[仓库 README](#使用限制与商家授权声明)。以下第三方组件和上游资料仍适用各自许可证，本项目声明不变更这些许可证。

| 部件 | 来源/版本 | 许可与保留位置 |
|---|---|---|
| Helios SDK 声明/链接输入 | QuecPython/Helios-SDK，commit de3b7eb84c4523957ab21a3a0488d9246fe5e361 | SDK根许可Apache-2.0，快照在 `../reverse/evidence/abi/SDK-LICENSE`；完整核心/loader二进制再分发权限没有逐件核对，所以没有打包 |
| LZ4 C实现 | 固件原快照，头部包含版本信息 | BSD-2-Clause，`firmware/src/third_party/LICENSE.lz4` |
| xxHash C头 | 固件原快照 | BSD-2-Clause，`firmware/src/third_party/LICENSE.xxhash` |
| sprdflash Python | ajsb85/sprdflash 的本机快照 | MIT，`third_party/sprdflash-LICENSE` |
| K4os.Compression.LZ4 | 1.3.8 | MIT，`dependencies/desktop/k4os.compression.lz4-LICENSE` |
| System.Memory / Buffers / Unsafe / Numerics.Vectors | 4.5.5 / 4.5.1 / 6.0.0 / 4.5.0 | 对应LICENSE与THIRD-PARTY-NOTICES在 `dependencies/desktop/` |
| 等待页、亮度条栅格字形 | 本机Microsoft YaHei渲染结果 | 保留匹配固件的生成图片/头，不复制字体文件；重新生成可选择有授权的本地字体 |
| Windows虚拟屏驱动 | VirtualDrivers/Virtual-Display-Driver，上游独立项目 | 本公开demo未打包驱动或测试证书，按上游版本许可处理 |

NuGet下载URL、包SHA和实际DLL SHA锁定在 [packages.lock.json](main/demo/dependencies/desktop/packages.lock.json)。引用SDK声明不意味着官方R03核心为开源软件。历史Logicrom/卖家ESP候选及下载工具已收纳到本地junk，未混进此demo。


## 源码和安装包分别发布

使用 `-RepositoryName` 参数指定仓库名。源码树保留逆向文档、证据、C/C#源代码、第三方许可、锁定依赖和版本说明；安装包作为 **GitHub Releases** 附件，不进入源码提交历史。当前版本标签：`v0.3.0-demo.20261009`。

| 位置 | 用途 |
|---|---|
| `main/reverse/` | 公开逆向文档与已整理证据 |
| `main/demo/firmware/src` / `desktop/src` | 参考实现源码 |
| `main/demo/releases/manifest.json`、版本说明 | Git保留的版本、核心身份、基址和文件指纹 |
| 本地 `junk/publish/v0.3.0-demo.20261009/` | 待上传BIN、MSI、Windows运行文件ZIP、校验和及upload-plan |
| 本地 `junk/publish/source-upload.zip` | 按Git可见清单生成的源码/文档预览包，方便上传前核对 |
| `main/reverse/private/` / `junk/archive/` | 原始dump/NV、个人历史和旧工具，只留本机 |

本地校验和打包，不要求GitHub登录，不写Git索引、不创建仓库：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File main/demo/scripts/publish_github.ps1 -PrepareOnly
python main/demo/scripts/prepare_upload_bundle.py
```

定好仓库名后，登录GitHub CLI（可用单独指定的便携 `gh.exe`），以自己的账号运行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File main/demo/scripts/publish_github.ps1 `
  -RepositoryName YOUR_REPOSITORY_NAME -Visibility public
```

`-Visibility private` 可建私有仓库；如果省略可见性，脚本默认私有。可以用 `-Owner YOUR_ACCOUNT` 检查GitHub CLI当前账号，防止传到其他登录账号。脚本执行顺序：校验源快照和附件→创建仓库→提交/推送源码→推版本标签→建草稿Release→上传附件→下载核对SHA→发布为demo预发行版本。失败会保留草稿/本地状态便于续传，不覆盖其他仓库或已有不同内容的同名版本。

首次创建需要GitHub CLI具有对应账号的仓库创建/写权限；连接Codex的GitHub账号不自动等同于本机 `gh` 已登录。Token不会写进源码、manifest、发布包或脚本参数。Git写权限和网络权限只在正式执行发布时需要，准备模式不执行这些步骤。

后续版本更新时同步程序集/MSI版本、产品升级身份、源快照和manifest，使用新标签，保留旧Release；固件BIN必须和对应源快照/核心匹配，不能用未验证候选冒充已经刷过的版本。厂商完整核心/loader不由此脚本上传。

源文件及生成资产的SHA按原始字节核对，`.gitattributes` 保留行尾，避免Git提交/检出改变CRLF/LF而破坏已部署快照指纹。

命令参数依据GitHub CLI官方文档：[创建仓库](https://cli.github.com/manual/gh_repo_create)、[创建Release](https://cli.github.com/manual/gh_release_create)、[上传附件](https://cli.github.com/manual/gh_release_upload)。


## 首个 Demo 版本说明

设备逆向资料与已部署demo的首个整理快照。固件为原生C，电脑端为C#/.NET Framework 4.8。完整源码和逆向文档在仓库内，安装包作为本Release附件分发。

| 文件 | 用途 |
|---|---|
| `qdisplay_native.bin` | 154400字节APP2容器，只适用于匹配R03核心的APP更新 |
| `QDisplay-0.3.0-x64.msi` | Windows x64上位机、设备后台服务和系统托盘程序 |
| `QDisplay-0.3.0-Windows-files.zip` | 同版GUI/服务/依赖原文件，供检查和开发；不替代MSI注册服务 |
| `release-manifest.json` | 核心身份、APP基址、版本、文件SHA-256及大小 |
| `SHA256SUMS.txt` | 下载后逐文件核验 |

已包含：USB二进制像素传输、LZ4及局部更新；相框/硬件信息/副屏；亮度按键及菜单长按待机；按原厂PA路径恢复喇叭；播放中直接调硬件音量档；设备重启和重连恢复已保存模式。10%独立MP3音量及6%～10%调节已获实机反馈确认。

限制：部分静态颜色闪烁和动态撕裂仍未完全解决；复杂画面1280×800 12Hz未保证；本机WASAPI采集报 `0x800706cc`，Windows声音桥当前未恢复；印刷小液晶屏与查询键地址不确定；Linux/macOS、AIDA64手机LCD/Odospace尚未完成。

固件核心必须为 `EC600UCNLBR03A04M08_OCPU_QPY`，AP SHA-256：`187abb282fd089e6c3fb9d8bb75b837826b1a726e943fe961e5bf052da433ca9`。BIN不是完整原厂ROM，也不用于原厂R05直接升级。下载/刷写前阅读仓库 `main/reverse/USB_AND_BOOT.md`、`main/demo/BUILD.md`。

Windows副屏另需上游Virtual Display Driver；MSI没有打包该驱动。此版本没有数字签名，不要求关闭杀毒软件或加排除。完整厂商核心、loader、原厂/NV dump与个人会话未包含在此Release。

### 使用限制与商家授权声明

**本项目禁止商用，仅限个人使用。**

没给任何卖这个终端的商家授权。

> 本项目仅限个人使用，任何贩卖此终端的商家禁止使用，包括但不限于，告诉买家有这个项目可以刷，直接附带本项目链接等。如有发现，乐意的话可以向我举报，我会感激不尽。

这些限制针对本项目原创内容。第三方部分仍按各自许可证使用。完整资料见[仓库 README](#使用限制与商家授权声明)。


分章节文档更新后，可运行 `python main/reverse/tools/render_readme.py` 同步本 README。
