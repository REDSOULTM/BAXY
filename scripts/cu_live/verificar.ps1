# Harness verifier (goal v3): dumps what a reviewer needs to judge a case WITHOUT reading BAXY's reply.
# usage: verificar.ps1 -Caso <id> [-Fase antes|despues] [-Antes "<pids>"] [-Out <file.json>]
#   -Antes: the PIDs running before the case (apps_del_caso.ps1 -Listar), so a window whose process the case started
#   counts as the case's.
#   Writes %LOCALAPPDATA%\BAXY\cu-universal-evidencia\v2-<id>\verificacion-<fase>.json (id '@' -> '-', as batch.sh)
#   and prints its path. Read only: it never clicks, types, focuses or closes anything.
# What it dumps:
#   - caso: id, app, turns and the manifest's "verify" text (cases/v3_manifiesto.json) when the case is there;
#     a bench case with no manifest entry gives its turns (cases/<id>.turns);
#   - ventanas: for each top-level window of the case's app(s) (by learned process, then by name in the title):
#     title, process, rect, foreground, minimized, and from UIA: selected items, toggles that are on, values of
#     edit/combo/document controls, the status bar, the focused element and a count per control type;
#     the names of list/tree/tab/header items (elementos) and of texts (textos) in tree order, 150 of each at most,
#     and whether the app runs elevated (then UIA sees nothing inside it: judge from after.png);
#   - exploradores: every Explorer window's folder, sort columns and selected items (Shell COM);
#   - archivos: every file under Documentos\baxy-prueba-v3 with size, modification time and SHA-256; image
#     width/height; zip entries; .docx paragraphs (text, bold, alignment); .pptx slide count and slide titles;
#   - pantallas: the screens' bounds (a full-screen capture is compared with them);
#   - portapapeles: its text, only when the case's verify text names the clipboard.
# Privacy (the person's windows are never dumped in full):
#   - after the case, the windows the case points at are added, manifest entry or not: those BAXY read or acted on
#     (journal-caso.json "tocadas"), the one in front when the conductor ended (after-mision.json) and those whose
#     process was born during the case (8 at most); each says why it is there in "app";
#   - a window is dumped in full only when it is the harness's (propios.jsonl, or a dialog owned by one) or its
#     process started during the case (not in -Antes); any other window of the case's app is the person's and gets
#     a reduced dump: no title, no item names, no texts, no values, no status bar; only the ribbon/navigation
#     controls that are selected or on (tabs, buttons, menu items, radio buttons, check boxes) and the counts;
#   - an Explorer window is dumped in full only on a folder under a baxy-prueba* folder; any other folder the case
#     names gives only its path and sort order, never its items or selection;
#   - the foreground window is named only when it is dumped in full.
# VS Code and Opera windows are never read. Text values are cut at 300 characters.
param([Parameter(Mandatory=$true)][string]$Caso,[string]$Fase='despues',[string]$Antes='',[string]$Out='')
$ErrorActionPreference='Stop'
$estado=Join-Path $PSScriptRoot 'estado'
. (Join-Path $PSScriptRoot 'estado\comun.ps1')
. (Join-Path $PSScriptRoot 'estado\apps_comun.ps1')
. (Join-Path $PSScriptRoot 'estado\explorador_comun.ps1')
Add-Type -AssemblyName System.IO.Compression,System.IO.Compression.FileSystem,System.Windows.Forms
$ErrorActionPreference='Continue'

$tid=($Caso -split '@')[0]
$man=$null
$mp=Join-Path $PSScriptRoot 'cases\v3_manifiesto.json'
if(Test-Path $mp){ $m=[IO.File]::ReadAllText($mp,[Text.Encoding]::UTF8) | ConvertFrom-Json; if($m.PSObject.Properties[$tid]){ $man=$m.$tid } }
$evDir=Join-Path $env:LOCALAPPDATA ("BAXY\cu-universal-evidencia\v2-{0}" -f ($Caso -replace '@','-'))
if(-not $Out){
  if(-not (Test-Path $evDir)){ New-Item -ItemType Directory -Force $evDir | Out-Null }
  $Out=Join-Path $evDir "verificacion-$Fase.json"
}else{ $evDir=Split-Path -Parent $Out }
# Until the very end the file says the verification is not complete: a run cut by the harness's ceiling (batch.sh,
# servidor_ps.sh) or stopped with its server never leaves an earlier run's dump reading as this case's.
[IO.File]::WriteAllText($Out,(([ordered]@{ caso=$Caso; fase=$Fase; hora=(Get-Date).ToString('s'); completa=$false; motivo='en_curso' } | ConvertTo-Json -Compress)+"`n"),(New-Object Text.UTF8Encoding $false))
# Windows whose program does not answer (t-menu-1, 2026-10-09: a hung secondary explorer.exe held verify 11 min): no
# UIA or COM read touches them or their process; they are listed as "colgada" and the dump is not complete.
$colgadas=@(Get-VentanasColgadas)
$pidsColgados=@($colgadas | ForEach-Object { [int]$_.pid } | Select-Object -Unique)
function Cut([string]$s,[int]$n=300){ if($null -eq $s){ return $null }; if($s.Length -gt $n){ $s.Substring(0,$n)+'...' }else{ $s } }

