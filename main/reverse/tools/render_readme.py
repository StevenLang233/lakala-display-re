"""Assemble the full root README from the maintained documentation chapters."""
from pathlib import Path
import argparse
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[3]
CHAPTERS = (
    ("main/LICENSE_SCOPE.md", "许可范围与兼容核对", "许可范围与兼容核对"),
    ("main/demo/SETUP.md", "一键刷写和基础使用", "一键刷写和基础使用"),
    ("main/reverse/HARDWARE.md", "板卡与信号映射", "板卡与信号映射"),
    ("main/reverse/MEMORY_AND_ABI.md", "内存、版本与 ABI", "内存版本与-abi"),
    ("main/reverse/IMPORTS_R03.md", "R03 已解析导入表", "r03-已解析导入表"),
    ("main/reverse/DISPLAY.md", "主屏显示路径", "主屏显示路径"),
    ("main/reverse/PANEL_INIT.md", "原厂 R05 主屏初始化字节", "原厂-r05-主屏初始化字节"),
    ("main/reverse/AUDIO.md", "喇叭、原厂增益与播放", "喇叭原厂增益与播放"),
    ("main/reverse/USB_AND_BOOT.md", "USB、下载与恢复", "usb下载与恢复"),
    ("main/reverse/PROTOCOL.md", "QDC1 二进制协议", "qdc1-二进制协议"),
    ("main/reverse/UNCERTAIN.md", "地址不确定及待验证项", "地址不确定及待验证项"),
    ("main/reverse/EVIDENCE.md", "证据与原始资料位置", "证据与原始资料位置"),
    ("main/demo/README.md", "QDisplay Demo", "qdisplay-demo"),
    ("main/demo/BUILD.md", "重建与更新 Demo", "重建与更新-demo"),
    ("main/demo/THIRD_PARTY.md", "第三方来源与许可", "第三方来源与许可"),
    ("main/demo/PUBLISH.md", "源码和安装包分别发布", "源码和安装包分别发布"),
    ("main/demo/releases/v0.3.0-demo.20261009.md", "首个 Demo 版本说明", "首个-demo-版本说明"),
)
ANCHORS = {(ROOT / path).resolve(): anchor for path, _, anchor in CHAPTERS}
INTRO = """# Lakala Display RE

拉卡拉客显屏音响逆向及 Demo。

这是个纯 **Vibe Coding / VibeRE** 项目。VibeRE 指 Vibe Reverse Engineering，也就是 AI 辅助逆向。

**作者的话**

> 我是个废物，但是废物也想给大家做点贡献，所以就选择了点燃token照亮大家的行为，希望大家可以用我抽ai生成出来的屎山代码做出很牛逼的项目！
>
> 我甚至废物到文档都是ai生成的，如果有人机味很重的话希望大家别骂我，因为我真的是纯废物呜呜呜呜呜呜呜TAT

如果您对我烧的token有所认可，并且您财力雄厚的话，欢迎您行行好给我打赏一下（端碗）orz

<img src="main/assets/steven-appreciation.jpg" alt="Steven 的赞赏码" width="360">

折腾的是一台用 Quectel **EC600U-CN** 的拉卡拉客显屏音响。引脚、地址、显示、音频、USB 协议和编译方法都在下面，资料截至 **2026-10-09**。

实机测过的、从固件里分析出的、还不确定的内容，分别标成 **实机确认**、**静态逆向** 和 **候选／地址不确定**。屏幕闪烁、撕裂和电脑声音采集还没完全解决，具体看对应章节。

固件 BIN、Windows MSI 和运行文件包从 [GitHub Releases](https://github.com/StevenLang233/lakala-display-re/releases) 下载。参考实现源码在 [C 固件](main/demo/firmware/src) 与 [C# 上位机](main/demo/desktop/src)。

新用户下载 [QDisplay-Setup-1.0.0.zip](https://github.com/StevenLang233/lakala-display-re/releases/tag/setup-v1.0.0)，完整解压，双击 **一键刷机.bat**，选 **1** 后确认。设备检测、依赖准备、备份刷写、上位机安装与日志都由入口处理。具体条件和验证范围见[一键刷写和基础使用](#一键刷写和基础使用)。

## 使用限制与商家授权声明

**本项目有权许可的原创部分采用 CC BY-NC-SA 4.0（署名—非商业性使用—相同方式共享），不授予商业用途许可。** 完整条款见 [LICENSE](LICENSE)，适用范围及例外见[许可范围与兼容核对](#许可范围与兼容核对)。第三方内容保留原许可，不能用本项目的非商业条款覆盖它们。

没给任何卖这个终端的商家单独商业授权。下面是我的个人使用倡议和商家声明：

> 本项目仅限个人使用，任何贩卖此终端的商家禁止使用，包括但不限于，告诉买家有这个项目可以刷，直接附带本项目链接等。如有发现，乐意的话可以向我举报，我会感激不尽。

上面的“仅限个人”和商家介绍、附链接限制是作者请求，不是标准 CC 许可的额外条件；正式授权以 CC 原文为准，不限制 CC 允许或依法无需许可的使用。第三方部分仍按各自许可证使用，见[第三方来源与许可](#第三方来源与许可)。

## 目录

"""
LINK = re.compile(r"(?P<label>!?\[[^\]\n]*\])\((?P<target>[^)\n]+)\)")


