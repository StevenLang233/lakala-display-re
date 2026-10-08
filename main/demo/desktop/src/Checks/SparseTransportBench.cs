using System;
using System.IO;
using System.IO.Ports;
using System.Collections.Generic;
using QDisplay.Core;
using QDisplay.Windows;
sealed class SparseTransport : ITransport {
    readonly SerialPort port;
    public SparseTransport(){port=new SerialPort("COM5",115200,Parity.None,8,StopBits.One){ReadTimeout=8000,WriteTimeout=8000,DtrEnable=false,RtsEnable=false};port.Open();port.DiscardInBuffer();}
    public void Write(byte[] b){port.Write(b,0,b.Length);}public int Read(byte[] b,int o,int n){return port.Read(b,o,n);}public void Dispose(){port.Dispose();}
}
class SparseTransportBench {
    static byte[] Change(byte[] original,int width,int height,int index){byte[] result=(byte[])original.Clone();int x=32+(index*7)%160,y=64+(index*13)%320;
        for(int row=0;row<height;row++)for(int col=0;col<width;col++){int off=((y+row)*800+x+col)*2;ushort color=(ushort)(0x801f+row*8+col*3+index*31);result[off]=(byte)color;result[off+1]=(byte)(color>>8);}return result;}
    static void Verify(NativeLink link,byte[] pixels){if(link.Command(6,0,0,0).Detail!=Hash32.Of(pixels))throw new IOException("Sparse framebuffer mismatch");}
    static int Main(string[] args){byte[] original=File.ReadAllBytes(args[0]);var rows=new List<object>();using(var link=new NativeLink(new SparseTransport())){
        link.Connect();if(!link.SparseFrames)throw new IOException("Missing sparse feature");
        foreach(int width in new[]{16,160,320}){byte[] previous=original;link.Frame(previous);
            for(int index=0;index<16;index++){byte[] pixels=Change(original,width,width==320?400:width,index);
                var prepared=PreparedFrame.Prepare(pixels,link.BlockBytes,link.WholeFrames,previous,Hash32.Of(previous));
                prepared=PreparedFrame.Parse(prepared.Serialize());Reply r=link.SendPrepared(prepared);Verify(link,pixels);
                if(!link.LastSparse)throw new IOException("Expected sparse frame width="+width);
                rows.Add(new{width=width,native_ms=link.LastFrameMs,encode_ms=link.LastEncodeMs,wire_bytes=link.LastWireBytes,decode_us=r.Decode,draw_us=r.Draw,hash_verified=true});previous=pixels;}
        }
        // Producer frames may be dropped. A stale reference must send a complete image.
        link.Frame(original);byte[] skipped=Change(original,160,240,20),latest=Change(original,160,240,21);
        var stale=PreparedFrame.Prepare(latest,link.BlockBytes,true,skipped,Hash32.Of(skipped));link.SendPrepared(stale);Verify(link,latest);
        if(link.LastSparse)throw new IOException("Stale sparse reference applied");
        // A reset/old client invalidates the device's reference even if the host cache still matches.
        byte[] next=Change(original,160,240,22);var reset=PreparedFrame.Prepare(next,link.BlockBytes,true,latest,Hash32.Of(latest));
        link.Command(2,0,0,NativeLink.FrameBytes);link.SendPrepared(reset);Verify(link,next);
        if(link.LastSparse)throw new IOException("Invalid device reference applied");
        // Invalid tile dimensions and truncated LZ4 must be rejected before changing scanout.
        byte[] malformed=new byte[1040];Buffer.BlockCopy(BitConverter.GetBytes(Hash32.Of(next)),0,malformed,0,4);malformed[4]=1;
        byte[] encoded=Lz4.Encode(malformed,0,malformed.Length);bool rejected=false;
        try{link.Command(10,1,Hash32.Of(next),1040,encoded);}catch(FirmwareException ex){rejected=ex.Status==2;}
        if(!rejected)throw new IOException("Invalid tile accepted");Verify(link,next);
        rejected=false;try{link.Command(10,1,Hash32.Of(next),1040,new byte[]{255});}catch(FirmwareException ex){rejected=ex.Status==5;}
        if(!rejected)throw new IOException("Truncated sparse block accepted");Verify(link,next);
        // Brightness OSD must keep its visible pixels while its underlying picture changes.
        link.Command(1,11,100,0);Reply bar=link.Command(1,14,0,0);byte[] overlay=(byte[])next.Clone();
        for(int y=1072;y<1264;y++)for(int x=128;x<448;x++){int off=(y*800+x)*2;overlay[off]=(byte)(x+y);overlay[off+1]=(byte)(y>>2);}
        link.SendPrepared(PreparedFrame.Prepare(overlay,link.BlockBytes,true,next,Hash32.Of(next)));Verify(link,overlay);Reply after=link.Command(1,14,0,0);
        if(!link.LastSparse||bar.Draw!=1||after.Draw!=1||bar.Decode!=after.Decode)throw new IOException("Sparse OSD preservation failed");
    }
    File.WriteAllBytes(args[1],Ipc.Json(new{success=true,frames=rows,stale_reference_fallback=true,device_reset_fallback=true,invalid_inputs_rejected=true,osd_verified=true,physical_tear_free=(bool?)null}));return 0;}
}