# Apps of the case: "Calculadora + Bloc de notas" -> two; "Outlook (classic)" is also looked up as "Outlook".
# Windows whose title does not carry the app's name are found by the process the harness learned when it opened
# the app (apps.json); the few that neither show it nor were opened by the harness yet are listed here.
$Procesos=@{ 'Explorador de archivos'='explorer'; 'Terminal'='WindowsTerminal'; ('Notas r'+[char]0xE1+'pidas')='Microsoft.Notes'; '7-Zip File Manager'='7zFM'; 'OBS Studio'='obs64' }
# A bench case (cases/<id>.turns only, no manifest entry) names its places in its turns.
$turnosArchivo=Join-Path $PSScriptRoot "cases\$tid.turns"
$turnosCaso=@(if(-not $man -and (Test-Path -LiteralPath $turnosArchivo)){ [IO.File]::ReadAllLines($turnosArchivo,[Text.Encoding]::UTF8) | Where-Object { $_.Trim() } })
$texto=if($man){ (@($man.turns)+@($man.verify)) -join ' ' }else{ $turnosCaso -join ' ' }
function Test-Nombrado([string]$Titulo){
  foreach($t in @($Titulo -split ' - |: ' | Select-Object -First 2)){ $t=$t.Trim(); if($t.Length -ge 4 -and $texto -like "*$t*"){ return $true } }
  $false
}
$apps=@(if($man){ $man.app -split '\s*\+\s*' | Where-Object { $_ } })
$ventanas=@()
$vistas=@{}
$todas=@((Get-TopWindows) | Where-Object { $global:AppsProhibidos -notcontains $_.app_proceso -and $_.app_proceso -ne 'Baxy' })
foreach($a in $apps){
  $nombres=@($a, ($a -replace '\s*\(.*\)\s*$','')) | Select-Object -Unique
  $proc=$Procesos[$a]
  if(-not $proc){ $ap=Get-AppsAprendidas; foreach($n in $nombres){ if($ap[$n]){ $proc=$ap[$n] } }; if(-not $proc){ $s=Resolve-StartApp $nombres[-1]; if($s -and $ap[$s.Name]){ $proc=$ap[$s.Name] } } }
  # When the Start-menu entry proves which process is the app (Get-IdentidadApp), only those windows are the app's:
  # a browser page whose title names the app is not read.
  $s=$null; foreach($n in $nombres){ if(-not $s){ $s=Resolve-StartApp $n } }
  $ident=if($s -and -not $Procesos[$a]){ Get-IdentidadApp $s }else{ $null }
  $probada=($ident -and $ident.tipo -in @('aumid','exe','asociada'))
  foreach($w in $todas){
    $porNombre=@($nombres | Where-Object { $w.titulo -like "*$_*" }).Count -gt 0
    $porProceso=($proc -and ($w.app_proceso -eq $proc -or $w.proceso -eq $proc))
    if($probada){ $porProceso=(Test-IdentidadVentana $w $ident $s.Name); $porNombre=$false }
    # Explorer is the shell of the whole desktop: only its windows about something the case names (the folder or file in
    # the title appears in the turns or the verify text) are read, never the person's other folders.
    if($proc -eq 'explorer'){ $porProceso=($porProceso -and $w.clase -in @('CabinetWClass','#32770') -and (Test-Nombrado $w.titulo)); $porNombre=$false }
    if(($porNombre -or $porProceso) -and -not $vistas.ContainsKey($w.hwnd)){ $vistas[$w.hwnd]=$a; $ventanas+=$w }
  }
}
$fgh=[long][EstadoW32]::GetForegroundWindow()
# Whose each window is (see Privacy above).
$previos=@($Antes -split '\s+' | Where-Object { $_ } | ForEach-Object { [int]$_ })
# After the case, also the windows the case itself points at, with or without a manifest entry (BANCO_72 r23: the 72
# bench cases have none and every dump came out with no window): the top-level windows BAXY read or acted on
# (journal-caso.json "tocadas", journal_caso.py), the window in front when the conductor ended, before the person got
# the front back (after-mision.json, captura_mision.ps1), and the windows whose process was born during the case. Both
# files are this run's: evidencia_corre moves an earlier run's aside. Whose each one is still decides how much of it
# is dumped (Test-Completa below).
if($Fase -eq 'despues'){
  $senal=@{}
  $jc=Join-Path $evDir 'journal-caso.json'
  if(Test-Path -LiteralPath $jc){ try{ foreach($h in @(([IO.File]::ReadAllText($jc,[Text.Encoding]::UTF8) | ConvertFrom-Json).tocadas)){ if($h -and -not $senal.ContainsKey([long]$h)){ $senal[[long]$h]='tocada_por_baxy' } } }catch{} }
  $am=Join-Path $evDir 'after-mision.json'
  if(Test-Path -LiteralPath $am){ try{ $h=[long](([IO.File]::ReadAllText($am,[Text.Encoding]::UTF8) | ConvertFrom-Json).primer_plano.hwnd); if($h -and -not $senal.ContainsKey($h)){ $senal[$h]='primer_plano_mision' } }catch{} }
  $extra=0
  foreach($w in $todas){
    if($vistas.ContainsKey($w.hwnd) -or $extra -ge 8){ continue }
    $por=$senal[[long]$w.hwnd]
    if(-not $por -and $previos.Count -gt 0 -and $previos -notcontains [int]$w.app_pid){ $por='nacida_en_el_caso' }
    if(-not $por){ continue }
    # Explorer windows: only ones about a folder (the desktop and the taskbar are Explorer's too).
    if($w.app_proceso -eq 'explorer' -and $w.clase -notin @('CabinetWClass','#32770')){ continue }
    $vistas[$w.hwnd]=$por; $ventanas+=$w; $extra++
  }
}
$propiasH=@(Get-Propios | ForEach-Object { [long]$_.hwnd })
$rutasExpl=@{}; foreach($x in @(Get-ShellExplorerWindows)){ $rutasExpl[[long]$x.HWND]=(Get-ShellPath $x) }
function Test-RutaDePrueba([string]$Ruta){ $Ruta -and $Ruta -match '\\baxy-prueba[^\\]*(\\|$)' }
function Test-Completa($W){
  if($W.app_proceso -eq 'explorer'){ return (Test-RutaDePrueba $rutasExpl[[long]$W.hwnd]) }
  if($propiasH -contains [long][EstadoProc]::OwnerRoot([IntPtr][long]$W.hwnd) -or $propiasH -contains [long]$W.hwnd){ return $true }
  ($previos.Count -gt 0 -and $previos -notcontains [int]$W.app_pid)
}

