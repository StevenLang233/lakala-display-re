# QDisplay 下载合集

刷写器、固件和上位机放在同一页，源码都在仓库里。

- **QDisplay-Flash.cmd**：可单独下载，双击后自动取得并校验完整刷写包，再进入设备检测、依赖准备、确认刷机、备份与读回验证流程。结尾可选导出日志。
- **QDisplay-Setup-1.0.0.zip**：完整刷写包，解压后双击 `一键刷机.bat`。如果和 CMD 放在同一个文件夹，CMD 会校验并使用它，不重复下载。
- **qdisplay_native.bin**：Demo 0.3.0 固件 APP，不能直接当作整机 ROM 写入。
- **QDisplay-0.3.0-x64.msi**：上位机安装包。
- **QDisplay-0.3.0-Windows-files.zip**：上位机运行文件，服务需要通过 MSI 注册。
- **QDisplay-0.3.0-LICENSES.zip**：原 Demo 的第三方许可附件；转发二进制时一并保留。

首次使用直接双击 CMD，或解压完整刷写包；已刷好只需安装上位机可运行 MSI，也可在刷写菜单选 2。适用 Windows 10/11 x64、文档对应 EC600U-CNLB 板卡。联网准备依赖，刷写前询问确认，不自动重启电脑或关闭安全软件。

CMD 缓存和设备备份保留在 CMD 所在目录的 `.qdisplay-launcher/setup-v1.0.0/QDisplay-Setup-1.0.0/` 下。不要删除自己的 `.qdisplay/backups/`。下载被浏览器改名时，把文件恢复为附件原名；哈希不一致时停止执行。

CMD 源码在 `main/demo/setup/QDisplay-Flash.cmd`，完整刷写器源码在同目录。此 CMD 固定使用已发布的 `setup-v1.0.0` 包，不覆盖既有版本；BIN/MSI/运行包/许可包沿用已核对的原始字节。逐文件 SHA-256 见 `SHA256SUMS.txt` 和 `tools-manifest.json`。

入口准备、设备只读检测、取消与日志已验证；新入口在另一台原厂板上的完整首次刷机、全新 Windows 安装仍待实测。现有显示/音频限制见 README；AIDA64/Odospace 尚未实现。

原创部分 CC BY-NC-SA 4.0；第三方部分按原许可，范围见仓库 LICENSE_SCOPE 和 THIRD_PARTY。
