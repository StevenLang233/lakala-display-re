using System;
using System.IO;
using QDisplay.Core;
class PreparedCodecBench {
    static int Main(string[] args){Directory.CreateDirectory(args[1]);foreach(string path in Directory.GetFiles(args[0],"*.raw")){
        byte[] pixels=File.ReadAllBytes(path);PreparedFrame prepared=PreparedFrame.Prepare(pixels,508*1024);byte[] wire=prepared.Serialize();PreparedFrame roundtrip=PreparedFrame.Parse(wire);
        if(roundtrip.PixelHash!=Hash32.Of(pixels)||roundtrip.WireBytes!=prepared.WireBytes)throw new Exception("Prepared frame mismatch");
        File.WriteAllBytes(Path.Combine(args[1],Path.GetFileNameWithoutExtension(path)+".prepared"),wire);
        File.WriteAllBytes(Path.Combine(args[1],Path.GetFileNameWithoutExtension(path)+".whole.prepared"),PreparedFrame.Prepare(pixels,508*1024,true).Serialize());
        byte[] bad=(byte[])wire.Clone();bad[24]=0;bad[25]=0;bad[26]=0;bad[27]=0;bool rejected=false;
        try{PreparedFrame.Parse(bad);}catch(InvalidDataException){rejected=true;}if(!rejected)throw new Exception("Malformed frame accepted");
    }return 0;}
}
