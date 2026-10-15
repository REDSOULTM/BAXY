# State sin_restos: no window an earlier case, batch or tanda opened is left open (goal v3, point 7; round 7
# 2026-10-08: a Reloj in front of v3-01..04, a OneNote in its File view under v3-08..10, a Word with its save prompt
# under t-form-4, all opened by earlier runs and taken as the person's by the next batch photo).
#  - Only processes in the persistent harness book (apps_comun.ps1: procesos_arnes.jsonl, documentos.jsonl), by their
#    exact key "pid:start ticks": what a batch ledger proved the harness's (positive provenance) or a state launched.
#    Nothing of the person is ever in it; a process the current batch ledger gave to the person is not touched either.
#  - Never VS Code, Opera, a terminal, the Claude app, BAXY, a shell host or the harness's interpreters.
#  - Office: Stop-ProcesoDelLote (a save prompt a case left is cancelled, then COM Quit only if every open document is
#    the harness's). Anything else: a normal close of each of its windows, and only when every window it shows now was
#    recorded for it (a window nobody recorded may be the person's, opened in that same instance: never touched). An app
#    with unsaved work asks and is left asking: the line says so. A process left without windows keeps running.
#  - The book drops the lines of processes that are gone.
#  - A close that failed in this batch on the same process and the same windows is not tried again for 10 min
#    (Get-DecisionReintentoResto, memo <ledger>.restos_fallidos.json): it stays in quedan, listed in sin_reintento.
# Prints one line: resultado ok | corregido | no_verificado; verificado=false while a leftover still shows a window
# (batch.sh then repairs once and otherwise does not run the case: it would not start from its base state).
param([string]$Arg='')
if(-not ('EstadoW32' -as [type])){ . (Join-Path $PSScriptRoot 'comun.ps1') }
. (Join-Path $PSScriptRoot 'apps_comun.ps1')
. (Join-Path $PSScriptRoot 'decisiones_comun.ps1')
$E='sin_restos'
# Harness data: what is never closed here (the agents' tools, BAXY, the harness itself).
$protegidas=@('powershell','pwsh','python','pythonw','py','bash','sh','conhost','OpenConsole','cmd','dotnet','git','Baxy','baxy-core',
  'WindowsTerminal','Claude','WmiPrvSE')+@($global:AppsProhibidos)+@($global:AppsHosts)
