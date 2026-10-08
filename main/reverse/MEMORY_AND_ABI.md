# 内存、版本与 ABI

## 镜像身份和地址换算

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

结构、各 region SHA 及基址见 [structure.json](evidence/r05/structure.json)。

## 当前 R03 应用所有权

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

## 导入绑定

SDK 的 `.text.core_stub.<name>` 包含 `df f8 00 f0` 和 4 字节导入哈希。应用最终 `.corestub` 留下所需 stub；在固定 AP 中搜索该 4 字节，取后续 little-endian u32，要求唯一匹配、目标 bit0=1、目标在 `0x60010000..0x6025ffff`。这是现有导入审计方法，不把扫描任意固件得到的偶然字节匹配当成通用 resolver。

全部已使用导入列在 [IMPORTS_R03.md](IMPORTS_R03.md) / [imports.json](evidence/r03/imports.json)，函数声明见 [SDK ABI 快照](evidence/abi)。自写程序应保留 SDK 链接/启动流程，再绑定命名 stub；对内部定时器、USB 流对象、LCD 变量等未公开地址，加完整核心指纹门禁。

SDK GPIO 配置里的 enum 字段不能直接传给本 R03：R03 `Helios_GPIO_Init` 实际读取三个 **u8**：`direction, pull, initial_level`。使用三字节布局；相关枚举数值从对应声明取，不拿 R01 大结构按猜测传入。

R03 MIPI 结构的重要字段偏移（32 位 ARM，常规四字节对齐）：`init_data=0`、`init_data_len=4`、`width=8`、`hight=12`、`bpp=u16@16`、`lcd_interface=u16@18`、`data_lane=u8@20`、`mipi_mode@21`、`pixel_format@22`、`dsi_format@23`、`trans_mode@24`、`rgb_order@25`、`bllp_enable@26`、水平 sync/back/front `u32@28/32/36`、垂直 sync/back/front `u32@40/44/48`、`frame_rate@52`、`te_sel@53`、`rst_Polarity@54`、`dsi_pclk_rate=u32@56`，结构总长 60 字节。使用前以编译器 offsetof/static_assert 和 ABI 证据复核。
