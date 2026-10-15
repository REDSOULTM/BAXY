# Batch ledger (libro del lote): what a batch, a case or a tanda opened is closed after it, by exact PID; what the
# person had open is never touched. Harness only, never product code. ASCII only (PowerShell 5.1 reads it as ANSI).
# usage:
#   libro_lote.ps1 -Foto -Libro <file.json>
#        Photo of now: every process ("pid:start ticks"), every visible top-level window (titled or not), the
#        person's browser (tab and window COUNTS only, never their names) and the Notepad tab files. Taken when a
#        batch starts (lote.sh, exported as CU_LIBRO so the states know what the batch started), before each case
#        (batch.sh) and before a tanda (uso_real/tanda.ps1).
#   libro_lote.ps1 -Cerrar -Libro <file.json> [-Registro <registro.json>] [-Seco]
#        Closes what was born after that photo (decisiones_comun.ps1). FAIL CLOSED: the owner-input record
#        (registro_dueno.py, -Registro or CU_REGISTRO, started before the photo by lote.sh, batch.sh or tanda.ps1)
#        is the only evidence that the person was idle; without it, or with a gap in it, the person counts as active.
#        - a process born after the photo is the batch's only with positive provenance (Get-ProcedenciaProceso,
#          Get-DecisionPropiedad): it descends from the harness root pid or BAXY, or a shell host (explorer, sihost,
#          the DcomLaunch svchost) started it while the record covered the 3 s before with no input, or BAXY's
#          journal says its app.open started that very process (Get-AbiertosPorBaxy: an elevated Task Manager
#          relaunched from a launcher the recorder missed). Born within 3 s
#          of the person's input: theirs. Anything else ('sin_procedencia': an updater of the person's app, a
#          terminal of a parallel agent) is only reported in avisos;
#        - a batch process is closed when it holds a visible top-level window, titled or not (a packaged app counts
#          through its frame), never a child of a process of the same program, never VS Code, Opera, Windows
#          Terminal, the Claude app, BAXY, a shell host or the harness's interpreters; a batch process with no
#          window is left running. Office through COM Quit only when every open document is the harness's (a fixture
#          file or a document a state created); any other process only when the person gave no input during its
#          whole life (Stop-ProcesoDelLote): a normal close of its main window and then Stop-Process on that PID;
#        - a NEW window inside a process of the person is closed only by that window, only when the record covers
#          the whole case with no input (Get-DecisionVentanaNueva), and only in a process BAXY worked in during the
#          case (its mission journal, -Journal or CU_JOURNAL, from the photo on: Get-ProcesosDeBaxy); a window the app
#          raised by itself (a reminder, an incoming call) is only reported; Explorer windows keep their own rule;
#        - every process is read back afterwards: one of the batch still running makes verificado=false;
#        - new tabs or windows in the person's browser are only reported (aviso), never closed;
#        - Notepad tab files born after the photo are moved (not deleted) to
#          %LOCALAPPDATA%\BAXY\cu-estado\tabstate-respaldo\<stamp> only under the same full-coverage-and-idle rule,
#          once no Notepad is running, so the next Notepad does not restore a case's text.
#        With CU_LIBRO set (a batch), every batch process a case classed 'lote' is added to the batch ledger
#        (procesos_lote): a leftover an earlier case could not close is retried after each case, the states close it
#        instead of calling it the person's (Test-ProcesoDelLote), and -Cerrar on the batch ledger itself (the sweep
#        at the end of lote.sh) closes only those processes, never a window and never a tab file.
#        -Seco: says what it would close and closes nothing.
#        Prints one JSON line {"estado":"libro_lote","resultado","verificado",...}.
param([switch]$Foto,[switch]$Cerrar,[Parameter(Mandatory=$true)][string]$Libro,[string]$Registro='',[switch]$Seco,[string]$Journal='')
. (Join-Path $PSScriptRoot 'estado\comun.ps1')
. (Join-Path $PSScriptRoot 'estado\apps_comun.ps1')
. (Join-Path $PSScriptRoot 'estado\decisiones_comun.ps1')
$ErrorActionPreference='Continue'

