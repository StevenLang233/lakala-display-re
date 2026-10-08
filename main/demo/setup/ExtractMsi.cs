// Read an MSI's embedded cabinets and file table without running its actions.
// Original project code; no external extractor code is incorporated.
using System;
using System.IO;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Diagnostics;

public static class QDisplayMsi {
    [DllImport("msi.dll",CharSet=CharSet.Unicode)] static extern uint MsiOpenDatabase(string file,IntPtr mode,out uint db);
    [DllImport("msi.dll",CharSet=CharSet.Unicode)] static extern uint MsiDatabaseOpenView(uint db,string sql,out uint view);
    [DllImport("msi.dll")] static extern uint MsiViewExecute(uint view,uint record);
    [DllImport("msi.dll")] static extern uint MsiViewFetch(uint view,out uint record);
    [DllImport("msi.dll",CharSet=CharSet.Unicode)] static extern uint MsiRecordGetString(uint record,uint field,StringBuilder text,ref uint length);
    [DllImport("msi.dll")] static extern uint MsiRecordReadStream(uint record,uint field,byte[] data,ref uint length);
    [DllImport("msi.dll")] static extern uint MsiCloseHandle(uint handle);
    static void Check(uint code){if(code!=0)throw new IOException("MSI read error "+code);}
    static string Value(uint record,uint field){uint n=4096;StringBuilder s=new StringBuilder((int)n);Check(MsiRecordGetString(record,field,s,ref n));return s.ToString();}
    static List<string[]> Rows(uint db,string query,int fields){uint view;Check(MsiDatabaseOpenView(db,query,out view));try{
        Check(MsiViewExecute(view,0));List<string[]> rows=new List<string[]>();uint record;
        while(true){uint code=MsiViewFetch(view,out record);if(code==259)break;Check(code);try{
            string[] row=new string[fields];for(uint i=0;i<fields;i++)row[i]=Value(record,i+1);rows.Add(row);
        }finally{MsiCloseHandle(record);}}return rows;
    }finally{MsiCloseHandle(view);}}
    static string Name(string name){string[] parts=name.Split('|');string value=parts[parts.Length-1];if(value=="."||value=="SourceDir")return "";
        if(value==".."||value.IndexOfAny(new[]{'\\','/',':'})>=0)throw new IOException("Unsafe MSI filename");return value;}
    static string DirectoryPath(string key,Dictionary<string,string[]> dirs,HashSet<string> seen){
        if(String.IsNullOrEmpty(key))return "";if(!seen.Add(key)||!dirs.ContainsKey(key))throw new IOException("Invalid MSI directory tree");
        string[] row=dirs[key];return Path.Combine(DirectoryPath(row[1],dirs,seen),Name(row[2].Split(':')[0]));}
    public static void Extract(string package,string output){uint db;Check(MsiOpenDatabase(package,IntPtr.Zero,out db));try{
        Directory.CreateDirectory(output);string temp=Path.Combine(output,"_cab_files");Directory.CreateDirectory(temp);
        Dictionary<string,string[]> dirs=new Dictionary<string,string[]>();foreach(string[] r in Rows(db,"SELECT `Directory`,`Directory_Parent`,`DefaultDir` FROM `Directory`",3))dirs.Add(r[0],r);
        Dictionary<string,string> components=new Dictionary<string,string>();foreach(string[] r in Rows(db,"SELECT `Component`,`Directory_` FROM `Component`",2))components.Add(r[0],r[1]);
        foreach(string[] row in Rows(db,"SELECT `Cabinet` FROM `Media`",1)){
            if(!row[0].StartsWith("#"))throw new IOException("Expected embedded cabinet");string stream=row[0].Substring(1);
            if(stream.IndexOf('\'')>=0)throw new IOException("Unsafe cabinet name");string cab=Path.Combine(temp,Name(stream));uint view;
            Check(MsiDatabaseOpenView(db,"SELECT `Data` FROM `_Streams` WHERE `Name`='"+stream+"'",out view));try{
                Check(MsiViewExecute(view,0));uint record;Check(MsiViewFetch(view,out record));try{using(FileStream f=File.Create(cab)){
                    byte[] b=new byte[65536];while(true){uint n=(uint)b.Length;Check(MsiRecordReadStream(record,1,b,ref n));if(n==0)break;f.Write(b,0,(int)n);}
                }}finally{MsiCloseHandle(record);}
            }finally{MsiCloseHandle(view);}
            ProcessStartInfo info=new ProcessStartInfo(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System),"expand.exe"),"-F:* \""+cab+"\" \""+temp+"\"");
            info.UseShellExecute=false;info.CreateNoWindow=true;info.RedirectStandardOutput=true;info.RedirectStandardError=true;
            using(Process p=Process.Start(info)){var stdout=p.StandardOutput.ReadToEndAsync();var stderr=p.StandardError.ReadToEndAsync();
                if(!p.WaitForExit(90000)){p.Kill();throw new IOException("Cabinet extraction timed out");}if(p.ExitCode!=0)throw new IOException("expand.exe failed: "+stderr.Result);}
        }
        foreach(string[] r in Rows(db,"SELECT `File`,`Component_`,`FileName` FROM `File`",3)){
            string source=Path.Combine(temp,Name(r[0]));if(!File.Exists(source))throw new IOException("Missing cabinet member "+r[0]);
            string relative=DirectoryPath(components[r[1]],dirs,new HashSet<string>());string dest=Path.Combine(output,relative,Name(r[2]));
            string root=Path.GetFullPath(output)+Path.DirectorySeparatorChar;if(!Path.GetFullPath(dest).StartsWith(root,StringComparison.OrdinalIgnoreCase))throw new IOException("MSI extraction path escapes root");
            Directory.CreateDirectory(Path.GetDirectoryName(dest));File.Copy(source,dest,true);
        }
    }finally{MsiCloseHandle(db);}}
}
