# Pure decisions of the harness app states (apps_comun.ps1). Dot-source it. No desktop access here, so
# tests/test_cu_live_estados_v3.py checks every branch with plain values.

function Test-RutaDeApp([string]$Ruta,[string]$Objetivo,[string]$Windows){
  # The process executable $Ruta is the app whose Start-menu shortcut targets $Objetivo: the same file, or a file
  # with the same name under the target's folder (a launcher stub next to versioned app folders, "app-3.5\X.exe").
  # A target in the Windows folder only matches itself (System32 holds every system tool). Never a different
  # program of the same folder (one Office folder holds every Office app). Case-insensitive, like the file system.
  if(-not $Ruta -or -not $Objetivo){ return $false }
  if([string]::Equals($Ruta,$Objetivo,[StringComparison]::OrdinalIgnoreCase)){ return $true }
  if(-not [string]::Equals([IO.Path]::GetFileName($Ruta),[IO.Path]::GetFileName($Objetivo),[StringComparison]::OrdinalIgnoreCase)){ return $false }
  $dir=[IO.Path]::GetDirectoryName($Objetivo).TrimEnd('\')+'\'
  if($Windows -and $dir.StartsWith($Windows.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)){ return $false }
  $Ruta.StartsWith($dir,[StringComparison]::OrdinalIgnoreCase)
}

function Get-DecisionFoco([long]$Activada,[long]$Actual){
  # After the harness closed its windows (app_cerrada): $Activada is the window Windows put in front right after
  # closing a harness window that WAS in front (0 when none was in front, or nothing was closed); $Actual is the
  # window in front now. The foreground is handed back only while that activated window is still in front.
  # Returns 'devolver' | 'sin_cambio' (no harness window was in front) | 'ajeno' (the person moved: never touched).
  if($Activada -eq 0){ return 'sin_cambio' }
  if($Actual -ne $Activada){ return 'ajeno' }
  'devolver'
}

# How the harness closes one window it opened (Close-AppPropia).
# Rules (owner 2026-10-07: the harness only ever closes what it opened):
#  - A window the harness opened is closed normally, by that window.
#  - If that window is already gone, the process is NEVER stopped: a single-instance app (an Office app, a terminal
#    that groups windows) may now hold the person's documents, and an app still syncing (mail) may be writing data.
#  - A process is stopped by its exact PID only when the harness window is still there after a normal close (a save
#    prompt of a test document), the harness started that process, it is not a shared host, and EVERY visible
#    top-level window of that process belongs to the harness (its window, or a dialog owned by it).
# $E: @{ intentado; ventana_viva; proceso_vivo; nuevo; host; ventanas_del_pid; propias }
#   intentado         the normal close was already tried
#   ventana_viva      the harness window still exists
#   proceso_vivo      the recorded process is still running with the recorded name
#   ventanas_del_pid  hwnds of the visible top-level windows of that process (a dialog counts as its owner's hwnd)
#   propias           hwnds in propios.jsonl
#   del_lote          (optional) the batch ledger proves the process was born in the batch (Test-ProcesoDelLote)
#   ventanas_lote     (optional) hwnds the ledger POSITIVELY proves are the batch's: windows of a batch process whose
#                     whole life the owner-input record covered with no input of the person (libro_lote.ps1)
#   sin_detener       (optional) the process is never stopped nor made to exit, whatever its windows: a window the
#                     harness did not open itself (apps_del_caso.ps1, Get-DecisionAppDelCaso) is only closed normally
# Returns 'cerrar' | 'ya_cerrada' | 'cerrada' | 'cerrada_proceso_vivo' (window gone, process left running) |
# 'salir_sin_ventanas' (window gone, a batch process whose every window is the harness's or proven the batch's: it is
# made to exit) | 'detener' | 'no_cierra:<why>'.
# The ventanas_ajenas rule holds for a batch process too: a window nobody recorded may be the person's document opened
# in that same instance (a double-clicked .pptx goes into the running PowerPoint). Only windows in ventanas_lote are
# exempt: no evidence about the person is never taken as evidence that a window is the batch's.
function Get-DecisionCierre($E){
  $lote=[bool]$E.del_lote -and -not $E.host
  $propias=@(@($E.propias)+@(if($lote){ $E.ventanas_lote }) | Where-Object { $null -ne $_ } | ForEach-Object { [long]$_ })
  $ajenas=@($E.ventanas_del_pid | Where-Object { $propias -notcontains [long]$_ })
  if(-not $E.ventana_viva){
    if($E.nuevo -and $E.proceso_vivo){
      if($lote -and $ajenas.Count -eq 0 -and -not $E.sin_detener){ return 'salir_sin_ventanas' }
      return 'cerrada_proceso_vivo'
    }
    if(-not $E.intentado){ return 'ya_cerrada' }
    return 'cerrada'
  }
  if(-not $E.intentado){ return 'cerrar' }
  if(-not $E.nuevo -or -not $E.proceso_vivo){ return 'no_cierra:ventana_viva' }
  if($E.host){ return 'no_cierra:proceso_compartido' }
  if($ajenas.Count -gt 0){ return 'no_cierra:ventanas_ajenas' }
  if($E.sin_detener){ return 'no_cierra:sin_detener' }
  'detener'
}

# A window of the case's own app (cases/v3_manifiesto.json "app") whose process did not exist before the case
# (apps_del_caso.ps1). That alone never makes it the harness's: the person may have opened that app during the case
# and be typing in it (a Word with an unsaved document, then its save prompt; review r10a). Owner rule: the harness
# only closes what it opened.
#   $DelLote     the batch ledger POSITIVELY proves the process the batch's (libro_lote.ps1 classed it 'lote': born from
#                the harness or BAXY, or from a shell host with the record covering the 3 s before and no input)
#   $Protegida   a terminal or the Claude app: the parallel agents work there (never stopped, only a normal close)
#   $QuietoVida  the owner-input record covers the whole life of the process with no input of the person
#   $DeBaxy      BAXY itself opened or worked in this exact window during the life of the process (its mission journal:
#                app.open result.windowHandle, or result.window.hwnd of a view; Get-ProcesosDeBaxy .hwnds)
# A process the batch owns may still hold the person's windows when the person was active during its life: Word,
# Notepad and Windows Terminal keep every window in one process, so a document the person double-clicked meanwhile
# opens inside the batch's Word (review r10b). Then, and in a terminal or the Claude app (a parallel agent's new window
# joins the running Windows Terminal process without any input of the person), only a window BAXY opened or worked in
# is closed; any other stays.
# Returns 'no_tocar:sin_procedencia' (nothing proves the process the batch's: never touched) | 'no_tocar:ventana_ajena'
# (a batch process, but nothing proves this window the batch's: never touched) | 'cerrar_sin_detener' (a normal close
# of the window only: a save prompt stays, nothing is lost) | 'cerrar' (a normal close, then its exact PID if its
# window stays and every window of the process is the harness's: Get-DecisionCierre).
function Get-DecisionAppDelCaso([bool]$DelLote,[bool]$Protegida,[bool]$QuietoVida,[bool]$DeBaxy){
  if(-not $DelLote){ return 'no_tocar:sin_procedencia' }
  if($QuietoVida -and -not $Protegida){ return 'cerrar' }
  if($DeBaxy){ return 'cerrar_sin_detener' }
  'no_tocar:ventana_ajena'
}

# A window of a test app that is already open when a state wants to reset it (calc_estandar: mode, angle unit,
# display). The state changes it only when it is the harness's: recorded in propios.jsonl ($Propias) or proven the
# batch's by the ledger ($DelLote: hwnds of a batch process, Get-VentanasLoteDelPid). Anything else is the person's (a
# half-done calculation in Programmer mode): 'ajena', never touched. Returns 'del_arnes' | 'ajena'.
function Get-DecisionVentanaPrevia([long]$Hwnd,$Propias,$DelLote){
  if($Hwnd -eq 0){ return 'ajena' }
  $suyas=@(@($Propias)+@($DelLote) | Where-Object { $null -ne $_ } | ForEach-Object { [long]$_ })
  if($suyas -contains $Hwnd){ return 'del_arnes' }
  'ajena'
}

# What BAXY itself touched during a case, from its mission journal ($Lineas: raw JSONL lines, newest last; $Desde:
# epoch seconds of the case photo). A record at or after $Desde names the window BAXY looked at or acted in
# (result.window: its exact processId and hwnd; only its process name when the record has no id) or the process and
# window it opened (app.open result.processId and result.windowHandle). Returns @{ procesos; pids; hwnds }.
# Read with plain patterns, never kept: only process names and ids leave this function.
function Get-ProcesosDeBaxy($Lineas,[double]$Desde){
  $procs=@(); $pids=@(); $hwnds=@()
  $inv=[Globalization.CultureInfo]::InvariantCulture
  foreach($l in @($Lineas)){
    if(-not $l){ continue }
    $t=[regex]::Match([string]$l,'"timestampUtc":"([^"]+)"')
    if(-not $t.Success){ continue }
    try{ $e=[DateTimeOffset]::Parse($t.Groups[1].Value,$inv).ToUnixTimeMilliseconds()/1000.0 }catch{ continue }
    if($e -lt $Desde){ continue }
    foreach($m in [regex]::Matches([string]$l,'"window":\{"title":"(?:[^"\\]|\\.)*","process":"([^"\\]+)"(?:,"processId":(\d+))?(?:,"hwnd":(\d+))?')){
      if($m.Groups[2].Success){ $pids+=[int]$m.Groups[2].Value }else{ $procs+=$m.Groups[1].Value }
      if($m.Groups[3].Success){ $hwnds+=[long]$m.Groups[3].Value }
    }
    if($l -match '"operation":"app\.open"'){
      foreach($m in [regex]::Matches([string]$l,'"processId":(\d+)')){ $pids+=[int]$m.Groups[1].Value }
      foreach($m in [regex]::Matches([string]$l,'"windowHandle":(\d+)')){ $hwnds+=[long]$m.Groups[1].Value }
    }
  }
  @{ procesos=@($procs | Select-Object -Unique); pids=@($pids | Select-Object -Unique)
     hwnds=@($hwnds | Where-Object { $_ -ne 0 } | Select-Object -Unique) }
}

# The processes BAXY itself started during a case: a completed app.open at or after $Desde whose result says it did not
# reuse a running copy ("alreadyRunning":false) names that process (result.processId). Positive provenance for the
# ledger (Get-DecisionPropiedad -AbiertoPorBaxy) where the parent chain breaks: a program that raises itself (Task
# Manager, Resource Monitor) is started by BAXY with the person's rights, exits within 0.4 s and its elevated copy is
# born from that short-lived launcher, which the 0.3 s recorder may never see (pasada r15b, v3-22: Taskmgr:48780
# 'sin_procedencia' stayed elevated and on top of v3-72, v3-20, v3-21, v3-23 and v3-26). A reused copy (true) is the
# person's and is never named. Returns the pids.
function Get-AbiertosPorBaxy($Lineas,[double]$Desde){
  $pids=@()
  $inv=[Globalization.CultureInfo]::InvariantCulture
  foreach($l in @($Lineas)){
    if(-not $l -or $l -notmatch '"operation":"app\.open"' -or $l -notmatch '"phase":"completed"'){ continue }
    $t=[regex]::Match([string]$l,'"timestampUtc":"([^"]+)"')
    if(-not $t.Success){ continue }
    try{ $e=[DateTimeOffset]::Parse($t.Groups[1].Value,$inv).ToUnixTimeMilliseconds()/1000.0 }catch{ continue }
    if($e -lt $Desde){ continue }
    foreach($m in [regex]::Matches([string]$l,'"alreadyRunning":false,"processId":(\d+)')){ $pids+=[int]$m.Groups[1].Value }
  }
  @($pids | Where-Object { $_ -gt 4 } | Select-Object -Unique)
}

# The windows BAXY itself opened during a case: a completed app.open at or after $Desde whose result says it opened a
# new window ("alreadyRunning":false) names that window (result.windowHandle). Positive provenance for a new window in
# a shared shell host, where the process says nothing (pasada r18, v3-43: BAXY's app.open opened two Control Panel
# windows, 15601624 and 2889276, in the person's Explorer; the record saw input during the case, so they stayed open
# over v3-44 and a later case typed into one). A window BAXY only looked at or acted in (result.window.hwnd of a
# view) is not named, nor one app.open reused (true: it was already there), nor anything without a journal.
# Returns the hwnds.
function Get-VentanasAbiertasPorBaxy($Lineas,[double]$Desde){
  $hwnds=@()
  $inv=[Globalization.CultureInfo]::InvariantCulture
  foreach($l in @($Lineas)){
    if(-not $l -or $l -notmatch '"operation":"app\.open"' -or $l -notmatch '"phase":"completed"'){ continue }
    $t=[regex]::Match([string]$l,'"timestampUtc":"([^"]+)"')
    if(-not $t.Success){ continue }
    try{ $e=[DateTimeOffset]::Parse($t.Groups[1].Value,$inv).ToUnixTimeMilliseconds()/1000.0 }catch{ continue }
    if($e -lt $Desde){ continue }
    foreach($m in [regex]::Matches([string]$l,'"result":\{[^{}]*?"alreadyRunning":false[^{}]*?"windowHandle":(\d+)')){ $hwnds+=[long]$m.Groups[1].Value }
  }
  @($hwnds | Where-Object { $_ -ne 0 } | Select-Object -Unique)
}

# A new Explorer window after a case (exploradores.ps1 -CerrarNuevos). $Previas: the Explorer windows listed before
# the case; $Lugar: it shows a test place; $DuenoQuieto: the record covers the whole case with no input of the person;
# $DeBaxy: hwnds BAXY's app.open opened during the case (Get-VentanasAbiertasPorBaxy).
# Returns 'previa' (it was there before: never closed) | 'cerrar_procedencia' (BAXY opened that exact window: closed
# whatever the person did meanwhile, like a process BAXY started) | 'cerrar_ventana' (a test place with the person idle:
# the ledger's rule) | 'sin_tocar' (a test place with the person active: maybe theirs) | 'ajena' (anything else).
function Get-DecisionExploradorNuevo([long]$Hwnd,$Previas,[bool]$Lugar,[bool]$DuenoQuieto,$DeBaxy){
  if(@(@($Previas) | Where-Object { $null -ne $_ } | ForEach-Object { [long]$_ }) -contains $Hwnd){ return 'previa' }
  if($Hwnd -ne 0 -and @(@($DeBaxy) | Where-Object { $null -ne $_ } | ForEach-Object { [long]$_ }) -contains $Hwnd){ return 'cerrar_procedencia' }
  if(-not $Lugar){ return 'ajena' }
  if((Get-DecisionVentanaNueva 'dueno' (-not $DuenoQuieto) $false $false) -eq 'cerrar_ventana'){ return 'cerrar_ventana' }
  'sin_tocar'
}

# A window app_cerrada would call the person's (Get-AjenasDe) that the batch ledger POSITIVELY proves the batch's
# (ventanas_lote: a window of a batch process quiet over its life, or one BAXY's app.open opened whose close failed,
# exploradores.ps1). Returns 'cerrar_lote' | 'ajena' (never touched).
function Get-DecisionAjenaApp([long]$Hwnd,$VentanasLote){
  if($Hwnd -ne 0 -and @(@($VentanasLote) | Where-Object { $null -ne $_ } | ForEach-Object { [long]$_ }) -contains $Hwnd){ return 'cerrar_lote' }
  'ajena'
}

# A new window inside a process of the person (libro_lote.ps1, after Get-DecisionVentanaNueva said 'cerrar_ventana'):
# it is closed only when BAXY worked in that process during the case ($DeBaxy, Get-ProcesosDeBaxy). A window an app
# raised by itself (a mail reminder, an incoming call: closing it may reject the call, an update dialog) in a process
# BAXY never touched is reported, never closed (review r10a). $W: @{ pid; proceso; app_pid; app_proceso }.
function Test-AtribuidaABaxy($W,$DeBaxy){
  if(-not $W -or -not $DeBaxy){ return $false }
  $p=@($DeBaxy.procesos | Where-Object { $_ } | ForEach-Object { [string]$_ })
  $i=@($DeBaxy.pids | Where-Object { $_ } | ForEach-Object { [int]$_ })
  ($i -contains [int]$W.app_pid) -or ($i -contains [int]$W.pid) -or ($p -contains [string]$W.app_proceso) -or ($p -contains [string]$W.proceso)
}

# One Notepad tab of a window the harness opened (clear_notepad.ps1). Windows 11 Notepad keeps every window in ONE
# process, so a tab is emptied only when it is untitled ($SinTitulo: not a file) and its whole text is made of the
# bank's test texts (textos_de_prueba.json), like bloc_vacio. Returns 'vacia' | 'vaciar' | 'ajena' (the person's text
# or a file: never emptied, and its window is not closed).
function Get-DecisionPestanaBloc([bool]$SinTitulo,[string]$Texto,$Textos){
  if([string]::IsNullOrEmpty($Texto)){ return 'vacia' }
  if(-not $SinTitulo){ return 'ajena' }
  $n=($Texto -replace '\s+',' ').Trim().ToLowerInvariant()
  if(-not $n){ return 'ajena' }
  foreach($x in @(@($Textos) | Where-Object { $_ } | Sort-Object { ([string]$_).Length } -Descending)){ $n=$n.Replace(([string]$x).ToLowerInvariant(),' ') }
  if(($n -replace '[\s\p{P}]','') -eq ''){ return 'vaciar' }
  'ajena'
}

function Get-DecisionDocumentos($Docs,[string]$Raiz,[bool]$Quieto=$false){
  # Before an Office copy of the batch is quit with its documents marked saved (Stop-ProcesoDelLote), every open
  # document must be the harness's: a file under the test fixture folder $Raiz, or a new never-saved one (in a copy
  # born in the batch that is what a state or a case made: BAXY's blank document of u5/n6 is recorded by no state,
  # and banco r30 ran 50 cases with it left open). A saved file elsewhere (the person's) stops it, unless the person
  # gave no input in the whole life of that copy ($Quieto): then a case opened it and the quit discards nothing.
  # $Docs: @{ nombre; ruta } with ruta '' for a document never saved. A document COM gives with neither name nor path
  # is unreadable (measured 2026-10-08 on Word): it is never quit, and only a document COM READ as someone else's is
  # 'documento_ajeno' (sin_restos.ps1 may fall back to the window titles for 'office_ilegible', never for that one).
  # Returns 'quit' | 'no_cierra:documento_ajeno' | 'no_cierra:office_ilegible'.
  if($Quieto){ return 'quit' }
  $r=$(if($Raiz){ $Raiz.TrimEnd([char]92)+[char]92 }else{ '' })
  $ilegible=$false
  foreach($d in @($Docs)){
    if($null -eq $d){ continue }
    $ruta=[string]$d.ruta
    if(-not $ruta -and [string]::IsNullOrWhiteSpace([string]$d.nombre)){ $ilegible=$true; continue }
    if($ruta -and (-not $r -or -not $ruta.StartsWith($r,[StringComparison]::OrdinalIgnoreCase))){ return 'no_cierra:documento_ajeno' }
  }
  if($ilegible){ return 'no_cierra:office_ilegible' }
  'quit'
}

# Batch ledger (libro del lote, scripts/cu_live/libro_lote.ps1). The photo taken when the batch starts holds every
# process then running, as "pid:start ticks" (a reused pid is another process): those are the person's and are never
# touched. A process born later is the batch's only with POSITIVE provenance (Get-ProcedenciaProceso): it descends from
# the harness (the root pid that started the owner-input recorder registro_dueno.py, or BAXY itself), or a shell host
# (explorer, sihost, the DcomLaunch svchost) started it while the input record covered the 3 s before with no input of
# the person. Anything else born in the batch (an updater of the person's app, a terminal of a parallel agent) has no
# provenance: it is reported, never closed.
function Get-ClaveProceso([int]$ProcessId,[long]$InicioTicks){ '{0}:{1}' -f $ProcessId,$InicioTicks }

function Get-MsDesdeInputDueno($Intervalos,[double]$Nacio){
  # $Intervalos: [ini,fin] pairs in epoch seconds of the person's real input; $Nacio: epoch seconds the process
  # started. Returns the ms from the person's last input at or before $Nacio to $Nacio, or $null when none.
  $best=$null
  foreach($i in @($Intervalos)){
    if($null -eq $i -or @($i).Count -lt 2){ continue }
    $s=[double]$i[0]; $e=[double]$i[1]
    if($s -gt $Nacio){ continue }
    $ms=($Nacio-[Math]::Min($e,$Nacio))*1000
    if($null -eq $best -or $ms -lt $best){ $best=$ms }
  }
  if($null -eq $best){ return $null }
  [long][Math]::Round($best)
}

function Get-DecisionCobertura($Registro,[double]$Desde,[double]$Hasta){
  # True only when the owner-input record (registro_dueno.py) covers the whole span [$Desde,$Hasta]: it started
  # before $Desde and was still recording, hooks intact, at $Hasta. No record, or a gap: $false.
  if(-not $Registro -or $null -eq $Registro.cubierto_desde -or $null -eq $Registro.cubierto_hasta){ return $false }
  ([double]$Registro.cubierto_desde -le $Desde) -and ([double]$Registro.cubierto_hasta -ge $Hasta)
}

function Get-DecisionDuenoQuieto($Registro,[double]$Desde,[double]$Hasta){
  # The person gave no input in [$Desde-3 s,$Hasta] and the record covers all of it. Without full coverage the person
  # is taken as active (fail closed): nobody is ever assumed idle for lack of a record.
  if(-not (Get-DecisionCobertura $Registro ($Desde-3) $Hasta)){ return $false }
  foreach($i in @($Registro.intervalos_dueno)){
    if($null -eq $i -or @($i).Count -lt 2){ continue }
    if([double]$i[0] -le $Hasta -and [double]$i[1] -ge ($Desde-3)){ return $false }
  }
  $true
}

$global:LibroProducto=@('Baxy','baxy-core')
function Get-IndiceProcesos($Tabla){
  # pid -> the rows of $Tabla with that pid (a pid reused over a long batch has several). Built once, it replaces a
  # scan of the whole table per parent: the record of a long batch holds ~55 000 processes, and that scan cost 1.3 s a
  # parent, ~4 s a new process, in every libro_lote.ps1 -Cerrar (measured 2026-10-09 on pasada r15b).
  $idx=@{}
  foreach($r in @($Tabla)){
    if(-not $r){ continue }
    $k=[int]$r.pid; $l=$idx[$k]
    if($null -eq $l){ $l=New-Object Collections.ArrayList; $idx[$k]=$l }
    [void]$l.Add($r)
  }
  $idx
}
function Get-ProcedenciaProceso($Tabla,$Proceso,$Raices,$Shells,[double]$FotoHora){
  # Walks the parents of $Proceso (@{pid; padre; nombre; nacio}) through $Tabla (every process the recorder saw, dead
  # ones included, plus the live ones; or its Get-IndiceProcesos, which a caller walking many processes builds once).
  # Returns 'arnes' (an ancestor is a harness root pid or BAXY) |
  # 'shell:<nacio>' (a shell host in $Shells started the ancestor born at <nacio>, after the photo) | 'dueno' (the
  # chain reaches a process that was running before the photo) | 'desconocida' (a parent the record never saw).
  $raiz=@($Raices | ForEach-Object { [int]$_ }); $sh=@($Shells | ForEach-Object { [int]$_ })
  $idx=$(if($Tabla -is [hashtable]){ $Tabla }else{ Get-IndiceProcesos $Tabla })
  $cur=$Proceso
  for($n=0;$n -lt 32;$n++){
    $pp=[int]$cur.padre
    if($raiz -contains $pp){ return 'arnes' }
    # The newest row with that pid born no later than the child (+0.5 s): the parent, not an older owner of the pid.
    $tope=[double]$cur.nacio+0.5; $par=$null
    foreach($r in @($idx[$pp])){ if([double]$r.nacio -le $tope -and ($null -eq $par -or [double]$r.nacio -gt [double]$par.nacio)){ $par=$r } }
    if($null -eq $par){ return 'desconocida' }
    if($global:LibroProducto -contains [string]$par.nombre){ return 'arnes' }
    if($sh -contains $pp){ return ('shell:{0}' -f ([double]$cur.nacio).ToString([Globalization.CultureInfo]::InvariantCulture)) }
    if([double]$par.nacio -lt $FotoHora){ return 'dueno' }
    $cur=$par
  }
  'desconocida'
}

function Get-DecisionPropiedad($Foto,[string]$Clave,$MsDesdeInputDueno,[string]$Procedencia='',[bool]$Cubierto=$false,[bool]$AbiertoPorBaxy=$false){
  # Returns 'dueno' (running when the batch started) | 'lote' (positive provenance: the harness or BAXY started it, or
  # a shell host started it with the record covering the 3 s before and no input of the person, or BAXY's journal
  # says app.open started this very process: $AbiertoPorBaxy, Get-AbiertosPorBaxy) | 'dueno_input' (born within 3 s
  # after the person's input) | 'sin_procedencia' (nothing proves whose: reported, never closed).
  # With a shell-launched ancestor, $MsDesdeInputDueno and $Cubierto are about that ancestor's birth.
  if(@($Foto) -contains $Clave){ return 'dueno' }
  if($Procedencia -eq 'arnes' -or $AbiertoPorBaxy){ return 'lote' }
  if($null -ne $MsDesdeInputDueno -and [double]$MsDesdeInputDueno -ge 0 -and [double]$MsDesdeInputDueno -le 3000){ return 'dueno_input' }
  if($Procedencia -like 'shell:*' -and $Cubierto){ return 'lote' }
  'sin_procedencia'
}

function Get-DecisionColgado([string]$Propiedad,[string]$Nombre,[int]$ProcessId,[int]$PidShell,[bool]$Quieto,[bool]$Protegida){
  # A process with a window that does not answer, at the close after a case (libro_lote.ps1 -Cerrar). t-menu-1,
  # 2026-10-09: a secondary explorer.exe born in the case hung behind an application error dialog and held the batch
  # 11 min; Explorer is a shell host, so the ledger never closed it. A hung program answers no close request, so it is
  # stopped by its exact PID, only with positive provenance from this batch ('lote'), never the shell's explorer (the
  # one with the taskbar), VS Code, Opera, the terminals, the Claude app, BAXY, another shell host or a harness
  # process ($Protegida). Any program but Explorer (which holds no document) also needs the person idle over its life.
  # Returns 'detener' | 'no_tocar:<why>'.
  $nunca=@('Code','opera','opera_gx','launcher','WindowsTerminal','Claude','Baxy','baxy-core','ApplicationFrameHost','svchost',
           'dwm','sihost','ShellExperienceHost','StartMenuExperienceHost','SearchHost','TextInputHost','RuntimeBroker','csrss','winlogon')
  if($Protegida -or $nunca -contains $Nombre){ return 'no_tocar:protegida' }
  if($ProcessId -le 4 -or ($Nombre -eq 'explorer' -and ($PidShell -le 0 -or $ProcessId -eq $PidShell))){ return 'no_tocar:shell' }
  if($Propiedad -ne 'lote'){ return 'no_tocar:no_es_del_lote' }
  if($Nombre -ne 'explorer' -and -not $Quieto){ return 'no_tocar:dueno_no_quieto' }
  'detener'
}

function Get-DecisionVentanaNueva([string]$Propiedad,[bool]$DuenoActivo,[bool]$Compartido,[bool]$Protegida){
  # A window that did not exist when the case started. In a process of the batch it goes with its process. In a
  # process of the person it is closed only by that window (never the process), only when the person gave no input
  # during the case, and never in a shared shell host (Explorer windows have their own rule) or a protected app.
  # Returns 'con_su_proceso' | 'cerrar_ventana' | 'no_tocar'.
  if($Protegida){ return 'no_tocar' }
  if($Propiedad -eq 'lote'){ return 'con_su_proceso' }
  if($Propiedad -ne 'dueno' -or $DuenoActivo -or $Compartido){ return 'no_tocar' }
  'cerrar_ventana'
}

function Get-DecisionProductor($Hecho,[bool]$DeEsteLote){
  # A case that needs what an earlier one leaves (casos.json "requiere"). $Hecho: the producer's marker
  # logs/v2-<id>.hecho (batch.sh writes it only AFTER the producer's mission ran: {caso, conductor_exit, veredicto}),
  # or $null; $DeEsteLote: the marker is newer than the batch ledger. The case photo is never proof: it is taken
  # before the producer's states, so it exists even when the producer did not run.
  # Returns 'no_corrio_antes' | 'productor_fallo' (conductor failed, or a judge's veredicto 'fallo') |
  # 'sin_veredicto' (it ran, nobody judged it yet: the case runs flagged productor_sin_verificar, the judge leaves it
  # out if the producer failed) | 'exito'.
  if(-not $Hecho -or -not $DeEsteLote){ return 'no_corrio_antes' }
  if($null -eq $Hecho.conductor_exit -or [int]$Hecho.conductor_exit -ne 0){ return 'productor_fallo' }
  if([string]$Hecho.veredicto -eq 'fallo'){ return 'productor_fallo' }
  if([string]$Hecho.veredicto -eq 'exito'){ return 'exito' }
  'sin_veredicto'
}

function Get-DecisionVerificado([string]$Resultado,[bool]$DelLote,[bool]$ProcesoVivo){
  # A close is verified only after reading the process back: one of the batch still running is not closed, whatever
  # the close reported (v3-02: 'cerrada' while POWERPNT kept running).
  if($Resultado -like 'no_cierra*'){ return $false }
  if($DelLote -and $ProcesoVivo){ return $false }
  $true
}

# A leftover of an earlier case, batch or tanda (state sin_restos): a running process whose exact key is in the
# persistent harness book (apps_comun.ps1, procesos_arnes.jsonl or documentos.jsonl).
# $E: @{ protegida (VS Code, Opera, a terminal, the Claude app, BAXY, a shell host, the harness's interpreters);
#        dueno (the current batch ledger gave it to the person: born right after their input); office (driven through
#        COM: Stop-ProcesoDelLote checks every open document is the harness's); ventanas (hwnds it shows now, a dialog as
#        its owner); libro (every hwnd recorded for it) }
# Returns 'no_tocar:protegida' | 'no_tocar:del_dueno' | 'office' | 'sin_ventanas' (nothing to cover the case: left
# running, never stopped) | 'no_cierra:ventanas_nuevas' (a window nobody recorded: maybe the person's, opened in that
# same instance) | 'cerrar_ventanas' (each one by a normal close: an app with unsaved work asks, and is left asking).
#   ajenas (how many of its windows are, as the root of their owner chain, a window of ANOTHER process: a dialog of
#   it owned by the person's window; a normal close of that root would close the person's window)
function Get-DecisionResto($E){
  if($E.protegida){ return 'no_tocar:protegida' }
  if($E.dueno){ return 'no_tocar:del_dueno' }
  if($E.office){ return 'office' }
  $ahora=@(@($E.ventanas) | Where-Object { $null -ne $_ } | ForEach-Object { [long]$_ })
  if($ahora.Count -eq 0){ return 'sin_ventanas' }
  if([int]$E.ajenas -gt 0){ return 'no_cierra:ventana_de_otro_proceso' }
  $libro=@(@($E.libro) | Where-Object { $null -ne $_ } | ForEach-Object { [long]$_ })
  if(@($ahora | Where-Object { $libro -notcontains $_ }).Count -gt 0){ return 'no_cierra:ventanas_nuevas' }
  'cerrar_ventanas'
}

# Pasada r9: a OneNote leftover (ONENOTE:10380) still showed its recorded window after every close for 3 h, and each
# sin_restos tried again (dialogs, close, 8 s wait) twice a case: 15 s of median each time, 0 closes in 82 tries. A
# close that failed on exactly this process ($Clave, pid and start) with exactly these windows is not tried again for
# $Vigencia seconds: it stays in quedan (the state still does not verify). Another window or a later time: tried again.
# $Memo: {clave: {ventanas: "h1 h2" (sorted), t: epoch s}} of this batch (sin_restos.ps1). Returns 'intentar' |
# 'sin_reintento'.
function Get-DecisionReintentoResto($Memo,[string]$Clave,$Ventanas,[double]$Ahora,[double]$Vigencia=600){
  if(-not $Memo -or -not $Memo.PSObject.Properties[$Clave]){ return 'intentar' }
  $m=$Memo.$Clave
  $v=(@(@($Ventanas) | Where-Object { $null -ne $_ } | ForEach-Object { [long]$_ } | Sort-Object) -join ' ')
  if([string]$m.ventanas -ne $v -or $v -eq ''){ return 'intentar' }
  if(($Ahora - [double]$m.t) -ge $Vigencia -or ($Ahora - [double]$m.t) -lt 0){ return 'intentar' }
  'sin_reintento'
}

# An Office leftover whose COM answers nothing readable (measured 2026-10-08: Word gave one document with every
# property empty, PowerPoint zero presentations while its 'Presentacion1' window was on screen), so the document check
# of Stop-ProcesoDelLote refuses it. Its windows still name every document it holds ('<document> - <app>'): when each
# titled window names a document a state created in THAT exact process ($Creados, documentos.jsonl by pid and start)
# the process holds nothing else (an instance numbers every new document, so the person's would be another name).
# Returns 'detener' | 'no_cierra:sin_titulos' | 'no_cierra:titulo_ajeno'.
# Only after COM gave nothing readable ('no_cierra:office_sin_com' or 'no_cierra:office_ilegible'): when COM READ a
# document that is not the harness's ('documento_ajeno'), a title list missing its window (another virtual desktop, a
# hung window) must never let the process be stopped.
function Get-DecisionOfficePorTitulos($Titulos,$Creados){
  $t=@(@($Titulos) | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) })
  $c=@(@($Creados) | Where-Object { $_ } | ForEach-Object { [string]$_ })
  if($t.Count -eq 0 -or $c.Count -eq 0){ return 'no_cierra:sin_titulos' }
  foreach($x in $t){
    $nombre=([string]$x -split ' - ',2)[0].Trim()
    if($c -notcontains $nombre){ return 'no_cierra:titulo_ajeno' }
  }
  'detener'
}

