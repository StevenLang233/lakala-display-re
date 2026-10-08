using System;
using System.IO;
using System.Drawing;
using System.Windows.Forms;
using System.Threading;
using System.Threading.Tasks;
using System.Diagnostics;
using System.Collections.Generic;
using QDisplay.Core;
namespace QDisplay.Windows {
    public sealed class MainWindow : Form {
        [System.Runtime.InteropServices.DllImport("user32.dll",CharSet=System.Runtime.InteropServices.CharSet.Unicode)]static extern uint RegisterWindowMessage(string text);
        [System.Runtime.InteropServices.DllImport("user32.dll",CharSet=System.Runtime.InteropServices.CharSet.Unicode)]static extern IntPtr FindWindow(string type,string title);
        [System.Runtime.InteropServices.DllImport("user32.dll")]static extern bool PostMessage(IntPtr window,uint message,IntPtr first,IntPtr second);
        static readonly uint ShowMessage=RegisterWindowMessage("QDisplay.Show.v1");
        public static void ShowExisting(){IntPtr window=FindWindow(null,"QDisplay");if(window!=IntPtr.Zero)PostMessage(window,ShowMessage,IntPtr.Zero,IntPtr.Zero);}
        protected override void WndProc(ref Message message){if((uint)message.Msg==ShowMessage){OpenWindow();return;}if(message.Msg==0x007e){Interlocked.Increment(ref pictureRevision);if(IsHandleCreated&&!exiting)BeginInvoke((Action)RememberDisplayPosition);}base.WndProc(ref message);}
        readonly Color surface=Color.FromArgb(22,33,49),textColor=Color.FromArgb(229,238,246),muted=Color.FromArgb(150,169,190),accent=Color.FromArgb(33,104,122);
        readonly Label connection=new Label(),rate=new Label(),photoInfo=new Label(),musicInfo=new Label(),audioStatus=new Label(),currentPhoto=new Label(),error=new Label();
        readonly TextBox photoPath=new TextBox(),musicPath=new TextBox();
        readonly CheckBox photoRecursive=new CheckBox(),musicRecursive=new CheckBox(),repeatMusic=new CheckBox();readonly ListBox tracks=new ListBox();
        readonly ComboBox audioMode=new ComboBox(),refreshRate=new ComboBox();readonly TrackBar volume=new TrackBar();readonly NumericUpDown fps=new NumericUpDown(),interval=new NumericUpDown();
        readonly System.Windows.Forms.Timer poll=new System.Windows.Forms.Timer();readonly ToolTip tips=new ToolTip();readonly List<Control> commands=new List<Control>();
        readonly Button display,photo,hardware,play;readonly NotifyIcon tray;readonly FlowLayoutPanel settingsPanel=new FlowLayoutPanel();
        readonly string config=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"QDisplay","ui.json");
        readonly int session=Process.GetCurrentProcess().SessionId;
        volatile bool exiting,captureEnabled,photoEnabled,busy;bool polling,restoring,volumeDragging,playlistWanted;volatile MediaSelection pictureSelection;
        MediaSelection musicSelection;Settings saved=new Settings();Loopback loopback;Thread capture;
        CancellationTokenSource photoScan,musicScan;int pictureRevision,musicRevision,musicIndex,modeRevision;long playingId;string uploadedPath="";long uploadedLength,uploadedWrite;
        volatile int targetFps=30,displayHz=30,photoSeconds=5,nativeBlockBytes=128*1024;volatile bool nativeWholeFrames,nativeSparseFrames;readonly object captureGate=new object();long transferMicroseconds;
        int pendingVolume=-1,volumeSending,volumeRevision;
        volatile bool recoveryPending=true,deviceConnected;bool audioRecoveryPending,musicLoading;
        string appliedService="";long appliedConnection=-1;DateTime nextRecovery=DateTime.MinValue,nextAudioRecovery=DateTime.MinValue;
        public MainWindow(bool hidden,string initialMode=null,string configurationPath=null,bool startWatchdog=true){
            if(configurationPath!=null)config=Path.GetFullPath(configurationPath);
            Text="QDisplay";Size area=Screen.PrimaryScreen.WorkingArea.Size;ClientSize=new Size(Math.Min(1100,area.Width-80),Math.Min(940,area.Height-100));MinimumSize=new Size(940,700);
            BackColor=Color.FromArgb(12,20,32);ForeColor=textColor;Font=new Font("Microsoft YaHei UI",10);StartPosition=FormStartPosition.CenterScreen;AutoScaleMode=AutoScaleMode.Dpi;
            Icon=Icon.ExtractAssociatedIcon(Application.ExecutablePath);
            TableLayoutPanel root=new TableLayoutPanel{Dock=DockStyle.Fill,ColumnCount=1,RowCount=4,Padding=new Padding(24,16,24,12)};
            root.RowStyles.Add(new RowStyle(SizeType.Absolute,80));root.RowStyles.Add(new RowStyle(SizeType.Absolute,58));root.RowStyles.Add(new RowStyle(SizeType.Percent,100));root.RowStyles.Add(new RowStyle(SizeType.Absolute,26));Controls.Add(root);
            Panel header=new Panel{Dock=DockStyle.Fill};root.Controls.Add(header,0,0);
            header.Controls.Add(new PictureBox{Location=new Point(0,2),Size=new Size(48,48),Image=Pictures.Logo(128),SizeMode=PictureBoxSizeMode.Zoom});
            header.Controls.Add(new Label{Text="QDisplay",Location=new Point(58,0),Size=new Size(240,48),Font=new Font("Segoe UI",25,FontStyle.Bold)});
            connection.SetBounds(0,52,760,24);connection.ForeColor=muted;header.Controls.Add(connection);rate.SetBounds(800,52,200,24);rate.Anchor=AnchorStyles.Top|AnchorStyles.Right;rate.TextAlign=ContentAlignment.MiddleRight;rate.ForeColor=muted;header.Controls.Add(rate);
            FlowLayoutPanel modes=new FlowLayoutPanel{Dock=DockStyle.Fill,WrapContents=false};root.Controls.Add(modes,0,1);
            display=MakeButton("副屏",160,48,()=>SetMode("display"));photo=MakeButton("相框",160,48,()=>SetMode("photo"));hardware=MakeButton("硬件信息",160,48,()=>SetMode("hardware"));modes.Controls.AddRange(new Control[]{display,photo,hardware});
            settingsPanel.Dock=DockStyle.Fill;settingsPanel.AutoScroll=true;settingsPanel.FlowDirection=FlowDirection.TopDown;settingsPanel.WrapContents=false;settingsPanel.Margin=new Padding(0);root.Controls.Add(settingsPanel,0,2);
            Panel frame=Card("副屏",106);AddLabel(frame,"目标帧率",14,38,150,26);fps.SetBounds(174,35,110,29);fps.Minimum=1;fps.Maximum=60;fps.Value=30;Style(fps);frame.Controls.Add(fps);fps.ValueChanged+=(s,e)=>{targetFps=(int)fps.Value;saved.Fps=targetFps;Save();};
            AddLabel(frame,"Windows 刷新率",14,76,150,26);refreshRate.SetBounds(174,72,110,29);refreshRate.DropDownStyle=ComboBoxStyle.DropDownList;refreshRate.Items.AddRange(new object[]{"30 Hz","60 Hz"});refreshRate.SelectedIndex=0;Style(refreshRate);frame.Controls.Add(refreshRate);commands.Add(refreshRate);refreshRate.SelectedIndexChanged+=(s,e)=>{displayHz=refreshRate.SelectedIndex==1?60:30;saved.RefreshHz=displayHz;Save();if(!restoring&&captureEnabled)SetMode("display");};
            Panel pictures=Card("相框",228);AddButton(pictures,"选择图片",14,36,145,36,()=>ChooseMedia(true,false));AddButton(pictures,"选择文件夹",169,36,145,36,()=>ChooseMedia(true,true));
            PathBox(pictures,photoPath,82);photoPath.Text="尚未选择图片或文件夹";Check(pictures,photoRecursive,"同时读取子文件夹",14,139);photoRecursive.CheckedChanged+=(s,e)=>{saved.PhotoRecursive=photoRecursive.Checked;if(!restoring&&saved.PhotoIsFolder&&saved.PhotoPath.Length>0)LoadSelection(true,saved.PhotoPath,true);Save();};
            photoInfo.SetBounds(14,166,430,22);photoInfo.Anchor=AnchorStyles.Top|AnchorStyles.Left|AnchorStyles.Right;photoInfo.AutoEllipsis=true;photoInfo.ForeColor=muted;pictures.Controls.Add(photoInfo);AddLabel(pictures,"轮播间隔（秒）",14,197,166,26);interval.SetBounds(190,193,110,29);interval.Minimum=1;interval.Maximum=3600;interval.Value=5;Style(interval);pictures.Controls.Add(interval);interval.ValueChanged+=(s,e)=>{photoSeconds=(int)interval.Value;saved.PhotoSeconds=photoSeconds;Save();};
            Panel sound=Card("音频",410);audioMode.SetBounds(14,36,430,32);audioMode.Anchor=AnchorStyles.Left|AnchorStyles.Top|AnchorStyles.Right;audioMode.DropDownStyle=ComboBoxStyle.DropDownList;audioMode.Items.AddRange(new object[]{"关闭","电脑声音","独立播放（MP3）"});Style(audioMode);sound.Controls.Add(audioMode);audioMode.SelectedIndex=0;audioMode.SelectedIndexChanged+=(s,e)=>{if(!restoring)ChangeAudio();};commands.Add(audioMode);
            AddButton(sound,"选择音频",14,80,145,35,()=>ChooseMedia(false,false));AddButton(sound,"选择文件夹",169,80,145,35,()=>ChooseMedia(false,true));PathBox(sound,musicPath,125);musicPath.Text="尚未选择音频或文件夹";
            Check(sound,musicRecursive,"同时读取子文件夹",14,179);Check(sound,repeatMusic,"循环播放",260,179);repeatMusic.CheckedChanged+=(s,e)=>{saved.RepeatMusic=repeatMusic.Checked;Save();};musicRecursive.CheckedChanged+=(s,e)=>{saved.MusicRecursive=musicRecursive.Checked;if(!restoring&&saved.MusicIsFolder&&saved.MusicPath.Length>0)LoadSelection(false,saved.MusicPath,true);Save();};
            musicInfo.SetBounds(14,211,440,23);musicInfo.ForeColor=muted;sound.Controls.Add(musicInfo);
            tracks.SetBounds(14,237,430,62);tracks.Anchor=AnchorStyles.Top|AnchorStyles.Left|AnchorStyles.Right;tracks.BorderStyle=BorderStyle.None;tracks.IntegralHeight=false;tracks.HorizontalScrollbar=true;Style(tracks);sound.Controls.Add(tracks);tracks.DoubleClick+=(s,e)=>StartTrack(Math.Max(0,tracks.SelectedIndex));
            tracks.SelectedIndexChanged+=(s,e)=>{if(!restoring&&!playlistWanted&&tracks.SelectedIndex>=0){saved.MusicIndex=tracks.SelectedIndex;Save();}};
            AddButton(sound,"上一首",14,309,91,34,()=>SkipTrack(-1));play=AddButton(sound,"播放",115,309,101,34,()=>StartTrack(Math.Max(0,tracks.SelectedIndex)));AddButton(sound,"停止",226,309,101,34,StopAudio);AddButton(sound,"下一首",337,309,91,34,()=>SkipTrack(1));
            AddLabel(sound,"音量",14,356,56,26);volume.SetBounds(74,348,285,41);volume.Maximum=100;volume.Minimum=0;volume.TickFrequency=10;volume.Value=10;volume.Anchor=AnchorStyles.Top|AnchorStyles.Left|AnchorStyles.Right;sound.Controls.Add(volume);volume.MouseDown+=(s,e)=>volumeDragging=true;volume.MouseUp+=(s,e)=>{volumeDragging=false;SetVolume();};volume.KeyUp+=(s,e)=>SetVolume();volume.Scroll+=(s,e)=>SetVolume();volume.ValueChanged+=(s,e)=>audioStatus.Text="音量 "+volume.Value+"%";
            audioStatus.SetBounds(14,387,430,21);audioStatus.ForeColor=muted;audioStatus.Text="音量 10%";sound.Controls.Add(audioStatus);
            error.Dock=DockStyle.Fill;error.ForeColor=Color.FromArgb(245,169,137);error.AutoEllipsis=true;root.Controls.Add(error,0,3);
            settingsPanel.SizeChanged+=(s,e)=>ResizeCards();ResizeCards();
            ContextMenuStrip menu=new ContextMenuStrip();menu.Items.Add("打开",null,(s,e)=>OpenWindow());menu.Items.Add("退出",null,(s,e)=>ExitApp());tray=new NotifyIcon{Icon=Icon,Text="QDisplay",Visible=true,ContextMenuStrip=menu};tray.DoubleClick+=(s,e)=>OpenWindow();
            FormClosing+=(s,e)=>{if(!exiting&&e.CloseReason==CloseReason.UserClosing){e.Cancel=true;Hide();}else if(!exiting){exiting=true;captureEnabled=photoEnabled=false;playlistWanted=false;tray.Visible=false;if(loopback!=null)loopback.Dispose();if(Ipc.ActiveSession==session)try{Displays.Detach();}catch{}}};
            Shown+=(s,e)=>{if(hidden)Hide();Poll();};poll.Interval=900;poll.Tick+=(s,e)=>Poll();poll.Start();
            capture=new Thread(CaptureLoop){IsBackground=true,Name="Active desktop capture"};capture.Start();
            restoring=true;try{saved=Ipc.Parse<Settings>(File.ReadAllBytes(config));if(String.IsNullOrEmpty(saved.PhotoPath))saved.PhotoPath=saved.PhotoFolder;
                saved.Mode=RecoveryPolicy.Mode(saved.Mode);saved.AudioMode=RecoveryPolicy.Audio(saved.AudioMode);saved.Volume=RecoveryPolicy.Volume(saved.Volume);
                photoRecursive.Checked=saved.PhotoRecursive;musicRecursive.Checked=saved.MusicRecursive;repeatMusic.Checked=saved.RepeatMusic;volume.Value=saved.Volume;audioMode.SelectedIndex=saved.AudioMode=="windows"?1:saved.AudioMode=="local"?2:0;
                fps.Value=Math.Max(1,Math.Min(60,saved.Fps));refreshRate.SelectedIndex=saved.RefreshHz==60?1:0;interval.Value=Math.Max(1,Math.Min(3600,saved.PhotoSeconds));}catch{}finally{restoring=false;}
            if(initialMode!=null)saved.Mode=RecoveryPolicy.Mode(initialMode);saved.PreferencesVersion=1;
            if(!String.IsNullOrEmpty(saved.PhotoPath))LoadSelection(true,saved.PhotoPath,saved.PhotoIsFolder);if(!String.IsNullOrEmpty(saved.MusicPath))LoadSelection(false,saved.MusicPath,saved.MusicIsFolder);
            if(startWatchdog)Process.Start(new ProcessStartInfo(Application.ExecutablePath,"--watch "+Process.GetCurrentProcess().Id+" "+session){UseShellExecute=false,CreateNoWindow=true});
        }
        void Style(Control control){control.BackColor=surface;control.ForeColor=textColor;}
        Panel Card(string title,int height){Panel card=new Panel{Width=500,Height=height,BackColor=surface,Margin=new Padding(0,0,0,14)};AddLabel(card,title,14,8,300,26).Font=new Font(Font,FontStyle.Bold);settingsPanel.Controls.Add(card);return card;}
        void ResizeCards(){foreach(Control card in settingsPanel.Controls)card.Width=Math.Max(440,settingsPanel.ClientSize.Width-SystemInformation.VerticalScrollBarWidth-3);}
        Label AddLabel(Control parent,string text,int x,int y,int width,int height){Label label=new Label{Text=text,Location=new Point(x,y),Size=new Size(width,height)};parent.Controls.Add(label);return label;}
        Button MakeButton(string text,int width,int height,Action action){Button button=new Button{Text=text,Size=new Size(width,height),FlatStyle=FlatStyle.Flat,BackColor=surface,ForeColor=textColor,Margin=new Padding(0,0,12,0)};button.FlatAppearance.BorderSize=1;button.FlatAppearance.BorderColor=Color.FromArgb(49,65,84);button.Click+=(s,e)=>action();commands.Add(button);return button;}
        Button AddButton(Control parent,string text,int x,int y,int width,int height,Action action){Button button=MakeButton(text,width,height,action);button.Location=new Point(x,y);parent.Controls.Add(button);return button;}
        void PathBox(Control parent,TextBox box,int y){box.SetBounds(14,y,430,48);box.Anchor=AnchorStyles.Top|AnchorStyles.Left|AnchorStyles.Right;box.Multiline=true;box.ReadOnly=true;box.ScrollBars=ScrollBars.Vertical;box.BorderStyle=BorderStyle.FixedSingle;Style(box);parent.Controls.Add(box);}
        void Check(Control parent,CheckBox box,string title,int x,int y){box.SetBounds(x,y,235,26);box.Text=title;box.ForeColor=textColor;parent.Controls.Add(box);}
        void OpenWindow(){Show();WindowState=FormWindowState.Normal;Activate();}
        void Save(){if(restoring)return;try{Directory.CreateDirectory(Path.GetDirectoryName(config));File.WriteAllBytes(config+".tmp",Ipc.Json(saved));if(File.Exists(config))File.Replace(config+".tmp",config,null);else File.Move(config+".tmp",config);}catch(Exception ex){ShowError(ex.Message);}}
        void ShowError(string message){if(exiting||!IsHandleCreated)return;if(InvokeRequired){BeginInvoke((Action)(()=>ShowError(message)));return;}error.Text=message;tips.SetToolTip(error,message);}
        async void Run(Action task,Action complete=null,Action<Exception> failed=null){if(busy){ShowError("正在执行设备操作，请稍候。");return;}busy=true;foreach(Control control in commands)control.Enabled=false;error.Text="";
            try{await Task.Run(task);if(!exiting&&complete!=null)complete();}catch(Exception ex){if(!exiting){ShowError(ex.Message);if(failed!=null)failed(ex);}}finally{busy=false;if(!exiting)foreach(Control control in commands)control.Enabled=true;}}
        void SendText(int command,string text){Ipc.Request(command,System.Text.Encoding.UTF8.GetBytes(text));}
        void RememberDisplayPosition(){if(saved==null||exiting||Ipc.ActiveSession!=session)return;try{foreach(Displays.Entry entry in Displays.List())if(entry.Virtual&&entry.Attached){saved.DisplayX=entry.Bounds.X;saved.DisplayY=entry.Bounds.Y;saved.DisplayPositionSaved=true;Save();break;}}catch{}}
        void ApplyDisplayMode(string mode,Point? position){lock(captureGate){SendText(Commands.Mode,mode);try{if(mode=="display")Displays.Attach(displayHz,position);else Displays.Detach();captureEnabled=mode=="display";photoEnabled=mode=="photo";Interlocked.Increment(ref pictureRevision);}catch{Displays.Detach();SendText(Commands.Mode,"hardware");throw;}}}
        void SetMode(string mode){if(busy){ShowError("正在执行设备操作，请稍候。");return;}RememberDisplayPosition();saved.Mode=RecoveryPolicy.Mode(mode);Save();Interlocked.Increment(ref modeRevision);captureEnabled=photoEnabled=false;
            if(!deviceConnected){recoveryPending=true;return;}Point? position=saved.DisplayPositionSaved?(Point?)new Point(saved.DisplayX,saved.DisplayY):null;
            Run(()=>ApplyDisplayMode(saved.Mode,position),RememberDisplayPosition);}
        void RestoreConnection(Status status){if(busy||DateTime.UtcNow<nextRecovery)return;nextRecovery=DateTime.UtcNow.AddSeconds(2);
            string mode=RecoveryPolicy.Mode(saved.Mode),sound=RecoveryPolicy.Audio(saved.AudioMode);int requestedVolume=saved.Volume,requestedRevision=Volatile.Read(ref volumeRevision);
            Point? position=saved.DisplayPositionSaved?(Point?)new Point(saved.DisplayX,saved.DisplayY):null;
            bool resumeLocal=sound=="local"&&saved.ResumeMusic&&!musicLoading&&musicSelection!=null&&musicSelection.Files.Length>0;
            int index=resumeLocal?Math.Max(0,Math.Min(saved.MusicIndex,musicSelection.Files.Length-1)):0;
            string music=resumeLocal?musicSelection.Files[index]:null;int selectedRevision=musicRevision;Status started=null;Exception audioFailure=null;
            captureEnabled=photoEnabled=false;playlistWanted=false;playingId=0;uploadedPath="";Interlocked.Increment(ref modeRevision);
            Run(()=>{StopLoopback();ApplyDisplayMode(mode,position);SendText(Commands.Volume,requestedVolume.ToString());SendText(Commands.AudioMode,"off");
                if(sound=="windows")try{StartWindowsAudio(requestedVolume);}catch(Exception ex){audioFailure=ex;}
                else if(resumeLocal)started=PlayTrack(music,selectedRevision,requestedVolume);
            },()=>{appliedService=status.ServiceInstance;appliedConnection=status.ConnectionGeneration;recoveryPending=false;
                audioRecoveryPending=sound=="local"&&saved.ResumeMusic&&!resumeLocal;
                if(audioFailure!=null){nextAudioRecovery=DateTime.UtcNow.AddSeconds(5);ShowError(audioFailure.Message);}
                if(started!=null){playingId=started.AudioTrackId;playlistWanted=true;musicIndex=index;tracks.SelectedIndex=index;play.Text="重新播放";}
                if(requestedRevision!=Volatile.Read(ref volumeRevision)){Interlocked.Exchange(ref pendingVolume,saved.Volume);StartVolumeSender();}else Interlocked.Exchange(ref pendingVolume,-1);
                RememberDisplayPosition();SystemLog.Log("Restored configuration: "+mode+", audio "+sound+", connection "+appliedConnection);
            },ex=>{recoveryPending=true;captureEnabled=photoEnabled=false;});}
        void RestoreWindowsAudio(){if(busy||DateTime.UtcNow<nextAudioRecovery)return;nextAudioRecovery=DateTime.UtcNow.AddSeconds(5);int requestedVolume=saved.Volume;
            Run(()=>{StopLoopback();StartWindowsAudio(requestedVolume);});}
        async void Poll(){if(polling||exiting||busy)return;polling=true;int observedRevision=Volatile.Read(ref modeRevision),observedVolumeRevision=Volatile.Read(ref volumeRevision);try{Status status=await Task.Run(()=>Ipc.Parse<Status>(Ipc.Request(Commands.Status)));if(exiting||busy||observedRevision!=Volatile.Read(ref modeRevision))return;
                nativeBlockBytes=status.NativeBlockBytes;nativeWholeFrames=status.NativeWholeFrames;nativeSparseFrames=status.NativeSparseFrames;Interlocked.Exchange(ref transferMicroseconds,(long)(status.NativeFrameMs*1000));
                bool active=status.Session==session;deviceConnected=active&&status.Connected;
                connection.Text=(status.Connected?"已连接 "+status.Port:"正在连接设备")+(active?"":" · 当前账户不在活动桌面");if(status.Error.Length>0)connection.Text=status.Error;
                rate.Text=status.Fps.ToString("0.0")+" FPS";display.BackColor=saved.Mode=="display"?accent:surface;photo.BackColor=saved.Mode=="photo"?accent:surface;hardware.BackColor=saved.Mode=="hardware"?accent:surface;
                if(!deviceConnected){bool wasCapturing=captureEnabled;captureEnabled=photoEnabled=false;recoveryPending=true;playlistWanted=false;playingId=0;uploadedPath="";
                    if(wasCapturing&&active){RememberDisplayPosition();try{Displays.Detach();}catch{}}
                    if(loopback!=null){Loopback stopped=loopback;loopback=null;await Task.Run(()=>stopped.Dispose());}
                    audioStatus.Text="音量 "+saved.Volume+"% · 等待连接";return;}
                if(RecoveryPolicy.Needed(status,session,appliedService,appliedConnection,saved.Mode,recoveryPending)){RestoreConnection(status);return;}
                if(saved.AudioMode=="windows"&&(loopback==null||status.AudioMode!="windows"||loopback.LastError.Length>0)){RestoreWindowsAudio();return;}
                if(audioRecoveryPending&&!musicLoading){audioRecoveryPending=false;if(saved.ResumeMusic&&musicSelection!=null&&musicSelection.Files.Length>0)StartTrack(saved.MusicIndex);else if(saved.ResumeMusic)ShowError("保存的音乐没有读取成功，请检查所选路径。");}
                if(!busy&&!volumeDragging&&Volatile.Read(ref volumeSending)==0&&Volatile.Read(ref pendingVolume)<0&&observedVolumeRevision==Volatile.Read(ref volumeRevision)){volume.Value=saved.Volume;audioStatus.Text="音量 "+saved.Volume+"%"+(status.AudioMode=="local"?(status.AudioPlaying?" · 播放中":" · 已结束"):status.AudioMode=="windows"?" · 电脑声音":"");}
                if(playlistWanted&&!busy&&playingId>0&&status.AudioCompletedId==playingId&&status.AudioMode=="local"){
                    if(musicSelection!=null&&(musicIndex+1<musicSelection.Files.Length||repeatMusic.Checked))StartTrack(Playlist.Next(musicIndex,musicSelection.Files.Length,1));
                    else {playlistWanted=false;saved.ResumeMusic=false;Save();play.Text="播放";}}
            }catch{if(!exiting&&!busy&&observedRevision==Volatile.Read(ref modeRevision)){connection.Text="后台服务尚未连接，请完成 QDisplay 安装或检查服务。";deviceConnected=false;recoveryPending=true;RememberDisplayPosition();captureEnabled=photoEnabled=false;playlistWanted=false;uploadedPath="";if(Ipc.ActiveSession==session)try{Displays.Detach();}catch{}}}finally{polling=false;}}
        void ChooseMedia(bool pictures,bool folder){try{string path=null;string existing=pictures?saved.PhotoPath:saved.MusicPath;
            if(folder)path=FolderPicker.Choose(Handle,pictures?"选择图片文件夹":"选择音乐文件夹",existing);
            else using(OpenFileDialog dialog=new OpenFileDialog{Filter=pictures?"图片|*.jpg;*.jpeg;*.png;*.bmp;*.gif":"MP3 音频|*.mp3",CheckFileExists=true,InitialDirectory=Directory.Exists(existing)?existing:File.Exists(existing)?Path.GetDirectoryName(existing):""}){if(dialog.ShowDialog(this)==DialogResult.OK)path=dialog.FileName;}
            if(path!=null)LoadSelection(pictures,path,folder);
            }catch(Exception ex){ShowError(ex.Message);}
        }
        async void LoadSelection(bool pictures,string path,bool folder){CancellationTokenSource token=new CancellationTokenSource();if(pictures){if(photoScan!=null)photoScan.Cancel();photoScan=token;saved.PhotoPath=path;saved.PhotoIsFolder=folder;photoPath.Text=path;photoInfo.Text="正在读取…";photoRecursive.Enabled=folder;pictureSelection=null;Interlocked.Increment(ref pictureRevision);}
            else {musicLoading=true;if(musicScan!=null)musicScan.Cancel();musicScan=token;if(saved.MusicPath!=path||saved.MusicIsFolder!=folder){saved.MusicIndex=0;saved.ResumeMusic=false;}saved.MusicPath=path;saved.MusicIsFolder=folder;musicPath.Text=path;musicInfo.Text="正在读取…";musicRecursive.Enabled=folder;musicSelection=null;tracks.Items.Clear();musicRevision++;if(playlistWanted)StopAudio();}
            Save();try{bool recursive=pictures?photoRecursive.Checked:musicRecursive.Checked;MediaSelection selection=await Task.Run(()=>MediaCatalog.Read(path,folder,recursive,pictures?MediaCatalog.Images:MediaCatalog.Music,token.Token));if(token.IsCancellationRequested||exiting)return;
                string info=(folder?"已选择文件夹":"已选择文件")+" · "+selection.Files.Length+(pictures?" 张图片":" 首音频")+(folder?(recursive?" · 包含子文件夹":" · 仅当前文件夹"):"");
                if(selection.UnavailableFolders>0)info+=" · "+selection.UnavailableFolders+" 个文件夹无权限";if(selection.SkippedLinks>0)info+=" · 跳过 "+selection.SkippedLinks+" 个目录链接";
                if(pictures){pictureSelection=selection;photoInfo.Text=info;Interlocked.Increment(ref pictureRevision);}
                else {musicSelection=selection;musicInfo.Text=info;musicIndex=Math.Max(0,Math.Min(saved.MusicIndex,Math.Max(0,selection.Files.Length-1)));foreach(string file in selection.Files)tracks.Items.Add(folder?file.Substring(selection.Source.TrimEnd(Path.DirectorySeparatorChar).Length+1):Path.GetFileName(file));if(tracks.Items.Count>0)tracks.SelectedIndex=musicIndex;}
                if(selection.Files.Length==0)ShowError(pictures?"此范围内没有支持的图片。":"此范围内没有 MP3 音频。");
            }catch(OperationCanceledException){}catch(Exception ex){if(!token.IsCancellationRequested&&!exiting){if(pictures)photoInfo.Text="读取失败";else musicInfo.Text="读取失败";ShowError(ex.Message);}}
            finally{if(!pictures&&musicScan==token)musicLoading=false;}
        }
        void CaptureLoop(){byte[] previousPixels=null;uint previousHash=0;bool hasPrevious=false;int revision=-1,index=0;PreparedFrame photoFrame=null;DateTime lastSend=DateTime.MinValue,lastPhoto=DateTime.MinValue;DesktopCapture desktop=null;
            using(var delay=new CaptureDelay())try{while(!exiting){var iteration=Stopwatch.StartNew();try{if(Ipc.ActiveSession!=session){delay.Wait(100);continue;}
                lock(captureGate){bool isDisplay=captureEnabled,isPhoto=!isDisplay&&photoEnabled;MediaSelection selected=pictureSelection;
                    int current=Volatile.Read(ref pictureRevision);if(current!=revision){revision=current;index=0;lastPhoto=DateTime.MinValue;photoFrame=null;hasPrevious=false;if(desktop!=null){desktop.Dispose();desktop=null;}}
                    byte[] pixels=null;
                    if(isDisplay){if(desktop==null)desktop=new DesktopCapture();pixels=desktop.Capture();}
                    else{if(desktop!=null){desktop.Dispose();desktop=null;}if(isPhoto&&selected!=null&&selected.Files.Length>0&&DateTime.UtcNow-lastPhoto>TimeSpan.FromSeconds(photoSeconds)){
                        using(Bitmap image=Pictures.Photo(selected.Files[index]))pixels=Pictures.Pixels(image);index=Playlist.Next(index,selected.Files.Length,1);lastPhoto=DateTime.UtcNow;}}
                    if(pixels!=null){uint hash=Hash32.Of(pixels);if(!hasPrevious||hash!=previousHash){PreparedFrame prepared=PreparedFrame.Prepare(pixels,nativeBlockBytes,nativeWholeFrames,isDisplay&&nativeSparseFrames&&hasPrevious?previousPixels:null,previousHash);
                        if(isPhoto)photoFrame=prepared;
                        Status accepted=Ipc.Parse<Status>(Ipc.Request(isPhoto?Commands.PreparedPhoto:Commands.PreparedDisplay,prepared.Serialize()));
                        Interlocked.Exchange(ref transferMicroseconds,(long)(accepted.NativeFrameMs*1000));previousHash=hash;previousPixels=pixels;hasPrevious=true;lastSend=DateTime.UtcNow;}}
                    if((isDisplay||isPhoto)&&DateTime.UtcNow-lastSend>TimeSpan.FromSeconds(1)){Status state=Ipc.Parse<Status>(Ipc.Request(Commands.KeepFrame));lastSend=DateTime.UtcNow;
                        if(hasPrevious&&state.LastFrameHash!=previousHash){hasPrevious=false;if(isPhoto&&photoFrame!=null)Ipc.Request(Commands.PreparedPhoto,photoFrame.Serialize());}}
                }
            }catch(Exception ex){SystemLog.Log("Capture: "+ex.Message);ShowError(ex.Message);hasPrevious=false;delay.Wait(100);}
                int effectiveFps=captureEnabled?Math.Min(targetFps,displayHz):targetFps;double interval=Math.Max(1000.0/effectiveFps,Interlocked.Read(ref transferMicroseconds)/1000.0*.9);if(!captureEnabled)interval=Math.Max(interval,100);
                delay.Wait(interval-iteration.Elapsed.TotalMilliseconds);
            }}finally{if(desktop!=null)desktop.Dispose();}
        }
        void SetVolume(){if(exiting)return;saved.Volume=volume.Value;Save();Interlocked.Increment(ref volumeRevision);Interlocked.Exchange(ref pendingVolume,volume.Value);if(deviceConnected)StartVolumeSender();}
        void StartVolumeSender(){if(!exiting&&deviceConnected&&Interlocked.CompareExchange(ref volumeSending,1,0)==0)Task.Run((Action)SendLatestVolume);}
        void SendLatestVolume(){try{
                while(!exiting&&deviceConnected){int value=Interlocked.Exchange(ref pendingVolume,-1);if(value<0)break;
                    SendText(Commands.Volume,value.ToString());Thread.Sleep(40);}
            }catch(Exception ex){Interlocked.Exchange(ref pendingVolume,-1);if(!exiting)ShowError(ex.Message);}
            finally{Interlocked.Exchange(ref volumeSending,0);if(!exiting&&deviceConnected&&Volatile.Read(ref pendingVolume)>=0)StartVolumeSender();}}
        void StopLoopback(){Loopback previous=loopback;loopback=null;if(previous!=null)previous.Dispose();}
        void SetAudioChoice(int choice){restoring=true;audioMode.SelectedIndex=choice;restoring=false;}
        void StartWindowsAudio(int requestedVolume){Loopback next=new Loopback();try{next.Start(bytes=>Ipc.Request(Commands.Pcm,bytes),()=>{SendText(Commands.Volume,requestedVolume.ToString());SendText(Commands.AudioMode,"windows");});loopback=next;}
            catch{next.Dispose();try{SendText(Commands.AudioMode,"off");}catch{}throw;}}
        void ChangeAudio(){int mode=audioMode.SelectedIndex,requestedVolume=volume.Value;playlistWanted=false;playingId=0;saved.AudioMode=mode==1?"windows":mode==2?"local":"off";saved.ResumeMusic=false;audioRecoveryPending=false;Save();
            if(!deviceConnected){recoveryPending=true;return;}Run(()=>{StopLoopback();SendText(Commands.AudioMode,"off");if(mode==1)StartWindowsAudio(requestedVolume);},()=>play.Text="播放",ex=>{if(mode==1)recoveryPending=true;});}
        Status PlayTrack(string path,int selectedRevision,int requestedVolume){FileInfo file=new FileInfo(path);if(!file.Exists)throw new FileNotFoundException("音频文件不存在",path);if(file.Length==0||file.Length>4*1024*1024)throw new InvalidDataException("当前固件支持单曲最大 4 MB："+Path.GetFileName(path));StopLoopback();
            if(path!=uploadedPath||file.Length!=uploadedLength||file.LastWriteTimeUtc.Ticks!=uploadedWrite){Ipc.Request(Commands.UploadAudio,File.ReadAllBytes(path));uploadedPath=path;uploadedLength=file.Length;uploadedWrite=file.LastWriteTimeUtc.Ticks;}
            if(selectedRevision!=musicRevision)throw new OperationCanceledException("所选音乐已改变");SendText(Commands.Volume,requestedVolume.ToString());return Ipc.Parse<Status>(Ipc.Request(Commands.PlayAudio));}
        void StartTrack(int index){if(musicSelection==null||musicSelection.Files.Length==0){ShowError("请先选择音频文件或音乐文件夹。");return;}if(index<0||index>=musicSelection.Files.Length)return;
            if(busy){ShowError("正在执行设备操作，请稍候。");return;}string path=musicSelection.Files[index];int selectedRevision=musicRevision,requestedVolume=volume.Value;Status started=null;SetAudioChoice(2);musicIndex=index;tracks.SelectedIndex=index;playlistWanted=false;
            saved.AudioMode="local";saved.ResumeMusic=true;saved.MusicIndex=index;Save();if(!deviceConnected){recoveryPending=true;return;}
            Run(()=>{started=PlayTrack(path,selectedRevision,requestedVolume);},
                ()=>{playingId=started.AudioTrackId;playlistWanted=true;play.Text="重新播放";musicInfo.Text="播放 "+(musicIndex+1)+" / "+musicSelection.Files.Length+" · "+Path.GetFileName(path);tips.SetToolTip(musicInfo,path);});
        }
        void SkipTrack(int direction){if(musicSelection==null||musicSelection.Files.Length==0){ShowError("请先选择音频文件或音乐文件夹。");return;}int next=Playlist.Next(Math.Max(0,tracks.SelectedIndex),musicSelection.Files.Length,direction);if(playlistWanted)StartTrack(next);else tracks.SelectedIndex=next;}
        void StopAudio(){playlistWanted=false;playingId=0;saved.ResumeMusic=false;audioRecoveryPending=false;saved.AudioMode=audioMode.SelectedIndex==2?"local":"off";if(saved.AudioMode=="off")SetAudioChoice(0);Save();
            if(!deviceConnected){play.Text="播放";return;}Run(()=>{StopLoopback();Ipc.Request(Commands.StopAudio);},()=>{play.Text="播放";audioStatus.Text="音量 "+volume.Value+"% · 已停止";});}
        public async void ExitApp(){if(exiting)return;exiting=true;poll.Stop();captureEnabled=photoEnabled=false;playlistWanted=false;if(photoScan!=null)photoScan.Cancel();if(musicScan!=null)musicScan.Cancel();
            await Task.Run(()=>{StopLoopback();try{Ipc.Request(Commands.Exit);}catch{}try{if(Ipc.ActiveSession==session)Displays.Detach();}catch{}});tray.Visible=false;tray.Dispose();Close();Application.Exit();}
        protected override void Dispose(bool disposing){if(disposing){poll.Dispose();tips.Dispose();}base.Dispose(disposing);}
    }
}
