# Puts the test apps in their base state before a live case (goal v3, point 7). Harness only, never product code.
# usage:
#   base.ps1 -Estados calc_estandar,config_busqueda_vacia     the listed states, in that order
#   base.ps1 -Caso s12                                         the states casos.json lists for that case
#   base.ps1 -Caso v3-53 -Devolver                             gives back the owner preference the case inverted
#   base.ps1 -DevolverPendientes                               retries every owner preference still pending (a
#                                                              -Devolver that failed earlier, OBS was open)
#   base.ps1 -Lista                                            the known states
# A state may take one argument after a colon, "estado:argumento" (app_abierta:Mapa de caracteres,
# documento_en_blanco:PowerPoint|Uno;Dos;Tres): the script gets it as -Arg. In -Estados, states are separated by
# commas (and, for states without an argument, also by spaces).
# Every state prints one JSON line {"estado","resultado","verificado",...} after reading the state back; a case that
# casos.json does not list prints {"caso":..,"estados":[]} and touches nothing. Exit code 0 always: the batch keeps
# going and the lines say what could not be verified (resultado other than ok/corregido, or verificado=false).
# With -Caso, two more sections of casos.json:
#   "requiere" {caso: {tras, comprueba}}: the case needs what an earlier case leaves (a OneNote section, a 7-Zip last
#     folder). "tras" must have run in this batch (its marker logs/v2-<tras>.hecho, written by batch.sh only after
#     its mission ran, is newer than the batch ledger CU_LIBRO, its conductor exited 0 and no judge marked it
#     "veredicto":"fallo") and the optional "comprueba" state must verify. Otherwise the case line says
#     resultado "no_corrio:estado_ausente" (batch.sh does not run it; it does not count against BAXY) and no state
#     is applied. The line always names "depende_de", so a judge knows the case leans on another one; with no
#     verdict and no "comprueba" it also says productor_sin_verificar (the judge leaves it out if "tras" failed).
#   "precondicion" {caso: {lee, invierte, devuelve, variante}}: an owner preference that may already fulfil the
#     order. "lee" says it (cumple_orden). When it does and the case has a reversible "invierte", that state runs
#     first and "devuelve" runs after the case (-Devolver); when it cannot be inverted the case line says
#     variante "ya_estaba" (success is saying so without changing anything). Without "lee" the line says
#     precondicion "no_legible" and the variant to judge by if it held.
param([string]$Estados='',[string]$Caso='',[switch]$Lista,[string]$Mapa='',[switch]$Devolver,[switch]$DevolverPendientes)
$ErrorActionPreference='Stop'
$dir=$PSScriptRoot
if(-not $Mapa){ $Mapa=Join-Path $dir 'casos.json' }
. (Join-Path $dir 'comun.ps1')
. (Join-Path $dir 'decisiones_comun.ps1')

$conocidos=@(Get-ChildItem -LiteralPath $dir -Filter *.ps1 | Where-Object { $_.BaseName -notmatch '^(base|comun|.*_comun|exploradores|apps_del_caso)$' } | ForEach-Object { $_.BaseName } | Sort-Object)
if($Lista){ $conocidos; return }

function Invoke-Estado([string]$e){
  # Runs one state and prints its JSON line(s) with the time it took.
  $nombre,$arg=$e -split ':',2
  if($nombre -notmatch '^[a-z0-9_]+$' -or $conocidos -notcontains $nombre){ Write-Estado $e 'desconocido' @{ verificado=$false }; return }
  $t0=Get-Date
  try{
    $script=Join-Path $dir "$nombre.ps1"
    $lines=@($(if($null -ne $arg){ & $script -Arg $arg 2>&1 }else{ & $script 2>&1 }) | ForEach-Object { "$_" })
    $json=@($lines | Where-Object { $_ -match '^\{"estado"' })
    if($json.Count -eq 0){ Write-Estado $e 'sin_informe' @{ verificado=$false; salida=($lines -join ' | ') } }
    foreach($j in $json){ $j.Substring(0,$j.Length-1)+(',"ms":{0}}}' -f [int]((Get-Date)-$t0).TotalMilliseconds) }
  }catch{
    Write-Estado $e 'error' @{ verificado=$false; error=$_.Exception.Message }
  }
}

function Get-Seccion($M,[string]$Nombre,[string]$Clave){
  if($M.PSObject.Properties[$Nombre] -and $M.$Nombre.PSObject.Properties[$Clave]){ return $M.$Nombre.$Clave }
  $null
}

function Get-EstadoProductor([string]$Tras){
  # Get-DecisionProductor (decisiones_comun.ps1) on the producer's marker logs/v2-<tras>.hecho, which batch.sh writes
  # only after that case's mission ran (never its photo: taken before its states, it exists even when it did not run).
  # Without a batch ledger any marker counts as this batch's.
  $logs=if($env:CU_LOGS){ $env:CU_LOGS }else{ Join-Path (Split-Path $dir) 'logs' }
  $f=Join-Path $logs ('v2-{0}.hecho' -f ($Tras -replace '@','-'))
  $h=$null; $nuevo=$false
  if(Test-Path -LiteralPath $f){
    try{ $h=[IO.File]::ReadAllText($f,[Text.Encoding]::UTF8) | ConvertFrom-Json }catch{}
    $nuevo=(-not $env:CU_LIBRO -or -not (Test-Path -LiteralPath $env:CU_LIBRO) -or (Get-Item -LiteralPath $f).LastWriteTimeUtc -ge (Get-Item -LiteralPath $env:CU_LIBRO).CreationTimeUtc)
  }
  Get-DecisionProductor $h $nuevo
}

