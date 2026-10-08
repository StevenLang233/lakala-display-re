# 逆向文档索引

本项目有权许可的原创说明采用 CC BY-NC-SA 4.0；原厂引用、SDK 声明及非原创照片等不重新授权，适用范围和来源疑点见 [LICENSE_SCOPE](../LICENSE_SCOPE.md)。

先读 [硬件映射](HARDWARE.md)，再读 [内存和 ABI](MEMORY_AND_ABI.md)、[主屏显示](DISPLAY.md) 和 [音频](AUDIO.md)。写独立电脑端可直接实现 [QDC1 二进制协议](PROTOCOL.md)，不需要复制现有客户端。

| 文档 | 独立实现需要的信息 |
|---|---|
| [HARDWARE.md](HARDWARE.md) | 板卡识别、物理脚、GPIO 命名空间、按键、背光、喇叭及 Flash |
| [MEMORY_AND_ABI.md](MEMORY_AND_ABI.md) | R05/R03 区别、地址换算、内存所有权、导入绑定、GPIO ABI |
| [IMPORTS_R03.md](IMPORTS_R03.md) | 实际已链接导入的名称、哈希、核心偏移、可调用目标地址 |
| [DISPLAY.md](DISPLAY.md) | 原厂 JPEG/合成/扫描链、R03 MIPI 参数、像素格式、DMA 陷阱 |
| [PANEL_INIT.md](PANEL_INIT.md) | 原厂主屏初始化指令、全部数据和延时 |
| [AUDIO.md](AUDIO.md) | PA 引脚、音频路径、工厂增益、音量档位、MP3/PCM 播放 |
| [USB_AND_BOOT.md](USB_AND_BOOT.md) | USB 接口、下载协议、APPIMG 布局及恢复边界 |
| [PROTOCOL.md](PROTOCOL.md) | 字节级头部、哈希、ACK、整帧、局部更新和音频命令 |
| [UNCERTAIN.md](UNCERTAIN.md) | 尚不能确证的地址、FG00 候选协议、剩余缺陷 |
| [EVIDENCE.md](EVIDENCE.md) | 原始证据在哪里，如何重新复核 |

证据等级：**实机确认**指设备读回/像素校验或用户明确反馈；**静态逆向**指镜像/SDK 中可复核的结构和调用；**候选/地址不确定**不能直接当成已测连线。软件 ACK、计时和 CRC 不等于光学刷新率、无撕裂或声学质量。
