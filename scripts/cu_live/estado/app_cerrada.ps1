# State app_cerrada:<process name | Start menu name | *>: no window of that app that the harness opened is left.
#  - Only items in propios.jsonl (what the harness opened) are closed: by their window, and a process the harness
#    started is stopped by its exact PID only when its window will not go (a save prompt of a test document).
#  - A copy the harness did not open is the person's: never touched; the line says ajena_abierta (verificado=false,
#    because the case will not start from a closed app).
#  - '*' closes everything the harness opened (end of a batch).
#  - Inside a batch, a window the batch ledger POSITIVELY proves the batch's (ventanas_lote: one BAXY's app.open opened
#    whose close failed, exploradores.ps1) is not the person's: it is closed by that exact window (Get-DecisionAjenaApp)
#    and read back; one that stays is no_cierra, never ajena_abierta (pasada r18, v3-44: the Control Panel BAXY opened
#    in v3-43 was called the person's and the case ran on it).
param([string]$Arg='')
if(-not ('EstadoW32' -as [type])){ . (Join-Path $PSScriptRoot 'comun.ps1') }
. (Join-Path $PSScriptRoot 'apps_comun.ps1')
. (Join-Path $PSScriptRoot 'decisiones_comun.ps1')
$E="app_cerrada:$Arg"
if(-not $Arg){ Write-Estado $E 'sin_argumento' @{ verificado=$false }; return }
$fg=Get-Foreground
$global:AppsActivadaTrasCerrar=[IntPtr]::Zero
$res=@(Close-AppsPropias $Arg)
# The foreground goes back only when a window the harness closed WAS in front and the window Windows activated in its
# place is still the one in front; if the person moved meanwhile (or nothing was closed), nothing is touched.
$foco=Get-DecisionFoco ([long]$global:AppsActivadaTrasCerrar) ([long](Get-Foreground))
if($foco -eq 'devolver'){ $foco=Restore-Foreground $fg @() -TrasCerrar }
$fallos=@($res | Where-Object { $_ -like '*:no_cierra*' })
if($Arg -eq '*'){ Write-Estado $E ($(if($fallos.Count){'no_verificado'}elseif($res.Count){'corregido'}else{'ok'})) @{ verificado=($fallos.Count -eq 0); cerradas=$res; foco=$foco }; return }
# The person's copies: by process name when $Arg is one, otherwise by the Start-menu name.
$porProceso=@(Get-Process -Name $Arg -ErrorAction SilentlyContinue)
# Windows of the harness that would not close are counted in $fallos, not here.
$mias=@(Get-Propios | ForEach-Object { [long]$_.hwnd })
$ajenas=@(if($porProceso.Count -gt 0){ (Get-TopWindows) | Where-Object { ($_.app_proceso -eq $Arg -or $_.proceso -eq $Arg) -and $mias -notcontains $_.hwnd } }else{ $s=Resolve-StartApp $Arg; Get-AjenasDe $(if($s){ $s.Name }else{ $Arg }) '' })
# Inside a batch, a copy an earlier case left (born in the batch) is not the person's: it exits, then is read again.
if($ajenas.Count -gt 0){
  $res+=@(Close-AjenasDelLote $ajenas); $fallos=@($res | Where-Object { $_ -like '*:no_cierra*' })
  $ajenas=@(if($porProceso.Count -gt 0){ (Get-TopWindows) | Where-Object { ($_.app_proceso -eq $Arg -or $_.proceso -eq $Arg) -and $mias -notcontains $_.hwnd } }else{ $s=Resolve-StartApp $Arg; Get-AjenasDe $(if($s){ $s.Name }else{ $Arg }) '' })
  $libro=Get-LibroLote
  $vl=@(if($libro){ $libro.ventanas_lote })
  $deLote=@($ajenas | Where-Object { (Get-DecisionAjenaApp ([long]$_.hwnd) $vl) -eq 'cerrar_lote' } | ForEach-Object { [long]$_.hwnd })
  if($deLote.Count){
    foreach($h in $deLote){ try{ Close-WindowExact ([Windows.Automation.AutomationElement]::FromHandle([IntPtr]$h)) }catch{} }
    $fin=(Get-Date).AddSeconds(3)
    do{ $siguen=@($deLote | Where-Object { [EstadoW32]::IsWindow([IntPtr]$_) }); if(-not $siguen.Count){ break }; Start-Sleep -Milliseconds 200 }while((Get-Date) -lt $fin)
    foreach($h in $deLote){ $res+=$(if($siguen -contains $h){ "ventana_lote:$($h):no_cierra" }else{ "ventana_lote:$($h):cerrada" }) }
    $fallos=@($res | Where-Object { $_ -like '*:no_cierra*' })
    $ajenas=@(if($porProceso.Count -gt 0){ (Get-TopWindows) | Where-Object { ($_.app_proceso -eq $Arg -or $_.proceso -eq $Arg) -and $mias -notcontains $_.hwnd } }else{ $s=Resolve-StartApp $Arg; Get-AjenasDe $(if($s){ $s.Name }else{ $Arg }) '' })
    # A batch window still there is a failed close (no_cierra above), not a copy of the person's.
    $ajenas=@($ajenas | Where-Object { $deLote -notcontains [long]$_.hwnd })
  }
}
$r=if($fallos.Count){ 'no_verificado' }elseif($ajenas.Count){ 'ajena_abierta' }elseif($res.Count){ 'corregido' }else{ 'ok' }
Write-Estado $E $r @{ verificado=($fallos.Count -eq 0 -and $ajenas.Count -eq 0); cerradas=$res; ajenas=@($ajenas | ForEach-Object { $_.titulo }); foco=$foco }
