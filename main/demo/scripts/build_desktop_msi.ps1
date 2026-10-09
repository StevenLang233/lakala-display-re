param([string]$BuildDirectory='build\windows')
$ErrorActionPreference='Stop'
$project=Split-Path $PSScriptRoot -Parent
$directory=Join-Path $project $BuildDirectory
$msi=Join-Path $directory 'QDisplay-0.3.1-x64.msi'
$cab=Join-Path $directory 'qdisplay.cab'
$files=@(
    @{key='Gui';name='QDisplay.exe';guid='{D7646E7E-69FD-415F-A05A-CC86BFB3A112}'},
    @{key='Service';name='QDisplay.Service.exe';guid='{9A0B3F02-707C-44F3-B126-EAE0D25F9DF3}'},
    @{key='Core';name='QDisplay.Core.dll';guid='{3C430326-2A58-457E-A767-E52B1C6FB563}'},
    @{key='Windows';name='QDisplay.Windows.dll';guid='{C3F8FD66-92A5-471C-8C4A-BCA156474D45}'},
    @{key='GuiConfig';name='QDisplay.exe.config';guid='{EA3376E8-6F70-443E-AE0E-2F5AC55599E5}'},
    @{key='ServiceConfig';name='QDisplay.Service.exe.config';guid='{21D2ECF4-8427-40FA-8052-C98CC0D15427}'},
    @{key='Lz4';name='K4os.Compression.LZ4.dll';guid='{AC026816-4824-499F-81D2-772203FB1F47}'},
    @{key='Memory';name='System.Memory.dll';guid='{B9B047B0-E31F-4E7B-8EAC-F859232767D7}'},
    @{key='Buffers';name='System.Buffers.dll';guid='{D9B09E76-C595-45EF-B1F3-84841C4C16B1}'},
    @{key='Unsafe';name='System.Runtime.CompilerServices.Unsafe.dll';guid='{7B31C998-470F-4CAA-ACD4-E69509C4107E}'},
    @{key='Vectors';name='System.Numerics.Vectors.dll';guid='{AA866E34-BB89-4102-AD1E-9900290E7CD2}'},
    @{key='Notices';name='THIRD-PARTY-NOTICES.txt';guid='{75DD499B-BDEA-494F-B399-42A1F5CCC036}'})