function Get-Dump($W){
  if($pidsColgados -contains [int]$W.pid -or $pidsColgados -contains [int]$W.app_pid -or -not (Test-VentanaResponde ([IntPtr][long]$W.hwnd))){
    $script:saltadas+=[long]$W.hwnd
    return [ordered]@{ app=$vistas[$W.hwnd]; colgada=$true; proceso=$W.app_proceso; pid=$W.app_pid; hwnd=$W.hwnd; clase=$W.clase }
  }
  $completa=Test-Completa $W
  $el=[Windows.Automation.AutomationElement]::FromHandle([IntPtr][long]$W.hwnd)
  $r=New-Object EstadoW32+RECT; [void][EstadoW32]::GetWindowRect([IntPtr][long]$W.hwnd,[ref]$r)
  $d=[ordered]@{ app=$vistas[$W.hwnd]; completa=$completa; titulo=$(if($completa){ $W.titulo }else{ $null }); proceso=$W.app_proceso; pid=$W.app_pid; hwnd=$W.hwnd; clase=$W.clase
    rect=@($r.Left,$r.Top,$r.Right,$r.Bottom); primer_plano=($W.hwnd -eq $fgh); minimizada=[EstadoW32]::IsIconic([IntPtr][long]$W.hwnd)
    # An elevated app shows only empty panes to UIA from here: its dump says nothing about its state (use after.png).
    elevada=(Test-Elevada ([int]$W.app_pid)) }
  $sel=@(); $tog=@(); $val=@(); $barra=@(); $elem=@(); $txt=@(); $conteo=@{}
  $all=$null
  try{ $all=$el.FindAll('Descendants',[Windows.Automation.Condition]::TrueCondition) }catch{ $d['error']=$_.Exception.Message; return $d }
  # Ceiling of 6000 elements and of 20 s per window (an app that answers UIA slowly does not hold the batch).
  $n=0; $tope=(Get-Date).AddSeconds(20)
  foreach($e in $all){
    $n++; if($n -gt 6000){ $d['cortado']=$true; break }
    if(($n % 50) -eq 0 -and (Get-Date) -gt $tope){ $d['cortado']=$true; $d['cortado_por_tiempo']=$true; break }
    try{
      $c=$e.Current; $ct=$c.ControlType.ProgrammaticName -replace '^ControlType\.',''
      if(-not $ct){ $ct='Desconocido' }  # an empty key breaks ConvertFrom-Json in PowerShell 5.1
      $conteo[$ct]=1+[int]$conteo[$ct]
      # The person's window: only which ribbon/navigation controls are selected or on.
      if(-not $completa -and $ct -notin @('TabItem','Button','SplitButton','MenuItem','RadioButton','CheckBox')){ continue }
      $p=$null
      if($sel.Count -lt 80 -and $e.TryGetCurrentPattern([Windows.Automation.SelectionItemPattern]::Pattern,[ref]$p) -and $p.Current.IsSelected){ $sel+=[ordered]@{ tipo=$ct; nombre=(Cut $c.Name 120); id=$c.AutomationId } }
      $p=$null
      if($tog.Count -lt 80 -and $e.TryGetCurrentPattern([Windows.Automation.TogglePattern]::Pattern,[ref]$p) -and $p.Current.ToggleState -eq 'On'){ $tog+=[ordered]@{ tipo=$ct; nombre=(Cut $c.Name 120); id=$c.AutomationId } }
      $p=$null
      # Values only of controls a person can type in or pick from (search boxes, fields, combos, documents): list cells
      # of the person's items are not keyboard-focusable and are not dumped.
      if($val.Count -lt 60 -and $ct -in @('Edit','ComboBox','Document','Spinner','Slider') -and $c.IsKeyboardFocusable -and -not $c.IsPassword -and $e.TryGetCurrentPattern([Windows.Automation.ValuePattern]::Pattern,[ref]$p)){
        $v=$p.Current.Value; if(-not [string]::IsNullOrEmpty($v)){ $val+=[ordered]@{ tipo=$ct; nombre=(Cut $c.Name 120); id=$c.AutomationId; valor=(Cut $v) } }
      }
      $p=$null
      if($val.Count -lt 60 -and $ct -ne 'ScrollBar' -and $e.TryGetCurrentPattern([Windows.Automation.RangeValuePattern]::Pattern,[ref]$p)){ $val+=[ordered]@{ tipo=$ct; nombre=(Cut $c.Name 120); id=$c.AutomationId; valor=[string]$p.Current.Value } }
      # Item names and texts in tree order, 150 of each at most (the after.png screenshot already shows them).
      if($elem.Count -lt 150 -and $ct -in @('ListItem','TreeItem','DataItem','TabItem','HeaderItem') -and $c.Name){ $elem+=('{0}:{1}' -f $ct,(Cut $c.Name 80)) }
      if($txt.Count -lt 150 -and $ct -eq 'Text' -and $c.Name){ $txt+=(Cut $c.Name 80) }
      if($ct -eq 'StatusBar' -and $barra.Count -lt 30){
        foreach($k in $e.FindAll('Descendants',[Windows.Automation.Condition]::TrueCondition)){ if($k.Current.Name){ $barra+=(Cut $k.Current.Name 120) } }
        if($c.Name){ $barra+=(Cut $c.Name 120) }
      }
    }catch{}
  }
  if($completa){ $d['elementos']=$elem; $d['textos']=$txt }
  $d['seleccionados']=$sel; $d['activados']=$tog
  if($completa){ $d['valores']=$val; $d['barra_estado']=@($barra | Select-Object -Unique) }
  $o=[ordered]@{}; foreach($k in @($conteo.Keys | Sort-Object)){ $o[$k]=$conteo[$k] }; $d['conteo']=$o
  try{
    $f=[Windows.Automation.AutomationElement]::FocusedElement
    if($f -and $f.Current.ProcessId -eq $W.pid -or ($f -and $f.Current.ProcessId -eq $W.app_pid)){
      $d['foco']=[ordered]@{ tipo=($f.Current.ControlType.ProgrammaticName -replace '^ControlType\.','') }
      if($completa){ $d['foco']['nombre']=(Cut $f.Current.Name 120); $d['foco']['id']=$f.Current.AutomationId }
    }
  }catch{}
  $d
}

