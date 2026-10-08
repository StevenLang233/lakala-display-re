param([Parameter(Mandatory=$true)][string]$Request)
$ErrorActionPreference='Stop'
Set-StrictMode -Version 2
$inputData=Get-Content -LiteralPath $Request -Raw -Encoding UTF8 | ConvertFrom-Json
$lock=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'dependencies.lock.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$result=[ordered]@{success=$false;error='';reboot_required=$false;was_running=$false}
function Hash([string]$Path,[string]$Expected){
    if(-not(Test-Path -LiteralPath $Path -PathType Leaf) -or (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Expected){throw ('输入文件校验失败：'+[IO.Path]::GetFileName($Path))}
}
function Signer([string]$Path){
    $signature=Get-AuthenticodeSignature -LiteralPath $Path
    if($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation') {throw ('签名无效或不是 Microsoft：'+[IO.Path]::GetFileName($Path))}
}
function Service {
    $item=Get-Service -Name 'QDisplayDevice' -ErrorAction SilentlyContinue
    if($item){
        $config=Get-ItemProperty -LiteralPath 'HKLM:\SYSTEM\CurrentControlSet\Services\QDisplayDevice'
        $expected=Join-Path $env:ProgramFiles 'QDisplay\QDisplay.Service.exe'
        if([Environment]::ExpandEnvironmentVariables($config.ImagePath).Trim().Trim('"') -ne $expected -or $config.ObjectName -ne 'LocalSystem'){throw '已有 QDisplayDevice 服务身份不同；不接管这个服务。'}
    }
    return $item
}
function Wait-Native([string]$Exe,[string]$Arguments,[string]$Name,[int]$Timeout=600000){
    $process=Start-Process -FilePath $Exe -ArgumentList $Arguments -WindowStyle Hidden -PassThru
    if(-not $process.WaitForExit($Timeout)){throw ($Name+' 超时，请检查安装进程，不要重复启动。')}
    if($process.ExitCode -eq 3010){$result.reboot_required=$true}
    elseif($process.ExitCode -ne 0){throw ($Name+' 返回 '+$process.ExitCode+'。')}
}
try {
    $principal=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw '需要管理员权限。'}
    Start-Transcript -LiteralPath (Join-Path $inputData.log_directory ('elevated-'+$inputData.action+'.txt')) -Force | Out-Null
    switch($inputData.action){
        'Stop' {
            $service=Service
            if($service -and $service.Status -ne 'Stopped'){$result.was_running=$true;Stop-Service -Name QDisplayDevice -ErrorAction Stop;$service.WaitForStatus('Stopped',[TimeSpan]::FromSeconds(30))}
        }
        'Start' {
            $service=Service
            if(-not $service){throw '后台服务已不存在，不能确认恢复成功。'}
            Start-Service -Name QDisplayDevice -ErrorAction Stop;$service.WaitForStatus('Running',[TimeSpan]::FromSeconds(30))
        }
        'Host' {
            Hash $inputData.package $lock.downloads.host.sha256
            $existing=Service
            $folder=Join-Path $env:ProgramFiles 'QDisplay'
            $files=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'host-files.lock.json') -Raw -Encoding UTF8 | ConvertFrom-Json
            $matching=[bool]$existing
            foreach($file in $files.PSObject.Properties){
                $path=Join-Path $folder $file.Name
                if(-not(Test-Path -LiteralPath $path -PathType Leaf) -or (Get-FileHash -LiteralPath $path).Hash.ToLowerInvariant() -ne $file.Value){$matching=$false;break}
            }
            if(-not $matching){
                $log=Join-Path $inputData.log_directory 'host-msi.log'
                $repair=if($existing){' REINSTALL=ALL REINSTALLMODE=amus'}else{''}
                Wait-Native "$env:WINDIR\System32\msiexec.exe" ('/i "'+$inputData.package+'" /qn /norestart REBOOT=ReallySuppress'+$repair+' /L*v "'+$log+'"') 'QDisplay MSI'
                # MSI repair of the same version must also restore changed files.
                foreach($file in $files.PSObject.Properties){Hash (Join-Path $folder $file.Name) $file.Value}
            }
            $service=Service
            if(-not $service){throw 'MSI 未注册 QDisplayDevice 服务。'}
            Start-Service -Name QDisplayDevice -ErrorAction Stop;$service.WaitForStatus('Running',[TimeSpan]::FromSeconds(30))
        }
        {$_ -in @('Usb','UsbDownload')} {
            $files=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'usb-files.lock.json') -Raw -Encoding UTF8 | ConvertFrom-Json
            foreach($file in $files.PSObject.Properties){Hash (Join-Path $inputData.package $file.Name) $file.Value}
            $names=if($inputData.action -eq 'UsbDownload'){@('rdavcom')}else{@('qcser','unisoc_iot')}
            foreach($name in $names){
                Signer (Join-Path $inputData.package ($name+'.cat'))
                & "$env:WINDIR\System32\pnputil.exe" /add-driver (Join-Path $inputData.package ($name+'.inf')) /install
                if($LASTEXITCODE -eq 3010){$result.reboot_required=$true}
                elseif($LASTEXITCODE -notin @(0,259)){throw ('pnputil '+$name+' 返回 '+$LASTEXITCODE)}
            }
            & "$env:WINDIR\System32\pnputil.exe" /scan-devices
            if($LASTEXITCODE -ne 0){throw ('设备重新扫描失败：'+$LASTEXITCODE)}
        }
        'Vdd' {
            foreach($file in $lock.vdd_files.PSObject.Properties){Hash (Join-Path $inputData.package $file.Name) $file.Value}
            Signer (Join-Path $inputData.package 'mttvdd.cat')
            $config=Join-Path $env:ProgramData 'QDisplay-VDD'
            if(Test-Path -LiteralPath $config){if((Get-Item -LiteralPath $config).Attributes -band [IO.FileAttributes]::ReparsePoint){throw '虚拟屏配置目录不能是符号链接。'}}
            New-Item -ItemType Directory -Path $config -Force | Out-Null
            $acl=New-Object Security.AccessControl.DirectorySecurity;$acl.SetAccessRuleProtection($true,$false)
            foreach($sid in @('S-1-5-18','S-1-5-32-544')){$acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule((New-Object Security.Principal.SecurityIdentifier($sid)),'FullControl','ContainerInherit,ObjectInherit','None','Allow')))}
            $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule((New-Object Security.Principal.SecurityIdentifier('S-1-5-11')),'ReadAndExecute','ContainerInherit,ObjectInherit','None','Allow')))
            Set-Acl -LiteralPath $config -AclObject $acl
            Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'vdd_settings.xml') -Destination (Join-Path $config 'vdd_settings.xml') -Force
            & $inputData.python (Join-Path $PSScriptRoot 'install_vdd.py') --package $inputData.package --config $config --output (Join-Path $inputData.log_directory 'vdd-result.json') --install
            if($LASTEXITCODE -ne 0){throw '虚拟屏安装失败，详情见 vdd-result.json。'}
            $vdd=Get-Content -LiteralPath (Join-Path $inputData.log_directory 'vdd-result.json') -Raw -Encoding UTF8 | ConvertFrom-Json
            if($vdd.reboot_required){$result.reboot_required=$true}
        }
        'DotNet' {
            Hash $inputData.package $lock.downloads.dotnet.sha256;Signer $inputData.package
            $log=Join-Path $inputData.log_directory 'dotnet-install.html'
            Wait-Native $inputData.package ('/q /norestart /log "'+$log+'"') '.NET Framework 4.8'
            if(-not $result.reboot_required){$release=Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full' -Name Release;if($release.Release -lt 528040){throw '.NET 安装后版本不匹配。'}}
        }
        default {throw '未知管理员操作；不执行。'}
    }
    $result.success=$true
} catch {$result.error=$_.Exception.Message}
finally {
    try{Stop-Transcript | Out-Null}catch{}
    [IO.File]::WriteAllText($inputData.result,($result | ConvertTo-Json -Depth 5),(New-Object Text.UTF8Encoding $false))
}
if(-not $result.success){exit 1};exit 0
