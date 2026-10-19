# Guardian for the PC's falsedades/e2e runs (as the notebook's, 2026-10-19): a game the model launched by mistake
# (F001 launched a real game on the notebook) is closed 20 s after it started, and noted; the model's receipt does not
# change. Only processes under steamapps\common that started after this guardian did, and only while a bench Baxy.exe
# (one with --command-dir) is open: a game of the owner's is never touched. Stops when the file named by -Stop exists.
param([Parameter(Mandatory = $true)][string]$Stop, [Parameter(Mandatory = $true)][string]$Log)
$start = Get-Date
while (-not (Test-Path $Stop)) {
    $bench = Get-CimInstance Win32_Process -Filter "Name = 'Baxy.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match '--command-dir' }
    if ($bench) {
        Get-Process -ErrorAction SilentlyContinue | Where-Object {
            $_.Path -and $_.Path -like '*\steamapps\common\*' -and $_.StartTime -gt $start -and
            ((Get-Date) - $_.StartTime).TotalSeconds -gt 20
        } | ForEach-Object {
            Add-Content -Encoding utf8 -Path $Log -Value ("{0:HH:mm:ss} cerrado {1} ({2}), arrancó {3:HH:mm:ss}" -f (Get-Date), $_.ProcessName, $_.Path, $_.StartTime)
            Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
        }
    }
    Start-Sleep -Seconds 5
}
