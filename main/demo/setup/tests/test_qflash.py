"""Safety tests: fake USB responses, no hardware access or system changes."""
from pathlib import Path
import contextlib
import hashlib
import io
import json
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import qflash as q


class MemoryLink:
    def __init__(self, image, wrong_on_second=False, short=False):
        self.image = image
        self.calls = []
        self.wrong_on_second = wrong_on_second
        self.short = short

    def command(self, cmd, data, **kwargs):
        address, count, unused = struct.unpack(">III", data)
        self.calls.append((cmd, address, count, unused))
        start = address - q.BASE
        result = self.image[start:start + count]
        if self.short:
            return result[:-1]
        if self.wrong_on_second and len(self.calls) > 2:
            return bytes([result[0] ^ 1]) + result[1:]
        return result


class FakeStream:
    def __init__(self):
        self.closed = 0
    def close(self):
        self.closed += 1


class Safety(unittest.TestCase):
    def setUp(self):
        self.quiet = patch.object(q, "emit")
        self.events = self.quiet.start()
        self.progress = patch.object(q, "progress")
        self.progress.start()

    def tearDown(self):
        self.quiet.stop()
        self.progress.stop()

    def test_checksum_matches_public_packet(self):
        path = Path(__file__).resolve().parents[3] / "reverse/evidence/protocol/hello.bin"
        packet = path.read_bytes()
        self.assertEqual(q.xxh32(b""), 0x02CC5D05)
        self.assertEqual(q.xxh32(packet[:28]), struct.unpack_from("<I", packet, 28)[0])

    def test_physical_reads_advance_absolute_address(self):
        data = bytes(range(251)) * 35
        link = MemoryLink(data)
        self.assertEqual(q.read_flash(link, q.BASE, len(data), "read"), data)
        self.assertEqual([r[1] for r in link.calls], [q.BASE, q.BASE + 4096, q.BASE + 8192])
        self.assertTrue(all(r[3] == 0 for r in link.calls))

    def test_short_usb_read_rejected(self):
        with self.assertRaises(q.SetupError) as error:
            q.read_flash(MemoryLink(b"A" * 32, short=True), q.BASE, 32, "read")
        self.assertEqual(error.exception.code, "SHORT_READ")

    def test_readback_mismatch_rejected(self):
        with self.assertRaises(q.SetupError) as error:
            q.read_flash(MemoryLink(b"B" * 32), q.BASE, 32, "verify", expected=b"A" * 32)
        self.assertEqual(error.exception.code, "READBACK_MISMATCH")

    def test_backup_is_not_marked_verified_after_second_read_mismatch(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(q, "FLASH_SIZE", 8192):
            folder = Path(temp) / "backup"
            with self.assertRaises(q.SetupError):
                q.backup(MemoryLink(b"A" * 8192, wrong_on_second=True), folder, {"state": "normal"})
            self.assertTrue((folder / "internal-8MiB.bin.partial").exists())
            self.assertFalse((folder / "backup.json").exists())
            self.assertFalse((folder / "internal-8MiB.bin").exists())

    def test_backup_contains_this_devices_bytes_and_verified_hash(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(q, "FLASH_SIZE", 8192):
            folder = Path(temp) / "backup"
            image = bytes(range(256)) * 32
            q.backup(MemoryLink(image), folder, {"identity": "LOCAL-ONLY"})
            meta = json.loads((folder / "backup.json").read_text())
            self.assertTrue(meta["verified_twice"])
            self.assertEqual(meta["sha256"], hashlib.sha256(image).hexdigest())
            self.assertEqual((folder / "internal-8MiB.bin").read_bytes(), image)

    def test_app_unlocked_or_corrupt_file_rejected(self):
        with self.assertRaises(q.SetupError) as error:
            q.validate_app(b"APP2" + b"\0" * 128)
        self.assertEqual(error.exception.code, "APP_HASH")

    def test_app_descriptor_cannot_clear_unowned_ram(self):
        data = bytearray(128)
        struct.pack_into("<II", data, 0, 0x41505032, len(data))
        struct.pack_into("<4I", data, 32, 3, 0, 16, 0x80000000)
        with patch.object(q, "APP_HASH", q.digest(data)), self.assertRaises(q.SetupError) as error:
            q.validate_app(data)
        self.assertEqual(error.exception.code, "APP_RANGE")

    def test_unknown_com_ports_are_never_probed(self):
        ports = [SimpleNamespace(device="COM99", vid=0x2C7C, pid=0x0901, hwid="DIAG")]
        with patch.object(q.list_ports, "comports", return_value=ports), patch.object(q, "port_roles", return_value={}), patch.object(q, "at_command") as at:
            state = q.detect(probe=True)
        self.assertEqual(state["state"], "missing")
        at.assert_not_called()

    def test_multiple_boards_rejected_before_any_commands(self):
        ports = [SimpleNamespace(device="COM8", vid=0x2C7C, pid=0x0901), SimpleNamespace(device="COM9", vid=0x2C7C, pid=0x0901)]
        with patch.object(q.list_ports, "comports", return_value=ports), patch.object(q, "port_roles", return_value={"COM8": ("at", "one"), "COM9": ("at", "two")}), patch.object(q, "at_command") as at:
            with self.assertRaises(q.SetupError) as error:
                q.detect(probe=True)
        self.assertEqual(error.exception.code, "MULTIPLE_DEVICES")
        at.assert_not_called()

    def test_rejected_pdl_ack_is_fatal(self):
        first = q.StrictPdl(None)
        with patch.object(first, "send"), patch.object(first, "recv", return_value=(1, b"")):
            with self.assertRaises(q.SetupError):
                first.command(b"test", what="START")

    def flash_case(self, approved=True, fail_write=False, unknown=False, fail_backup=False, backup_only=False):
        with tempfile.TemporaryDirectory() as temp, contextlib.ExitStack() as stack:
            folder = Path(temp) / "backup"
            app = Path(temp) / "app.bin"
            app.write_bytes(b"APP")
            state = dict(state="normal", core=q.R03, at_port="COM8", data_port="COM5")
            reference = b"REFERENCE"
            original = b"\0" * 0x10000 + (b"UNKNOWN!!" if unknown else reference)
            link, stream = object(), FakeStream()
            stack.enter_context(patch.object(q, "pac_entries", return_value={"AP": (q.BASE + 0x10000, reference)}))
            stack.enter_context(patch.object(q, "validate_app"))
            stack.enter_context(patch.object(q, "CORE_HASH", q.digest(reference)))
            stack.enter_context(patch.object(q, "detect", return_value=state))
            enter = stack.enter_context(patch.object(q, "enter_download", return_value="COM10"))
            stack.enter_context(patch.object(q, "open_loader", return_value=(link, stream)))
            def do_backup(*_):
                folder.mkdir()
                if fail_backup:
                    raise q.SetupError("READBACK_MISMATCH", "backup failed")
                return original
            stack.enter_context(patch.object(q, "backup", side_effect=do_backup))
            write = stack.enter_context(patch.object(q, "write_verify", side_effect=q.SetupError("USB_LOST", "disconnect") if fail_write else None))
            reset = stack.enter_context(patch.object(q, "reset"))
            stack.enter_context(patch.object(q, "wait_state", return_value=state))
            stack.enter_context(patch.object(q, "hello", return_value=dict(hello=True)))
            try:
                q.flash(Path("ignored.pac"), app, folder, approved, backup_only)
                error = None
            except q.SetupError as exc:
                error = exc.code
            report = json.loads((Path(temp) / "backup-result.json").read_text()) if (Path(temp) / "backup-result.json").exists() else None
            return error, write.call_count, reset.call_count, enter.call_count, report

    def test_unconfirmed_request_never_enters_download(self):
        error, writes, resets, enters, report = self.flash_case(approved=False)
        self.assertEqual(error, "CONFIRMATION_REQUIRED")
        self.assertEqual((writes, resets, enters), (0, 0, 0))

    def test_failed_backup_cannot_start_writing(self):
        error, writes, resets, _, report = self.flash_case(fail_backup=True)
        self.assertEqual(error, "READBACK_MISMATCH")
        self.assertEqual((writes, resets), (0, 1))
        self.assertFalse(report["flash_modified"])

    def test_partial_write_failure_keeps_loader_and_backup(self):
        error, writes, resets, _, report = self.flash_case(fail_write=True)
        self.assertEqual(error, "USB_LOST")
        self.assertEqual((writes, resets), (1, 0))
        self.assertTrue(report["download_mode_kept"])
        self.assertFalse(report["success"])

    def test_unsupported_core_backup_is_kept_without_writing(self):
        error, writes, resets, _, report = self.flash_case(unknown=True)
        self.assertEqual(error, "UNSUPPORTED_CORE")
        self.assertEqual((writes, resets), (0, 1))
        self.assertFalse(report["flash_modified"])

    def test_backup_only_changes_no_flash(self):
        error, writes, resets, _, report = self.flash_case(backup_only=True)
        self.assertIsNone(error)
        self.assertEqual((writes, resets), (0, 1))
        self.assertTrue(report["backup_only"])

    def test_success_requires_write_readback_reboot_and_hello(self):
        error, writes, resets, _, report = self.flash_case()
        self.assertIsNone(error)
        self.assertEqual((writes, resets), (1, 1))
        self.assertTrue(report["hello"])
        self.assertTrue(report["success"])

    def test_wrong_pac_is_rejected_without_using_its_table(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "wrong.pac"
            path.write_bytes(b"untrusted")
            with patch.object(q, "parse_pac") as parse, self.assertRaises(q.SetupError):
                q.pac_entries(path)
            parse.assert_not_called()

    def test_hello_checks_sequence_and_packet_hashes(self):
        payload=struct.pack('<6I',0,0,0,0,1024,520192)
        def reply(sequence=1):
            header=struct.pack('<IBBHIIIII',0x31434451,1,128,0,sequence,0,24,24,q.xxh32(payload))
            return header+struct.pack('<I',q.xxh32(header))+payload
        class SerialReply:
            def __init__(self, data): self.data=data
            def __enter__(self): return self
            def __exit__(self,*_): pass
            def reset_input_buffer(self): pass
            def write(self,_): pass
            def read(self,count): out=self.data[:count];self.data=self.data[count:];return out
        with patch.object(q.serial,'Serial',return_value=SerialReply(reply())):
            self.assertTrue(q.hello('COM5')['hello'])
        with patch.object(q.serial,'Serial',return_value=SerialReply(reply(sequence=99))),self.assertRaises(q.SetupError):
            q.hello('COM5')
        corrupt=bytearray(reply());corrupt[-1]^=1
        with patch.object(q.serial,'Serial',return_value=SerialReply(corrupt)),self.assertRaises(q.SetupError):
            q.hello('COM5')

    def test_tampered_backup_cannot_be_used_for_recovery(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(q,'FLASH_SIZE',0x20000):
            folder=Path(temp)
            data=b'\0'*0x10000+q.R03.encode()+b'\0'*(0x10000-len(q.R03))
            (folder/'internal-8MiB.bin').write_bytes(data)
            (folder/'backup.json').write_text(json.dumps(dict(bytes=len(data),base=hex(q.BASE),verified_twice=True,sha256=q.digest(data))))
            self.assertEqual(q.recovery_image(folder),data)
            changed=bytearray(data);changed[-1]=1;(folder/'internal-8MiB.bin').write_bytes(changed)
            with self.assertRaises(q.SetupError) as error:q.recovery_image(folder)
            self.assertEqual(error.exception.code,'BACKUP_INVALID')

    def test_restore_requires_own_device_confirmation_before_download(self):
        with patch.object(q,'pac_entries'),patch.object(q,'recovery_image',return_value=b'original'),patch.object(q,'enter_download') as enter:
            with self.assertRaises(q.SetupError) as error:q.restore(Path('pac'),Path('old'),Path('new'),False)
            self.assertEqual(error.exception.code,'OWN_BACKUP_CONFIRMATION')
            enter.assert_not_called()

    def test_nv_end_failure_is_not_swallowed(self):
        entries={n:(address,b'\0'*32) for n,address in [('AP',0x60010000),('APPIMG',q.APP_BASE),('PS',0x60560000),('BOOTLOADER',q.BASE),('PREPACK',0xFE000004),('NV',0xFE000003),('INDELTANV',0xFE000004)]}
        link=SimpleNamespace(command=lambda command,*args,**kwargs: (_ for _ in ()).throw(q.bsl.ProtocolError('NV END rejected')) if kwargs.get('what')=='NV END' else None)
        with patch.object(q,'write_verify'),patch.object(q,'send_stage'),self.assertRaises(q.bsl.ProtocolError):q.convert_core(link,entries)


if __name__ == "__main__":
    unittest.main()
