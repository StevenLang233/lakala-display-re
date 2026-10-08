"""Offline QDC1 test vectors. Does not open a device or change its state."""
from pathlib import Path
import struct, json
import xxhash

OUT=Path(__file__).resolve().parents[1]/'evidence/protocol'
OUT.mkdir(parents=True,exist_ok=True)
def hash32(data): return xxhash.xxh32_intdigest(data,seed=0)
def packet(kind,seq,flags=0,offset=0,raw=0,payload=b''):
    header=struct.pack('<IBBHIIIII',0x31434451,1,kind,flags,seq,offset,len(payload),raw,hash32(payload))
    assert len(header)==28
    return header+struct.pack('<I',hash32(header))+payload
hello=packet(1,1)
reply=packet(128,1,raw=24,payload=struct.pack('<6I',0,0,0,0,0,508*1024))
(OUT/'hello.bin').write_bytes(hello)
(OUT/'hello_ack_example.bin').write_bytes(reply)
pixels=bytes(2048000); full_hash=hash32(pixels)
vectors={'encoding':'all integer fields little-endian; XXH32 seed=0',
    'hashes':{'empty':hex(hash32(b'')),'ascii_abc':hex(hash32(b'abc')),
        'black_frame_800x1280_bgr565':hex(full_hash)},
    'hello_seq_1_hex':hello.hex(' '),'example_ack_seq_1_hex':reply.hex(' '),
    'ack_note':'example only: timings and free_heap are zero, detail is block capacity',
    'black_frame_stop_and_wait_headers':[]}
vectors['black_frame_stop_and_wait_headers'].append({'type':'BEGIN','seq':2,'header_hex':packet(2,2,raw=len(pixels)).hex(' ')})
offset=0;seq=3
while offset<len(pixels):
    payload=pixels[offset:offset+508*1024]
    data=packet(3,seq,offset=offset,raw=len(payload),payload=payload)
    vectors['black_frame_stop_and_wait_headers'].append({'type':'DATA','seq':seq,'offset':offset,'payload_bytes':len(payload),
        'payload':'all zero bytes','header_hex':data[:32].hex(' ')})
    offset+=len(payload);seq+=1
vectors['black_frame_stop_and_wait_headers'].append({'type':'COMMIT','seq':seq,'header_hex':packet(4,seq,flags=1,offset=full_hash).hex(' ')})
(OUT/'vectors.json').write_text(json.dumps(vectors,indent=2)+'\n',encoding='utf-8')
print('QDC1 vectors generated without device IO')
