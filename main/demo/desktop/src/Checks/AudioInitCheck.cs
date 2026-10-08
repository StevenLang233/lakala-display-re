using System;
using System.IO;
using System.Threading;
using QDisplay.Windows;
// Silent initialization only: no source playback, board command, or PCM send.
public static class AudioInitCheck {
    [MTAThread] public static int Main(string[] args) {
        bool success=false;string error="",format="";int blocks=0;
        using(Loopback loop=new Loopback()) {
            try {
                loop.Trace=text=>File.AppendAllText(args[0]+".trace",DateTime.Now.ToString("o")+" "+text+Environment.NewLine);
                loop.Start(bytes=>Interlocked.Increment(ref blocks));
                Thread.Sleep(1200);format=loop.InputFormat;error=loop.LastError;
                success=error.Length==0&&blocks>=5;
            } catch(Exception ex) {error=ex.ToString();}
        }
        File.WriteAllBytes(args[0],Ipc.Json(new{success=success,error=error,input_format=format,blocks=blocks,sound_started=false}));
        return success?0:1;
    }
}
