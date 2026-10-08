param(
    [Parameter(Mandatory=$true)][string]$SdkRoot,
    [Parameter(Mandatory=$true)][string]$ToolchainBin,
    [Parameter(Mandatory=$true)][string]$QpyInputs,
    [Parameter(Mandatory=$true)][string]$DTools,
    [string]$Python='python'
)
$ErrorActionPreference='Stop'
$demo=Split-Path $PSScriptRoot -Parent
# This compiler requires ASCII source/include paths. Create one checked temp junction.
$bridge=Join-Path ([IO.Path]::GetTempPath()) 'qdisplay-demo-workspace'
if($bridge -match '[^\x00-\x7F]'){throw 'Select an ASCII TEMP path for this build.'}
if(Test-Path -LiteralPath $bridge){
    $item=Get-Item -LiteralPath $bridge
    if($item.LinkType -ne 'Junction' -or $item.Target -notcontains $demo){throw 'Existing build junction points elsewhere.'}
}else{New-Item -ItemType Junction -Path $bridge -Target $demo | Out-Null}
foreach($external in @($SdkRoot,$ToolchainBin,$QpyInputs,$DTools)){
    if(-not(Test-Path -LiteralPath $external)){throw "Missing build input: $external"}
    if($external -match '[^\x00-\x7F]'){throw 'Use ASCII paths for external SDK/compiler inputs as well.'}
}
$previousRoot=$env:QDISPLAY_NATIVE_ROOT
try{
    $env:QDISPLAY_NATIVE_ROOT=$bridge
    & $Python (Join-Path $bridge 'scripts\build_native_firmware.py') --sdk-root $SdkRoot --toolchain-bin $ToolchainBin --qpy-inputs $QpyInputs --dtools $DTools
    if($LASTEXITCODE -ne 0){throw 'Firmware build failed'}
}finally{$env:QDISPLAY_NATIVE_ROOT=$previousRoot}
