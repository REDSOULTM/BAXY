# During a falsehoods run: a game the model launched (any process under steamapps\common) is closed 20 s after it starts,
# and logged. On 2026-10-19 F001 (a game not installed) made c2-e1.0 launch Rocket League by mistake: 7 GB private,
# the commit limit ran out and the bench died (Errno 22, fork failures). Runs until the file <stop> exists.
param([string]$Stop, [string]$Log)
while (-not (Test-Path $Stop)) {
  Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -like '*\steamapps\common\*' } | ForEach-Object {
    $p = Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue
    if ($p -and ((Get-Date) - $p.StartTime).TotalSeconds -gt 20) {
      Add-Content -Path $Log -Value ("{0:HH:mm:ss} closed {1} ({2})" -f (Get-Date), $_.Name, $_.ProcessId)
      Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
  }
  Start-Sleep 5
}
