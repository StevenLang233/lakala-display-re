"""Spreadtrum/UNISOC BootROM + FDL download protocol (BSL over HDLC).

This is a clean-room Python implementation of the wire protocol used by the
vendor ResearchDownload / CmdDloader tools, following the documented behaviour
of the open-source ``spreadtrum_flash`` (spd_dump) project. No vendor binaries
are used.

Wire format of one message::

    0x7e | escape( type[2] size[2] data[size] checksum[2] ) | 0x7e

- ``type`` and ``size`` are big-endian u16.
- In **BootROM** mode the checksum is CRC16 (poly 0x11021, MSB-first).
- After FDL1 runs, the device switches to **FDL** mode where the checksum is a
  16-bit ones-complement sum (little-endian words).
- HDLC escaping: any 0x7e/0x7d byte in the framed region becomes
  ``0x7d, byte ^ 0x20``. The leading/trailing 0x7e flags are never escaped.
"""
from __future__ import annotations

import logging
import struct
import time

log = logging.getLogger('sprdflash')

HDLC_FLAG = 0x7E
HDLC_ESCAPE = 0x7D

# Host -> device commands
BSL_CMD_CONNECT = 0x00
BSL_CMD_START_DATA = 0x01
BSL_CMD_MIDST_DATA = 0x02
BSL_CMD_END_DATA = 0x03
BSL_CMD_EXEC_DATA = 0x04
BSL_CMD_NORMAL_RESET = 0x05
BSL_CMD_READ_FLASH = 0x06
BSL_CMD_READ_CHIP_TYPE = 0x07
BSL_CMD_CHANGE_BAUD = 0x09
BSL_CMD_ERASE_FLASH = 0x0A
BSL_CMD_READ_CHIP_UID = 0x1A
BSL_CMD_CHECK_BAUD = 0x7E
BSL_CMD_END_PROCESS = 0x7F

# Device -> host replies
BSL_REP_ACK = 0x80
BSL_REP_VER = 0x81
BSL_REP_INVALID_CMD = 0x82
BSL_REP_UNKNOWN_CMD = 0x83
BSL_REP_OPERATION_FAILED = 0x84
BSL_REP_DOWN_NOT_START = 0x86
BSL_REP_DOWN_MULTI_START = 0x87
BSL_REP_DOWN_EARLY_END = 0x88
BSL_REP_DOWN_DEST_ERROR = 0x89
BSL_REP_DOWN_SIZE_ERROR = 0x8A
BSL_REP_VERIFY_ERROR = 0x8B
BSL_REP_NOT_VERIFY = 0x8C
BSL_REP_READ_FLASH = 0x93
BSL_REP_READ_CHIP_TYPE = 0x94
BSL_REP_READ_CHIP_UID = 0xAB
BSL_REP_UNSUPPORTED_COMMAND = 0xFE

_REP_NAMES = {v: k for k, v in globals().items()
              if k.startswith('BSL_REP_') and isinstance(v, int)}


def rep_name(code: int) -> str:
    return _REP_NAMES.get(code, f'0x{code:04x}')


def crc16(data: bytes, crc: int = 0) -> int:
    """BootROM checksum: CRC16 with polynomial 0x11021 (MSB-first)."""
    crc &= 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ (0x11021 if crc & 0x8000 else 0)) & 0xFFFF
    return crc


def sprd_checksum(data: bytes) -> int:
    """Spreadtrum sum checksum (ones-complement sum of little-endian 16-bit
    words, always byte-swapped at the end).

    This is the checksum the RDA8910/UIS8910 BootROM uses for *every* packet
    (verified byte-for-byte against the vendor ResearchDownload wire log). It
    matches kagaimiq/sprdproto's ``calc_sprdcheck`` exactly — note the final
    byte swap is unconditional, unlike spd_dump's odd-length-only variant.
    """
    total = 0
    i = 0
    n = len(data)
    while n - i >= 2:
        total += data[i] | (data[i + 1] << 8)
        i += 2
    if i < n:
        total += data[i]
    total = (total >> 16) + (total & 0xFFFF)
    total = ~(total + (total >> 16)) & 0xFFFF
    return ((total >> 8) | ((total & 0xFF) << 8)) & 0xFFFF


# backwards-compatible alias
fdl_checksum = sprd_checksum


def checksum_for(mode: str, data: bytes) -> int:
    return crc16(data) if mode == 'crc' else sprd_checksum(data)


def detect_checksum(frame_body: bytes) -> str | None:
    """Given an unescaped frame body (type+len+data+checksum, no 0x7e flags),
    return 'crc' or 'sprd' whichever checksum validates it, else None."""
    if len(frame_body) < 6:
        return None
    body, chk = frame_body[:-2], (frame_body[-2] << 8) | frame_body[-1]
    if sprd_checksum(body) == chk:
        return 'sprd'
    if crc16(body) == chk:
        return 'crc'
    return None


def hdlc_escape(frame: bytes) -> bytes:
    out = bytearray()
    for b in frame:
        if b in (HDLC_FLAG, HDLC_ESCAPE):
            out.append(HDLC_ESCAPE)
            out.append(b ^ 0x20)
        else:
            out.append(b)
    return bytes(out)