# PowerShell variables ignore case: $datos (the ledger read back) and $fotoProc never reuse the names of the
# parameters $Libro and $Foto.
# The harness's own processes (interpreters, consoles) and BAXY: never closed by the ledger.
$Propios=@('powershell','pwsh','python','pythonw','py','bash','sh','conhost','OpenConsole','cmd','dotnet','git','Baxy','baxy-core','tasklist','WMIC','WmiPrvSE')
# Never closed by the ledger, process or window: the terminals and the Claude app the parallel agents work in. A
# Terminal case's own window is closed by its state (app_cerrada, propios.jsonl), never by the ledger.
$NoTocarLibro=@('WindowsTerminal','Claude')
if($Registro){ $env:CU_REGISTRO=$Registro }
$TabState=Join-Path $env:LOCALAPPDATA 'Packages\Microsoft.WindowsNotepad_8wekyb3d8bbwe\LocalState\TabState'

function Get-NavegadorDueno(){
  # Process name of the person's default browser (https handler), from the registry; $null when unknown.
  try{
    $id=(Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice' -ErrorAction Stop).ProgId
    $cmd=(Get-ItemProperty ("Registry::HKEY_CLASSES_ROOT\{0}\shell\open\command" -f $id) -ErrorAction Stop).'(default)'
    if($cmd -match '^"([^"]+)"' -or $cmd -match '^(\S+)'){ return [IO.Path]::GetFileNameWithoutExtension($matches[1]) }
  }catch{}
  $null
}

function Get-Huella([string]$Texto){
  # SHA-256 of a title, so a change can be told without keeping the person's titles anywhere.
  $sha=[Security.Cryptography.SHA256]::Create()
  try{ -join @($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($Texto)) | ForEach-Object { $_.ToString('x2') }) }finally{ $sha.Dispose() }
}

function Get-ConteoNavegador([string]$Proceso){
  # The person's browser: window count, tab count (UIA TabItems; a browser that hides its tab strip from UI
  # Automation gives 0, measured on Opera GX) and the fingerprints of the window titles, which name the active tab:
  # a new tab the case opened shows up as a window whose active tab changed. Titles are never kept, only hashes.
  if(-not $Proceso){ return $null }
  $ids=@(Get-Process -Name $Proceso -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
  $cTab=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::TabItem)
  $v=0; $t=0; $h=@()
  foreach($w in [Windows.Automation.AutomationElement]::RootElement.FindAll('Children',[Windows.Automation.Condition]::TrueCondition)){
    try{
      if($ids -notcontains $w.Current.ProcessId -or [string]::IsNullOrWhiteSpace($w.Current.Name)){ continue }
      $v++; $t+=@($w.FindAll('Descendants',$cTab)).Count; $h+=(Get-Huella $w.Current.Name)
    }catch{}
  }
  [ordered]@{ proceso=$Proceso; ventanas=$v; pestanas=$t; huellas=@($h | Sort-Object) }
}

function Get-TabFiles(){ @(Get-ChildItem $TabState -Filter *.bin -ErrorAction SilentlyContinue | ForEach-Object { $_.Name }) }

# BAXY's mission journal (Read-ColaJournal, apps_comun.ps1): -Journal, or CU_JOURNAL from batch.sh.
if(-not $Journal -and $env:CU_JOURNAL){ $Journal=$env:CU_JOURNAL }

