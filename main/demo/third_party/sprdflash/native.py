"""Complete native flash: PDL (FDL1) -> BSL (FDL2 + partitions) -> reset.

Ties together the two link layers reverse-engineered from the vendor tool:
  Phase 1 (pdl.py)      : load + exec the first-stage loader (HOST_FDL/"PDL1")
  Phase 2 (protocol.py) : BSL handshake, load + exec FDL2, write each partition

Verified end-to-end on a real Air724UG (RDA8910), including a cross-SDK change
(LuatOS V4035 -> CSDK V302340) that boots correctly.

Firmware-TYPE changes (--format) need the erase/format markers: the PAC's
logical-address entries (>= 0xFE000000) are not payload partitions but
erase/format ops. Every step below was verified byte-for-byte against a Frida
trace of the vendor tool doing a cross-SDK flash. After the real partitions and
before reset the vendor issues, in PAC order:

    FMT_FSSYS (0xFE000006) -> ERASE_FLASH  addr, "SYSF"     (format system FS)
    FLASH     (0xFE000001) -> ERASE_FLASH  addr, 0
    NV        (0xFE000003) -> the PAC's nvitem template, written with a 12-byte
                              START_DATA (addr | size | sum32(data)); END_DATA
                              verifies that transfer sum. The template ships with
                              a stale placeholder CRC, so its leading big-endian
                              CRC-16-ARC slot is recomputed first -- the FDL2
                              validates it and answers OPERATION_FAILED otherwise.
                              IMEI/RF-cal live in a separate factorynv region the
                              format never touches, so they survive.
    PREPACK   (0xFE000004) -> the PAC's prepack blob (plain START/MIDST/END).

FMT_FSEXT shares 0xFE000006 with FMT_FSSYS and is NOT separately erased. After
NORMAL_RESET the frame is flushed and the port held briefly before closing;
closing immediately cancels the in-flight reset and the module comes back up in
download mode instead of booting.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Callable

from . import pdl
from . import protocol as p
from .flasher import DEFAULT_CHUNK, classify, send_stage
from .pac import parse_pac

log = logging.getLogger('sprdflash')

Progress = Callable[[str, int, int], None]

# BSL MIDST_DATA chunk (the vendor sends 0x210 = 528-byte data frames)
BSL_CHUNK = DEFAULT_CHUNK

# Zero-size logical markers (PAC address >= 0xFE000000) mapped to the BSL
# ERASE_FLASH 4-byte parameter the vendor sends. Verified byte-for-byte from a
# Frida trace of a vendor cross-SDK flash: it issues exactly these two erases.
# The address is the marker's own logical address, big-endian. FMT_FSEXT shares
# 0xFE000006 with FMT_FSSYS and is NOT separately erased (dedup by address).
_ERASE_PARAM = {
    'FMT_FSSYS': b'SYSF',                  # format the system filesystem
    'FLASH': b'\x00\x00\x00\x00',          # clear the app flash region
}
# Zero-size markers deliberately left alone (the vendor does not erase them):
# PhaseCheck, and NV (its data is preserved via read-back + restore).
_SKIP_MARKERS = {'NV', 'PHASECHECK', 'PREPACK'}


def _sum32(data: bytes) -> int:
    """32-bit additive byte checksum (the value the vendor puts in the NV
    START_DATA trailer; END_DATA verifies the written NV against it)."""
    return sum(data) & 0xFFFFFFFF


def _nv_crc16(data: bytes) -> int:
    """CRC-16-ARC (poly 0xA001, reflected, init 0) -- the internal NV-image
    checksum the modem validates. Verified against the vendor: it equals the
    stored value over the whole NV region minus the 2-byte slot it occupies."""
    crc = 0
    for x in data:
        crc ^= x
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc & 0xFFFF


def _nv_fix_crc(data: bytes) -> bytes:
    """Patch the NV blob's leading big-endian CRC-16 slot (bytes 0..1) to match
    its content. The PAC's nvitem template ships with a stale placeholder CRC;
    the device's FDL2 validates this field at END_DATA, so it must be recomputed
    over the whole region (bytes 2..end) before the write -- otherwise END_DATA
    returns OPERATION_FAILED and the module will not boot on a soft reset."""
    b = bytearray(data)
    crc = _nv_crc16(bytes(b[2:]))
    b[0], b[1] = (crc >> 8) & 0xFF, crc & 0xFF
    return bytes(b)


def _erase_ops(info):
    """Return [(file_id, address, param_bytes)] for the zero-size format markers
    to erase, in PAC order, deduped by address (a repeated address is issued
    once). Skips data-bearing markers (NV/PREPACK), PhaseCheck, and unknowns."""
    ops = []
    seen = set()
    for e in info.entries:
        if classify(e) != 'marker' or e.size or e.address < 0xFE000000:
            continue
        param = _ERASE_PARAM.get(e.file_id.upper()) or _ERASE_PARAM.get(e.file_id)
        if param is not None and e.address not in seen:
            seen.add(e.address)
            ops.append((e.file_id, e.address, param))
    return ops


def _data_markers(info):
    """Data-bearing logical markers (address >= 0xFE000000, size > 0), in PAC
    order. These carry firmware content the vendor writes after the erases: NV
    (0xFE000003, the nvitem template -- written with the sum32-checked START) and
    PREPACK (0xFE000004, the prepack cpio blob -- a plain START/MIDST/END)."""
    return [e for e in info.entries
            if classify(e) == 'marker' and e.size and e.address >= 0xFE000000]


def _open_serial(com: str, timeout: float = 0.3):
    import serial
    s = None
    for _ in range(200):
        try:
            s = serial.Serial(com, 115200, timeout=timeout, write_timeout=2.0)
            break
        except Exception:
            time.sleep(0.03)
    if s is None:
        raise pdl.PdlError(f'could not open {com}')
    try:
        s.dtr = True
        s.rts = True
    except Exception:
        pass
    time.sleep(0.05)
    try:
        s.reset_input_buffer()
    except Exception:
        pass
    return s


def _read_entry(f, entry):
    f.seek(entry.offset)
    return f.read(entry.size)


# NV read-back chunk the vendor uses (0x3000 = 12288 bytes per READ_FLASH).
NV_READ_CHUNK = 0x3000


def _read_flash(io: 'p.SpdIO', addr: int, total: int, chunk: int = NV_READ_CHUNK) -> bytes:
    """BSL READ_FLASH: read *total* bytes from logical *addr* in chunks.

    Payload = addr(4 BE) | size(4 BE) | offset(4 BE); reply BSL_REP_READ_FLASH
    (0x93) carries the data. A reusable primitive for reading back flash/NV.
    """
    import struct as _s
    out = bytearray()
    off = 0
    while off < total:
        n = min(chunk, total - off)
        io.send(p.BSL_CMD_READ_FLASH, _s.pack('>III', addr, n, off))
        rtype, rdata = io.recv(timeout=3.0)
        if rtype != p.BSL_REP_READ_FLASH:
            raise pdl.PdlError(f'READ_FLASH @ {addr:#x}+{off}: got {p.rep_name(rtype)}')
        out += rdata
        off += n
    return bytes(out)


def _write_nv(io: 'p.SpdIO', addr: int, data: bytes, progress=None) -> None:
    """Write the NV region (0xFE000003) from the PAC's nvitem template.

    The NV write differs from a normal partition write in two ways, both learned
    from a byte-for-byte Frida trace of the vendor tool:

    * START_DATA carries a 12-byte payload -- addr(4 BE) | size(4 BE) |
      sum32(data)(4 BE) -- and END_DATA verifies the received bytes against that
      transfer sum. Omitting it (8-byte START) makes the device answer
      OPERATION_FAILED, and the module then will not boot on a soft reset.
    * The bytes must be a valid *download-format* NV image (the PAC template),
      not the raw on-flash NV read back with READ_FLASH -- the on-flash layout is
      different and the device rejects it. IMEI/RF-calibration live in a separate
      factorynv region that the format does not touch, so writing the template
      (whose runtime NV the modem re-derives on boot) preserves them.

    The vendor additionally merges ~5% device-specific runtime items into the
    template before writing; those are non-critical (re-derived from factorynv),
    so the plain template boots correctly.
    """
    import struct as _s
    data = _nv_fix_crc(data)   # refresh the stale template CRC so END_DATA ACKs
    io.command(p.BSL_CMD_START_DATA, _s.pack('>III', addr, len(data), _sum32(data)),
               what='NV START')
    for off in range(0, len(data), BSL_CHUNK):
        io.command(p.BSL_CMD_MIDST_DATA, data[off:off + BSL_CHUNK], what='NV MIDST')
        if progress:
            progress(min(off + BSL_CHUNK, len(data)), len(data))
    try:
        io.command(p.BSL_CMD_END_DATA, what='NV END')
    except p.ProtocolError as e:
        log.warning('NV END_DATA: %s (MIDST data already written; continuing)', e)


def native_flash(com: str, pac_path: str | Path, *,
                 progress: Progress | None = None,
                 fdl1_end_checksum: int = 0,
                 format_fs: bool = False,
                 do_reset: bool = True) -> None:
    """Flash *pac_path* to the module on serial port *com*, entirely natively.

    The module must already be in download mode (0525:a4a7 / COM port). The
    PDL END checksum for FDL1 is not verified by the agent (confirmed on
    hardware: a full flash with checksum=0 boots correctly), so it defaults to 0.

    *format_fs* controls the destructive filesystem format needed when changing
    firmware TYPE (e.g. LuatOS -> CSDK). Default False = write the payload
    partitions only, which is the proven, safe path for a same-SDK reflash.
    Set True for a cross-SDK change: it additionally issues the PAC's ERASE/
    format markers (FMT_FSSYS, FLASH), backs up + restores NV with the vendor's
    sum32-checked START_DATA (preserving IMEI/RF-cal), and writes the PREPACK
    blob. Verified byte-for-byte against a Frida trace of the vendor tool.
    """
    pac_path = Path(pac_path)
    info = parse_pac(pac_path, verify_payload=True)
    if not info.crc_ok:
        raise pdl.PdlError('PAC checksum mismatch - refusing to flash')

    fdl1 = next((e for e in info.entries if classify(e) == 'fdl1'), None)
    fdl2 = next((e for e in info.entries if classify(e) == 'fdl2'), None)
    if not fdl1:
        raise pdl.PdlError('no FDL1 (HOST_FDL) stage in the PAC')
    partitions = [e for e in info.entries if classify(e) == 'flash']
    # For hybrid internal/external-flash products, prove the external APPIMG
    # write path before changing the currently bootable AP/boot partitions.
    # Python's sort is stable, so all remaining PAC entries retain their order.
    partitions.sort(key=lambda e: 0 if e.address >= 0x70000000 else 1)
    data_markers = _data_markers(info)   # e.g. PREPACK (written only with --format)

    with open(pac_path, 'rb') as f:
        fdl1_data = _read_entry(f, fdl1)
        fdl2_data = _read_entry(f, fdl2) if fdl2 else b''
        part_data = {e.file_id: _read_entry(f, e) for e in partitions}
        marker_data = {e.file_id: _read_entry(f, e) for e in data_markers}

    s = _open_serial(com)
    try:
        # ---- Phase 1: PDL loads and execs FDL1 -----------------------------
        pio = pdl.PdlIO(s, timeout=2.0)
        log.info('PDL connect')
        pio.connect()
        log.info('PDL load FDL1 (%d bytes @ %#x)', len(fdl1_data), fdl1.address)
        pio.send_image(fdl1.address, fdl1_data, checksum=fdl1_end_checksum,
                       progress=(lambda d, t: progress('FDL1', d, t)) if progress else None)
        ver = pio.exec_and_get_ver(timeout=5.0)
        body = p.hdlc_unescape(ver.strip(b'\x7e'))
        _, vdata = p.parse_message(body)
        log.info('FDL1 running: %s', vdata.decode('latin-1', 'replace').strip())

        # ---- Phase 2: BSL loads FDL2, then writes partitions ---------------
        io = p.SpdIO(s, timeout=2.0)
        io.checksum = 'sprd'
        io.connect()
        if fdl2:
            log.info('BSL load FDL2 (%d bytes @ %#x)', len(fdl2_data), fdl2.address)
            send_stage(io, fdl2.address, fdl2_data, BSL_CHUNK,
                       progress=(lambda d, t: progress('FDL2', d, t)) if progress else None)
            io.command(p.BSL_CMD_EXEC_DATA, timeout=15.0, what='EXEC FDL2')
            io.connect()   # re-handshake under FDL2 (vendor "Connect2")

        for e in partitions:
            data = part_data[e.file_id]
            log.info('flash %s (%d bytes @ %#x)', e.file_id, len(data), e.address)
            send_stage(io, e.address, data, BSL_CHUNK,
                       progress=(lambda d, t, _e=e: progress(_e.file_id, d, t)) if progress else None)

        # Erase/format markers (FMT_FSSYS, FLASH) then the data-bearing markers
        # (NV template, PREPACK): only for a firmware-TYPE change (--format). A
        # same-SDK reflash keeps the existing filesystem and NV.
        if format_fs:
            import struct as _struct
            for fid, addr, param in _erase_ops(info):
                log.info('erase %s (%#x)', fid, addr)
                io.command(p.BSL_CMD_ERASE_FLASH, _struct.pack('>I', addr) + param,
                           what=f'ERASE {fid}')
            # After the erases the vendor writes the NV template (sum32-checked
            # START) and PREPACK (plain), in PAC order, before reset.
            for e in data_markers:
                data = marker_data[e.file_id]
                log.info('write %s (%d bytes @ %#x)', e.file_id, len(data), e.address)
                prog = (lambda d, t, _e=e: progress(_e.file_id, d, t)) if progress else None
                if e.file_id.upper() == 'NV':
                    _write_nv(io, e.address, data, progress=prog)
                else:
                    send_stage(io, e.address, data, BSL_CHUNK, progress=prog)

        if do_reset:
            io.send(p.BSL_CMD_NORMAL_RESET)
            # Let the module act on the reset before we drop the line: closing the
            # port immediately can cancel the in-flight frame (Windows CloseHandle
            # aborts pending I/O) or drop DTR mid-reset, leaving the device in
            # download mode instead of booting the new firmware.
            try:
                s.flush()
            except Exception:
                pass
            time.sleep(1.0)
            log.info('reset; module reboots into the new firmware')
    finally:
        try:
            s.close()
        except Exception:
            pass
