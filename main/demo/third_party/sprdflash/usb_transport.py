"""libusb (pyusb) transport for the Spreadtrum BootROM download gadget.

The BootROM enumerates as a CDC-ACM-style device but the BSL protocol does
**not** ride the CDC serial framing - it uses the raw bulk endpoints of the
data interface, kicked off by a vendor control transfer. This mirrors the
open-source ``iscle/sprdclient`` and ``spd_dump`` references and the behaviour
of the vendor ChannelD.dll.

Two download identities are supported (see ``BOOTROM_IDS``):

- ``1782:4d00`` - the raw BootROM, presented when the ``USB_BOOT`` pin is
  strapped high (to VDD_EXT / VDD_1V8, directly or via a pull-up) during
  reset. This is the classic spd_dump target.
- ``0525:a4a7`` ("SPRD U2S Diag") - the soft-download interface the module
  exposes after ``AT*DOWNLOAD=1``.

Wire-up (confirmed against the live 0525:a4a7 descriptor; auto-discovered for
either identity):

- CDC-Data interface: bulk OUT ``0x02``, bulk IN ``0x81`` (discovered, not
  hardcoded, so both device identities work).
- connect kick: control transfer ``bmRequestType=0x21, bRequest=0,
  wValue=1, wIndex=0`` (asserts the line / activates the endpoints).
- then a lone ``0x7e`` on the bulk OUT starts autobaud; the device answers a
  ``BSL_REP_VER`` frame on bulk IN.

**Windows note:** libusb can read descriptors while the device is on the
CDC/usbser driver, but *I/O* (open/claim/transfer) requires the device to be
bound to a WinUSB/libusbK driver (use Zadig once). That is mutually exclusive
with the vendor tool / pacflash, which need the COM driver.
"""
from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger('sprdflash')

# Known Spreadtrum/UNISOC BootROM download identities. 1782:4d00 is the raw
# BROM presented when the USB_BOOT pin is strapped high at reset (the classic
# spd_dump target); 0525:a4a7 ("SPRD U2S Diag") is the soft-download interface
# the module exposes after AT*DOWNLOAD=1. Endpoints and the data interface are
# auto-discovered from the descriptor, so both work without per-device tuning.
BOOTROM_IDS = [
    (0x1782, 0x4D00),   # raw BootROM (USB_BOOT strapped)
    (0x1782, 0x4D11),   # BootROM variant seen on some UIS8910 builds
    (0x0525, 0xA4A7),   # SPRD U2S Diag (soft download)
]

# Vendor "activate the port" control transfer, required before the bulk
# endpoints respond. Values from kagaimiq/sprdproto (proven against real
# Spreadtrum BootROMs): CDC SET_CONTROL_LINE_STATE (bRequest 0x22) with the
# Spreadtrum-specific wValue 0x601. (The earlier 0x00/0x01 from sprdclient did
# not wake this gadget.)
CTRL_REQUEST_TYPE = 0x21
CTRL_REQUEST = 0x22
CTRL_VALUE = 0x0601
CTRL_INDEX = 0x00

# Bulk writes are chunked to the endpoint's max packet size (sprdproto notes a
# 64-byte endpoint quirk where oversized transfers are dropped).
MAX_EP_CHUNK = 64


class UsbUnavailable(RuntimeError):
    """pyusb/libusb backend missing, or the device is not WinUSB-bound."""


def _is_timeout(exc: Exception) -> bool:
    try:
        import usb.core
        if isinstance(exc, usb.core.USBTimeoutError):
            return True
    except Exception:
        pass
    msg = str(exc).lower()
    return 'timed out' in msg or 'timeout' in msg


def _get_backend():
    try:
        import libusb_package
        return libusb_package.get_libusb1_backend()
    except Exception:
        pass

    # Project-local fallback for macOS hosts where Homebrew cannot install a
    # bottle (for example because the installed Command Line Tools are older).
    # usb_transport.py lives at tools/sprdflash-python/src/sprdflash/.
    try:
        import usb.backend.libusb1
        project_root = Path(__file__).resolve().parents[4]
        candidates = (
            project_root / "tools/libusb-local/lib/libusb-1.0.0.dylib",
            Path("/opt/homebrew/opt/libusb/lib/libusb-1.0.dylib"),
            Path("/usr/local/opt/libusb/lib/libusb-1.0.dylib"),
        )
        for candidate in candidates:
            if not candidate.is_file():
                continue
            backend = usb.backend.libusb1.get_backend(
                find_library=lambda _name, path=str(candidate): path
            )
            if backend is not None:
                return backend
    except Exception:
        pass
    return None   # pyusb will fall back to a system libusb if present


def find_bootrom():
    """Return the pyusb device for the first matching BootROM identity, or None."""
    try:
        import usb.core
    except ImportError as e:
        raise UsbUnavailable(
            'pyusb is not installed - install with: pip install "sprdflash[usb]"') from e
    backend = _get_backend()
    for vid, pid in BOOTROM_IDS:
        dev = usb.core.find(idVendor=vid, idProduct=pid, backend=backend)
        if dev is not None:
            log.info('BootROM device: %04x:%04x', vid, pid)
            return dev
    return None


