using System;
using System.IO;
using System.IO.Pipes;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Windows.Media;
using System.Windows.Threading;
using QDisplay.Windows;

// Diagnostic only: uses the installed service and its normal PCM commands.
public static class AudioBridgeCheck {
    [DllImport("kernel32.dll",SetLastError=true)]static extern bool GetNamedPipeServerProcessId(IntPtr pipe,out uint pid);
    [DllImport("advapi32.dll",CharSet=CharSet.Unicode)]static extern IntPtr OpenSCManager(string machine,string database,uint access);
    [DllImport("advapi32.dll",CharSet=CharSet.Unicode)]static extern IntPtr OpenService(IntPtr manager,string name,uint access);
    [DllImport("advapi32.dll")]static extern bool QueryServiceStatusEx(IntPtr service,int level,out ServiceState status,int size,out int needed);
    [DllImport("advapi32.dll")]static extern bool CloseServiceHandle(IntPtr handle);
    [StructLayout(LayoutKind.Sequential)]struct ServiceState {public uint Type,State,Controls,Error,SpecificError,Checkpoint,WaitHint,Pid,Flags;}
    static byte[] Request(int command,byte[] body=null){
        using(NamedPipeClientStream pipe=new NamedPipeClientStream(".",Ipc.Name,PipeDirection.InOut,PipeOptions.Asynchronous)){
            pipe.Connect(1500);uint pid;
            if(!GetNamedPipeServerProcessId(pipe.SafePipeHandle.DangerousGetHandle(),out pid))throw new IOException("Cannot verify pipe owner");
            IntPtr manager=OpenSCManager(null,null,1),service=IntPtr.Zero;
            try{if(manager==IntPtr.Zero)throw new IOException("Cannot query SCM");service=OpenService(manager,"QDisplayDevice",4);ServiceState state;int needed;
                if(service==IntPtr.Zero||!QueryServiceStatusEx(service,0,out state,Marshal.SizeOf(typeof(ServiceState)),out needed)||state.State!=4||state.Pid!=pid)throw new IOException("Unexpected pipe owner");
            }finally{if(service!=IntPtr.Zero)CloseServiceHandle(service);if(manager!=IntPtr.Zero)CloseServiceHandle(manager);}
            if(body==null)body=new byte[0];BinaryWriter writer=new BinaryWriter(pipe);writer.Write(0x31504451);writer.Write(command);writer.Write(body.Length);writer.Write(body);writer.Flush();
            byte[] header=Ipc.Read(pipe,8);int status=BitConverter.ToInt32(header,0),length=BitConverter.ToInt32(header,4);byte[] result=Ipc.Read(pipe,length);
            if(status!=0)throw new IOException(Encoding.UTF8.GetString(result));return result;
        }
    }
    [MTAThread]public static int Main(string[] args){
        int blocks=0,nonzero=0,peak=0;bool opened=false;string mediaError="",captureError="",input="",before="",after="",device="";Exception failure=null;
        try{
            before=Encoding.UTF8.GetString(Request(1));Request(6);Request(7,Encoding.ASCII.GetBytes("10"));Request(19,Encoding.ASCII.GetBytes(args.Length>2?args[2]:"2"));
            using(Loopback loop=new Loopback()){
                loop.Trace=stage=>File.AppendAllText(args[1]+".trace",DateTime.Now.ToString("o")+" "+stage+Environment.NewLine);
                loop.Start(bytes=>{
                    Request(9,bytes);Interlocked.Increment(ref blocks);
                    for(int i=0;i<bytes.Length;i+=2){short sample=BitConverter.ToInt16(bytes,i);if(sample!=0)Interlocked.Increment(ref nonzero);peak=Math.Max(peak,Math.Abs((int)sample));}
                },()=>Request(8,Encoding.ASCII.GetBytes("windows")));
                // Match the real GUI: Start runs on a worker, while the media
                // STA keeps pumping messages. Blocking the caller's STA here
                // caused the diagnostic-only WASAPI Initialize timeout.
                Thread playback=new Thread(()=>{
                    MediaPlayer player=null;
                    try{
                        player=new MediaPlayer();player.Volume=0.1;
                        player.MediaOpened+=(s,e)=>opened=true;player.MediaFailed+=(s,e)=>mediaError=e.ErrorException.ToString();
                        player.Open(new Uri(args[0]));player.Play();
                        DispatcherTimer timer=new DispatcherTimer{Interval=TimeSpan.FromSeconds(8)};
                        timer.Tick+=(s,e)=>{timer.Stop();Dispatcher.CurrentDispatcher.BeginInvokeShutdown(DispatcherPriority.Background);};
                        timer.Start();Dispatcher.Run();
                    }catch(Exception ex){mediaError=ex.ToString();}
                    finally{if(player!=null){player.Stop();player.Close();}}
                }){IsBackground=true};
                playback.SetApartmentState(ApartmentState.STA);playback.Start();
                if(!playback.Join(12000))throw new TimeoutException("Media playback diagnostic timed out");
                input=loop.InputFormat;captureError=loop.LastError;after=Encoding.UTF8.GetString(Request(1));device=Encoding.UTF8.GetString(Request(18));
            }
        }catch(Exception ex){failure=ex;}
        finally{try{Request(6);}catch(Exception ex){if(failure==null)failure=ex;}}
        bool success=failure==null&&blocks>=30&&nonzero>100&&mediaError.Length==0&&captureError.Length==0;
        File.WriteAllBytes(args[1],Ipc.Json(new{success=success,blocks=blocks,nonzero_samples=nonzero,peak=peak,board_volume_percent=10,player_volume_percent=10,physical_sound_confirmed=false,input_format=input,media_opened=opened,media_error=mediaError,capture_error=captureError,error=failure==null?"":failure.ToString(),before=before,after=after,device_audio_state=device}));
        return success?0:1;
    }
}
