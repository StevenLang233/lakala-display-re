# 重建与更新 demo

所有脚本以自身位置确定目录，可从任意工作目录调用。构建不会自动安装上位机、刷写硬件或改变 Windows 显示配置。`releases/` 只保存实际部署版本的元数据和说明；BIN/MSI通过GitHub Releases分发，本机待上传快照在 `junk/publish/`。重建输出在忽略的 `build/`，不要覆盖快照来冒充同一次验证。

## Windows C# 上位机

需要 Windows x64、.NET Framework 4.8 及系统自带 Framework64 C# 编译器。本仓库保留NuGet依赖的版本、下载地址、包/DLL指纹和许可；构建脚本会恢复缺失依赖并核对SHA-256。DLL和下载缓存不进入Git，不需要原项目的虚拟环境。

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File main/demo/scripts/build_desktop.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File main/demo/scripts/build_desktop_msi.ps1
```

输出 `main/demo/build/windows/QDisplay.exe`、`QDisplay.Service.exe` 和 `QDisplay-0.3.0-x64.msi`。MSI使用Windows Installer标准表注册服务、快捷方式和启动项，不使用自安装/自提权代码。makecab只使用本次创建的ASCII临时目录；它的路径会打印，避免与源码中文目录混淆。ExecutionPolicy Bypass仅在当前脚本进程生效，不更改系统策略。

核对原快照源文件、BIN、MSI和依赖可运行 `python main/demo/scripts/verify_snapshot.py`。重建固件已复现与发布BIN完全相同的SHA-256；C# PE/MSI包含构建时间/包标识，重新构建不要求字节哈希相同，不要把“编译成功”表述为已再次做完硬件验收。

原快照MSI是0.3.0；为公开发布新版本，请同步修改程序集和MSI版本/ProductCode并完成升级验证。本整理没有制造一个行为改变的新版本。现有代码没有Linux/macOS UI/USB实现，仅Core协议层可复用。

已有无硬件检查在 `desktop/src/Checks`；例如恢复策略：

```powershell
$demo = (Resolve-Path main/demo).Path
$out = Join-Path $demo 'build\windows'
$csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$exe = Join-Path $out 'RecoveryPolicyCheck.exe'
$core = Join-Path $out 'QDisplay.Core.dll'
$source = Join-Path $demo 'desktop\src\Checks\RecoveryPolicyCheck.cs'
& $csc /nologo /target:exe "/out:$exe" "/r:$core" $source
& $exe (Join-Path $out 'recovery_check.json')
```

## 原生 C APPIMG

需要自行获取：固定 [Helios SDK](https://github.com/QuecPython/Helios-SDK/tree/de3b7eb84c4523957ab21a3a0488d9246fe5e361)、匹配 Cortex-A5 hard-float 的 ARM GCC、厂商 `dtools.exe`（mkappimg）、匹配 R03 的 `AP_8915DM_cat1_open.sign.img` 和 `APPIMG_EC600UCNLBR03A04M08_OCPU_QPY.img`。此处没有打包完整官方核心和编译器；许可证与来源请按上游处理。

Python仅作为离线构建/刷写工具，固件和上位机产品运行均不依赖Python。安装 `requirements-build.txt`，生成等待页与亮度条不需要重新装字体/图像库：使用 `firmware/assets/` 已部署的生成头，减少重建差异。

```powershell
python -m pip install -r main/demo/requirements-build.txt
powershell.exe -NoProfile -ExecutionPolicy Bypass -File main/demo/scripts/build_firmware.ps1 `
  -SdkRoot C:/sdk/Helios-SDK -ToolchainBin C:/sdk/gcc/bin `
  -QpyInputs C:/sdk/r03-pac-extracted -DTools C:/sdk/dtools.exe
```

输入必须为ASCII路径；脚本为demo源码创建检查过目标的临时junction以适配旧GCC。输出 `build/firmware/qdisplay_native.img`、ELF、map、导入审计manifest。`.img` 与发布 `.bin` 同为APP2容器；没有转换成整机raw镜像。脚本强制R03 AP SHA，检查导入唯一性，并以固定APP Flash/RAM区链接；不会运行SDK的整包烧录或格式化目标。默认保持原厂panel初始化，试验性关闭dither不混入快照。

## 在已经是匹配 R03 核心的板卡更新 APP

先确认工作态端口身份和AP版本，停止占用数据口的服务/客户端。`--at-port`必须显式填写本次MI_02 AT端口，不固定COM数字。工具无 `--image` 时只备份/检查；有该参数才更新APP：

```powershell
python main/demo/scripts/deploy_native_app.py --at-port COM8 --qpy-inputs C:/sdk/r03-pac-extracted
python main/demo/scripts/deploy_native_app.py --at-port COM8 --qpy-inputs C:/sdk/r03-pac-extracted `
  --image C:/Downloads/qdisplay_native.bin
```

loader也必须匹配 [USB_AND_BOOT](../reverse/USB_AND_BOOT.md) 指纹。备份和读回写入 `main/reverse/private/backups/demo_app_updates/`，不进入Git。工具双读验证备份，只更新APPIMG区、读回比对、reset；不提供此板原厂R05首次转R03的自动操作。R05原厂地址、其他PAC或整机dump不能拿来配当前APP。
