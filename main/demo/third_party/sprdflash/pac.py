"""Parser for SPRD/UNISOC firmware package (.pac) files.

The format is the one produced by the vendor ``dtools``/ResearchDownload
toolchain (and Luatools' ``pacgen``): a fixed-size UTF-16LE header, a table
of per-file headers, then the raw payloads. Two CRC16 values protect the
header and the payload area.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

PAC_HEADER_FMT = '<48sI512s512s7I200s3I800sI2H'
FILE_HEADER_FMT = '<I512s512s512s6I5I996s'
PAC_HEADER_SIZE = struct.calcsize(PAC_HEADER_FMT)
FILE_HEADER_SIZE = struct.calcsize(FILE_HEADER_FMT)

PAC_MAGIC = 0xFFFAFFFA

# CRC16 (IBM/ARC polynomial, table-driven) as used by the PAC format.
_CRC16_TABLE = []
for _i in range(256):
    _crc = _i
    for _ in range(8):
        _crc = (_crc >> 1) ^ 0xA001 if _crc & 1 else _crc >> 1
    _CRC16_TABLE.append(_crc)


def crc16(data: bytes, crc: int = 0) -> int:
    for b in data:
        crc = (crc >> 8) ^ _CRC16_TABLE[(crc ^ b) & 0xFF]
    return crc


def _utf16z(raw: bytes) -> str:
    """Decode a NUL-terminated UTF-16LE fixed-size field."""
    text = raw.decode('utf-16le', errors='replace')
    nul = text.find('\x00')
    return text if nul < 0 else text[:nul]


@dataclass
class PacEntry:
    file_id: str
    file_name: str
    size: int
    offset: int
    address: int
    flag: int
    omit: int

    @property
    def is_marker(self) -> bool:
        """True for pseudo-entries (erase markers, phase check) without payload."""
        return self.size == 0


@dataclass
class PacInfo:
    version: str
    product_name: str
    product_version: str
    size: int
    file_count: int
    mode: int
    flash_type: int
    magic: int
    header_crc_ok: bool
    payload_crc_ok: bool | None
    entries: list[PacEntry]

    @property
    def crc_ok(self) -> bool:
        return self.header_crc_ok and self.payload_crc_ok is not False


def parse_pac(path: str | Path, verify_payload: bool = True) -> PacInfo:
    """Parse and validate *path*; raises ValueError on malformed files."""
    path = Path(path)
    file_size = path.stat().st_size
    if file_size < PAC_HEADER_SIZE:
        raise ValueError(f'{path.name}: too small to be a PAC file ({file_size} bytes)')
    with open(path, 'rb') as f:
        header = f.read(PAC_HEADER_SIZE)
        (version, pac_size, prd_name, prd_version, file_count, file_offset,
         mode, flash_type, _nand_strategy, _is_nv_backup, _nand_page_type,
         _prd_alias, _oma_dm_flag, _is_oma_dm, _is_preload, _other,
         magic, crc1, crc2) = struct.unpack(PAC_HEADER_FMT, header)

        header_crc_ok = crc16(header[:-4]) == crc1
        if pac_size != file_size:
            raise ValueError(
                f'{path.name}: header size field {pac_size} != actual file size {file_size} (truncated download?)')

        entries: list[PacEntry] = []
        f.seek(file_offset)
        for _ in range(file_count):
            fh = f.read(FILE_HEADER_SIZE)
            if len(fh) != FILE_HEADER_SIZE:
                raise ValueError(f'{path.name}: truncated file table')
            (_hsize, file_id, file_name, _unused, data_size, flag, _check,
             data_offset, omit, _u2, address, *_rest) = struct.unpack(FILE_HEADER_FMT, fh)
            entries.append(PacEntry(
                file_id=_utf16z(file_id),
                file_name=_utf16z(file_name),
                size=data_size,
                offset=data_offset,
                address=address,
                flag=flag,
                omit=omit,
            ))

        payload_crc_ok: bool | None = None
        if verify_payload:
            payload_crc_ok = _verify_payload_crc(f, crc2)

    return PacInfo(
        version=_utf16z(version),
        product_name=_utf16z(prd_name),
        product_version=_utf16z(prd_version),
        size=pac_size,
        file_count=file_count,
        mode=mode,
        flash_type=flash_type,
        magic=magic,
        header_crc_ok=header_crc_ok,
        payload_crc_ok=payload_crc_ok,
        entries=entries,
    )


def _verify_payload_crc(f: BinaryIO, expected: int) -> bool:
    f.seek(PAC_HEADER_SIZE)
    crc = 0
    while True:
        chunk = f.read(1 << 20)
        if not chunk:
            break
        crc = crc16(chunk, crc)
    return crc == expected
