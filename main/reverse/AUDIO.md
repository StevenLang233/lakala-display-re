# 喇叭、原厂增益与播放

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

R03 导入目标/哈希从 [IMPORTS_R03](IMPORTS_R03.md) 查询，不把这些 R05 地址复制过去。R03 PA 回调注册 `Helios_Audio_SetPaCallback` 只记录请求；渲染任务拥有 GPIO22，按请求、speaker 路由、非零音量、增益就绪决定物理 PA。当前独立播放采用 `HELIOS_AUDIO_PLAY_TYPE_LOCAL` + `HELIOS_OUTPUT_SPEAKER`。低层文件 ABI 为 `UFS:文件名`；Python 的 `U:/` 别名不等于 C API 路径。

## 不突然放大的音量实现

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

## MP3 和电脑 PCM

MP3 上传到 `UFS:qdisplay_audio.part`，最大 4 MiB；按块写、全文件 XXH32 验证完成后才更名 `UFS:qdisplay_audio.mp3`。文件大小上限是当前 demo 设定，不是硬件存储容量。目录播放由电脑逐曲上传，设备没有复制整个电脑目录。

电脑采集流：**16 kHz、单声道、signed 16-bit little-endian PCM**。开始流后第一块加 44 字节 WAVPCM 头，以显式指定格式；R03 PCM 参数 setter `0x601e3084` 是 `bx lr`，不能靠调用它改变采样率。R03 `0x6013cd19`（Thumb 指针）控制 keep-open，避免每块流写入被当 EOS。2 s 没 PCM 会停流并关闭 PA；它不是 USB 音频声卡枚举，Windows 端需 loopback/capture 转发。

**当前本机 Windows 音频采集尚有问题**：WASAPI `IAudioClient.Initialize` 报 `0x800706cc`，重启音频服务后未恢复；旧 DLL 对照也同样失败。已有 Audiosrv/audiodg 关联挂起记录，但原因未确证。独立 MP3 可响，不等于电脑声音桥当前可用。完整证据在本地 `private/logs/auto_restore_20261009/`。
