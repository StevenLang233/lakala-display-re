using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Threading;
namespace QDisplay.Windows {
    // WASAPI belongs to the active desktop session, never Session 0.
    public sealed class Loopback : IDisposable {
        [ComImport,Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")]class EnumeratorClass{}
        [ComImport,Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"),InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]interface Enumerator {
            int EnumEndpoints(int flow,int state,out IntPtr devices);[PreserveSig]int DefaultEndpoint(int flow,int role,out Device device);int GetDevice(string id,out Device device);int Register(IntPtr cb);int Unregister(IntPtr cb);
        }
        [ComImport,Guid("D666063F-1587-4E43-81F1-B948E807363F"),InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]interface Device {
            [PreserveSig]int Activate(ref Guid iid,uint context,IntPtr param,[MarshalAs(UnmanagedType.IUnknown)]out object result);
            [PreserveSig]int Properties(int access,out IntPtr props);[PreserveSig]int Id(out IntPtr id);[PreserveSig]int State(out int state);
        }
        [ComImport,Guid("1CB9AD4C-DBFA-4C32-B178-C2F568A703B2"),InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]interface AudioClient {
            [PreserveSig]int Initialize(int mode,uint flags,long buffer,long period,IntPtr format,IntPtr session);
            [PreserveSig]int BufferSize(out uint size);[PreserveSig]int Latency(out long latency);[PreserveSig]int Padding(out uint padding);
            [PreserveSig]int Supported(int mode,IntPtr format,out IntPtr closest);[PreserveSig]int MixFormat(out IntPtr format);[PreserveSig]int Period(out long def,out long min);
            [PreserveSig]int Start();[PreserveSig]int Stop();[PreserveSig]int Reset();[PreserveSig]int Event(IntPtr handle);
            [PreserveSig]int Service(ref Guid iid,[MarshalAs(UnmanagedType.IUnknown)]out object result);
        }
        [ComImport,Guid("C8ADBD64-E71E-48A0-A4DE-185C395CD317"),InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]interface CaptureClient {
            [PreserveSig]int Buffer(out IntPtr data,out uint frames,out uint flags,out ulong position,out ulong clock);
            [PreserveSig]int Release(uint frames);[PreserveSig]int Next(out uint frames);
        }
        volatile bool stopped;Thread capture,sender;readonly Queue<byte[]> queue=new Queue<byte[]>();readonly object gate=new object();readonly AutoResetEvent wake=new AutoResetEvent(false);
        readonly ManualResetEvent ready=new ManualResetEvent(false);public string LastError="",InputFormat="";public int CapturedBlocks;
        public Action<string> Trace;Action beginStream;
        void Step(string text){if(Trace!=null)Trace(text);}
        public void Start(Action<byte[]> send,Action begin=null){if(capture!=null)throw new InvalidOperationException("音频采集已经启动");beginStream=begin;sender=new Thread(()=>{while(!stopped){byte[] b=null;lock(gate){if(queue.Count>0)b=queue.Dequeue();}if(b==null){wake.WaitOne(100);continue;}try{send(b);}catch(Exception ex){LastError=ex.Message;SystemLog.Log("Audio send: "+ex.Message);stopped=true;}}}){IsBackground=true,Name="USB audio feed"};
            capture=new Thread(Capture){IsBackground=true,Name="WASAPI loopback"};capture.SetApartmentState(ApartmentState.STA);sender.Start();capture.Start();
            if(!ready.WaitOne(15000)){Dispose();throw new TimeoutException("电脑音频初始化超时");}if(LastError.Length>0){Dispose();throw new InvalidOperationException(LastError);}}
        static void Check(int result){if(result<0)throw new COMException(result==unchecked((int)0x800706CC)?"Windows 音频服务返回终结点重复错误（0x800706CC）":"WASAPI HRESULT 0x"+result.ToString("X8"),result);}
        void QueueBlock(byte[] block){Interlocked.Increment(ref CapturedBlocks);lock(gate){while(queue.Count>=5)queue.Dequeue();queue.Enqueue(block);}wake.Set();}
        void Capture(){Enumerator en=null;Device device=null;AudioClient client=null;CaptureClient reader=null;IntPtr format=IntPtr.Zero;
            try{Step("capture thread entered");en=(Enumerator)new EnumeratorClass();Step("enumerator created");Check(en.DefaultEndpoint(0,0,out device));IntPtr endpointId;Check(device.Id(out endpointId));try{Step("endpoint selected: "+Marshal.PtrToStringUni(endpointId));}finally{Marshal.FreeCoTaskMem(endpointId);}Guid iid=typeof(AudioClient).GUID;object raw;Check(device.Activate(ref iid,1,IntPtr.Zero,out raw));client=(AudioClient)raw;Step("audio client activated");
                Check(client.MixFormat(out format));int tag=Marshal.ReadInt16(format,0)&65535,channels=Marshal.ReadInt16(format,2),sampleRate=Marshal.ReadInt32(format,4),align=Marshal.ReadInt16(format,12),bits=Marshal.ReadInt16(format,14);
                if(tag==65534)tag=Marshal.ReadInt32(format,24);if(channels<1||channels>16||sampleRate<8000||sampleRate>192000||(tag!=1&&tag!=3)||!new[]{16,24,32}.Contains(bits)||(tag==3&&bits!=32)||align<channels*(bits/8))throw new NotSupportedException("不支持当前音频格式");
                InputFormat=sampleRate+" Hz / "+channels+" ch / "+bits+" bit / tag "+tag;Step("mix format read: "+InputFormat);Check(client.Initialize(0,0x20000,0,0,format,IntPtr.Zero));Step("initialized loopback");iid=typeof(CaptureClient).GUID;Check(client.Service(ref iid,out raw));reader=(CaptureClient)raw;Check(client.Start());Step("started loopback");
                if(stopped)return;if(beginStream!=null)beginStream();Step("device stream ready");InputFormat=sampleRate+" Hz / "+channels+" ch / "+bits+" bit";ready.Set();SystemLog.Log("WASAPI "+InputFormat+" -> 16000 mono PCM");
                byte[] block=new byte[3200];int fill=0,phase=0;double sum=0;int summed=0;DateTime lastBlock=DateTime.UtcNow;
                while(!stopped){uint packets;Check(reader.Next(out packets));if(packets==0){if(DateTime.UtcNow-lastBlock>TimeSpan.FromMilliseconds(100)){QueueBlock(block);block=new byte[3200];fill=phase=summed=0;sum=0;lastBlock=DateTime.UtcNow;}Thread.Sleep(5);continue;}
                    IntPtr data;uint frames,flags;ulong position,clock;Check(reader.Buffer(out data,out frames,out flags,out position,out clock));
                    try{byte[] b=new byte[(int)frames*align];if((flags&2)==0)Marshal.Copy(data,b,0,b.Length);
                        for(int f=0;f<frames;f++){double value=0;for(int c=0;c<channels;c++){int offset=f*align+c*(bits/8);
                            if(tag==3)value+=BitConverter.ToSingle(b,offset);
                            else if(bits==16)value+=BitConverter.ToInt16(b,offset)/32768.0;
                            else if(bits==24){int v=b[offset]|b[offset+1]<<8|b[offset+2]<<16;if((v&0x800000)!=0)v|=unchecked((int)0xff000000);value+=v/8388608.0;}
                            else value+=BitConverter.ToInt32(b,offset)/2147483648.0;
                        }sum+=value/channels;summed++;phase+=16000;if(phase>=sampleRate){double sample=sum/summed;sum=0;summed=0;if(Double.IsNaN(sample)||Double.IsInfinity(sample))sample=0;
                            short v=(short)Math.Max(-32768,Math.Min(32767,sample*32767));while(phase>=sampleRate){phase-=sampleRate;block[fill++]=(byte)v;block[fill++]=(byte)(v>>8);
                            if(fill==block.Length){QueueBlock(block);block=new byte[3200];fill=0;lastBlock=DateTime.UtcNow;}}
                        }}
                    }finally{Check(reader.Release(frames));}
                }
            }catch(Exception ex){LastError=ex.Message;SystemLog.Log("WASAPI: "+ex);stopped=true;}
            finally{ready.Set();if(client!=null)client.Stop();if(format!=IntPtr.Zero)Marshal.FreeCoTaskMem(format);foreach(object o in new object[]{reader,client,device,en})if(o!=null)Marshal.ReleaseComObject(o);}
        }
        public void Dispose(){stopped=true;wake.Set();if(capture!=null)capture.Join(2000);if(sender!=null)sender.Join(2000);}
    }
    static class ArrayContains {public static bool Contains(this int[] values,int n){foreach(int v in values)if(v==n)return true;return false;}}
}
