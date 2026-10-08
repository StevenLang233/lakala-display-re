"""High-level flash flow built on the BSL protocol: connect, load FDLs, write
partitions from a parsed .pac, reset.
"""
from __future__ import annotations

import logging
import struct
import time
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Callable

from . import protocol as p
from .pac import PAC_HEADER_SIZE, PacEntry, PacInfo, parse_pac

log = logging.getLogger('sprdflash')

DEFAULT_CHUNK = 528  # matches spd_dump's default MIDST_DATA step

# PAC "address" values >= this are logical markers (erase/format/phasecheck),
# not real load addresses.
LOGICAL_ADDRESS_BASE = 0xFE000000

# File-id substrings identifying the two FDL stages inside a PAC.
FDL1_IDS = ('HOST_FDL', 'FDL', 'FDL1')
FDL2_IDS = ('FDL2',)


class FlashError(RuntimeError):
    pass


def classify(entry: PacEntry) -> str:
    """Return 'fdl1', 'fdl2', 'marker', or 'flash' for a PAC entry.

    Order matters: markers (zero size, address 0, or a logical >=0xFE000000
    address) win first, then FDL2 before FDL1 so 'FDL2' is not swallowed by
    the 'FDL' prefix used to spot FDL1.
    """
    fid = entry.file_id.upper()
    if entry.size == 0 or entry.address == 0 or entry.address >= LOGICAL_ADDRESS_BASE:
        return 'marker'
    if any(fid == x or fid.startswith(x) for x in FDL2_IDS):
        return 'fdl2'
    if any(fid == x or fid.startswith(x) for x in FDL1_IDS):
        return 'fdl1'
    return 'flash'


@dataclass
class Stage:
    entry: PacEntry
    data: bytes


def _read_entry(f: BinaryIO, entry: PacEntry) -> bytes:
    f.seek(entry.offset)
    data = f.read(entry.size)
    if len(data) != entry.size:
        raise FlashError(f'{entry.file_id}: short read '
                         f'({len(data)}/{entry.size} bytes)')
    return data


def _find_stage(info: PacInfo, f: BinaryIO, role: str) -> Stage | None:
    """Locate the FDL1 or FDL2 stage by classification (role='fdl1'|'fdl2')."""
    for entry in info.entries:
        if entry.size and classify(entry) == role:
            return Stage(entry, _read_entry(f, entry))
    return None


def send_stage(io: p.SpdIO, addr: int, data: bytes, chunk: int,
               progress: Callable[[int, int], None] | None = None) -> None:
    """START_DATA(addr,size) -> MIDST_DATA* -> END_DATA."""
    io.command(p.BSL_CMD_START_DATA, struct.pack('>II', addr, len(data)),
               what='START_DATA')
    sent = 0
    total = len(data)
    while sent < total:
        piece = data[sent:sent + chunk]
        io.command(p.BSL_CMD_MIDST_DATA, piece, what='MIDST_DATA')
        sent += len(piece)
        if progress:
            progress(sent, total)
    io.command(p.BSL_CMD_END_DATA, what='END_DATA')


def _open_transport(transport: str, device: str | None, baudrate: int, timeout: float):
    """Return a serial-port-like object for the chosen transport.

    'usb' (default) drives the BootROM bulk endpoints via libusb - the only
    transport that works for the RDA8910 USB gadget. 'serial' opens a COM port
    for targets that expose BSL over a plain UART.
    """
    if transport == 'usb':
        from .usb_transport import open_usb_port
        return open_usb_port(timeout=timeout)
    import serial
    if not device:
        raise FlashError('serial transport requires --port COMx')
    # Use a SHORT read timeout: SpdIO._read_frame polls one byte at a time and
    # manages its own deadline, so pyserial's per-read block must be brief -
    # otherwise autobaud's many short retries each stall on the full port
    # timeout. DTR/RTS are asserted so a CDC-ACM gadget's device-side port
    # gets carrier (required for it to start responding).
    s = serial.Serial(device, baudrate, timeout=0.02, write_timeout=timeout)
    try:
        s.dtr = True
        s.rts = True
    except (OSError, serial.SerialException):
        pass
    return s