# What hides the case's application before it starts (state sin_obstaculos, banco r6): an always-on-top window of a
# program that is neither the shell, the harness nor BAXY ($Excluidos) and covers at least a tenth of the screen (the
# On-Screen Keyboard a case opened sat over every later case), or a dialog that disables the main window of the case's
# application (a save prompt an earlier case or tanda left: Excel and Word showed only their 'Guardar este archivo').
# $Ventanas: @{ proceso; encima (bool); x; y; w; h }. $Pantalla: @{ w; h }. Returns the processes of what covers it.
function Get-DecisionEncima($Ventanas,$Pantalla,[string[]]$Excluidos){
  $area=[double]$Pantalla.w*[double]$Pantalla.h
  foreach($v in @($Ventanas)){
    if($null -eq $v -or -not $v.encima -or $Excluidos -contains [string]$v.proceso -or $area -le 0){ continue }
    $ix=[Math]::Max(0,[Math]::Min([double]$v.x+[double]$v.w,[double]$Pantalla.w)-[Math]::Max([double]$v.x,0))
    $iy=[Math]::Max(0,[Math]::Min([double]$v.y+[double]$v.h,[double]$Pantalla.h)-[Math]::Max([double]$v.y,0))
    if(($ix*$iy)/$area -ge 0.1){ [string]$v.proceso }
  }
}

