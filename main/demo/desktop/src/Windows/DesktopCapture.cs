using System;
using System.Drawing;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;
using QDisplay.Core;
namespace QDisplay.Windows {
    // Same top-down BGRX DIB/BitBlt path as the previously verified native host.
    // Reuse the DIB; flush GDI before reading it and pack pixels in one pass.
    public sealed class DesktopCapture : IDisposable {
        readonly Rectangle bounds;IntPtr screen,memory,bitmap,previous,bits;
        [StructLayout(LayoutKind.Sequential)]struct Header {public uint Size;public int Width,Height;public ushort Planes,Bits;public uint Compression,ImageSize;public int X,Y;public uint Used,Important;}
        [StructLayout(LayoutKind.Sequential)]struct Cursor {public int Size,Flags;public IntPtr Handle;public int X,Y;}
        [StructLayout(LayoutKind.Sequential)]struct IconInfo {public int Icon;public uint HotX,HotY;public IntPtr Mask,Color;}
        [DllImport("user32.dll")]static extern IntPtr GetDC(IntPtr window);
        [DllImport("user32.dll")]static extern int ReleaseDC(IntPtr window,IntPtr dc);
        [DllImport("user32.dll")]static extern IntPtr SetThreadDpiAwarenessContext(IntPtr value);
        [DllImport("user32.dll")]static extern bool GetCursorInfo(ref Cursor cursor);
        [DllImport("user32.dll")]static extern bool GetIconInfo(IntPtr icon,out IconInfo info);
        [DllImport("user32.dll")]static extern bool DrawIconEx(IntPtr dc,int x,int y,IntPtr icon,int width,int height,uint step,IntPtr brush,uint flags);
        [DllImport("gdi32.dll")]static extern IntPtr CreateCompatibleDC(IntPtr dc);
        [DllImport("gdi32.dll")]static extern IntPtr CreateDIBSection(IntPtr dc,ref Header info,uint usage,out IntPtr pixels,IntPtr section,uint offset);
        [DllImport("gdi32.dll")]static extern IntPtr SelectObject(IntPtr dc,IntPtr value);
        [DllImport("gdi32.dll")]static extern bool DeleteObject(IntPtr value);
        [DllImport("gdi32.dll")]static extern bool DeleteDC(IntPtr dc);
        [DllImport("gdi32.dll")]static extern bool BitBlt(IntPtr dest,int x,int y,int width,int height,IntPtr source,int sx,int sy,uint operation);
        [DllImport("gdi32.dll")]static extern bool GdiFlush();
        public DesktopCapture(){IntPtr dpi=SetThreadDpiAwarenessContext(new IntPtr(-4));try{bounds=Displays.Bounds();screen=GetDC(IntPtr.Zero);memory=CreateCompatibleDC(screen);
            Header header=new Header{Size=(uint)Marshal.SizeOf(typeof(Header)),Width=800,Height=-1280,Planes=1,Bits=32};bitmap=CreateDIBSection(screen,ref header,0,out bits,IntPtr.Zero,0);
            if(screen==IntPtr.Zero||memory==IntPtr.Zero||bitmap==IntPtr.Zero||bits==IntPtr.Zero)throw new IOException("无法创建桌面采集缓冲区");previous=SelectObject(memory,bitmap);
        }catch{Dispose();throw;}finally{if(dpi!=IntPtr.Zero)SetThreadDpiAwarenessContext(dpi);}}
        public unsafe byte[] Capture(){IntPtr dpi=SetThreadDpiAwarenessContext(new IntPtr(-4));try{
            if(!BitBlt(memory,0,0,800,1280,screen,bounds.X,bounds.Y,0x40CC0020))throw new IOException("桌面采集失败");
            Cursor cursor=new Cursor{Size=Marshal.SizeOf(typeof(Cursor))};IconInfo info;
            if(GetCursorInfo(ref cursor)&&(cursor.Flags&1)!=0&&bounds.Contains(cursor.X,cursor.Y)&&GetIconInfo(cursor.Handle,out info)){
                try{DrawIconEx(memory,cursor.X-bounds.X-(int)info.HotX,cursor.Y-bounds.Y-(int)info.HotY,cursor.Handle,0,0,0,IntPtr.Zero,3);}finally{if(info.Mask!=IntPtr.Zero)DeleteObject(info.Mask);if(info.Color!=IntPtr.Zero)DeleteObject(info.Color);}}
            if(!GdiFlush())throw new IOException("桌面采集未完成");
            byte[] pixels=new byte[NativeLink.FrameBytes];uint* source=(uint*)bits.ToPointer();fixed(byte* output=pixels){ushort* target=(ushort*)output;
                for(int i=0;i<800*1280;i++){uint p=source[i];target[i]=(ushort)(((p&0x00f80000)>>19)|((p&0x0000fc00)>>5)|((p&0x000000f8)<<8));}}
            return pixels;
        }finally{if(dpi!=IntPtr.Zero)SetThreadDpiAwarenessContext(dpi);}}
        public void Dispose(){if(previous!=IntPtr.Zero&&memory!=IntPtr.Zero)SelectObject(memory,previous);if(bitmap!=IntPtr.Zero)DeleteObject(bitmap);if(memory!=IntPtr.Zero)DeleteDC(memory);if(screen!=IntPtr.Zero)ReleaseDC(IntPtr.Zero,screen);previous=bitmap=memory=screen=bits=IntPtr.Zero;}
    }
    public sealed class CaptureDelay : IDisposable {
        IntPtr timer;
        [DllImport("kernel32.dll",CharSet=CharSet.Unicode)]static extern IntPtr CreateWaitableTimerEx(IntPtr attributes,string name,uint flags,uint access);
        [DllImport("kernel32.dll")]static extern bool SetWaitableTimer(IntPtr handle,ref long due,int period,IntPtr completion,IntPtr argument,bool resume);
        [DllImport("kernel32.dll")]static extern uint WaitForSingleObject(IntPtr handle,uint milliseconds);
        [DllImport("kernel32.dll")]static extern bool CloseHandle(IntPtr handle);
        public CaptureDelay(){timer=CreateWaitableTimerEx(IntPtr.Zero,null,2,0x00100002);if(timer==IntPtr.Zero)timer=CreateWaitableTimerEx(IntPtr.Zero,null,0,0x00100002);}
        public void Wait(double milliseconds){if(milliseconds<=0)return;milliseconds=Math.Min(milliseconds,100);long due=-(long)(milliseconds*10000);
            if(timer!=IntPtr.Zero&&SetWaitableTimer(timer,ref due,0,IntPtr.Zero,IntPtr.Zero,false))WaitForSingleObject(timer,200);else Thread.Sleep(Math.Max(1,(int)milliseconds));}
        public void Dispose(){if(timer!=IntPtr.Zero)CloseHandle(timer);timer=IntPtr.Zero;}
    }
}
