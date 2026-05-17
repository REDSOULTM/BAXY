# Launch Opera GX with CDP enabled so Gemma4 can attach for streaming auto-play.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File launch_opera_cdp.ps1
#
# Make a desktop shortcut to this script (or pin it in Start) to use it
# routinely. Tabs and login state are preserved (--user-data-dir points at
# the same profile Opera uses by default).

$ErrorActionPreference = "Stop"

# Resolve Opera GX path.
$opera_exe = "$env:LOCALAPPDATA\Programs\Opera GX\opera.exe"
if (-not (Test-Path $opera_exe)) {
    Write-Host "Opera GX not found at: $opera_exe" -ForegroundColor Red
    exit 1
}

$profile_dir = "$env:APPDATA\Opera Software\Opera GX Stable"
if (-not (Test-Path $profile_dir)) {
    Write-Host "Opera GX profile dir not found: $profile_dir" -ForegroundColor Yellow
}

# If Opera is already running WITHOUT CDP, we need to close it first
# (a second instance would create a new profile copy).
$running = Get-Process opera -ErrorAction SilentlyContinue
if ($running) {
    Write-Host "Opera GX is already running. Checking CDP..." -ForegroundColor Yellow
    try {
        Invoke-WebRequest -Uri 'http://127.0.0.1:9222/json/version' -TimeoutSec 2 -UseBasicParsing | Out-Null
        Write-Host "  -> CDP already enabled. Nothing to do." -ForegroundColor Green
        exit 0
    } catch {
        Write-Host "  -> No CDP. Closing Opera to relaunch with --remote-debugging-port..."
        $running | Stop-Process -Force
        Start-Sleep -Seconds 2
    }
}

# Launch Opera GX with CDP.
Start-Process -FilePath $opera_exe `
              -ArgumentList "--remote-debugging-port=9222","--user-data-dir=`"$profile_dir`""
Write-Host "Opera GX launched with CDP on port 9222." -ForegroundColor Green
Write-Host "Verify: http://127.0.0.1:9222/json/version"