$libro=Get-ProcesosArnes
$procs=@(Get-ProcesosCim)
$lote=Get-LibroLote
$delDueno=@(if($lote){ $lote.procesos_dueno })
$res=@(); $quedan=@(); $avisos=@(); $sinReintento=@()
# Closes that failed in this batch (Get-DecisionReintentoResto): next to the batch ledger, so it lives as long as it.
$memoRuta=$(if($env:CU_LIBRO){ ($env:CU_LIBRO -replace '\.json$','')+'.restos_fallidos.json' }else{ '' })
$memo=$null
if($memoRuta -and (Test-Path -LiteralPath $memoRuta)){ try{ $memo=[IO.File]::ReadAllText($memoRuta,[Text.Encoding]::UTF8) | ConvertFrom-Json }catch{} }
$memoNuevo=[ordered]@{}
foreach($p in $procs){
  if(-not $libro.ContainsKey($p.clave)){ continue }
  $vent=@(if($protegidas -notcontains $p.nombre){ Get-VentanasDelPid $p.pid })
  # A root of another process (a dialog of this one owned by the person's window) is never closed from here.
  $top=@(if($vent.Count){ Get-TopWindows })
  $ajenas=@($vent | Where-Object {
    $h=[long]$_; $dp=0; [void][EstadoW32]::GetWindowThreadProcessId([IntPtr]$h,[ref]$dp)
    $dp -ne $p.pid -and @($top | Where-Object { [long]$_.hwnd -eq $h -and [int]$_.app_pid -eq $p.pid }).Count -eq 0 })
  $d=Get-DecisionResto @{ protegida=($protegidas -contains $p.nombre); dueno=($delDueno -contains $p.clave); office=[bool]$global:AppsQuitCom[$p.nombre]
    ventanas=$vent; libro=$libro[$p.clave].ventanas; ajenas=$ajenas.Count }
  # sin_restos:seco says what it would do and touches nothing.
  if($Arg -eq 'seco'){ $res+="$($p.nombre):$($p.pid):$d"; continue }
  switch -Wildcard ($d){
    'office' {
      $n=Get-NacioProceso $p.pid
      $r=Stop-ProcesoDelLote $p.pid $p.nombre ([bool]($n -and (Test-QuietoDesde $n.nacio)))
      if($r -eq 'no_cierra:office_ilegible' -or $r -eq 'no_cierra:office_sin_com'){
        # COM gave nothing readable: the window titles must each name a document a state created in this process.
        # Never after 'documento_ajeno': COM read a document that is not the harness's (a window of it the titles
        # miss, on another desktop or hung, would otherwise be stopped with the person's work).
        $tit=@((Get-TopWindows) | Where-Object { [int]$_.app_pid -eq $p.pid -or [int]$_.pid -eq $p.pid } | ForEach-Object { $_.titulo })
        $dt=Get-DecisionOfficePorTitulos $tit @(Get-DocumentosCreados $p.pid)
        if($dt -eq 'detener'){
          try{ Stop-Process -Id $p.pid -Force -ErrorAction Stop; [void](Get-Process -Id $p.pid -ErrorAction SilentlyContinue | ForEach-Object { $_.WaitForExit(5000) }); $r='detenida_por_titulos' }catch{ $r="no_cierra:$($_.Exception.Message)" }
        }else{ $r="$($r)+$dt" }
      }
      $res+="$($p.nombre):$($p.pid):$r"
      if(Get-Process -Id $p.pid -ErrorAction SilentlyContinue){ $quedan+="$($p.nombre):$($p.pid):$r" }
    }
    'cerrar_ventanas' {
      if((Get-DecisionReintentoResto $memo $p.clave @($vent) (Get-EpochAhora)) -eq 'sin_reintento'){
        # The same windows of the same process survived a close in this batch less than 10 min ago: not tried again.
        $quedan+="$($p.nombre):$($p.pid):ventana_viva"; $sinReintento+="$($p.nombre):$($p.pid)"
        $memoNuevo[$p.clave]=$memo.($p.clave)
        break
      }
      foreach($h in $vent){
        # A dialog left over it is cancelled, then the close; its save prompt is answered without saving (every
        # window it shows was recorded for this harness process).
        [void]@(Close-DialogosDeVentana ([long]$h) 'cancelar')
        try{ Close-WindowExact ([Windows.Automation.AutomationElement]::FromHandle([IntPtr][long]$h)) -SinGuardar; $res+="$($p.nombre):$($p.pid):ventana:$($h):cerrada" }
        catch{ $res+="$($p.nombre):$($p.pid):ventana:$($h):no_cierra" }
      }
      $fin=(Get-Date).AddSeconds(8)
      while((Get-Date) -lt $fin -and @(Get-VentanasDelPid $p.pid).Count -gt 0){ Start-Sleep -Milliseconds 300 }
      $siguen=@(Get-VentanasDelPid $p.pid)
      if($siguen.Count -gt 0 -and @($siguen | Where-Object { @($libro[$p.clave].ventanas) -notcontains [long]$_ }).Count -eq 0){
        # Pasada r9: the OneNote and Paint leftovers stayed with a dialog for hours. A process of the harness book whose
        # every window is its recorded one is stopped by its exact PID (never a dialog left up).
        try{ Stop-Process -Id $p.pid -Force -ErrorAction Stop; [void](Get-Process -Id $p.pid -ErrorAction SilentlyContinue | ForEach-Object { $_.WaitForExit(5000) }); $res+="$($p.nombre):$($p.pid):detenida" }catch{}
        $siguen=@(Get-VentanasDelPid $p.pid)
      }
      if($siguen.Count -gt 0){
        $quedan+="$($p.nombre):$($p.pid):ventana_viva"
        $memoNuevo[$p.clave]=[ordered]@{ ventanas=(@($siguen | ForEach-Object { [long]$_ } | Sort-Object) -join ' '); t=(Get-EpochAhora) }
      }
    }
    'no_cierra:*' { $quedan+="$($p.nombre):$($p.pid):$($d.Substring(10))" }
    'no_tocar:del_dueno' { $avisos+="$($p.nombre):$($p.pid):del_dueno" }
    default {}
  }
}
# Explorer windows the batch ledger proves the batch's (ventanas_lote; exploradores.ps1 adds one BAXY's app.open opened
# whose close failed): Explorer is a shared shell host, never in the book above, so they are retried here by that exact
# window (pasada r18: a Control Panel BAXY opened in v3-43 stayed open, and a later case typed into it).
if($lote -and @($lote.ventanas_lote).Count){
  . (Join-Path $PSScriptRoot 'explorador_comun.ps1')
  $vl=@($lote.ventanas_lote)
  $expl=@(Get-ShellExplorerWindows | Where-Object { (Get-DecisionAjenaApp ([long]$_.HWND) $vl) -eq 'cerrar_lote' })
  foreach($w in $expl){
    $h=[long]$w.HWND
    if($Arg -eq 'seco'){ $res+="explorador:$($h):cerrar"; continue }
    try{ $w.Quit() }catch{}
    $fin=(Get-Date).AddSeconds(3)
    while((Get-Date) -lt $fin -and [EstadoW32]::IsWindow([IntPtr]$h)){ Start-Sleep -Milliseconds 200 }
    if([EstadoW32]::IsWindow([IntPtr]$h)){ $quedan+="explorador:$($h):ventana_viva" }else{ $res+="explorador:$($h):cerrada" }
  }
}
if($Arg -eq 'seco'){ Write-Estado "${E}:seco" 'seco' @{ verificado=$true; haria=$res }; return }
Optimize-ProcesosArnes @(Get-ProcesosCim | ForEach-Object { $_.clave })
if($memoRuta -and ($memoNuevo.Count -or $memo)){
  try{ [IO.File]::WriteAllText($memoRuta,(([pscustomobject]$memoNuevo) | ConvertTo-Json -Compress -Depth 4),(New-Object Text.UTF8Encoding $false)) }catch{}
}
$r=if($quedan.Count){ 'no_verificado' }elseif($res.Count){ 'corregido' }else{ 'ok' }
Write-Estado $E $r @{ verificado=($quedan.Count -eq 0); cerradas=$res; quedan=$quedan; avisos=$avisos; sin_reintento=$sinReintento }
