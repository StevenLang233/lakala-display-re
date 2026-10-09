using System;
namespace QDisplay.Core {
    public sealed class Status {
        public string Mode="hardware",AudioMode="off",Message="正在连接设备",Port="",Error="",ServiceInstance="";
        public bool Connected,AudioAvailable,AudioPlaying;public int Volume=10,Session=-1,UiSession=-1;
        public double Fps,Cpu,Memory,TotalMemory;public long Frames,AudioTrackId,AudioCompletedId;
        public double NativeFrameMs,EncodeMs;public long WireBytes,FrameRequests;
        public int NativeBlockBytes=128*1024;public bool NativeWholeFrames,NativeSparseFrames,LastSparseFrame;public uint LastFrameHash,ReceiveUs,DecodeUs,DrawUs;
        public long PcmBlocks,PcmNonzeroSamples;public int AudioOutput,AudioHardwareVolume;
        public long ConnectionGeneration;
        public bool ScreenOn=true,ScreenPowerAvailable;
    }
    public sealed class Settings {
        public string Mode="hardware",PhotoFolder="",AudioMode="off",PhotoPath="",MusicPath="";
        public bool PhotoIsFolder=true,PhotoRecursive,MusicIsFolder,MusicRecursive,ResumeMusic,RepeatMusic,DisplayPositionSaved;
        public int Volume=10,Fps=30,PhotoSeconds=5,RefreshHz=30;
        public int MusicIndex,DisplayX,DisplayY,PreferencesVersion;
        public bool FollowWindowsScreen,ScreenOn=true;
    }
    public static class Commands {
        public const int Status=1,Mode=2,Frame=3,UploadAudio=4,PlayAudio=5,StopAudio=6,Volume=7,AudioMode=8,Pcm=9,Exit=10,Photos=11,Preview=12,PhotoFrame=13,PreparedDisplay=14,PreparedPhoto=15,KeepFrame=16,VerifyFrame=17,AudioState=18,AudioOutput=19;
        public const int ScreenPower=20;
        public const int MaximumBody=4*1024*1024;
    }
    public static class SessionPolicy {
        public static bool CanControl(int active,int sender){return active>=0 && sender==active;}
        public static string AfterSwitch(string mode){return mode=="display"?"hardware":mode;}
    }
    public static class RecoveryPolicy {
        public static string Mode(string mode){return mode=="display"||mode=="photo"?mode:"hardware";}
        public static string Audio(string mode){return mode=="windows"||mode=="local"?mode:"off";}
        public static int Volume(int volume){return Math.Max(0,Math.Min(100,volume));}
        public static bool Needed(Status status,int session,string service,long generation,string mode,bool pending){
            return status.Connected&&SessionPolicy.CanControl(status.Session,session)&&
                (pending||status.ServiceInstance!=service||status.ConnectionGeneration!=generation||status.Mode!=Mode(mode)||status.UiSession!=session);
        }
    }
}
