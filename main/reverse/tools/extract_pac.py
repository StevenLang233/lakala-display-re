#!/usr/bin/env python3
"""Validate and extract payloads from a Spreadtrum/UNISOC PAC file.

Offline only: this script never opens a USB device and has no flash path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'demo/third_party'))
from sprdflash.flasher import classify
from sprdflash.pac import parse_pac


def safe_name(text: str, fallback: str) -> str:
    name = Path(text).name if text else fallback
    return re.sub(r"[^A-Za-z0-9._+-]", "_", name)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pac", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()

    info = parse_pac(args.pac, verify_payload=True)
    if not info.crc_ok:
        raise SystemExit("PAC CRC validation failed")
    args.out.mkdir(parents=True, exist_ok=True)

    manifest = {
        "source": str(args.pac.resolve()),
        "source_sha256": hashlib.sha256(args.pac.read_bytes()).hexdigest(),
        "product": info.product_name,
        "version": info.product_version,
        "entries": [],
    }
    with args.pac.open("rb") as pac:
        for index, entry in enumerate(info.entries):
            row = {
                "index": index,
                "id": entry.file_id,
                "role": classify(entry),
                "address": f"0x{entry.address:08x}",
                "offset": entry.offset,
                "size": entry.size,
                "filename": None,
                "sha256": None,
            }
            if entry.size:
                pac.seek(entry.offset)
                data = pac.read(entry.size)
                if len(data) != entry.size:
                    raise SystemExit(f"short read for {entry.file_id}")
                filename = f"{index:02d}_{safe_name(entry.file_name, entry.file_id or 'entry.bin')}"
                target = args.out / filename
                target.write_bytes(data)
                row["filename"] = filename
                row["sha256"] = hashlib.sha256(data).hexdigest()
            manifest["entries"].append(row)

    manifest_path = args.out / "manifest.json"
    with manifest_path.open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