# $Ventanas of one process: @{ hwnd; dueno (hwnd of the root of its owner chain, 0 when it has no owner);
# dueno_habilitado (bool) }. A visible window whose owner is a window of the same process that is disabled is that
# process's modal dialog: returns those hwnds.
function Get-DecisionDialogos($Ventanas){
  $propias=@(@($Ventanas) | Where-Object { $null -ne $_ } | ForEach-Object { [long]$_.hwnd })
  foreach($v in @($Ventanas)){
    if($null -eq $v -or [long]$v.dueno -eq 0 -or [long]$v.dueno -eq [long]$v.hwnd -or $v.dueno_habilitado){ continue }
    if($propias -contains [long]$v.dueno){ [long]$v.hwnd }
  }
}

# A modal dialog of an Office process of the harness (Close-DialogosModales, before the COM document check): it is
# cancelled only when the window it blocks names a document of the harness ($Documento: the owner window's title up to
# ' - '), one a state created in that exact process ($Creados) or a fixture file ($Fixtures, with or without its
# extension). A dialog over the person's document opened in that same instance (their Save As, their save prompt) is
# theirs and is never touched. Returns 'cancelar' | 'no_tocar:documento_ajeno'.
function Get-DecisionDialogoOffice([string]$Documento,$Creados,$Fixtures){
  $d=([string]$Documento).Trim()
  if(-not $d){ return 'no_tocar:documento_ajeno' }
  if(@(@($Creados)+@($Fixtures) | Where-Object { $_ } | ForEach-Object { [string]$_ }) -contains $d){ return 'cancelar' }
  'no_tocar:documento_ajeno'
}

