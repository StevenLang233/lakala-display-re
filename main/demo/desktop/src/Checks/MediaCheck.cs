using System;
using System.IO;
using System.Threading;
using QDisplay.Core;
public static class MediaCheck {
    static void Require(bool value,string test){if(!value)throw new Exception(test);}
    public static int Main(string[] args){string root=Path.GetFullPath(args[0]);Directory.CreateDirectory(root);Directory.CreateDirectory(Path.Combine(root,"子文件夹"));
        File.WriteAllText(Path.Combine(root,"图片.PNG"),"fixture");File.WriteAllText(Path.Combine(root,"歌曲.MP3"),"fixture");File.WriteAllText(Path.Combine(root,"ignore.txt"),"fixture");
        File.WriteAllText(Path.Combine(root,"子文件夹","图片2.jpg"),"fixture");File.WriteAllText(Path.Combine(root,"子文件夹","歌曲2.mp3"),"fixture");
        Require(MediaCatalog.Read(root,true,false,MediaCatalog.Images,CancellationToken.None).Files.Length==1,"image current folder");
        Require(MediaCatalog.Read(root,true,true,MediaCatalog.Images,CancellationToken.None).Files.Length==2,"image recursive folder");
        Require(MediaCatalog.Read(root,true,false,MediaCatalog.Music,CancellationToken.None).Files.Length==1,"music current folder");
        Require(MediaCatalog.Read(root,true,true,MediaCatalog.Music,CancellationToken.None).Files.Length==2,"music recursive folder");
        Require(MediaCatalog.Read(Path.Combine(root,"图片.PNG"),false,false,MediaCatalog.Images,CancellationToken.None).Files.Length==1,"single image");
        Require(MediaCatalog.Read(Path.Combine(root,"歌曲.MP3"),false,false,MediaCatalog.Music,CancellationToken.None).Files.Length==1,"single music");
        bool cancelled=false;try{MediaCatalog.Read(root,true,true,MediaCatalog.Images,new CancellationToken(true));}catch(OperationCanceledException){cancelled=true;}Require(cancelled,"cancel folder scan");
        bool missing=false;try{MediaCatalog.Read(Path.Combine(root,"missing"),true,true,MediaCatalog.Images,CancellationToken.None);}catch(DirectoryNotFoundException){missing=true;}Require(missing,"missing source reports error");
        Require(Playlist.Next(0,2,1)==1&&Playlist.Next(1,2,1)==0&&Playlist.Next(0,2,-1)==1&&Playlist.Next(0,1,1)==0&&Playlist.Next(0,0,1)==-1,"playlist boundaries");
        File.WriteAllText(args[1],"{\"success\":true,\"checks\":9,\"tested\":\"single file, folder, recursive folder, case-insensitive extension, cancellation, missing source, playlist advance\"}");return 0;
    }
}
