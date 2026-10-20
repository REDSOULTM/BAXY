# During a falsehoods run: any game the model launched (a process under steamapps\common) is closed AT ONCE and logged.
# On 2026-10-19 F001 (a game not installed) made c2-e1.0 launch Rocket League by mistake: 7 GB private, the commit limit
# ran out and the bench died; on 2026-10-20 03:35 it opened again in front of the owner. Polls every second until the
# file <stop> exists.
param([string]$Stop, [string]$Log)
while (-not (Test-Path $Stop)) {
  Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -like '*\steamapps\common\*' } | ForEach-Object {
    Add-Content -Path $Log -Value ("{0:HH:mm:ss} closed {1} ({2})" -f (Get-Date), $_.Name, $_.ProcessId)
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
  }
  Start-Sleep -Milliseconds 1000
}
