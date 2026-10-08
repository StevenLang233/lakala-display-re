param([switch]$Offline)
$ErrorActionPreference='Stop'
$demo=Split-Path $PSScriptRoot -Parent
$directory=Join-Path $demo 'dependencies\desktop'
$cache=Join-Path $demo 'dependencies\cache'
$frameworks=@{'k4os.compression.lz4'='net462';'system.memory'='net461';'system.buffers'='net461';'system.runtime.compilerservices.unsafe'='net461';'system.numerics.vectors'='net46'}
$packages=Get-Content -LiteralPath (Join-Path $directory 'packages.lock.json') -Raw -Encoding UTF8 | ConvertFrom-Json
Add-Type -AssemblyName System.IO.Compression.FileSystem
foreach($package in $packages){
    $dll=Join-Path $directory $package.assembly
    if(Test-Path -LiteralPath $dll){
        if((Get-FileHash -LiteralPath $dll -Algorithm SHA256).Hash -ne $package.assembly_sha256){throw "Dependency SHA mismatch: $($package.assembly)"}
        continue
    }
    if($Offline){throw "Missing offline dependency: $($package.assembly)"}
    if(-not $frameworks.ContainsKey($package.id)){throw 'Unsupported dependency in lock file'}
    $url='https://api.nuget.org/v3-flatcontainer/'+$package.id+'/'+$package.version+'/'+$package.id+'.'+$package.version+'.nupkg'
    if($package.url -ne $url){throw 'Dependency URL does not match locked NuGet coordinates'}
    New-Item -ItemType Directory -Path $cache -Force | Out-Null
    $file=Join-Path $cache ($package.id+'.'+$package.version+'.nupkg')
    if(-not(Test-Path -LiteralPath $file)){
        [Net.ServicePointManager]::SecurityProtocol=[Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $url -OutFile $file -UseBasicParsing
    }
    if((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash -ne $package.sha256){throw "NuGet package SHA mismatch: $($package.id)"}
    $archive=[IO.Compression.ZipFile]::OpenRead($file)
    try{
        $entry=$archive.GetEntry('lib/'+$frameworks[$package.id]+'/'+$package.assembly)
        if($null -eq $entry){throw 'Locked framework assembly not found in package'}
        [IO.Compression.ZipFileExtensions]::ExtractToFile($entry,$dll,$false)
    }finally{$archive.Dispose()}
    if((Get-FileHash -LiteralPath $dll -Algorithm SHA256).Hash -ne $package.assembly_sha256){throw "Restored DLL SHA mismatch: $($package.assembly)"}
}
Write-Output 'Five locked desktop dependencies verified.'
