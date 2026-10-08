"""Collect the public flasher, frozen setup package and Demo files for one Release."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[3]
TAG = "tools-v1.0.0"
SETUP_HASH = "1d16681760edd8960bbafb1c02c6db30624d31184006cba257bba014588ff5a5"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--git", default="git")
    args = parser.parse_args()
    status = subprocess.run([args.git, "status", "--porcelain"], cwd=ROOT, check=True, capture_output=True).stdout
    if status:
        raise SystemExit("Commit the reviewed source before preparing the collection.")
    commit = subprocess.run([args.git, "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True).stdout.decode().strip()
    old = ROOT / "junk/publish/v0.3.0-demo.20261009"
    setup = ROOT / "junk/publish/setup-v1.0.0/QDisplay-Setup-1.0.0.zip"
    locks = json.loads((ROOT / "main/demo/setup/dependencies.lock.json").read_text(encoding="utf-8"))["downloads"]
    sources = [
        (ROOT / "main/demo/setup/QDisplay-Flash.cmd", None),
        (setup, SETUP_HASH),
        (old / "firmware/qdisplay_native.bin", locks["app"]["sha256"]),
        (old / "windows/QDisplay-0.3.0-x64.msi", locks["host"]["sha256"]),
        (old / "QDisplay-0.3.0-Windows-files.zip", "a45d06597f9fe79c431eedbf3cfaec0da2bf82ff585b378c398ff0dbaa4237e4"),
        (old / "QDisplay-0.3.0-LICENSES.zip", locks["licenses"]["sha256"]),
    ]
    output = ROOT / "junk/publish" / TAG
    output.mkdir(parents=True, exist_ok=True)
    inventory = []
    for source, expected in sources:
        digest = sha(source)
        if expected and digest != expected:
            raise SystemExit("Frozen artifact mismatch: " + source.name)
        target = output / source.name
        if target.exists() and sha(target) != digest:
            raise SystemExit("Refusing to replace a different collection artifact: " + target.name)
        shutil.copyfile(source, target)
        if sha(target) != digest:
            raise SystemExit("Collection copy mismatch: " + target.name)
        inventory.append(dict(file=target.name, bytes=target.stat().st_size, sha256=digest))
    report = dict(tag=TAG, source_commit=commit, demo="0.3.0", setup="1.0.0",
                  setup_source_commit="85b3c4763a0523868af2044757452c4a509c2548",
                  vendor_rom_bundled=False, private_data_bundled=False, files=inventory)
    manifest = output / "tools-manifest.json"
    manifest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sums = [row["sha256"] + "  " + row["file"] for row in inventory]
    sums.append(sha(manifest) + "  " + manifest.name)
    (output / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="ascii")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
