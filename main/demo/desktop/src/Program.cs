using System;
using System.IO;
using System.Linq;
using System.Diagnostics;
using System.Security.Principal;
using System.ServiceProcess;
using System.Threading;
using System.Windows.Forms;
using QDisplay.Windows;
using QDisplay.Core;
namespace QDisplay {
    static class Program {
        [STAThread]static int Main(string[] args){try{


            if(args.Contains("--watch")){Watch(Int32.Parse(args[1]),Int32.Parse(args[2]));return 0;}
            if(args.Contains("--status")){File.WriteAllBytes(args[1],Ipc.Request(Commands.Status));return 0;}
            if(args.Contains("--command")){int kind=Int32.Parse(args[1]);byte[] result=Ipc.Request(kind,args.Length>2?System.Text.Encoding.UTF8.GetBytes(args[2]):null);if(args.Length>3)File.WriteAllBytes(args[3],result);return 0;}
            if(args.Contains("--upload")){Ipc.Request(Commands.UploadAudio,File.ReadAllBytes(args[1]));return 0;}
            if(args.Contains("--vdd-on")){Displays.Attach();return 0;}if(args.Contains("--vdd-off")){Displays.Detach();return 0;}
            if(args.Contains("--codec")){byte[] b=File.ReadAllBytes(args[1]);File.WriteAllBytes(args[2],Lz4.Encode(b,0,b.Length));File.WriteAllText(args[2]+".hash",Hash32.Of(b).ToString());return 0;}
            if(args.Contains("--self-test")){if(SessionPolicy.CanControl(2,1)||!SessionPolicy.CanControl(2,2)||SessionPolicy.CanControl(-1,-1)||SessionPolicy.AfterSwitch("display")!="hardware"||SessionPolicy.AfterSwitch("photo")!="photo")throw new Exception("Session policy");File.WriteAllText(args[1],"pass");return 0;}
            if(args.Contains("--tray-check")){Application.EnableVisualStyles();using(MainWindow form=new MainWindow(false)){form.Show();Application.DoEvents();form.Close();Application.DoEvents();if(form.IsDisposed||form.Visible)throw new Exception("Close did not retain tray");File.WriteAllText(args[1],"pass");form.ExitApp();}return 0;}
            Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);
            int session=Process.GetCurrentProcess().SessionId;using(Mutex single=new Mutex(false,"Local\\QDisplay.UI.v1")){if(!single.WaitOne(0)){MainWindow.ShowExisting();return 0;}
                try{using(MainWindow window=new MainWindow(args.Contains("--tray"),args.Contains("--display")?"display":null))Application.Run(window);}finally{single.ReleaseMutex();}}
            return 0;
        }catch(Exception ex){SystemLog.Log(ex.ToString());try{File.WriteAllText(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"last-error.txt"),ex.ToString());}catch{}if(args.Length==0)MessageBox.Show(ex.Message,"QDisplay",MessageBoxButtons.OK,MessageBoxIcon.Error);return 1;}}
        static void Watch(int pid,int session){DateTime started;int unwanted=0;try{using(Process p=Process.GetProcessById(pid))started=p.StartTime;}catch{return;}
            while(true){bool alive;try{using(Process p=Process.GetProcessById(pid))alive=!p.HasExited&&p.StartTime==started;}catch{alive=false;}
                bool attached=false;try{attached=Displays.List().Any(e=>e.Virtual&&e.Attached);}catch{}
                if(Ipc.ActiveSession==session&&attached){bool wanted=false;if(alive){try{Status s=Ipc.Parse<Status>(Ipc.Request(Commands.Status));wanted=s.Connected&&s.Mode=="display"&&s.UiSession==session;}catch{}}
                    unwanted=wanted?0:unwanted+1;
                    if(!wanted&&(!alive||unwanted>=3))try{SystemLog.Log("Watchdog: detach; alive="+alive);Displays.Detach();}catch(Exception ex){SystemLog.Log("Watchdog: "+ex.Message);}}
                if(!alive)break;Thread.Sleep(500);
            }
        }
    }
}
