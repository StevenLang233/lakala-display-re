using System.IO;
using QDisplay.Windows;
class CaptureSave {static void Main(string[] args){using(var capture=new DesktopCapture())File.WriteAllBytes(args[0],capture.Capture());}}
