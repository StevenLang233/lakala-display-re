"""Package license texts and scope separately without changing published binaries."""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[3]
DEMO = ROOT / 'main/demo'


def license_paths():
    files = [ROOT / 'LICENSE', ROOT / 'main/LICENSE_SCOPE.md', DEMO / 'THIRD_PARTY.md',
             ROOT / 'main/reverse/evidence/abi/SDK-LICENSE',
             ROOT / 'main/reverse/evidence/abi/APACHE-2.0.txt',
             DEMO / 'firmware/src/third_party/LICENSE.lz4',
             DEMO / 'firmware/src/third_party/LICENSE.xxhash',
             DEMO / 'third_party/sprdflash-LICENSE', DEMO / 'third_party/sprdproto-LICENSE',
             DEMO / 'third_party/SOURCE-HEADER-NOTICES.txt']
    files += list((DEMO / 'third_party/runtime').glob('COPYING*'))
    files += [p for p in (DEMO / 'dependencies/desktop').iterdir()
              if p.is_file() and ('LICENSE' in p.name or 'NOTICES' in p.name)]
    for path in files:
        if not path.is_file():
            raise FileNotFoundError(path.relative_to(ROOT))
    return sorted(set(files))


def notice_text():
    return '\n\n'.join('===== ' + p.relative_to(ROOT).as_posix() + ' =====\n' +
                         p.read_text(encoding='utf-8-sig') for p in license_paths()) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--notice-output', type=Path)
    args = parser.parse_args()
    metadata = json.loads((DEMO / 'releases/manifest.json').read_text(encoding='utf-8'))
    destination = (args.output_dir or ROOT / 'junk/publish' / metadata['tag']).resolve()
    if not destination.is_relative_to(ROOT):
        raise ValueError('License output must stay inside the workspace')
    destination.mkdir(parents=True, exist_ok=True)
    name = 'QDisplay-' + metadata['windows']['version'] + '-LICENSES.zip'
    archive_path = destination / name
    paths = license_paths()
    with zipfile.ZipFile(archive_path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            item = zipfile.ZipInfo(path.relative_to(ROOT).as_posix(), (1980, 1, 1, 0, 0, 0))
            item.compress_type = zipfile.ZIP_DEFLATED
            item.external_attr = 0o100644 << 16
            archive.writestr(item, path.read_bytes())
    with zipfile.ZipFile(archive_path) as archive:
        if archive.namelist() != [p.relative_to(ROOT).as_posix() for p in paths]:
            raise ValueError('License ZIP file list mismatch')
        for path in paths:
            if archive.read(path.relative_to(ROOT).as_posix()) != path.read_bytes():
                raise ValueError('License ZIP content mismatch')
    result = {'file': name, 'bytes': archive_path.stat().st_size,
              'sha256': hashlib.sha256(archive_path.read_bytes()).hexdigest(),
              'scope': 'original portions only; third-party licenses retained',
              'files': [p.relative_to(ROOT).as_posix() for p in paths]}
    (DEMO / 'releases/license-bundle.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if args.notice_output:
        output = args.notice_output.resolve()
        if not output.is_relative_to(ROOT):
            raise ValueError('Notice output must stay inside the workspace')
        output.write_text(notice_text(), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
