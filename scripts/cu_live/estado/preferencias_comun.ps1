# Owner preferences a state inverts for a case (casos.json "precondicion"): the file is copied byte for byte before
# the change and put back after the case. Dot-source after comun.ps1. Harness only. ASCII only.
#   pendientes.jsonl  one line per copy not yet given back: {estado, archivo, respaldo, desde, invertido}
#                     invertido = SHA-256 of the file right after the harness inverted it ('' until then)
$global:PrefDir=Join-Path $env:LOCALAPPDATA 'BAXY\cu-estado\preferencias'
$global:PrefPendientes=Join-Path $global:PrefDir 'pendientes.jsonl'

function Get-PreferenciasPendientes(){
  if(-not (Test-Path -LiteralPath $global:PrefPendientes)){ return }
  foreach($l in [IO.File]::ReadAllLines($global:PrefPendientes)){ if($l.Trim()){ try{ $l | ConvertFrom-Json }catch{} } }
}

function Set-PreferenciasPendientes($Items){
  $lines=@(foreach($i in @($Items)){ if($i){ ([pscustomobject]@{ estado=[string]$i.estado; archivo=[string]$i.archivo; respaldo=[string]$i.respaldo; desde=[string]$i.desde; invertido=[string]$i.invertido } | ConvertTo-Json -Compress) } })
  [IO.File]::WriteAllText($global:PrefPendientes,$(if($lines.Count){ ($lines -join "`n")+"`n" }else{ '' }),(New-Object Text.UTF8Encoding $false))
}

function Get-DecisionRespaldoPendiente([string]$Actual,[string]$Invertido,[string]$Respaldo){
  # A copy still pending from an earlier run is the owner's original, and is reused only while the file is exactly
  # what the harness left: its inversion ($Invertido), or, when the inversion never happened, the copy itself. Any
  # other content means the owner changed the file since: giving the old copy back would undo their changes.
  # Returns 'reutilizar' | 'respaldo_pendiente_obsoleto'.
  if($Invertido -and $Actual -eq $Invertido){ return 'reutilizar' }
  if(-not $Invertido -and $Actual -eq $Respaldo){ return 'reutilizar' }
  'respaldo_pendiente_obsoleto'
}

function Save-PreferenciaRespaldo([string]$Estado,[string]$Archivo){
  # Copies the file once per state. Returns @{ resultado = 'nuevo' | 'reutilizado' | 'respaldo_pendiente_obsoleto' |
  # 'sin_respaldo'; respaldo }. Only 'nuevo' and 'reutilizado' let the state invert the preference.
  if(-not (Test-Path $global:PrefDir)){ New-Item -ItemType Directory -Force $global:PrefDir | Out-Null }
  $prev=@(Get-PreferenciasPendientes | Where-Object { $_.estado -eq $Estado -and $_.archivo -eq $Archivo })
  if($prev.Count){
    $hr=$(if(Test-Path -LiteralPath $prev[0].respaldo){ (Get-FileHash -LiteralPath $prev[0].respaldo).Hash }else{ '' })
    $d=Get-DecisionRespaldoPendiente (Get-FileHash -LiteralPath $Archivo).Hash ([string]$prev[0].invertido) $hr
    if($d -eq 'reutilizar' -and $hr){ return @{ resultado='reutilizado'; respaldo=$prev[0].respaldo } }
    return @{ resultado='respaldo_pendiente_obsoleto'; respaldo=$prev[0].respaldo }
  }
  $dst=Join-Path $global:PrefDir ('{0}-{1}.bin' -f ($Estado -replace '[^A-Za-z0-9_]','_'),(Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
  Copy-Item -LiteralPath $Archivo -Destination $dst
  if((Get-FileHash -LiteralPath $dst).Hash -ne (Get-FileHash -LiteralPath $Archivo).Hash){ return @{ resultado='sin_respaldo'; respaldo=$null } }
  Set-PreferenciasPendientes (@(Get-PreferenciasPendientes)+[pscustomobject]@{ estado=$Estado; archivo=$Archivo; respaldo=$dst; desde=(Get-Date).ToString('s'); invertido='' })
  @{ resultado='nuevo'; respaldo=$dst }
}

function Set-PreferenciaInvertida([string]$Estado,[string]$Archivo){
  # Records the hash of the file right after the inversion, so a later run can tell the harness's inversion from a
  # change of the owner (Get-DecisionRespaldoPendiente).
  $h=(Get-FileHash -LiteralPath $Archivo).Hash
  Set-PreferenciasPendientes @(foreach($i in @(Get-PreferenciasPendientes)){ if($i.estado -eq $Estado -and $i.archivo -eq $Archivo){ $i.invertido=$h }; $i })
}

function Restore-PreferenciaRespaldo([string]$Estado,[switch]$SoloSiInvertido){
  # Puts back every pending copy of that state byte for byte; returns @{ resultado; verificado; archivos }.
  # -SoloSiInvertido (a retry in a later run): only while the file is still exactly the harness's inversion; a file
  # the owner changed since stays as it is (respaldo_pendiente_obsoleto) and the copy stays pending for a human.
  $todos=@(Get-PreferenciasPendientes); $quedan=@(); $hechos=@(); $ok=$true; $obsoleto=$false
  foreach($i in $todos){
    if($i.estado -ne $Estado){ $quedan+=$i; continue }
    if($SoloSiInvertido -and (-not $i.invertido -or (Get-FileHash -LiteralPath $i.archivo).Hash -ne [string]$i.invertido)){ $ok=$false; $obsoleto=$true; $quedan+=$i; continue }
    try{
      Copy-Item -LiteralPath $i.respaldo -Destination $i.archivo -Force
      if((Get-FileHash -LiteralPath $i.respaldo).Hash -eq (Get-FileHash -LiteralPath $i.archivo).Hash){ $hechos+=[IO.Path]::GetFileName($i.archivo) }else{ $ok=$false; $quedan+=$i }
    }catch{ $ok=$false; $quedan+=$i }
  }
  Set-PreferenciasPendientes $quedan
  @{ resultado=$(if($obsoleto){'respaldo_pendiente_obsoleto'}elseif(-not $ok){'no_verificado'}elseif($hechos.Count){'corregido'}else{'ok'}); verificado=$ok; archivos=$hechos }
}