# How Close-WindowExact (comun.ps1) answers a dialog its own close raised: 'cancelar' for a window that is not the
# harness's (-SinConfirmar wins over everything: nothing over it is ever confirmed), 'sin_guardar' for a harness
# document, else 'confirmar'.
function Get-DecisionModoTrasCerrar([bool]$SinGuardar,[bool]$SinConfirmar){
  if($SinConfirmar){ return 'cancelar' }
  if($SinGuardar){ return 'sin_guardar' }
  'confirmar'
}

# The ONE button the harness presses in a dialog over a window it already proved its own (Close-DialogosDeVentana,
# comun.ps1). $Botones: the dialog's button names. $Modo:
#   'cancelar'     a dialog left open over the window (Paint's resize dialog a case left): Cancelar / Cancel / Cerrar /
#                  Close. Cancelling never loses data.
#   'confirmar'    the confirmation the harness's own close raised (Windows Terminal: close all tabs?): the button that
#                  closes. Never in a save prompt (a button that saves or discards is data, not a confirmation), never
#                  Aceptar/OK (they also apply a settings dialog), never Cancel.
#   'sin_guardar'  the save prompt of a harness window (its test document): No guardar / Don't save; without one, as
#                  'confirmar'.
# Returns the exact button name, or '' (nothing is pressed). Non-ASCII built from code points (ASCII-only file).
function Get-DecisionBotonDialogo($Botones,[string]$Modo){
  $b=@(@($Botones) | Where-Object { $_ } | ForEach-Object { ([string]$_).Trim() })
  $n=[string][char]0xF1; $i=[string][char]0xED
  $guarda='(?i)guardar|save'
  $sinGuardar='^(?i:No guardar|Don.t save|Do not save)$'
  $cierraTodo="^(?i:Cerrar todo|Cerrar todas|Cerrar todas las pesta$($n)as|Close all|Close all tabs)$"
  $cierra="^(?i:Cerrar|Close|S$i|Yes|Cerrar ventana|Close window)$"
  $cancela='^(?i:Cancelar|Cancel|Cerrar|Close)$'
  if($Modo -eq 'cancelar'){
    foreach($x in $b){ if($x -match $cancela){ return $x } }
    return ''
  }
  if($Modo -ne 'confirmar' -and $Modo -ne 'sin_guardar'){ return '' }
  if($Modo -eq 'sin_guardar'){ foreach($x in $b){ if($x -match $sinGuardar){ return $x } } }
  if(@($b | Where-Object { $_ -match $guarda }).Count -gt 0){ return '' }
  foreach($x in $b){ if($x -match $cierraTodo){ return $x } }
  foreach($x in $b){ if($x -match $cierra){ return $x } }
  ''
}

