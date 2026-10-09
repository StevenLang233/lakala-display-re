using System;
using System.IO;
namespace QDisplay.Core {
    // This file has no Windows dependency; it is shared by future OS transports.
    public interface ITransport : IDisposable { void Write(byte[] bytes); int Read(byte[] bytes,int offset,int count); }
    public static class Hash32 {
        const uint P1=2654435761U,P2=2246822519U,P3=3266489917U,P4=668265263U,P5=374761393U;
        public static uint Rotate(uint x,int n){return (x<<n)|(x>>(32-n));}
        static uint Word(byte[] b,int i){return (uint)(b[i]|b[i+1]<<8|b[i+2]<<16|b[i+3]<<24);}
        static uint Round(uint h,uint x){return Rotate(unchecked(h+x*P2),13)*P1;}
        public static uint Of(byte[] b){return Of(b,0,b.Length);}
        public static uint Of(byte[] b,int offset,int length){ unchecked {
            int i=offset,end=offset+length;uint h;
            if(length>=16){uint a=P1+P2,c=P2,d=0,e=0-P1;int limit=end-16;
                do{a=Round(a,Word(b,i));c=Round(c,Word(b,i+4));d=Round(d,Word(b,i+8));e=Round(e,Word(b,i+12));i+=16;}while(i<=limit);
                h=Rotate(a,1)+Rotate(c,7)+Rotate(d,12)+Rotate(e,18);
            }else h=P5;
            h+=(uint)length;
            while(i+4<=end){h=Rotate(h+Word(b,i)*P3,17)*P4;i+=4;}
            while(i<end)h=Rotate(h+b[i++]*P5,11)*P1;
            h^=h>>15;h*=P2;h^=h>>13;h*=P3;h^=h>>16;return h;
        }}
    }
    public static class Lz4 {
        public static byte[] Encode(byte[] src,int start,int count,bool high=false){
            if(count==0)return new byte[]{0};byte[] dst=new byte[K4os.Compression.LZ4.LZ4Codec.MaximumOutputSize(count)];
            int size=K4os.Compression.LZ4.LZ4Codec.Encode(src,start,count,dst,0,dst.Length,high?K4os.Compression.LZ4.LZ4Level.L03_HC:K4os.Compression.LZ4.LZ4Level.L00_FAST);
            if(size<=0)throw new IOException("LZ4 压缩失败");Array.Resize(ref dst,size);return dst;
        }
    }
    public sealed class Reply {
        public uint Status,Receive,Decode,Draw,Heap,Detail;
    }
    public sealed class FirmwareException : IOException {
        public readonly uint Status,Detail;
        public FirmwareException(uint status,uint detail):base("固件拒绝命令："+status+" / "+detail){Status=status;Detail=detail;}
    }
    public sealed class PreparedFrame {
        public readonly byte[][] Blocks;public readonly int[] Lengths;public readonly ushort[] Codecs;
        public readonly int BlockBytes;public readonly uint PixelHash;public readonly double EncodeMs;public readonly long WireBytes;
        public uint BaseHash;public int SparseRawBytes;public byte[] SparseBlock;
        PreparedFrame(int blockBytes,uint hash,double encodeMs,byte[][] blocks,int[] lengths,ushort[] codecs){
            BlockBytes=blockBytes;PixelHash=hash;EncodeMs=encodeMs;Blocks=blocks;Lengths=lengths;Codecs=codecs;
            foreach(byte[] b in blocks)WireBytes+=b.Length;
        }
        public static PreparedFrame Prepare(byte[] pixels,int blockBytes,bool whole=false,byte[] reference=null,uint baseHash=0){
            if(pixels==null||pixels.Length!=NativeLink.FrameBytes)throw new ArgumentException("Invalid frame dimensions");
            if(blockBytes!=128*1024&&blockBytes!=508*1024)throw new ArgumentException("Unsupported block size");
            var clock=System.Diagnostics.Stopwatch.StartNew();uint pixelHash=Hash32.Of(pixels);int sparseRaw=0;
            byte[] sparse=SparseFrame.Prepare(pixels,reference,pixelHash,out sparseRaw);
            int transportBlock=blockBytes;if(whole&&sparse==null)blockBytes=NativeLink.FrameBytes;
            int count=(pixels.Length+blockBytes-1)/blockBytes;int[] lengths=new int[count];
            byte[][] blocks=new byte[count][];ushort[] codecs=new ushort[count];long wire=0;
            for(int i=0;i<count;i++){int off=i*blockBytes,n=lengths[i]=Math.Min(blockBytes,pixels.Length-off);byte[] encoded=Lz4.Encode(pixels,off,n);
                if(encoded.Length<n){blocks[i]=encoded;codecs[i]=1;}else{blocks[i]=new byte[n];Buffer.BlockCopy(pixels,off,blocks[i],0,n);}wire+=blocks[i].Length;}
            if(sparse==null&&wire>256*1024&&wire<pixels.Length*.85){byte[][] smaller=new byte[count][];ushort[] smallerCodecs=new ushort[count];long size=0;
                for(int i=0;i<count;i++){int off=i*blockBytes,n=lengths[i];byte[] encoded=Lz4.Encode(pixels,off,n,true);
                    if(encoded.Length<n){smaller[i]=encoded;smallerCodecs[i]=1;}else{smaller[i]=new byte[n];Buffer.BlockCopy(pixels,off,smaller[i],0,n);}size+=smaller[i].Length;}
                if(size<wire){blocks=smaller;codecs=smallerCodecs;}}
            if(blockBytes==NativeLink.FrameBytes&&(blocks[0].Length>transportBlock||codecs[0]!=1))return Prepare(pixels,transportBlock);
            double encodeMs=clock.Elapsed.TotalMilliseconds;return new PreparedFrame(blockBytes,pixelHash,encodeMs,blocks,lengths,codecs){BaseHash=baseHash,SparseRawBytes=sparseRaw,SparseBlock=sparse};
        }
        public byte[] Serialize(){using(var stream=new MemoryStream())using(var writer=new BinaryWriter(stream)){
            writer.Write(0x31465051);writer.Write(BlockBytes);writer.Write(Blocks.Length);writer.Write(PixelHash);writer.Write(EncodeMs);
            for(int i=0;i<Blocks.Length;i++){writer.Write(Lengths[i]);writer.Write((int)Codecs[i]);writer.Write(Blocks[i].Length);writer.Write(Blocks[i]);}
            if(SparseBlock!=null){writer.Write(0x31584451);writer.Write(BaseHash);writer.Write(SparseRawBytes);writer.Write(SparseBlock.Length);writer.Write(SparseBlock);}return stream.ToArray();}}
        public static PreparedFrame Parse(byte[] data){using(var stream=new MemoryStream(data,false))using(var reader=new BinaryReader(stream)){
            if(reader.ReadInt32()!=0x31465051)throw new InvalidDataException("帧格式错误");int block=reader.ReadInt32(),count=reader.ReadInt32();uint hash=reader.ReadUInt32();double ms=reader.ReadDouble();
            if((block!=128*1024&&block!=508*1024&&block!=NativeLink.FrameBytes)||count!=(NativeLink.FrameBytes+block-1)/block||Double.IsNaN(ms)||Double.IsInfinity(ms)||ms<0)throw new InvalidDataException("帧参数错误");
            byte[][] blocks=new byte[count][];int[] lengths=new int[count];ushort[] codecs=new ushort[count];int off=0;
            for(int i=0;i<count;i++){int raw=reader.ReadInt32(),codec=reader.ReadInt32(),size=reader.ReadInt32();
                if(raw!=Math.Min(block,NativeLink.FrameBytes-off)||codec<0||codec>1||size<1||size>raw||(codec==0&&size!=raw)||size>stream.Length-stream.Position)throw new InvalidDataException("帧块尺寸错误");
                if(block==NativeLink.FrameBytes&&(codec!=1||size>508*1024))throw new InvalidDataException("整帧压缩块超过设备接收大小");
                blocks[i]=reader.ReadBytes(size);lengths[i]=raw;codecs[i]=(ushort)codec;off+=raw;}
            var result=new PreparedFrame(block,hash,ms,blocks,lengths,codecs);
            if(stream.Position!=stream.Length){if(reader.ReadUInt32()!=0x31584451)throw new InvalidDataException("局部更新格式错误");result.BaseHash=reader.ReadUInt32();result.SparseRawBytes=reader.ReadInt32();int size=reader.ReadInt32();
                if(result.SparseRawBytes<1040||result.SparseRawBytes>508*1024||size<1||size>508*1024||size>stream.Length-stream.Position)throw new InvalidDataException("局部更新尺寸错误");result.SparseBlock=reader.ReadBytes(size);}
            if(stream.Position!=stream.Length)throw new InvalidDataException("帧包含多余数据");return result;
        }}
    }
    public sealed class NativeLink : IDisposable {
        public const int FrameBytes=800*1280*2;
        public double LastFrameMs,LastEncodeMs;public long LastWireBytes;
        readonly ITransport port;uint sequence,committedHash;bool committedValid;public int BlockBytes=128*1024,MaxWindow=4;public bool Audio,WholeFrames,SparseFrames,ScreenPower;bool deferred;
        public void InvalidateFrame(){committedValid=false;}
        public NativeLink(ITransport transport){port=transport;sequence=unchecked((uint)System.Diagnostics.Stopwatch.GetTimestamp());}
        static void U32(byte[] b,int o,uint n){b[o]=(byte)n;b[o+1]=(byte)(n>>8);b[o+2]=(byte)(n>>16);b[o+3]=(byte)(n>>24);}
        static uint Get(byte[] b,int o){return BitConverter.ToUInt32(b,o);}
        byte[] Read(int n){byte[] b=new byte[n];int done=0;while(done<n){int got=port.Read(b,done,n-done);if(got==0)throw new EndOfStreamException("USB 连接已断开");done+=got;}return b;}
        uint Send(byte kind,ushort flags,uint offset,uint raw,byte[] payload){
            if(payload==null)payload=new byte[0];uint seq=++sequence;
            byte[] bytes=new byte[32+payload.Length];U32(bytes,0,0x31434451);bytes[4]=1;bytes[5]=kind;
            bytes[6]=(byte)flags;bytes[7]=(byte)(flags>>8);U32(bytes,8,seq);U32(bytes,12,offset);
            U32(bytes,16,(uint)payload.Length);U32(bytes,20,raw);U32(bytes,24,Hash32.Of(payload));U32(bytes,28,Hash32.Of(bytes,0,28));
            Buffer.BlockCopy(payload,0,bytes,32,payload.Length);port.Write(bytes);
            return seq;
        }
        Reply Receive(uint seq,bool discardStale=false){
            DateTime deadline=DateTime.UtcNow.AddSeconds(8);
            while(true){byte[] header=Read(32);
                while(Get(header,0)!=0x31434451 || Hash32.Of(header,0,28)!=Get(header,28)){
                    if(DateTime.UtcNow>deadline)throw new TimeoutException("USB 回复超时");
                    Buffer.BlockCopy(header,1,header,0,31);header[31]=Read(1)[0];
                }
                if(header[4]!=1 || header[5]!=128 || BitConverter.ToUInt16(header,6)!=0 || Get(header,12)!=0 || Get(header,16)!=24 || Get(header,20)!=24)throw new IOException("USB 回复格式错误");
                byte[] body=Read(24);if(Hash32.Of(body)!=Get(header,24))throw new IOException("USB 回复校验失败");
                Reply r=new Reply{Status=Get(body,0),Receive=Get(body,4),Decode=Get(body,8),Draw=Get(body,12),Heap=Get(body,16),Detail=Get(body,20)};
                if(Get(header,8)!=seq){if(discardStale)continue;throw new IOException("USB 回复序号不匹配");}
                if(r.Status!=0)throw new FirmwareException(r.Status,r.Detail);return r;
            }
        }
        public Reply Command(byte kind,ushort flags,uint offset,uint raw,byte[] payload){return Receive(Send(kind,flags,offset,raw,payload));}
        public Reply Command(byte kind,ushort flags,uint offset,uint raw){return Command(kind,flags,offset,raw,null);}
        public Reply Hello(){return Command(1,0,0,0);}
        public void Connect(){Reply hello=Receive(Send(1,0,0,0,null),true);if(hello.Detail!=128*1024 && hello.Detail!=508*1024)throw new IOException("设备协议不匹配");BlockBytes=(int)hello.Detail;uint features=Command(1,2,0,0).Detail;Audio=(features&4)!=0;WholeFrames=(features&16)!=0;SparseFrames=(features&32)!=0;ScreenPower=(features&64)!=0;deferred=(features&1)!=0;MaxWindow=deferred?(int)((features>>8)&15):4;if(MaxWindow==0)MaxWindow=4;if(MaxWindow<1||MaxWindow>4)throw new IOException("设备接收窗口不匹配");}
        public Reply Frame(byte[] pixels){
            return SendPrepared(PreparedFrame.Prepare(pixels,BlockBytes,WholeFrames));
        }
        public Reply SendPrepared(PreparedFrame frame){
            if(frame.BlockBytes>BlockBytes&&!(WholeFrames&&frame.BlockBytes==FrameBytes&&frame.Blocks[0].Length<=BlockBytes))throw new ArgumentException("Frame exceeds receive buffer");
            var clock=System.Diagnostics.Stopwatch.StartNew();LastSparse=false;
            if(SparseFrames&&committedValid&&committedHash==frame.BaseHash&&frame.SparseBlock!=null){
                committedValid=false;
                try {Reply patch=Command(10,1,frame.BaseHash,(uint)frame.SparseRawBytes,frame.SparseBlock);
                    if(patch.Detail!=frame.PixelHash)throw new IOException("局部更新提交校验失败");committedHash=frame.PixelHash;committedValid=true;LastSparse=true;
                    LastEncodeMs=frame.EncodeMs;LastWireBytes=frame.SparseBlock.Length+32;LastFrameMs=clock.Elapsed.TotalMilliseconds;return patch;
                }catch(FirmwareException ex){if(ex.Status!=4&&ex.Status!=2)throw;}
            }
            committedValid=false;Reply begin=Command(2,0,0,FrameBytes);
            if(frame.BlockBytes==FrameBytes&&begin.Detail==1){byte[] pixels=new byte[FrameBytes];int n=K4os.Compression.LZ4.LZ4Codec.Decode(frame.Blocks[0],0,frame.Blocks[0].Length,pixels,0,pixels.Length);
                if(n!=FrameBytes||Hash32.Of(pixels)!=frame.PixelHash)throw new IOException("整帧压缩数据校验失败");frame=PreparedFrame.Prepare(pixels,BlockBytes);}
            LastEncodeMs=frame.EncodeMs;LastWireBytes=frame.WireBytes+64+frame.Blocks.Length*32;
            var outstanding=new System.Collections.Generic.Queue<System.Tuple<uint,int>>();int offset=0;
            for(int i=0;i<frame.Blocks.Length;i++){int n=frame.Lengths[i];bool skip=deferred&&(i+1)%MaxWindow!=0&&i+1<frame.Blocks.Length;
                if(!deferred&&outstanding.Count>=MaxWindow){var ack=outstanding.Dequeue();if(Receive(ack.Item1).Detail!=ack.Item2)throw new IOException("固件接收偏移不匹配");}
                uint seq=Send(3,(ushort)(frame.Codecs[i]|(skip?256:0)),(uint)offset,(uint)n,frame.Blocks[i]);offset+=n;
                if(deferred){if(!skip&&Receive(seq).Detail!=offset)throw new IOException("固件接收偏移不匹配");}else outstanding.Enqueue(System.Tuple.Create(seq,offset));
            }
            while(outstanding.Count>0){var ack=outstanding.Dequeue();if(Receive(ack.Item1).Detail!=ack.Item2)throw new IOException("固件接收偏移不匹配");}
            Reply result=Command(4,SparseFrames?(ushort)1:(ushort)0,frame.PixelHash,0);if(result.Detail!=FrameBytes)throw new IOException("固件提交长度不匹配");committedHash=frame.PixelHash;committedValid=true;LastFrameMs=clock.Elapsed.TotalMilliseconds;return result;
        }
        public bool LastSparse;
        public void UploadAudio(byte[] mp3){
            if(!Audio)throw new InvalidOperationException("固件尚不支持音频");if(mp3.Length<1 || mp3.Length>4*1024*1024)throw new ArgumentException("音频文件限制 4 MB");
            Command(7,1,0,0);Command(7,2,10,0);Command(7,3,(uint)mp3.Length,Hash32.Of(mp3));
            for(int off=0;off<mp3.Length;off+=16384){int n=Math.Min(16384,mp3.Length-off);byte[] b=new byte[n];Buffer.BlockCopy(mp3,off,b,0,n);Command(8,0,(uint)off,(uint)n,b);}
            Command(7,4,0,0);Reply read=Command(7,6,0,0);
            if(read.Receive!=mp3.Length || read.Detail!=Hash32.Of(mp3))throw new IOException("设备内音频校验失败");
        }
        public void Dispose(){port.Dispose();}
    }
}
