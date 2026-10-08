"""Local packaging audit: sanitize copied evidence, verify archive, index public files."""
from pathlib import Path, PureWindowsPath, PurePosixPath
import hashlib, json, re, sys
ROOT=Path(__file__).resolve().parents[3]
MAIN=ROOT/'main'
sys.stdout.reconfigure(encoding='utf-8')
def sha(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()
def public_files():
    for path in MAIN.rglob('*'):
        if not path.is_file(): continue
        rel=path.relative_to(MAIN)
        if 'private' in rel.parts or 'build' in rel.parts or '__pycache__' in rel.parts or path.suffix=='.pyc': continue
        if rel.parts[:3]==('demo','dependencies','desktop') and path.suffix in ('.dll','.nupkg'): continue
        if rel.parts[:2]==('demo','releases') and path.suffix in ('.bin','.img','.msi','.exe','.dll','.zip'): continue
        yield path
def sanitize(value):
    if isinstance(value,dict): return {k:sanitize(v) for k,v in value.items()}
    if isinstance(value,list): return [sanitize(v) for v in value]
    if isinstance(value,str) and re.match(r'^[A-Za-z]:[\\/]',value): return PureWindowsPath(value).name
    if isinstance(value,str) and value.startswith(('/Users/','/private/tmp/')): return PurePosixPath(value).name
    return value
sanitized=[]
for path in (MAIN/'reverse/evidence').rglob('*'):
    if path.suffix not in ('.txt','.json') or not path.is_file(): continue
    original=path.read_text(encoding='utf-8-sig')
    if path.suffix=='.json':
        value=json.dumps(sanitize(json.loads(original)),ensure_ascii=False,indent=2)+'\n'
    else:
        # objdump's first source-path line is metadata, not an instruction.
        value=re.sub(r'(?m)^.*(?:C:\\Users\\[^\r\n]*\\|/Users/[^\r\n]*/)([^\\/\r\n]+):\s+(file format[^\r\n]*)$',r'\1:     \2',original)
    if value!=original:
        path.write_text(value,encoding='utf-8');sanitized.append(str(path.relative_to(MAIN)))
inventory=json.loads((ROOT/'junk/inventory.json').read_text(encoding='utf-8'))
failures=[]
for i,row in enumerate(inventory):
    path=ROOT/row['destination']
    # The move may put an existing filename just past Win32's 260-char limit.
    if sys.platform=='win32' and len(str(path))>=250:
        path=Path('\\\\?\\'+str(path))
    if not path.is_file(): failures.append({'file':row['destination'],'error':'missing'})
    elif path.stat().st_size!=row['bytes'] or sha(path)!=row['sha256']: failures.append({'file':row['destination'],'error':'changed'})
    if (i+1)%4000==0: print('Verified archived files:',i+1,flush=True)
audit={'archive_files':len(inventory),'archive_bytes':sum(r['bytes'] for r in inventory),
    'archive_failures':failures,'sanitized_evidence_files':sanitized}
(ROOT/'junk/integrity_check.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
if failures:
    print(json.dumps(failures[:20],ensure_ascii=False));raise SystemExit('Original archive integrity failed')
leaks=[]
for path in public_files():
    if path.suffix.lower() in ('.md','.txt','.json','.cs','.c','.h','.py','.ps1'):
        value=path.read_text(encoding='utf-8-sig')
        if re.search(r'(?:[A-Za-z]:[\\/]+Users[\\/]+[A-Za-z0-9._-]+|/Users/[A-Za-z0-9._-]+)',value,re.I):
            leaks.append(str(path.relative_to(MAIN)))
if leaks: raise SystemExit('Personal source paths remain in '+str(leaks))
rows=[{'file':str(p.relative_to(MAIN)).replace('\\','/'),'bytes':p.stat().st_size,'sha256':sha(p)}
    for p in sorted(public_files()) if p.name!='PUBLIC_FILES.json']
(MAIN/'PUBLIC_FILES.json').write_text(json.dumps({'files':rows,'count':len(rows),'bytes':sum(r['bytes'] for r in rows)},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'archive_files_verified':len(inventory),'public_files':len(rows),'public_bytes':sum(r['bytes'] for r in rows),'personal_path_scan_passed':True},ensure_ascii=False))
