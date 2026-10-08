# QDisplay 一键刷写入口 1.0.0

下载 **QDisplay-Setup-1.0.0.zip**，完整解压，双击 **一键刷机.bat**。

入口检测设备、自动补齐依赖，确认后备份/刷写/读回验证，再安装并打开上位机。支持已核对的原厂 R05 转换和 R03 APP 更新。成功、失败或取消后都能选择导出日志；另有只安装上位机、只备份和恢复本机备份的菜单。

适用 Windows 10/11 x64、文档对应的 EC600U-CNLB 板卡。BIN/MSI 仍是 Demo 0.3.0，字节不变。首次准备需要网络；Python、官方核心、USB/虚拟屏驱动按锁定哈希从各自来源取得，完整厂商 ROM、他人 NV、私人历史均不在包里。

已经验证 PowerShell 5.1、实机只读检测、服务身份/连接查询、依赖准备、取消/日志导出和 22 项故障模拟；尚未在另一台原厂板上用新入口完成首次刷机及全新 Windows 安装实测。基础显示/相框使用沿用现有 Demo。AIDA64/Odospace、Linux/macOS 兼容未实现，现有闪烁/撕裂与 Windows 声音采集限制仍然保留。

使用说明在包内 README 的“一键刷写和基础使用”章节和 `main/demo/SETUP.md`。请用本 Release 的安装入口 ZIP；旧 Demo 标签的自动源码 ZIP 不包含新增入口。校验和见 `SHA256SUMS.txt`，文件清单及逐文件指纹在包内 `SETUP-CONTENTS.json`。

原创部分 CC BY-NC-SA 4.0；第三方部分保留原许可和通知。转发时保持包内 LICENSE、范围说明、第三方通知和 `offline/` 下的许可 ZIP。
