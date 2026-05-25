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

# Target apps: .lnk name (no extension) as shown. Chromium and Electron alike
# (Electron IS Chromium -> the flag propagates to the renderer).
# Excludes 'Visual Studio Code' (IDE) and UWP (WhatsApp).
$TARGETS = @('Discord', 'Spotify', 'Google Chrome', 'Chrome', 'Microsoft Edge',
             'Brave', 'Slack')

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

if ($Revert) {
    Write-Host "== REVERT: restoring original shortcuts ==" -ForegroundColor Cyan
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
    Write-Host "== $n shortcuts restored ==" -ForegroundColor Green
    return
}

Write-Host "== Adapting Chromium/Electron apps for accessibility (Gemma 4) ==" -ForegroundColor Cyan
$shortcuts = Find-Shortcuts
if (-not $shortcuts) {
    Write-Host "No shortcuts found for: $($TARGETS -join ', ')" -ForegroundColor Yellow
    Write-Host "(Apps may open from a pinned taskbar item or be UWP -- the agent still passes the flag when IT opens them.)"
    return
}

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
Write-Host "== $n shortcuts adapted (backup in *.lnk.gemma4bak) ==" -ForegroundColor Green
Write-Host "To revert: powershell -ExecutionPolicy Bypass -File scripts\enable_app_accessibility.ps1 -Revert"
Write-Host "NOTE: close and reopen the apps for it to take effect (single-instance)." -ForegroundColor Yellow
