<#
.SYNOPSIS
  Adapt Chromium/Electron app shortcuts (Discord, Spotify, Chrome, Edge, Brave,
  Slack) so they ALWAYS launch with the full accessibility (UIA) tree enabled.
  This lets Gemma 4 Agent control them by control name (UIA click_button) instead
  of OCR/vision -- more precise, faster, more reliable.

.DESCRIPTION
  These apps are Chromium under the hood. By default they do NOT expose their
  accessibility tree to UI Automation, so an agent (or a screen reader) cannot
  "see" their buttons. The official Chromium flag
  --force-renderer-accessibility=complete enables it.

  The script adds that flag to each .lnk's arguments, saving a backup
  (.lnk.gemma4bak) of each one first. Fully reversible with -Revert.

  COST: +5-15% sustained CPU in those apps (they keep the tree serialized).
  Modest; fine for desktop use. If you do not want it, run -Revert.

  Does NOT touch VS Code (dev IDE) nor UWP apps (WhatsApp already exposes UIA).

.PARAMETER Revert
  Restores the original .lnk files from backups and deletes the backups.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\enable_app_accessibility.ps1
  powershell -ExecutionPolicy Bypass -File scripts\enable_app_accessibility.ps1 -WhatIf
  powershell -ExecutionPolicy Bypass -File scripts\enable_app_accessibility.ps1 -Revert

.NOTES
  For Gemma 4 Agent. When the AGENT opens these apps it already passes the flag
  (app_resolver._ax_launch_target). This script covers the case where YOU open them.
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [switch]$Revert
)

# Chromium flag that fills the UIA tree. 'complete' = full AXMode.
$FLAG = '--force-renderer-accessibility=complete'

# Target apps via SHORTCUT flag: browsers (Chromium puro). The CLI flag DOES
# reach their renderer. Discord is NOT here: it is Squirrel-packaged and SWALLOWS
# the CLI flag (validated 2026-05-25: shortcut flag -> 0 named UIA controls).
# Discord (and Electron apps with a config-based switch list) go through the
# settings.json path below instead (validated: 0 -> 273 named UIA controls).
$TARGETS = @('Spotify', 'Google Chrome', 'Chrome', 'Microsoft Edge', 'Brave')

# Electron apps that read chromiumSwitches from their own settings.json (the CLI
# flag does NOT work for them). {name = path to settings.json}. The switch goes
# as a JSON property "force-renderer-accessibility": "complete".
$ELECTRON_CONFIG_APPS = @{
    'Discord' = (Join-Path $env:APPDATA 'discord\settings.json')
}

# Standard .lnk locations in Windows.
$SEARCH_DIRS = @(
    [Environment]::GetFolderPath('Desktop'),
    [Environment]::GetFolderPath('CommonDesktopDirectory'),
    (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'),
    (Join-Path $env:ProgramData 'Microsoft\Windows\Start Menu\Programs')
) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -Unique

function Find-Shortcuts {
    $found = @()
    foreach ($dir in $SEARCH_DIRS) {
        Get-ChildItem -Path $dir -Filter '*.lnk' -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
            $base = [IO.Path]::GetFileNameWithoutExtension($_.Name)
            if ($TARGETS -contains $base) { $found += $_.FullName }
        }
    }
    return $found | Select-Object -Unique
}

$shell = New-Object -ComObject WScript.Shell

