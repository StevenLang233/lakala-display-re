using System;
using System.IO;
using System.Reflection;
using System.Runtime.Serialization;
using System.Threading;
using System.Windows.Forms;
using QDisplay.Core;
using QDisplay.Windows;

// Diagnostic only: exercise the real GUI sender with rapid quiet slider
// values, without starting another GUI, capture worker, watchdog or playback.
public sealed class VolumeSenderCheck : MarshalByRefObject {
    [STAThread] public static int Main(string[] args) {
        AppDomain domain=AppDomain.CreateDomain("Installed volume sender",null,
            new AppDomainSetup{ApplicationBase=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),"QDisplay")});
        try {
            VolumeSenderCheck check=(VolumeSenderCheck)domain.CreateInstanceFromAndUnwrap(
                Assembly.GetExecutingAssembly().Location,typeof(VolumeSenderCheck).FullName);
            return check.Run(Path.GetFullPath(args[0]));
        }finally{AppDomain.Unload(domain);}
    }
    public int Run(string report) {
        bool success=false;string error="";int updates=0;
        try {
            Ipc.Request(Commands.StopAudio);
            Ipc.Request(Commands.Volume,System.Text.Encoding.ASCII.GetBytes("0"));
            MainWindow window=(MainWindow)FormatterServices.GetUninitializedObject(typeof(MainWindow));
            BindingFlags flags=BindingFlags.Instance|BindingFlags.NonPublic;
            FieldInfo pending=typeof(MainWindow).GetField("pendingVolume",flags);
            FieldInfo sending=typeof(MainWindow).GetField("volumeSending",flags);
            MethodInfo set=typeof(MainWindow).GetMethod("SetVolume",flags);
            using(TrackBar slider=new TrackBar{Minimum=0,Maximum=100}) {
                typeof(MainWindow).GetField("volume",flags).SetValue(window,slider);
                typeof(MainWindow).GetField("saved",flags).SetValue(window,new Settings());
                typeof(MainWindow).GetField("config",flags).SetValue(window,Path.Combine(Path.GetDirectoryName(report),"volume_sender_settings.json"));
                typeof(MainWindow).GetField("deviceConnected",flags).SetValue(window,true);
                typeof(MainWindow).GetField("captureEnabled",flags).SetValue(window,true);
                pending.SetValue(window,-1);
                for(int i=0;i<500;i++){slider.Value=i%11;set.Invoke(window,null);updates++;}
                slider.Value=10;set.Invoke(window,null);updates++;
                DateTime deadline=DateTime.UtcNow.AddSeconds(10);
                while((int)sending.GetValue(window)!=0||(int)pending.GetValue(window)>=0){
                    if(DateTime.UtcNow>deadline)throw new TimeoutException("Volume sender did not drain");Thread.Sleep(10);
                }
                Status status=Ipc.Parse<Status>(Ipc.Request(Commands.Status));
                if(!status.Connected||status.Volume!=10||status.AudioMode!="off")throw new IOException("Latest volume did not arrive");
                if(!(bool)typeof(MainWindow).GetField("captureEnabled",flags).GetValue(window)||
                   (bool)typeof(MainWindow).GetField("busy",flags).GetValue(window))throw new IOException("Volume sender changed capture/busy state");
            }
            success=true;
        }catch(Exception ex){error=ex.ToString();}
        File.WriteAllBytes(report,Ipc.Json(new{success=success,rapid_ui_updates=updates,final_volume_percent=10,playback_started=false,gui_assembly=typeof(MainWindow).Assembly.Location,error=error}));
        return success?0:1;
    }
}
