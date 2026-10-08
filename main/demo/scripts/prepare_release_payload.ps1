param([string]$AssetsDirectory)
$ErrorActionPreference='Stop'
$demo=Split-Path $PSScriptRoot -Parent
$main=Split-Path $demo -Parent
$root=Split-Path $main -Parent
$metadataPath=Join-Path $demo 'releases\manifest.json'
$metadata=Get-Content -LiteralPath $metadataPath -Raw -Encoding UTF8 | ConvertFrom-Json
if($metadata.tag -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]+$'){throw 'Invalid Release tag in metadata'}
if(-not $AssetsDirectory){$AssetsDirectory=Join-Path $root ('junk\publish\'+$metadata.tag)}
$AssetsDirectory=[IO.Path]::GetFullPath($AssetsDirectory)
if(-not $AssetsDirectory.StartsWith($root.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Release packaging output must stay inside the workspace'}
$snapshot=Get-Content -LiteralPath (Join-Path $demo 'SOURCE_SNAPSHOT.json') -Raw -Encoding UTF8 | ConvertFrom-Json
foreach($group in @('firmware_source','desktop_source','generated_assets')){
    foreach($property in $snapshot.$group.PSObject.Properties){
        $path=Join-Path $main $property.Name
        if((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $property.Value){throw "Source snapshot changed: $($property.Name)"}
    }
}
$firmware=Join-Path $AssetsDirectory $metadata.firmware.file
$installer=Join-Path $AssetsDirectory $metadata.windows.msi
if((Get-FileHash -LiteralPath $firmware -Algorithm SHA256).Hash -ne $metadata.firmware.sha256){throw 'Firmware Release hash mismatch'}
if((Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash -ne $metadata.windows.sha256){throw 'MSI Release hash mismatch'}
$portable=Join-Path $AssetsDirectory 'windows\portable'
if(-not(Test-Path -LiteralPath $portable -PathType Container)){throw 'Original Windows files not found'}
$zipName='QDisplay-'+$metadata.windows.version+'-Windows-files.zip'
$zipPath=Join-Path $AssetsDirectory $zipName
Add-Type -AssemblyName System.IO.Compression.FileSystem
if(-not(Test-Path -LiteralPath $zipPath)){
    [IO.Compression.ZipFile]::CreateFromDirectory($portable,$zipPath,[IO.Compression.CompressionLevel]::Optimal,$false)
}
# Verify existing archives too, so a resumed publish cannot silently package stale files.
$expectedFiles=@{}
foreach($file in Get-ChildItem -LiteralPath $portable -File -Recurse -Force){
    $name=$file.FullName.Substring($portable.TrimEnd('\').Length+1).Replace('\','/')
    $expectedFiles[$name]=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
}
$archive=[IO.Compression.ZipFile]::OpenRead($zipPath)
$hasher=[Security.Cryptography.SHA256]::Create()
$seen=@{}
try{
    foreach($entry in $archive.Entries){
        if($entry.FullName.EndsWith('/')){continue}
        if(-not $expectedFiles.ContainsKey($entry.FullName) -or $seen.ContainsKey($entry.FullName)){throw 'Unexpected or duplicate Windows ZIP entry'}
        $stream=$entry.Open()
        try{$digest=[BitConverter]::ToString($hasher.ComputeHash($stream)).Replace('-','')}finally{$stream.Dispose()}
        if($digest -ne $expectedFiles[$entry.FullName]){throw "Windows ZIP content mismatch: $($entry.FullName)"}
        $seen[$entry.FullName]=$true
    }
    if($seen.Count -ne $expectedFiles.Count){throw 'Windows ZIP has missing files'}
}finally{$hasher.Dispose();$archive.Dispose()}
$assetPaths=@($firmware,$installer,$zipPath)
$manifest=[ordered]@{tag=$metadata.tag;purpose=$metadata.purpose;firmware=$metadata.firmware;windows=$metadata.windows;limitations=$metadata.limitations;assets=@()}
foreach($path in $assetPaths){
    $item=Get-Item -LiteralPath $path
    $manifest.assets+=[ordered]@{name=$item.Name;bytes=$item.Length;sha256=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()}
}
$manifestPath=Join-Path $AssetsDirectory 'release-manifest.json'
$utf8=New-Object Text.UTF8Encoding $false
[IO.File]::WriteAllText($manifestPath,($manifest | ConvertTo-Json -Depth 8 -Compress)+[Environment]::NewLine,$utf8)
$assetPaths+=$manifestPath
$lines=@($assetPaths | ForEach-Object {((Get-FileHash -LiteralPath $_ -Algorithm SHA256).Hash.ToLowerInvariant())+'  '+[IO.Path]::GetFileName($_)})
$sumsPath=Join-Path $AssetsDirectory 'SHA256SUMS.txt'
[IO.File]::WriteAllLines($sumsPath,$lines,$utf8)
$assetPaths+=$sumsPath
$notes=Join-Path $demo ('releases\'+$metadata.tag+'.md')
if(-not(Test-Path -LiteralPath $notes)){throw 'Release notes missing'}
$plan=[ordered]@{tag=$metadata.tag;assets=$assetPaths;notes=$notes;source_snapshot_verified=$true;firmware_verified=$true;msi_verified=$true}
[IO.File]::WriteAllText((Join-Path $AssetsDirectory 'upload-plan.json'),($plan | ConvertTo-Json -Depth 5)+[Environment]::NewLine,$utf8)
Write-Output ('Release payload ready: '+$AssetsDirectory)
