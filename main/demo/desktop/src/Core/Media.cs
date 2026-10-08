using System;
using System.IO;
using System.Collections.Generic;
using System.Threading;
namespace QDisplay.Core {
    public sealed class MediaSelection {
        public string Source;
        public bool Folder,Recursive;
        public string[] Files=new string[0];
        public int UnavailableFolders,SkippedLinks;
    }
    public static class MediaCatalog {
        public static readonly string[] Images={".jpg",".jpeg",".png",".bmp",".gif"};
        public static readonly string[] Music={".mp3"};
        public static MediaSelection Read(string source,bool folder,bool recursive,string[] extensions,CancellationToken cancel){
            string path=Path.GetFullPath(source);MediaSelection result=new MediaSelection{Source=path,Folder=folder,Recursive=recursive};
            HashSet<string> allowed=new HashSet<string>(extensions,StringComparer.OrdinalIgnoreCase);
            if(!folder){if(!File.Exists(path))throw new FileNotFoundException("文件不存在",path);if(!allowed.Contains(Path.GetExtension(path)))throw new InvalidDataException("不支持此文件格式");result.Files=new[]{path};return result;}
            if(!Directory.Exists(path))throw new DirectoryNotFoundException("文件夹不存在："+path);
            List<string> files=new List<string>();Stack<string> directories=new Stack<string>();directories.Push(path);
            while(directories.Count>0){cancel.ThrowIfCancellationRequested();string current=directories.Pop();
                try{foreach(string file in Directory.GetFiles(current)){cancel.ThrowIfCancellationRequested();if(allowed.Contains(Path.GetExtension(file)))files.Add(file);}
                    if(recursive)foreach(string directory in Directory.GetDirectories(current)){cancel.ThrowIfCancellationRequested();if((File.GetAttributes(directory)&FileAttributes.ReparsePoint)!=0){result.SkippedLinks++;continue;}directories.Push(directory);}}
                catch(UnauthorizedAccessException){if(current==path)throw;result.UnavailableFolders++;}
                catch(IOException){if(current==path)throw;result.UnavailableFolders++;}
            }
            files.Sort(StringComparer.OrdinalIgnoreCase);result.Files=files.ToArray();return result;
        }
    }
    public static class Playlist {
        // A single file remains displayed/replays; folders advance through their full list.
        public static int Next(int index,int count,int direction){if(count==0)return -1;return ((index+direction)%count+count)%count;}
    }
}
