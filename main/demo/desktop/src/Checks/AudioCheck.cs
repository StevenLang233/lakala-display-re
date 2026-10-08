using System;
using System.IO;
using System.Threading;
using System.Windows.Media;
using System.Windows.Threading;
using QDisplay.Windows;
public static class AudioCheck {
    [STAThread]public static int Main(string[] args){int blocks=0,nonzero=0,peak=0;object gate=new object();bool opened=false;string mediaError="",input="",captureError="";
        bool playbackOnly=args.Length>2&&args[2]=="--play-only";
        try{using(Loopback loop=new Loopback()){loop.Trace=stage=>File.AppendAllText(args[1]+".trace",DateTime.Now.ToString("o")+" "+stage+Environment.NewLine);if(!playbackOnly)loop.Start(bytes=>{lock(gate){blocks++;for(int i=0;i<bytes.Length;i+=2){short v=BitConverter.ToInt16(bytes,i);if(v!=0)nonzero++;peak=Math.Max(peak,Math.Abs((int)v));}}});
            MediaPlayer player=new MediaPlayer();player.MediaOpened+=(s,e)=>opened=true;player.MediaFailed+=(s,e)=>mediaError=e.ErrorException.ToString();player.Volume=0.1;player.Open(new Uri(args[0]));player.Play();
            DispatcherTimer timer=new DispatcherTimer{Interval=TimeSpan.FromSeconds(5)};timer.Tick+=(s,e)=>{timer.Stop();player.Stop();player.Close();Dispatcher.CurrentDispatcher.BeginInvokeShutdown(DispatcherPriority.Background);};timer.Start();Dispatcher.Run();
            input=loop.InputFormat;captureError=loop.LastError;}
        bool success=playbackOnly?opened&&mediaError.Length==0:blocks>=10&&nonzero>100;
        File.WriteAllBytes(args[1],Ipc.Json(new{success=success,playback_only=playbackOnly,blocks=blocks,nonzero_samples=nonzero,peak=peak,file=args[0],player_volume_percent=10,board_playback=false,media_opened=opened,media_error=mediaError,input_format=input,capture_error=captureError}));return success?0:1;
        }catch(Exception ex){File.WriteAllText(args[1],ex.ToString());return 1;}
    }
}