# Apps Electron config-based (Discord): agregar/quitar el switch en su settings.json.
function Set-ElectronConfigSwitch {
    param([string]$name, [string]$jsonPath, [switch]$Remove)
    if (-not (Test-Path $jsonPath)) {
        Write-Host "  $name`: no settings.json en $jsonPath (saltado)" -ForegroundColor DarkGray
        return
    }
    $bak = "$jsonPath.gemma4bak"
    if ($Remove) {
        if (Test-Path $bak) {
            if ($PSCmdlet.ShouldProcess($jsonPath, "Restore Discord settings")) {
                Copy-Item $bak $jsonPath -Force; Remove-Item $bak -Force
                Write-Host "  $name`: settings.json restaurado" -ForegroundColor Green
            }
        }
        return
    }
    if ($PSCmdlet.ShouldProcess($jsonPath, "Add force-renderer-accessibility to chromiumSwitches")) {
        if (-not (Test-Path $bak)) { Copy-Item $jsonPath $bak -Force }
        $j = Get-Content $jsonPath -Raw | ConvertFrom-Json
        if ($null -eq $j.chromiumSwitches) {
            $j | Add-Member -NotePropertyName chromiumSwitches -NotePropertyValue (New-Object PSObject) -Force
        }
        $j.chromiumSwitches | Add-Member -NotePropertyName 'force-renderer-accessibility' -NotePropertyValue 'complete' -Force
        $j | ConvertTo-Json -Depth 10 | Set-Content $jsonPath -Encoding utf8
        Write-Host "  $name`: chromiumSwitches actualizado (cerrá y reabrí Discord)" -ForegroundColor Green
    }
}

if ($Revert) {
    Write-Host "== REVERT: restoring original shortcuts + Electron configs ==" -ForegroundColor Cyan
    $n = 0
    foreach ($dir in $SEARCH_DIRS) {
        Get-ChildItem -Path $dir -Filter '*.lnk.gemma4bak' -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
            $orig = $_.FullName -replace '\.gemma4bak$', ''
            if ($PSCmdlet.ShouldProcess($orig, 'Restore from backup')) {
                Copy-Item $_.FullName $orig -Force
                Remove-Item $_.FullName -Force
                Write-Host "  restored: $orig"
                $n++
            }
        }
    }
    foreach ($name in $ELECTRON_CONFIG_APPS.Keys) {
        Set-ElectronConfigSwitch -name $name -jsonPath $ELECTRON_CONFIG_APPS[$name] -Remove
    }
    Write-Host "== $n shortcuts restored + Electron configs reverted ==" -ForegroundColor Green
    return
}

Write-Host "== Adapting Chromium/Electron apps for accessibility (Gemma 4) ==" -ForegroundColor Cyan
$shortcuts = Find-Shortcuts
$n = 0
foreach ($lnkPath in $shortcuts) {
    $lnk = $shell.CreateShortcut($lnkPath)
    $existing = $lnk.Arguments
    if ($existing -match [regex]::Escape($FLAG)) {
        Write-Host "  already has flag: $lnkPath" -ForegroundColor DarkGray
        continue
    }
    if ($PSCmdlet.ShouldProcess($lnkPath, "Add $FLAG")) {
        # backup BEFORE touching (reversible).
        $bak = "$lnkPath.gemma4bak"
        if (-not (Test-Path $bak)) { Copy-Item $lnkPath $bak -Force }
        $lnk.Arguments = ($existing + ' ' + $FLAG).Trim()
        $lnk.Save()
        Write-Host "  adapted: $lnkPath" -ForegroundColor Green
        $n++
    }
}
Write-Host "== $n browser shortcuts adapted (backup in *.lnk.gemma4bak) ==" -ForegroundColor Green

# Apps Electron config-based (Discord): editar su settings.json (VALIDADO:
# 0 -> 273 controles UIA con nombre tras esto). El flag CLI NO les sirve.
Write-Host "== Electron config-based apps (chromiumSwitches) ==" -ForegroundColor Cyan
foreach ($name in $ELECTRON_CONFIG_APPS.Keys) {
    Set-ElectronConfigSwitch -name $name -jsonPath $ELECTRON_CONFIG_APPS[$name]
}

Write-Host "To revert: powershell -ExecutionPolicy Bypass -File scripts\enable_app_accessibility.ps1 -Revert"
Write-Host "NOTE: close and reopen the apps for it to take effect (single-instance)." -ForegroundColor Yellow
