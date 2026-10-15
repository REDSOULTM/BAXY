# Windows of the case's own apps around one case (used by batch.sh; not a state).
#   apps_del_caso.ps1 -Listar                       the PIDs running now, space separated
#   apps_del_caso.ps1 -Caso <id> -Antes "p1 p2"     closes the windows of the case's app(s) (cases/v3_manifiesto.json
#        "app", "A + B" = two) whose process did NOT exist before the case AND that the batch ledger positively proves
#        the batch's (Get-DecisionAppDelCaso: libro_lote.ps1 -Cerrar, which runs before this, classed the process 'lote').
#        A process born during the case is not proof by itself: the person may have opened that app meanwhile and be
#        typing in it (review r10a); without positive provenance its windows are never touched (sin_tocar). A process
#        that existed before (the person's, or one a state opened) is never touched, nor VS Code / Opera / BAXY.
#        A window is closed normally. Its process is stopped by its exact PID only when the window stays (a save
#        prompt), every window of the process is the harness's (decisiones_comun.ps1), the person gave no input during
#        the whole life of the process (the owner-input record covers it), and it is not a terminal or the Claude app
#        (the parallel agents work there: a normal close only). When the person was active during the life of the
#        process, or in a terminal or the Claude app, a window is closed only when BAXY opened or worked in that exact
#        window (its mission journal, CU_JOURNAL: Get-ProcesosDeBaxy .hwnds): Word, Notepad and Windows Terminal keep
#        every window in one process, so the person's document may sit in the batch's Word (review r10b). A window is
#        the app's only when its process is proven to be the Start-menu entry (Get-IdentidadApp), never by its title.
#        Without a manifest entry it does nothing (batch.sh's own list rules).
param([switch]$Listar,[string]$Caso='',[string]$Antes='')
. (Join-Path $PSScriptRoot 'comun.ps1')
. (Join-Path $PSScriptRoot 'apps_comun.ps1')
. (Join-Path $PSScriptRoot 'decisiones_comun.ps1')
if($Listar){ (@(Get-Process | ForEach-Object { $_.Id } | Sort-Object) -join ' '); return }
# Never stopped, whatever proves them the batch's: the terminals and the Claude app the parallel agents work in (the
# ledger's own list, libro_lote.ps1 NoTocarLibro).
$NoDetener=@('WindowsTerminal','Claude')
$tid=($Caso -split '@')[0]
$mp=Join-Path (Split-Path $PSScriptRoot) 'cases\v3_manifiesto.json'
$man=$null
if(Test-Path $mp){ $m=[IO.File]::ReadAllText($mp,[Text.Encoding]::UTF8) | ConvertFrom-Json; if($m.PSObject.Properties[$tid]){ $man=$m.$tid } }
if(-not $man){ Write-Estado 'apps_del_caso' 'sin_manifiesto' @{ verificado=$true; cerradas=@() }; return }
$previos=@($Antes -split '\s+' | Where-Object { $_ } | ForEach-Object { [int]$_ })
$propios=@(Get-Propios | ForEach-Object { [long]$_.hwnd })
$res=@(); $sinTocar=@()
# BAXY's mission journal (batch.sh exports CU_JOURNAL), read once and only when a window needs it.
$lineasJournal=$null
foreach($a in @($man.app -split '\s*\+\s*' | Where-Object { $_ })){
  $s=Resolve-StartApp $a; if(-not $s){ $s=Resolve-StartApp ($a -replace '\s*\(.*\)\s*$','') }
  # Without a Start-menu entry nothing proves which process is the app: nothing is closed.
  if(-not $s){ $res+="$($a):sin_entrada"; continue }
  $nombre=$s.Name; $ident=Get-IdentidadApp $s
  foreach($w in @(Find-AppWindows $nombre '')){
    if($previos -contains [int]$w.app_pid -or $propios -contains $w.hwnd -or $global:AppsHosts -contains $w.app_proceso -or $w.app_proceso -eq 'Baxy'){ continue }
    # A title that only mentions the app (a browser page about it) is not the app: the process must be proven.
    if(-not (Test-IdentidadVentana $w $ident $nombre)){ continue }
    $delLote=[bool](Test-ProcesoDelLote ([int]$w.app_pid) -ConProtegidos)
    $n=Get-NacioProceso ([int]$w.app_pid)
    $quieto=[bool]($n -and (Test-QuietoDesde $n.nacio))
    $protegida=($NoDetener -contains [string]$w.app_proceso)
    # This exact window opened or worked in by BAXY since its process was born.
    $deBaxy=$false
    if($delLote -and $n -and ($protegida -or -not $quieto)){
      if($null -eq $lineasJournal){ $lineasJournal=@(Read-ColaJournal $env:CU_JOURNAL) }
      $deBaxy=@((Get-ProcesosDeBaxy $lineasJournal $n.nacio).hwnds) -contains [long]$w.hwnd
    }
    $d=Get-DecisionAppDelCaso $delLote $protegida $quieto $deBaxy
    if($d -like 'no_tocar*'){ $sinTocar+="$($w.app_proceso):$($w.app_pid):$d"; continue }
    Set-AppAprendida $nombre $w.app_proceso
    $i=[pscustomobject]@{ tipo='app'; pid=[int]$w.app_pid; hwnd=[long]$w.hwnd; desde=''; proceso=[string]$w.app_proceso; nombre=$nombre; nuevo=$true; sin_detener=($d -eq 'cerrar_sin_detener') }
    $res+="$($w.app_proceso):$($w.app_pid):$(Close-AppPropia $i)"
  }
}
$fallos=@($res | Where-Object { $_ -like '*:no_cierra*' })
Write-Estado 'apps_del_caso' ($(if($fallos.Count){'no_verificado'}else{'ok'})) @{ verificado=($fallos.Count -eq 0); cerradas=$res; sin_tocar=$sinTocar }