if($DevolverPendientes){
  # Every pending copy (preferencias_comun.ps1) is given back by the "devuelve" state of the precondicion that inverts
  # it. A copy whose state no precondicion names is reported, never guessed.
  . (Join-Path $dir 'preferencias_comun.ps1')
  $m=[IO.File]::ReadAllText($Mapa,[Text.Encoding]::UTF8) | ConvertFrom-Json
  $hechos=@()
  foreach($i in @(Get-PreferenciasPendientes)){
    $dev=@(foreach($c in @($m.precondicion.PSObject.Properties)){ if([string]$c.Value.invierte -eq [string]$i.estado -and $c.Value.devuelve){ [string]$c.Value.devuelve } })
    if($dev.Count -eq 0){ Write-Estado ([string]$i.estado) 'pendiente_sin_devuelve' @{ verificado=$false; respaldo=[string]$i.respaldo }; continue }
    if($hechos -contains $dev[0]){ continue }
    # A devuelve state takes '<arg>_pendiente' for a retry: it gives the copy back only while the harness's
    # inversion is intact, never over a file the owner changed since.
    $hechos+=$dev[0]; Invoke-Estado ($dev[0]+'_pendiente')
  }
  return
}

$aplicar=@()
if($Caso){
  $m=[IO.File]::ReadAllText($Mapa,[Text.Encoding]::UTF8) | ConvertFrom-Json
  $pre=Get-Seccion $m 'precondicion' $Caso
  if($Devolver){
    if($pre -and $pre.devuelve){ Invoke-Estado ([string]$pre.devuelve) }
    return
  }
  $p=$m.casos.PSObject.Properties[$Caso]
  if($p){ $aplicar=@($p.Value) }
  # Setup the manifest asks for that no state can give (casos.json "sin_estado"): the reason goes in the case line.
  $o=[ordered]@{ caso=$Caso; estados=$aplicar }
  $sin=Get-Seccion $m 'sin_estado' $Caso; if($sin){ $o['sin_estado']=$sin }
  $req=Get-Seccion $m 'requiere' $Caso
  if($req){
    $o['depende_de']=[string]$req.tras
    $falta=@()
    $prod=$(if($req.tras){ Get-EstadoProductor ([string]$req.tras) }else{ 'exito' })
    if($prod -eq 'no_corrio_antes' -or $prod -eq 'productor_fallo'){ $falta+="$($prod):$($req.tras)" }
    $comprobado=$false
    if($req.comprueba -and $falta.Count -eq 0){
      $l=@(Invoke-Estado ([string]$req.comprueba)); $l
      if(@($l | Where-Object { $_ -match '"verificado":true' }).Count -eq 0){ $falta+=[string]$req.comprueba }else{ $comprobado=$true }
    }
    # The producer ran but nobody judged it and no read-only check proves what it left: the case runs, flagged, and
    # the judge leaves it out if the producer failed (it must not count against BAXY).
    if($falta.Count -eq 0 -and $prod -eq 'sin_veredicto' -and -not $comprobado){ $o['productor_sin_verificar']=$true }
    if($falta.Count){ $o['resultado']='no_corrio:estado_ausente'; $o['verificado']=$false; $o['falta']=$falta; ($o | ConvertTo-Json -Compress); return }
  }
  $antes=@()
  if($pre){
    if($pre.lee){
      $l=@(Invoke-Estado ([string]$pre.lee)); $l
      $cumple=@($l | Where-Object { $_ -match '"cumple_orden":true' }).Count -gt 0
      $o['precondicion']=$(if($cumple){'cumple'}else{'no_cumple'})
      if($cumple -and $pre.invierte){ $antes+=[string]$pre.invierte; $o['precondicion']='se_invierte' }
      elseif($cumple){ $o['variante']=[string]$pre.variante }
    }else{ $o['precondicion']='no_legible'; $o['variante_si_cumple']=[string]$pre.variante }
  }
  ($o | ConvertTo-Json -Compress)
  # An inversion that does not verify leaves the preference as it was: the case is then the "ya estaba" variant.
  foreach($e in $antes){
    $l=@(Invoke-Estado $e); $l
    if(@($l | Where-Object { $_ -match '"verificado":true' }).Count -eq 0){ ([ordered]@{ caso=$Caso; precondicion='no_invertida'; variante=[string]$pre.variante } | ConvertTo-Json -Compress) }
  }
}
if($Estados){
  foreach($x in @($Estados -split ',')){
    $x=$x.Trim(); if(-not $x){ continue }
    if($x -match ':'){ $aplicar+=$x }else{ $aplicar+=@($x -split '\s+' | Where-Object { $_ }) }
  }
}

foreach($e in $aplicar){ Invoke-Estado $e }
