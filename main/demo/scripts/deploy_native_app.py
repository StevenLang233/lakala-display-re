"""Back up and verify the R03 core, then optionally replace only APPIMG.

No erase/format commands; bootloader, radio firmware, calibration and user FS
are never written. The RAM download loaders come from the installed R03 PAC.
"""
from pathlib import Path
import argparse, hashlib, json, struct, sys, time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'third_party'))
import serial
from serial.tools import list_ports
from sprdflash import pdl, protocol as p
from sprdflash.flasher import send_stage, DEFAULT_CHUNK

QPY = ROOT/'analysis/helios_sdk_review_20261005/pac_qpy'
APP_BASE, APP_SIZE = 0x60260000, 0xe0000
CORE_HASH = '187abb282fd089e6c3fb9d8bb75b837826b1a726e943fe961e5bf052da433ca9'

def sha(data):
    return hashlib.sha256(data).hexdigest()

class BufferedPort:
    """Avoid one Windows kernel read for every byte of a BSL response."""
    def __init__(self, port):
        self.port, self.buffer = port, bytearray()
    def read(self, n):
        if not self.buffer:
            self.buffer.extend(self.port.read(max(n, self.port.in_waiting)))
        out = bytes(self.buffer[:n]); del self.buffer[:n]
        return out
    def write(self, data):
        return self.port.write(data)
    def flush(self):
        self.port.flush()

def read_flash(io, address, size, path=None):
    result = bytearray()
    last = time.monotonic()
    for off in range(0, size, 4096):
        count = min(4096, size-off)
        # R03 FDL2 ignores the third field for physical NOR addresses. Advance
        # the absolute address; using base+offset fields repeats the first block.
        data = io.command(p.BSL_CMD_READ_FLASH, struct.pack('>III', address+off, count, 0),
                          expect=p.BSL_REP_READ_FLASH, timeout=5)
        if len(data) != count:
            raise RuntimeError(f'short read at {address+off:#x}: {len(data)}/{count}')
        result.extend(data)
        if time.monotonic()-last > 10:
            print(f'Read {address:#x}: {len(result)}/{size}', flush=True)
            last = time.monotonic()
    if path:
        path.write_bytes(result)
    return bytes(result)

