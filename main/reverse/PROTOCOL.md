# QDC1 二进制协议（当前 demo）

这是本项目应用层协议，**不是原厂协议，也不是 AIDA64/Odospace 协议**。跨语言电脑端只需按本页序列化；USB VCOM 是字节流，读写可能拆包。所有多字节数为 little-endian，无 Base64、换行或 JSON。传的是最终 BGR565 像素，设备不解 PNG/JPEG；可用原始块或无 frame/container 的 LZ4 block。

## 32 字节头部

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

XXH32 不是 CRC32，也不是 xxh3。LZ4 为 raw block，不带原始长度前缀。空载荷头、ACK 和校验向量见 [fixtures](evidence/protocol)。首次建议 `HELLO(seq=1)`，只做协议查询；不能直接向未知 AT 或诊断端口发送整帧。

## 回复

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

## 握手和超时

`HELLO(flags=0,offset=0,raw_length=0,payload空)` 的 detail=接收块上限：当前 **508×1024=520192**。`HELLO(flags=2)` 的 detail 当前 **0x023f**：bit0 延迟 DATA ACK、bit1 UI 状态、bit2 文件音频、bit3 PCM、bit4 整帧 LZ4、bit5 PATCH；bits8..11 为窗口数 **2**。以后以协商结果为准，旧版本可能只有 128 KiB 或不支持这些功能。

无有效命令 5 s，固件使帧失效并显示等待连接；静态画面也需发送保活 HELLO。板卡重启、链路重连、等待页出现或 PATCH 失效后，要清主机参考帧并发完整帧。

`HELLO(flags=7)`：receive 为 UI bits（bit0 awake、bit1 frame_valid、bit2 host_recent）；decode 为按键 raw bits 0..2 及可用键 mask<<16；draw 为距最后有效主机命令的 ms；detail 为 UI magic `0x31534451`（QDS1）。`flags=10`：receive=亮度%，decode=PWM运行，draw=边沿计数，detail bits0awake/1OSD已绘制/2OSD请求。`flags=11,offset=5..100且5的倍数` 设置亮度并请求条；其余诊断 flags 不作为稳定公共控制 API。

## 最小整帧实现

1. 将 800×1280 画面转换为 [DISPLAY](DISPLAY.md) 的 BGR565，得到 2,048,000 字节。计算最终完整像素 XXH32。
2. 发 BEGIN：flags=0、offset=0、raw_length=2048000、payload 空；等 ACK。
3. 从 offset=0 顺序发 DATA。每块 raw_length≤520192，最后一块为余数；codec flags=0 表示原始块（length 必须等于 raw_length），flags=1 表示 LZ4 block。offset 是解压后在帧中的累计**字节**偏移；原始和解压长度都必须偶数，以保持像素边界。
4. 最简单的可靠实现是每块等待 ACK，detail 必须等于累计 raw 字节数。优化时，每组最多 2 块，组内前块 flags|=0x0100 可省成功 ACK，组末正常等 ACK；错误即使 defer 也回复。不无限流水发送，USB/R03 RX 缓冲可能溢出。
5. 发 COMMIT：flags=1、offset=最终完整像素哈希、raw_length=0、payload 空。ACK detail=2048000。flags=1 告诉固件该帧可作为 PATCH 基准。此处哈希是逻辑帧身份，并未自动重新扫描校验整帧；要验证真实像素再发 VERIFY。

全帧原始方式为 4 个 DATA，长度 `520192,520192,520192,487424`。不需要高压缩实现即可互通。整帧 LZ4 另允许一个 DATA：offset=0、raw_length=2048000、flags=1，**压缩长度仍≤520192**。BEGIN ACK detail=1 表示当前 OSD 冲突，应改分块；复杂图压缩不够也回退分块。

VERIFY flags=0 计算完整底图哈希；flags=1 用 offset/raw_length 指定区域，允许组装中检查；ACK detail 是 XXH32，OSD 区以底图备份替代亮度条像素。最小空白帧的哈希和合法序列见 fixtures。

## PATCH

必须在成功 COMMIT(flags=1) 或成功 PATCH 后发；与其他帧命令串行。头 type=10、flags=1、offset=**上一确认帧的 hash**、raw_length=补丁解压大小、payload=LZ4(block)。解压格式：

```
u32 target_full_frame_hash
u32 tile_count
repeat tile_count:
  u16 x, y, width=32, height=16
  u8 pixels[1024]    // 16 行，每行 32 个 BGR565 像素
```

x 是 32 倍数且 <800；y 是 16 倍数且 <1280；tile=1032 字节；raw_length 必须等于 `8+1032*count` 且≤520192（最多504个 tile）。这是**绝对像素**，不是 XOR；目标完整哈希由主机计算。ACK detail 返回 target hash。基准不匹配 status4 则发完整帧；高变化图超过补丁空间也用完整帧。设备没有第二张参考全帧，仅保存已确认哈希。

## 音频命令

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

## 0.3.1 屏幕电源扩展

HELLO(flags=2) 的 bit6 表示软件开关屏幕。HELLO(flags=18,offset=0/1/2) 分别息屏、亮屏、只查询；payload/raw_length 均为空/零。ACK receive 为 awake，detail=0x31534451。查询和 flags=7 不保活、不唤醒。手动息屏只改背光，不关机或断开 USB。5秒等待页之后持续无命令到90秒自动息屏，重连自动唤醒仅适用于这次自动息屏。