def connect_bootrom(device: str | None = None, baudrate: int = 115200,
                    timeout: float = 2.0, transport: str = 'usb') -> tuple[p.SpdIO, bytes]:
    """Open the download port and complete the BootROM autobaud + CONNECT.

    Returns (io, version_bytes). Non-destructive - safe for `identify`.
    """
    port = _open_transport(transport, device, baudrate, timeout)
    io = p.SpdIO(port, timeout=timeout)
    io.crc_mode = True
    version = io.autobaud()
    io.connect()
    return io, version


def load_fdls(io: p.SpdIO, info: PacInfo, f: BinaryIO, chunk: int,
              on_stage: Callable[[str], None] | None = None) -> None:
    """Send FDL1, exec it, re-handshake in FDL (sum-checksum) mode, send FDL2,
    exec it. After this the device is ready for partition writes."""
    fdl1 = _find_stage(info, f, 'fdl1')
    fdl2 = _find_stage(info, f, 'fdl2')
    if not fdl1:
        raise FlashError('no FDL1 (HOST_FDL) stage found in the PAC file')

    if on_stage:
        on_stage(f'FDL1 {fdl1.entry.file_id} @ 0x{fdl1.entry.address:08X} '
                 f'({len(fdl1.data)} bytes)')
    send_stage(io, fdl1.entry.address, fdl1.data, chunk)
    io.command(p.BSL_CMD_EXEC_DATA, what='EXEC FDL1')

    # FDL1 is now running; it speaks the sum-checksum dialect and must be
    # re-handshaked.
    io.crc_mode = False
    time.sleep(0.2)
    io.autobaud(attempts=10, timeout=0.5)
    io.connect()

    if fdl2:
        if on_stage:
            on_stage(f'FDL2 {fdl2.entry.file_id} @ 0x{fdl2.entry.address:08X} '
                     f'({len(fdl2.data)} bytes)')
        send_stage(io, fdl2.entry.address, fdl2.data, chunk)
        # EXEC of FDL2 can take longer to come back.
        io.command(p.BSL_CMD_EXEC_DATA, timeout=15.0, what='EXEC FDL2')


def flashable_entries(info: PacInfo) -> list[PacEntry]:
    """Real payload partitions to write, excluding the FDL stages, the logical
    erase/format markers, and address-0 manifests (e.g. the trailing XML)."""
    return [e for e in info.entries if classify(e) == 'flash']


def flash_pac(device: str | None, pac_path: str | Path, *, baudrate: int = 115200,
              chunk: int = DEFAULT_CHUNK, do_reset: bool = True,
              progress: Callable[[str, int, int], None] | None = None,
              timeout: float = 2.0, transport: str = 'usb') -> None:
    """Full native flash of *pac_path* through the BootROM download port."""
    pac_path = Path(pac_path)
    info = parse_pac(pac_path, verify_payload=True)
    if not info.crc_ok:
        raise FlashError('PAC checksum mismatch - refusing to flash')

    with open(pac_path, 'rb') as f:
        io, _ver = connect_bootrom(device, baudrate, timeout, transport)
        try:
            load_fdls(io, info, f,
                      chunk if info.size else chunk,
                      on_stage=lambda m: log.info('stage: %s', m))

            partitions = flashable_entries(info)
            log.info('flashing %d partitions', len(partitions))
            for e in partitions:
                data = _read_entry(f, e)

                def _p(sent, total, _e=e):
                    if progress:
                        progress(_e.file_id, sent, total)

                log.info('partition %s @ 0x%08X (%d bytes)',
                         e.file_id, e.address, e.size)
                send_stage(io, e.address, data, chunk, progress=_p)

            if do_reset:
                io.send(p.BSL_CMD_NORMAL_RESET)
                log.info('reset sent; module reboots into the new firmware')
        finally:
            try:
                io.port.close()
            except Exception:
                pass


# keep PAC_HEADER_SIZE reachable for callers/tests
__all__ = ['FlashError', 'connect_bootrom', 'load_fdls', 'send_stage',
           'flash_pac', 'flashable_entries', 'PAC_HEADER_SIZE']
