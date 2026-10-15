# State reloj_por_defecto: the Clock app on the tab it opens on, "Temporizador" (TimerButton).
# Measured 2026-10-07 on this PC: a fresh Clock opens on Temporizador whatever tab it was closed on (left on Cronómetro
# and on Sesiones de concentración, it reopened on Temporizador both times). So a closed Clock is already in its base
# state and is not opened; an open one is put back on that tab with SelectionItemPattern (no click).
if(-not ('EstadoW32' -as [type])){ . (Join-Path $PSScriptRoot 'comun.ps1') }
$E='reloj_por_defecto'
$Defecto='TimerButton'
$Tabs='FocusButton','TimerButton','AlarmButton','StopwatchButton','ClockButton'

function Get-ClockTab($W){
  foreach($id in $Tabs){
    $i=Find-ById $W $id
    if($i){ $p=$null; if($i.TryGetCurrentPattern([Windows.Automation.SelectionItemPattern]::Pattern,[ref]$p) -and $p.Current.IsSelected){ return $id } }
  }
  'desconocida'
}

$fg=Get-Foreground
$wins=@(Find-TopWindowByName 'Reloj')
if($wins.Count -eq 0){ Write-Estado $E 'ok' @{ verificado=$true; ventana='cerrada'; nota='Reloj cerrado: abre en Temporizador' }; return }
$out=@()
foreach($w in $wins){
  $antes=Get-ClockTab $w
  if($antes -ne $Defecto){
    $item=Find-ById $w $Defecto
    if($item){ $item.GetCurrentPattern([Windows.Automation.SelectionItemPattern]::Pattern).Select() }
    for($i=0;$i -lt 20 -and (Get-ClockTab $w) -ne $Defecto;$i++){ Start-Sleep -Milliseconds 150 }
  }
  $out+=[pscustomobject]@{ antes=$antes; despues=(Get-ClockTab $w) }
}
$ok=@($out | Where-Object { $_.despues -ne $Defecto }).Count -eq 0
$cambio=@($out | Where-Object { $_.antes -ne $Defecto }).Count -gt 0
# Selecting a tab can bring the Clock to the front: the window that had the foreground gets it back.
$foco=Restore-Foreground $fg @('ApplicationFrameHost','Time')
$r=if(-not $ok){ 'no_verificado' }elseif($cambio){ 'corregido' }else{ 'ok' }
Write-Estado $E $r @{ verificado=$ok; ventana='abierta'; pestana_antes=@($out | ForEach-Object { $_.antes }); pestana=@($out | ForEach-Object { $_.despues }); foco=$foco }
