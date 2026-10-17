param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('desktop','documents','downloads','home','pictures')]
    [string]$Folder,
    # A folder inside the known one («BAXY-bench», «proyectos/tesis»), never above it.
    [string]$Subdirectory
)
$ErrorActionPreference='Stop'
# The runner reads stdout as UTF-8 (PowerShellCommand); PowerShell 5.1 otherwise writes the console's code page.
[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false)
$effect=$false
function Wait-BaxyPoll([DateTime]$Deadline,[int]$IntervalMilliseconds){
    $remaining=$Deadline-(Get-Date)
    if($remaining.TotalMilliseconds -le 0){return $false}
    $delay=[Math]::Max(
        1,
        [Math]::Min(
            $IntervalMilliseconds,
            [int][Math]::Ceiling($remaining.TotalMilliseconds)))
    Start-Sleep -Milliseconds $delay
    return $true
}
try {
    $path=switch($Folder){
        'desktop' {[Environment]::GetFolderPath('Desktop')}
        'documents' {[Environment]::GetFolderPath('MyDocuments')}
        'pictures' {[Environment]::GetFolderPath('MyPictures')}
        'home' {[Environment]::GetFolderPath('UserProfile')}
        'downloads' {(New-Object -ComObject Shell.Application).NameSpace('shell:Downloads').Self.Path}
    }
    $path=[IO.Path]::GetFullPath($path)
    if($Subdirectory -match '^([A-Za-z]:[\\/]|[\\/]{2})'){
        # A full path inside the folder is the same place as its relative path; one outside it is refused.
        $full=[IO.Path]::GetFullPath($Subdirectory)
        if(-not $full.StartsWith($path.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'known_path_outside_folder'}
        $Subdirectory=$full.Substring($path.TrimEnd('\').Length+1)
    }
    if($Subdirectory){
        $parts=@($Subdirectory -split '[\\/]')
        if([IO.Path]::IsPathRooted($Subdirectory) -or ($parts | Where-Object {$_ -in @('','.','..')})){throw 'known_subdirectory_invalid'}
        $inside=[IO.Path]::GetFullPath((Join-Path $path $Subdirectory))
        if(-not $inside.StartsWith($path.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'known_subdirectory_invalid'}
        $path=$inside
    }
    # Auditoría final (regla 3): only a path that is not there is «missing»; access denied, a path too long or a
    # network that does not answer is the folder not read (Test-Path says false for all of them).
    try{$item=Get-Item -LiteralPath $path -Force -ErrorAction Stop}
    catch [System.Management.Automation.ItemNotFoundException]{throw 'known_folder_missing'}
    catch{throw 'known_folder_not_read'}
    if(-not $item.PSIsContainer){throw 'known_folder_missing'}
    # Ronda final 32 (regla 3): only one more Explorer window or tab showing the folder than before the launch proves it
    # (a window the person already had open there proved nothing).
    $shell=New-Object -ComObject Shell.Application
    # Ronda final 33: a window whose location could not be read before counts as one that may already show the folder.
    $script:unread=0
    function Count-Showing {
        $count=0;$script:unread=0
        foreach($window in @($shell.Windows())){
            # Ronda final 34: only a window whose location cannot be read is unread; an empty or non-file location
            # (Inicio, Este equipo) is read and does not show the folder.
            try {$location=[string]$window.LocationURL} catch {$script:unread++;continue}
            if(-not $location.StartsWith('file:',[StringComparison]::OrdinalIgnoreCase)){continue}
            try {
                $observed=[Uri]::UnescapeDataString(([Uri]$location).LocalPath).TrimEnd('\')
                if([string]::Equals([IO.Path]::GetFullPath($observed),$path.TrimEnd('\'),[StringComparison]::OrdinalIgnoreCase)){$count++}
            } catch {}
        }
        $count
    }
    $before=Count-Showing
    $before+=$script:unread
    Start-Process explorer.exe -ArgumentList @($path)
    $effect=$true
    $deadline=(Get-Date).AddSeconds(8)
    $verified=$false
    do {
        if((Count-Showing) -gt $before){$verified=$true;break}
    } while((Wait-BaxyPoll $deadline 250))
    [pscustomobject]@{version=1;ok=$verified;effectObserved=$effect;folder=$Folder;subdirectory=$Subdirectory;verifiedPathName=[IO.Path]::GetFileName($path);authority='windows_shell_location_postread';error=$(if($verified){$null}else{'known_folder_window_not_verified'})}|ConvertTo-Json -Compress
    if(-not $verified){exit 2}
} catch {
    # The script's own refusals keep their code, so the model learns why (a subfolder that is not there, a path outside).
    $code=if($_.Exception.Message -match '^known_[a-z_]+$'){$_.Exception.Message}else{'known_folder_open_failed'}
    [pscustomobject]@{version=1;ok=$false;effectObserved=$effect;error=$code}|ConvertTo-Json -Compress
    exit 2
}
