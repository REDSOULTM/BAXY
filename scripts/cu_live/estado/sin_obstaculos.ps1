# State sin_obstaculos[:<process>]: read-only check that nothing hides the case's application before it starts
# (banco r6 2026-10-08: eight cases that passed before failed on what earlier cases and tandas left on the desktop).
#  - encima: visible always-on-top windows of a program that is neither the shell, the harness nor BAXY, covering at
#    least a tenth of the primary screen (the On-Screen Keyboard a case opened at 02:25 sat over every later case).
#  - dialogos: with <process>, each running copy whose main window a dialog it owns disables (a save prompt left by an
#    earlier case or tanda: Excel and Word showed BAXY only their 'Guardar este archivo', zero steps possible).
#  - a dialog over a window of an app of the batch or the harness (any process): cancelled, then read again (below).
#  - elevadas: an elevated process with a visible window that the batch or the harness is proven to have started
#    (Taskmgr, an MMC console BAXY opened in a case) is closed by its exact PID (below); anybody else's never is.
# Never closes another window, and never touches the person's (what is there may be theirs): resultado 'ok' | 'corregido'
# (verificado) or 'obstruido' (verificado=false: batch.sh says AVISO, and the case did not start from its base state;
# the judge leaves it out).
param([string]$Arg='')
if(-not ('EstadoW32' -as [type])){ . (Join-Path $PSScriptRoot 'comun.ps1') }
. (Join-Path $PSScriptRoot 'apps_comun.ps1')
. (Join-Path $PSScriptRoot 'decisiones_comun.ps1')
if(-not ('EstadoEncima' -as [type])){
Add-Type @"
using System; using System.Runtime.InteropServices;
public static class EstadoEncima {
  [DllImport("user32.dll")] static extern int GetWindowLong(IntPtr h, int i);
  [DllImport("user32.dll")] static extern int GetSystemMetrics(int i);
  // WS_EX_TOPMOST (0x8) in GWL_EXSTYLE (-20).
  public static bool Topmost(IntPtr h){ return (GetWindowLong(h,-20) & 0x8)!=0; }
  public static int Ancho(){ return GetSystemMetrics(0); }
  public static int Alto(){ return GetSystemMetrics(1); }
}
"@
}
$E=$(if($Arg){ "sin_obstaculos:$Arg" }else{ 'sin_obstaculos' })
# Harness data, never product code: the shell, the harness (its interpreters, the simulated user's window), the
# agents' terminals and editors, and BAXY itself (Get-ExcluidosObstaculos, decisiones_comun.ps1).
$excluidos=@(Get-ExcluidosObstaculos)
$nombres=@{}
function Get-NombreProceso([int]$ProcessId){
  if(-not $nombres.ContainsKey($ProcessId)){ $nombres[$ProcessId]=[string](Get-Process -Id $ProcessId -ErrorAction SilentlyContinue).ProcessName }
  $nombres[$ProcessId]
}
# Elevated windows (pasada r9: a Taskmgr, two Resource Monitors and a Services console BAXY opened elevated, and
# elevated consoles, stayed over the next cases; Taskmgr is single-instance, so the next Taskmgr case got the elevated
# one, unreadable). Only an elevated process with a visible window that the batch ledger classed 'lote' (born in a case
# of this batch: Test-ProcesoDelLote) or the harness book holds is closed by its exact PID (Stop-ProcesoElevado: an
# elevated normal close, then an elevated stop, where UAC does not ask). Never: anything else (the person's admin
# terminal, an installer, another agent's windows: revision 2026-10-08), VS Code, the Claude app, the shell, the
# terminals and interpreters ($excluidos), BAXY, the harness's own process chain, anything an agent's tool started,
# the app a state just opened for this case (propios.jsonl), or anything at all when the harness itself runs elevated
# (UAC off: it reads those windows). One that cannot be closed is named in elevadas_quedan, and the case is obstruido.
# Before the reads below: an elevated window always on top (the On-Screen Keyboard) is closed here too.
$protegidosElev=@(Get-ProtegidosElevadas)+@($global:AppsProhibidos)+@($global:AppsHosts)
$propiosH=@(Get-Propios | ForEach-Object { [long]$_.hwnd })
$elevadas=@(); $elevadasQuedan=@()
$filasElev=@(foreach($v in @(Get-VentanasVisibles)){ [pscustomobject]@{ pid=[int]$v.pid; hwnd=[long]$v.hwnd; proceso=(Get-NombreProceso $v.pid); elevada=(Test-Elevada ([int]$v.pid)) } })
if(@($filasElev | Where-Object { $_.elevada -eq $true }).Count){
  $tabla=@{}; foreach($c in @(Get-ProcesosCim)){ $tabla[[int]$c.pid]=$c }
  $cadena=@($PID)+@(Get-AncestrosProceso $tabla $PID)
  $deAgente=@(foreach($x in @($filasElev | Where-Object { $_.elevada -eq $true } | ForEach-Object { $_.pid } | Select-Object -Unique)){
    if(@(Get-AncestrosProceso $tabla $x | Where-Object { @('Code','Claude') -contains [string]$tabla[[int]$_].nombre }).Count){ $x } })
  $libroElev=Get-ProcesosArnes
  $delLote=@(foreach($x in @($filasElev | Where-Object { $_.elevada -eq $true } | ForEach-Object { $_.pid } | Select-Object -Unique)){
    if(($tabla.ContainsKey([int]$x) -and $libroElev.ContainsKey([string]$tabla[[int]$x].clave)) -or (Test-ProcesoDelLote ([int]$x))){ $x } })
  foreach($x in @(Get-DecisionElevadas $filasElev $protegidosElev $propiosH $cadena $deAgente $delLote ((Test-Elevada $PID) -eq $true))){
    $r=Stop-ProcesoElevado $x.pid $x.proceso
    $elevadas+="$($x.proceso):$($x.pid):$r"
    if($r -like 'no_cierra*'){ $elevadasQuedan+="$($x.proceso):$($x.pid)" }
  }
}
$vis=@(Get-VentanasVisibles)
$filas=@(foreach($v in $vis){
  $r=New-Object EstadoW32+RECT; [void][EstadoW32]::GetWindowRect([IntPtr]$v.hwnd,[ref]$r)
  [pscustomobject]@{ hwnd=$v.hwnd; titulo=$v.titulo; proceso=(Get-NombreProceso $v.pid); encima=[EstadoEncima]::Topmost([IntPtr]$v.hwnd)
    x=$r.Left; y=$r.Top; w=($r.Right-$r.Left); h=($r.Bottom-$r.Top) }
})
$pantalla=@{ w=[EstadoEncima]::Ancho(); h=[EstadoEncima]::Alto() }
$encima=@(Get-DecisionEncima $filas $pantalla $excluidos | Select-Object -Unique)
$dialogos=@()
if($Arg){
  foreach($p in @(Get-Process -Name $Arg -ErrorAction SilentlyContinue)){
    $suyas=@($vis | Where-Object { $_.pid -eq $p.Id } | ForEach-Object {
      $d=[long][EstadoProc]::OwnerRoot([IntPtr]$_.hwnd)
      [pscustomobject]@{ hwnd=[long]$_.hwnd; titulo=$_.titulo; dueno=$(if($d -eq [long]$_.hwnd){0}else{$d}); dueno_habilitado=[EstadoW32]::IsWindowEnabled([IntPtr]$d) } })
    foreach($h in @(Get-DecisionDialogos $suyas)){
      $w=@($suyas | Where-Object { $_.hwnd -eq $h })[0]
      $dialogos+=[ordered]@{ pid=$p.Id; dialogo=[string]$w.titulo; ventana=[EstadoW32]::Title([IntPtr]$w.dueno) }
    }
  }
}
# Apps of the batch held by a dialog (pasada r9: Paint's resize dialog, drawn inside its window, sat under four cases;
# ModalOf never saw it). A window of a process the harness opened (propios.jsonl), the batch started (the ledger proves
# it) or the persistent harness book holds, with a Win32 dialog or one inside it, gets that dialog cancelled through
# UIA. One that stays is an obstacle (batch.sh repairs once more: sin_restos, the states). The person's apps, the
# terminals and the Claude app are never touched here.
$reparados=@()
$propiosH=@(Get-Propios | ForEach-Object { [long]$_.hwnd })
$libroArnes=Get-ProcesosArnes
$claves=@{}; if($libroArnes.Count){ foreach($c in @(Get-ProcesosCim)){ $claves[[int]$c.pid]=[string]$c.clave } }
$nuestras=@{}
foreach($v in @($vis | Where-Object { $_.titulo })){
  $pn=Get-NombreProceso $v.pid
  if($excluidos -contains $pn -or $global:AppsProhibidos -contains $pn -or $global:AppsHosts -contains $pn){ continue }
  if(-not $nuestras.ContainsKey([int]$v.pid)){
    $nuestras[[int]$v.pid]=[bool]($libroArnes.ContainsKey([string]$claves[[int]$v.pid]) -or (Test-ProcesoDelLote ([int]$v.pid)))
  }
  if(-not ($nuestras[[int]$v.pid] -or $propiosH -contains [long]$v.hwnd)){ continue }
  $antes=@(Get-DialogosDeVentana ([long]$v.hwnd))
  if($antes.Count -eq 0){ continue }
  $r=@(Close-DialogosDeVentana ([long]$v.hwnd) 'cancelar')
  $reparados+=@($r | ForEach-Object { "$($pn):$($v.pid):$_" })
  foreach($d in @(Get-DialogosDeVentana ([long]$v.hwnd))){
    $dialogos+=[ordered]@{ pid=[int]$v.pid; dialogo=$(try{ [string]$d.Current.Name }catch{ '?' }); ventana=[string]$v.titulo; del_lote=$true }
  }
}
$obstruido=($encima.Count -gt 0 -or $dialogos.Count -gt 0 -or $elevadasQuedan.Count -gt 0)
$res=if($obstruido){'obstruido'}elseif($reparados.Count -or $elevadas.Count){'corregido'}else{'ok'}
Write-Estado $E $res @{ verificado=(-not $obstruido); encima=$encima; dialogos=$dialogos; reparados=$reparados; elevadas=$elevadas; elevadas_quedan=$elevadasQuedan }
