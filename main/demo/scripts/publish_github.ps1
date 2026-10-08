param(
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$')][string]$RepositoryName,
    [ValidateSet('public','private')][string]$Visibility='private',
    [ValidatePattern('^[A-Za-z0-9-]+$')][string]$Owner,
    [string]$GithubCli='gh',
    [switch]$PrepareOnly
)
$ErrorActionPreference='Stop'
$demo=Split-Path $PSScriptRoot -Parent
$main=Split-Path $demo -Parent
$root=Split-Path $main -Parent
$metadata=Get-Content -LiteralPath (Join-Path $demo 'releases\manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$assetsDirectory=Join-Path $root ('junk\publish\'+$metadata.tag)
& (Join-Path $PSScriptRoot 'prepare_release_payload.ps1') -AssetsDirectory $assetsDirectory
$plan=Get-Content -LiteralPath (Join-Path $assetsDirectory 'upload-plan.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$git=(Get-Command git -ErrorAction Stop).Source
function Run-Git([string[]]$Arguments){$value=& $git @Arguments;if($LASTEXITCODE -ne 0){throw ('Git command failed: '+($Arguments -join ' '))};return $value}
Push-Location $root
try{
    $paths=@(Run-Git -Arguments @('-c','core.quotepath=false','ls-files','--cached','--others','--exclude-standard')) | Sort-Object -Unique
    foreach($path in $paths){
        if($path -notmatch '^(README\.md|\.gitignore|\.gitattributes|main/)' -or
           $path -match '^(junk/|main/reverse/private/|main/demo/build/)' -or
           $path -match '\.(exe|dll|msi|img|zip|nupkg)$' -or
           ($path -match '\.bin$' -and $path -notmatch '^main/reverse/evidence/protocol/(hello|hello_ack_example)\.bin$')){
            throw "File must not enter source repository: $path"
        }
    }
    if($PrepareOnly){
        [ordered]@{status='ready_local';repository_name=$RepositoryName;tag=$plan.tag;source_files=$paths.Count;release_assets=@($plan.assets | ForEach-Object {[IO.Path]::GetFileName($_)});network_or_git_write_executed=$false} | ConvertTo-Json -Depth 5
        return
    }
    if(-not $RepositoryName){throw 'Choose a repository name before publishing.'}
    $gh=(Get-Command $GithubCli -ErrorAction Stop).Source
    function Run-Gh([string[]]$Arguments){$value=& $gh @Arguments;if($LASTEXITCODE -ne 0){throw ('GitHub CLI command failed: '+($Arguments -join ' '))};return $value}
    $user=(Run-Gh -Arguments @('api','user')) | ConvertFrom-Json
    if($Owner -and $Owner -ne $user.login){throw 'Authenticated GitHub account differs from the requested owner.'}
    $Owner=$user.login
    $repository=$Owner+'/'+$RepositoryName
    $remoteUrl='https://github.com/'+$repository+'.git'
    $statePath=Join-Path $assetsDirectory 'publish-state.json'
    $state=if(Test-Path -LiteralPath $statePath){Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json}else{$null}
    $remotes=@(Run-Git -Arguments @('remote'))
    if($remotes -contains 'origin'){
        $origin=(Run-Git -Arguments @('remote','get-url','origin')).Trim()
        if($origin -notin @($remoteUrl,'git@github.com:'+ $repository+'.git')){throw 'Existing origin belongs to another repository.'}
    }
    $priorPreference=$ErrorActionPreference
    $ErrorActionPreference='Continue'
    $remoteText=& $gh api ('repos/'+$repository) 2>$null
    $remoteExit=$LASTEXITCODE
    $ErrorActionPreference=$priorPreference
    if($remoteExit -eq 0){
        if(-not ($remotes -contains 'origin') -and ($null -eq $state -or $state.repository -ne $repository)){
            throw 'Repository name already exists; no unrelated repository will be overwritten.'
        }
    }else{
        Run-Gh -Arguments @('repo','create',$repository,('--'+$Visibility),'--description','EC600U hardware reverse-engineering notes and QDisplay native C/C# demo') | Out-Null
        [IO.File]::WriteAllText($statePath,(@{repository=$repository;tag=$plan.tag;created=$true} | ConvertTo-Json),(New-Object Text.UTF8Encoding $false))
    }
    if(-not ($remotes -contains 'origin')){Run-Git -Arguments @('remote','add','origin',$remoteUrl) | Out-Null}
    $gitName=& $git config --get user.name
    if(-not $gitName){Run-Git -Arguments @('config','user.name',$user.login) | Out-Null}
    $gitEmail=& $git config --get user.email
    if(-not $gitEmail){Run-Git -Arguments @('config','user.email',($user.id.ToString()+'+'+$user.login+'@users.noreply.github.com')) | Out-Null}
    Run-Git -Arguments @('add','--','README.md','.gitignore','.gitattributes','main') | Out-Null
    $staged=@(Run-Git -Arguments @('diff','--cached','--name-only'))
    if($staged.Count){Run-Git -Arguments @('commit','-m',('Publish reverse-engineering notes and QDisplay demo '+$plan.tag)) | Out-Null}
    $head=(Run-Git -Arguments @('rev-parse','HEAD')).Trim()
    $tags=@(Run-Git -Arguments @('tag','--list',$plan.tag))
    if($tags.Count){
        $tagHead=(Run-Git -Arguments @('rev-parse',($plan.tag+'^{}'))).Trim()
        if($tagHead -ne $head){throw 'Existing version tag points to another commit; choose a new version.'}
    }else{Run-Git -Arguments @('tag','-a',$plan.tag,'-m',('QDisplay demo '+$plan.tag)) | Out-Null}
    $priorPath=$env:PATH
    try{
        # Use gh authentication only for these pushes; do not alter global credential settings.
        $env:PATH=(Split-Path $gh -Parent)+[IO.Path]::PathSeparator+$priorPath
        Run-Git -Arguments @('-c','credential.helper=','-c','credential.helper=!gh auth git-credential','push','-u','origin','HEAD:main') | Out-Null
        Run-Git -Arguments @('-c','credential.helper=','-c','credential.helper=!gh auth git-credential','push','origin',('refs/tags/'+$plan.tag)) | Out-Null
    }finally{$env:PATH=$priorPath}
    $priorPreference=$ErrorActionPreference
    $ErrorActionPreference='Continue'
    $releaseText=& $gh release view $plan.tag --repo $repository --json assets,isDraft,url 2>$null
    $releaseExit=$LASTEXITCODE
    $ErrorActionPreference=$priorPreference
    if($releaseExit -ne 0){
        Run-Gh -Arguments @('release','create',$plan.tag,'--repo',$repository,'--verify-tag','--draft','--prerelease','--title',('QDisplay demo '+$metadata.windows.version+' / '+$metadata.snapshot_date),'--notes-file',$plan.notes) | Out-Null
        $releaseText=Run-Gh -Arguments @('release','view',$plan.tag,'--repo',$repository,'--json','assets,isDraft,url')
    }
    $release=$releaseText | ConvertFrom-Json
    $verification=Join-Path $assetsDirectory 'github-verification'
    New-Item -ItemType Directory -Path $verification -Force | Out-Null
    foreach($asset in $plan.assets){
        $name=[IO.Path]::GetFileName($asset)
        if(@($release.assets | Where-Object {$_.name -eq $name}).Count -eq 0){
            if(-not $release.isDraft){throw 'Published Release is missing an asset; use a new version.'}
            Run-Gh -Arguments @('release','upload',$plan.tag,$asset,'--repo',$repository) | Out-Null
        }
        Run-Gh -Arguments @('release','download',$plan.tag,'--repo',$repository,'--pattern',$name,'--dir',$verification,'--clobber') | Out-Null
        if((Get-FileHash -LiteralPath $asset -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath (Join-Path $verification $name) -Algorithm SHA256).Hash){throw "Uploaded asset hash mismatch: $name"}
    }
    if($release.isDraft){Run-Gh -Arguments @('release','edit',$plan.tag,'--repo',$repository,'--draft=false') | Out-Null}
    [ordered]@{repository=('https://github.com/'+$repository);release=('https://github.com/'+$repository+'/releases/tag/'+$plan.tag);commit=$head;uploaded_assets_verified=$true} | ConvertTo-Json
}finally{Pop-Location}
