"""Build a basic-use ZIP without vendor ROMs, Python runtimes, NV or history."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[3]
SETUP = ROOT / "main/demo/setup"
VERSION = "1.0.0"
TAG = "setup-v" + VERSION


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--git", default="git")
    parser.add_argument("--demo-assets", type=Path, default=ROOT / "junk/publish/v0.3.0-demo.20261009")
    parser.add_argument("--output", type=Path, default=ROOT / "junk/publish" / TAG)
    args = parser.parse_args()
    output = args.output.resolve()
    output.relative_to((ROOT / "junk").resolve())
    output.mkdir(parents=True, exist_ok=True)
    lock = json.loads((SETUP / "dependencies.lock.json").read_text(encoding="utf-8"))
    names = subprocess.run([args.git, "-c", "core.quotepath=false", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT, check=True, capture_output=True).stdout
    source = sorted(set(n.decode("utf-8") for n in names.split(b"\0") if n))
    allowed = {"README.md", "LICENSE", ".gitignore", ".gitattributes", "一键刷机.bat"}
    pairs = []
    for name in source:
        if name not in allowed and not name.startswith("main/"):
            raise SystemExit("Unexpected source path: " + name)
        if name.startswith(("main/reverse/private/", "main/demo/build/")) or Path(name).suffix.lower() in (".exe", ".dll", ".msi", ".zip", ".img", ".nupkg"):
            raise SystemExit("Private/binary source file: " + name)
        if Path(name).suffix.lower() == ".bin" and name not in ("main/reverse/evidence/protocol/hello.bin", "main/reverse/evidence/protocol/hello_ack_example.bin"):
            raise SystemExit("Unexpected binary: " + name)
        pairs.append((name, ROOT / name))
    asset_map = {"app": "firmware", "host": "windows", "licenses": ""}
    for key, folder in asset_map.items():
        item = lock["downloads"][key]
        path = args.demo_assets / folder / item["file"]
        if sha(path) != item["sha256"]:
            raise SystemExit("Frozen demo asset mismatch: " + item["file"])
        pairs.append(("offline/" + item["file"], path))
    prefix = "QDisplay-Setup-" + VERSION + "/"
    inventory = [{"file": name, "bytes": path.stat().st_size, "sha256": sha(path)} for name, path in pairs]
    filename = prefix.rstrip("/") + ".zip"
    destination = output / filename
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, path in pairs:
            info = zipfile.ZipInfo(prefix + name, (2026, 10, 9, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
        info = zipfile.ZipInfo(prefix + "SETUP-CONTENTS.json", (2026, 10, 9, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, json.dumps(dict(files=inventory), ensure_ascii=False, indent=2) + "\n")
    with zipfile.ZipFile(destination) as archive:
        for row in inventory:
            if hashlib.sha256(archive.read(prefix + row["file"])).hexdigest() != row["sha256"]:
                raise SystemExit("ZIP readback mismatch: " + row["file"])
    report = dict(version=VERSION, tag=TAG, file=filename, bytes=destination.stat().st_size,
                  sha256=sha(destination), files=len(inventory), demo="0.3.0",
                  vendor_core_bundled=False, python_runtime_bundled=False, vendor_usb_driver_bundled=False,
                  private_data_bundled=False, source_content_sha256=hashlib.sha256(
                      json.dumps(inventory, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest())
    (output / "setup-manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "SHA256SUMS.txt").write_text(sha(destination) + "  " + filename + "\n" + sha(output / "setup-manifest.json") + "  setup-manifest.json\n", encoding="ascii")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
