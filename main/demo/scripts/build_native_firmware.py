"""Build an APPIMG-only native C application for the verified R03 core (no device IO)."""
from pathlib import Path
import argparse, hashlib, importlib.util, json, os, struct, subprocess, sys

ROOT=Path(os.environ.get('QDISPLAY_NATIVE_ROOT',Path(__file__).resolve().parents[1]))
SDK=None
BOARD=None
SRC=ROOT/'firmware/src'
OUT=ROOT/'build/firmware'
ARM=None
from elftools.elf.elffile import ELFFile

def run(args):
    p=subprocess.run([str(x) for x in args],capture_output=True,text=True)
    if p.stdout: print(p.stdout,end='')
    if p.stderr: print(p.stderr,end='',file=sys.stderr)
    if p.returncode:
        raise RuntimeError(p.stderr or f'command failed: {args}')

def main():
    global OUT,SRC,SDK,BOARD,ARM
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk-root',type=Path,required=True)
    parser.add_argument('--toolchain-bin',type=Path,required=True)
    parser.add_argument('--qpy-inputs',type=Path,required=True)
    parser.add_argument('--dtools',type=Path,required=True)
    parser.add_argument('--assets-dir',type=Path,default=ROOT/'firmware/assets')
    parser.add_argument('--safe-decoder',action='store_true',help='use conservative bytewise LZ4 loads')
    parser.add_argument('--output-dir',type=Path,help='separate project-relative output directory for a candidate')
    parser.add_argument('--source-dir',type=Path,help='project-relative source snapshot, leaving other candidates untouched')
    parser.add_argument('--disable-panel-dither',action='store_true',
                        help='experimental SC7705 DITH_EN clear; requires physical verification')
    args=parser.parse_args()
    SDK=args.sdk_root
    BOARD=SDK/'system/platform/Unisoc/boards/EC600UCN_LB'
    ARM=args.toolchain_bin
    if args.source_dir is not None:
        source=ROOT/args.source_dir
        if args.source_dir.is_absolute() or not source.resolve().is_relative_to(ROOT.resolve()):
            raise RuntimeError('source snapshot must stay inside this project')
        SRC=source
    if args.output_dir is not None:
        candidate=ROOT/args.output_dir
        if args.output_dir.is_absolute() or not candidate.resolve().is_relative_to(ROOT.resolve()):
            raise RuntimeError('candidate output must stay inside this project')
        # Keep the ASCII junction spelling for the old GCC, not the resolved path.
        OUT=candidate
    OUT.mkdir(parents=True,exist_ok=True)
    os.environ['PATH']=str(ARM)+os.pathsep+os.environ.get('PATH','')
    if args.disable_panel_dither:
        raise RuntimeError('The curated demo preserves the tested panel initialization; use a separate experiment.')
    import shutil
    for name in ('panel_init.h','waiting_page.h','brightness_osd.h'):
        shutil.copy2(args.assets_dir/name,OUT/name)
    # The SDK core is R01. Reuse its named import stubs, but retain the user's
    # exact R03 core and its APPIMG memory ownership from the shipped image.
    qpy=args.qpy_inputs
    ap=(qpy/'AP_8915DM_cat1_open.sign.img').read_bytes()
    app=(qpy/'APPIMG_EC600UCNLBR03A04M08_OCPU_QPY.img').read_bytes()
    if hashlib.sha256(ap).hexdigest()!='187abb282fd089e6c3fb9d8bb75b837826b1a726e943fe961e5bf052da433ca9':
        raise RuntimeError('unrecognized R03 core')
    import xxhash
    waiting_asset={'source':'matched generated headers in firmware/assets'}
    (OUT/'core_guard.h').write_text(
        '#define R03_CORE_SIZE '+str(len(ap))+'u\n'
        '#define R03_CORE_XXH32 '+hex(xxhash.xxh32_intdigest(ap))+'u\n')
    words=struct.unpack_from('<32I',app)
    if words[0]!=0x41505032 or words[11]!=0x80f00000:
        raise RuntimeError('unexpected R03 APPIMG memory layout')
    ld=(SDK/'system/platform/Unisoc/scripts/linkscript.ld').read_text()
    ld=ld.replace('#include "hal_config.h"',
        '#define CONFIG_CPU_ARM 1\n#define CONFIG_APPIMG_FLASH_ADDRESS 0x60260000\n'
        '#define CONFIG_APPIMG_FLASH_SIZE 0xe0000\n#define CONFIG_RAM_PHY_ADDRESS 0x80000000\n'
        '#define CONFIG_APP_FLASHIMG_RAM_OFFSET 0xf00000\n#define CONFIG_APP_FLASHIMG_RAM_SIZE 0x100000\n')
    (OUT/'linkscript.ld.S').write_text(ld)
    gcc=ARM/'arm-none-eabi-gcc.exe'
    run([gcc,'-E','-P','-x','c',OUT/'linkscript.ld.S','-o',OUT/'linkscript.ld'])
    includes=[OUT,SRC,SRC/'third_party',SDK/'system/os',SDK/'system/hal',SDK/'system/fs',SDK/'peripheral',
              SDK/'system/platform/Unisoc/include',BOARD/'include']
    flags=['-mcpu=cortex-a5','-mthumb','-mfpu=neon-vfpv4','-mfloat-abi=hard',
           '-mno-unaligned-access','-O3','-fno-tree-vectorize','-ffunction-sections',
           '-fdata-sections','-fno-common','-fno-strict-aliasing','-DPLAT_Unisoc',
           '-DBOARD_EC600UCN_LB','-DLZ4_FREESTANDING=1','-DLZ4_memcpy=memcpy',
           '-DLZ4_memmove=memmove','-DLZ4_memset=memset','-include','string.h','-Wall','-Wextra']
    flags += [a for p in includes for a in ['-I',str(p)]]
    objects=[]
    for source in [SRC/'main.c',SRC/'third_party/lz4.c']:
        source_flags=list(flags)
        if source.name=='lz4.c' and not args.safe_decoder:
            # Verified R03 SCTLR.A=0. Only normal-RAM LZ4 accesses use this;
            # main.c keeps the SDK's conservative alignment rules for MMIO.
            source_flags += ['-munaligned-access','-DLZ4_FAST_DEC_LOOP=1']
        obj=OUT/(source.stem+'.o');run([gcc,*source_flags,'-c',source,'-o',obj]);objects.append(obj)
    stub=BOARD/'libraries/core_stub.o'
    elf=OUT/'qdisplay_native.elf'
    run([gcc,*flags,'-nostartfiles','-nostdlib','-Wl,--gc-sections',
         '-Wl,-Map='+str(OUT/'qdisplay_native.map'),'-T',OUT/'linkscript.ld',*objects,stub,
         '-Wl,--start-group','-lc','-lgcc','-lnosys','-Wl,--end-group','-o',elf])
    run([ARM/'arm-none-eabi-size.exe',elf])
    imports=[]
    with stub.open('rb') as f:
        e=ELFFile(f)
        for section in e.iter_sections():
            if section.name.startswith('.text.core_stub.'):
                imports.append((section.name.split('.',3)[-1],section.data()[4:8]))
    with elf.open('rb') as f:
        e=ELFFile(f);core=e.get_section_by_name('.corestub').data()
        required=[(name,key) for name,key in imports if b'\xdf\xf8\x00\xf0'+key in core]
        audit=[]
        for name,key in required:
            hits=[];pos=ap.find(key)
            while pos>=0:
                ptr=struct.unpack_from('<I',ap,pos+4)[0]
                if ptr&1 and 0x60010000<=ptr<0x60260000: hits.append((pos,ptr))
                pos=ap.find(key,pos+1)
            if len(hits)!=1: raise RuntimeError(f'import missing/ambiguous in R03: {name}')
            audit.append({'name':name,'hash':key.hex(),'core_offset':hex(hits[0][0]),'target':hex(hits[0][1])})
    # Generic UNISOC image formatter shipped by Quectel, not Logicrom firmware.
    dtools=args.dtools
    image=OUT/'qdisplay_native.img';run([dtools,'mkappimg',elf,image])
    report={'core':'EC600UCNLBR03A04M08_OCPU_QPY','core_ap_sha256':hashlib.sha256(ap).hexdigest(),
            'app_address':'0x60260000','ram_address':'0x80f00000','imports':audit,
            'image_sha256':hashlib.sha256(image.read_bytes()).hexdigest(),
            'image_bytes':image.stat().st_size,'device_tested':False,
            'panel_dither_control':'SC7705 CDh=00 candidate' if args.disable_panel_dither else 'original R05 init',
            'lz4_fast_loop':not args.safe_decoder,'lz4_unaligned_access':not args.safe_decoder}
    report['pixel_decoder']='bounded RGB565 stores directly into scanout; staged LZ4 while OSD is visible'
    report['source_dir']=str(SRC.relative_to(ROOT)).replace('\\','/')
    report['waiting_page']=waiting_asset
    report['disconnect_timeout_ms']=5000
    report['long_press_ms']=2000
    report['long_press_keys']=['GPIO44 (menu)']
    report['brightness_keys']=['GPIO47 (+)','GPIO46 (-)']
    report['brightness_backlight']='GPIO8 1kHz software PWM; 100% DC; physical verification pending'
    report['query_key']='backend unverified; no guessed GPIO'
    (OUT/'build_manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='imports'},indent=2))

if __name__=='__main__': main()
