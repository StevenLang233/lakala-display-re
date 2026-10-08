"""SPRD PDL (Packet Download Loader) protocol - the FIRST-stage link layer.

Reverse-engineered from the vendor ResearchDownload tool via a Frida trace of
its WriteFile/ReadFile calls to the sprd_rdavcom COM port. This is the protocol
the RDA8910/UIS8910 download agent (USB 0525:a4a7, reached by AT*DOWNLOAD)
speaks BEFORE any BSL: it is used to load and execute the first-stage loader
(HOST_FDL / "PDL1"), after which the device switches to the BSL/HDLC protocol.

Wire format (each message = an 8-byte header write, then a payload write - they
MUST be separate writes; the driver reads the header to learn the length):

    header  : ae | len(u16 LE) | 00 00 | ff | 00 00          (8 bytes)
    payload : cmd(u32 LE) | arg1(u32 LE) | arg2(u32 LE) | extra...

    response: ae | rlen(u16 LE) | 00 00 | .. | 00 00 | status(u32 LE)

Commands (cmd field):
    0  CONNECT
    4  START_DATA   arg1=load_addr  arg2=total_size   extra=loader name ("PDL1")
    5  MIDST_DATA   arg1=block_index arg2=chunk_len    extra=chunk bytes
    6  END_DATA     extra=4-byte image checksum
    7  EXEC         extra=single 0x7e (hands over to BSL; reply is the BSL VER)
"""
from __future__ import annotations

import logging
import struct

log = logging.getLogger('sprdflash')

PDL_MAGIC = 0xAE

PDL_CONNECT = 0
PDL_START_DATA = 4
PDL_MIDST_DATA = 5
PDL_END_DATA = 6
PDL_EXEC = 7

CHUNK = 2048


class PdlError(RuntimeError):
    pass


def build(payload: bytes) -> tuple[bytes, bytes]:
    """Return (header, payload) - send them as two separate writes."""
    header = bytes([PDL_MAGIC]) + struct.pack('<H', len(payload)) + b'\x00\x00\xff\x00\x00'
    return header, payload


def params(cmd: int, arg1: int = 0, arg2: int = 0, extra: bytes = b'') -> bytes:
    return struct.pack('<III', cmd, arg1, arg2) + extra


class PdlIO:
    """PDL transport over a serial-port-like object (write/flush/read)."""

    def __init__(self, port, timeout: float = 1.0):
        self.port = port
        self.timeout = timeout

    def send(self, payload: bytes) -> None:
        header, body = build(payload)
        self.port.write(header)
        self.port.flush()
        self.port.write(body)
        self.port.flush()

    def recv(self, timeout: float | None = None) -> tuple[int, bytes]:
        """Read one ae-framed response; returns (status, extra)."""
        import time
        deadline = time.monotonic() + (timeout if timeout is not None else self.timeout)
        buf = bytearray()
        while time.monotonic() < deadline:
            b = self.port.read(64)
            if b:
                buf += b
                if buf and buf[0] != PDL_MAGIC:
                    # resync to magic
                    idx = buf.find(bytes([PDL_MAGIC]))
                    if idx < 0:
                        buf.clear()
                        continue
                    del buf[:idx]
                if len(buf) >= 8:
                    rlen = buf[1] | (buf[2] << 8)
                    if len(buf) >= 8 + rlen:
                        payload = bytes(buf[8:8 + rlen])
                        status = struct.unpack('<I', payload[:4])[0] if len(payload) >= 4 else 0
                        return status, payload
        raise PdlError('no PDL response (timeout)')

    def command(self, payload: bytes, timeout: float | None = None, what: str = '') -> bytes:
        self.send(payload)
        status, extra = self.recv(timeout)
        # status 0 == OK for this agent; some builds echo 0 in the ack
        if status not in (0,):
            log.debug('PDL %s: status=%#x', what or 'cmd', status)
        return extra

    # -- high level --------------------------------------------------------
    def connect(self) -> None:
        self.command(params(PDL_CONNECT), what='CONNECT')

    def send_image(self, addr: int, data: bytes, name: bytes = b'PDL1\x00',
                   checksum: int | None = None,
                   progress=None) -> None:
        self.command(params(PDL_START_DATA, addr, len(data), name), what='START')
        total = len(data)
        for i, off in enumerate(range(0, total, CHUNK)):
            chunk = data[off:off + CHUNK]
            self.command(params(PDL_MIDST_DATA, i, len(chunk), chunk), what='MIDST')
            if progress:
                progress(off + len(chunk), total)
        crc = checksum if checksum is not None else _pdl_image_crc(data)
        self.command(params(PDL_END_DATA, extra=struct.pack('<I', crc)), what='END')

    def exec_and_get_ver(self, timeout: float = 3.0) -> bytes:
        """EXEC the loaded FDL1, then send the first BSL checkbaud (a lone 0x7e)
        and read back the BSL VER frame. After this the device speaks BSL.

        The capture shows EXEC = the PDL params(cmd=7) frame with NO extra byte,
        immediately followed by a separate lone-0x7e write (the BSL checkbaud);
        the device replies directly with the 0x7e-framed VER (no PDL ack).
        """
        import time
        header, body = build(params(PDL_EXEC))
        self.port.write(header)
        self.port.flush()
        self.port.write(body)
        self.port.flush()
        # now the BSL checkbaud handshake; retry the lone 0x7e until VER
        deadline = time.monotonic() + timeout
        buf = bytearray()
        next_kick = 0.0
        while time.monotonic() < deadline:
            now = time.monotonic()
            if now >= next_kick:
                self.port.write(b'\x7e')
                self.port.flush()
                next_kick = now + 0.05
            b = self.port.read(64)
            if b:
                buf += b
                if 0x7e in buf:
                    first = buf.index(0x7e)
                    rest = buf[first + 1:]
                    if 0x7e in rest:
                        return bytes(buf[first:first + 2 + rest.index(0x7e)])
        raise PdlError('no BSL VER after EXEC')


def _pdl_image_crc(data: bytes) -> int:
    """Checksum the PDL END command carries. The exact algorithm is still being
    pinned down empirically; CRC32 is the working hypothesis. If a target NAKs,
    try the alternatives in _crc_candidates()."""
    import zlib
    return zlib.crc32(data) & 0xFFFFFFFF


def _crc_candidates(data: bytes):
    import zlib
    yield ('crc32', zlib.crc32(data) & 0xFFFFFFFF)
    yield ('crc32_inv', zlib.crc32(data) ^ 0xFFFFFFFF)
    yield ('sum32', sum(data) & 0xFFFFFFFF)
