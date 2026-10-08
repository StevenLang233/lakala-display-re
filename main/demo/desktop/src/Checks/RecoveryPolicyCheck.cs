using System;
using System.IO;
using QDisplay.Core;

public static class RecoveryPolicyCheck {
    static int cases;
    static void Check(bool result,string name){cases++;if(!result)throw new Exception(name);}
    public static int Main(string[] args){try{
        Status state=new Status{Connected=true,Session=1,UiSession=1,Mode="display",ServiceInstance="service-a",ConnectionGeneration=7};
        Check(!RecoveryPolicy.Needed(state,1,"service-a",7,"display",false),"stable connection must not restart capture or audio");
        Check(RecoveryPolicy.Needed(state,1,"",-1,"display",true),"startup applies saved mode");
        Check(RecoveryPolicy.Needed(state,1,"service-a",6,"display",false),"fast reconnect missed between polls still recovers");
        Check(RecoveryPolicy.Needed(state,1,"service-b",7,"display",false),"service restart recovers even with equal generation");
        state.Connected=false;Check(!RecoveryPolicy.Needed(state,1,"service-a",6,"display",true),"offline must wait");
        state.Connected=true;state.Session=-1;Check(!RecoveryPolicy.Needed(state,1,"",-1,"display",true),"locked session must wait");
        state.Session=2;Check(!RecoveryPolicy.Needed(state,1,"",-1,"display",true),"inactive account cannot take over");
        state.Session=1;state.UiSession=-1;Check(RecoveryPolicy.Needed(state,1,"service-a",7,"display",false),"unlock reclaims frame ownership");
        state.UiSession=1;state.Mode="hardware";Check(RecoveryPolicy.Needed(state,1,"service-a",7,"photo",false),"fallback does not erase photo intent");
        state.Mode="photo";Check(!RecoveryPolicy.Needed(state,1,"service-a",7,"photo",false),"stable photo mode stays running");
        state.Mode="hardware";Check(!RecoveryPolicy.Needed(state,1,"service-a",7,"hardware",false),"stable hardware mode stays running");
        Check(RecoveryPolicy.Volume(-1)==0&&RecoveryPolicy.Volume(101)==100&&RecoveryPolicy.Volume(10)==10,"saved volume validation");
        Check(RecoveryPolicy.Mode(null)=="hardware"&&RecoveryPolicy.Audio(null)=="off","invalid saved choices default safely");
        File.WriteAllText(args[0],"{\"success\":true,\"cases\":"+cases+"}");return 0;
    }catch(Exception ex){File.WriteAllText(args[0],ex.ToString());return 1;}}
}
