# State obs_audio_escritorio:<leer|sin_silenciar|devolver>: the owner's OBS preference "desktop audio muted", which
# already fulfils the order of v3-53 ("silencia el audio del escritorio"). Owner preference: inverted only because it
# is reversible, and given back after the case (casos.json "precondicion").
#  - leer: says whether the desktop audio sources of the scene collection in use are muted (read only).
#  - sin_silenciar: with OBS closed (it rewrites the file when it exits), copies the collection file byte for byte to
#    %LOCALAPPDATA%\BAXY\cu-estado\preferencias\ and records it in pendientes.jsonl, then unmutes the desktop audio
#    sources (wasapi_output_capture) and reads the file back.
#  - devolver: with OBS closed, puts the recorded copy back byte for byte and drops it from pendientes.jsonl.
#  - devolver_pendiente: the same in a later run (base.ps1 -DevolverPendientes), only while the file is still the
#    harness's inversion: a collection the owner changed since is never overwritten with the old copy.
# OBS open: nothing is written (obs_abierto, verificado=false). Harness only. ASCII only.
param([string]$Arg='')
if(-not ('EstadoW32' -as [type])){ . (Join-Path $PSScriptRoot 'comun.ps1') }
. (Join-Path $PSScriptRoot 'preferencias_comun.ps1')
$E="obs_audio_escritorio:$Arg"
$dir=Join-Path $env:APPDATA 'obs-studio\basic\scenes'

function Get-Coleccion(){
  # The collection OBS uses: SceneCollectionFile of user.ini / global.ini, else the newest collection file.
  $nombre=$null
  foreach($ini in @('user.ini','global.ini')){
    $p=Join-Path (Join-Path $env:APPDATA 'obs-studio') $ini
    if(-not $nombre -and (Test-Path -LiteralPath $p)){ $m=Select-String -LiteralPath $p -Pattern '^SceneCollectionFile=(.+)$' -Encoding UTF8 | Select-Object -First 1; if($m){ $nombre=$m.Matches[0].Groups[1].Value.Trim() } }
  }
  if($nombre){ $f=Join-Path $dir ($nombre+'.json'); if(Test-Path -LiteralPath $f){ return $f } }
  $n=@(Get-ChildItem -LiteralPath $dir -Filter *.json -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending)
  if($n.Count){ $n[0].FullName }else{ $null }
}

function Get-Silencio($Doc){
  # Muted flag of each desktop audio source (top-level DesktopAudioDevice* entries).
  @(foreach($p in $Doc.PSObject.Properties){ if($p.Name -like 'DesktopAudioDevice*' -and $p.Value -and $p.Value.id -eq 'wasapi_output_capture'){ [bool]$p.Value.muted } })
}

$f=Get-Coleccion
if(-not $f){ Write-Estado $E 'sin_obs' @{ verificado=$false; nota='no hay coleccion de escenas de OBS' }; return }
$leer={ $d=[IO.File]::ReadAllText($f,[Text.Encoding]::UTF8) | ConvertFrom-Json; @(Get-Silencio $d) }
$antes=& $leer
$silenciado=($antes.Count -gt 0 -and @($antes | Where-Object { -not $_ }).Count -eq 0)
switch($Arg){
  'leer' { Write-Estado $E ($(if($silenciado){'silenciado'}else{'sin_silenciar'})) @{ verificado=$true; cumple_orden=$silenciado; fuentes=$antes.Count }; return }
  'sin_silenciar' {
    if(-not $silenciado){ Write-Estado $E 'ok' @{ verificado=$true; fuentes=$antes.Count }; return }
    if(@(Get-Process obs64,obs32 -ErrorAction SilentlyContinue).Count){ Write-Estado $E 'obs_abierto' @{ verificado=$false; nota='OBS reescribe el archivo al salir: no se toca abierto' }; return }
    $r=Save-PreferenciaRespaldo $E $f
    if($r.resultado -ne 'nuevo' -and $r.resultado -ne 'reutilizado'){ Write-Estado $E $r.resultado @{ verificado=$false; respaldo=$r.respaldo; nota='no se invierte: una copia pendiente ya no corresponde al archivo actual' }; return }
    $d=[IO.File]::ReadAllText($f,[Text.Encoding]::UTF8) | ConvertFrom-Json
    foreach($p in $d.PSObject.Properties){ if($p.Name -like 'DesktopAudioDevice*' -and $p.Value -and $p.Value.id -eq 'wasapi_output_capture'){ $p.Value.muted=$false } }
    [IO.File]::WriteAllText($f,($d | ConvertTo-Json -Depth 100 -Compress),(New-Object Text.UTF8Encoding $false))
    Set-PreferenciaInvertida $E $f
    $despues=& $leer
    $ok=(@($despues | Where-Object { $_ }).Count -eq 0)
    Write-Estado $E ($(if($ok){'corregido'}else{'no_verificado'})) @{ verificado=$ok; respaldo=$r.respaldo; copia=$r.resultado; fuentes=$despues.Count }
    return
  }
  {$_ -eq 'devolver' -or $_ -eq 'devolver_pendiente'} {
    if(@(Get-Process obs64,obs32 -ErrorAction SilentlyContinue).Count){ Write-Estado $E 'obs_abierto' @{ verificado=$false; nota='se devuelve con OBS cerrado' }; return }
    $r=Restore-PreferenciaRespaldo 'obs_audio_escritorio:sin_silenciar' -SoloSiInvertido:($Arg -eq 'devolver_pendiente')
    Write-Estado $E $r.resultado @{ verificado=$r.verificado; archivos=$r.archivos }
    return
  }
}
Write-Estado $E 'sin_argumento' @{ verificado=$false; nota='leer, sin_silenciar, devolver o devolver_pendiente' }
