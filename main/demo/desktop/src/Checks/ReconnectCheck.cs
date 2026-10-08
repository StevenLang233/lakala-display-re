using System;
using System.IO;
using System.IO.Ports;
using System.Linq;
using System.Drawing;
using System.Reflection;
using System.Management;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;
using QDisplay.Core;
using QDisplay.Windows;

// Uses the installed application's real constructor, polling, capture, audio
// and preferences. It never calls its mode buttons or restoration methods.
public sealed class ReconnectCheck : MarshalByRefObject {
    MainWindow window;string config;string mode,sound;int session;bool external,resumeMusic;byte[] original;
    string installed=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),"QDisplay","QDisplay.exe");
    readonly BindingFlags fields=BindingFlags.NonPublic|BindingFlags.Instance;
    [STAThread]public static int Main(string[] args){
        AppDomain domain=AppDomain.CreateDomain("Installed reconnect check",null,new AppDomainSetup{
            ApplicationBase=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),"QDisplay")});
        try{return ((ReconnectCheck)domain.CreateInstanceFromAndUnwrap(Assembly.GetExecutingAssembly().Location,typeof(ReconnectCheck).FullName)).Run(args);}
        finally{AppDomain.Unload(domain);}
    }
    object Field(string name){return typeof(MainWindow).GetField(name,fields).GetValue(window);}
    Status State(){return Ipc.Parse<Status>(Ipc.Request(Commands.Status));}
    Status Wait(Func<Status,bool> condition,int seconds,string description){DateTime end=DateTime.UtcNow.AddSeconds(seconds);Status latest=null;
        while(DateTime.UtcNow<end){Application.DoEvents();try{latest=State();if(condition(latest))return latest;}catch{}Thread.Sleep(100);}
        throw new TimeoutException(description+"; status="+System.Text.Encoding.UTF8.GetString(Ipc.Json(latest))+"; GUI="+(external?"external application":((Label)Field("error")).Text));
    }
    bool Ready(Status status){if(external){var target=Displays.List().Single(d=>d.Virtual);if(mode=="display"?(!target.Attached||target.Bounds!=new Rectangle(-800,152,800,1280)||target.Hz!=30):target.Attached)return false;}
        return status.Connected&&status.UiSession==session&&status.Mode==mode&&
        (external||((long)Field("appliedConnection")==status.ConnectionGeneration&&(string)Field("appliedService")==status.ServiceInstance&&
        !(bool)Field("busy")&&!(bool)Field("recoveryPending")))&&status.Volume==0&&
        (sound=="local"&&resumeMusic?status.AudioMode=="local"&&status.AudioPlaying&&status.AudioTrackId>0:
         sound=="windows"?status.AudioMode=="windows"&&(external?status.PcmBlocks>0:Field("loopback")!=null):status.AudioMode=="off");}
    void Pump(int milliseconds){DateTime end=DateTime.UtcNow.AddMilliseconds(milliseconds);while(DateTime.UtcNow<end){Application.DoEvents();Thread.Sleep(20);}}
    void Open(){if(external){System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo(installed,"--tray"){UseShellExecute=false});return;}window=new MainWindow(true,null,config,false);window.Show();}
    void Close(){if(external){foreach(var process in System.Diagnostics.Process.GetProcessesByName("QDisplay")){using(process){if(String.Equals(process.MainModule.FileName,installed,StringComparison.OrdinalIgnoreCase)){process.Kill();process.WaitForExit(5000);}}}Ipc.Request(Commands.Exit);Displays.Detach();return;}
        if(window!=null&&!window.IsDisposed){window.ExitApp();DateTime end=DateTime.UtcNow.AddSeconds(12);while(!window.IsDisposed&&DateTime.UtcNow<end)Pump(50);if(!window.IsDisposed)throw new TimeoutException("GUI exit did not complete");}window=null;}
    void AssertDisplay(){var list=Displays.List();var target=list.Single(d=>d.Virtual);if(mode=="display"){
        if(!target.Attached||target.Bounds!=new Rectangle(-800,152,800,1280)||target.Hz!=30)throw new IOException("Saved display position/refresh not restored");
    }else if(target.Attached)throw new IOException("Virtual display remained attached outside display mode");}
    static string ResetBoard(){string name=null;using(ManagementObjectSearcher search=new ManagementObjectSearcher("SELECT Name,PNPDeviceID FROM Win32_PnPEntity WHERE PNPDeviceID LIKE 'USB%VID_2C7C%PID_0901%MI_02%'")){
        foreach(ManagementObject item in search.Get()){string text=Convert.ToString(item["Name"]);int start=text.LastIndexOf("(COM",StringComparison.Ordinal);if(start<0)continue;if(name!=null)throw new IOException("More than one matching board AT port");name=text.Substring(start+1).TrimEnd(')');}}
        if(name==null)throw new IOException("Board AT interface not found");
        using(SerialPort port=new SerialPort(name,115200){ReadTimeout=2000,WriteTimeout=2000,DtrEnable=false,RtsEnable=false}){
            port.Open();port.DiscardInBuffer();port.Write("AT\r");Thread.Sleep(150);string ready=port.ReadExisting();if(!ready.Contains("OK"))throw new IOException("AT interface did not respond: "+ready);
            port.Write("AT+CFUN=1,1\r");Thread.Sleep(150);string reply="";try{reply=port.ReadExisting();}catch(IOException){reply="USB disconnected after reset";}catch(InvalidOperationException){reply="USB disconnected after reset";}return name+": "+ready+"; reset response: "+reply;
        }
    }
    public int Run(string[] args){string report=Path.GetFullPath(args[0]);config=Path.Combine(Path.GetDirectoryName(report),Path.GetFileNameWithoutExtension(report)+".settings.json");mode=args[1];sound=args[2]=="paused"?"local":args[2];resumeMusic=args[2]=="local";external=args.Length>5&&args[5]=="external";session=System.Diagnostics.Process.GetCurrentProcess().SessionId;
        bool success=false,disconnected=false;string error="",reset="";Status initial=null,after=null,reopened=null,stable=null;var primary=Displays.List().Where(d=>d.Attached&&!d.Virtual).ToArray();
        try{
            Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);
            if(external){config=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"QDisplay","ui.json");original=File.ReadAllBytes(config);File.WriteAllBytes(report+".original-ui.json",original);Close();}
            Ipc.Request(Commands.StopAudio);Ipc.Request(Commands.Volume,System.Text.Encoding.ASCII.GetBytes("0"));
            Settings settings=new Settings{Mode=mode,AudioMode=sound,Volume=0,PhotoPath=args[3],PhotoIsFolder=false,MusicPath=args[4],MusicIsFolder=false,
                MusicRecursive=true,ResumeMusic=resumeMusic,RepeatMusic=true,Fps=60,PhotoSeconds=5,RefreshHz=30,DisplayPositionSaved=true,DisplayX=-800,DisplayY=152,PreferencesVersion=1};
            File.WriteAllBytes(config,Ipc.Json(settings));long requests=State().FrameRequests;Open();initial=Wait(Ready,95,"Startup did not restore selected settings");
            if(mode!="hardware")Wait(s=>Ready(s)&&s.FrameRequests>requests&&s.LastFrameHash!=0,15,"Startup did not send frame");AssertDisplay();
            long generation=initial.ConnectionGeneration,track=initial.AudioTrackId;requests=State().FrameRequests;
            Task<string> resetting=Task.Run((Func<string>)ResetBoard);
            DateTime deadline=DateTime.UtcNow.AddSeconds(15);while(!resetting.IsCompleted&&DateTime.UtcNow<deadline)Pump(50);if(!resetting.IsCompleted)throw new TimeoutException("Reset command timed out");reset=resetting.Result;
            after=Wait(s=>{if(!s.Connected)disconnected=true;return Ready(s)&&s.ConnectionGeneration>generation&&(!resumeMusic||s.AudioTrackId>track);},95,"Hardware reboot did not restore automatically");
            if(mode!="hardware")Wait(s=>Ready(s)&&s.FrameRequests>requests&&s.LastFrameHash!=0,15,"Reconnected capture did not resume");AssertDisplay();
            if(mode=="photo"){uint expected;using(Bitmap image=Pictures.Photo(args[3]))expected=Hash32.Of(Pictures.Pixels(image));
                Wait(s=>Ready(s)&&s.LastFrameHash==expected,15,"Photo content not restored");string verify=System.Text.Encoding.UTF8.GetString(Ipc.Request(Commands.VerifyFrame));
                var verification=Ipc.Parse<System.Collections.Generic.Dictionary<string,uint>>(System.Text.Encoding.UTF8.GetBytes(verify));
                if(verification["Hash"]!=expected)throw new IOException("Board framebuffer does not match saved picture");}
            string applied=after.ServiceInstance;Pump(3500);stable=State();if(!Ready(stable)||stable.AudioTrackId!=after.AudioTrackId||stable.ServiceInstance!=applied)throw new IOException("Stable connection repeatedly restarted");
            Close();requests=State().FrameRequests;Open();reopened=Wait(Ready,95,"Software restart did not restore saved settings");if(mode!="hardware")Wait(s=>Ready(s)&&s.FrameRequests>requests,15,"Reopened GUI did not send saved content");AssertDisplay();
            byte[] savedBytes=File.ReadAllBytes(config);File.WriteAllBytes(report+".final-settings.json",savedBytes);Settings persisted=Ipc.Parse<Settings>(savedBytes);if(persisted.Mode!=mode||persisted.AudioMode!=sound||persisted.Volume!=0||persisted.PhotoPath!=args[3]||persisted.MusicPath!=args[4]||!persisted.MusicRecursive||persisted.Fps!=60||persisted.RefreshHz!=30||!persisted.RepeatMusic||persisted.ResumeMusic!=resumeMusic)throw new IOException("Preferences were overwritten during reconnect");
            success=true;
        }catch(Exception ex){error=ex.ToString();}
        finally{try{Close();}catch(Exception ex){success=false;error+="; cleanup: "+ex;}try{Ipc.Request(Commands.StopAudio);}catch{}try{Displays.Detach();}catch{}if(external&&original!=null)File.WriteAllBytes(config,original);}
        var final=Displays.List();bool primaryUnchanged=primary.All(p=>final.Any(d=>d.Name==p.Name&&d.Bounds==p.Bounds&&d.Hz==p.Hz&&d.Primary==p.Primary));if(!primaryUnchanged){success=false;error+="; primary display changed";}
        File.WriteAllBytes(report,Ipc.Json(new{success=success,mode=mode,audio_mode=sound,volume_percent=0,reset=reset,disconnected_observed=disconnected,
            startup=initial,after_board_reboot=after,stable_connection=stable,after_software_restart=reopened,primary_displays_unchanged=primaryUnchanged,
            physical_visual_or_hearing_verified=false,external_gui_process=external,resume_music=resumeMusic,gui_assembly=typeof(MainWindow).Assembly.Location,settings=config,error=error}));return success?0:1;
    }
}
