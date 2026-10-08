# QDisplay demo

参考实现快照：2026-10-09。固件为原生 **C**，桌面为 **C#/.NET Framework 4.8**；不是 Python/CMD 产品启动器。固件以 APPIMG 方式在指定官方 R03 核心上运行，无 Logicrom 激活/SIM 授权步骤。官方核心和厂商 loader 自行获取，未声明其全部源码开源。安装包见 [GitHub Releases](https://github.com/StevenLang233/lakala-display-re/releases)。

| 保留内容 | 路径 |
|---|---|
| 已刷入版本源码 | [firmware/src](firmware/src) |
| 与固件匹配的生成头/图片 | [firmware/assets](firmware/assets) |
| 固件 BIN，154400字节 | GitHub Releases 附件 `qdisplay_native.bin`（APP2容器，原 `.img` 字节未修改） |
| 当前上位机源码，含诊断检查 | [desktop/src](desktop/src) |
| 实际已安装的 MSI | GitHub Releases 附件 `QDisplay-0.3.0-x64.msi` |
| GUI/服务及依赖原包文件 | Releases 附件 `QDisplay-0.3.0-Windows-files.zip`；服务须通过 MSI 注册，单拷 EXE 不是完整安装 |
| 版本/基址/二进制哈希 | [releases/manifest.json](releases/manifest.json) |
| 源码逐文件指纹 | [SOURCE_SNAPSHOT.json](SOURCE_SNAPSHOT.json) |
| 构建与APP更新 | [BUILD.md](BUILD.md) |
| 创建仓库与发布版本 | [PUBLISH.md](PUBLISH.md) |

发布包的本地副本在 `junk/publish/v0.3.0-demo.20261009/`，不进入源码 Git 历史。这些文件作为同一 demo 版本的 Release 附件分发，下载后以 `SHA256SUMS.txt` 核验。版本说明在 [releases/v0.3.0-demo.20261009.md](releases/v0.3.0-demo.20261009.md)。

固件 SHA-256：`4e6da49fcff0628532ed325b7c722db4e83971015b4f6783a0655c4f099fb437`。
MSI SHA-256：`129e947933e041bf0e93c482c4d8bd9cb6e66e3fd28ba6d4f43c9f40bd4efa07`。

MSI 安装 LocalSystem 自动启动服务 `QDisplayDevice`、图形界面和系统托盘启动项。每用户配置在 `%LOCALAPPDATA%/QDisplay/ui.json`；板卡重启/USB重连时恢复所选显示/相框/硬件模式及音频意图。运行稳定时不重启采集流水线。虚拟副屏依赖独立的 **MikeTheTech Virtual Display Driver**（`ROOT\MTTVDD`），MSI 本身不包含该驱动；当前实现期望唯一虚拟设备，不改真实主显示器配置。请从 [上游项目](https://github.com/VirtualDrivers/Virtual-Display-Driver) 获取匹配驱动，本机历史使用25.7.23版本。

已知限制：部分颜色静态闪烁、动态撕裂仍有用户反馈；任意复杂画面12Hz未保证；本机当前WASAPI loopback报 `0x800706cc`，电脑声音桥未恢复，独立MP3已实机验证；小屏/查询键地址不确定，未启用。Linux/macOS尚无适配，不称跨平台成品；AIDA64手机LCD/Odospace兼容尚未完成。

历史上旧构建曾被卡巴斯基拦截，本目录保留的是之后实际安装且2026-10-09本机扫描未检出的版本；这不是数字签名，也不能承诺所有杀毒软件都不会误报。没有要求关闭杀毒/添加排除。

源码及二进制是 demo；本仓库尚未替原创部分选定统一许可证。已有第三方许可保留，见 [THIRD_PARTY](THIRD_PARTY.md)，不能把整个固件核心一并宣称为某个开源许可。