$dump=[ordered]@{ caso=$Caso; fase=$Fase; hora=(Get-Date).ToString('s') }
if($man){ $dump['app']=$man.app; $dump['turnos']=$man.turns; $dump['verificar']=$man.verify }
elseif($turnosCaso.Count){ $dump['turnos']=$turnosCaso }
# An owner preference that may already fulfil the order (estado/casos.json "precondicion"), read back with its
# read-only reader, so the reviewer judges the "ya estaba" variant from the dump and not from BAXY's reply.
try{
  $cj=[IO.File]::ReadAllText((Join-Path $estado 'casos.json'),[Text.Encoding]::UTF8) | ConvertFrom-Json
  if($cj.PSObject.Properties['precondicion'] -and $cj.precondicion.PSObject.Properties[$Caso]){
    $pc=$cj.precondicion.$Caso
    $dump['precondicion']=[ordered]@{ variante=$pc.variante; lee=$pc.lee; invierte=$pc.invierte }
    if($pc.lee){
      # In this process (a read-only state): a new powershell cost ~1.5 s more per case with a precondition.
      $l=@(& (Join-Path $estado 'base.ps1') -Estados ([string]$pc.lee) 2>&1 | ForEach-Object { "$_" } | Where-Object { $_ -match '^\{"estado"' })
      if($l.Count){ $dump['precondicion']['lectura']=("$($l[-1])" | ConvertFrom-Json) }
    }
  }
}catch{ $dump['precondicion_error']=$_.Exception.Message }
$saltadas=@()
$dump['ventanas']=@(foreach($w in $ventanas){ Get-Dump $w })
# The window in front: its title only when it is dumped in full (the person's window in front says only its process).
$dump['primer_plano']=@($todas | Where-Object { $_.hwnd -eq $fgh } | ForEach-Object { [ordered]@{ titulo=$(if($vistas.ContainsKey($_.hwnd) -and (Test-Completa $_)){ $_.titulo }else{ $null }); proceso=$_.app_proceso } })

