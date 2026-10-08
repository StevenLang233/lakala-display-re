using System;
using System.IO;
using System.Drawing;
using System.Windows.Forms;
using System.Runtime.InteropServices;
using QDisplay.Windows;
using QDisplay.Core;
class DisplayScenarioBench : Form {
    readonly Timer tick=new Timer();readonly Font title=new Font("Segoe UI",25),text=new Font("Segoe UI",18);readonly string folder,scene;Bitmap photo;int index;
    [DllImport("user32.dll")]static extern bool SetProcessDpiAwarenessContext(IntPtr context);
    [DllImport("user32.dll")]static extern bool SetWindowPos(IntPtr window,IntPtr after,int x,int y,int width,int height,uint flags);
    DisplayScenarioBench(string scene,string folder,string image){this.folder=folder;this.scene=scene;var area=Displays.Bounds();FormBorderStyle=FormBorderStyle.None;StartPosition=FormStartPosition.Manual;Bounds=area;TopMost=true;ShowInTaskbar=false;DoubleBuffered=true;
        if(scene=="photo")photo=Pictures.Photo(image);
        if(scene=="actual"||scene=="drag"){byte[] raw=File.ReadAllBytes(image);photo=new Bitmap(800,1280);var bits=photo.LockBits(new Rectangle(0,0,800,1280),System.Drawing.Imaging.ImageLockMode.WriteOnly,System.Drawing.Imaging.PixelFormat.Format32bppArgb);byte[] rgba=new byte[800*1280*4];
            for(int pixel=0;pixel<800*1280;pixel++){int v=raw[pixel*2]|raw[pixel*2+1]<<8;rgba[pixel*4]=(byte)(((v>>11)&31)*255/31);rgba[pixel*4+1]=(byte)(((v>>5)&63)*255/63);rgba[pixel*4+2]=(byte)((v&31)*255/31);rgba[pixel*4+3]=255;}
            Marshal.Copy(rgba,0,bits.Scan0,rgba.Length);photo.UnlockBits(bits);}
        tick.Interval=25;tick.Tick+=(s,e)=>{index++;Invalidate();};Shown+=(s,e)=>{Raise();File.WriteAllBytes(Path.Combine(folder,scene+".window.json"),Ipc.Json(new{bounds=Bounds,requested=Displays.Bounds(),displays=Displays.List()}));tick.Start();};}
    void Raise(){var area=Displays.Bounds();SetWindowPos(Handle,new IntPtr(-1),area.X,area.Y,800,1280,0x0010|0x0040);}
    protected override void OnPaint(PaintEventArgs e){Graphics g=e.Graphics;int i=index%24;g.Clear(Color.FromArgb(16+i*8,40+i*4,56+i*8));
        if(scene=="drag"){g.DrawImageUnscaled(photo,0,0);int x=40+(index%40)*6,y=160+(index%24)*8;g.FillRectangle(Brushes.White,x,y,320,400);g.FillRectangle(Brushes.SteelBlue,x,y,320,40);g.DrawString("Moving window "+index,text,Brushes.Black,x+12,y+60);}
        else if(photo!=null){int dy=index%8*80;g.DrawImageUnscaled(photo,0,dy);g.DrawImageUnscaled(photo,0,dy-1280);}
        else for(int row=0;row<12;row++){using(var brush=new SolidBrush(Color.FromArgb((index*13+row*19)%256,64+row*12,96+row*8)))g.FillRectangle(brush,24,140+row*85,752,77);g.DrawString((row+1).ToString("00")+" Windows extended desktop Native USB",text,Brushes.White,40,153+row*85);}
        g.FillRectangle(Brushes.Black,0,0,800,110);g.DrawString("QDisplay dynamic test "+index.ToString("0000"),title,Brushes.White,24,25);
    }
    void Freeze(){tick.Stop();Invalidate();Update();File.WriteAllText(Path.Combine(folder,scene+".static"),"ready");}
    void Finish(){using(var capture=new DesktopCapture()){File.WriteAllBytes(Path.Combine(folder,scene+".screen.raw"),capture.Capture());}Close();}
    [STAThread]static int Main(string[] args){SetProcessDpiAwarenessContext(new IntPtr(-4));Application.EnableVisualStyles();using(var form=new DisplayScenarioBench(args[0],args[1],args[2])){
        var phases=new Timer{Interval=100};var clock=System.Diagnostics.Stopwatch.StartNew();bool frozen=false;
        phases.Tick+=(s,e)=>{form.Raise();if(!frozen&&clock.Elapsed.TotalSeconds>=14){frozen=true;form.Freeze();}if(clock.Elapsed.TotalSeconds>=20){phases.Stop();form.Finish();}};phases.Start();Application.Run(form);phases.Dispose();}
        return 0;
    }
    protected override void Dispose(bool disposing){if(disposing){tick.Dispose();title.Dispose();text.Dispose();if(photo!=null)photo.Dispose();}base.Dispose(disposing);}
}
