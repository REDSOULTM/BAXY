param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('desktop','documents','downloads','pictures')]
    [string]$Folder
)
$ErrorActionPreference='Stop'
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
        'downloads' {(New-Object -ComObject Shell.Application).NameSpace('shell:Downloads').Self.Path}
    }
    $path=[IO.Path]::GetFullPath($path)
    if(-not (Test-Path -LiteralPath $path -PathType Container)){throw 'known_folder_missing'}
    Start-Process explorer.exe -ArgumentList @($path)
    $effect=$true
    $shell=New-Object -ComObject Shell.Application
    $deadline=(Get-Date).AddSeconds(8)
    $verified=$false
    do {
        foreach($window in @($shell.Windows())){
            try {
                $observed=[Uri]::UnescapeDataString(([Uri]$window.LocationURL).LocalPath).TrimEnd('\')
                if([string]::Equals([IO.Path]::GetFullPath($observed),$path.TrimEnd('\'),[StringComparison]::OrdinalIgnoreCase)){
                    $verified=$true
                    break
                }
            } catch {}
        }
        if($verified){break}
    } while((Wait-BaxyPoll $deadline 250))
    [pscustomobject]@{version=1;ok=$verified;effectObserved=$effect;folder=$Folder;verifiedPathName=[IO.Path]::GetFileName($path);authority='windows_shell_location_postread';error=$(if($verified){$null}else{'known_folder_window_not_verified'})}|ConvertTo-Json -Compress
    if(-not $verified){exit 2}
} catch {
    [pscustomobject]@{version=1;ok=$false;effectObserved=$effect;error='known_folder_open_failed'}|ConvertTo-Json -Compress
    exit 2
}
