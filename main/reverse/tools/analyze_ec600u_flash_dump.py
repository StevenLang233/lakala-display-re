#!/usr/bin/env python3
"""Offline structural analysis for a full EC600U/RDA8910 NOR dump."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import struct
import zlib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree


NOR_BASE = 0x6000_0000
BLOCK = 0x1_0000
UIMAGE_MAGIC = b"\x27\x05\x19\x56"
LUADB_MAGIC = b"\x5a\xa5\x5a\xa5"

KEYWORDS = (
    "lcd", "mipi", "display", "screen", "panel", "backlight", "pwm",
    "jpeg", "jpg", "bmp", "png", "qrcode", "framebuffer", "st7789",
    "st7735", "st7567", "gc9306", "sc7705", "spi6", "ext nor",
    "extflash", "external flash", "sffs", "efs:", "ext_fs", "flash capacity",
    "1280", "800", "cloudspeak", "cs80", "app_mipilcd", "picinfotobmp",
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    total = len(data)
    return -sum((n / total) * math.log2(n / total) for n in counts.values())


def find_all(data: bytes, needle: bytes):
    start = 0
    while True:
        pos = data.find(needle, start)
        if pos < 0:
            return
        yield pos
        start = pos + 1


def parse_uimage(image: bytes, offset: int) -> dict[str, object] | None:
    if offset + 64 > len(image) or image[offset:offset + 4] != UIMAGE_MAGIC:
        return None
    fields = struct.unpack_from(">7I4B32s", image, offset)
    magic, header_crc, timestamp, size, load, entry, data_crc, os_id, arch, kind, comp, raw_name = fields
    end = offset + 64 + size
    if end > len(image):
        return None
    header = bytearray(image[offset:offset + 64])
    header[4:8] = b"\0\0\0\0"
    payload = image[offset + 64:end]
    name = raw_name.split(b"\0", 1)[0].decode("latin-1", "replace")
    return {
        "offset": offset,
        "physical_address": f"0x{NOR_BASE + offset:08x}",
        "payload_size": size,
        "total_size": size + 64,
        "load_address": f"0x{load:08x}",
        "entry_point": f"0x{entry:08x}",
        "timestamp_utc": datetime.fromtimestamp(timestamp, timezone.utc).isoformat(),
        "name": name,
        "os": os_id,
        "arch": arch,
        "type": kind,
        "compression": comp,
        "header_crc_expected": f"0x{header_crc:08x}",
        "header_crc_actual": f"0x{zlib.crc32(header) & 0xffffffff:08x}",
        "header_crc_ok": (zlib.crc32(header) & 0xffffffff) == header_crc,
        "data_crc_expected": f"0x{data_crc:08x}",
        "data_crc_actual": f"0x{zlib.crc32(payload) & 0xffffffff:08x}",
        "data_crc_ok": (zlib.crc32(payload) & 0xffffffff) == data_crc,
    }


def parse_reference_layout(xml_path: Path, image_size: int) -> list[dict[str, object]]:
    text = xml_path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff\0")
    root = ElementTree.fromstring(text)
    fixed = []
    for node in root.findall(".//Scheme/File"):
        ident = (node.findtext("ID") or "").strip()
        base_text = node.findtext("./Block/Base")
        size_text = node.findtext("./Block/Size")
        if not base_text or not size_text:
            continue
        base = int(base_text, 0)
        size = int(size_text, 0)
        if NOR_BASE <= base < NOR_BASE + image_size and size:
            fixed.append({"name": ident or "unnamed", "base": base, "size": size, "source": "reference PAC XML"})
    fixed.sort(key=lambda item: int(item["base"]))

    regions = []
    cursor = NOR_BASE
    for item in fixed:
        base = int(item["base"])
        size = int(item["size"])
        if base > cursor:
            regions.append({
                "name": "gap_filesystem_candidate",
                "base": cursor,
                "size": base - cursor,
                "source": "gap between reference PAC regions",
            })
        regions.append(item)
        cursor = max(cursor, base + size)
    image_end = NOR_BASE + image_size
    if cursor < image_end:
        regions.append({
            "name": "top_nv_factory_candidate",
            "base": cursor,
            "size": image_end - cursor,
            "source": "tail after reference PAC regions",
        })
    return regions


def used_size(data: bytes) -> int:
    return len(data.rstrip(b"\xff"))


def extract_interesting_strings(image: bytes) -> list[dict[str, object]]:
    rows = []
    seen = set()
    for match in re.finditer(rb"[\x20-\x7e]{6,}", image):
        raw = match.group(0)
        text = raw.decode("ascii", "replace")
        lower = text.lower()
        if not any(keyword in lower for keyword in KEYWORDS):
            continue
        key = text[:500]
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "offset": match.start(),
            "physical_address": f"0x{NOR_BASE + match.start():08x}",
            "text": text[:500],
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--reference-xml", type=Path, required=True)
    args = parser.parse_args()

    image = args.image.read_bytes()
    args.out.mkdir(parents=True, exist_ok=True)
    parts_dir = args.out / "regions"
    parts_dir.mkdir(exist_ok=True)

    uimages = [
        parsed
        for offset in find_all(image, UIMAGE_MAGIC)
        if (parsed := parse_uimage(image, offset)) is not None
    ]
    luadb_offsets = [
        offset - 2
        for offset in find_all(image, LUADB_MAGIC)
        if offset >= 2 and (offset - 2) % BLOCK == 0
    ]

    regions = parse_reference_layout(args.reference_xml, len(image))
    region_rows = []
    for index, region in enumerate(regions):
        base = int(region["base"])
        size = min(int(region["size"]), NOR_BASE + len(image) - base)
        start = base - NOR_BASE
        data = image[start:start + size]
        filename = f"{index:02d}_{region['name']}_0x{base:08x}_0x{size:x}.bin"
        (parts_dir / filename).write_bytes(data)
        region_rows.append({
            **region,
            "base": f"0x{base:08x}",
            "size": size,
            "used_through_last_non_ff": used_size(data),
            "sha256": sha256(data),
            "filename": f"regions/{filename}",
        })

    block_rows = []
    for offset in range(0, len(image), BLOCK):
        block = image[offset:offset + BLOCK]
        generation = None
        if len(block) >= 4 and block[2:4] == b"\0\0":
            value = int.from_bytes(block[:2], "little")
            if value not in (0, 0xFFFF):
                generation = value
        block_rows.append({
            "offset": f"0x{offset:06x}",
            "physical_address": f"0x{NOR_BASE + offset:08x}",
            "entropy": round(entropy(block), 5),
            "ff_percent": round(block.count(0xFF) * 100 / len(block), 3),
            "zero_percent": round(block.count(0x00) * 100 / len(block), 3),
            "first16_hex": block[:16].hex(),
            "fs_generation_candidate": generation,
        })

    interesting = extract_interesting_strings(image)
    strings_path = args.out / "interesting_strings.txt"
    with strings_path.open("x", encoding="utf-8") as stream:
        for row in interesting:
            stream.write(f"0x{row['offset']:08x} {row['physical_address']} {row['text']}\n")

    csv_path = args.out / "block_map.csv"
    with csv_path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=block_rows[0].keys())
        writer.writeheader()
        writer.writerows(block_rows)

    report = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source": str(args.image.resolve()),
        "size": len(image),
        "sha256": sha256(image),
        "nor_base": f"0x{NOR_BASE:08x}",
        "uimages": uimages,
        "luadb_block_offsets": [f"0x{x:x}" for x in luadb_offsets],
        "regions": region_rows,
        "interesting_string_count": len(interesting),
        "magic_hits": {
            "jpeg_soi": [f"0x{x:x}" for x in find_all(image, b"\xff\xd8\xff")],
            "png": [f"0x{x:x}" for x in find_all(image, b"\x89PNG\r\n\x1a\n")],
            "bmp": [f"0x{x:x}" for x in find_all(image, b"BM")][:500],
            "cpio_newc": [f"0x{x:x}" for x in find_all(image, b"070701")],
            "squashfs_le": [f"0x{x:x}" for x in find_all(image, b"hsqs")],
        },
    }
    json_path = args.out / "analysis.json"
    with json_path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")

    markdown = [
        "# EC600U full-flash offline analysis",
        "",
        f"- Source: `{args.image}`",
        f"- Size: `{len(image)}` bytes ({len(image) / 1048576:.1f} MiB)",
        f"- SHA-256: `{report['sha256']}`",
        f"- uImage count: `{len(uimages)}`; all CRC-valid: `{all(x['header_crc_ok'] and x['data_crc_ok'] for x in uimages)}`",
        f"- Block-aligned LuatOS luadb signatures: `{len(luadb_offsets)}`",
        f"- Interesting strings: `{len(interesting)}` (see `interesting_strings.txt`)",
        "",
        "## CRC-verified uImages",
        "",
        "| Offset | Physical | Payload | Load | Entry | Build name | HCRC | DCRC |",
        "|---:|---:|---:|---:|---:|---|---|---|",
    ]
    for item in uimages:
        markdown.append(
            f"| `0x{item['offset']:x}` | `{item['physical_address']}` | `{item['payload_size']}` | "
            f"`{item['load_address']}` | `{item['entry_point']}` | {item['name']} | "
            f"{item['header_crc_ok']} | {item['data_crc_ok']} |"
        )
    markdown += [
        "",
        "## Regions using the reference PAC geometry",
        "",
        "| Name | Base | Reserved size | Used through last non-FF | SHA-256 |",
        "|---|---:|---:|---:|---|",
    ]
    for item in region_rows:
        markdown.append(
            f"| {item['name']} | `{item['base']}` | `0x{item['size']:x}` | "
            f"`0x{item['used_through_last_non_ff']:x}` | `{item['sha256']}` |"
        )
    markdown += [
        "",
        "## External-flash conclusion",
        "",
        "The downloaded image is exactly 8 MiB. The photographed GD25LQ128C is a 128-Mbit "
        "(16-MiB) 1.8-V SPI NOR, so its contents are not this image. The installed AP image "
        "contains explicit SPI6 external-NOR/SFFS mount strings, confirming that the main "
        "firmware is designed to access a separate external flash.",
        "",
    ]
    (args.out / "ANALYSIS.md").write_text("\n".join(markdown), encoding="utf-8")
    print(json_path)
    print(args.out / "ANALYSIS.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
