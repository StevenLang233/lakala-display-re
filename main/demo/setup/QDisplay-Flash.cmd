@echo off
setlocal
chcp 65001 >nul
set "QDISPLAY_LAUNCHER_FILE=%~f0"
set "QDISPLAY_LAUNCHER_ARGS=%*"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "$raw=[IO.File]::ReadAllText($env:QDISPLAY_LAUNCHER_FILE); $parts=[regex]::Split($raw,'(?m)^# QDISPLAY_POWERSHELL_BEGIN\r?$'); if($parts.Length -ne 2){throw 'Invalid launcher source'}; & ([scriptblock]::Create($parts[1]))"
set "qdisplay_result=%errorlevel%"
echo.
echo QDisplay setup exit code: %qdisplay_result%
pause
exit /b %qdisplay_result%
# QDISPLAY_POWERSHELL_BEGIN
# SPDX-License-Identifier: CC-BY-NC-SA-4.0
# Standalone entry for the immutable setup-v1.0.0 package. No firmware writes here.
$ErrorActionPreference='Stop'
Set-StrictMode -Version 2
$packageName='QDisplay-Setup-1.0.0.zip'
$packageHash='1d16681760edd8960bbafb1c02c6db30624d31184006cba257bba014588ff5a5'
$packageUrl='https://github.com/StevenLang233/lakala-display-re/releases/download/setup-v1.0.0/'+$packageName
$folder=Split-Path -Parent $env:QDISPLAY_LAUNCHER_FILE
$cache=Join-Path $folder '.qdisplay-launcher'
$stamp=[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')+'-'+[Guid]::NewGuid().ToString('N').Substring(0,8)
$logPath=Join-Path $cache ('launcher-'+$stamp+'.txt')
$records=New-Object Collections.Generic.List[string]
$lockStream=$null;$delegated=$false;$code=1
$flags=@();$noPrompt=$false;$offline=$false
function Say([string]$Text,[string]$Color='Cyan') {
    $line='['+[DateTime]::Now.ToString('HH:mm:ss')+'] '+$Text
    Write-Host $line -ForegroundColor $Color
    $records.Add($line)
}
function Verify-Package([string]$Path) {
    if((Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $packageHash){
        throw ('PACKAGE_HASH: '+$packageName+' 与固定版本不一致，请重新下载匹配的原包。')
    }
}
try {
    $flags=@(($env:QDISPLAY_LAUNCHER_ARGS -split '\s+') | Where-Object {$_})
    foreach($flag in $flags){
        if($flag -notin @('-CheckOnly','-PrepareOnly','-NoPrompt','-Offline')){throw ('ARGUMENT: 不支持的参数 '+$flag)}
    }
    $noPrompt=$flags -contains '-NoPrompt';$offline=$flags -contains '-Offline'
    if($noPrompt -and -not($flags -contains '-CheckOnly' -or $flags -contains '-PrepareOnly')){
        throw 'ARGUMENT: -NoPrompt 只能用于 -CheckOnly 或 -PrepareOnly；刷写必须由用户确认。'
    }
    New-Item -ItemType Directory -Path $cache -Force | Out-Null
    $lockStream=[IO.File]::Open((Join-Path $cache 'launcher.lock'),[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
    Say 'QDisplay 刷写器：先准备并校验完整包，再打开设备检测与安装菜单。'
    $adjacent=Join-Path $folder $packageName
    $archive=Join-Path $cache $packageName
    if(Test-Path -LiteralPath $adjacent -PathType Leaf){$archive=$adjacent}
    if(Test-Path -LiteralPath $archive -PathType Leaf){Verify-Package $archive;Say '本地完整包 SHA-256 校验通过。'}
    else {
        if($offline){throw ('OFFLINE_MISSING: 请把 '+$packageName+' 放在 CMD 同一文件夹后重试。')}
        Say ('从项目 Release 下载 '+$packageName+'，约 1.5 MB。')
        [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
        $partial=$archive+'.'+$stamp+'.partial'
        $response=$null;$inputStream=$null;$outputStream=$null
        try {
            $request=[Net.HttpWebRequest]::Create($packageUrl)
            $request.Timeout=30000;$request.ReadWriteTimeout=15000;$request.UserAgent='QDisplay-Flash/1.0.0'
            $response=$request.GetResponse();$inputStream=$response.GetResponseStream();$inputStream.ReadTimeout=15000
            $outputStream=[IO.File]::Open($partial,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
            $buffer=New-Object byte[] 65536;$received=0L
            while(($count=$inputStream.Read($buffer,0,$buffer.Length)) -gt 0){
                $outputStream.Write($buffer,0,$count);$received+=$count
                $percent=if($response.ContentLength -gt 0){[Math]::Min(100,[int]($received*100/$response.ContentLength))}else{-1}
                Write-Progress -Activity '下载完整刷写包' -Status ($received.ToString('N0')+' 字节') -PercentComplete $percent
            }
            $outputStream.Flush();$outputStream.Dispose();$outputStream=$null
            Verify-Package $partial
            [IO.File]::Move($partial,$archive)
            Say '下载完成，SHA-256 校验通过。' 'Green'
        } finally {
            if($outputStream){$outputStream.Dispose()};if($inputStream){$inputStream.Dispose()};if($response){$response.Dispose()}
            Write-Progress -Activity '下载完整刷写包' -Completed
        }
    }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $destination=Join-Path $cache 'setup-v1.0.0'
    $prefix=[IO.Path]::GetFullPath($destination).TrimEnd('\')+'\'
    New-Item -ItemType Directory -Path $destination -Force | Out-Null
    $zip=[IO.Compression.ZipFile]::OpenRead($archive)
    try {
        foreach($entry in $zip.Entries){
            $path=[IO.Path]::GetFullPath((Join-Path $destination $entry.FullName))
            if(-not $path.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase)){throw 'ZIP_PATH: 压缩包路径越界。'}
            if($entry.FullName.EndsWith('/')){New-Item -ItemType Directory -Path $path -Force | Out-Null;continue}
            New-Item -ItemType Directory -Path (Split-Path -Parent $path) -Force | Out-Null
            [IO.Compression.ZipFileExtensions]::ExtractToFile($entry,$path,$true)
        }
    } finally {$zip.Dispose()}
    $setup=Join-Path $destination 'QDisplay-Setup-1.0.0\main\demo\setup\setup.ps1'
    if(-not(Test-Path -LiteralPath $setup -PathType Leaf)){throw 'PACKAGE_LAYOUT: 完整包缺少 setup.ps1。'}
    Say ('打开设备检测与安装菜单；完整包和本机备份保留在 '+$destination)
    & "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File $setup @flags
    $code=$LASTEXITCODE;$delegated=$true
    Say ('安装入口退出码：'+$code)
} catch {
    Say ('LAUNCHER_FAILED: 入口准备失败。'+$_.Exception.Message) 'Red'
} finally {
    if($lockStream){$lockStream.Dispose()}
    try {
        New-Item -ItemType Directory -Path $cache -Force | Out-Null
        $text=$records -join [Environment]::NewLine
        if($env:USERPROFILE){$text=$text.Replace($env:USERPROFILE,'<USER>')}
        $text=$text.Replace($folder,'<LAUNCHER-FOLDER>')
        [IO.File]::WriteAllText($logPath,$text,(New-Object Text.UTF8Encoding $false))
        if(-not $delegated -and -not $noPrompt){
            if((Read-Host '是否导出入口失败日志？ [y/N]') -match '^(y|yes|是)$'){
                $export=Join-Path $folder ('QDisplay-launcher-log-'+$stamp+'.txt')
                Copy-Item -LiteralPath $logPath -Destination $export
                Write-Host ('日志已导出：'+$export) -ForegroundColor Green
            } else {Write-Host ('本地日志保留在 '+$logPath)}
        }
    } catch {Write-Host ('日志导出失败：'+$_.Exception.Message) -ForegroundColor Red}
}
exit $code