def main():
    global QPY
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--at-port', required=True, help='explicit VID/PID-verified MI_02 AT port')
    parser.add_argument('--qpy-inputs',type=Path,required=True)
    parser.add_argument('--image', type=Path, help='omit to only back up and check recovery')
    args = parser.parse_args()
    QPY=args.qpy_inputs
    reference = (QPY/'AP_8915DM_cat1_open.sign.img').read_bytes()
    if sha(reference) != CORE_HASH:
        raise RuntimeError('reference R03 core hash mismatch')
    image = args.image.read_bytes() if args.image else None
    if image is not None:
        if not 128 <= len(image) <= APP_SIZE:
            raise RuntimeError('APPIMG exceeds its partition')
        magic, length = struct.unpack_from('<II', image)
        if magic != 0x41505032 or length != len(image):
            raise RuntimeError('invalid APPIMG header or length')
        # Every load/clear descriptor must stay within the known APP ownership.
        for i in range(32, 128, 16):
            kind, offset, size, address = struct.unpack_from('<4I', image, i)
            if not kind:
                continue
            low, high = (APP_BASE, APP_BASE+APP_SIZE) if kind == 4 else (0x80f00000, 0x81000000)
            if kind not in (1,2,3,4) or not low <= address <= address+size <= high:
                raise RuntimeError('APPIMG load address outside owned memory')
            if kind != 3 and offset+size > len(image):
                raise RuntimeError('APPIMG load descriptor exceeds file')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output = ROOT.parent/'reverse/private/backups/demo_app_updates'/stamp
    output.mkdir(parents=True)
    report = dict(success=False, app_address=hex(APP_BASE), output=str(output),
                  image_sha256=sha(image) if image else None, written=False)
    print(f'Backup/report: {output}', flush=True)
    port, io = None, None
    try:
        ports = list(list_ports.comports())
        download = [x for x in ports if (x.vid,x.pid)==(0x0525,0xa4a7)]
        if not download:
            match = [x for x in ports if x.device==args.at_port and (x.vid,x.pid)==(0x2c7c,0x0901)]
            if len(match)!=1:
                raise RuntimeError('AT port does not identify the expected Quectel board')
            with serial.Serial(args.at_port,115200,timeout=.2,write_timeout=3) as at:
                at.write(b'AT\r'); at.flush()
                response = at.read(1024)
                if b'OK' not in response:
                    raise RuntimeError(f'AT port did not answer OK: {response!r}')
                at.write(b'AT+QDOWNLOAD=1\r'); at.flush()
                time.sleep(.5)
            print('Requested RAM download mode', flush=True)
        deadline = time.monotonic()+30
        while time.monotonic()<deadline:
            download = [x for x in list_ports.comports() if (x.vid,x.pid)==(0x0525,0xa4a7)]
            if len(download)==1:
                try:
                    port=serial.Serial(download[0].device,115200,timeout=.02,write_timeout=5)
                    break
                except serial.SerialException:
                    pass
            time.sleep(.2)
        if port is None:
            raise RuntimeError('download COM port not available')
        print(f'Download: {port.port}', flush=True)
        port.dtr=True; port.rts=True; time.sleep(.1); port.reset_input_buffer()
        buffered=BufferedPort(port)
        loader1=(QPY/'HOST_FDL_fdl1.sign.img').read_bytes()
        loader2=(QPY/'FDL2_fdl2.sign.img').read_bytes()
        if sha(loader1)!='cfad226ef5d892ee24609e0e3104109d459cd1daf3206357e698a1253ef67968' or sha(loader2)!='61ba99f74ea0614fd5996064670dc1caa705ef044a8acc919a8872557a38309a':
            raise RuntimeError('R03 RAM loader hash mismatch')
        pio=pdl.PdlIO(buffered,timeout=3)
        pio.connect(); print('PDL connected', flush=True)
        pio.send_image(0x8000c0,loader1,checksum=0)
        version=pio.exec_and_get_ver(timeout=8)
        report['fdl1_version_frame']=version.hex()
        print('FDL1 running', flush=True)
        io=p.SpdIO(buffered,timeout=3); io.checksum='sprd'; io.connect()
        send_stage(io,0x810000,loader2,DEFAULT_CHUNK)
        io.command(p.BSL_CMD_EXEC_DATA,timeout=15); io.connect()
        print('FDL2 running; reading installed core', flush=True)
        actual=read_flash(io,0x60010000,len(reference),output/'AP.bin')
        report['core_sha256']=sha(actual)
        if actual!=reference:
            raise RuntimeError('installed core differs from audited R03; no flash write allowed')
        before=read_flash(io,APP_BASE,APP_SIZE,output/'APPIMG_before.bin')
        report['app_before_sha256']=sha(before)
        # A second independent read validates the recovery copy before mutation.
        check=read_flash(io,APP_BASE,APP_SIZE)
        if check!=before:
            raise RuntimeError('APPIMG backup readback mismatch')
        report['backup_verified']=True
        (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        if image is not None:
            print(f'Writing APPIMG only: {len(image)} bytes', flush=True)
            send_stage(io,APP_BASE,image,DEFAULT_CHUNK)
            report['written']=True
            after=read_flash(io,APP_BASE,len(image),output/'APPIMG_after.bin')
            if after!=image:
                raise RuntimeError('APPIMG write verification mismatch; recovery backup is retained')
            report['readback_verified']=True
        report['success']=True
    except Exception as exc:
        report['error']=repr(exc)
        raise
    finally:
        if io is not None:
            try:
                io.send(p.BSL_CMD_NORMAL_RESET); port.flush(); time.sleep(1)
                report['reset_sent']=True
            except Exception as exc:
                report['reset_error']=repr(exc)
        if port:
            port.close()
        (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,ensure_ascii=True), flush=True)

if __name__=='__main__':
    main()
