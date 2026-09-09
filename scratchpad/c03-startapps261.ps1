$ErrorActionPreference = 'Stop'
$catalogEvidenceRoot = Join-Path $env:LOCALAPPDATA 'BAXY/C03-retrieval261-private'
$catalogOutput = Join-Path $catalogEvidenceRoot 'START_APPS_STEAM.json'
if (Test-Path -LiteralPath $catalogOutput) { throw 'Evidence already exists' }
$catalogSteamRows = @(Get-StartApps | Where-Object Name -Match 'Steam' | Select-Object Name,AppID)
$catalogShell = New-Object -ComObject Shell.Application
try {
    $catalogFolder = $catalogShell.NameSpace('shell:AppsFolder')
    $catalogShellRows = @($catalogFolder.Items() | Where-Object Name -EQ 'Steam' | ForEach-Object {
        [pscustomobject]@{
            Name = $_.Name
            Path = $_.Path
            AppId = $_.ExtendedProperty('System.AppUserModel.ID')
            Target = $_.ExtendedProperty('System.Link.TargetParsingPath')
            Arguments = $_.ExtendedProperty('System.Link.Arguments')
            Link = $_.ExtendedProperty('System.Link.TargetSFGAOFlags')
        }
    })
    [pscustomobject]@{ StartApps = $catalogSteamRows; ShellItems = $catalogShellRows } |
        ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $catalogOutput -Encoding UTF8
    Get-Content -LiteralPath $catalogOutput -TotalCount 70
} finally {
    if ($null -ne $catalogFolder) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($catalogFolder) }
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($catalogShell)
}
