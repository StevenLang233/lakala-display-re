"""Windows setup backend. JSONL progress; only locked EC600U-CNLB inputs.

Original orchestration under the repository license; sprdflash stays MIT.
No UI/frame-transport changes. A write error keeps the loader alive for recovery.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import struct
import sys
import time
import traceback
import zipfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "third_party"))
import serial
from serial.tools import list_ports
from sprdflash import native, pdl, protocol as bsl
from sprdflash.flasher import send_stage, DEFAULT_CHUNK
from sprdflash.pac import parse_pac

BASE, FLASH_SIZE = 0x60000000, 8 * 1024 * 1024
APP_BASE, APP_SIZE = 0x60260000, 0xE0000
CORE_HASH = "187abb282fd089e6c3fb9d8bb75b837826b1a726e943fe961e5bf052da433ca9"
PAC_HASH = "a85f766d28e0f51a7f40f5e78ce6ec6ec3b2595146a85b9783cb45d43d47ebc8"
ZIP_HASH = "8182d7b62e220e3033cefcca4300376bfb4279821f4ba08fa43e25ffcf3ab510"
BIN_HASH = "7db107334fc1a522128e34290ecf371b3216f08037d2d978ee8cda470f483e23"
APP_HASH = "4e6da49fcff0628532ed325b7c722db4e83971015b4f6783a0655c4f099fb437"
R03 = "EC600UCNLBR03A04M08_OCPU_QPY"
R05 = "EC600UCNLBR05A01M08_OCPU_BETA1215"


class SetupError(RuntimeError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def emit(kind, **fields):
    print(json.dumps(dict(event=kind, **fields), ensure_ascii=False), flush=True)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


class Progress:
    def __init__(self):
        self.last, self.when = None, 0

    def __call__(self, stage, done, total):
        percent = done * 100 // total if total else 100
        now = time.monotonic()
        if (stage, percent) != self.last or now - self.when >= 3:
            emit("progress", stage=stage, done=done, total=total, percent=percent)
            self.last, self.when = (stage, percent), now


progress = Progress()


def port_roles(ports):
    """Registry MI identity, intersected with present SetupAPI COM enumeration.

    pyserial's Windows hwid does not always include MI_02/MI_20. Do not guess a
    command port from its COM number or probe unrelated diagnostic endpoints.
    """
    roles = {}
    if sys.platform != "win32":
        for item in ports:
            for role, token in (("at", "MI_02"), ("data", "MI_20")):
                if token in (item.hwid or "").upper():
                    roles[item.device] = (role, item.hwid)
        return roles
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Enum\USB") as usb:
            for index in range(winreg.QueryInfoKey(usb)[0]):
                name = winreg.EnumKey(usb, index)
                match = re.fullmatch(r"VID_2C7C&PID_0901&MI_(02|20)", name, re.I)
                if not match:
                    continue
                with winreg.OpenKey(usb, name) as interface:
                    for n in range(winreg.QueryInfoKey(interface)[0]):
                        instance = winreg.EnumKey(interface, n)
                        try:
                            with winreg.OpenKey(interface, instance + r"\Device Parameters") as parameters:
                                com = winreg.QueryValueEx(parameters, "PortName")[0]
                            roles[com] = ("at" if match[1] == "02" else "data", name + "\\" + instance)
                        except FileNotFoundError:
                            continue
    except PermissionError as exc:
        raise SetupError("DETECTION_DENIED", "无法读取 USB 接口身份。请检查系统权限。") from exc
    return roles


def detect(probe=False):
    ports = list(list_ports.comports())
    roles = port_roles(ports)
    rows = []
    for item in ports:
        if (item.vid, item.pid) == (0x0525, 0xA4A7):
            role, identity = "download", item.hwid
        elif (item.vid, item.pid) == (0x2C7C, 0x0901) and item.device in roles:
            role, identity = roles[item.device]
        else:
            continue
        rows.append(dict(port=item.device, role=role, identity=identity))
    at = [r for r in rows if r["role"] == "at"]
    dl = [r for r in rows if r["role"] == "download"]
    data = [r for r in rows if r["role"] == "data"]
    if len(at) > 1 or len(dl) > 1 or len(data) > 1 or (at and dl):
        raise SetupError("MULTIPLE_DEVICES", "检测到多台设备。只连接一台待刷客显屏，再重新运行。")
    state = dict(state="normal" if at else "download" if dl else "missing", ports=rows,
                 at_port=at[0]["port"] if at else None, download_port=dl[0]["port"] if dl else None,
                 data_port=data[0]["port"] if data else None, core="unknown")
    if probe and at:
        text = at_command(at[0]["port"], "ATI")
        if "EC600U" not in text:
            raise SetupError("WRONG_MODEL", "AT 口未返回 EC600U 型号；不允许刷写。")
        state["core"] = R03 if R03 in text else R05 if R05 in text else "unsupported"
        if state["core"] == "unsupported":
            raise SetupError("UNSUPPORTED_CORE", "这台设备核心版本不在已验证的 R03/R05 列表内。")
    return state


def at_command(port, command):
    try:
        with serial.Serial(port, 115200, timeout=0.15, write_timeout=2) as stream:
            stream.reset_input_buffer()
            stream.write((command + "\r").encode("ascii"))
            result = bytearray()
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline:
                result.extend(stream.read(1024))
                if b"\r\nOK" in result or b"\r\nERROR" in result:
                    break
            if b"OK" not in result:
                raise SetupError("AT_NO_RESPONSE", "AT 查询未成功。检查端口占用、USB 驱动和供电。")
            return result.decode("ascii", "replace")
    except serial.SerialException as exc:
        raise SetupError("PORT_BUSY", "AT 口无法打开。请关闭 QPYcom、其他刷写工具或串口软件。") from exc


def wait_state(name, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = detect()
        if state["state"] == name:
            return state
        progress("等待 USB " + name, int(timeout - max(0, deadline - time.monotonic())), timeout)
        time.sleep(0.5)
    code = "DOWNLOAD_PORT_TIMEOUT" if name == "download" else "USB_BOOT_TIMEOUT"
    raise SetupError(code, "设备重新枚举超时。检查下载口驱动和 USB 连接；不要反复盲刷。")


def enter_download(state, after_write=False):
    if state["state"] == "download":
        return state["download_port"]
    if state["state"] != "normal":
        raise SetupError("NO_DEVICE", "没有找到客显屏 AT 口或下载口。请接入数据线并安装 USB 驱动。")
    # SerialException during this command is expected when the USB gadget drops.
    with serial.Serial(state["at_port"], 115200, timeout=0.15, write_timeout=2) as stream:
        stream.reset_input_buffer()
        stream.write(b"AT+QDOWNLOAD=1\r")
        try:
            stream.read(512)
        except serial.SerialException:
            pass
    try:
        return wait_state("download", 45)["download_port"]
    except SetupError as exc:
        if after_write and exc.code == "DOWNLOAD_PORT_TIMEOUT":
            raise SetupError("DOWNLOAD_RECONNECT_TIMEOUT", "核心转换后下载口重连失败。保留首次备份；不能当作未写入而自动重跑转换。") from exc
        raise


class BufferedPort:
    def __init__(self, port):
        self.port, self.buffer = port, bytearray()

    def read(self, n):
        if not self.buffer:
            self.buffer.extend(self.port.read(max(n, self.port.in_waiting)))
        data = bytes(self.buffer[:n])
        del self.buffer[:n]
        return data

    def write(self, data):
        count = self.port.write(data)
        if count != len(data):
            raise SetupError("SHORT_WRITE", "USB 写入字节不足；停止刷写。")
        return count

    def flush(self):
        self.port.flush()

    def close(self):
        self.port.close()


class StrictPdl(pdl.PdlIO):
    def command(self, payload, timeout=None, what=""):
        self.send(payload)
        status, extra = self.recv(timeout)
        if status:
            raise SetupError("LOADER_REJECTED", f"PDL {what} 返回错误状态 {status:#x}。")
        return extra


def open_loader(port, entries):
    stream = BufferedPort(serial.Serial(port, 115200, timeout=0.2, write_timeout=3))
    try:
        stream.port.dtr = stream.port.rts = True
        stream.port.reset_input_buffer()
        io_bsl = bsl.SpdIO(stream, timeout=3)
        # A previous failed run may have left FDL1/FDL2 in RAM. Check baud is
        # read-only and lets the same entrance recover without a power cycle.
        try:
            io_bsl.autobaud(attempts=12, timeout=0.08)
            io_bsl.connect()
        except (TimeoutError, ValueError, bsl.ProtocolError):
            stream.buffer.clear()
            stream.port.reset_input_buffer()
            first = StrictPdl(stream, timeout=3)
            first.connect()
            first.send_image(0x008000C0, entries["HOST_FDL"][1], checksum=0,
                             progress=lambda d, t: progress("加载 FDL1", d, t))
            first.exec_and_get_ver(timeout=6)
            io_bsl = bsl.SpdIO(stream, timeout=3)
            io_bsl.checksum = "sprd"
            io_bsl.connect()
        try:
            check = io_bsl.command(bsl.BSL_CMD_READ_FLASH, struct.pack(">III", BASE, 32, 0),
                                   expect=bsl.BSL_REP_READ_FLASH, timeout=2)
            if len(check) == 32:
                return io_bsl, stream
        except (bsl.ProtocolError, TimeoutError):
            pass
        send_stage(io_bsl, 0x00810000, entries["FDL2"][1], DEFAULT_CHUNK,
                   progress=lambda d, t: progress("加载 FDL2", d, t))
        io_bsl.command(bsl.BSL_CMD_EXEC_DATA, timeout=15, what="EXEC FDL2")
        io_bsl.connect()
        return io_bsl, stream
    except BaseException:
        stream.close()
        raise


def read_flash(link, address, size, stage, sink=None, expected=None):
    output = bytearray()
    for offset in range(0, size, 4096):
        count = min(4096, size - offset)
        data = link.command(bsl.BSL_CMD_READ_FLASH, struct.pack(">III", address + offset, count, 0),
                            expect=bsl.BSL_REP_READ_FLASH, timeout=6)
        if len(data) != count:
            raise SetupError("SHORT_READ", f"读回 {address + offset:#x} 字节不足。")
        if expected is not None and data != expected[offset:offset + count]:
            raise SetupError("READBACK_MISMATCH", f"{stage} 在 {address + offset:#x} 不一致。")
        if sink:
            sink.write(data)
        output.extend(data)
        progress(stage, offset + count, size)
    return bytes(output)


def validate_app(data):
    if digest(data) != APP_HASH:
        raise SetupError("APP_HASH", "固件不是这个版本锁定的 qdisplay_native.bin。")
    if not 128 <= len(data) <= APP_SIZE or struct.unpack_from("<II", data) != (0x41505032, len(data)):
        raise SetupError("APP_HEADER", "固件 APP2 头或长度不正确。")
    for offset in range(32, 128, 16):
        kind, pos, size, address = struct.unpack_from("<4I", data, offset)
        if not kind:
            continue
        low, high = (APP_BASE, APP_BASE + APP_SIZE) if kind == 4 else (0x80F00000, 0x81000000)
        if kind not in (1, 2, 3, 4) or not low <= address <= address + size <= high:
            raise SetupError("APP_RANGE", "固件描述符超出 APP 所属地址范围。")
        if kind != 3 and pos + size > len(data):
            raise SetupError("APP_RANGE", "固件描述符超出文件长度。")


def pac_entries(path):
    raw = path.read_bytes()
    if digest(raw) != PAC_HASH:
        raise SetupError("PAC_HASH", "官方 PAC 哈希不匹配；不能使用 EXTFS8M 或其他版本。")
    info = parse_pac(path, verify_payload=True)
    if not info.crc_ok:
        raise SetupError("PAC_CRC", "官方 PAC CRC 校验失败。")
    entries = {}
    for entry in info.entries:
        if not entry.size:
            continue
        if entry.offset + entry.size > len(raw) or entry.file_id in entries:
            raise SetupError("PAC_TABLE", "PAC 文件表越界或重复。")
        entries[entry.file_id] = (entry.address, raw[entry.offset:entry.offset + entry.size])
    required = {"HOST_FDL": (0x8000C0, "cfad226ef5d892ee24609e0e3104109d459cd1daf3206357e698a1253ef67968"),
                "FDL2": (0x810000, "61ba99f74ea0614fd5996064670dc1caa705ef044a8acc919a8872557a38309a"),
                "AP": (0x60010000, CORE_HASH)}
    for name, (address, expected) in required.items():
        if name not in entries or entries[name][0] != address or digest(entries[name][1]) != expected:
            raise SetupError("PAC_IDENTITY", "PAC 关键条目不匹配：" + name)
    return entries


def unpack_pac(source, destination):
    data = source.read_bytes()
    if digest(data) == PAC_HASH:
        result = data
    else:
        if digest(data) != ZIP_HASH:
            raise SetupError("CORE_ZIP_HASH", "官方核心 ZIP/PAC 指纹不匹配。")
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = [n for n in archive.namelist() if n.endswith("QPY_OCPU_V0004_EC600U_CNLB_FW.bin")]
            if len(names) != 1:
                raise SetupError("CORE_CONTAINER", "官方包内未找到唯一的固件容器。")
            container = archive.read(names[0])
        if digest(container) != BIN_HASH:
            raise SetupError("CORE_CONTAINER", "官方 BIN 容器指纹不匹配。")
        with zipfile.ZipFile(io.BytesIO(container)) as archive:
            names = [n for n in archive.namelist() if n.lower().endswith(".pac")]
            if len(names) != 1:
                raise SetupError("CORE_CONTAINER", "容器内 PAC 不唯一。")
            result = archive.read(names[0])
        if digest(result) != PAC_HASH:
            raise SetupError("PAC_HASH", "解包后的 PAC 指纹不匹配。")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(result)
    pac_entries(destination)
    emit("result", success=True, pac=str(destination))


def backup(link, folder, state):
    folder.mkdir(parents=True, exist_ok=False)
    part = folder / "internal-8MiB.bin.partial"
    with part.open("xb") as sink:
        first = read_flash(link, BASE, FLASH_SIZE, "备份内部 Flash（第 1 遍）", sink=sink)
        sink.flush()
        os.fsync(sink.fileno())
    read_flash(link, BASE, FLASH_SIZE, "核对备份（第 2 遍）", expected=first)
    os.replace(part, folder / "internal-8MiB.bin")
    # Raw identity is local only. Exported diagnostic logs intentionally omit it.
    save_json(folder / "backup.json", dict(bytes=FLASH_SIZE, sha256=digest(first),
              base=hex(BASE), verified_twice=True, device=state, external_flash_backed_up=False))
    emit("backup", path=str(folder), sha256=digest(first), verified=True)
    return first


def reset(link, stream):
    link.send(bsl.BSL_CMD_NORMAL_RESET)
    stream.flush()
    time.sleep(1)


def write_verify(link, name, address, data):
    emit("stage", stage="写入 " + name)
    send_stage(link, address, data, DEFAULT_CHUNK,
               progress=lambda d, t: progress("写入 " + name, d, t))
    read_flash(link, address, len(data), "读回核对 " + name, expected=data)


def convert_core(link, entries):
    # Match the successful EC600U native conversion, but fail on *every* NAK.
    # Physical boot is last; never assume a template is the board's raw NV.
    for name in ("AP", "APPIMG", "PS", "BOOTLOADER"):
        address, data = entries[name]
        if not BASE <= address < address + len(data) <= BASE + FLASH_SIZE:
            raise SetupError("PAC_RANGE", "核心分区超出内部 Flash。")
        write_verify(link, name, address, data)
    for name, address, param in (("FMT_FSSYS", 0xFE000006, b"SYSF"), ("FLASH", 0xFE000001, b"\0" * 4)):
        emit("stage", stage="格式化 " + name)
        link.command(bsl.BSL_CMD_ERASE_FLASH, struct.pack(">I", address) + param, what=name)
    # Keep the PAC's PREPACK -> NV -> INDELTANV order. END failures are errors,
    # unlike the historical tool which only warned and continued.
    for name in ("PREPACK", "NV", "INDELTANV"):
        address, data = entries[name]
        emit("stage", stage="初始化 " + name)
        if name == "NV":
            data = native._nv_fix_crc(data)
            link.command(bsl.BSL_CMD_START_DATA, struct.pack(">III", address, len(data), sum(data) & 0xFFFFFFFF), what="NV START")
            for off in range(0, len(data), DEFAULT_CHUNK):
                link.command(bsl.BSL_CMD_MIDST_DATA, data[off:off + DEFAULT_CHUNK], what="NV MIDST")
                progress("初始化 NV", min(off + DEFAULT_CHUNK, len(data)), len(data))
            link.command(bsl.BSL_CMD_END_DATA, what="NV END")
        else:
            send_stage(link, address, data, DEFAULT_CHUNK,
                       progress=lambda d, t, n=name: progress("初始化 " + n, d, t))


def xxh32(data):
    """Protocol checksum for small setup packets; no additional native package."""
    mask = 0xFFFFFFFF
    p1, p2, p3, p4, p5 = 0x9E3779B1, 0x85EBCA77, 0xC2B2AE3D, 0x27D4EB2F, 0x165667B1
    def rot(value, count):
        return ((value << count) | (value >> (32 - count))) & mask
    offset, size = 0, len(data)
    if size >= 16:
        values = [(p1 + p2) & mask, p2, 0, (-p1) & mask]
        while offset <= size - 16:
            for i in range(4):
                value = struct.unpack_from("<I", data, offset)[0]
                values[i] = rot((values[i] + value * p2) & mask, 13) * p1 & mask
                offset += 4
        value = sum(rot(v, n) for v, n in zip(values, (1, 7, 12, 18))) & mask
    else:
        value = p5
    value = (value + size) & mask
    while offset <= size - 4:
        value = rot((value + struct.unpack_from("<I", data, offset)[0] * p3) & mask, 17) * p4 & mask
        offset += 4
    while offset < size:
        value = rot((value + data[offset] * p5) & mask, 11) * p1 & mask
        offset += 1
    value = (value ^ (value >> 15)) * p2 & mask
    value = (value ^ (value >> 13)) * p3 & mask
    return value ^ (value >> 16)


def hello(port):
    head = struct.pack("<IBBHIIIII", 0x31434451, 1, 1, 0, 1, 0, 0, 0, xxh32(b""))
    packet = head + struct.pack("<I", xxh32(head))
    with serial.Serial(port, 115200, timeout=0.2, write_timeout=2) as stream:
        stream.reset_input_buffer()
        stream.write(packet)
        response = bytearray()
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline and len(response) < 56:
            response.extend(stream.read(56 - len(response)))
    if len(response) != 56:
        raise SetupError("HELLO_TIMEOUT", "刷写后未收到 QDC1 握手。不能把单纯写入成功当作联动成功。")
    magic, version, kind, flags, seq, offset, length, raw, check, header = struct.unpack_from("<IBBHIIIIII", response)
    payload = response[32:]
    if (magic, version, kind, flags, seq, offset, length, raw) != (0x31434451, 1, 128, 0, 1, 0, 24, 24) or header != xxh32(response[:28]) or check != xxh32(payload):
        raise SetupError("HELLO_INVALID", "握手回复格式/校验不正确。")
    values = struct.unpack("<6I", payload)
    if values[0] != 0 or values[5] < 128 * 1024:
        raise SetupError("HELLO_INVALID", "固件没有返回有效的 QDC1 能力。")
    return dict(hello=True, maximum_block=values[5])


def flash(pac, app, folder, approved, backup_only=False):
    entries = pac_entries(pac)
    image = app.read_bytes()
    validate_app(image)
    state = detect(probe=True)
    if state["state"] == "missing":
        raise SetupError("NO_DEVICE", "未检测到设备；未触发下载或写入。")
    if not approved and not backup_only:
        raise SetupError("CONFIRMATION_REQUIRED", "必须通过入口明确确认刷写。")
    port = enter_download(state)
    link, stream = open_loader(port, entries)
    mutated, finished = False, False
    report = dict(success=False, flash_modified=False, backup=str(folder), core="unknown")
    try:
        first = backup(link, folder, state)
        actual_core = first[0x10000:0x10000 + len(entries["AP"][1])]
        core = R03 if digest(actual_core) == CORE_HASH else R05 if R05.encode() in actual_core else "unsupported"
        report["core"] = core
        if core == "unsupported":
            raise SetupError("UNSUPPORTED_CORE", "Flash 内核心不是已核对的 R03 或原厂 R05。备份已保留，不写入。")
        if backup_only:
            finished = True
        else:
            mutated = True  # Set before START_DATA: errors may already modify flash.
            if core == R05:
                convert_core(link, entries)
                reset(link, stream)
                stream.close()
                normal = wait_state("normal", 120)
                if detect(probe=True)["core"] != R03:
                    raise SetupError("CORE_BOOT_FAILED", "官方核心重启后版本不匹配。已保留刷写前备份。")
                port = enter_download(normal, after_write=True)
                link, stream = open_loader(port, entries)
                read_flash(link, 0x60010000, len(entries["AP"][1]), "再次核对 R03 核心", expected=entries["AP"][1])
            write_verify(link, "QDisplay APP", APP_BASE, image)
            finished = True
        reset(link, stream)
        stream.close()
        normal = wait_state("normal", 90)
        if not backup_only:
            deadline = time.monotonic() + 25
            while not normal["data_port"] and time.monotonic() < deadline:
                time.sleep(0.5)
                normal = detect()
            if not normal["data_port"]:
                raise SetupError("DATA_PORT_MISSING", "固件已写入但数据接口未枚举。请检查 USB 串口驱动。")
            report.update(hello(normal["data_port"]))
        report.update(success=True, flash_modified=mutated, backup_only=backup_only)
        emit("result", **report)
    except BaseException:
        report.update(flash_modified=mutated, flash_verified=finished, download_mode_kept=mutated and not finished)
        if mutated and not finished:
            emit("recovery", message="写入未完成；保留下载状态，未强制重启。备份仍在本地。", backup=str(folder))
        elif not mutated:
            try:
                reset(link, stream)
            except Exception:
                pass
        raise
    finally:
        stream.close()
        save_json(folder.parent / (folder.name + "-result.json"), report)


def recovery_image(folder):
    metadata = json.loads((folder / "backup.json").read_text(encoding="utf-8"))
    image = (folder / "internal-8MiB.bin").read_bytes()
    if not metadata.get("verified_twice") or metadata.get("bytes") != FLASH_SIZE or len(image) != FLASH_SIZE or metadata.get("base") != hex(BASE) or digest(image) != metadata.get("sha256"):
        raise SetupError("BACKUP_INVALID", "恢复文件不是两遍核对过的本机完整内部备份，或指纹不匹配。")
    if not (R03.encode() in image[0x10000:APP_BASE - BASE] or R05.encode() in image[0x10000:APP_BASE - BASE]):
        raise SetupError("BACKUP_CORE", "备份不含已支持的 R03/R05 核心版本。")
    return image


def restore(pac, source, safety_folder, approved_own_device):
    entries = pac_entries(pac)
    original = recovery_image(source)
    if not approved_own_device:
        raise SetupError("OWN_BACKUP_CONFIRMATION", "必须确认此备份由当前这台设备生成。")
    # Download USB identity is generic. Software cannot prove which board it is;
    # explicit own-device confirmation is required, never a hidden --force path.
    state = detect()
    port = enter_download(state)
    link, stream = open_loader(port, entries)
    mutated, finished = False, False
    report = dict(success=False, flash_modified=False, restored_from=str(source), backup=str(safety_folder))
    try:
        current = backup(link, safety_folder, state)
        sector = 0x10000
        # Restore changed 64 KiB groups, boot last. Preserve an additional
        # double-read snapshot of the failed/current state before overwriting it.
        offsets = list(range(sector, FLASH_SIZE, sector)) + [0]
        for offset in offsets:
            data = original[offset:offset + sector]
            if current[offset:offset + sector] == data:
                progress("恢复未变化区域（跳过）", offset + sector, FLASH_SIZE)
                continue
            mutated = True
            write_verify(link, f"恢复 {BASE + offset:#x}", BASE + offset, data)
        read_flash(link, BASE, FLASH_SIZE, "核对完整恢复镜像", expected=original)
        finished = True
        reset(link, stream)
        stream.close()
        wait_state("normal", 120)
        report.update(success=True, flash_modified=mutated, restored=True)
        emit("result", **report)
    except BaseException:
        report.update(flash_modified=mutated, flash_verified=finished, download_mode_kept=mutated and not finished)
        if mutated and not finished:
            emit("recovery", message="恢复未完成，保留下载状态；原备份和恢复前备份仍保留。", backup=str(safety_folder))
        elif not mutated:
            try:
                reset(link, stream)
            except Exception:
                pass
        raise
    finally:
        stream.close()
        save_json(safety_folder.parent / (safety_folder.name + "-result.json"), report)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    detection = commands.add_parser("detect")
    detection.add_argument("--probe", action="store_true")
    commands.add_parser("verify-running")
    unpack = commands.add_parser("unpack")
    unpack.add_argument("source", type=Path)
    unpack.add_argument("destination", type=Path)
    prepare = commands.add_parser("validate")
    update = commands.add_parser("flash")
    for command in (prepare, update):
        command.add_argument("--pac", type=Path, required=True)
        command.add_argument("--app", type=Path, required=True)
    update.add_argument("--backup", type=Path, required=True)
    update.add_argument("--confirmed", action="store_true")
    update.add_argument("--backup-only", action="store_true")
    recovery = commands.add_parser("restore")
    recovery.add_argument("--pac", type=Path, required=True)
    recovery.add_argument("--from-backup", type=Path, required=True)
    recovery.add_argument("--safety-backup", type=Path, required=True)
    recovery.add_argument("--confirmed-own-device", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "detect":
            result = detect(args.probe)
            # USB instance IDs are for local backup binding, never diagnostic stdout.
            for row in result["ports"]:
                row.pop("identity", None)
            emit("result", **result)
        elif args.command == "unpack":
            unpack_pac(args.source, args.destination)
        elif args.command == "verify-running":
            state = detect(probe=True)
            if state["core"] != R03 or not state["data_port"]:
                raise SetupError("DATA_PORT_MISSING", "未找到运行 QDisplay 的 R03 数据接口。")
            emit("result", success=True, **hello(state["data_port"]))
        elif args.command == "validate":
            pac_entries(args.pac)
            validate_app(args.app.read_bytes())
            emit("result", success=True, message="PAC、loader、APP 的 SHA/CRC/地址校验通过。")
        elif args.command == "restore":
            restore(args.pac, args.from_backup, args.safety_backup, args.confirmed_own_device)
        else:
            flash(args.pac, args.app, args.backup, args.confirmed, args.backup_only)
        return 0
    except (Exception, KeyboardInterrupt) as exc:
        emit("error", code=getattr(exc, "code", "CANCELLED" if isinstance(exc, KeyboardInterrupt) else "BACKEND_ERROR"),
             message=str(exc), exception=type(exc).__name__)
        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
