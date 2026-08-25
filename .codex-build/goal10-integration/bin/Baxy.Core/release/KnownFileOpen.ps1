param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('desktop','documents','downloads','pictures')]
    [string]$Folder
)
$ErrorActionPreference='Stop'
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
        'downloads' {(New-Object -ComObject Shell.Application).NameSpace('shell:Downloads').Self.Path}
    }
    $path=[IO.Path]::GetFullPath($path)
    if(-not (Test-Path -LiteralPath $path -PathType Container)){throw 'known_folder_missing'}
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
    $verified=$false
    if($null -ne $process){
        # A live process must still survive the original 350 ms stability
        # horizon. WaitForExit preserves that success criterion while allowing
        # a terminal process failure to return as soon as it is observable.
        $exited=$process.WaitForExit(350)
        $verified=-not $exited -and -not $process.HasExited
    }
    [pscustomobject]@{
        version=1;ok=$verified;effectObserved=$effect;folder=$Folder
        fileName=$file.Name;lastWriteUtc=$file.LastWriteTimeUtc.ToString('O')
        processId=$(if($null -eq $process){$null}else{$process.Id})
        authority='known_folder_latest_safe_file_process_postread'
        error=$(if($verified){$null}else{'latest_file_process_not_verified'})
    }|ConvertTo-Json -Compress
    if(-not $verified){exit 2}
} catch {
    [pscustomobject]@{version=1;ok=$false;effectObserved=$effect;error='latest_file_open_failed'}|ConvertTo-Json -Compress
    exit 2
}
