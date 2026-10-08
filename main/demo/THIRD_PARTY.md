# 第三方来源

本项目原创内容的非商业个人使用限制及商家授权声明见[仓库 README](../../README.md#使用限制与商家授权声明)。以下第三方组件和上游资料仍适用各自许可证，本项目声明不变更这些许可证。

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

NuGet下载URL、包SHA和实际DLL SHA锁定在 [packages.lock.json](dependencies/desktop/packages.lock.json)。引用SDK声明不意味着官方R03核心为开源软件。历史Logicrom/卖家ESP候选及下载工具已收纳到本地junk，未混进此demo。
