# 源码和安装包分别发布

使用 `-RepositoryName` 参数指定仓库名。源码树保留逆向文档、证据、C/C#源代码、第三方许可、锁定依赖和版本说明；安装包作为 **GitHub Releases** 附件，不进入源码提交历史。当前版本标签：`v0.3.0-demo.20261009`。

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