# Whether the harness can run one command elevated without a UAC prompt: UAC on (EnableLUA 1) with
# ConsentPromptBehaviorAdmin 0 ("elevate without prompting") for a user in Administrators. UAC off (EnableLUA 0) is
# $false: there every process of an administrator, the harness included, already runs with full rights, so nothing is
# elevated above the harness and nothing needs raising (revision 2026-10-08: with $true there, every window of the
# person counted as "elevated"). Anything else (a prompt, a standard user, an unreadable policy) is $false.
function Get-DecisionUacSilencioso($EnableLua,$Consent,[bool]$Admin){
  if(-not $Admin -or $null -eq $EnableLua -or [int]$EnableLua -eq 0){ return $false }
  ($null -ne $Consent -and [int]$Consent -eq 0)
}

# Ancestors of a process, nearest first: $Tabla pid -> @{ padre; nacio }. A parent pid counts only while that process
# was born before its child (a reused pid is another process); the walk stops at a gap or a loop.
function Get-AncestrosProceso($Tabla,[int]$ProcessId){
  $vistos=@{ $ProcessId=$true }; $actual=$Tabla[$ProcessId]
  while($actual){
    $padre=[int]$actual.padre
    if($padre -le 0 -or $vistos.ContainsKey($padre) -or -not $Tabla.ContainsKey($padre)){ break }
    $p=$Tabla[$padre]
    if([double]$p.nacio -gt [double]$actual.nacio){ break }
    $vistos[$padre]=$true; $padre; $actual=$p
  }
}

