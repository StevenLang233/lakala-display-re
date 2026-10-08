using System;
using System.IO;
using System.Diagnostics;
using QDisplay.Core;
using QDisplay.Windows;
class CodecBench {
 [STAThread]static int Main(string[] args){using(var image=args[0]=="--capture"?Pictures.Capture():Pictures.Photo(args[0])){var clock=Stopwatch.StartNew();double capture=0;if(args[0]=="--capture"){for(int i=0;i<10;i++)using(var frame=Pictures.Capture()){}capture=clock.Elapsed.TotalMilliseconds/10;clock.Restart();}byte[] pixels=null;for(int i=0;i<10;i++)pixels=Pictures.Pixels(image);double conversion=clock.Elapsed.TotalMilliseconds/10;clock.Restart();uint hash=0;for(int i=0;i<30;i++)hash=Hash32.Of(pixels);double hashMs=clock.Elapsed.TotalMilliseconds/30;clock.Restart();long size=0;for(int i=0;i<10;i++)for(int off=0;off<pixels.Length;off+=508*1024)size+=Lz4.Encode(pixels,off,Math.Min(508*1024,pixels.Length-off)).Length;double compression=clock.Elapsed.TotalMilliseconds/10;File.WriteAllBytes(args[1],Ipc.Json(new{capture_ms=capture,convert_ms=conversion,hash_ms=hashMs,encode_ms=compression,compressed_bytes=size/10,frame_hash=hash,frame_bytes=pixels.Length}));return 0;}}
}
