using System;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Windows.Forms;
using QDisplay.Core;
using QDisplay.Windows;
public static class ScreenPowerCheck {
    [DllImport("user32.dll")]static extern IntPtr SendMessage(IntPtr window,int message,IntPtr first,IntPtr second);
    static void Notification(MainWindow window,int state){IntPtr data=Marshal.AllocHGlobal(24);try{
        Marshal.StructureToPtr(new Guid("2B84C20E-AD23-4DDF-93DB-05FFBD7EFCA5"),data,false);
        Marshal.WriteInt32(data,16,4);Marshal.WriteInt32(data,20,state);SendMessage(window.Handle,0x218,new IntPtr(0x8013),data);
    }finally{Marshal.FreeHGlobal(data);}}
    static Button Button(Control parent,string text){foreach(Control child in parent.Controls){if(child is Button&&child.Text==text)return (Button)child;Button found=Button(child,text);if(found!=null)return found;}return null;}
    [STAThread]public static int Main(string[] args){string directory=args[0],result=Path.Combine(directory,"screen-power-ui-test.txt");int stage=0;DateTime deadline=DateTime.UtcNow.AddSeconds(35);Exception error=null;
        string config=Path.Combine(directory,"screen-power-ui-config.json");File.WriteAllBytes(config,Ipc.Json(new Settings{Volume=0,FollowWindowsScreen=true,ScreenOn=true}));
        Application.EnableVisualStyles();using(MainWindow window=new MainWindow(false,null,config,false))using(Timer timer=new Timer{Interval=250}){
            timer.Tick+=(s,e)=>{try{if(DateTime.UtcNow>deadline)throw new TimeoutException("Screen power integration check timed out");
                Status status=Ipc.Parse<Status>(Ipc.Request(Commands.Status));if(!status.Connected||status.UiSession!=status.Session)return;
                if(stage==0){if(!status.ScreenPowerAvailable)throw new Exception("Firmware capability missing");
                    if((IntPtr)typeof(MainWindow).GetField("powerNotification",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(window)==IntPtr.Zero)throw new Exception("Power notification registration failed");
                    Button(window,"息屏").PerformClick();stage=1;}
                else if(stage==1&&!status.ScreenOn){Button(window,"亮屏").PerformClick();stage=2;}
                else if(stage==2&&status.ScreenOn){Notification(window,0);stage=3;}
                else if(stage==3&&!status.ScreenOn){Notification(window,1);stage=4;}
                else if(stage==4&&status.ScreenOn){window.Close();Application.DoEvents();if(window.IsDisposed||window.Visible)throw new Exception("Tray close failed");Notification(window,0);stage=5;}
                else if(stage==5&&!status.ScreenOn){Notification(window,1);stage=6;}
                else if(stage==6&&status.ScreenOn){File.WriteAllText(result,"PASS: registered Windows power notifications, manual off/on, notification off/on, notification off/on while in tray");timer.Stop();window.ExitApp();}
            }catch(Exception ex){error=ex;File.WriteAllText(result,ex.ToString());timer.Stop();window.ExitApp();}};
            timer.Start();Application.Run(window);
        }return error==null?0:1;
    }
}