# Harness data for sin_obstaculos, never product code: processes whose windows are never an obstacle it acts on: the
# shell, the harness (its interpreters, the simulated user's window), the agents' terminals and editors, and BAXY.
function Get-ExcluidosObstaculos(){
  @('explorer','ShellExperienceHost','StartMenuExperienceHost','SearchHost','SearchApp','TextInputHost','dwm','LockApp',
    'ShellHost','python','pythonw','powershell','pwsh','conhost','OpenConsole','WindowsTerminal','Code','Claude','Baxy',
    'baxy-core')
}
# ...and, for the elevated closes, also the plain console and the system's own logon and consent processes.
function Get-ProtegidosElevadas(){ @(Get-ExcluidosObstaculos)+@('cmd','consent','LogonUI','winlogon','csrss') }

# Elevated windows that hide a case and sin_obstaculos closes (pasada r9: a Taskmgr, Resource Monitors and Services
# consoles BAXY opened elevated stayed over the next cases; the harness could not close them). $Ventanas: @{ pid;
# proceso; elevada; hwnd }. ONLY a process the batch or the harness is proven to have started ($DelLote: pids the
# batch ledger classed 'lote' or the harness book holds); an elevated window of anybody else (the person's admin
# terminal, an installer, another agent's tools) is never chosen, whatever it is (revision 2026-10-08). Never either:
# a protected process ($Protegidos: VS Code, the Claude app, the shell, the terminals and interpreters...), a window
# the harness opened for the case's state ($Propios: hwnds), the harness's own process chain ($Cadena: pids), or a
# process descended from an agent's tool ($DeAgente: pids whose ancestors include VS Code or the Claude app). Nothing
# when the harness itself runs elevated ($ArnesElevado: it reads and closes those windows like any other). Returns
# @{ pid; proceso } once per process.
function Get-DecisionElevadas($Ventanas,[string[]]$Protegidos,$Propios,$Cadena,$DeAgente,$DelLote,[bool]$ArnesElevado=$false){
  if($ArnesElevado){ return }
  $vistos=@{}
  foreach($v in @($Ventanas)){
    if($null -eq $v -or $v.elevada -ne $true){ continue }
    $p=[int]$v.pid
    if($vistos.ContainsKey($p) -or $Protegidos -contains [string]$v.proceso){ continue }
    if(@($Cadena) -contains $p -or @($DeAgente) -contains $p -or @($DelLote) -notcontains $p){ continue }
    # A process with a window the harness opened for this case keeps every window (it is the case's app).
    if(@(@($Ventanas) | Where-Object { [int]$_.pid -eq $p -and @($Propios) -contains [long]$_.hwnd }).Count){ $vistos[$p]=$true; continue }
    $vistos[$p]=$true
    [pscustomobject]@{ pid=$p; proceso=[string]$v.proceso }
  }
}

