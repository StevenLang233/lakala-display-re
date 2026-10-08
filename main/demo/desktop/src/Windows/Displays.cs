using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using System.Runtime.InteropServices;
namespace QDisplay.Windows {
    public static class Displays {
        [StructLayout(LayoutKind.Sequential,CharSet=CharSet.Unicode)]struct Device {
            public uint cb;[MarshalAs(UnmanagedType.ByValTStr,SizeConst=32)]public string Name;
            [MarshalAs(UnmanagedType.ByValTStr,SizeConst=128)]public string Description;public uint Flags;
            [MarshalAs(UnmanagedType.ByValTStr,SizeConst=128)]public string Id;
            [MarshalAs(UnmanagedType.ByValTStr,SizeConst=128)]public string Key;
        }
        [StructLayout(LayoutKind.Sequential,CharSet=CharSet.Unicode)]struct Mode {
            [MarshalAs(UnmanagedType.ByValTStr,SizeConst=32)]public string Name;
            public ushort Spec,Driver,Size,Extra;public uint Fields;public int X,Y;public uint Orientation,Fixed;
            public short Color,Duplex,YRes,TT,Collate;[MarshalAs(UnmanagedType.ByValTStr,SizeConst=32)]public string Form;
            public ushort LogPixels;public uint Bpp,Width,Height,Flags,Hz,IcmMethod,IcmIntent,Media,Dither,Reserved1,Reserved2,PanW,PanH;
        }
        [DllImport("user32.dll",CharSet=CharSet.Unicode)]static extern bool EnumDisplayDevices(string name,uint index,ref Device d,uint flags);
        [DllImport("user32.dll",CharSet=CharSet.Unicode)]static extern bool EnumDisplaySettingsEx(string name,int index,ref Mode m,uint flags);
        [DllImport("user32.dll",CharSet=CharSet.Unicode)]static extern int ChangeDisplaySettingsEx(string name,ref Mode m,IntPtr window,uint flags,IntPtr param);
        [DllImport("user32.dll")]static extern int GetDisplayConfigBufferSizes(uint flags,out uint paths,out uint modes);
        [DllImport("user32.dll")]static extern int QueryDisplayConfig(uint flags,ref uint pc,IntPtr paths,ref uint mc,IntPtr modes,IntPtr topology);
        [DllImport("user32.dll")]static extern int SetDisplayConfig(uint pc,byte[] paths,uint mc,byte[] modes,uint flags);
        [DllImport("user32.dll")]static extern int DisplayConfigGetDeviceInfo(byte[] request);
        public sealed class Entry { public string Name,Id;public bool Virtual,Attached,Primary;public Rectangle Bounds;public uint Hz; }
        static Mode Current(string name){Mode m=new Mode{Size=(ushort)Marshal.SizeOf(typeof(Mode))};if(!EnumDisplaySettingsEx(name,-1,ref m,0))throw new InvalidOperationException("无法读取显示模式");return m;}
        public static List<Entry> List(){List<Entry> list=new List<Entry>();
            for(uint i=0;i<256;i++){Device d=new Device{cb=(uint)Marshal.SizeOf(typeof(Device))};if(!EnumDisplayDevices(null,i,ref d,0))break;
                Entry e=new Entry{Name=d.Name,Id=d.Id,Attached=(d.Flags&1)!=0,Primary=(d.Flags&4)!=0,
                    Virtual=d.Description=="Virtual Display Driver"&&(d.Id.ToUpperInvariant()=="ROOT\\MTTVDD"||d.Id.ToUpperInvariant().StartsWith("ROOT\\MTTVDD\\"))};
                try{Mode m=Current(d.Name);e.Bounds=new Rectangle(m.X,m.Y,(int)m.Width,(int)m.Height);e.Hz=m.Hz;}catch{}list.Add(e);
            }return list;
        }
        static Entry Target(List<Entry> list){Entry[] v=list.Where(e=>e.Virtual).ToArray();if(v.Length!=1)throw new InvalidOperationException("未找到唯一的 QDisplay 虚拟显示器");if(v[0].Primary)throw new InvalidOperationException("虚拟显示器不能设为主屏");return v[0];}
        static void Verify(List<Entry> before){List<Entry> after=List();foreach(Entry e in before.Where(e=>e.Attached&&!e.Virtual)){
            Entry n=after.Find(x=>x.Name==e.Name);if(n==null || e.Bounds!=n.Bounds || e.Hz!=n.Hz || e.Primary!=n.Primary)throw new InvalidOperationException("原显示器配置发生变化");}}
        public static Rectangle Bounds(){Entry e=Target(List());if(!e.Attached || e.Bounds.Width!=800 || e.Bounds.Height!=1280)throw new InvalidOperationException("副屏未启用");return e.Bounds;}
        public static void Detach(){List<Entry> before=List();if(!before.Any(item=>item.Virtual))return;Entry e=Target(before);if(!e.Attached)return;
            Mode m=Current(e.Name);m.X=m.Y=0;m.Width=m.Height=0;m.Fields=0x20|0x80000|0x100000;
            int rc=ChangeDisplaySettingsEx(e.Name,ref m,IntPtr.Zero,1,IntPtr.Zero);if(rc!=0)throw new InvalidOperationException("断开副屏失败："+rc);Verify(before);
        }
        public static void Attach(int frequency=30,Point? position=null){if(frequency!=30&&frequency!=60)throw new ArgumentOutOfRangeException("frequency");List<Entry> before=List();Entry target=Target(before);if(target.Attached&&target.Bounds.Size==new Size(800,1280)&&target.Hz==(uint)frequency&&(!position.HasValue||target.Bounds.Location==position.Value))return;
            Entry primary=before.Find(e=>e.Attached&&e.Primary&&!e.Virtual);if(primary==null)throw new InvalidOperationException("未找到主显示器");
            int x=target.Attached?target.Bounds.X:before.Where(e=>e.Attached&&!e.Virtual).Max(e=>e.Bounds.Right),y=target.Attached?target.Bounds.Y:primary.Bounds.Y;
            if(position.HasValue){x=position.Value.X;y=position.Value.Y;}
            Mode chosen=new Mode();bool found=false;
            for(int i=0;i<256;i++){Mode m=new Mode{Size=(ushort)Marshal.SizeOf(typeof(Mode))};if(!EnumDisplaySettingsEx(target.Name,i,ref m,0))break;
                if(m.Width==800&&m.Height==1280&&m.Hz==(uint)frequency){chosen=m;found=true;break;}}
            if(!found)throw new InvalidOperationException("驱动未提供 800×1280 @ "+frequency+" Hz 模式");
            chosen.X=x;chosen.Y=y;chosen.Orientation=0;chosen.Fields=0x20|0x80000|0x100000|0x40000|0x400000|0x80;
            int rc=ChangeDisplaySettingsEx(target.Name,ref chosen,IntPtr.Zero,2,IntPtr.Zero);
            if(rc!=0&&!target.Attached)AttachCcd(target.Name,x,y,frequency);
            else{if(rc!=0)throw new InvalidOperationException("显示模式测试失败："+rc);rc=ChangeDisplaySettingsEx(target.Name,ref chosen,IntPtr.Zero,1,IntPtr.Zero);if(rc!=0)throw new InvalidOperationException("启用副屏失败："+rc);}
            Verify(before);Bounds();if(Target(List()).Hz!=(uint)frequency)throw new InvalidOperationException("Windows 未应用所选刷新率");
        }
        static void Put(byte[] b,int offset,uint value){Buffer.BlockCopy(BitConverter.GetBytes(value),0,b,offset,4);}
        static string SourceName(byte[] path){byte[] request=new byte[84];Put(request,0,1);Put(request,4,84);Buffer.BlockCopy(path,0,request,8,12);
            return DisplayConfigGetDeviceInfo(request)==0?System.Text.Encoding.Unicode.GetString(request,20,64).TrimEnd('\0'):"";}
        static void AttachCcd(string name,int x,int y,int frequency){uint pc,mc;int rc=GetDisplayConfigBufferSizes(1,out pc,out mc);if(rc!=0)throw new InvalidOperationException("CCD 查询失败");
            IntPtr p=Marshal.AllocHGlobal((int)pc*72),m=Marshal.AllocHGlobal((int)mc*64);
            try{rc=QueryDisplayConfig(1,ref pc,p,ref mc,m,IntPtr.Zero);if(rc!=0)throw new InvalidOperationException("CCD 路径查询失败："+rc);
                List<byte[]> active=new List<byte[]>();byte[] target=null;bool ready=false;
                for(int i=0;i<pc;i++){byte[] path=new byte[72];Marshal.Copy(IntPtr.Add(p,i*72),path,0,72);string source=SourceName(path);
                    if(source==name&&BitConverter.ToUInt32(path,60)!=0){if(target==null || BitConverter.ToUInt32(path,68)!=0){target=path;ready=BitConverter.ToUInt32(path,68)!=0;}}
                    else if((BitConverter.ToUInt32(path,68)&1)!=0)active.Add(path);
                }
                if(target==null || active.Count==0)throw new InvalidOperationException("无可用虚拟显示路径");
                byte[] modes=new byte[((int)mc+1)*64];Marshal.Copy(m,modes,0,(int)mc*64);int off=(int)mc*64;
                Put(modes,off,1);Buffer.BlockCopy(target,8,modes,off+4,4);Buffer.BlockCopy(target,0,modes,off+8,8);
                Put(modes,off+16,800);Put(modes,off+20,1280);Put(modes,off+24,4);Put(modes,off+28,(uint)x);Put(modes,off+32,(uint)y);
                Put(target,12,mc);Put(target,32,uint.MaxValue);Put(target,40,1);Put(target,44,1);Put(target,48,(uint)frequency);Put(target,52,1);Put(target,56,1);Put(target,68,1);
                active.Add(target);byte[] paths=new byte[active.Count*72];for(int i=0;i<active.Count;i++)Buffer.BlockCopy(active[i],0,paths,i*72,72);
                rc=SetDisplayConfig((uint)active.Count,paths,mc+1,modes,0x20|0x40);if(rc!=0)throw new InvalidOperationException("CCD 配置验证失败："+rc);
                rc=SetDisplayConfig((uint)active.Count,paths,mc+1,modes,0x20|0x80|0x200);if(rc!=0)throw new InvalidOperationException("CCD 配置应用失败："+rc);
            }finally{Marshal.FreeHGlobal(p);Marshal.FreeHGlobal(m);}
        }
    }
}
