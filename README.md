# Lakala Display RE

拉卡拉客显屏音响逆向及 Demo。

项目入口：[main/README.md](main/README.md)。

`main/reverse/` 是独立的硬件、内存地址、ABI、显示、音频及 USB 文档；`main/demo/` 保留实际部署版本的 C 固件、C# 上位机源码及版本元数据。固件 BIN、上位机 MSI 和运行文件包从 [Releases](https://github.com/StevenLang233/lakala-display-re/releases) 下载。

原始镜像及完整研究记录在 `main/reverse/private/`，旧环境、旧构建和会话在 `junk/`，两者默认不进入 Git。安装包的本地副本在 `junk/publish/`，发布方式见 [PUBLISH.md](main/demo/PUBLISH.md)，仓库名称通过发布脚本参数指定。
