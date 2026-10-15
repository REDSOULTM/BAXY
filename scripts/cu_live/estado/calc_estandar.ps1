# State calc_estandar: Calculator in Standard mode, angle unit in degrees (DEG), display 0.
# The Calculator remembers its mode across launches, so a closed Calculator is opened, fixed and closed again
# (the harness opened it, so it closes it by that exact window). Everything is done through UIA patterns.
# A Calculator already open is reset only when it is the harness's (propios.jsonl, or proven the batch's by the
# ledger); the person's is never touched (ajena_abierta).
if(-not ('EstadoW32' -as [type])){ . (Join-Path $PSScriptRoot 'comun.ps1') }
. (Join-Path $PSScriptRoot 'apps_comun.ps1')
. (Join-Path $PSScriptRoot 'decisiones_comun.ps1')
$E='calc_estandar'

function Get-CalcMode($W){
  # The header ("Modo de calculadora Científica") is always in the tree; the nav items only while the pane is built.
  $h=Find-ById $W 'Header'
  if($h){
    $n=$h.Current.Name
    foreach($m in @(@('Est.ndar|Standard','Standard'),@('Cient.fica|Scientific','Scientific'),@('Programador|Programmer','Programmer'),@('Graficar|Graphing','Graphing'),@('fecha|Date','Date'))){
      if($n -match $m[0]){ return $m[1] }
    }
  }
  foreach($id in 'Standard','Scientific','Programmer','Graphing','Date'){
    $i=Find-ById $W $id
    if($i){ $p=$null; if($i.TryGetCurrentPattern([Windows.Automation.SelectionItemPattern]::Pattern,[ref]$p) -and $p.Current.IsSelected){ return $id } }
  }
  $h=Find-ById $W 'Header'; if($h){ return "header:$($h.Current.Name)" }
  'desconocido'
}

function Set-CalcMode($W,[string]$Id){
  # The nav items exist only while the pane is open; the pane may still be animating, or the app still loading.
  $item=Find-ById $W $Id
  for($try=0;$try -lt 3 -and -not $item;$try++){
    $t=Find-ById $W 'TogglePaneButton'
    if($t -and $t.Current.Name -notmatch 'Cerrar|Close'){ [void](Invoke-Element $t) }
    for($i=0;$i -lt 8 -and -not $item;$i++){ Start-Sleep -Milliseconds 150; $item=Find-ById $W $Id }
  }
  if(-not $item){ throw "sin el modo $Id en la navegacion" }
  $p=$item.GetCurrentPattern([Windows.Automation.SelectionItemPattern]::Pattern)
  if(-not $p.Current.IsSelected){ $p.Select() }
  for($i=0;$i -lt 20;$i++){ Start-Sleep -Milliseconds 150; if($p.Current.IsSelected -and (Find-ById $W 'CalculatorResults')){ break } }
  # The pane stays open after a programmatic Select on some builds: close it again by its own button.
  $t=Find-ById $W 'TogglePaneButton'
  if($t -and $t.Current.Name -match 'Cerrar|Close'){ [void](Invoke-Element $t) }
}

function Get-Angle($W){
  foreach($id in 'degButton','radButton','gradButton'){ if(Find-ById $W $id){ return $id } }
  $null
}