if($Foto){
  $procs=@(Get-ProcesosCim)
  $prev=$null; if(Test-Path -LiteralPath $Libro){ try{ $prev=[IO.File]::ReadAllText($Libro,[Text.Encoding]::UTF8) | ConvertFrom-Json }catch{} }
  if(-not $prev){ $prev=Get-LibroLote }
  $nav=Get-NavegadorDueno
  $ahora=Get-EpochAhora
  $reg=Get-RegistroDueno
  $o=[ordered]@{ hora=(Get-Date).ToUniversalTime().ToString('o'); hora_epoch=$ahora; procesos=@($procs | ForEach-Object { $_.clave } | Sort-Object)
    ventanas=@(Get-VentanasVisibles | ForEach-Object { $_.hwnd }); navegador=(Get-ConteoNavegador $nav); tabstate=@(Get-TabFiles)
    # Kept from an earlier photo of the same file: what the ledger already gave to the person.
    procesos_dueno=@(if($prev){ $prev.procesos_dueno }); ventanas_lote=@(if($prev){ $prev.ventanas_lote }) }
  $d=Split-Path $Libro; if($d -and -not (Test-Path $d)){ New-Item -ItemType Directory -Force $d | Out-Null }
  [IO.File]::WriteAllText($Libro,(($o | ConvertTo-Json -Depth 4 -Compress)+"`n"),(New-Object Text.UTF8Encoding $false))
  # Without a record started before this photo, -Cerrar will treat the person as active (nothing assumed idle).
  $cub=[bool]($reg -and $null -ne $reg.cubierto_desde -and [double]$reg.cubierto_desde -le ($ahora-3))
  Write-Estado 'libro_lote:foto' 'ok' @{ verificado=$true; procesos=$o.procesos.Count; ventanas=$o.ventanas.Count; registro_cubre=$cub; navegador=$(if($o.navegador){ [ordered]@{ proceso=$o.navegador.proceso; ventanas=$o.navegador.ventanas; pestanas=$o.navegador.pestanas } }) }
  return
}
if(-not $Cerrar){ Write-Estado 'libro_lote' 'sin_modo' @{ verificado=$false; nota='-Foto o -Cerrar' }; return }
if(-not (Test-Path -LiteralPath $Libro)){ Write-Estado 'libro_lote' 'sin_foto' @{ verificado=$false; libro=$Libro }; return }
$datos=[IO.File]::ReadAllText($Libro,[Text.Encoding]::UTF8) | ConvertFrom-Json
foreach($k in @('procesos_dueno','ventanas_lote')){ if(-not $datos.PSObject.Properties[$k]){ $datos | Add-Member -NotePropertyName $k -NotePropertyValue @() } }
$lote=Get-LibroLote
$barrido=[bool]($lote -and $env:CU_LIBRO -eq $Libro)
$fotoProc=@($datos.procesos)
$delLoteYa=@(if($lote){ $lote.procesos_lote })
if($lote){
  $datos.procesos_dueno=@(@($datos.procesos_dueno)+@($lote.procesos_dueno) | Where-Object { $_ } | Select-Object -Unique)
  $datos.ventanas_lote=@(@($datos.ventanas_lote)+@($lote.ventanas_lote) | Where-Object { $_ } | Select-Object -Unique)
}
$fotoHora=$(if($datos.hora_epoch){ [double]$datos.hora_epoch }else{ ([DateTimeOffset][DateTime]::Parse([string]$datos.hora,[Globalization.CultureInfo]::InvariantCulture,[Globalization.DateTimeStyles]::RoundtripKind)).ToUnixTimeMilliseconds()/1000.0 })

