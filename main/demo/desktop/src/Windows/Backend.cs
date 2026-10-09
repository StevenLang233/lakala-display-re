using System;
using System.IO;
using System.IO.Ports;
using System.IO.Pipes;
using System.Collections.Generic;
using System.Threading;
using System.ServiceProcess;
using System.Diagnostics;
using QDisplay.Core;
namespace QDisplay.Windows {
    sealed class Usb : ITransport {
        readonly SerialPort port;
        public Usb(string name){port=new SerialPort(name,115200,Parity.None,8,StopBits.One){ReadTimeout=8000,WriteTimeout=8000,ReadBufferSize=65536,WriteBufferSize=65536,DtrEnable=false,RtsEnable=false};port.Open();port.DiscardInBuffer();}
        public void Write(byte[] b){port.Write(b,0,b.Length);}public int Read(byte[] b,int o,int n){return port.Read(b,o,n);}public void Dispose(){port.Dispose();}
        public static string Find(){List<string> matches=new List<string>();string[] present=SerialPort.GetPortNames();
            using(Microsoft.Win32.RegistryKey usb=Microsoft.Win32.Registry.LocalMachine.OpenSubKey(@"SYSTEM\CurrentControlSet\Enum\USB\VID_2C7C&PID_0901&MI_20")){
                if(usb==null)return null;foreach(string instance in usb.GetSubKeyNames())using(Microsoft.Win32.RegistryKey parameters=usb.OpenSubKey(instance+@"\Device Parameters")){
                    string name=parameters==null?null:Convert.ToString(parameters.GetValue("PortName"));if(!String.IsNullOrEmpty(name)&&Array.IndexOf(present,name)>=0&&!matches.Contains(name))matches.Add(name);
                }}return matches.Count==1?matches[0]:null;}
    }
    sealed class Job {public int Kind,Session;public byte[] Body,Result=new byte[0];public Exception Error;public ManualResetEvent Done=new ManualResetEvent(false);}
    public sealed class Backend : IDisposable {
        readonly object gate=new object();readonly Queue<Job> jobs=new Queue<Job>();readonly List<NamedPipeServerStream> pipes=new List<NamedPipeServerStream>();
        readonly Status status=new Status{ServiceInstance=Guid.NewGuid().ToString("N")};Settings settings=new Settings();NativeLink link;byte[] pending;PreparedFrame pendingPrepared;DateTime lastFrame=DateTime.MinValue,lastUi=DateTime.MinValue;
        volatile bool stopped;Thread worker;readonly AutoResetEvent wake=new AutoResetEvent(false);int lastSession=-2;long frames;DateTime fpsSince=DateTime.UtcNow;int fpsFrames;
        volatile int lockedSession=-1;DateTime audioStarted=DateTime.MinValue;bool audioObservedPlaying;
        int ActiveSession {get{int session=Ipc.ActiveSession;return session==lockedSession?-1:session;}}
        public void SessionEvent(SessionChangeDescription change){if(change.Reason==SessionChangeReason.SessionLock)lockedSession=change.SessionId;
            else if(change.Reason==SessionChangeReason.SessionUnlock&&lockedSession==change.SessionId)lockedSession=-1;
            wake.Set();Log("Session event "+change.Reason+" session "+change.SessionId);}
        public static readonly string Data=SystemLog.ServiceData;
        public static void Log(string text){SystemLog.Log(text);}
        public void Start(){Directory.CreateDirectory(Data);if((File.GetAttributes(Data)&FileAttributes.ReparsePoint)!=0)throw new IOException("服务数据目录不能是符号链接");
            System.Security.AccessControl.DirectorySecurity acl=new System.Security.AccessControl.DirectorySecurity();acl.SetAccessRuleProtection(true,false);
            foreach(System.Security.Principal.WellKnownSidType sid in new[]{System.Security.Principal.WellKnownSidType.LocalSystemSid,System.Security.Principal.WellKnownSidType.BuiltinAdministratorsSid})
                acl.AddAccessRule(new System.Security.AccessControl.FileSystemAccessRule(new System.Security.Principal.SecurityIdentifier(sid,null),System.Security.AccessControl.FileSystemRights.FullControl,System.Security.AccessControl.InheritanceFlags.ContainerInherit|System.Security.AccessControl.InheritanceFlags.ObjectInherit,System.Security.AccessControl.PropagationFlags.None,System.Security.AccessControl.AccessControlType.Allow));
            acl.AddAccessRule(new System.Security.AccessControl.FileSystemAccessRule(new System.Security.Principal.SecurityIdentifier(System.Security.Principal.WellKnownSidType.AuthenticatedUserSid,null),System.Security.AccessControl.FileSystemRights.ReadAndExecute,System.Security.AccessControl.InheritanceFlags.ContainerInherit|System.Security.AccessControl.InheritanceFlags.ObjectInherit,System.Security.AccessControl.PropagationFlags.None,System.Security.AccessControl.AccessControlType.Allow));
            Directory.SetAccessControl(Data,acl);try{settings=Ipc.Parse<Settings>(File.ReadAllBytes(Path.Combine(Data,"settings.json")));}catch{}
            settings.Mode=RecoveryPolicy.Mode(settings.Mode);settings.AudioMode=RecoveryPolicy.Audio(settings.AudioMode);settings.Volume=RecoveryPolicy.Volume(settings.Volume);
            // Runtime falls back until the active user's GUI claims ownership;
            // never overwrite saved intent with a temporary/offline state.
            status.Mode="hardware";status.AudioMode="off";status.Volume=settings.Volume;
            worker=new Thread(Run){IsBackground=true,Name="QDisplay USB"};worker.Start();for(int i=0;i<4;i++)new Thread(Serve){IsBackground=true,Name="QDisplay IPC"}.Start();Log("Started service; saved volume "+settings.Volume+"%, waiting for active user configuration");}
        void Save(){try{string path=Path.Combine(Data,"settings.json");File.WriteAllBytes(path+".tmp",Ipc.Json(settings));if(File.Exists(path))File.Replace(path+".tmp",path,null);else File.Move(path+".tmp",path);}catch(Exception ex){Log(ex.Message);}}
        byte[] Dispatch(int command,byte[] body,int session){
            if(command==Commands.Status){lock(gate){status.Session=ActiveSession;return Ipc.Json(status);}}
            if(!SessionPolicy.CanControl(ActiveSession,session))throw new InvalidOperationException("当前账户没有控制屏幕的活动桌面");
            if(command==Commands.Frame||command==Commands.PhotoFrame||command==Commands.PreparedDisplay||command==Commands.PreparedPhoto||command==Commands.KeepFrame){
                bool encoded=command==Commands.PreparedDisplay||command==Commands.PreparedPhoto;PreparedFrame prepared=encoded?PreparedFrame.Parse(body):null;
                if(command!=Commands.KeepFrame&&!encoded&&body.Length!=NativeLink.FrameBytes)throw new InvalidDataException("帧尺寸错误");
                lock(gate){bool display=command==Commands.Frame||command==Commands.PreparedDisplay;
                    if(status.UiSession!=session||(command==Commands.KeepFrame?(status.Mode!="display"&&status.Mode!="photo"):status.Mode!=(display?"display":"photo")))throw new InvalidOperationException("当前模式不接收此画面");
                    if(prepared!=null&&prepared.BlockBytes>status.NativeBlockBytes&&!(status.NativeWholeFrames&&prepared.BlockBytes==NativeLink.FrameBytes&&prepared.Blocks[0].Length<=status.NativeBlockBytes))throw new InvalidDataException("帧块超出设备接收大小");
                    if(command!=Commands.KeepFrame){status.FrameRequests++;pending=encoded?null:body;pendingPrepared=prepared;}lastFrame=lastUi=DateTime.UtcNow;
                    wake.Set();return Ipc.Json(status);}}
            Job job=new Job{Kind=command,Body=body,Session=session};lock(gate){if(jobs.Count>=8)throw new InvalidOperationException("设备忙");jobs.Enqueue(job);}wake.Set();
            if(!job.Done.WaitOne(command==Commands.UploadAudio?90000:12000))throw new System.TimeoutException("设备命令超时");job.Done.Close();if(job.Error!=null)throw job.Error;return job.Result;
        }
        void Serve(){while(!stopped){NamedPipeServerStream pipe=null;try{pipe=Ipc.Server();lock(gate)pipes.Add(pipe);pipe.WaitForConnection();int session=Ipc.ClientSession(pipe);
                byte[] h=Ipc.Read(pipe,12);if(BitConverter.ToInt32(h,0)!=0x31504451)throw new InvalidDataException();int command=BitConverter.ToInt32(h,4);byte[] body=Ipc.Read(pipe,BitConverter.ToInt32(h,8));
                int resultCode=0;byte[] result;try{result=Dispatch(command,body,session);}catch(Exception ex){resultCode=1;result=System.Text.Encoding.UTF8.GetBytes(ex.Message);}
                BinaryWriter writer=new BinaryWriter(pipe);writer.Write(resultCode);writer.Write(result.Length);writer.Write(result);writer.Flush();
            }catch(Exception ex){if(!stopped&&!(ex is EndOfStreamException))Log("IPC: "+ex.Message);}finally{if(pipe!=null){lock(gate)pipes.Remove(pipe);pipe.Dispose();}}}}
        void Execute(Job job){if(!SessionPolicy.CanControl(ActiveSession,job.Session))throw new InvalidOperationException("账户已切换或锁定");
            string text=(job.Kind==Commands.UploadAudio||job.Kind==Commands.Pcm)?"":System.Text.Encoding.UTF8.GetString(job.Body);
            switch(job.Kind){
            case Commands.Mode:
                if(text!="display"&&text!="photo"&&text!="hardware")throw new InvalidDataException("未知显示模式");
                lock(gate){settings.Mode=status.Mode=text;status.UiSession=job.Session;pending=null;pendingPrepared=null;lastUi=DateTime.UtcNow;}Save();break;
            case Commands.Exit:
                lock(gate){if(status.UiSession==job.Session){status.Mode="hardware";pending=null;pendingPrepared=null;status.UiSession=-1;}}
                if(status.AudioMode=="windows"&&link!=null){link.Command(7,1,0,0);status.AudioMode="off";}break;
            case Commands.UploadAudio:
                RequireLink();link.UploadAudio(job.Body);status.Volume=settings.Volume=10;status.AudioMode="off";settings.AudioMode="off";status.AudioPlaying=false;break;
            case Commands.PlayAudio:RequireLink();link.Command(7,2,(uint)settings.Volume,0);Reply playback=link.Command(7,5,0,0);status.AudioOutput=(int)playback.Draw;status.AudioHardwareVolume=(int)playback.Decode;status.AudioMode=settings.AudioMode="local";status.AudioPlaying=true;audioStarted=DateTime.UtcNow;audioObservedPlaying=false;status.AudioTrackId++;job.Result=Ipc.Json(status);break;
            case Commands.StopAudio:RequireLink();link.Command(7,1,0,0);status.AudioMode=settings.AudioMode="off";status.AudioPlaying=false;audioStarted=DateTime.MinValue;break;
            case Commands.Volume:
                int volume;if(!Int32.TryParse(text,out volume)||volume<0||volume>100)throw new InvalidDataException("音量范围 0–100");RequireLink();link.Command(7,2,(uint)volume,0);settings.Volume=status.Volume=volume;Save();break;
            case Commands.AudioMode:
                RequireLink();if(text!="windows"&&text!="off")throw new InvalidDataException("未知音频模式");link.Command(7,1,0,0);
                if(text=="windows"){link.Command(7,2,(uint)settings.Volume,0);link.Command(7,7,16000,1);status.PcmBlocks=status.PcmNonzeroSamples=0;}audioStarted=DateTime.MinValue;status.AudioMode=settings.AudioMode=text;lastUi=DateTime.UtcNow;break;
            case Commands.Pcm:
                if(job.Body.Length<2||job.Body.Length>16384||job.Body.Length%2!=0)throw new InvalidDataException("音频块尺寸错误");
                RequireLink();if(status.AudioMode!="windows")throw new InvalidOperationException("电脑音频未启用");link.Command(9,0,0,(uint)job.Body.Length,job.Body);status.PcmBlocks++;for(int i=0;i<job.Body.Length;i+=2)if(job.Body[i]!=0||job.Body[i+1]!=0)status.PcmNonzeroSamples++;lastUi=DateTime.UtcNow;break;
            case Commands.ScreenPower:
                bool on;if(text=="1")on=true;else if(text=="0")on=false;else throw new InvalidDataException("屏幕状态无效");
                RequireLink();if(!link.ScreenPower)throw new InvalidOperationException("请先刷入支持屏幕开关的新版固件");
                Reply power=link.Command(1,18,on?1u:0u,0);if(power.Detail!=0x31534451u)throw new InvalidDataException("屏幕开关协议不匹配");
                settings.ScreenOn=status.ScreenOn=on;pending=null;pendingPrepared=null;if(on)lastFrame=lastUi=DateTime.UtcNow;Save();break;
            case Commands.VerifyFrame:RequireLink();Reply verified=link.Command(6,0,0,0);job.Result=Ipc.Json(new{Hash=verified.Detail,Expected=status.LastFrameHash});break;
            case Commands.AudioState:RequireLink();Reply audio=link.Command(7,8,0,0);job.Result=Ipc.Json(new{Output=audio.Receive,HardwareVolume=audio.Decode,PaType=audio.Draw,Flags=audio.Detail});break;
            case Commands.AudioOutput:RequireLink();int output;if(!Int32.TryParse(text,out output)||output<0||output>2)throw new InvalidDataException("音频输出通道无效");link.Command(7,9,(uint)output,0);status.AudioMode=settings.AudioMode="off";status.AudioPlaying=false;status.AudioOutput=output;break;
            default:throw new InvalidDataException("未知请求");
            }
        }
        void RequireLink(){if(link==null)throw new InvalidOperationException("设备未连接");}
        void Run(){DateTime nextConnect=DateTime.MinValue,nextMetrics=DateTime.MinValue,nextHello=DateTime.MinValue,nextAudio=DateTime.MinValue;using(Dashboard dashboard=new Dashboard()){
            while(!stopped){try{
                int session=ActiveSession;if(session!=lastSession){lock(gate){status.Mode=SessionPolicy.AfterSwitch(status.Mode);status.UiSession=-1;pending=null;pendingPrepared=null;lastFrame=DateTime.MinValue;}
                    if(status.AudioMode!="off"&&link!=null){link.Command(7,1,0,0);status.AudioMode="off";status.AudioPlaying=false;}Log("Active session "+lastSession+" -> "+session);lastSession=session;}
                if(link==null&&DateTime.UtcNow>=nextConnect){nextConnect=DateTime.UtcNow.AddSeconds(2);string port=Usb.Find();if(port!=null){NativeLink attempt=null;try{attempt=new NativeLink(new Usb(port));attempt.Connect();link=attempt;lock(gate){status.NativeBlockBytes=link.BlockBytes;status.NativeWholeFrames=link.WholeFrames;status.NativeSparseFrames=link.SparseFrames;status.ScreenPowerAvailable=link.ScreenPower;status.ConnectionGeneration++;status.Connected=true;status.AudioAvailable=link.Audio;status.Port=port;status.Error="";status.Message="已连接";}if(link.ScreenPower){link.Command(1,18,settings.ScreenOn?1u:0u,0);status.ScreenOn=settings.ScreenOn;}nextHello=DateTime.MinValue;Log("USB connected "+port+" generation "+status.ConnectionGeneration);}catch{if(attempt!=null)attempt.Dispose();throw;}}}
                Job job=null;lock(gate){if(jobs.Count>0)job=jobs.Dequeue();}
                if(job!=null){try{Execute(job);}catch(Exception ex){job.Error=ex;}finally{job.Done.Set();}continue;}
                if(link!=null){byte[] frame=null;PreparedFrame prepared=null;string mode;lock(gate){mode=status.Mode;if(status.ScreenOn&&(mode=="display"||mode=="photo")&&DateTime.UtcNow-lastFrame>TimeSpan.FromSeconds(5)&&DateTime.UtcNow-lastUi>TimeSpan.FromSeconds(5)){
                            status.Mode=mode="hardware";status.UiSession=-1;pending=null;pendingPrepared=null;Log("UI stopped delivering frames; hardware fallback");}
                        if(pending!=null){frame=pending;pending=null;}if(pendingPrepared!=null){prepared=pendingPrepared;pendingPrepared=null;}}
                    if(status.ScreenOn&&mode=="hardware"&&DateTime.UtcNow>=nextMetrics){dashboard.Sample();status.Cpu=dashboard.Cpu;status.Memory=dashboard.Used;status.TotalMemory=dashboard.Total;using(System.Drawing.Bitmap image=dashboard.Draw()){
                        frame=Pictures.Pixels(image);}
                        nextMetrics=DateTime.UtcNow.AddSeconds(1);}
                    if(!status.ScreenOn){frame=null;prepared=null;}bool sent=frame!=null||prepared!=null;
                    if(sent){if(prepared==null)prepared=PreparedFrame.Prepare(frame,link.BlockBytes);Reply completed=link.SendPrepared(prepared);
                        status.NativeFrameMs=link.LastFrameMs;status.EncodeMs=link.LastEncodeMs;status.WireBytes=link.LastWireBytes;status.ReceiveUs=completed.Receive;status.DecodeUs=completed.Decode;status.DrawUs=completed.Draw;status.LastFrameHash=prepared.PixelHash;status.LastSparseFrame=link.LastSparse;
                        frames++;fpsFrames++;status.Frames=frames;nextHello=DateTime.UtcNow.AddSeconds(1);}
                    if(DateTime.UtcNow>=nextHello){link.Hello();Reply panel=link.Command(1,7,0,0);if((panel.Receive&2)==0){status.LastFrameHash=0;link.InvalidateFrame();}nextHello=DateTime.UtcNow.AddSeconds(1);}
                    if(DateTime.UtcNow>=nextAudio&&link.Audio&&status.AudioMode!="off"){bool playing=link.Command(7,0,0,0).Decode==1;
                        if(status.AudioMode=="local"&&audioStarted!=DateTime.MinValue){if(playing)audioObservedPlaying=true;
                            else if(audioObservedPlaying||DateTime.UtcNow-audioStarted>TimeSpan.FromSeconds(2)){status.AudioCompletedId=status.AudioTrackId;audioStarted=DateTime.MinValue;}}
                        status.AudioPlaying=playing;nextAudio=DateTime.UtcNow.AddMilliseconds(500);}
                    if(DateTime.UtcNow-fpsSince>TimeSpan.FromSeconds(2)){status.Fps=fpsFrames/(DateTime.UtcNow-fpsSince).TotalSeconds;fpsFrames=0;fpsSince=DateTime.UtcNow;}
                    if(sent)continue;
                }
                wake.WaitOne(10);
            }catch(Exception ex){lock(gate){status.Error=ex.Message;status.Message="正在重连设备";status.Connected=false;status.AudioMode="off";status.AudioPlaying=false;status.Mode="hardware";status.UiSession=-1;status.LastFrameHash=0;pending=null;pendingPrepared=null;}audioStarted=DateTime.MinValue;Log("USB: "+ex.Message);if(link!=null){link.Dispose();link=null;}wake.WaitOne(500);}}
        }if(link!=null){try{link.Command(7,1,0,0);}catch{}link.Dispose();}Log("Service stopped");}
        public void Dispose(){stopped=true;wake.Set();lock(gate){foreach(NamedPipeServerStream pipe in pipes.ToArray())pipe.Dispose();}if(worker!=null)worker.Join(12000);}
    }
    public sealed class DeviceService : ServiceBase {
        Backend backend;public DeviceService(){ServiceName="QDisplayDevice";CanHandleSessionChangeEvent=true;CanStop=true;AutoLog=true;}
        protected override void OnStart(string[] args){backend=new Backend();backend.Start();}
        protected override void OnStop(){if(backend!=null)backend.Dispose();}
        protected override void OnShutdown(){OnStop();}
        protected override void OnSessionChange(SessionChangeDescription change){if(backend!=null)backend.SessionEvent(change);}
    }
}
