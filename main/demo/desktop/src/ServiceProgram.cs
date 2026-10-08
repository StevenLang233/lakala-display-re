using System;
using System.ServiceProcess;
using QDisplay.Windows;
namespace QDisplay {
    public static class ServiceProgram {
        public static int Main(){try{ServiceBase.Run(new DeviceService());return 0;}catch(Exception ex){SystemLog.Log(ex.ToString());return 1;}}
    }
}
