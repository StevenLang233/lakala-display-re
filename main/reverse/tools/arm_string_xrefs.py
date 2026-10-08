#!/usr/bin/env python3
"""Find ARM/Thumb PC-relative references to selected strings in a raw image."""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_LITTLE_ENDIAN, CS_MODE_THUMB
from capstone.arm import ARM_OP_MEM, ARM_REG_PC


def literal_target(insn):
    for operand in insn.operands:
        if operand.type != ARM_OP_MEM or operand.mem.base != ARM_REG_PC:
            continue
        if insn.id == 0:
            continue
        pc = insn.address + (4 if insn.size == 2 else 4 if "thumb" in insn.mnemonic else 8)
        if insn.size in (2, 4) and insn.address & 1 == 0:
            # Thumb literal loads use Align(PC,4); ARM uses PC+8. The caller
            # tries both interpretations to avoid relying on mnemonic labels.
            return ((insn.address + 4) & ~3) + operand.mem.disp, insn.address + 8 + operand.mem.disp
    return None


def one_instruction(md: Cs, data: bytes, off: int, base: int):
    items = list(md.disasm(data[off:off + 4], base + off, count=1))
    return items[0] if items else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--base", type=lambda value: int(value, 0), default=0x60000000)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("strings", nargs="+")
    args = parser.parse_args()
    data = args.image.read_bytes()

    arm = Cs(CS_ARCH_ARM, CS_MODE_ARM | CS_MODE_LITTLE_ENDIAN)
    thumb = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
    arm.detail = thumb.detail = True
    results = []

    for text in args.strings:
        raw = text.encode("ascii")
        start = 0
        while True:
            string_off = data.find(raw, start)
            if string_off < 0:
                break
            string_addr = args.base + string_off
            pointer = struct.pack("<I", string_addr)
            pointer_offsets = []
            p = 0
            while True:
                p = data.find(pointer, p)
                if p < 0:
                    break
                pointer_offsets.append(p)
                p += 1

            xrefs = []
            for pointer_off in pointer_offsets:
                literal_addr = args.base + pointer_off
                scan_start = max(0, pointer_off - 0x1000)
                for off in range(scan_start & ~3, pointer_off, 4):
                    insn = one_instruction(arm, data, off, args.base)
                    if not insn or not insn.mnemonic.startswith("ldr"):
                        continue
                    target = literal_target(insn)
                    if target and literal_addr in target:
                        xrefs.append({
                            "mode": "arm", "offset": off,
                            "address": f"0x{args.base + off:08x}",
                            "instruction": f"{insn.mnemonic} {insn.op_str}",
                            "literal_offset": pointer_off,
                        })
                for off in range(scan_start & ~1, pointer_off, 2):
                    insn = one_instruction(thumb, data, off, args.base)
                    if not insn or not insn.mnemonic.startswith("ldr"):
                        continue
                    target = literal_target(insn)
                    if target and literal_addr in target:
                        xrefs.append({
                            "mode": "thumb", "offset": off,
                            "address": f"0x{args.base + off:08x}",
                            "instruction": f"{insn.mnemonic} {insn.op_str}",
                            "literal_offset": pointer_off,
                        })
            results.append({
                "string": text,
                "string_offset": string_off,
                "string_address": f"0x{string_addr:08x}",
                "pointer_offsets": pointer_offsets,
                "xrefs": xrefs,
            })
            start = string_off + 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(results, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(args.out)
    for row in results:
        print(
            f"{row['string']!r} @ {row['string_address']}: "
            f"{len(row['pointer_offsets'])} pointers, {len(row['xrefs'])} xrefs"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
