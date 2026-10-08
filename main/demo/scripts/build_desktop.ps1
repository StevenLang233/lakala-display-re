param([string]$OutputDirectory='build\windows')
$ErrorActionPreference='Stop'
$project=Split-Path $PSScriptRoot -Parent
& (Join-Path $PSScriptRoot 'restore_desktop_dependencies.ps1')
$destination=Join-Path $project $OutputDirectory
New-Item -ItemType Directory -Path $destination -Force | Out-Null
Add-Type -AssemblyName System.Drawing
$bitmap=New-Object Drawing.Bitmap 128,128
$graphics=[Drawing.Graphics]::FromImage($bitmap)
$graphics.SmoothingMode=[Drawing.Drawing2D.SmoothingMode]::AntiAlias
$graphics.Clear([Drawing.Color]::Transparent)
$brush=New-Object Drawing.SolidBrush ([Drawing.Color]::FromArgb(18,28,43))
$pen=New-Object Drawing.Pen ([Drawing.Color]::FromArgb(66,211,214)),8
$graphics.FillEllipse($brush,2,2,124,124)
$graphics.DrawRectangle($pen,25,30,78,57)
$graphics.DrawLine($pen,64,91,64,101)
$graphics.DrawLine($pen,45,103,83,103)
$graphics.DrawLine($pen,86,76,104,94)
$icon=[Drawing.Icon]::FromHandle($bitmap.GetHicon())
$file=[IO.File]::Create((Join-Path $destination 'QDisplay.ico'))
try {$icon.Save($file)} finally {$file.Dispose();$icon.Dispose();$graphics.Dispose();$bitmap.Dispose();$brush.Dispose();$pen.Dispose()}
$compiler=Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$sourceRoot=Join-Path $project 'desktop\src'
$info=Join-Path $sourceRoot 'AssemblyInfo.cs'
$packages=Join-Path $project 'dependencies\desktop'
foreach($dependency in @('K4os.Compression.LZ4.dll','System.Memory.dll','System.Buffers.dll','System.Runtime.CompilerServices.Unsafe.dll','System.Numerics.Vectors.dll')){Copy-Item -LiteralPath (Join-Path $packages $dependency) -Destination $destination -Force}
& python (Join-Path $PSScriptRoot 'prepare_license_bundle.py') --notice-output (Join-Path $destination 'THIRD-PARTY-NOTICES.txt') | Out-Null
if($LASTEXITCODE -ne 0){throw 'License bundle generation failed'}
$core=Join-Path $destination 'QDisplay.Core.dll'
& $compiler /nologo /target:library /optimize+ /unsafe+ "/out:$core" "/r:$(Join-Path $destination 'K4os.Compression.LZ4.dll')" "/r:$(Join-Path $destination 'System.Memory.dll')" $info (Join-Path $sourceRoot 'Core\Models.cs') (Join-Path $sourceRoot 'Core\Protocol.cs') (Join-Path $sourceRoot 'Core\Media.cs') (Join-Path $sourceRoot 'Core\SparseFrame.cs')
if($LASTEXITCODE -ne 0){throw 'Core compilation failed'}
$windows=Join-Path $destination 'QDisplay.Windows.dll'
& $compiler /nologo /target:library /optimize+ /unsafe+ "/out:$windows" "/r:$core" /r:System.Drawing.dll /r:System.Web.Extensions.dll $info (Join-Path $sourceRoot 'Windows\Ipc.cs') (Join-Path $sourceRoot 'Windows\Displays.cs') (Join-Path $sourceRoot 'Windows\Graphics.cs') (Join-Path $sourceRoot 'Windows\Loopback.cs') (Join-Path $sourceRoot 'Windows\SystemLog.cs') (Join-Path $sourceRoot 'Windows\FolderPicker.cs') (Join-Path $sourceRoot 'Windows\DesktopCapture.cs')
if($LASTEXITCODE -ne 0){throw 'Windows adapter compilation failed'}
$binary=Join-Path $destination 'QDisplay.exe'
& $compiler /nologo /target:winexe /platform:anycpu /optimize+ "/out:$binary" "/win32icon:$(Join-Path $destination 'QDisplay.ico')" "/r:$core" "/r:$windows" /r:System.Drawing.dll /r:System.Windows.Forms.dll $info (Join-Path $sourceRoot 'Program.cs') (Join-Path $sourceRoot 'Windows\MainWindow.cs')
if($LASTEXITCODE -ne 0){throw 'Desktop compilation failed'}
$service=Join-Path $destination 'QDisplay.Service.exe'
& $compiler /nologo /target:winexe /platform:anycpu /optimize+ "/out:$service" "/r:$core" "/r:$windows" /r:System.Drawing.dll /r:System.ServiceProcess.dll $info (Join-Path $sourceRoot 'ServiceProgram.cs') (Join-Path $sourceRoot 'Windows\Backend.cs')
if($LASTEXITCODE -ne 0){throw 'Service compilation failed'}
[IO.File]::WriteAllText(($binary+'.config'),'<configuration><startup><supportedRuntime version="v4.0" sku=".NETFramework,Version=v4.8" /></startup></configuration>')
[IO.File]::WriteAllText(($service+'.config'),'<configuration><startup><supportedRuntime version="v4.0" sku=".NETFramework,Version=v4.8" /></startup></configuration>')
[ordered]@{language='C#';runtime='.NET Framework 4.8';exe=$binary;sha256=(Get-FileHash -LiteralPath $binary -Algorithm SHA256).Hash.ToLower();service=$service;service_sha256=(Get-FileHash -LiteralPath $service -Algorithm SHA256).Hash.ToLower();built_at=[DateTime]::UtcNow.ToString('o');installer='standard MSI, no program self-install';device_tested=$false} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $destination 'manifest.json') -Encoding utf8
Write-Output $binary
