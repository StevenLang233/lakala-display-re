#!/usr/bin/env python3
"""Disassemble a selected ARM or Thumb range from a raw mapped image."""

from __future__ import annotations

import argparse
from pathlib import Path

from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_LITTLE_ENDIAN, CS_MODE_THUMB


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("address", type=lambda value: int(value, 0))
    parser.add_argument("size", type=lambda value: int(value, 0))
    parser.add_argument("--base", type=lambda value: int(value, 0), default=0x60000000)
    parser.add_argument("--mode", choices=("arm", "thumb"), default="thumb")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    image = args.image.read_bytes()
    address = args.address & ~1 if args.mode == "thumb" else args.address & ~3
    offset = address - args.base
    if offset < 0 or offset + args.size > len(image):
        raise SystemExit("requested range falls outside the image")
    mode = CS_MODE_LITTLE_ENDIAN | (CS_MODE_THUMB if args.mode == "thumb" else CS_MODE_ARM)
    md = Cs(CS_ARCH_ARM, mode)
    md.skipdata = True
    lines = []
    for insn in md.disasm(image[offset:offset + args.size], address):
        raw = insn.bytes.hex(" ")
        lines.append(f"0x{insn.address:08x}: {raw:<14} {insn.mnemonic:<10} {insn.op_str}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as stream:
        stream.write("\n".join(lines))
        stream.write("\n")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