# Processes first, then the owner-input record written after that instant (it writes every 0.5 s).
$procs=@(Get-ProcesosCim)
$hasta=Get-EpochAhora
$reg=Get-RegistroDueno $hasta -ConProcesos:(-not $barrido)
$intervalos=@(if($reg){ $reg.intervalos_dueno })
# The sweep at the end of a batch acts on procesos_lote only: never a window of the person, never a tab file.
$quietoCaso=[bool](-not $barrido -and (Get-DecisionDuenoQuieto $reg $fotoHora $hasta))
$duenoActivo=-not $quietoCaso
# Every process the recorder saw plus the live ones, indexed by pid once (Get-IndiceProcesos form) for the walks below.
$tabla=$(if($reg -and $reg.PSObject.Properties['indice_procesos']){ $reg.indice_procesos }else{ @{} })
foreach($p in $procs){ $l=$tabla[[int]$p.pid]; if($null -eq $l){ $l=New-Object Collections.ArrayList; $tabla[[int]$p.pid]=$l }; [void]$l.Add($p) }
$raices=@(if($reg -and $reg.raiz){ [int]$reg.raiz })
$shells=@(@($procs | Where-Object { $_.nombre -eq 'explorer' -or $_.nombre -eq 'sihost' } | ForEach-Object { $_.pid })+@(Get-PidServicio 'DcomLaunch'))
$porPid=@{}; foreach($p in $procs){ $porPid[$p.pid]=$p }
$ventanas=@(Get-VentanasVisibles)
# A packaged app's window is a frame of ApplicationFrameHost: Get-TopWindows gives the app process inside it. One read
# serves both uses (here and the new windows of the person below): nothing is closed in between.
$topVentanas=@(Get-TopWindows)
$conVentana=@(@($ventanas | ForEach-Object { $_.pid })+@($topVentanas | ForEach-Object { [int]$_.app_pid }) | Select-Object -Unique)
$propiedad=@{}; $procedencia=@{}; $delDueno=@(); $aCerrar=@(); $avisos=@(); $protegidasLote=@()
# What BAXY's journal says app.open started during the case (Get-AbiertosPorBaxy): its own positive provenance when
# the parent chain breaks (a program that raises itself relaunches from a launcher the recorder may miss).
$abiertosBaxy=@(if(-not $barrido){ Get-AbiertosPorBaxy (Read-ColaJournal $Journal) $fotoHora })
# Hung processes born in the case (t-menu-1, 2026-10-09: a secondary explorer.exe behind an application error dialog
# held the batch 11 min): a process of the batch with a window that does not answer is stopped by its exact PID with
# its provenance (Get-DecisionColgado), never the shell's explorer (Get-PidShell), VS Code or Opera; it is never asked
# through UIA or COM, which would wait on it.
$colgadas=@(Get-VentanasColgadas)
$pidsColgados=@($colgadas | ForEach-Object { [int]$_.pid } | Select-Object -Unique)
$pidShell=Get-PidShell
$aColgados=@()
foreach($p in $procs){
  if($p.pid -le 4){ continue }
  if($barrido){
    $prop=$(if($delLoteYa -contains $p.clave -and $fotoProc -notcontains $p.clave -and @($datos.procesos_dueno) -notcontains $p.clave){ 'lote' }else{ 'dueno' })
  }else{
    $proc=''; $ms=$null; $cub=$false
    if($fotoProc -notcontains $p.clave){
      $proc=Get-ProcedenciaProceso $tabla $p $raices $shells $fotoHora
      $nac=[double]$p.nacio
      if($proc -like 'shell:*'){ $nac=[double]::Parse($proc.Substring(6),[Globalization.CultureInfo]::InvariantCulture); $cub=Get-DecisionCobertura $reg ($nac-3) $nac }
      $ms=Get-MsDesdeInputDueno $intervalos $nac
    }
    $procedencia[$p.pid]=$proc
    $prop=Get-DecisionPropiedad $fotoProc $p.clave $ms $proc $cub ($abiertosBaxy -contains [int]$p.pid)
    if(@($datos.procesos_dueno) -contains $p.clave){ $prop='dueno_input' }
    # A leftover an earlier case classed 'lote' is retried.
    elseif($prop -eq 'sin_procedencia' -and $delLoteYa -contains $p.clave){ $prop='lote' }
  }
  $propiedad[$p.pid]=$prop
  if($prop -eq 'dueno'){ continue }
  if($pidsColgados -contains [int]$p.pid){
    $protegido=($Propios -contains $p.nombre -or $NoTocarLibro -contains $p.nombre -or $global:AppsProhibidos -contains $p.nombre)
    $quietoColgado=($prop -eq 'lote' -and [bool](Get-DecisionDuenoQuieto $reg ([double]$p.nacio) $hasta))
    $colgadoElegible=Get-DecisionColgado $prop $p.nombre ([int]$p.pid) $pidShell $quietoColgado $protegido
    if($colgadoElegible -eq 'detener'){ $aColgados+=$p }else{ $avisos+="colgado:$($p.nombre):$($p.pid):$colgadoElegible (no se cierra)" }
    continue
  }
  $ventanaPropia=($conVentana -contains $p.pid)
  if($Propios -contains $p.nombre -or $global:AppsProhibidos -contains $p.nombre -or $global:AppsHosts -contains $p.nombre){ continue }
  if($NoTocarLibro -contains $p.nombre){ if($prop -eq 'lote' -and $ventanaPropia){ $avisos+="protegida:$($p.nombre):$($p.pid) (no se cierra)"; $protegidasLote+=$p.clave }; continue }
  if($prop -eq 'dueno_input'){ $delDueno+=$p; continue }
  if($prop -eq 'sin_procedencia'){ if($ventanaPropia){ $avisos+="sin_procedencia:$($p.nombre):$($p.pid):$($procedencia[$p.pid]) (no se cierra)" }; continue }
  # A child of the same program (closing the parent ends it).
  $padre=$porPid[$p.padre]
  if($padre -and $padre.nombre -eq $p.nombre){ continue }
  if($ventanaPropia){ $aCerrar+=$p }
}

