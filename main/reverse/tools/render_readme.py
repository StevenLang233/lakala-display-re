"""Assemble the full root README from the maintained documentation chapters."""
from pathlib import Path
import argparse
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[3]
CHAPTERS = (
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

本项目是一个 **Vibe Coding** 与 **Vibe Reverse Engineering（VibeRE）** 项目。由项目作者 **StevenLang233** 指挥，**Codex（OpenAI）** 辅助执行资料检索、固件逆向分析、C/C# 代码编写、调试和文档整理；作者负责需求、方案取舍，并观察和反馈实物画面、声音及按键效果。VibeRE 在本项目中指 AI 辅助逆向工程。

研究对象为使用 Quectel EC600U-CN 的拉卡拉客显屏音响设备，资料截至 **2026-10-09**。下文直接包含完整的逆向章节、协议、构建方法和版本说明，供开发者依据硬件与接口资料编写自己的实现。

证据分为 **实机确认**、**静态逆向** 和 **候选／地址不确定**。软件 ACK、计时与校验通过不等于光学刷新率、无撕裂或声学质量；具体依据及剩余问题在对应章节列出。

固件 BIN、Windows MSI 和运行文件包从 [GitHub Releases](https://github.com/StevenLang233/lakala-display-re/releases) 下载。参考实现源码在 [C 固件](main/demo/firmware/src) 与 [C# 上位机](main/demo/desktop/src)。

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
    if resolved in ANCHORS and not url.fragment and not url.query:
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
    contents = "\n".join("- [" + title + "](#" + anchor + ")" for _, title, anchor in CHAPTERS)
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