# The harness's test repo (repo_prueba_comun.ps1) is valid only exactly as built: main checked out, its commits in
# order ($Mensajes oldest first; $S.commits is newest first), main plus $Rama as the only branches, a clean tree.
function Get-DecisionRepoPrueba($S,$Mensajes,[string]$Rama){
  if(-not $S -or -not $S.existe -or $S.rama -ne 'main' -or -not $S.limpio){ return $false }
  $esperados=@($Mensajes); [array]::Reverse($esperados)
  if((@($S.commits) -join "`n") -cne ($esperados -join "`n")){ return $false }
  ((@($S.ramas) | Sort-Object) -join ',') -ceq ((@('main',$Rama) | Sort-Object) -join ',')
}

# The folder of the test repo may be emptied and rebuilt only when it is the harness's (revision 2026-10-08: it was
# deleted whenever it was not exactly as built, with no proof of whose it was): it is missing or empty, or git read it
# ($S.git_ok) and every commit on every ref has the harness's author ($S.autores: e-mails, prueba@baxy.invalid).
# Anything else (another repository, a folder with no git, a git that failed) is never touched.
function Get-DecisionRepoDelArnes($S){
  if(-not $S -or -not $S.existe -or $S.vacia){ return $true }
  $a=@(@($S.autores) | Where-Object { $_ } | ForEach-Object { ([string]$_).Trim() })
  [bool]($S.git_ok -and $a.Count -gt 0 -and @($a | Where-Object { $_ -cne 'prueba@baxy.invalid' }).Count -eq 0)
}

# GitHub Desktop's Options dialog is open: its Accounts and Appearance tabs are both named in the window.
function Get-DecisionOpcionesAbiertas($Nombres){
  $n=@(@($Nombres) | Where-Object { $_ } | ForEach-Object { ([string]$_).Trim() })
  ($n -ccontains 'Accounts' -and $n -ccontains 'Appearance')
}

# GitHub Desktop shows the test repo as its current repository: its toolbar button is named exactly
# 'Current repository <repo>' and no text says it cannot find a repository (r9: "Can't find "RicardoYMontiel"").
function Get-DecisionGithubRepo($Nombres,[string]$Repo){
  $n=@(@($Nombres) | Where-Object { $_ } | ForEach-Object { ([string]$_).Trim() })
  if(@($n | Where-Object { $_ -match "^Can.t find" }).Count){ return $false }
  @($n | Where-Object { $_ -ceq "Current repository $Repo" }).Count -gt 0
}

