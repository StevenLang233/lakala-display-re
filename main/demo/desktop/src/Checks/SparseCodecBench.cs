using System;
using System.IO;
using QDisplay.Core;
class SparseCodecBench {
    static int Main(string[] args){Directory.CreateDirectory(args[1]);byte[] reference=File.ReadAllBytes(args[0]);
        for(int i=0;i<24;i++){byte[] pixels=(byte[])reference.Clone();int x=(i*31)%480,y=(i*79)%800,width=i%3==0?16:(i%3==1?160:320),height=400;
            for(int row=0;row<height;row++)for(int col=0;col<width;col++){int off=((y+row)*800+x+col)*2;pixels[off]=(byte)(i+col);pixels[off+1]=(byte)(row+i*7);}
            var prepared=PreparedFrame.Prepare(pixels,508*1024,true,reference,Hash32.Of(reference));if(prepared.SparseBlock==null)throw new IOException("Missing sparse patch");
            byte[] serialized=prepared.Serialize();if(!Equals(prepared.PixelHash,PreparedFrame.Parse(serialized).PixelHash))throw new IOException("Roundtrip hash mismatch");
            string path=Path.Combine(args[1],i.ToString("00"));File.WriteAllBytes(path+".prepared",serialized);File.WriteAllBytes(path+".base",reference);File.WriteAllBytes(path+".raw",pixels);
            byte[] invalid=(byte[])serialized.Clone();Array.Resize(ref invalid,invalid.Length-1);bool rejected=false;try{PreparedFrame.Parse(invalid);}catch(Exception){rejected=true;}if(!rejected)throw new IOException("Truncated prepared patch accepted");
        }return 0;}
}
