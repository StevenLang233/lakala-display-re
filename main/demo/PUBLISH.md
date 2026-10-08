# 源码和安装包分别发布

使用 `-RepositoryName` 参数指定仓库名。源码树保留逆向文档、证据、C/C#源代码、第三方许可、锁定依赖和版本说明；安装包作为 **GitHub Releases** 附件，不进入源码提交历史。当前版本标签：`v0.3.0-demo.20261009`。

普通用户优先看 `tools-v1.0.0` [下载合集](releases/tools-v1.0.0.md)：独立 `QDisplay-Flash.cmd`、已发布的完整 Setup ZIP、原 Demo BIN/MSI/运行文件包和许可 ZIP 放在同一 Release。CMD 源码在 `main/demo/setup/`，固定校验原 `setup-v1.0.0` ZIP 的指纹；合集只复制原附件，不重新构建或覆盖旧 Release。合集自己的 manifest 和 SHA256SUMS 对这些附件重新列清单。

提交源码后运行 `python main/demo/scripts/prepare_tools_bundle.py` 生成合集，输出到本机 `junk/publish/tools-v1.0.0/`。脚本核对原附件指纹、复制后读回核对，并记录源码提交；不从当前树重建旧 Setup ZIP。

一键入口单独用 `setup-v1.0.0` 标签和 [版本说明](releases/setup-v1.0.0.md)，Demo BIN/MSI不改版本和字节。用 `prepare_setup_bundle.py` 从 Git 可见源文件及 0.3.0 原附件生成 `QDisplay-Setup-1.0.0.zip`、独立 manifest 和 SHA256SUMS，默认保存在本机 `junk/publish/setup-v1.0.0/`。包内 `offline/` 带 APP/MSI/原许可 ZIP，外部依赖仍由入口锁定下载；不把原厂核心、USB 驱动、NV 或私人历史打包。

```powershell
python main/demo/scripts/prepare_upload_bundle.py
python main/demo/scripts/prepare_setup_bundle.py
```

更新入口发布说明或依赖锁时使用新入口版本；不要重用已有同名包覆盖不同源码，不要移动旧 Demo 标签。现有 0.3.0 Release 的不可变 BIN/MSI 和依赖锁对应，用于一键包的哈希核验；修改安装器/固件行为时必须另外更新 Demo 版本、二进制指纹和验证结果。

发布准备需要 PATH 中可调用的 Python 3.11+，用于离线许可打包。`prepare_release_payload.ps1` 会附上 `QDisplay-0.3.0-LICENSES.zip`，校验和及 Release manifest 同时记录这个附件；二进制转发时一并保留它。许可附件的指纹和文件清单在 [license-bundle.json](releases/license-bundle.json)。原有 BIN/MSI/Windows 文件包不因补充许可而重编译或替换。

| 位置 | 用途 |
|---|---|
| `main/reverse/` | 公开逆向文档与已整理证据 |
| `main/demo/firmware/src` / `desktop/src` | 参考实现源码 |
| `main/demo/releases/manifest.json`、版本说明 | Git保留的版本、核心身份、基址和文件指纹 |
| 本地 `junk/publish/v0.3.0-demo.20261009/` | 待上传BIN、MSI、Windows运行文件ZIP、校验和及upload-plan |
| 本地 `junk/publish/source-upload.zip` | 按Git可见清单生成的源码/文档预览包，方便上传前核对 |
| `main/reverse/private/` / `junk/archive/` | 原始dump/NV、个人历史和旧工具，只留本机 |

本地校验和打包，不要求GitHub登录，不写Git索引、不创建仓库：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File main/demo/scripts/publish_github.ps1 -PrepareOnly
python main/demo/scripts/prepare_upload_bundle.py
```

定好仓库名后，登录GitHub CLI（可用单独指定的便携 `gh.exe`），以自己的账号运行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File main/demo/scripts/publish_github.ps1 `
  -RepositoryName YOUR_REPOSITORY_NAME -Visibility public
```

`-Visibility private` 可建私有仓库；如果省略可见性，脚本默认私有。可以用 `-Owner YOUR_ACCOUNT` 检查GitHub CLI当前账号，防止传到其他登录账号。脚本执行顺序：校验源快照和附件→创建仓库→提交/推送源码→推版本标签→建草稿Release→上传附件→下载核对SHA→发布为demo预发行版本。失败会保留草稿/本地状态便于续传，不覆盖其他仓库或已有不同内容的同名版本。

首次创建需要GitHub CLI具有对应账号的仓库创建/写权限；连接Codex的GitHub账号不自动等同于本机 `gh` 已登录。Token不会写进源码、manifest、发布包或脚本参数。Git写权限和网络权限只在正式执行发布时需要，准备模式不执行这些步骤。

后续版本更新时同步程序集/MSI版本、产品升级身份、源快照和manifest，使用新标签，保留旧Release；固件BIN必须和对应源快照/核心匹配，不能用未验证候选冒充已经刷过的版本。厂商完整核心/loader不由此脚本上传。

源文件及生成资产的SHA按原始字节核对，`.gitattributes` 保留行尾，避免Git提交/检出改变CRLF/LF而破坏已部署快照指纹。

命令参数依据GitHub CLI官方文档：[创建仓库](https://cli.github.com/manual/gh_repo_create)、[创建Release](https://cli.github.com/manual/gh_release_create)、[上传附件](https://cli.github.com/manual/gh_release_upload)。
