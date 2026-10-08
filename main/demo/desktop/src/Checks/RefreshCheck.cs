using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using QDisplay.Windows;
public static class RefreshCheck {
    static void VerifyPhysical(List<Displays.Entry> before,List<Displays.Entry> after){foreach(var original in before.Where(d=>d.Attached&&!d.Virtual)){
        var current=after.Single(d=>d.Name==original.Name);if(current.Primary!=original.Primary||current.Bounds!=original.Bounds||current.Hz!=original.Hz)throw new Exception("physical display changed");}}
    public static int Main(string[] args){var before=Displays.List();var steps=new List<object>();try{
        foreach(int hz in new[]{30,60,30}){Displays.Attach(hz);var displays=Displays.List();var target=displays.Single(d=>d.Virtual);
            if(!target.Attached||target.Bounds.Width!=800||target.Bounds.Height!=1280||target.Hz!=(uint)hz)throw new Exception("requested refresh not applied");
            VerifyPhysical(before,displays);steps.Add(new{requested_hz=hz,displays=displays});}
        Displays.Detach();var detached=Displays.List();if(detached.Any(d=>d.Virtual&&d.Attached))throw new Exception("detach failed");VerifyPhysical(before,detached);
        Displays.Attach(30);var final=Displays.List();VerifyPhysical(before,final);if(final.Single(d=>d.Virtual).Hz!=30)throw new Exception("30 Hz not restored after detach");
        File.WriteAllBytes(args[0],Ipc.Json(new{success=true,before=before,steps=steps,detached=detached,final=final,physical_displays_unchanged=true}));return 0;
    }catch(Exception ex){File.WriteAllBytes(args[0],Ipc.Json(new{success=false,error=ex.ToString(),before=before,steps=steps}));return 1;}
    }
}