# Explorer windows (Shell COM): folder, sort and selection.
$dump['exploradores']=@(foreach($x in Get-ShellExplorerWindows){
  # The person's other folders: only that a window exists, never where.
  $sel=@(); $orden=$null; $ruta=Get-ShellPath $x
  $prueba=Test-RutaDePrueba $ruta
  if(-not $prueba -and -not (Test-Nombrado $x.LocationName)){ [ordered]@{ hwnd=[long]$x.HWND; nombrada=$false }; continue }
  try{ $orden=$x.Document.SortColumns }catch{}
  # Items and selection only in a test folder; another folder the case names says only where it is and its sort.
  if(-not $prueba){ [ordered]@{ hwnd=[long]$x.HWND; nombrada=$true; de_prueba=$false; titulo=$x.LocationName; ruta=$ruta; orden=$orden }; continue }
  try{ foreach($i in $x.Document.SelectedItems()){ if($sel.Count -lt 50){ $sel+=$i.Name } } }catch{}
  [ordered]@{ hwnd=[long]$x.HWND; nombrada=$true; de_prueba=$true; titulo=$x.LocationName; ruta=$ruta; orden=$orden; seleccionados=$sel }
})

# Test files.
$raiz=Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'baxy-prueba-v3'
$arch=@()
if(Test-Path -LiteralPath $raiz){
  foreach($f in @(Get-ChildItem -LiteralPath $raiz -Recurse -Force)){
    $rel=$f.FullName.Substring($raiz.Length+1)
    if($f.PSIsContainer){ $arch+=[ordered]@{ ruta=$rel; carpeta=$true; elementos=@(Get-ChildItem -LiteralPath $f.FullName -Force).Count }; continue }
    $i=[ordered]@{ ruta=$rel; bytes=$f.Length; modificado=$f.LastWriteTimeUtc.ToString('o') }
    try{ if($f.Length -lt 50MB){ $i['sha256']=(Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash.ToLowerInvariant() } }catch{ $i['sha256']="error:$($_.Exception.Message)" }
    $ext=$f.Extension.ToLowerInvariant()
    try{
      if($ext -in @('.png','.jpg','.jpeg','.bmp','.gif')){ $im=[Drawing.Image]::FromFile($f.FullName); $i['ancho']=$im.Width; $i['alto']=$im.Height; $im.Dispose() }
      elseif($ext -in @('.zip','.docx','.pptx','.xlsx')){
        $z=[IO.Compression.ZipFile]::OpenRead($f.FullName)
        try{
          if($ext -eq '.zip'){ $i['entradas']=@($z.Entries | ForEach-Object { $_.FullName }) }
          elseif($ext -eq '.docx'){
            $e=$z.GetEntry('word/document.xml'); $sr=New-Object IO.StreamReader($e.Open()); $xml=$sr.ReadToEnd(); $sr.Dispose()
            $i['parrafos']=@($(foreach($pm in [regex]::Matches($xml,'<w:p[ >].*?</w:p>')){
              $t=-join @([regex]::Matches($pm.Value,'<w:t(?: [^>]*)?>([^<]*)</w:t>') | ForEach-Object { $_.Groups[1].Value })
              if($t){ [ordered]@{ texto=(Cut $t 200); negrita=($pm.Value -match '<w:b/>|<w:b w:val="(1|true)"/>'); alineacion=([regex]::Match($pm.Value,'<w:jc w:val="([^"]+)"').Groups[1].Value) } }
            }) | Select-Object -First 30)
          }
          elseif($ext -eq '.pptx'){
            $sl=@($z.Entries | Where-Object { $_.FullName -match '^ppt/slides/slide\d+\.xml$' } | Sort-Object { [int]([regex]::Match($_.FullName,'\d+').Value) })
            $i['diapositivas']=$sl.Count
            $i['textos']=@(foreach($s in $sl | Select-Object -First 20){ $sr=New-Object IO.StreamReader($s.Open()); $x=$sr.ReadToEnd(); $sr.Dispose(); Cut (( @([regex]::Matches($x,'<a:t>([^<]*)</a:t>') | ForEach-Object { $_.Groups[1].Value }) -join ' | ')) 200 })
          }
        } finally { $z.Dispose() }
      }
    }catch{ $i['error']=$_.Exception.Message }
    $arch+=$i
  }
}
$dump['archivos']=[ordered]@{ raiz=$raiz; existe=(Test-Path -LiteralPath $raiz); elementos=$arch }
$dump['pantallas']=@([Windows.Forms.Screen]::AllScreens | ForEach-Object { [ordered]@{ principal=$_.Primary; ancho=$_.Bounds.Width; alto=$_.Bounds.Height; x=$_.Bounds.X; y=$_.Bounds.Y } })
if($man -and $man.verify -match 'portapapeles|clipboard'){
  try{ $dump['portapapeles']=Cut ([Windows.Forms.Clipboard]::GetText()) 200 }catch{ $dump['portapapeles']="error:$($_.Exception.Message)" }
}
# Hung windows: their title only when a window of that process may be dumped in full (born during the case, or on a
# test folder); the person's say only their process.
$procsCaso=@($ventanas | ForEach-Object { [string]$_.app_proceso } | Select-Object -Unique)
$dump['colgadas']=@(foreach($c in $colgadas){
  $nacida=($previos.Count -gt 0 -and $previos -notcontains [int]$c.pid)
  $ver=($nacida -or $c.titulo -match 'baxy-prueba')
  [ordered]@{ proceso=$c.proceso; pid=$c.pid; hwnd=$c.hwnd; clase=$c.clase; titulo=$(if($ver){ Cut $c.titulo 120 }else{ $null }); nacida_en_el_caso=$nacida }
})
# Not complete when a hung window may hide what the case changed: a window of the case's app was skipped, or the hung
# program is Explorer (the Shell windows were read only where their host answered) or was born during the case.
$relevantes=@($colgadas | Where-Object { $procsCaso -contains $_.proceso -or $_.proceso -eq 'explorer' -or ($previos.Count -gt 0 -and $previos -notcontains [int]$_.pid) })
$dump['completa']=($saltadas.Count -eq 0 -and $relevantes.Count -eq 0)
if(-not $dump['completa']){ $dump['motivo']='ventanas_colgadas' }
$json=$dump | ConvertTo-Json -Depth 8
[IO.File]::WriteAllText($Out,$json+"`n",(New-Object Text.UTF8Encoding $false))
$Out
