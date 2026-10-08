using System;
using System.IO;
using System.Diagnostics;
namespace QDisplay.Windows {
    public static class SystemLog {
        public static readonly string ServiceData=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData),"QDisplay");
        static readonly object gate=new object();
        public static void Log(string text){try{bool service=Process.GetCurrentProcess().SessionId==0;
            string directory=service?ServiceData:Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"QDisplay");
            lock(gate){Directory.CreateDirectory(directory);string path=Path.Combine(directory,service?"service.log":"ui.log");
                if(File.Exists(path)&&new FileInfo(path).Length>2097152){string old=path+".old";if(File.Exists(old))File.Delete(old);File.Move(path,old);}
                File.AppendAllText(path,DateTime.Now.ToString("s")+" "+text+Environment.NewLine);}}
            catch{}}
    }
}
