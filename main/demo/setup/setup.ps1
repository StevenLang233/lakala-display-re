param([switch]$CheckOnly,[switch]$PrepareOnly,[switch]$Offline,[switch]$NoPrompt)
# Windows PowerShell 5.1 compatible. Saved with BOM so Chinese text survives.
$ErrorActionPreference='Stop'
Set-StrictMode -Version 2
$root=Split-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) -Parent
$cache=Join-Path $root '.qdisplay'
$run=Join-Path $cache ('logs\'+[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')+'-'+[Guid]::NewGuid().ToString('N').Substring(0,8))
$downloads=Join-Path $cache 'downloads'
$script:Result='failed';$script:Code=1;$script:ServiceStopped=$false;$script:Python=$null;$script:Reboot=$false
$script:Records=New-Object Collections.Generic.List[object]
$script:LogStarted=$false
$script:SetupLock=$null
function Say([string]$Message,[string]$Color='Cyan') {
    Write-Host ('['+[DateTime]::Now.ToString('HH:mm:ss')+'] '+$Message) -ForegroundColor $Color
    $script:Records.Add([ordered]@{time=[DateTime]::UtcNow.ToString('o');message=$Message})
}
function Ask([string]$Question) {
    if($NoPrompt){return $false}
    return (Read-Host ($Question+' [y/N]')) -match '^(y|yes|是)$'
}
function Check-Hash([string]$Path,[string]$Expected) {
    if(-not(Test-Path -LiteralPath $Path -PathType Leaf)){throw ('MISSING_FILE: '+$Path)}
    if((Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Expected){throw ('HASH_MISMATCH: '+[IO.Path]::GetFileName($Path)+' 校验失败，请重新下载锁定版本。')}
}
function Get-Dependency([string]$Key) {
    $item=$script:Lock.downloads.$Key
    $target=Join-Path $downloads $item.file
    if(Test-Path -LiteralPath $target){Check-Hash $target $item.sha256;Say ('已校验 '+$item.file);return $target}
    foreach($folder in @((Join-Path $root 'offline'),$root,(Join-Path $root 'main\demo\releases'))){
        $candidate=Join-Path $folder $item.file
        if(Test-Path -LiteralPath $candidate){Check-Hash $candidate $item.sha256;Copy-Item -LiteralPath $candidate -Destination $target;Say ('从本地取得 '+$item.file);return $target}
    }
    if($Offline){throw ('OFFLINE_MISSING: 缺少 '+$item.file+'。把原包放入项目的 offline 文件夹后重试。')}
    Say ('下载 '+$item.file)
    $partial=$target+'.partial'
    $response=$null;$inputStream=$null;$outputStream=$null
    try {
        [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
        $request=[Net.HttpWebRequest]::Create($item.url)
        $request.Timeout=30000;$request.ReadWriteTimeout=15000;$request.UserAgent='QDisplay-Setup/1.0'
        $response=$request.GetResponse();$inputStream=$response.GetResponseStream();$inputStream.ReadTimeout=15000
        $outputStream=[IO.File]::Open($partial,[IO.FileMode]::Create,[IO.FileAccess]::Write,[IO.FileShare]::None)
        $buffer=New-Object byte[] 65536;$received=0L;$last=[DateTime]::UtcNow
        while(($count=$inputStream.Read($buffer,0,$buffer.Length)) -gt 0){
            $outputStream.Write($buffer,0,$count);$received+=$count
            if(([DateTime]::UtcNow-$last).TotalMilliseconds -gt 500){
                $percent=if($response.ContentLength -gt 0){[Math]::Min(100,[int]($received*100/$response.ContentLength))}else{-1}
                Write-Progress -Activity ('下载 '+$item.file) -Status ($received.ToString('N0')+' 字节') -PercentComplete $percent
                $last=[DateTime]::UtcNow
            }
        }
        $outputStream.Flush();$outputStream.Dispose();$outputStream=$null
        Check-Hash $partial $item.sha256
        [IO.File]::Move($partial,$target)
        Say ('下载及 SHA-256 校验通过：'+$item.file)
        return $target
    } catch {
        if($Key -in @('app','host','licenses')){
            throw ('DOWNLOAD_FAILED: '+$item.file+' 未取得。仓库为私有时需在浏览器登录后下载 Release；也可直接下载 QDisplay-Setup 包，或把附件放入 offline 文件夹。'+$_.Exception.Message)
        }
        throw ('DOWNLOAD_FAILED: '+$item.file+'。检查网络，或把同名官方原包放入 offline 文件夹。'+$_.Exception.Message)
    } finally {
        if($outputStream){$outputStream.Dispose()};if($inputStream){$inputStream.Dispose()};if($response){$response.Dispose()}
        Write-Progress -Activity ('下载 '+$item.file) -Completed
    }
}
function Expand-SafeZip([string]$Archive,[string]$Destination) {
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip=[IO.Compression.ZipFile]::OpenRead($Archive)
    try {
        $prefix=[IO.Path]::GetFullPath($Destination).TrimEnd('\')+'\'
        foreach($entry in $zip.Entries){
            $path=[IO.Path]::GetFullPath((Join-Path $Destination $entry.FullName))
            if(-not $path.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase)){throw 'ZIP_PATH: 压缩包路径越界。'}
            if($entry.FullName.EndsWith('/')){New-Item -ItemType Directory -Path $path -Force | Out-Null;continue}
            New-Item -ItemType Directory -Path (Split-Path $path -Parent) -Force | Out-Null
            if(Test-Path -LiteralPath $path -PathType Leaf){
                $source=$entry.Open();$hasher=[Security.Cryptography.SHA256]::Create()
                try{$entryHash=[BitConverter]::ToString($hasher.ComputeHash($source)).Replace('-','').ToLowerInvariant()}finally{$source.Dispose();$hasher.Dispose()}
                if((Get-FileHash -LiteralPath $path).Hash.ToLowerInvariant() -eq $entryHash){continue}
            }
            [IO.Compression.ZipFileExtensions]::ExtractToFile($entry,$path,$true)
        }
    } finally {$zip.Dispose()}
}
function Run-Backend([string[]]$Arguments) {
    $info=New-Object Diagnostics.ProcessStartInfo
    $info.FileName=$script:Python
    # Windows filenames cannot contain a quote. Our arguments are flags or paths,
    # never shell source; shell execution is disabled.
    $parts=@((Join-Path $PSScriptRoot 'qflash.py'))+$Arguments
    $info.Arguments=($parts | ForEach-Object {'"'+$_.Replace('"','\"')+'"'}) -join ' '
    $info.UseShellExecute=$false;$info.CreateNoWindow=$true
    $info.RedirectStandardOutput=$true;$info.RedirectStandardError=$true
    $info.StandardOutputEncoding=New-Object Text.UTF8Encoding $false
    $info.StandardErrorEncoding=New-Object Text.UTF8Encoding $false
    $proc=New-Object Diagnostics.Process;$proc.StartInfo=$info
    $jsonPath=Join-Path $run ('backend-'+[Guid]::NewGuid().ToString('N')+'.jsonl')
    $raw=New-Object IO.StreamWriter($jsonPath,$false,(New-Object Text.UTF8Encoding $false))
    $lastEvent=[DateTime]::UtcNow;$lastHeartbeat=$lastEvent;$reply=$null;$errorMessage=$null;$processStarted=$false
    try {
        $null=$proc.Start();$processStarted=$true
        $stderr=$proc.StandardError.ReadToEndAsync()
        $line=$proc.StandardOutput.ReadLineAsync()
        while($true){
            if($line.IsCompleted){
                $value=$line.Result
                if($null -eq $value){break}
                $raw.WriteLine($value);$raw.Flush();$lastEvent=[DateTime]::UtcNow
                $row=$value | ConvertFrom-Json
                switch($row.event){
                    'progress' {Write-Progress -Activity $row.stage -Status ($row.percent.ToString()+'%  '+$row.done+'/'+$row.total+' 字节/秒数') -PercentComplete $row.percent}
                    'stage' {Say $row.stage}
                    'backup' {Say ('两遍备份一致，保存在 '+$row.path) 'Green'}
                    'recovery' {Say ($row.message+'  '+$row.backup) 'Yellow'}
                    'error' {$errorMessage=$row.code+': '+$row.message;Say $errorMessage 'Red'}
                    'result' {$reply=$row}
                }
                $line=$proc.StandardOutput.ReadLineAsync()
            } else {
                Start-Sleep -Milliseconds 100
                if(([DateTime]::UtcNow-$lastHeartbeat).TotalSeconds -ge 10){Say '后台仍在运行，等待设备响应。';$lastHeartbeat=[DateTime]::UtcNow}
                if(([DateTime]::UtcNow-$lastEvent).TotalSeconds -gt 180){
                    $proc.Kill();throw 'BACKEND_TIMEOUT: 180 秒没有进度。已停止后台；保留备份和下载状态，不强制重启设备。'
                }
            }
        }
        $proc.WaitForExit()
        [IO.File]::WriteAllText(($jsonPath+'.stderr.txt'),$stderr.Result,(New-Object Text.UTF8Encoding $false))
        if($proc.ExitCode -ne 0){if($errorMessage){throw $errorMessage};throw ('BACKEND_EXIT: '+$proc.ExitCode+'，详情见本次日志。')}
        if($null -eq $reply){throw 'BACKEND_NO_RESULT: 后台退出但没有结果，不能确认成功。'}
        return $reply
    } finally {
        Write-Progress -Activity '设备操作' -Completed
        if($processStarted -and -not $proc.HasExited){$proc.Kill()}
        $raw.Dispose();$proc.Dispose()
    }
}
function Admin([string]$Action,[string]$Package='') {
    $inputFile=Join-Path $run ('admin-'+[Guid]::NewGuid().ToString('N')+'.json')
    $output=$inputFile+'.result.json'
    $request=@{action=$Action;package=$Package;python=$script:Python;result=$output;log_directory=$run}
    [IO.File]::WriteAllText($inputFile,($request | ConvertTo-Json),(New-Object Text.UTF8Encoding $false))
    Say ('申请管理员权限：'+$Action)
    $elevatedArgs='-NoLogo -NoProfile -ExecutionPolicy Bypass -File "'+(Join-Path $PSScriptRoot 'admin.ps1')+'" -Request "'+$inputFile+'"'
    try {$proc=Start-Process -FilePath "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" -ArgumentList $elevatedArgs -Verb RunAs -WindowStyle Hidden -PassThru}
    catch {throw 'UAC_CANCELLED: 未取得管理员权限，本步骤未完成。'}
    $started=[DateTime]::UtcNow
    while(-not $proc.WaitForExit(1000)){
        Write-Progress -Activity ('系统设置：'+$Action) -Status ('等待完成，已用 '+[int]([DateTime]::UtcNow-$started).TotalSeconds+' 秒')
        if(([DateTime]::UtcNow-$started).TotalMinutes -gt 15){throw 'ADMIN_TIMEOUT: 系统安装超过 15 分钟。不要重复启动安装，先查看本次安装日志。'}
    }
    Write-Progress -Activity ('系统设置：'+$Action) -Completed
    if(-not(Test-Path -LiteralPath $output)){throw ('ADMIN_NO_RESULT: 管理员步骤未返回结果（退出码 '+$proc.ExitCode+'）。')}
    $answer=Get-Content -LiteralPath $output -Raw -Encoding UTF8 | ConvertFrom-Json
    if(-not $answer.success){throw ('ADMIN_FAILED: '+$answer.error)}
    if($answer.reboot_required){$script:Reboot=$true;Say '安装要求重启 Windows；不会自动重启，重启后重新打开入口。' 'Yellow'}
    return $answer
}
function Prepare-Python {
    $pythonZip=Get-Dependency 'python';$serialWheel=Get-Dependency 'serial'
    $runtime=Join-Path $cache 'python-3.13.16'
    # Re-extract the verified originals on every run, so a stale/truncated cache
    # cannot silently supply different executable code.
    Expand-SafeZip $pythonZip $runtime
    Expand-SafeZip $serialWheel (Join-Path $runtime 'packages')
    [IO.File]::WriteAllText((Join-Path $runtime 'python313._pth'),"python313.zip`r`n.`r`npackages`r`n",[Text.Encoding]::ASCII)
    $script:Python=Join-Path $runtime 'python.exe'
    $version=& $script:Python -c 'import sys,serial; print(sys.version.split()[0]); print(serial.VERSION)' 2>&1
    if($LASTEXITCODE -ne 0){throw ('PYTHON_FAILED: '+($version -join ' '))}
    Say ('独立刷写环境就绪：'+($version -join ' / '))
}
function Prepare-Usb {
    $package=Get-Dependency 'usb';$seven=Get-Dependency 'sevenzip';$isx=Get-Dependency 'isx'
    $isxDir=Join-Path $cache 'isx';New-Item -ItemType Directory -Path $isxDir -Force | Out-Null
    & $seven x $isx ('-o'+$isxDir) -y | Out-File -LiteralPath (Join-Path $run '7zr.log') -Encoding UTF8
    if($LASTEXITCODE -ne 0){throw 'ISX_EXTRACT: 解包工具准备失败。'}
    $exe=Join-Path $isxDir 'ISx.exe';Check-Hash $exe $script:Lock.isx_exe_sha256
    $installer=Join-Path $cache 'driver-installer';Expand-SafeZip $package $installer
    & $exe (Join-Path $installer 'setup.exe') | Out-File -LiteralPath (Join-Path $run 'isx.log') -Encoding UTF8
    if($LASTEXITCODE -ne 0){throw 'USB_EXTRACT: 官方驱动包解开失败。'}
    $msi=Join-Path $installer 'setup_u\Quectel_Windows_USB_Driver(U).msi'
    Check-Hash $msi $script:Lock.usb_msi_sha256
    if(-not ('QDisplayMsi' -as [type])){Add-Type -Path (Join-Path $PSScriptRoot 'ExtractMsi.cs')}
    $target=Join-Path $cache 'usb-extracted';[QDisplayMsi]::Extract($msi,$target)
    $inf=@(Get-ChildItem -LiteralPath $target -Recurse -Filter 'qcser.inf' | Where-Object {$_.Directory.Name -eq 'windows10'})
    if($inf.Count -ne 1){throw 'USB_LAYOUT: 没有唯一的 Windows 10 驱动目录。'}
    $driver=$inf[0].Directory.FullName
    $tree=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'usb-files.lock.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach($file in $tree.PSObject.Properties){Check-Hash (Join-Path $driver $file.Name) $file.Value}
    return $driver
}
function Prepare-Vdd {
    $archive=Get-Dependency 'vdd';$folder=Join-Path $cache 'vdd-25.7.23';Expand-SafeZip $archive $folder
    $folder=Join-Path $folder 'VirtualDisplayDriver'
    foreach($file in $script:Lock.vdd_files.PSObject.Properties){Check-Hash (Join-Path $folder $file.Name) $file.Value}
    return $folder
}
function Host-Status {
    $pipe=New-Object IO.Pipes.NamedPipeClientStream('.', 'QDisplay.Native.v1', [IO.Pipes.PipeDirection]::InOut, [IO.Pipes.PipeOptions]::Asynchronous)
    try {
        $pipe.Connect(1500)
        if(-not ('QDisplayRuntime' -as [type])){Add-Type -Path (Join-Path $PSScriptRoot 'RuntimeChecks.cs')}
        [QDisplayRuntime]::Verify($pipe)
        $writer=New-Object IO.BinaryWriter($pipe)
        $writer.Write([int]0x31504451);$writer.Write([int]1);$writer.Write([int]0);$writer.Flush()
        function Read-Pipe([int]$Count){
            $buffer=New-Object byte[] $Count;$offset=0
            while($offset -lt $Count){$read=$pipe.BeginRead($buffer,$offset,$Count-$offset,$null,$null)
                if(-not $read.AsyncWaitHandle.WaitOne(3000)){$pipe.Dispose();throw 'HOST_TIMEOUT: 上位机服务响应超时。'}
                $n=$pipe.EndRead($read);$read.AsyncWaitHandle.Dispose();if($n -eq 0){throw 'HOST_CLOSED: 上位机服务断开。'};$offset+=$n
            };return ,$buffer
        }
        $head=Read-Pipe 8;$status=[BitConverter]::ToInt32($head,0);$size=[BitConverter]::ToInt32($head,4)
        if($status -ne 0 -or $size -lt 2 -or $size -gt 65536){throw 'HOST_REPLY: 服务状态格式错误。'}
        return ([Text.Encoding]::UTF8.GetString((Read-Pipe $size)) | ConvertFrom-Json)
    } finally {$pipe.Dispose()}
}
function Install-Host {
    $msi=Get-Dependency 'host';$license=Get-Dependency 'licenses'
    Expand-SafeZip $license (Join-Path $cache 'licenses')
    $release=(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full' -Name Release -ErrorAction SilentlyContinue)
    if(-not $release -or $release.Release -lt 528040){
        $dotnet=Get-Dependency 'dotnet';$null=Admin 'DotNet' $dotnet
        if($script:Reboot){throw 'REBOOT_REQUIRED: .NET 已安装，请重启后重新运行本入口。'}
    }
    $null=Admin 'Host' $msi
    $script:ServiceStopped=$false
    if($script:Reboot){throw 'REBOOT_REQUIRED: 上位机安装要求重启，请重启后重新运行本入口。'}
    $gui=Join-Path $env:ProgramFiles 'QDisplay\QDisplay.exe'
    if(-not(Test-Path -LiteralPath $gui)){throw 'HOST_MISSING: MSI 返回成功但图形程序未找到。'}
    # GUI runs as the caller in their session, rather than inside the elevated
    # helper or LocalSystem service session.
    Start-Process -FilePath $gui
    Say '上位机已打开。先用硬件信息或相框模式检查联动；音频初次默认关闭。'
    $connected=$false
    for($i=0;$i -lt 20;$i++){
        try {$state=Host-Status;if($state.Connected){Say ('联动已确认：'+$state.Port+'，当前模式 '+$state.Mode) 'Green';$connected=$true;break}}catch{}
        Start-Sleep -Milliseconds 500
    }
    if(-not $connected){Say '上位机已安装并打开，设备连接尚未确认。请看上位机连接状态；不是完整联动成功。' 'Yellow'}
    $devices=@(Get-PnpDevice -PresentOnly -ErrorAction Stop | Where-Object {$_.InstanceId -like 'ROOT\MTTVDD\*'})
    if($devices.Count -eq 0 -and (Ask '是否同时安装虚拟屏驱动，以便使用 Windows 扩展副屏模式？')){
        $vdd=Prepare-Vdd;$null=Admin 'Vdd' $vdd
        if($script:Reboot){throw 'REBOOT_REQUIRED: 上位机已打开，虚拟屏驱动需要重启后确认。'}
        $current=Host-Status
        if($current.Mode -ne 'display'){
            # Reuse the frozen client helper in the caller's desktop session.
            # A newly installed virtual adapter must not stay attached while
            # the host is showing hardware/photos. It only targets MttVDD.
            if(-not ('QDisplay.Windows.Displays' -as [type])){Add-Type -Path (Join-Path (Split-Path $PSScriptRoot -Parent) 'desktop\src\Windows\Displays.cs') -ReferencedAssemblies 'System.Drawing.dll','System.Core.dll'}
            [QDisplay.Windows.Displays]::Detach()
        }
        Say '虚拟屏驱动已安装。上位机选择“副屏”后可把窗口拖到扩展桌面。' 'Green'
    } elseif($devices.Count -gt 1){Say '检测到多个 MttVDD 虚拟屏，当前上位机要求唯一设备。请先整理已有虚拟屏。' 'Yellow'}
    return $connected
}
try {
    New-Item -ItemType Directory -Path $run,$downloads -Force | Out-Null
    Start-Transcript -LiteralPath (Join-Path $run 'console.txt') -Force | Out-Null;$script:LogStarted=$true
    Say 'QDisplay 一键刷写 / 上位机安装 1.0.0'
    if(-not [Environment]::Is64BitOperatingSystem -or -not [Environment]::Is64BitProcess -or $env:PROCESSOR_ARCHITECTURE -ne 'AMD64'){throw 'UNSUPPORTED_OS: 此版本要求 Windows 10/11 x64；ARM64、Linux 和 macOS 暂不支持。'}
    if([Environment]::OSVersion.Version.Major -lt 10){throw 'UNSUPPORTED_OS: 此版本要求 Windows 10 或 11。'}
    if($NoPrompt -and -not($CheckOnly -or $PrepareOnly)){throw 'NO_CONFIRMATION: NoPrompt 只允许检测或准备，不允许刷写或安装。'}
    try {$script:SetupLock=[IO.File]::Open((Join-Path $cache 'setup.lock'),[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)}
    catch {throw 'ALREADY_RUNNING: 已有一键入口运行，请不要同时操作同一设备。'}
    $script:Lock=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'dependencies.lock.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    Prepare-Python
    $detected=Run-Backend -Arguments @('detect')
    Say ('设备状态：'+$detected.state+'；AT='+$detected.at_port+'；数据='+$detected.data_port+'；下载='+$detected.download_port)
    if($CheckOnly){$script:Result='checked';$script:Code=0;Say '只读检测完成；没有刷写、停止服务或安装系统依赖。' 'Green'}
    else {
        $coreZip=Get-Dependency 'core';$app=Get-Dependency 'app';$pac=Join-Path $cache 'core\R03.pac'
        $null=Run-Backend -Arguments @('unpack',$coreZip,$pac)
        $null=Run-Backend -Arguments @('validate','--pac',$pac,'--app',$app)
        $null=Get-Dependency 'host';$null=Get-Dependency 'licenses'
        if($PrepareOnly){
            $null=Prepare-Usb;$null=Prepare-Vdd
            $script:Result='prepared';$script:Code=0;Say '依赖和刷写输入准备完成；没有停止服务、进入下载模式或安装系统驱动。' 'Green'
        } else {
            if($detected.state -eq 'missing'){
                $present=@(Get-PnpDevice -PresentOnly -ErrorAction Stop | Where-Object {$_.InstanceId -match '^USB\\VID_(2C7C&PID_0901|0525&PID_A4A7)'})
                if($present.Count){Say 'USB 设备已出现但所需 COM 接口未就绪，补齐串口/下载驱动。';$driver=Prepare-Usb;$null=Admin 'Usb' $driver
                    if($script:Reboot){throw 'REBOOT_REQUIRED: USB 驱动安装后需要重启，再运行入口。'}
                    $detected=Run-Backend -Arguments @('detect')
                }
            }
            Write-Host '';Write-Host '1  刷写 QDisplay 并安装/打开上位机';Write-Host '2  只安装/打开上位机';Write-Host '3  只备份设备内部 Flash';Write-Host '4  恢复这台设备的本地备份';Write-Host '0  退出'
            $choice=Read-Host '请选择'
            if($choice -eq '0'){$script:Result='cancelled';$script:Code=2;Say '已退出，未刷写。' 'Yellow'}
            elseif($choice -in @('1','3')){
                $detected=Run-Backend -Arguments @('detect','--probe')
                if($detected.state -eq 'missing'){throw 'NO_DEVICE: 未找到设备。请连接客显屏的 USB 数据线后重试。'}
                $disk=[IO.DriveInfo]::new([IO.Path]::GetPathRoot($cache))
                if($disk.AvailableFreeSpace -lt 64MB){throw 'DISK_SPACE: 请至少留出 64 MiB 备份空间。'}
                Say ('将操作唯一设备，核心：'+$detected.core)
                if($detected.core -ne 'EC600UCNLBR03A04M08_OCPU_QPY'){Say '原厂 R05 首次转换会重建内部应用/文件系统。此入口只支持文档里的 EC600U-CNLB 客显屏。' 'Yellow'}
                $confirm=if($choice -eq '3'){Ask '备份会短暂进入下载模式，完成后重启设备。是否继续？'}else{Ask '是否刷写？将先两遍读取并核对本机内部 8 MiB 备份；刷写期间请保持 USB 连接。'}
                if(-not $confirm){$script:Result='cancelled';$script:Code=2;Say '未确认，未停止上位机或刷写。' 'Yellow'}
                else {
                    if((Get-Service QDisplayDevice -ErrorAction SilentlyContinue)){$stopped=Admin 'Stop';$script:ServiceStopped=$stopped.was_running}
                    $backup=Join-Path $cache ('backups\'+[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ'))
                    $arguments=@('flash','--pac',$pac,'--app',$app,'--backup',$backup)
                    if($choice -eq '3'){$arguments+='--backup-only'}else{$arguments+='--confirmed'}
                    try {$flash=Run-Backend -Arguments $arguments}
                    catch {
                        if($_.Exception.Message -like 'DOWNLOAD_PORT_TIMEOUT:*'){
                            Say '进入下载后 COM 口未就绪；补齐官方 RDA 下载驱动后重试一次（尚未写 Flash）。' 'Yellow'
                            $driver=Prepare-Usb;$null=Admin 'UsbDownload' $driver
                            if($script:Reboot){throw 'REBOOT_REQUIRED: 下载驱动要求重启，再运行入口。'}
                            $flash=Run-Backend -Arguments $arguments
                        } elseif($_.Exception.Message -like 'DATA_PORT_MISSING:*' -and $choice -eq '1'){
                            Say 'APP 已读回核对但数据口未就绪；补齐驱动后只验证握手，不重复刷写。' 'Yellow'
                            $driver=Prepare-Usb;$null=Admin 'Usb' $driver
                            if($script:Reboot){throw 'REBOOT_REQUIRED: 数据口驱动要求重启，再运行入口。'}
                            $flash=Run-Backend -Arguments @('verify-running')
                        } else {throw}
                    }
                    if(-not $flash.success){throw 'FLASH_NOT_CONFIRMED: 后台没有确认刷写成功。'}
                    if($choice -eq '1'){
                        if(-not $flash.hello){throw 'NO_HELLO: 固件写入后握手未确认。'}
                        $linked=Install-Host
                        $script:Result=if($linked){'complete'}else{'host_installed_link_pending'};$script:Code=if($linked){0}else{3}
                    } else {$script:Result='backed_up';$script:Code=0;Say '设备内部备份完成，原有 Flash 内容未改写。' 'Green'}
                }
            } elseif($choice -eq '4'){
                $backups=@(Get-ChildItem -LiteralPath (Join-Path $cache 'backups') -Directory -ErrorAction SilentlyContinue | Where-Object {(Test-Path (Join-Path $_.FullName 'backup.json')) -and (Test-Path (Join-Path $_.FullName 'internal-8MiB.bin'))} | Sort-Object Name -Descending)
                if(-not $backups.Count){throw 'NO_BACKUP: 没有本机生成的完整备份；不能使用别人提供的 dump 恢复。'}
                for($i=0;$i -lt $backups.Count;$i++){Write-Host (($i+1).ToString()+'  '+$backups[$i].Name)}
                $index=0
                if(-not [int]::TryParse((Read-Host '选择本机备份编号'),[ref]$index) -or $index -lt 1 -or $index -gt $backups.Count){throw 'BACKUP_SELECTION: 编号不正确。'}
                $selected=$backups[$index-1].FullName
                Say ('恢复来源：'+$selected) 'Yellow'
                if(-not (Ask '下载口没有唯一板卡身份。你是否确认这份备份来自当前这台设备，并同意恢复整个内部 Flash？')){$script:Result='cancelled';$script:Code=2}
                else {
                    if((Get-Service QDisplayDevice -ErrorAction SilentlyContinue)){$stopped=Admin 'Stop';$script:ServiceStopped=$stopped.was_running}
                    $safety=Join-Path $cache ('backups\'+[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')+'-before-restore')
                    $restore=Run-Backend -Arguments @('restore','--pac',$pac,'--from-backup',$selected,'--safety-backup',$safety,'--confirmed-own-device')
                    if(-not $restore.success){throw 'RESTORE_FAILED: 完整恢复未确认成功。'}
                    $script:Result='restored';$script:Code=0;Say '本机备份已恢复并完成全镜像读回核对。原厂系统不能连接 QDisplay 上位机；需要时重新选择菜单 1。' 'Green'
                }
            } elseif($choice -eq '2'){$linked=Install-Host;$script:Result=if($linked){'complete'}else{'host_installed_link_pending'};$script:Code=if($linked){0}else{3}}
            else {throw 'INVALID_CHOICE: 请选择菜单中的编号。'}
        }
    }
} catch {
    Say $_.Exception.Message 'Red'
    if($_.Exception.Message -like 'REBOOT_REQUIRED:*'){$script:Result='reboot_required';$script:Code=3010}
    Say '操作未全部完成。已取得的备份会保留；不要把其他设备的备份刷到本机。' 'Yellow'
} finally {
    if($script:ServiceStopped){try{$null=Admin 'Start';Say '已恢复原先运行的 QDisplay 后台服务。'}catch{Say ('恢复服务失败：'+$_.Exception.Message) 'Red'}}
    if($script:SetupLock){$script:SetupLock.Dispose()}
    if(Test-Path -LiteralPath $run){
        [ordered]@{result=$script:Result;exit_code=$script:Code;reboot_required=$script:Reboot;events=$script:Records.ToArray()} | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath (Join-Path $run 'summary.json') -Encoding UTF8
    }
    if($script:LogStarted){try{Stop-Transcript | Out-Null}catch{}}
    Write-Host '';Write-Host ('本次结果：'+$script:Result+'，退出码 '+$script:Code)
    if(Ask '是否导出本次诊断日志？（不包含固件备份、NV、账户配置或音视频）'){
        try {
            $export=Join-Path $run 'export';New-Item -ItemType Directory -Path $export -Force | Out-Null
            foreach($file in (Get-ChildItem -LiteralPath $run -File | Where-Object {$_.Name -notlike 'admin-*.json'})){
                $text=[IO.File]::ReadAllText($file.FullName)
                $text=$text.Replace($root,'<PROJECT>')
                if($env:USERPROFILE){$text=$text.Replace($env:USERPROFILE,'<USER>')}
                $text=$text -replace 'USB\\VID_[^\s"''<>]+','<USB-INSTANCE>'
                [IO.File]::WriteAllText((Join-Path $export $file.Name),$text,(New-Object Text.UTF8Encoding $false))
            }
            $output=Join-Path $root ('QDisplay-log-'+[IO.Path]::GetFileName($run)+'.zip')
            Compress-Archive -Path (Join-Path $export '*') -DestinationPath $output
            Write-Host ('日志已导出：'+$output) -ForegroundColor Green
        } catch {Write-Host ('日志导出失败：'+$_.Exception.Message+'；原始日志仍在 '+$run) -ForegroundColor Red}
    } else {Write-Host ('本地日志保留在 '+$run)}
}
exit $script:Code