$res=@()
# New windows inside processes of the person: by that window only, only with full coverage and no input in the case.
$fotoV=@($datos.ventanas | ForEach-Object { [long]$_ })
$nuevasDueno=@()
if(-not $barrido){
  # What BAXY worked in during the case (its mission journal from the photo on): a new window of the person's process
  # is closed only there. Without the journal nothing is attributed to BAXY and nothing of the person is closed.
  $deBaxy=Get-ProcesosDeBaxy (Read-ColaJournal $Journal) $fotoHora
  foreach($w in $topVentanas){
    if($fotoV -contains [long]$w.hwnd){ continue }
    $pp=$porPid[[int]$w.pid]; if(-not $pp){ continue }
    $prot=($global:AppsProhibidos -contains $w.app_proceso -or $global:AppsProhibidos -contains $w.proceso -or $Propios -contains $w.proceso -or $w.app_proceso -eq 'Baxy' -or
           $NoTocarLibro -contains $w.proceso -or $NoTocarLibro -contains $w.app_proceso)
    $comp=($global:AppsHosts -contains $w.proceso)
    $owner=$propiedad[[int]$w.app_pid]; if(-not $owner){ $owner=$propiedad[[int]$w.pid] }
    if((Get-DecisionVentanaNueva $owner $duenoActivo $comp $prot) -ne 'cerrar_ventana'){ continue }
    # A window the app raised by itself (a reminder, an incoming call, an update dialog) in a process BAXY never
    # touched: reported, never closed (review r10a).
    if(Test-AtribuidaABaxy $w $deBaxy){ $nuevasDueno+=$w }else{ $avisos+="ventana_nueva_sin_baxy:$($w.app_proceso):$($w.hwnd) (no se cierra)" }
  }
}
foreach($p in $delDueno){ $datos.procesos_dueno=@(@($datos.procesos_dueno)+$p.clave | Select-Object -Unique) }

# Quiet over its whole life: the only case where a non-Office batch process may be stopped, and where its windows
# become positively the batch's (ventanas_lote) for the states.
$quietoVida=@{}
foreach($p in $aCerrar){ $quietoVida[$p.pid]=[bool](Get-DecisionDuenoQuieto $reg ([double]$p.nacio) $hasta) }
foreach($p in $aCerrar){
  if($quietoVida[$p.pid]){ $datos.ventanas_lote=@(@($datos.ventanas_lote)+@($ventanas | Where-Object { $_.pid -eq $p.pid } | ForEach-Object { [long]$_.hwnd }) | Select-Object -Unique) }
}

