using System;
using System.IO;
using System.IO.Ports;
using System.Collections.Generic;
using System.Threading;
using System.Diagnostics;
using QDisplay.Core;
using QDisplay.Windows;
public static class NativeAudioCheck {
    sealed class Usb : ITransport {
        readonly SerialPort port;
        public Usb(string name){port=new SerialPort(name,115200){ReadTimeout=8000,WriteTimeout=8000,DtrEnable=false,RtsEnable=false};port.Open();port.DiscardInBuffer();}
        public void Write(byte[] data){port.Write(data,0,data.Length);}public int Read(byte[] data,int offset,int count){return port.Read(data,offset,count);}public void Dispose(){port.Dispose();}
    }
    [STAThread]public static int Main(string[] args){List<object> tracks=new List<object>();try{using(NativeLink link=new NativeLink(new Usb(args[0]))){link.Connect();try{
            for(int index=0;index<2;index++){byte[] data=File.ReadAllBytes(args[1]);link.UploadAudio(data);link.Command(7,2,10,0);var start=link.Command(7,5,0,0);Stopwatch clock=Stopwatch.StartNew();bool playing=false,ended=false;
                while(clock.Elapsed.TotalSeconds<35){var state=link.Command(7,0,0,0);if(state.Decode==1)playing=true;else if(playing){ended=true;break;}link.Hello();Thread.Sleep(250);}
                tracks.Add(new{index=index+1,bytes=data.Length,hash=Hash32.Of(data),speaker_route=start.Draw,hardware_volume_step=start.Decode,requested_volume_percent=10,observed_playing=playing,completed=ended,elapsed_seconds=clock.Elapsed.TotalSeconds});
                if(!playing||!ended)throw new Exception("未观察到完整播放结束，已停止测试");
            }
        }finally{link.Command(7,1,0,0);}}
        File.WriteAllBytes(args[2],Ipc.Json(new{success=true,tracks=tracks,physical_sound_confirmed=false,service_integration=false}));return 0;
        }catch(Exception ex){File.WriteAllBytes(args[2],Ipc.Json(new{success=false,error=ex.Message,tracks=tracks}));return 1;}
    }
}
