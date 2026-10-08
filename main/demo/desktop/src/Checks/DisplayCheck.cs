using System;
using System.IO;
using System.Linq;
using QDisplay.Windows;
public static class DisplayCheck {
    [STAThread]public static int Main(string[] args){var before=Displays.List();try{Displays.Attach();var attached=Displays.List();
            if(!attached.Any(d=>d.Virtual&&d.Attached&&d.Bounds.Width==800&&d.Bounds.Height==1280))throw new Exception("virtual display not attached");
            Displays.Detach();var after=Displays.List();if(after.Any(d=>d.Virtual&&d.Attached))throw new Exception("virtual display not detached");
            foreach(var original in before.Where(d=>d.Attached&&!d.Virtual)){var current=after.Single(d=>d.Name==original.Name);if(current.Primary!=original.Primary||current.Bounds!=original.Bounds||current.Hz!=original.Hz)throw new Exception("physical display changed");}
            File.WriteAllBytes(args[0],Ipc.Json(new{success=true,before=before,attached=attached,after=after,physical_displays_unchanged=true}));return 0;
        }catch(Exception ex){File.WriteAllBytes(args[0],Ipc.Json(new{success=false,error=ex.ToString(),before=before}));return 1;}
        finally{try{Displays.Detach();}catch{}}
    }
}
