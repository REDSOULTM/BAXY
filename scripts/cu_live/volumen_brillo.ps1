# Master volume and brightness around one live case (cu_live.sh), in ONE powershell instead of seven (two reads before,
# three sets and two reads after: ~3 s a case). Uses scripts/semantic_replay_state.ps1 in this process.
#   volumen_brillo.ps1 -Leer                                   prints "<volume json> <brightness json>"
#   volumen_brillo.ps1 -Devolver -Nivel n -Silencio 0|1 [-Brillo n]
#        gives back what the case changed (a value already equal is not set again: setting it was a no-op) and prints
#        the line read back afterwards, as -Leer.
# ASCII only (PowerShell 5.1 reads it as ANSI).
param([switch]$Leer,[switch]$Devolver,[int]$Nivel=-1,[int]$Silencio=-1,[int]$Brillo=-1)
$s=Join-Path (Split-Path $PSScriptRoot) 'semantic_replay_state.ps1'
if($Devolver){
  $v=(& $s volume get) | ConvertFrom-Json
  if($Nivel -ge 0 -and [int]$v.level -ne $Nivel){ & $s volume set $Nivel | Out-Null }
  if($Silencio -ge 0 -and [bool]$v.muted -ne ($Silencio -ne 0)){ & $s volume mute $Silencio | Out-Null }
  if($Brillo -ge 0){
    $b=(& $s brightness get) | ConvertFrom-Json
    if(@(@($b.levels) | Where-Object { [int]$_ -ne $Brillo }).Count -gt 0){ & $s brightness set $Brillo | Out-Null }
  }
}
'{0} {1}' -f (& $s volume get),(& $s brightness get)