$hechos=@()
$abierta=$false
$fg=Get-Foreground
$wins=@(Find-TopWindowByName 'Calculadora')
if($wins.Count -gt 1){ Write-Estado $E 'varias_calculadoras' @{ verificado=$false; ventanas=$wins.Count }; return }
if($wins.Count -eq 1){
  # A Calculator already open is changed (mode, angle unit, display) only when it is the harness's: recorded in
  # propios.jsonl or proven the batch's by the ledger. The person's (a half-done calculation in Programmer mode,
  # review r10a) is never touched (Get-DecisionVentanaPrevia).
  $h=[long]$wins[0].Current.NativeWindowHandle
  $tw=@((Get-TopWindows) | Where-Object { [long]$_.hwnd -eq $h })[0]
  $delLote=@(if($tw -and (Test-ProcesoDelLote ([int]$tw.app_pid))){ Get-VentanasLoteDelPid ([int]$tw.app_pid) })
  if((Get-DecisionVentanaPrevia $h @(Get-Propios | ForEach-Object { [long]$_.hwnd }) $delLote) -ne 'del_arnes'){
    Write-Estado $E 'ajena_abierta' @{ verificado=$false; nota='hay una Calculadora que el arnes no abrio: no se toca' }; return
  }
}
if($wins.Count -eq 0){
  Start-Process 'calculator:'
  for($i=0;$i -lt 60 -and $wins.Count -eq 0;$i++){ Start-Sleep -Milliseconds 150; $wins=@(Find-TopWindowByName 'Calculadora') }
  if($wins.Count -eq 0){ Write-Estado $E 'no_abre' @{ verificado=$false }; return }
  $abierta=$true; $hechos+='abierta_por_el_arnes'
  for($i=0;$i -lt 30 -and -not (Find-ById $wins[0] 'CalculatorResults');$i++){ Start-Sleep -Milliseconds 150 }
}
$w=$wins[0]
$modoAntes=$null; $angAntes=$null; $ang=$null; $modo=$null; $res=$null; $expr=$null; $ok=$false; $fallo=$null; $alFrente=$false
try{
  $modoAntes=Get-CalcMode $w
  # Degrees: the angle button only exists in Scientific mode, and the unit lives on in this Calculator session.
  if($modoAntes -ne 'Scientific'){ Set-CalcMode $w 'Scientific'; $hechos+='cientifica' }
  $ang=Get-Angle $w; $angAntes=$ang
  for($i=0;$i -lt 3 -and $ang -and $ang -ne 'degButton';$i++){
    [void](Invoke-Element (Find-ById $w $ang)); Start-Sleep -Milliseconds 300; $ang=Get-Angle $w
  }
  if($angAntes -ne $ang){ $hechos+="angulo:$angAntes a $ang" }
  Set-CalcMode $w 'Standard'; $hechos+='estandar'
  $c=Find-ById $w 'clearButton'; if($c){ [void](Invoke-Element $c); Start-Sleep -Milliseconds 200; $hechos+='borrar' }
  # Verification: read it back.
  $modo=Get-CalcMode $w
  $res=(Find-ById $w 'CalculatorResults').Current.Name
  $x=Find-ById $w 'CalculatorExpression'; if($x){ $expr=$x.Current.Name }
  $ok=($modo -eq 'Standard' -and $ang -eq 'degButton' -and ($res -match '(^|\s)0$'))
} catch {
  $fallo=$_.Exception.Message
} finally {
  # A Calculator the harness opened is always closed again, also after a failure.
  if($abierta){
    $alFrente=([EstadoW32]::GetForegroundWindow() -eq [IntPtr]$w.Current.NativeWindowHandle)
    try{ Close-WindowExact $w; $hechos+='cerrada_por_el_arnes' }catch{}
    for($i=0;$i -lt 20 -and @(Find-TopWindowByName 'Calculadora').Count -gt 0;$i++){ Start-Sleep -Milliseconds 150 }
  }
}
$foco=Restore-Foreground $fg @('ApplicationFrameHost','CalculatorApp') -TrasCerrar:([bool]$alFrente)
$resultado=if($fallo){ 'error' }elseif(-not $ok){ 'no_verificado' }elseif($modoAntes -eq 'Standard' -and $angAntes -eq 'degButton' -and -not $abierta){ 'ok' }else{ 'corregido' }
$datos=@{ verificado=$ok; modo_antes=$modoAntes; modo=$modo; angulo=$ang; pantalla=$res; expresion=$expr; hechos=$hechos; foco=$foco }
if($fallo){ $datos['error']=$fallo }
Write-Estado $E $resultado $datos
