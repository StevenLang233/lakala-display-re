# QDisplay demo

参考实现快照：2026-10-10。固件为原生 **C**，桌面为 **C#/.NET Framework 4.8**；不是 Python/CMD 产品启动器。固件以 APPIMG 方式在指定官方 R03 核心上运行，无 Logicrom 激活/SIM 授权步骤。官方核心和厂商 loader 自行获取，未声明其全部源码开源。安装包见 [GitHub Releases](https://github.com/StevenLang233/lakala-display-re/releases)。

新版屏幕电源功能需要配套更新固件和 MSI，见 [0.3.1 下载](https://github.com/StevenLang233/lakala-display-re/releases/tag/v0.3.1-demo.20261010)。旧下载合集固定在 0.3.0。

新用户到 [下载合集](https://github.com/StevenLang233/lakala-display-re/releases/tag/tools-v1.0.0) 取得 `QDisplay-Flash.cmd`，双击后自动下载并校验完整入口包；也可以下载 ZIP，解压并双击根目录 `一键刷机.bat`。同一页放固件 BIN、上位机 MSI 和运行文件包。刷写器源码在 [setup](setup/)。它处理官方依赖获取、原厂 R05 首次转换或 R03 APP 更新、备份校验、MSI 安装与连接检查；日常上位机仍独立运行。流程、恢复和已测试范围见 [SETUP](SETUP.md)。AIDA64/Odospace 兼容留待后续。

| 保留内容 | 路径 |
|---|---|
| 已刷入版本源码 | [firmware/src](firmware/src) |
| 与固件匹配的生成头/图片 | [firmware/assets](firmware/assets) |
| 固件 BIN，155456字节 | GitHub Releases 附件 `qdisplay_native.bin`（APP2容器，原 `.img` 字节未修改） |
| 当前上位机源码，含诊断检查 | [desktop/src](desktop/src) |
| 实际已安装的 MSI | GitHub Releases 附件 `QDisplay-0.3.1-x64.msi` |
| GUI/服务及依赖原包文件 | Releases 附件 `QDisplay-0.3.1-Windows-files.zip`；服务须通过 MSI 注册，单拷 EXE 不是完整安装 |
| 版本/基址/二进制哈希 | [releases/manifest.json](releases/manifest.json) |
| 源码逐文件指纹 | [SOURCE_SNAPSHOT.json](SOURCE_SNAPSHOT.json) |
| 构建与APP更新 | [BUILD.md](BUILD.md) |
| 创建仓库与发布版本 | [PUBLISH.md](PUBLISH.md) |

发布包的本地副本在 `junk/publish/v0.3.1-demo.20261010/`，不进入源码 Git 历史。这些文件作为同一 demo 版本的 Release 附件分发，下载后以 `SHA256SUMS.txt` 核验。版本说明在 [releases/v0.3.1-demo.20261010.md](releases/v0.3.1-demo.20261010.md)。

固件 SHA-256：`4af5b2b0df8ea504d07ae18bb900aae3fd69381e45e707b2c9ca39ae1c5a5fee`。
MSI SHA-256：`3955286e39faa450324cd335c6c454e99fd552278fd74ea941a8196d167ee80f`。

MSI 安装 LocalSystem 自动启动服务 `QDisplayDevice`、图形界面和系统托盘启动项。每用户配置在 `%LOCALAPPDATA%/QDisplay/ui.json`；板卡重启/USB重连时恢复所选显示/相框/硬件模式及音频意图。运行稳定时不重启采集流水线。虚拟副屏依赖独立的 **MikeTheTech Virtual Display Driver**（`ROOT\MTTVDD`），MSI 本身不包含该驱动；当前实现期望唯一虚拟设备，不改真实主显示器配置。请从 [上游项目](https://github.com/VirtualDrivers/Virtual-Display-Driver) 获取匹配驱动，本机历史使用25.7.23版本。

一键入口可代为取得并安装这个固定版本的签名驱动，不创建重复适配器，不导入测试证书。相框和硬件信息模式无需虚拟屏驱动。

屏幕电源：勾选“跟随 Windows 息屏和亮屏”后随当前 Windows 会话的显示器状态同步，变暗不算息屏；窗口关闭到托盘后仍有效。主窗口和托盘均可手动亮屏/息屏，下次 Windows 显示状态变化会重新同步。息屏时停止画面采集与发送，但音频独立工作；不关机、不关闭 USB。断开有效命令后 5 秒进入等待页，倒计时到 90 秒后关闭背光；重连可唤醒超时息屏，保活不会唤醒手动息屏。需要配套 0.3.1 固件。

已知限制：部分颜色静态闪烁、动态撕裂仍有用户反馈；任意复杂画面12Hz未保证；本机当前WASAPI loopback报 `0x800706cc`，电脑声音桥未恢复，独立MP3已实机验证；小屏/查询键地址不确定，未启用。Linux/macOS尚无适配，不称跨平台成品；AIDA64手机LCD/Odospace兼容尚未完成。

历史上旧构建曾被卡巴斯基拦截，旧版2026-10-09本机扫描未检出；新版尚未做完整杀毒复核；这不是数字签名，也不能承诺所有杀毒软件都不会误报。没有要求关闭杀毒/添加排除。

本项目有权许可的原创源码、固件、上位机软件和文档采用 **CC BY-NC-SA 4.0**，不授予商业用途许可。完整条款见 [LICENSE](../../LICENSE)，排除的第三方、原厂内容及兼容核对结论见 [LICENSE_SCOPE](../LICENSE_SCOPE.md) 和 [THIRD_PARTY](THIRD_PARTY.md)。这不把安装包中的第三方组件改成 CC 许可。个人使用倡议、商家声明及举报原话见[仓库 README](../../README.md#使用限制与商家授权声明)，不追加 CC 许可条件。