# Use an ASCII staging directory for makecab; never depend on a project junction.
$scratch=Join-Path ([IO.Path]::GetTempPath()) ('qdisplay-msi-'+[Guid]::NewGuid().ToString('N'))
if($scratch -match '[^\x00-\x7F]'){throw 'makecab needs an ASCII TEMP path; set TEMP for this build process.'}
New-Item -ItemType Directory -Path $scratch | Out-Null
$ddf=@('.OPTION EXPLICIT','.Set Cabinet=ON','.Set Compress=ON','.Set CompressionType=MSZIP','.Set CabinetNameTemplate=qdisplay.cab','.Set DiskDirectoryTemplate=.', '.Set MaxDiskSize=0')
foreach($file in $files){
    $path=Join-Path $directory $file.name
    if(-not(Test-Path -LiteralPath $path)){throw "Missing $path"}
    Copy-Item -LiteralPath $path -Destination (Join-Path $scratch $file.name)
    $ddf+=('"'+$file.name+'" '+$file.key)
}
$ddfPath=Join-Path $scratch 'package.ddf'
[IO.File]::WriteAllLines($ddfPath,$ddf,[Text.Encoding]::ASCII)
Push-Location $scratch
try{& "$env:WINDIR\System32\makecab.exe" /F package.ddf | Out-Null;if($LASTEXITCODE -ne 0){throw 'Cabinet build failed'}}finally{Pop-Location}
Copy-Item -LiteralPath (Join-Path $scratch 'qdisplay.cab') -Destination $cab -Force
# The build-only staging path is reported for the caller to inspect/clean.
Write-Output ("MSI staging: "+$scratch)
if(Test-Path -LiteralPath $msi){Remove-Item -LiteralPath $msi}
$installer=New-Object -ComObject WindowsInstaller.Installer
$database=$installer.OpenDatabase($msi,3)
function Sql([string]$query){$view=$database.OpenView($query);try{$view.Execute($null)}finally{$view.Close();[Runtime.InteropServices.Marshal]::FinalReleaseComObject($view) | Out-Null}}
function Row([string]$table,[string[]]$columns,[object[]]$values){
    $quoted=@($columns | ForEach-Object {'`'+$_+'`'}) -join ','
    $placeholders=@($values | ForEach-Object {'?'}) -join ','
    $query='INSERT INTO `'+$table+'` ('+$quoted+') VALUES ('+$placeholders+')'
    $view=$database.OpenView($query);$record=$installer.CreateRecord($values.Count)
    try{for($i=0;$i -lt $values.Count;$i++){if($null -eq $values[$i]){continue};if($values[$i] -is [int]){$record.IntegerData($i+1)=$values[$i]}else{$record.StringData($i+1)=[string]$values[$i]}};$view.Execute($record)}finally{$view.Close();[Runtime.InteropServices.Marshal]::FinalReleaseComObject($record) | Out-Null;[Runtime.InteropServices.Marshal]::FinalReleaseComObject($view) | Out-Null}
}
$schemas=@(
    'CREATE TABLE `Property` (`Property` CHAR(72) NOT NULL,`Value` CHAR(0) NOT NULL PRIMARY KEY `Property`)',
    'CREATE TABLE `Directory` (`Directory` CHAR(72) NOT NULL,`Directory_Parent` CHAR(72),`DefaultDir` CHAR(255) NOT NULL PRIMARY KEY `Directory`)',
    'CREATE TABLE `Component` (`Component` CHAR(72) NOT NULL,`ComponentId` CHAR(38),`Directory_` CHAR(72) NOT NULL,`Attributes` SHORT NOT NULL,`Condition` CHAR(255),`KeyPath` CHAR(72) PRIMARY KEY `Component`)',
    'CREATE TABLE `Feature` (`Feature` CHAR(38) NOT NULL,`Feature_Parent` CHAR(38),`Title` CHAR(64),`Description` CHAR(255),`Display` SHORT,`Level` SHORT NOT NULL,`Directory_` CHAR(72),`Attributes` SHORT NOT NULL PRIMARY KEY `Feature`)',
    'CREATE TABLE `FeatureComponents` (`Feature_` CHAR(38) NOT NULL,`Component_` CHAR(72) NOT NULL PRIMARY KEY `Feature_`,`Component_`)',
    'CREATE TABLE `File` (`File` CHAR(72) NOT NULL,`Component_` CHAR(72) NOT NULL,`FileName` CHAR(255) NOT NULL,`FileSize` LONG NOT NULL,`Version` CHAR(72),`Language` CHAR(20),`Attributes` SHORT,`Sequence` SHORT NOT NULL PRIMARY KEY `File`)',
    'CREATE TABLE `Media` (`DiskId` SHORT NOT NULL,`LastSequence` SHORT NOT NULL,`DiskPrompt` CHAR(64),`Cabinet` CHAR(255),`VolumeLabel` CHAR(32),`Source` CHAR(72) PRIMARY KEY `DiskId`)',
    'CREATE TABLE `Registry` (`Registry` CHAR(72) NOT NULL,`Root` SHORT NOT NULL,`Key` CHAR(255) NOT NULL,`Name` CHAR(255),`Value` CHAR(0),`Component_` CHAR(72) NOT NULL PRIMARY KEY `Registry`)',
    'CREATE TABLE `Shortcut` (`Shortcut` CHAR(72) NOT NULL,`Directory_` CHAR(72) NOT NULL,`Name` CHAR(128) NOT NULL,`Component_` CHAR(72) NOT NULL,`Target` CHAR(255) NOT NULL,`Arguments` CHAR(255),`Description` CHAR(255),`Hotkey` SHORT,`Icon_` CHAR(72),`IconIndex` SHORT,`ShowCmd` SHORT,`WkDir` CHAR(72) PRIMARY KEY `Shortcut`)',
    'CREATE TABLE `Icon` (`Name` CHAR(72) NOT NULL,`Data` OBJECT NOT NULL PRIMARY KEY `Name`)',
    'CREATE TABLE `ServiceInstall` (`ServiceInstall` CHAR(72) NOT NULL,`Name` CHAR(255) NOT NULL,`DisplayName` CHAR(255),`ServiceType` LONG NOT NULL,`StartType` LONG NOT NULL,`ErrorControl` LONG NOT NULL,`LoadOrderGroup` CHAR(255),`Dependencies` CHAR(255),`StartName` CHAR(255),`Password` CHAR(255),`Arguments` CHAR(255),`Component_` CHAR(72) NOT NULL,`Description` CHAR(255) PRIMARY KEY `ServiceInstall`)',
    'CREATE TABLE `ServiceControl` (`ServiceControl` CHAR(72) NOT NULL,`Name` CHAR(255) NOT NULL,`Event` SHORT NOT NULL,`Arguments` CHAR(255),`Wait` SHORT,`Component_` CHAR(72) NOT NULL PRIMARY KEY `ServiceControl`)',
    'CREATE TABLE `InstallExecuteSequence` (`Action` CHAR(72) NOT NULL,`Condition` CHAR(255),`Sequence` SHORT PRIMARY KEY `Action`)',
    'CREATE TABLE `InstallUISequence` (`Action` CHAR(72) NOT NULL,`Condition` CHAR(255),`Sequence` SHORT PRIMARY KEY `Action`)',
    'CREATE TABLE `Upgrade` (`UpgradeCode` CHAR(38) NOT NULL,`VersionMin` CHAR(20),`VersionMax` CHAR(20),`Language` CHAR(255),`Attributes` LONG NOT NULL,`Remove` CHAR(255),`ActionProperty` CHAR(72) NOT NULL PRIMARY KEY `UpgradeCode`,`VersionMin`,`VersionMax`,`Language`,`Attributes`)',
    'CREATE TABLE `LaunchCondition` (`Condition` CHAR(255) NOT NULL,`Description` CHAR(255) NOT NULL PRIMARY KEY `Condition`)')
