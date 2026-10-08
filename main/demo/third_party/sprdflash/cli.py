"""sprdflash - native (no vendor exe) flasher for SPRD/UNISOC .pac firmware."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import __version__
from .pac import parse_pac

log = logging.getLogger('sprdflash')

DOWNLOAD_VID = 0x0525
DOWNLOAD_PID = 0xA4A7


def _usb_unavailable():
    """The UsbUnavailable exception type, imported lazily so the CLI works
    even when pyusb is not installed."""
    try:
        from .usb_transport import UsbUnavailable
        return UsbUnavailable
    except Exception:
        class _Never(Exception):
            pass
        return _Never


def _find_download_port() -> str | None:
    from serial.tools import list_ports
    for pinfo in list_ports.comports():
        if pinfo.vid == DOWNLOAD_VID and pinfo.pid == DOWNLOAD_PID:
            return pinfo.device
    return None


def _resolve_port(explicit: str | None) -> str:
    if explicit:
        return explicit
    port = _find_download_port()
    if not port:
        raise TimeoutError(
            f'no BootROM download port ({DOWNLOAD_VID:04x}:{DOWNLOAD_PID:04x}) found. '
            'Put the module in download mode (hold boot key while powering on, or '
            'send AT*DOWNLOAD=1), or pass --port.')
    return port


def _cmd_identify(args: argparse.Namespace) -> int:
    from .flasher import connect_bootrom
    port = None if args.transport == 'usb' else _resolve_port(args.port)
    log.info('connecting via %s%s', args.transport, f' ({port})' if port else '')
    io, version = connect_bootrom(port, args.baud, timeout=args.timeout,
                                  transport=args.transport)
    try:
        print(f'connected via {args.transport}')
        print(f'BootROM version: {version.decode("latin-1", "replace").strip()}')
    finally:
        io.port.close()
    return 0


def _cmd_info(args: argparse.Namespace) -> int:
    info = parse_pac(args.pac, verify_payload=not args.no_verify)
    print(f'Product : {info.product_name} ({info.product_version})')
    print(f'Size    : {info.size:,} bytes')
    print(f'CRC     : header {"ok" if info.header_crc_ok else "BAD"}, '
          f'payload {"ok" if info.payload_crc_ok else "n/a" if info.payload_crc_ok is None else "BAD"}')
    from .flasher import classify
    for e in info.entries:
        role = classify(e)
        addr = f'0x{e.address:08X}' if e.address else '          '
        size = 'marker' if e.is_marker else f'{e.size:>10,} B'
        print(f'  [{role:<6}] {e.file_id:<12} {addr}  {size:>12}  {e.file_name}')
    return 0 if info.crc_ok else 2


def _cmd_flash(args: argparse.Namespace) -> int:
    from . import native, pdl
    pac_path = Path(args.pac).resolve()
    info = parse_pac(pac_path, verify_payload=not args.no_verify)
    if not info.crc_ok and not args.force:
        log.error('PAC checksum mismatch - refusing to flash (use --force to override)')
        return 2
    port = _resolve_port(args.port)   # the download-mode COM port (0525:a4a7)
    print(f'native-flashing {pac_path.name} via {port} (PDL+BSL, no vendor tool)')

    state = {'file': None, 'pct': -1}

    def progress(file_id: str, sent: int, total: int) -> None:
        pct = sent * 100 // total if total else 100
        if file_id != state['file']:
            if state['file'] is not None:
                print()
            state['file'] = file_id
            state['pct'] = -1
        if pct != state['pct']:
            state['pct'] = pct
            print(f'\r  {file_id:<14} {pct:3d}%', end='', flush=True)

    try:
        native.native_flash(port, pac_path, progress=progress,
                            format_fs=args.format, do_reset=not args.no_reset)
    except pdl.PdlError as e:
        print()
        log.error('%s', e)
        return 4
    print('\nflash complete - module reboots into the new firmware')
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='sprdflash',
        description='Native flasher for SPRD/UNISOC .pac firmware (Air724UG / '
                    'RDA8910 and friends) - speaks the BootROM/FDL protocol '
                    'directly, no vendor download tool required.')
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    parser.add_argument('-v', '--verbose', action='store_true', help='debug logging')
    sub = parser.add_subparsers(dest='command', required=True)

    pi = sub.add_parser('info', help='parse and validate a .pac file')
    pi.add_argument('pac')
    pi.add_argument('--no-verify', action='store_true')
    pi.set_defaults(fn=_cmd_info)

    pid = sub.add_parser('identify', help='connect to the BootROM and read its version (safe)')
    pid.add_argument('--transport', choices=['usb', 'serial'], default='usb',
                     help='usb = libusb bulk (RDA8910 gadget); serial = plain UART')
    pid.add_argument('--port', help='serial download port (serial transport only)')
    pid.add_argument('--baud', type=int, default=115200)
    pid.add_argument('--timeout', type=float, default=2.0)
    pid.set_defaults(fn=_cmd_identify)

    pf = sub.add_parser('flash', help='flash a .pac natively (PDL+BSL, no vendor tool)')
    pf.add_argument('pac')
    pf.add_argument('--port', help='download-mode COM port (e.g. COM34); '
                                   'auto-detected (0525:a4a7) if omitted')
    pf.add_argument('--no-verify', action='store_true',
                    help='skip the payload CRC check before flashing')
    pf.add_argument('--force', action='store_true',
                    help='flash even if the PAC checksum does not match')
    pf.add_argument('--format', action='store_true',
                    help='also format the filesystem + refresh NV/prepack '
                         '(needed when changing firmware TYPE, e.g. LuatOS<->CSDK)')
    pf.add_argument('--no-reset', action='store_true', help='do not reset after flashing')
    pf.set_defaults(fn=_cmd_flash)
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors='replace')
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s', datefmt='%H:%M:%S')
    try:
        return args.fn(args)
    except FileNotFoundError as e:
        log.error('%s', e)
        return 1
    except _usb_unavailable() as e:
        log.error('%s', e)
        return 5
    except ValueError as e:
        log.error('%s', e)
        return 2
    except TimeoutError as e:
        log.error('%s', e)
        return 3
    except RuntimeError as e:
        log.error('%s', e)
        return 4
    except KeyboardInterrupt:
        print('\ninterrupted')
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
