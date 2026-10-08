"""Install the reviewed, unmodified signed VDD package as a new root device.

Administrator rights are required. Never edits USB IDs, certificate stores,
boot settings, or existing adapters. A failed new device is removed again.
"""
import argparse
import ctypes as c
from ctypes import wintypes as w
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid
import winreg

HERE = Path(__file__).resolve().parent
REG_KEY = r'SOFTWARE\MikeTheTech\VirtualDisplayDriver'
HWID = r'Root\MttVDD'


class GUID(c.Structure):
    _fields_ = [('data', c.c_ubyte * 16)]


class DEVINFO(c.Structure):
    _fields_ = [('cbSize', w.DWORD), ('ClassGuid', GUID),
                ('DevInst', w.DWORD), ('Reserved', c.c_void_p)]


def bind(dll, name, restype, args):
    fn = getattr(dll, name)
    fn.restype, fn.argtypes = restype, args
    return fn


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true')
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    PACKAGE, CONFIG = args.package, args.config
    output = args.output.parent
    output.mkdir(parents=True, exist_ok=True)
    report = {'success': False, 'timestamp': datetime.now(timezone.utc).isoformat(),
              'hardware_id': HWID, 'package': str(PACKAGE),
              'security_settings_changed': False, 'certificate_imported': False}
    setup = c.WinDLL('setupapi', use_last_error=True)
    create_list = bind(setup, 'SetupDiCreateDeviceInfoList', c.c_void_p, [c.POINTER(GUID), w.HWND])
    create_info = bind(setup, 'SetupDiCreateDeviceInfoW', w.BOOL,
                       [c.c_void_p, w.LPCWSTR, c.POINTER(GUID), w.LPCWSTR, w.HWND, w.DWORD, c.POINTER(DEVINFO)])
    set_property = bind(setup, 'SetupDiSetDeviceRegistryPropertyW', w.BOOL,
                        [c.c_void_p, c.POINTER(DEVINFO), w.DWORD, c.c_void_p, w.DWORD])
    call_installer = bind(setup, 'SetupDiCallClassInstaller', w.BOOL,
                          [w.DWORD, c.c_void_p, c.POINTER(DEVINFO)])
    get_instance = bind(setup, 'SetupDiGetDeviceInstanceIdW', w.BOOL,
                        [c.c_void_p, c.POINTER(DEVINFO), w.LPWSTR, w.DWORD, c.POINTER(w.DWORD)])
    remove = bind(setup, 'SetupDiRemoveDevice', w.BOOL, [c.c_void_p, c.POINTER(DEVINFO)])
    destroy = bind(setup, 'SetupDiDestroyDeviceInfoList', w.BOOL, [c.c_void_p])
    update = bind(c.WinDLL('newdev', use_last_error=True), 'UpdateDriverForPlugAndPlayDevicesW',
                  w.BOOL, [w.HWND, w.LPCWSTR, w.LPCWSTR, w.DWORD, c.POINTER(w.BOOL)])
    def checked(value):
        if not value:
            raise c.WinError(c.get_last_error())
        return value
    handle = None
    registered = False
    changed_registry = False
    previous = None
    try:
        pinned = json.loads((HERE / 'dependencies.lock.json').read_text(encoding='utf-8'))['vdd_files']
        for name, expected in pinned.items():
            if hashlib.sha256((PACKAGE / name).read_bytes()).hexdigest() != expected:
                raise RuntimeError('Reviewed package changed: ' + name)
        if not (CONFIG / 'vdd_settings.xml').is_file():
            raise RuntimeError('800x1280 configuration missing')
        report['package_hashes'] = pinned
        if not args.install:
            report['preflight'] = 'passed; no changes requested'
            report['success'] = True
            return 0
        if not c.windll.shell32.IsUserAnAdmin():
            raise PermissionError('Administrator rights required')
        # Do not take over an existing installation or create duplicate adapters.
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Enum\ROOT') as key:
            for index in range(winreg.QueryInfoKey(key)[0]):
                if winreg.EnumKey(key, index).upper() == 'MTTVDD':
                    raise RuntimeError('Existing MttVDD root device found; inspect before changing it')
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, REG_KEY) as key:
                previous = winreg.QueryValueEx(key, 'VDDPATH')
        except FileNotFoundError:
            pass
        report['previous_vddpath'] = previous
        with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, REG_KEY) as key:
            winreg.SetValueEx(key, 'VDDPATH', 0, winreg.REG_SZ, str(CONFIG))
        changed_registry = True
        guid = GUID((c.c_ubyte * 16).from_buffer_copy(uuid.UUID('4d36e968-e325-11ce-bfc1-08002be10318').bytes_le))
        handle = create_list(c.byref(guid), None)
        if handle == c.c_void_p(-1).value or not handle:
            raise c.WinError(c.get_last_error())
        info = DEVINFO()
        info.cbSize = c.sizeof(info)
        checked(create_info(handle, 'MttVDD', c.byref(guid), 'QDisplay Virtual Display', None, 1, c.byref(info)))
        hardware_ids = (HWID + '\0\0').encode('utf-16le')
        buffer = c.create_string_buffer(hardware_ids)
        checked(set_property(handle, c.byref(info), 1, buffer, len(hardware_ids)))
        checked(call_installer(0x19, handle, c.byref(info)))  # DIF_REGISTERDEVICE
        registered = True
        instance = c.create_unicode_buffer(512)
        checked(get_instance(handle, c.byref(info), instance, len(instance), None))
        report['instance_id'] = instance.value
        # Write the identity immediately, even if the driver install is interrupted.
        (output / 'install_pending.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        reboot = w.BOOL()
        checked(update(None, HWID, str(PACKAGE / 'MttVDD.inf'), 0, c.byref(reboot)))
        report['reboot_required'] = bool(reboot.value)
        report['success'] = True
    except Exception as exc:
        report['error'] = repr(exc)
        if registered:
            report['failed_device_removed'] = bool(remove(handle, c.byref(info)))
        if changed_registry:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, REG_KEY, 0, winreg.KEY_SET_VALUE) as key:
                if previous is None:
                    winreg.DeleteValue(key, 'VDDPATH')
                else:
                    winreg.SetValueEx(key, 'VDDPATH', 0, previous[1], previous[0])
            report['configuration_restored'] = True
    finally:
        if handle and handle != c.c_void_p(-1).value:
            destroy(handle)
        name = 'install_result.json' if args.install else 'install_preflight.json'
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False))
    return 0 if report['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
