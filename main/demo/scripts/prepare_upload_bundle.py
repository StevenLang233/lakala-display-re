"""Offline source/Release packaging audit. No network, credentials or Git writes."""
from pathlib import Path
import hashlib, json, re, subprocess, sys, zipfile

ROOT=Path(__file__).resolve().parents[3]
MAIN=ROOT/'main'
sys.stdout.reconfigure(encoding='utf-8')
def sha(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()
def listed():
    result=subprocess.run(['git','-c','core.quotepath=false','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT,capture_output=True,check=True)
    return sorted(set(name.decode('utf-8') for name in result.stdout.split(b'\0') if name))
paths=listed()
for name in paths:
    if not (name in ('README.md','.gitignore','.gitattributes') or name.startswith('main/')): raise SystemExit('Unexpected source path: '+name)
    if re.search(r'^(junk/|main/reverse/private/|main/demo/build/)',name): raise SystemExit('Local data in Git: '+name)
    if Path(name).suffix.lower() in ('.exe','.dll','.msi','.img','.zip','.nupkg'): raise SystemExit('Binary artifact in source: '+name)
    if Path(name).suffix.lower()=='.bin' and name not in ('main/reverse/evidence/protocol/hello.bin','main/reverse/evidence/protocol/hello_ack_example.bin'):
        raise SystemExit('Firmware/package in source: '+name)
    path=ROOT/name
    if not path.is_file(): raise SystemExit('Missing source file: '+name)
    if path.suffix.lower() in ('.md','.json','.cs','.c','.h','.py','.ps1','.txt'):
        value=path.read_text(encoding='utf-8-sig')
        if re.search(r'(?:[A-Za-z]:[\\/]+Users[\\/]+[A-Za-z0-9._-]+|/Users/[A-Za-z0-9._-]+|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{25,})',value):
            raise SystemExit('Private path/key in public file: '+name)
index_rows=[{'file':name[5:],'bytes':(ROOT/name).stat().st_size,'sha256':sha(ROOT/name)}
    for name in paths if name.startswith('main/') and name!='main/PUBLIC_FILES.json']
(MAIN/'PUBLIC_FILES.json').write_text(json.dumps({'files':index_rows,'count':len(index_rows),'bytes':sum(r['bytes'] for r in index_rows)},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
paths=listed()
metadata=json.loads((MAIN/'demo/releases/manifest.json').read_text(encoding='utf-8'))
payload=ROOT/'junk/publish'/metadata['tag']
plan=json.loads((payload/'upload-plan.json').read_text(encoding='utf-8'))
expected=[]
for line in (payload/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
    digest,name=line.split('  ',1)
    if not (payload/name).is_file():
        candidate=next((Path(p) for p in plan['assets'] if Path(p).name==name),None)
    else: candidate=payload/name
    if candidate is None or sha(candidate)!=digest: raise SystemExit('Release checksum mismatch: '+name)
    expected.append(name)
zip_path=ROOT/'junk/publish/source-upload.zip'
with zipfile.ZipFile(zip_path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
    for name in paths: archive.write(ROOT/name,name)
with zipfile.ZipFile(zip_path) as archive:
    if archive.namelist()!=paths: raise SystemExit('Source ZIP file list mismatch')
    for name in paths:
        if hashlib.sha256(archive.read(name)).hexdigest()!=sha(ROOT/name): raise SystemExit('Source ZIP content mismatch: '+name)
rows=[{'file':name,'bytes':(ROOT/name).stat().st_size,'sha256':sha(ROOT/name)} for name in paths]
report={'status':'ready_local','repository_name':None,'tag':metadata['tag'],'source_files':len(paths),
    'source_bytes':sum(r['bytes'] for r in rows),'source_zip_bytes':zip_path.stat().st_size,
    'source_zip_sha256':sha(zip_path),'release_assets':[{'name':Path(p).name,'bytes':Path(p).stat().st_size,'sha256':sha(Path(p))} for p in plan['assets']],
    'source_excludes_installers_dumps_history':True,'network_executed':False,'git_index_or_remote_changed':False}
(ROOT/'junk/publish/source-file-list.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(ROOT/'junk/publish/preparation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
