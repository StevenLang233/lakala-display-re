using System;
using System.IO;
using System.IO.Ports;
using System.Diagnostics;
using System.Collections.Generic;
using QDisplay.Core;
using QDisplay.Windows;
sealed class BenchTransport : ITransport {
    readonly SerialPort port;
    public BenchTransport(string name){port=new SerialPort(name,115200,Parity.None,8,StopBits.One){ReadTimeout=8000,WriteTimeout=8000,ReadBufferSize=65536,WriteBufferSize=65536,DtrEnable=false,RtsEnable=false};port.Open();port.DiscardInBuffer();}
    public void Write(byte[] b){port.Write(b,0,b.Length);}public int Read(byte[] b,int o,int n){return port.Read(b,o,n);}public void Dispose(){port.Dispose();}
}
class NativeTransportBench {
    static int Main(string[] args){var rows=new List<object>();using(var link=new NativeLink(new BenchTransport("COM5"))){link.Connect();foreach(string scene in new[]{"ui","illustration","wallpaper","actual"})foreach(string path in Directory.GetFiles(args[0],scene+"_*.raw")){
        byte[] pixels=File.ReadAllBytes(path);Reply reply=link.Frame(pixels);uint hash=link.Command(6,0,0,0).Detail;
        if(hash!=Hash32.Of(pixels))throw new IOException("Framebuffer mismatch "+path);
        rows.Add(new{scene=scene,native_ms=link.LastFrameMs,encode_ms=link.LastEncodeMs,wire_bytes=link.LastWireBytes,receive_us=reply.Receive,decode_us=reply.Decode,draw_us=reply.Draw,framebuffer_verified=true});}
        byte[] overlayPixels=File.ReadAllBytes(Directory.GetFiles(args[0],"ui_*.raw")[0]);link.Command(1,11,100,0);Reply bar=link.Command(1,14,0,0);
        link.Frame(overlayPixels);Reply after=link.Command(1,14,0,0);if(bar.Draw!=1||after.Draw!=1||after.Decode!=bar.Decode||link.Command(6,0,0,0).Detail!=Hash32.Of(overlayPixels))throw new IOException("OSD preservation failed");
    }File.WriteAllBytes(args[1],Ipc.Json(new{success=true,frames=rows,overlay_fallback_verified=true,physical_tear_free=(bool?)null}));return 0;}
}
