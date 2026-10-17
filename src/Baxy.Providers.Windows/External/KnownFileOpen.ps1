param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('desktop','documents','downloads','home','pictures')]
    [string]$Folder
)
$ErrorActionPreference='Stop'
# The runner reads stdout as UTF-8 (PowerShellCommand); PowerShell 5.1 otherwise writes the console's code page.
[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false)
$effect=$false
$safeExtensions=@(
    '.txt','.md','.log','.pdf','.rtf','.doc','.docx','.xls','.xlsx','.ppt','.pptx',
    '.csv','.tsv','.json','.xml','.yaml','.yml','.png','.jpg','.jpeg','.gif','.bmp',
    '.webp','.svg','.mp3','.wav','.m4a','.flac','.mp4','.mkv','.mov','.webm','.zip','.7z'
)
try {
    $path=switch($Folder){
        'desktop' {[Environment]::GetFolderPath('Desktop')}
        'documents' {[Environment]::GetFolderPath('MyDocuments')}
        'pictures' {[Environment]::GetFolderPath('MyPictures')}
        'home' {[Environment]::GetFolderPath('UserProfile')}
        'downloads' {(New-Object -ComObject Shell.Application).NameSpace('shell:Downloads').Self.Path}
    }
    $path=[IO.Path]::GetFullPath($path)
    # Auditoría final (regla 3): only a path that is not there is «missing»; access denied, a path too long or a
    # network that does not answer is the folder not read (Test-Path says false for all of them).
    try{$item=Get-Item -LiteralPath $path -Force -ErrorAction Stop}
    catch [System.Management.Automation.ItemNotFoundException]{throw 'known_folder_missing'}
    catch{throw 'known_folder_not_read'}
    if(-not $item.PSIsContainer){throw 'known_folder_missing'}
    $file=Get-ChildItem -LiteralPath $path -File -Force |
        Where-Object { $safeExtensions -contains $_.Extension.ToLowerInvariant() } |
        Sort-Object LastWriteTimeUtc,Name -Descending |
        Select-Object -First 1
    if($null -eq $file){throw 'safe_latest_file_not_found'}
    $startInfo=[Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName=$file.FullName
    $startInfo.UseShellExecute=$true
    $process=[Diagnostics.Process]::Start($startInfo)
    $effect=$true
    # Ronda final 22 (regla 3): a live process is no proof the file opened (Word alive under «el archivo está dañado»):
    # the proof is a window whose title names the file, as file.open's; the process id goes as data.
    $stem=[IO.Path]::GetFileNameWithoutExtension($file.Name)
    $title=$null
    for($look=0;$look -lt 16 -and $null -eq $title;$look++){
        Start-Sleep -Milliseconds 250
        $shown=Get-Process -ErrorAction SilentlyContinue | Where-Object {
            $_.MainWindowTitle -and $_.MainWindowTitle.IndexOf($stem,[StringComparison]::OrdinalIgnoreCase) -ge 0 } |
            Select-Object -First 1
        if($null -ne $shown){$title=$shown.MainWindowTitle}
    }
    $verified=$null -ne $title
    [pscustomobject]@{
        version=1;ok=$verified;effectObserved=$effect;folder=$Folder
        fileName=$file.Name;lastWriteUtc=$file.LastWriteTimeUtc.ToString('O')
        processId=$(if($null -eq $process){$null}else{$process.Id})
        windowTitle=$title
        authority='known_folder_latest_safe_file_window_title_postread'
        error=$(if($verified){$null}else{'latest_file_open_not_verified'})
    }|ConvertTo-Json -Compress
    if(-not $verified){exit 2}
} catch {
    [pscustomobject]@{version=1;ok=$false;effectObserved=$effect;error='latest_file_open_failed'}|ConvertTo-Json -Compress
    exit 2
}