# A window is in a light theme when the mean brightness (0..255) of its sampled pixels is above the middle.
function Get-DecisionTemaClaro($Brillo){ ($null -ne $Brillo -and [double]$Brillo -ge 160) }

# Sticky Notes asking for an account (pasada r9: its onboarding and the Microsoft account picker a case opened sat
# over v3-34/35/36 and t-drag-3). $Nombres: UIA names of its windows (and of an account window). Non-ASCII from code
# points (ASCII-only file).
# A note window's own name carries its text ('<color> ventana de nota. <text>'): never read as a prompt (revision
# 2026-10-08: a note saying "sign in" left the state on pide_cuenta).
function Get-DecisionPideCuenta($Nombres){
  $o=[string][char]0xF3
  $re="(?i)iniciar sesi$o|iniciando sesi$o|vamos a iniciar sesi$o|\bsign in\b|\bsigning in\b|let.s get you signed in"
  @(@($Nombres) | Where-Object { $_ -and ([string]$_) -notmatch '(?i)(ventana de nota|note window)\.' -and ([string]$_) -match $re }).Count -gt 0
}

# The ONE button that dismisses an account prompt without signing in: Ahora no / Not now / Omitir / Skip, else
# Cancelar / Cancel. Never one that signs in or closes a note. Returns its exact name or ''.
function Get-DecisionBotonSinCuenta($Botones){
  $b=@(@($Botones) | Where-Object { $_ } | ForEach-Object { ([string]$_).Trim() })
  foreach($re in @('^(?i:Ahora no|Not now|Omitir|Skip|Quiz.s m.s tarde|Maybe later)$','^(?i:Cancelar|Cancel)$')){
    foreach($x in $b){ if($x -match $re){ return $x } }
  }
  ''
}

# The note of the harness is on the screen: a note window whose name ends with '. <texto>' (Sticky Notes names it
# '<color> ventana de nota. <text>' / '<color> note window. <text>').
function Get-DecisionNotaVisible($Nombres,[string]$Texto){
  if(-not $Texto){ return $true }
  @(@($Nombres) | Where-Object { $_ -and ([string]$_).EndsWith(". $Texto") -and ([string]$_) -match '(?i)nota|note' }).Count -gt 0
}

# What one window of Outlook (classic) is, for outlook_listo. $Titulo, $Clase of a top-level window of OUTLOOK.EXE:
#   'principal'  its main window, loaded (class rctrl_renwnd32, not "Abriendo"/"Opening"/"Cargando perfil")
#   'cargando'   still opening the profile
#   'cuenta'     the e-mail account setup (pasada r9: "Configuracion de cuenta de correo electronico" with Conectar)
#   'avisos'     the Reminders window ("86 aviso(s)", measured 2026-10-08): closed, never dismissed (that changes the
#                person's calendar in their account)
#   'otra'       anything else (left alone). Non-ASCII from code points (ASCII-only file).
function Get-DecisionVentanaOutlook([string]$Titulo,[string]$Clase){
  $o=[string][char]0xF3
  if($Titulo -match "(?i)^(abriendo|opening)\b|cargando perfil|loading profile"){ return 'cargando' }
  if($Titulo -match "(?i)configuraci${o}n de cuenta|account setup|agregar cuenta|add account|cuenta de correo electr${o}nico"){ return 'cuenta' }
  if($Titulo -match '(?i)^\d+\s+(aviso|avisos|reminder|reminders)\b|aviso\(s\)|reminder\(s\)'){ return 'avisos' }
  if($Clase -eq 'rctrl_renwnd32' -and $Titulo -match '(?i)\s-\s*Outlook$'){ return 'principal' }
  'otra'
}

# The main window is on the mail module: its title names the inbox ("Bandeja de entrada - ... - Outlook").
function Get-DecisionOutlookEnCorreo([string]$Titulo){ $Titulo -match '(?i)^(bandeja de entrada|inbox)\s-\s' }

# The value registro_escribe writes. $Arg: '<HKCU\Software\...>|<name>|<value>'; <value> 'dword:<n>' (0..4294967295)
# is a REG_DWORD; 'bin32@<offset>:<n>' replaces only the little-endian 32-bit word at byte <offset> (a multiple of 4)
# of an EXISTING REG_BINARY (7-Zip keeps a folder view's sort column there: revision 2026-10-08, v3-49); anything else
# is a REG_SZ where '{Documentos}' is $Documentos. Only under HKCU\Software, no '..'.
# Returns @{ ok; clave (without 'HKCU\'); nombre; valor; tipo ('DWord'|'String'|'Bin32'); offset; nota }.
function Get-DecisionRegistroEscribe([string]$Arg,[string]$Documentos){
  $no=@{ ok=$false; nota='HKCU\Software\ruta|nombre|valor (dword:<n>, bin32@<offset>:<n> o texto; {Documentos})' }
  $clave,$nombre,$valor=([string]$Arg) -split '\|',3
  if(-not $clave -or -not $nombre -or $null -eq $valor -or $clave -notmatch '^(?i)HKCU\\Software\\.+$' -or $clave -match '\\\.\.(\\|$)'){ return $no }
  if($valor -match '^bin32@(\d{1,6}):(\d{1,10})$'){
    $o=[int]$Matches[1]; $n=[uint64]$Matches[2]
    if($o % 4 -ne 0 -or $n -gt 4294967295){ return $no }
    return @{ ok=$true; clave=$clave.Substring(5); nombre=$nombre; valor=[uint32]$n; tipo='Bin32'; offset=$o; nota='' }
  }
  if($valor -match '^dword:(\d{1,10})$'){
    $n=[uint64]$Matches[1]; if($n -gt 4294967295){ return $no }
    # Set-ItemProperty takes a DWORD above 2^31 as the signed Int32 with the same bits.
    return @{ ok=$true; clave=$clave.Substring(5); nombre=$nombre; valor=[BitConverter]::ToInt32([BitConverter]::GetBytes([uint32]$n),0); tipo='DWord'; nota='' }
  }
  @{ ok=$true; clave=$clave.Substring(5); nombre=$nombre; valor=$valor.Replace('{Documentos}',[string]$Documentos); tipo='String'; nota='' }
}

# The bytes registro_escribe writes for a 'Bin32' value: $Antes (the REG_BINARY now) with the 32-bit little-endian word
# at $Offset set to $Valor; $null when the value is missing or too short (nothing is invented). Pure.
function Get-DecisionBinarioParcheado($Antes,[int]$Offset,[uint32]$Valor){
  if($null -eq $Antes -or $Antes -isnot [byte[]] -or $Antes.Length -lt $Offset+4){ return $null }
  $b=[byte[]]$Antes.Clone()
  [Array]::Copy([BitConverter]::GetBytes($Valor),0,$b,$Offset,4)
  ,$b
}
