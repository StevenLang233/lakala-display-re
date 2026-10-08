# 主屏显示路径

## 可复现初始化

R03 调用 `Helios_LCD_MIPIInit` 前，把 GPIO27、GPIO8 配置输出低。按 [PANEL_INIT](PANEL_INIT.md) 发送原厂初始化数据，数据流编码为 `命令,u8延时ms,u8数据长度,数据`；唤醒末尾为 `11 250 0`、`29 50 0`。

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

## 像素与提交

缓冲按行从左上开始：stride=800 像素=1600 字节，一帧 2,048,000 字节，无行填充。16 位字：`((B & 248)<<8) | ((G & 252)<<3) | (R>>3)`，little-endian。红色 `0x001f`（`1f 00`），绿色 `0x07e0`（`e0 07`），蓝色 `0xf800`（`00 f8`），白色 `0xffff`。本文称它 **BGR565**，不要套另一个项目的标准 RGB565 色序。

读取核心扫描缓冲指针前检查宽高、范围、对齐。写完真实像素后，调用 R03 cache-clean Thumb 指针 `0x60137213`，参数 `(buffer,length)`；随后 `0x08807038 |= 1` 并执行 `dsb sy`。这是当前复现 R03 提交流程的方法，要求核心 SHA 匹配。**提交返回/ACK 不是 vblank，也不是所有像素已经显示的证明。**

原生 SDK 的整屏写函数会 DMA 复制参数缓冲到核心扫描缓冲。把扫描缓冲自身作为它的输入曾造成实机内存损坏；另一独立 64 KiB DMA 实验也有损坏。因此当前 demo 采用 CPU 复制/受边界约束的 LZ4 像素写入，避免 DMA 自拷贝。LZ4 通用快速 decoder 会进行临时 wild-copy，直接在扫描缓冲上使用它可能被 LCD 扫描成雪花横条；必须保证只发布最终完整像素，或先在分块 staging 中解码。

接收缓存为两块 508 KiB，**不是**两张完整屏幕缓冲。亮度 OSD 有 480×112 的区域备份；OSD 开着时更新该区域的底图备份，再叠加条形图，避免恢复旧画面。整帧 LZ4 仅在压缩后 ≤508 KiB 且 OSD 无冲突时使用，其余分块。

## 原厂 R05 合成链

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

## 帧率和现存问题

面板扫描 60 Hz 与 Windows 虚拟桌面 30 Hz、USB 交付帧率是三个数；少交付帧只应保持前一幅图，并不必然黑一下。现在还没有可靠的持续 vblank/TE 同步或无撕裂扫描提交机制。用户报告静态灰色/蓝绿混色闪烁，以及动态雪花横条，**尚未完全解决，也未证明是屏幕物理损坏**。

早期软件计时曾约 28 fps 简单原生 UI、约 10.6 fps 某复杂图片；场景、压缩率、模式和版本影响很大，不能作为“任意 1280×800 12 Hz”保证。测试应分别记录捕获/转换、编码、USB、解码、提交、整帧哈希及光学结果。已有可复核状态寄存器：LCD `0x08807008/0x0880700c`、DSI `0x08807454`；变化位不等于 vblank，W1C 不能随便清驱动已启用的中断位。
