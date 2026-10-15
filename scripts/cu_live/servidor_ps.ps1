# One persistent PowerShell for the harness utilities of a batch (batch.sh, function ps): each helper script (libro_lote,
# marcos, base.ps1 and its states, verificar, apps_del_caso, exploradores, screen...) runs here with & instead of in a
# new powershell.exe, which cost 1-1.5 s of start and type compilation per call, ~20 calls a case. Harness only.
# Protocol on stdin, one line each (UTF-8): '@@baxy-llamada@@', the script's Windows path, its arguments one per
# line, '@@baxy-args-fin@@'. The output of the call (errors included, as with 2>&1) goes to stdout one line each,
# then '@@baxy-fin@@ <code>'. Every call runs in its own script scope: the helpers dot-source comun.ps1 again (its
# Add-Type blocks are guarded, the types are compiled once). The process ends when stdin closes (batch.sh exits).
# -Padre: the Windows pid of the bash that started it; the server also ends when that process is gone (a program a
# case left open may hold a copy of the pipe, so the end of stdin alone could come late or never).
# ASCII only (PowerShell 5.1 reads it as ANSI).
param([int]$Padre=0)
$utf8=New-Object Text.UTF8Encoding $false
[Console]::OutputEncoding=$utf8
$ErrorActionPreference='Continue'
$entrada=New-Object IO.StreamReader([Console]::OpenStandardInput(),$utf8)
function Read-Linea(){
  # The next line of stdin, or $null at its end or once the parent is gone.
  $t=$entrada.ReadLineAsync()
  while(-not $t.Wait(2000)){
    if($Padre -gt 0 -and -not (Get-Process -Id $Padre -ErrorAction SilentlyContinue)){ return $null }
  }
  $t.Result
}

function Get-ArgumentosLlamada([string]$Script,[string[]]$Partes){
  # -Name value / -Switch, told apart by the script's own parameters (a switch never takes the next line).
  $cmd=$ExecutionContext.InvokeCommand.GetCommand($Script,'ExternalScript')
  if(-not $cmd){ throw "no existe el script $Script" }
  $meta=$cmd.Parameters
  $h=@{}; $pos=New-Object Collections.ArrayList
  for($i=0;$i -lt $Partes.Count;$i++){
    $a=$Partes[$i]
    if($a -match '^-([A-Za-z][A-Za-z0-9_]*)$' -and $meta.ContainsKey($matches[1])){
      $n=$matches[1]
      if($meta[$n].SwitchParameter){ $h[$n]=$true }
      elseif($i+1 -lt $Partes.Count){ $i++; $h[$n]=$Partes[$i] }
      else{ $h[$n]='' }
    }else{ [void]$pos.Add($a) }
  }
  @{ con_nombre=$h; posicionales=@($pos) }
}

while($true){
  $l=Read-Linea
  if($null -eq $l){ break }
  if($l -ne '@@baxy-llamada@@'){ continue }
  $partes=New-Object Collections.ArrayList
  while($true){ $x=Read-Linea; if($null -eq $x -or $x -eq '@@baxy-args-fin@@'){ break }; [void]$partes.Add($x) }
  if($partes.Count -eq 0){ [Console]::Out.WriteLine('@@baxy-fin@@ 2'); continue }
  $script=[string]$partes[0]; $codigo=0
  try{
    $a=Get-ArgumentosLlamada $script @($partes | Select-Object -Skip 1)
    $h=$a.con_nombre; $p=$a.posicionales
    $global:LASTEXITCODE=0
    & $script @h @p 2>&1 | Out-String -Stream -Width 32766 | ForEach-Object { [Console]::Out.WriteLine($_) }
    if($LASTEXITCODE){ $codigo=$LASTEXITCODE }
  }catch{
    [Console]::Out.WriteLine("servidor_ps: $($_.Exception.Message)"); $codigo=1
  }
  # A helper may have changed the console encoding (comun.ps1 sets UTF-8 with BOM): no BOM for the next call.
  [Console]::OutputEncoding=$utf8
  [Console]::Out.WriteLine("@@baxy-fin@@ $codigo")
}
