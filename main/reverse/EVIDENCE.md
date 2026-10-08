# 证据与原始资料位置

公开资料和本地原件分开存放。公开目录允许重新核对指令、函数地址、字段和初始化数据；原始 dump、PAC、NV、用户路径和完整运行记录保留在 `private/` 并被 Git 忽略。这不是删掉逆向资料。

| 内容 | 路径 |
|---|---|
| R05 主显示、按键、LED、外部NOR/分区函数反汇编 | [evidence/r05](evidence/r05) |
| R05 硬件字符串引用和指令地址 | [hardware_xrefs.json](evidence/r05/hardware_xrefs.json) |
| R05 镜像区域基址、长度、SHA、uImage校验 | [structure.json](evidence/r05/structure.json) |
| R03 全部当前命名导入及目标 | [imports.json](evidence/r03/imports.json) / [IMPORTS_R03](IMPORTS_R03.md) |
| R03 MIPI配置、寄存器、提交 helpers | [evidence/r03](evidence/r03) |
| R03/R05 音频调用、导入及增益反汇编 | [native_audio_20261005](evidence/native_audio_20261005)、[20261008](evidence/native_audio_20261008)、[20261009](evidence/native_audio_20261009) |
| SDK 声明原文与许可 | [evidence/abi](evidence/abi)，它们是上游声明，不是本项目AI重建函数 |
| 主屏 DCS 完整参数 | [panel_init_r05.json](evidence/panel_init_r05.json) / [PANEL_INIT](PANEL_INIT.md) |
| 用户提供的屏幕丝印 | [evidence/photos](evidence/photos) |
| 实际部署 demo 哈希、大小和基址 | [manifest](../demo/releases/manifest.json) |
| 每个公开文件大小/哈希 | [PUBLIC_FILES.json](../PUBLIC_FILES.json)（清理结束生成） |

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

每次迁移逐文件检查 SHA-256；本地 [private/INVENTORY.json](private/INVENTORY.json) 记录原相对路径、新路径、字节数和SHA。别把历史“device_tested=false”构建字段当成后来刷写失败，也别把后来软件ACK通过当成光学缺陷已经修复。

## 重新定位地址

持有自己的合法镜像后，可用 [reverse/tools](tools) 离线重跑结构分析、ARM字符串交叉引用和指定范围反汇编。需要 Python、Capstone，PAC抽取还需 [sprdflash](../demo/third_party/sprdflash)。例如对原厂完整dump：

```powershell
python main/reverse/tools/disassemble_arm_range.py own_factory.bin 0x602a43e4 0x100 --base 0x60000000 --out pa.txt
```

引用的上游：[Helios SDK 固定版本](https://github.com/QuecPython/Helios-SDK/tree/de3b7eb84c4523957ab21a3a0488d9246fe5e361)、[sprdflash](https://github.com/ajsb85/sprdflash)、[官方 QuecPython 文档](https://python.quectel.com/doc/quecpython/)。第三方不同型号的应用笔记只能作背景，不能替代本板映射证据。
