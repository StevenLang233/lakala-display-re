// Read-only service/pipe identity checks; no CIM or administrator token needed.
using System;
using System.IO;
using System.Runtime.InteropServices;
using System.IO.Pipes;
public static class QDisplayRuntime {
    [DllImport("advapi32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern IntPtr OpenSCManager(string machine,string database,uint access);
    [DllImport("advapi32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern IntPtr OpenService(IntPtr manager,string name,uint access);
    [DllImport("advapi32.dll",SetLastError=true)] static extern bool QueryServiceStatusEx(IntPtr service,int level,out Status status,int size,out int needed);
    [DllImport("advapi32.dll")] static extern bool CloseServiceHandle(IntPtr handle);
    [DllImport("kernel32.dll",SetLastError=true)] static extern bool GetNamedPipeServerProcessId(IntPtr pipe,out uint pid);
    [StructLayout(LayoutKind.Sequential)] struct Status {public uint Type,State,Controls,Error,SpecificError,Checkpoint,WaitHint,Pid,Flags;}
    public static void Verify(NamedPipeClientStream pipe){
        IntPtr manager=OpenSCManager(null,null,1),service=IntPtr.Zero;
        try{if(manager==IntPtr.Zero)throw new IOException("Cannot query SCM");service=OpenService(manager,"QDisplayDevice",4);
            Status status;int needed;uint pid;
            if(service==IntPtr.Zero||!QueryServiceStatusEx(service,0,out status,Marshal.SizeOf(typeof(Status)),out needed))throw new IOException("Cannot query QDisplay service");
            if(!GetNamedPipeServerProcessId(pipe.SafePipeHandle.DangerousGetHandle(),out pid)||status.State!=4||status.Type!=16||pid!=status.Pid)throw new IOException("QDisplay pipe/service identity mismatch");
        }finally{if(service!=IntPtr.Zero)CloseServiceHandle(service);if(manager!=IntPtr.Zero)CloseServiceHandle(manager);}
    }
}
