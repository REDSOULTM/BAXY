# State notas_sin_cuenta[:<texto> | :sin=<texto>]: Sticky Notes (Notas rapidas) freshly open WITHOUT an account, with the harness's
# test notes in its local store. Pasada r9: it sat on its sign-in onboarding and on the Microsoft account picker a case
# opened, so v3-34/35 (create a note), v3-36 (search "dentista") and t-drag-3 (drag "baxy prueba") had nothing to work
# on. Measured 2026-10-08 (Sticky Notes 6.1.4): the app works without an account: cancelling the sign-in skips its
# onboarding for good (log OnboardingSignInSkipped), and later launches open straight on the notes.
#  - Every running copy is stopped by its exact PID first (the owner made this a test PC; the store is written with
#    the app closed), then scripts/cu_live/notas_prueba.py writes into plum.sqlite: the note "cita con el dentista el
#    jueves" (v3-36 searches "dentista"; v3-34 writes "llamar al dentista el martes", another text), with <texto> also
#    that note OPEN at the centre of the primary screen (t-drag-3: "baxy prueba"). Harness notes have fixed ids;
#    nobody else's note is changed, except that an open EMPTY note (no text, image or ink) is closed (never deleted).
#    With sin=<texto> (v3-34, v3-35) the note an earlier run of that case left, whole text exactly <texto>, is removed
#    instead: Sticky Notes reopens it, and the judge saw the earlier attempt (revision 2026-10-08).
#  - Nothing is written while the store holds an account (SyncState, RemoteId): the harness notes would sync to the
#    owner's account; the state says con_cuenta. Stopping the app is needed to write the store; it is one copy per
#    user, and every note it had open is kept in the store and reopens with it.
#  - Opened like app_abierta (propios.jsonl: app_cerrada closes it). An account prompt that shows anyway is dismissed
#    through UIA (Ahora no / Not now / Omitir / Cancelar, never sign in); an account window is closed only when the
#    batch ledger proves a case of this batch started its process (Test-ProcesoDelLote), and with -SinConfirmar.
#  - Verified through UIA: no Sticky Notes window asks for an account and, with <texto>, that note is on the screen.
# Harness only. ASCII only.
param([string]$Arg='')
if(-not (Get-Command Write-Estado -ErrorAction SilentlyContinue)){ . (Join-Path $PSScriptRoot 'comun.ps1') }
. (Join-Path $PSScriptRoot 'apps_comun.ps1')
. (Join-Path $PSScriptRoot 'decisiones_comun.ps1')
Add-Type -AssemblyName System.Windows.Forms
$E=$(if($Arg){ "notas_sin_cuenta:$Arg" }else{ 'notas_sin_cuenta' })
$quitar=''; $abierta=$Arg
if($Arg -like 'sin=*'){ $quitar=$Arg.Substring(4); $abierta='' }
$proc='Microsoft.Notes'
$nombreApp='Notas r'+[char]0xE1+'pidas'
$dentista='cita con el dentista el jueves'
$db=Join-Path $env:LOCALAPPDATA 'Packages\Microsoft.MicrosoftStickyNotes_8wekyb3d8bbwe\LocalState\plum.sqlite'
if(-not (Test-Path -LiteralPath $db)){ Write-Estado $E 'sin_almacen' @{ verificado=$false; nota='Notas rapidas sin plum.sqlite (nunca se abrio)' }; return }
# Windows of the account sign-in that a case may have left (the Microsoft account picker): their processes.
$cuentaProcs=@('Microsoft.AAD.BrokerPlugin','WWAHost','CredentialUIBroker')

function Get-VentanasNotas(){
  # Its note windows live in ApplicationFrameHost frames (Get-TopWindows names the app inside), plus account windows.
  @((Get-TopWindows) | Where-Object { (@($proc)+$cuentaProcs) -contains $_.app_proceso -or $cuentaProcs -contains $_.proceso } |
    ForEach-Object { [Windows.Automation.AutomationElement]::FromHandle([IntPtr][long]$_.hwnd) })
}
function Get-NombresNotas(){
  $n=@()
  foreach($w in @(Get-VentanasNotas)){
    # A note's own text (its Edit/Document) is never read as a prompt: only the window and its controls' names.
    try{ $n+=[string]$w.Current.Name; $n+=@($w.FindAll('Descendants',[Windows.Automation.Condition]::TrueCondition) | Where-Object { @('ControlType.Edit','ControlType.Document') -notcontains $_.Current.ControlType.ProgrammaticName } | ForEach-Object { [string]$_.Current.Name }) }catch{}
  }
  $n
}

