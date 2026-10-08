using System;
using System.IO;
using System.Runtime.InteropServices;
namespace QDisplay.Windows {
    public static class FolderPicker {
        [ComImport,Guid("DC1C5A9C-E88A-4DDE-A5A1-60F82A20AEF7")]class DialogClass{}
        [ComImport,Guid("42F85136-DB7E-439C-85F1-E4075D135FC8"),InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]interface Dialog {
            [PreserveSig]int Show(IntPtr owner);
            void SetFileTypes(uint count,IntPtr filters);void SetFileTypeIndex(uint index);void GetFileTypeIndex(out uint index);void Advise(IntPtr callback,out uint cookie);void Unadvise(uint cookie);
            void SetOptions(uint flags);void GetOptions(out uint flags);void SetDefaultFolder(Item item);void SetFolder(Item item);void GetFolder(out Item item);void GetCurrentSelection(out Item item);
            void SetFileName([MarshalAs(UnmanagedType.LPWStr)]string name);void GetFileName(out IntPtr name);void SetTitle([MarshalAs(UnmanagedType.LPWStr)]string title);void SetOkButtonLabel([MarshalAs(UnmanagedType.LPWStr)]string title);void SetFileNameLabel([MarshalAs(UnmanagedType.LPWStr)]string title);
            void GetResult(out Item item);void AddPlace(Item item,int place);void SetDefaultExtension([MarshalAs(UnmanagedType.LPWStr)]string extension);void Close(int error);void SetClientGuid(ref Guid guid);void ClearClientData();void SetFilter(IntPtr filter);
        }
        [ComImport,Guid("43826D1E-E718-42EE-BC55-A1E261C37BFE"),InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]interface Item {
            void BindToHandler(IntPtr context,ref Guid handler,ref Guid iid,out IntPtr result);void GetParent(out Item parent);void GetDisplayName(uint type,out IntPtr text);void GetAttributes(uint mask,out uint attributes);void Compare(Item other,uint hint,out int order);
        }
        [DllImport("shell32.dll",CharSet=CharSet.Unicode,PreserveSig=true)]static extern int SHCreateItemFromParsingName(string path,IntPtr context,ref Guid iid,out Item item);
        public static string Choose(IntPtr owner,string title,string initial){Dialog dialog=(Dialog)new DialogClass();Item folder=null,result=null;
            try{uint options;dialog.GetOptions(out options);dialog.SetOptions(options|0x20|0x40|0x800|0x8);dialog.SetTitle(title);dialog.SetOkButtonLabel("选择文件夹");
                string directory=Directory.Exists(initial)?initial:File.Exists(initial)?Path.GetDirectoryName(initial):null;
                if(directory!=null){Guid iid=typeof(Item).GUID;if(SHCreateItemFromParsingName(directory,IntPtr.Zero,ref iid,out folder)>=0)dialog.SetFolder(folder);}
                int code=dialog.Show(owner);if(code==unchecked((int)0x800704C7))return null;if(code<0)Marshal.ThrowExceptionForHR(code);dialog.GetResult(out result);IntPtr path;result.GetDisplayName(0x80058000,out path);try{return Marshal.PtrToStringUni(path);}finally{Marshal.FreeCoTaskMem(path);}
            }finally{if(result!=null)Marshal.ReleaseComObject(result);if(folder!=null)Marshal.ReleaseComObject(folder);Marshal.ReleaseComObject(dialog);}
        }
    }
}
