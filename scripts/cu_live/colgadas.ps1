# Windows whose program does not answer (harness only, read only). ASCII only (PowerShell 5.1 reads it as ANSI).
# usage: colgadas.ps1 [-Antes "<pids>"] [-Incompleta <verificacion-*.json> -Caso <id> -Fase <fase> -Tope <s>]
#   Prints one JSON line {"estado":"colgadas","colgadas":[{proceso,pid,hwnd,clase,titulo}],"resumen":"..."}: what
#   batch.sh names in "AVISO: verify sin respuesta (<resumen>)" when a verification ran out of its ceiling
#   (t-menu-1, 2026-10-09: a secondary explorer.exe hung behind an application error dialog held verify 11 min).
#   A title is given only for a window of a process born during the case (not in -Antes) or on a baxy-prueba folder;
#   the person's other windows say only their process.
#   -Incompleta: writes that verification file as cut by the ceiling (completa=false, motivo=sin_respuesta, the hung
#   windows), so a reviewer never reads it, or an earlier run's, as a complete verification.
param([string]$Antes='',[string]$Incompleta='',[string]$Caso='',[string]$Fase='',[int]$Tope=0)
. (Join-Path $PSScriptRoot 'estado\comun.ps1')
$ErrorActionPreference='Continue'
$previos=@($Antes -split '\s+' | Where-Object { $_ } | ForEach-Object { [int]$_ })
$l=@(foreach($c in @(Get-VentanasColgadas)){
  $nacida=($previos.Count -gt 0 -and $previos -notcontains [int]$c.pid)
  $t=$(if($nacida -or $c.titulo -match 'baxy-prueba'){ $c.titulo }else{ $null })
  [ordered]@{ proceso=$c.proceso; pid=$c.pid; hwnd=$c.hwnd; clase=$c.clase; titulo=$t; nacida_en_el_caso=$nacida }
})
$resumen=(@($l | ForEach-Object { if($_.titulo){ "$($_.titulo) [$($_.proceso) $($_.pid)]" }else{ "$($_.proceso) $($_.pid)" } }) -join '; ')
if(-not $resumen){ $resumen='ninguna ventana colgada a la vista' }
if($Incompleta){
  $d=Split-Path $Incompleta; if($d -and -not (Test-Path $d)){ New-Item -ItemType Directory -Force $d | Out-Null }
  $o=[ordered]@{ caso=$Caso; fase=$Fase; hora=(Get-Date).ToString('s'); completa=$false; motivo='sin_respuesta'; tope_s=$Tope; colgadas=@($l) }
  [IO.File]::WriteAllText($Incompleta,(($o | ConvertTo-Json -Depth 4)+"`n"),(New-Object Text.UTF8Encoding $false))
}
[ordered]@{ estado='colgadas'; colgadas=@($l); resumen=$resumen } | ConvertTo-Json -Compress -Depth 4