# 1. Every copy stops (its exact PID), so the store can be written.
$fg=Get-Foreground
$cerradas=@(Close-AppsPropias $nombreApp)
foreach($p in @(Get-Process -Name $proc -ErrorAction SilentlyContinue)){
  try{ Stop-Process -Id $p.Id -Force -ErrorAction Stop; [void]$p.WaitForExit(5000); $cerradas+="$($proc):$($p.Id):detenida" }catch{ $cerradas+="$($proc):$($p.Id):no_cierra" }
}
foreach($p in @(Get-Process -Name $cuentaProcs -ErrorAction SilentlyContinue)){
  if(-not (Test-ProcesoDelLote ([int]$p.Id))){ continue }
  foreach($w in @((Get-TopWindows) | Where-Object { $_.app_pid -eq $p.Id -or $_.pid -eq $p.Id })){
    if(Get-DecisionPideCuenta @($w.titulo)){ try{ Close-WindowExact ([Windows.Automation.AutomationElement]::FromHandle([IntPtr][long]$w.hwnd)) -SinConfirmar; $cerradas+="cuenta:$($p.Id):cerrada" }catch{} }
  }
}
if(@(Get-Process -Name $proc -ErrorAction SilentlyContinue).Count){ Write-Estado $E 'no_cierra' @{ verificado=$false; cerradas=$cerradas }; return }

# 2. The harness's notes in the store.
$ancho=[Windows.Forms.Screen]::PrimaryScreen.Bounds.Width; $alto=[Windows.Forms.Screen]::PrimaryScreen.Bounds.Height
$py=Join-Path (Split-Path $PSScriptRoot) 'notas_prueba.py'
$pyArgs=@('-3.12','-I',$py,'--db',$db,'--texto',$dentista,'--pantalla',"$($ancho)x$($alto)",'--cerrar-demas','--cerrar-vacias')
if($abierta){ $pyArgs+=@('--abierta',$abierta) }
if($quitar){ $pyArgs+=@('--quitar',$quitar) }
$out=@(& py @pyArgs 2>$null | Where-Object { $_ -match '^\{' })
$notas=$(if($out.Count){ $out[-1] | ConvertFrom-Json }else{ $null })
if($notas -and $notas.resultado -eq 'con_cuenta'){ Write-Estado $E 'con_cuenta' @{ verificado=$false; cerradas=$cerradas; nota='Notas rapidas tiene cuenta: no se escribe nada' }; return }
if(-not $notas -or -not $notas.verificado){ Write-Estado $E 'notas_no_escritas' @{ verificado=$false; cerradas=$cerradas; salida=[string]$out }; return }

# 3. Opened like app_abierta, then any account prompt is dismissed without signing in.
$abre=@(& (Join-Path $PSScriptRoot 'app_abierta.ps1') -Arg $nombreApp | Where-Object { "$_" -match '^\{"estado"' } | ForEach-Object { "$_" | ConvertFrom-Json })
if($abre.Count -eq 0 -or -not $abre[-1].verificado){ Write-Estado $E 'no_abre' @{ verificado=$false; cerradas=$cerradas; app_abierta=$(if($abre.Count){ [string]$abre[-1].resultado }else{ 'sin_informe' }) }; return }
$descartados=@()
$fin=(Get-Date).AddSeconds(6)
do{
  Start-Sleep -Milliseconds 700
  $nombres=@(Get-NombresNotas)
  if(Get-DecisionPideCuenta $nombres){
    $btn=Get-DecisionBotonSinCuenta $nombres
    if($btn){
      foreach($w in @(Get-VentanasNotas)){
        try{ $b=Find-ByName $w $btn; if($b -and $b.Current.ControlType.ProgrammaticName -eq 'ControlType.Button'){ [void](Invoke-Element $b); $descartados+=$btn; break } }catch{}
      }
    }
  }
}while((Get-Date) -lt $fin -and ((Get-DecisionPideCuenta $nombres) -or -not (Get-DecisionNotaVisible $nombres $abierta)))
$pide=Get-DecisionPideCuenta $nombres
$visible=Get-DecisionNotaVisible $nombres $abierta
$foco=Restore-Foreground $fg @($proc,'ApplicationFrameHost')
$ok=(-not $pide -and $visible)
Write-Estado $E ($(if($ok){'corregido'}elseif($pide){'pide_cuenta'}else{'no_verificado'})) @{ verificado=$ok; cerradas=$cerradas; notas=@($notas.hechos)
  descartados=$descartados; nota_visible=$visible; foco=$foco }