def _discover_data_interface(dev):
    """Return (interface_number, ep_out, ep_in) for the interface carrying the
    bulk BSL endpoints. Prefers the CDC-Data interface (class 0x0a); falls back
    to any interface exposing both bulk directions."""
    import usb.util
    cfg = dev.get_active_configuration()
    fallback = None
    for intf in cfg:
        ep_out = ep_in = None
        for ep in intf:
            if usb.util.endpoint_type(ep.bmAttributes) != usb.util.ENDPOINT_TYPE_BULK:
                continue
            if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT:
                ep_out = ep.bEndpointAddress
            else:
                ep_in = ep.bEndpointAddress
        if ep_out is not None and ep_in is not None:
            found = (intf.bInterfaceNumber, ep_out, ep_in)
            if intf.bInterfaceClass == 0x0A:   # CDC-Data
                return found
            if fallback is None:
                fallback = found
    if fallback is None:
        raise UsbUnavailable('no bulk endpoints found on the BootROM device')
    return fallback


class UsbPort:
    """A serial-port-like adapter (read/write/flush) over the BootROM's bulk
    endpoints, so the framed SpdIO layer can drive it unchanged."""

    def __init__(self, dev, timeout: float = 2.0, interface: int = 1,
                 ep_out: int = 0x02, ep_in: int = 0x81):
        self.dev = dev
        self.timeout_ms = int(timeout * 1000)
        self.interface = interface
        self.ep_out = ep_out
        self.ep_in = ep_in
        self._rx = bytearray()
        self._opened = False

    def open(self) -> None:
        import usb.util
        try:
            try:
                self.interface, self.ep_out, self.ep_in = _discover_data_interface(self.dev)
            except UsbUnavailable:
                raise
            except Exception as e:
                log.debug('endpoint discovery failed (%s); using defaults', e)
            # On Linux the cdc_acm driver claims BOTH the control (0) and data
            # interfaces; the vendor control transfer targets the control
            # interface, so detach the kernel driver from every interface, not
            # just the bulk one. (No-op on Windows/WinUSB.)
            for intf in self._all_interface_numbers():
                try:
                    if self.dev.is_kernel_driver_active(intf):
                        self.dev.detach_kernel_driver(intf)
                except Exception:
                    pass
            usb.util.claim_interface(self.dev, self.interface)
            # kick the endpoints alive (vendor connect request)
            self.dev.ctrl_transfer(CTRL_REQUEST_TYPE, CTRL_REQUEST,
                                   CTRL_VALUE, CTRL_INDEX, None, self.timeout_ms)
            self._opened = True
        except NotImplementedError as e:
            raise UsbUnavailable(
                'the BootROM port is not accessible via libusb - it is bound to '
                'the CDC/usbser driver. Replace that driver with WinUSB using '
                'Zadig (https://zadig.akeo.ie) for USB 0525:A4A7, then retry. '
                'Note: this disables the vendor tool / pacflash for this device '
                'until you restore the CDC driver.') from e
        except Exception as e:
            raise UsbUnavailable(f'could not open the BootROM USB device: {e}') from e

    def _all_interface_numbers(self):
        try:
            cfg = self.dev.get_active_configuration()
            return [intf.bInterfaceNumber for intf in cfg]
        except Exception:
            return [0, self.interface]

    # -- serial-like API --------------------------------------------------
    def write(self, data: bytes) -> int:
        # chunk to the endpoint max-packet size (sprdproto endpoint quirk)
        sent = 0
        while sent < len(data):
            piece = data[sent:sent + MAX_EP_CHUNK]
            self.dev.write(self.ep_out, piece, timeout=self.timeout_ms)
            sent += len(piece)
        return sent

    def flush(self) -> None:
        pass

    def read(self, n: int = 1) -> bytes:
        if not self._rx:
            try:
                chunk = self.dev.read(self.ep_in, 4096, timeout=self.timeout_ms)
                self._rx += bytes(chunk)
            except Exception as e:
                # a bulk-IN read with no data raises USBTimeoutError; its message
                # is like "[Errno 110] Operation timed out"
                if _is_timeout(e):
                    return b''
                raise
        take = self._rx[:n]
        del self._rx[:n]
        return bytes(take)

    def close(self) -> None:
        if self._opened:
            try:
                import usb.util
                usb.util.release_interface(self.dev, self.interface)
                usb.util.dispose_resources(self.dev)
            except Exception:
                pass
            self._opened = False


def open_usb_port(timeout: float = 2.0) -> UsbPort:
    dev = find_bootrom()
    if dev is None:
        ids = ', '.join(f'{v:04x}:{p:04x}' for v, p in BOOTROM_IDS)
        raise UsbUnavailable(
            f'no BootROM device found (looked for {ids}). Put the module in '
            'download mode first (USB_BOOT strap + reset, or AT*DOWNLOAD=1).')
    port = UsbPort(dev, timeout=timeout)
    port.open()
    return port