def hdlc_unescape(frame: bytes) -> bytes:
    out = bytearray()
    it = iter(frame)
    for b in it:
        if b == HDLC_ESCAPE:
            try:
                nxt = next(it)
            except StopIteration:
                break
            out.append(nxt ^ 0x20)
        else:
            out.append(b)
    return bytes(out)


def build_message(cmd: int, data: bytes = b'', checksum: str = 'sprd') -> bytes:
    """Frame one BSL message ready for the wire (including 0x7e flags).

    *checksum* is 'sprd' (Spreadtrum sum, used by RDA8910/UIS8910) or 'crc'
    (CRC16, classic Spreadtrum BootROM). The checkbaud handshake detects which.
    """
    body = struct.pack('>HH', cmd, len(data)) + data
    body += struct.pack('>H', checksum_for(checksum, body))
    return bytes([HDLC_FLAG]) + hdlc_escape(body) + bytes([HDLC_FLAG])


def parse_message(frame_no_flags: bytes) -> tuple[int, bytes]:
    """Decode an unescaped message body (without 0x7e flags).

    Returns (type, data). Raises ValueError on a malformed frame.
    """
    if len(frame_no_flags) < 6:
        raise ValueError(f'frame too short ({len(frame_no_flags)} bytes)')
    cmd, size = struct.unpack('>HH', frame_no_flags[:4])
    data = frame_no_flags[4:4 + size]
    if len(data) != size:
        raise ValueError(f'truncated frame: declared {size}, got {len(data)}')
    return cmd, data


class ProtocolError(RuntimeError):
    pass


class SpdIO:
    """Framed BSL transport over a pyserial-like port object."""

    def __init__(self, port, timeout: float = 1.0):
        self.port = port
        self.timeout = timeout
        # 'sprd' or 'crc'; the checkbaud handshake auto-detects it from VER.
        self.checksum = 'sprd'

    # crc_mode kept as a bool view for older callers
    @property
    def crc_mode(self) -> bool:
        return self.checksum == 'crc'

    @crc_mode.setter
    def crc_mode(self, value: bool) -> None:
        self.checksum = 'crc' if value else 'sprd'

    # -- low level ---------------------------------------------------------
    def _read_frame(self, timeout: float) -> bytes:
        """Read one 0x7e...0x7e frame and return its unescaped body."""
        deadline = time.monotonic() + timeout
        # skip to the opening flag
        while time.monotonic() < deadline:
            b = self.port.read(1)
            if not b:
                continue
            if b[0] == HDLC_FLAG:
                break
        else:
            raise TimeoutError('no response frame (opening flag not seen)')

        body = bytearray()
        while time.monotonic() < deadline:
            b = self.port.read(1)
            if not b:
                continue
            if b[0] == HDLC_FLAG:
                if not body:
                    # back-to-back flags; treat this as the real opener
                    continue
                return hdlc_unescape(bytes(body))
            body.append(b[0])
        raise TimeoutError('no response frame (closing flag not seen)')

    def send(self, cmd: int, data: bytes = b'') -> None:
        msg = build_message(cmd, data, checksum=self.checksum)
        self.port.write(msg)
        self.port.flush()

    def recv(self, timeout: float | None = None) -> tuple[int, bytes]:
        body = self._read_frame(timeout if timeout is not None else self.timeout)
        return parse_message(body)

    # -- handshakes --------------------------------------------------------
    def autobaud(self, attempts: int = 200, timeout: float = 0.05) -> bytes:
        """Send lone-0x7e checkbaud bytes until the BootROM answers VER.

        Matches the vendor tool's tight retry loop (short per-try timeout, many
        retries) — the download gadget only answers within a brief window. On
        the VER frame we also auto-detect the checksum type (sprd vs crc) that
        the rest of the session must use.
        """
        for _ in range(attempts):
            self.port.write(bytes([HDLC_FLAG]))
            # A one-byte check-baud write is atomic. Avoid tcdrain here: after
            # FDL1 takes over, macOS's CDC driver can wait forever for the old
            # endpoint even though the byte has already been queued.
            time.sleep(0.01)
            try:
                raw = self._read_frame(timeout)
            except (TimeoutError, ValueError):
                continue
            detected = detect_checksum(raw)
            try:
                cmd, data = parse_message(raw)
            except ValueError:
                continue
            if cmd == BSL_REP_VER:
                if detected:
                    self.checksum = detected
                log.info('device version: %s (checksum=%s)',
                         data.decode('latin-1', 'replace').strip(), self.checksum)
                return data
            log.debug('autobaud got %s, retrying', rep_name(cmd))
        raise ProtocolError(f'no VER response after {attempts} autobaud attempts')

    def connect(self) -> None:
        self.command(BSL_CMD_CONNECT, expect=BSL_REP_ACK, what='CONNECT')

    def command(self, cmd: int, data: bytes = b'', expect: int = BSL_REP_ACK,
                timeout: float | None = None, what: str | None = None) -> bytes:
        """Send a command and require *expect* as the reply type."""
        self.send(cmd, data)
        rtype, rdata = self.recv(timeout=timeout)
        if rtype != expect:
            label = what or f'cmd 0x{cmd:02x}'
            raise ProtocolError(f'{label}: expected {rep_name(expect)}, '
                                f'got {rep_name(rtype)}')
        return rdata
