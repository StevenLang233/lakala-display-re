"""Verify curated source and demo release fingerprints without device IO."""
from pathlib import Path
import hashlib, json, argparse
DEMO=Path(__file__).resolve().parents[1]
MAIN=DEMO.parent
def sha(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()
snapshot=json.loads((DEMO/'SOURCE_SNAPSHOT.json').read_text(encoding='utf-8'))
checked=0
for group in ('firmware_source','desktop_source','generated_assets'):
    for name,expected in snapshot[group].items():
        assert sha(MAIN/name)==expected, 'Changed snapshot file: '+name
        checked+=1
release=json.loads((DEMO/'releases/manifest.json').read_text(encoding='utf-8'))
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--assets-dir',type=Path,default=MAIN.parent/'junk/publish'/release['tag'])
parser.add_argument('--source-only',action='store_true',help='verify a clone without local Release files/dependency DLLs')
args=parser.parse_args()
if not args.source_only:
    assert sha(args.assets_dir/release['firmware']['file'])==release['firmware']['sha256']
    assert sha(args.assets_dir/release['windows']['msi'])==release['windows']['sha256']
for dependency in json.loads((DEMO/'dependencies/desktop/packages.lock.json').read_text(encoding='utf-8-sig')):
    if not args.source_only:
        assert sha(DEMO/'dependencies/desktop'/dependency['assembly']).upper()==dependency['assembly_sha256'].upper()
print(json.dumps({'source_and_asset_files_verified':checked,'firmware_release_verified':not args.source_only,'msi_release_verified':not args.source_only,'dependencies_verified':0 if args.source_only else 5}))
