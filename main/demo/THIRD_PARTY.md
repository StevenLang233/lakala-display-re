# 第三方来源

本项目的 CC BY-NC-SA 4.0 只覆盖有权许可的原创部分，**不覆盖第三方代码、运行库和原厂引用**。它们仍适用原许可证，版权、许可与免责文本保留；原许可允许的独立商业使用不因本项目的 NC 声明而消失。完整范围见 [LICENSE_SCOPE](../LICENSE_SCOPE.md)，根目录 [LICENSE](../../LICENSE) 是标准 CC 原文。核对日期：2026-10-09。

| 部件 | 来源/版本 | 许可与保留位置 |
|---|---|---|
| Helios SDK 声明/链接输入 | [QuecPython/Helios-SDK](https://github.com/QuecPython/Helios-SDK/tree/de3b7eb84c4523957ab21a3a0488d9246fe5e361)，commit de3b7eb84c4523957ab21a3a0488d9246fe5e361 | 根许可 Apache-2.0；[SDK声明](../reverse/evidence/abi/SDK-LICENSE)和[完整条款](../reverse/evidence/abi/APACHE-2.0.txt)；完整核心/loader 二进制再分发权限未逐件核对，没有打包 |
| LZ4 C库 | [lz4/lz4](https://github.com/lz4/lz4/tree/v1.10.0/lib)，本地头文件版本1.10.0 | BSD-2-Clause，[原快照许可](firmware/src/third_party/LICENSE.lz4)、源文件完整头及[当前头部通知](third_party/SOURCE-HEADER-NOTICES.txt)；没有使用上游另有 GPL 条款的命令行程序 |
| xxHash C头 | [Cyan4973/xxHash](https://github.com/Cyan4973/xxHash/tree/v0.8.3)，本地头版本0.8.3 | BSD-2-Clause，[原快照许可](firmware/src/third_party/LICENSE.xxhash)、源文件完整头及[当前头部通知](third_party/SOURCE-HEADER-NOTICES.txt) |
| sprdflash Python | [ajsb85/sprdflash](https://github.com/ajsb85/sprdflash) 的本机快照；不声称逐文件等于某个上游commit | MIT，[许可](third_party/sprdflash-LICENSE)；源码及本机衍生部分保留随附 MIT，不重新许可为 CC |
| K4os.Compression.LZ4 | 1.3.8 | MIT，`dependencies/desktop/k4os.compression.lz4-LICENSE` |
| System.Memory / Buffers / Unsafe / Numerics.Vectors | 4.5.5 / 4.5.1 / 6.0.0 / 4.5.0 | 对应LICENSE与THIRD-PARTY-NOTICES在 `dependencies/desktop/` |
| newlib C运行库 | 现用ARM工具链 newlib 3.0.0；已部署链接map可见 libc.a 的 memcpy/memmove/memset对象 | 各来源许可集合，[COPYING.NEWLIB](third_party/runtime/COPYING.NEWLIB)原样复制自工具链；不是原创 |
| libgcc运行库 | 现用GCC 8.2.1；链接map可见 libgcc.a 算术辅助对象 | [GPLv3](third_party/runtime/COPYING3)及 [Runtime Library Exception 3.1](third_party/runtime/COPYING.RUNTIME)；例外允许符合条件的独立模块使用不同条款，不能据此改许可分发GCC本体 |
| 等待页、亮度条图片 | Microsoft YaHei渲染完整词句/百分比，已核对生成脚本 | 不复制TTF/TTC，不是逐字位图字体；原创布局可授权，字体本身除外。[微软说明](https://learn.microsoft.com/en-us/typography/fonts/font-faq) |
| Windows虚拟屏驱动 | [VirtualDrivers/Virtual-Display-Driver](https://github.com/VirtualDrivers/Virtual-Display-Driver)，本机历史使用25.7.23 | 当前上游 [MIT](https://github.com/VirtualDrivers/Virtual-Display-Driver/blob/master/LICENSE)；未打包驱动、运行时或测试证书，独立获取时核对对应版本许可 |

NuGet下载URL、包SHA和实际DLL SHA锁定在 [packages.lock.json](dependencies/desktop/packages.lock.json)。微软包内还有 Unicode、zlib、BSD、Apache 等通知，不能只写 MIT 就丢掉它们，本次保留了完整 THIRD-PARTY-NOTICES。

BSD/MIT 条款没有要求独立原创代码沿用同一种许可；Apache 第4条也允许在遵守原义务的前提下给自己的修改/衍生部分采用不同条款。本项目选择并列保留第三方原许可，不给它们追加 NC 限制。LZ4/xxHash 独立 LICENSE 快照的年份较旧，当前源文件保留了2023年版权头；新增通知直接复制当前完整头部，原快照字节不变。

## 协议参考与尚未完成的来源鉴定

sprdflash 注释提到了其他开源协议项目：

- [kagaimiq/sprdproto](https://github.com/kagaimiq/sprdproto) 是 MIT，控制请求值和校验行为出现在注释中，本次附上其[原MIT文本](third_party/sprdproto-LICENSE)。
- [iscle/sprdclient](https://github.com/iscle/sprdclient) 是 GPL-3.0。当前快照自述为独立的 Python 协议实现，没有打包该项目的 C/C++ 源文件；没有完成历史代码的逐行溯源，不能据此保证不存在衍生关系。
- `spreadtrum_flash`/`spd_dump` 历史参考没有固定版本，不能把未核对版本的许可写成已确认；它的代码和二进制没有随本仓库分发。

**如果确认有 GPL 衍生代码，必须按其 GPL 处理，不能对必须按 GPL 分发的部分加上 CC 的非商业限制。** 应移除、替换、另行取得授权，或在符合 GPL 的前提下单独提供；不能用“第三方例外”消除不相容的组合。[GNU GPL FAQ](https://www.gnu.org/licenses/gpl-faq.html#DoesTheGPLAllowMoney)

## 仅开发时使用、没有打包的依赖

构建/逆向脚本使用 pyelftools、xxhash、pyserial、capstone，sprdflash 可选 USB 路径还调用 PyUSB/libusb；没有把这些包塞进固件或上位机。pyelftools 主体为 public domain/Unlicense（随附 construct 有独立许可），xxhash Python 包、pyserial 和 PyUSB 按各自 BSD 条款，capstone 按 BSD 及其随附通知，libusb 为 LGPL-2.1-or-later。自行安装原包；以后若封装 Python 可执行文件或分发 libusb，需要按实际版本补齐许可、通知及 LGPL 的替换/重新链接等义务。

来源：[pyelftools](https://github.com/eliben/pyelftools/blob/main/LICENSE)、[xxhash Python](https://github.com/ifduyue/python-xxhash/blob/master/LICENSE)、[pyserial](https://github.com/pyserial/pyserial/blob/master/LICENSE.txt)、[capstone](https://www.capstone-engine.org/download)、[PyUSB](https://github.com/pyusb/pyusb/blob/master/LICENSE)、[libusb](https://github.com/libusb/libusb/blob/master/COPYING)。

完整厂商核心、loader、原厂/NV dump没有分发。历史 Logicrom、卖家 ESP 候选和下载工具只在本地 `junk/`，未混进此 Demo，不能据此声称这些工程已兼容 CC。

## 二进制分发通知

保留根目录 CC 原文、[范围说明](../LICENSE_SCOPE.md)、本清单及各第三方版权/许可/通知。现有 Release 增加 `QDisplay-0.3.0-LICENSES.zip`，与 BIN/MSI 一起下载和转发；BIN/MSI原文件不改字节。桌面包已有 NuGet 的 `THIRD-PARTY-NOTICES.txt`，不替代固件运行库等其他通知。构建/发布脚本会生成完整许可包；增加依赖、修改第三方源文件或发布新版时同步更新通知。