if($Seco){
  Write-Estado 'libro_lote' 'seco' @{ verificado=$true; cerraria=@(@($aCerrar | ForEach-Object { "$($_.nombre):$($_.pid):quieto=$($quietoVida[$_.pid])" })+@($aColgados | ForEach-Object { "colgado:$($_.nombre):$($_.pid)" })); ventanas_del_dueno_nuevas=$nuevasDueno.Count
    del_dueno=@($delDueno | ForEach-Object { "$($_.nombre):$($_.pid)" }); dueno_activo=$duenoActivo; barrido=$barrido; avisos=$avisos }
  return
}
# Persistent harness book (apps_comun.ps1): what this ledger proved the batch's, with its windows, so a later case,
# batch or tanda closes it if it is still there (estado/sin_restos.ps1). A batch photo alone made it the person's.
$origenLibro="libro:$([IO.Path]::GetFileNameWithoutExtension($Libro))"
foreach($p in $aCerrar){
  Add-ProcesoArnes $p.clave $p.nombre @($ventanas | Where-Object { $_.pid -eq $p.pid } | ForEach-Object { [long][EstadoProc]::OwnerRoot([IntPtr][long]$_.hwnd) }; $topVentanas | Where-Object { [int]$_.app_pid -eq $p.pid } | ForEach-Object { [long]$_.hwnd }) $origenLibro
}
foreach($w in $nuevasDueno){
  try{ Close-WindowExact ([Windows.Automation.AutomationElement]::FromHandle([IntPtr][long]$w.hwnd)); $res+="ventana:$($w.app_proceso):$($w.hwnd):cerrada" }catch{ $res+="ventana:$($w.app_proceso):$($w.hwnd):no_cierra" }
}
# Parents before children: closing a program's main process ends its helpers, which then count as gone.
foreach($p in @($aCerrar | Sort-Object nacio)){
  if(-not (Get-Process -Id $p.pid -ErrorAction SilentlyContinue)){ continue }
  $res+="$($p.nombre):$($p.pid):$(Stop-ProcesoDelLote $p.pid $p.nombre $quietoVida[$p.pid])"
}
# A hung process of the batch answers no close request: its exact PID, with the provenance that made it the batch's.
foreach($p in $aColgados){
  $vivo=Get-Process -Id $p.pid -ErrorAction SilentlyContinue
  if(-not $vivo -or $vivo.ProcessName -ne $p.nombre){ continue }
  $r=try{ Stop-Process -Id $p.pid -Force -ErrorAction Stop; [void]$vivo.WaitForExit(5000); 'detenido' }catch{ "no_cierra:$($_.Exception.Message)" }
  $res+="colgado:$($p.nombre):$($p.pid):$($r):procedencia=$(if($procedencia[$p.pid]){ $procedencia[$p.pid] }else{ 'lote' })"
}
# Read back: every process the ledger meant to close, by its exact key.
$vivos=@(Get-ProcesosCim | ForEach-Object { $_.clave })
$sobreviven=@(@($aCerrar)+@($aColgados) | Where-Object { -not (Get-DecisionVerificado 'cerrada' $true ($vivos -contains $_.clave)) } | ForEach-Object { "$($_.nombre):$($_.pid)" })