foreach($schema in $schemas){Sql $schema}
$properties=[ordered]@{ProductCode='{32989BD8-8D5F-48D0-A6F6-447544C5B869}';UpgradeCode='{F5923C19-B395-4509-AE80-67B7020A15BA}';ProductName='QDisplay';ProductVersion='0.3.1';ProductLanguage='1033';Manufacturer='QDisplay';ALLUSERS='1';INSTALLLEVEL='1';ARPNOMODIFY='1';ARPPRODUCTICON='QDisplayIcon';REBOOT='ReallySuppress'}
$properties['SecureCustomProperties']='QDISPLAY_OLD';
foreach($p in $properties.GetEnumerator()){Row 'Property' @('Property','Value') @($p.Key,$p.Value)}
Row 'Upgrade' @('UpgradeCode','VersionMin','VersionMax','Attributes','Remove','ActionProperty') @($properties.UpgradeCode,'0.0.0','0.3.1',1,'ALL','QDISPLAY_OLD')
Row 'Directory' @('Directory','Directory_Parent','DefaultDir') @('TARGETDIR',$null,'SourceDir')
Row 'Directory' @('Directory','Directory_Parent','DefaultDir') @('ProgramFiles64Folder','TARGETDIR','.')
Row 'Directory' @('Directory','Directory_Parent','DefaultDir') @('INSTALLFOLDER','ProgramFiles64Folder','QDisplay')
Row 'Directory' @('Directory','Directory_Parent','DefaultDir') @('ProgramMenuFolder','TARGETDIR','.')
Row 'Feature' @('Feature','Title','Level','Directory_','Attributes') @('Main','QDisplay',1,'INSTALLFOLDER',0)
$sequence=0
foreach($f in $files){$sequence++;$file=Get-Item -LiteralPath (Join-Path $directory $f.name);$version=if($f.name -match '\.(exe|dll)$'){$file.VersionInfo.FileVersion}else{$null}
    Row 'Component' @('Component','ComponentId','Directory_','Attributes','KeyPath') @($f.key,$f.guid,'INSTALLFOLDER',256,$f.key)
    Row 'FeatureComponents' @('Feature_','Component_') @('Main',$f.key)
    Row 'File' @('File','Component_','FileName','FileSize','Version','Attributes','Sequence') @($f.key,$f.key,$f.name,[int]$file.Length,$version,512,$sequence)
}
Row 'Media' @('DiskId','LastSequence','Cabinet') @(1,$sequence,'#qdisplay.cab')
Row 'Registry' @('Registry','Root','Key','Name','Value','Component_') @('Login',2,'SOFTWARE\Microsoft\Windows\CurrentVersion\Run','QDisplay','"[#Gui]" --tray','Gui')
Row 'Shortcut' @('Shortcut','Directory_','Name','Component_','Target','Description','Icon_','IconIndex','ShowCmd','WkDir') @('StartMenu','ProgramMenuFolder','QDisplay','Gui','[#Gui]','QDisplay','QDisplayIcon',0,1,'INSTALLFOLDER')
Row 'ServiceInstall' @('ServiceInstall','Name','DisplayName','ServiceType','StartType','ErrorControl','Component_','Description') @('Device','QDisplayDevice','QDisplay Device Service',16,2,32769,'Service','QDisplay USB connection and device audio')
Row 'ServiceControl' @('ServiceControl','Name','Event','Wait','Component_') @('Device','QDisplayDevice',163,1,'Service')
Row 'LaunchCondition' @('Condition','Description') @('VersionNT64','QDisplay requires 64-bit Windows.')
$actions=[ordered]@{FindRelatedProducts=25;LaunchConditions=100;CostInitialize=800;FileCost=900;CostFinalize=1000;InstallValidate=1400;InstallInitialize=1500;RemoveExistingProducts=1550;ProcessComponents=1600;UnpublishFeatures=1800;StopServices=1900;DeleteServices=2000;RemoveRegistryValues=2600;RemoveShortcuts=3200;RemoveFiles=3500;RemoveFolders=3600;InstallFiles=4000;CreateShortcuts=4500;WriteRegistryValues=5000;InstallServices=5800;StartServices=5900;RegisterUser=6000;RegisterProduct=6100;PublishFeatures=6300;PublishProduct=6400;InstallFinalize=6600}
foreach($action in $actions.GetEnumerator()){Row 'InstallExecuteSequence' @('Action','Sequence') @($action.Key,[int]$action.Value)}
foreach($action in @(@('FindRelatedProducts',25),@('LaunchConditions',100),@('CostInitialize',800),@('FileCost',900),@('CostFinalize',1000),@('ExecuteAction',1300))){Row 'InstallUISequence' @('Action','Sequence') @($action[0],[int]$action[1])}
function Stream([string]$table,[string]$key,[string]$path){$view=$database.OpenView('INSERT INTO `'+$table+'` (`Name`,`Data`) VALUES (?,?)');$record=$installer.CreateRecord(2);$record.StringData(1)=$key;$record.SetStream(2,$path);try{$view.Execute($record)}finally{$view.Close();[Runtime.InteropServices.Marshal]::FinalReleaseComObject($record) | Out-Null;[Runtime.InteropServices.Marshal]::FinalReleaseComObject($view) | Out-Null}}
Stream 'Icon' 'QDisplayIcon' (Join-Path $directory 'QDisplay.ico')
Stream '_Streams' 'qdisplay.cab' $cab
$summary=$database.SummaryInformation(20)
$summary.Property(1)=1252;$summary.Property(2)='QDisplay installer';$summary.Property(4)='QDisplay';$summary.Property(7)='x64;1033';$summary.Property(9)=[Guid]::NewGuid().ToString('B').ToUpper();$summary.Property(14)=500;$summary.Property(15)=2;$summary.Property(18)='QDisplay native MSI builder';$summary.Persist();$database.Commit()
[Runtime.InteropServices.Marshal]::FinalReleaseComObject($summary) | Out-Null
[Runtime.InteropServices.Marshal]::FinalReleaseComObject($database) | Out-Null
[Runtime.InteropServices.Marshal]::FinalReleaseComObject($installer) | Out-Null
[ordered]@{msi=$msi;sha256=(Get-FileHash -LiteralPath $msi -Algorithm SHA256).Hash.ToLower();custom_actions=@();product_code=$properties.ProductCode;service='QDisplayDevice';files=$files;built=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $directory 'package.json') -Encoding utf8
Write-Output $msi