def rewrite_link(match, document):
    target = match["target"]
    url = urlsplit(target)
    if url.scheme or target.startswith(("#", "//")):
        return match[0]
    resolved = (document.parent / unquote(url.path)).resolve()
    relative = resolved.relative_to(ROOT).as_posix()
    if relative.startswith(("main/reverse/private/", "junk/")):
        # These originals exist only locally; do not create dead GitHub links.
        return "`" + relative + "`"
    if resolved == ROOT / "README.md" and url.fragment and not url.query:
        destination = "#" + url.fragment
    elif resolved in ANCHORS and not url.fragment and not url.query:
        destination = "#" + ANCHORS[resolved]
    else:
        destination = relative
        if url.query:
            destination += "?" + url.query
        if url.fragment:
            destination += "#" + url.fragment
    return match["label"] + "(" + destination + ")"


def chapter(path, title):
    document = ROOT / path
    original = document.read_text(encoding="utf-8-sig").splitlines()
    if not original or not original[0].startswith("# "):
        raise ValueError("Chapter must start with a title: " + path)
    while len(original) > 1 and not original[1].strip():
        original.pop(1)
    output = ["## " + title, ""]
    fence = None
    for line in original[1:]:
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker:
            if fence is None:
                fence = marker[1][0]
            elif marker[1][0] == fence:
                fence = None
            output.append(line)
        elif fence is not None:
            output.append(line)
        else:
            line = re.sub(r"^(#{1,5}) ", lambda match: "#" + match[1] + " ", line)
            output.append(LINK.sub(lambda match: rewrite_link(match, document), line))
    if fence is not None:
        raise ValueError("Unclosed code fence in " + path)
    return "\n".join(output).strip() + "\n"


def render():
    contents = "- [使用限制与商家授权声明](#使用限制与商家授权声明)\n"
    contents += "\n".join("- [" + title + "](#" + anchor + ")" for _, title, anchor in CHAPTERS)
    body = "\n\n".join(chapter(path, title) for path, title, _ in CHAPTERS)
    return INTRO + contents + "\n\n" + body + "\n\n分章节文档更新后，可运行 `python main/reverse/tools/render_readme.py` 同步本 README。\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="check that README matches its chapters")
    args = parser.parse_args()
    expected = render()
    destination = ROOT / "README.md"
    if args.check:
        if destination.read_text(encoding="utf-8") != expected:
            raise SystemExit("README differs from the documentation chapters; regenerate it.")
    else:
        destination.write_text(expected, encoding="utf-8", newline="\n")
    print("README: " + str(len(CHAPTERS)) + " complete chapters, " + str(len(expected.encode("utf-8"))) + " bytes.")