# Notepad tab files born after the photo: moved aside only with full coverage and no input, once Notepad is closed.
$movidas=0
if($quietoCaso -and @(Get-Process Notepad -ErrorAction SilentlyContinue).Count -eq 0){
  $nuevosTab=@(Get-TabFiles | Where-Object { @($datos.tabstate) -notcontains $_ })
  if($nuevosTab.Count -gt 0){
    $dst=Join-Path $env:LOCALAPPDATA ("BAXY\cu-estado\tabstate-respaldo\{0}" -f (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
    New-Item -ItemType Directory -Force $dst | Out-Null
    foreach($f in $nuevosTab){ try{ Move-Item -LiteralPath (Join-Path $TabState $f) -Destination $dst -ErrorAction Stop; $movidas++ }catch{ $avisos+="tabstate:${f}:no_movido" } }
  }
}elseif(-not $barrido -and @(Get-TabFiles | Where-Object { @($datos.tabstate) -notcontains $_ }).Count -gt 0){
  $avisos+='tabstate: pestanas nuevas del Bloc de notas sin mover (dueno activo o sin registro completo)'
}

# The person's browser: counts only, never closed.
$nav=$null
if($datos.navegador -and $datos.navegador.proceso){
  $nav=Get-ConteoNavegador ([string]$datos.navegador.proceso)
  $dt=[int]$nav.pestanas-[int]$datos.navegador.pestanas; $dv=[int]$nav.ventanas-[int]$datos.navegador.ventanas
  if($dt -gt 0){ $avisos+="navegador_del_dueno:$($nav.proceso):$dt pestanas nuevas (no se cierran)" }
  if($dv -gt 0){ $avisos+="navegador_del_dueno:$($nav.proceso):$dv ventanas nuevas (no se cierran)" }
  $cambio=@($nav.huellas | Where-Object { @($datos.navegador.huellas) -notcontains $_ }).Count
  if($cambio -gt 0 -and $dt -le 0 -and $dv -le 0){ $avisos+="navegador_del_dueno:$($nav.proceso):$cambio ventanas con otra pestana activa (posible pestana nueva; no se cierra)" }
}
[IO.File]::WriteAllText($Libro,(($datos | ConvertTo-Json -Depth 4 -Compress)+"`n"),(New-Object Text.UTF8Encoding $false))
if($lote -and -not $barrido){
  $lote.procesos_dueno=@($datos.procesos_dueno)
  $vistos=@($aCerrar | ForEach-Object { $_.clave })
  foreach($k in @('procesos_lote','ventanas_lote','procesos_lote_protegidos')){ if(-not $lote.PSObject.Properties[$k]){ $lote | Add-Member -NotePropertyName $k -NotePropertyValue @() } }
  $lote.procesos_lote=@(@($delLoteYa)+$vistos | Where-Object { $_ } | Select-Object -Unique)
  # A terminal or the Claude app with positive provenance: never closed by the ledger, but apps_del_caso.ps1 may close
  # its window normally when it is the case's own app (Test-ProcesoDelLote -ConProtegidos).
  $lote.procesos_lote_protegidos=@(@($lote.procesos_lote_protegidos)+$protegidasLote | Where-Object { $_ } | Select-Object -Unique)
  $lote.ventanas_lote=@($datos.ventanas_lote)
  [IO.File]::WriteAllText($env:CU_LIBRO,(($lote | ConvertTo-Json -Depth 4 -Compress)+"`n"),(New-Object Text.UTF8Encoding $false))
}
$fallos=@($res | Where-Object { $_ -like '*:no_cierra*' })
$ok=($fallos.Count -eq 0 -and $sobreviven.Count -eq 0)
Write-Estado 'libro_lote' ($(if(-not $ok){'no_verificado'}elseif($res.Count -or $movidas){'corregido'}else{'ok'})) @{ verificado=$ok; cerradas=$res; sobreviven=$sobreviven
  del_dueno=@($delDueno | ForEach-Object { "$($_.nombre):$($_.pid)" }); dueno_activo=$duenoActivo; registro=[bool]$reg; barrido=$barrido; pestanas_bloc_movidas=$movidas; avisos=$avisos
  navegador=$(if($nav){ [ordered]@{ proceso=$nav.proceso; ventanas=$nav.ventanas; pestanas=$nav.pestanas } }) }
