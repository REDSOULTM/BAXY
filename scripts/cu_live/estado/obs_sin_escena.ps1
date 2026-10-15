# State obs_sin_escena:<name>: the OBS scene collection in use has no scene of that EXACT name (v3-51 creates
# "Pruebas"; in pasada r9 it was still there from r5, so the case could not tell anything). Test data a case made, not
# an owner preference: it is removed, never given back.
#  - Only with OBS closed (OBS rewrites the collection when it exits). A copy the harness opened, or one the batch
#    started (the ledger proves it), is closed first; the person's OBS is never closed: obs_abierto, nothing written.
#  - Only an EMPTY scene of exactly that name that no other scene or group uses (scripts/cu_live/obs_escena.py); the
#    file is copied byte for byte to %LOCALAPPDATA%\BAXY\cu-estado\obs first, and read back after.
# Harness only. ASCII only.
param([string]$Arg='')
if(-not ('EstadoW32' -as [type])){ . (Join-Path $PSScriptRoot 'comun.ps1') }
. (Join-Path $PSScriptRoot 'apps_comun.ps1')
$E="obs_sin_escena:$Arg"
if([string]::IsNullOrWhiteSpace($Arg)){ Write-Estado $E 'sin_argumento' @{ verificado=$false; nota='obs_sin_escena:<nombre exacto de la escena>' }; return }
$dir=Join-Path $env:APPDATA 'obs-studio\basic\scenes'

function Get-ColeccionObs(){
  # The collection OBS uses: SceneCollectionFile of user.ini / global.ini (with or without its .json), else the newest.
  $nombre=$null
  foreach($ini in @('user.ini','global.ini')){
    $p=Join-Path (Join-Path $env:APPDATA 'obs-studio') $ini
    if(-not $nombre -and (Test-Path -LiteralPath $p)){ $m=Select-String -LiteralPath $p -Pattern '^SceneCollectionFile=(.+)$' -Encoding UTF8 | Select-Object -First 1; if($m){ $nombre=$m.Matches[0].Groups[1].Value.Trim() } }
  }
  if($nombre){
    foreach($n in @($nombre,($nombre+'.json'))){ $f=Join-Path $dir $n; if($n -like '*.json' -and (Test-Path -LiteralPath $f)){ return $f } }
  }
  $n=@(Get-ChildItem -LiteralPath $dir -Filter *.json -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending)
  if($n.Count){ $n[0].FullName }else{ $null }
}

$f=Get-ColeccionObs
if(-not $f){ Write-Estado $E 'sin_obs' @{ verificado=$false; nota='no hay coleccion de escenas de OBS' }; return }
$cerradas=@()
if(@(Get-Process obs64,obs32 -ErrorAction SilentlyContinue).Count){
  $cerradas=@(Close-AppsPropias 'OBS Studio')+@(Close-ProcesosDelLote 'obs64')
  $fin=(Get-Date).AddSeconds(10)
  while((Get-Date) -lt $fin -and @(Get-Process obs64,obs32 -ErrorAction SilentlyContinue).Count){ Start-Sleep -Milliseconds 300 }
}
if(@(Get-Process obs64,obs32 -ErrorAction SilentlyContinue).Count){ Write-Estado $E 'obs_abierto' @{ verificado=$false; cerradas_antes=$cerradas; nota='OBS abierto que el arnes no abrio: no se toca (reescribe el archivo al salir)' }; return }
$py=Join-Path (Split-Path $PSScriptRoot) 'obs_escena.py'
$resp=Join-Path $env:LOCALAPPDATA 'BAXY\cu-estado\obs'
$hashAntes=(Get-FileHash -LiteralPath $f).Hash
$out=@(& py -3.12 -I $py --archivo $f --nombre $Arg --respaldo $resp 2>$null | Where-Object { $_ -match '^\{' })
if($out.Count -eq 0){ Write-Estado $E 'error' @{ verificado=$false; cerradas_antes=$cerradas; nota='obs_escena.py no respondio' }; return }
$r=$out[-1] | ConvertFrom-Json
if($r.resultado -eq 'quitada'){
  # v3-53 inverts an owner preference in this same file first (obs_audio_escritorio, preferencias_comun.ps1): its
  # pending copy keeps the owner's original, and the hash of the harness's inversion now includes this removal, so a
  # later devolver_pendiente still tells the harness's file from one the owner changed.
  . (Join-Path $PSScriptRoot 'preferencias_comun.ps1')
  $hashDespues=(Get-FileHash -LiteralPath $f).Hash
  $pend=@(Get-PreferenciasPendientes)
  if(@($pend | Where-Object { $_.archivo -eq $f -and $_.invertido -eq $hashAntes }).Count){
    Set-PreferenciasPendientes @(foreach($i in $pend){ if($i.archivo -eq $f -and $i.invertido -eq $hashAntes){ $i.invertido=$hashDespues }; $i })
  }
}
switch($r.resultado){
  'no_estaba' { Write-Estado $E 'ok' @{ verificado=$true; cerradas_antes=$cerradas } }
  'quitada' { $ok=($r.releido -eq 'no_estaba'); Write-Estado $E ($(if($ok){'corregido'}else{'no_verificado'})) @{ verificado=$ok; respaldo=[string]$r.respaldo; cerradas_antes=$cerradas } }
  default { Write-Estado $E ([string]$r.resultado) @{ verificado=$false; cerradas_antes=$cerradas; nota='la escena no se quita: puede ser del dueno' } }
}
