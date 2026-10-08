using System;
using System.IO;
using System.IO.Pipes;
using System.Diagnostics;
using System.Security.AccessControl;
using System.Security.Principal;
using System.Runtime.InteropServices;
using System.Threading;
using System.Web.Script.Serialization;
using QDisplay.Core;
namespace QDisplay.Windows {
    public static class Ipc {
        public const string Name="QDisplay.Native.v1";
        [DllImport("kernel32.dll",SetLastError=true)]static extern bool GetNamedPipeClientProcessId(IntPtr pipe,out uint pid);
        [DllImport("kernel32.dll",SetLastError=true)]static extern bool GetNamedPipeServerProcessId(IntPtr pipe,out uint pid);
        [DllImport("kernel32.dll",SetLastError=true)]static extern bool ProcessIdToSessionId(uint pid,out uint session);
        [DllImport("advapi32.dll",CharSet=CharSet.Unicode,SetLastError=true)]static extern IntPtr OpenSCManager(string machine,string database,uint access);
        [DllImport("advapi32.dll",CharSet=CharSet.Unicode,SetLastError=true)]static extern IntPtr OpenService(IntPtr manager,string name,uint access);
        [DllImport("advapi32.dll",SetLastError=true)]static extern bool QueryServiceStatusEx(IntPtr service,int level,out ServiceStatus status,int size,out int needed);
        [DllImport("advapi32.dll")]static extern bool CloseServiceHandle(IntPtr handle);
        [StructLayout(LayoutKind.Sequential)]struct ServiceStatus {public uint Type,State,Controls,Error,SpecificError,Checkpoint,WaitHint,Pid,Flags;}
        [DllImport("kernel32.dll")]public static extern uint WTSGetActiveConsoleSessionId();
        public static int ActiveSession {get{return unchecked((int)WTSGetActiveConsoleSessionId());}}
        public static byte[] Json(object o){return System.Text.Encoding.UTF8.GetBytes(new JavaScriptSerializer().Serialize(o));}
        public static T Parse<T>(byte[] b){return new JavaScriptSerializer{MaxJsonLength=Commands.MaximumBody}.Deserialize<T>(System.Text.Encoding.UTF8.GetString(b));}
        static void VerifyServer(uint pid){
            // SCM query rights are available to ordinary interactive users. Opening a
            // LocalSystem process is not, and is unnecessary to authenticate this pipe.
            IntPtr manager=OpenSCManager(null,null,1),service=IntPtr.Zero;
            try{if(manager==IntPtr.Zero)throw new IOException("无法查询后台服务");service=OpenService(manager,"QDisplayDevice",4);
                ServiceStatus status;int needed;
                if(service==IntPtr.Zero||!QueryServiceStatusEx(service,0,out status,Marshal.SizeOf(typeof(ServiceStatus)),out needed))throw new IOException("后台服务尚未安装或无法查询");
                if(status.State!=4||status.Type!=16||status.Pid!=pid)throw new IOException("后台服务身份不匹配");
                string configured,account;using(Microsoft.Win32.RegistryKey root=Microsoft.Win32.RegistryKey.OpenBaseKey(Microsoft.Win32.RegistryHive.LocalMachine,Microsoft.Win32.RegistryView.Registry64))
                    using(Microsoft.Win32.RegistryKey key=root.OpenSubKey(@"SYSTEM\CurrentControlSet\Services\QDisplayDevice")){configured=key==null?"":Convert.ToString(key.GetValue("ImagePath"));account=key==null?"":Convert.ToString(key.GetValue("ObjectName"));}
                // A non-interactive LocalSystem service is isolated in Session 0.
                // ProcessIdToSessionId itself needs process access on this machine.
                if(!String.Equals(account,"LocalSystem",StringComparison.OrdinalIgnoreCase))throw new IOException("后台服务账户不匹配");
                string expected=Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"QDisplay.Service.exe");
                if(!String.Equals(Environment.ExpandEnvironmentVariables(configured).Trim().Trim('"'),expected,StringComparison.OrdinalIgnoreCase))throw new IOException("后台服务安装路径不匹配");
            }finally{if(service!=IntPtr.Zero)CloseServiceHandle(service);if(manager!=IntPtr.Zero)CloseServiceHandle(manager);}
        }
        public static byte[] Read(Stream stream,int count,int timeout=12000){if(count<0||count>Commands.MaximumBody)throw new IOException("消息过大");
            byte[] b=new byte[count];int off=0;while(off<count){IAsyncResult read=stream.BeginRead(b,off,count-off,null,null);
                if(!read.AsyncWaitHandle.WaitOne(timeout)){stream.Dispose();throw new TimeoutException("后台响应超时");}
                int n=stream.EndRead(read);read.AsyncWaitHandle.Close();if(n==0)throw new EndOfStreamException();off+=n;}return b;}
        public static byte[] Request(int command,byte[] body){using(NamedPipeClientStream pipe=new NamedPipeClientStream(".",Name,PipeDirection.InOut,PipeOptions.Asynchronous)){
            pipe.Connect(1500);uint pid;if(!GetNamedPipeServerProcessId(pipe.SafePipeHandle.DangerousGetHandle(),out pid))throw new IOException("无法验证后台服务");
            VerifyServer(pid);
            if(body==null)body=new byte[0];if(body.Length>Commands.MaximumBody)throw new IOException("消息过大");
            BinaryWriter writer=new BinaryWriter(pipe);writer.Write(0x31504451);writer.Write(command);writer.Write(body.Length);writer.Write(body);writer.Flush();
            byte[] header=Read(pipe,8,command==Commands.UploadAudio?95000:12000);int status=BitConverter.ToInt32(header,0),length=BitConverter.ToInt32(header,4);byte[] result=Read(pipe,length);
            if(status!=0)throw new InvalidOperationException(System.Text.Encoding.UTF8.GetString(result));return result;
        }}
        public static byte[] Request(int command){return Request(command,null);}
        public static int ClientSession(NamedPipeServerStream pipe){uint pid;
            if(!GetNamedPipeClientProcessId(pipe.SafePipeHandle.DangerousGetHandle(),out pid))throw new IOException("无法验证客户端");
            uint session;if(!ProcessIdToSessionId(pid,out session))throw new IOException("无法验证客户端会话");return unchecked((int)session);
        }
        public static NamedPipeServerStream Server(){PipeSecurity acl=new PipeSecurity();acl.SetAccessRuleProtection(true,false);
            acl.AddAccessRule(new PipeAccessRule(new SecurityIdentifier(WellKnownSidType.NetworkSid,null),PipeAccessRights.FullControl,AccessControlType.Deny));
            foreach(WellKnownSidType sid in new[]{WellKnownSidType.LocalSystemSid,WellKnownSidType.BuiltinAdministratorsSid})
                acl.AddAccessRule(new PipeAccessRule(new SecurityIdentifier(sid,null),PipeAccessRights.FullControl,AccessControlType.Allow));
            // A logged-on user is never granted ownership or ACL-changing rights.
            acl.AddAccessRule(new PipeAccessRule(new SecurityIdentifier(WellKnownSidType.InteractiveSid,null),PipeAccessRights.ReadWrite,AccessControlType.Allow));
            return new NamedPipeServerStream(Name,PipeDirection.InOut,8,PipeTransmissionMode.Byte,PipeOptions.Asynchronous,65536,65536,acl);
        }
    }
}
