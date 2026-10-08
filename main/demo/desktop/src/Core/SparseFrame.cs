using System;
using System.IO;
namespace QDisplay.Core {
    // Absolute RGB565 tiles, compared against an acknowledged device frame.
    // The full prepared image remains available if that reference is stale.
    static class SparseFrame {
        public static unsafe byte[] Prepare(byte[] pixels,byte[] reference,uint targetHash,out int rawBytes){
            rawBytes=0;if(reference==null||reference.Length!=NativeLink.FrameBytes)return null;
            using(var output=new MemoryStream(508*1024))using(var writer=new BinaryWriter(output)){
                writer.Write(targetHash);writer.Write(0);int count=0;
                fixed(byte* p=pixels,b=reference){
                    for(int y=0;y<1280;y+=16)for(int x=0;x<800;x+=32){
                        bool changed=false;for(int row=0;row<16&&!changed;row++){
                            uint* a=(uint*)(p+((y+row)*800+x)*2),c=(uint*)(b+((y+row)*800+x)*2);
                            for(int word=0;word<16;word++)if(a[word]!=c[word]){changed=true;break;}
                        }
                        if(!changed)continue;
                        if(output.Length+1032>508*1024)return null;
                        writer.Write((ushort)x);writer.Write((ushort)y);writer.Write((ushort)32);writer.Write((ushort)16);
                        for(int row=0;row<16;row++)writer.Write(pixels,((y+row)*800+x)*2,64);
                        count++;
                    }
                }
                if(count==0)return null;output.Position=4;writer.Write(count);
                byte[] raw=output.ToArray(),encoded=Lz4.Encode(raw,0,raw.Length);
                if(encoded.Length>508*1024)return null;rawBytes=raw.Length;return encoded;
            }
        }
    }
}
