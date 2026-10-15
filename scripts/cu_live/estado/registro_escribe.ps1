# State registro_escribe:<HKCU key>|<value name>|<value>: writes that value of the current user's registry, then
# reads it back. For an app that remembers its last place or view there (casos.json, v3-49: 7-Zip opens in the folder
# of HKCU\Software\7-Zip\FM PanelPath0, with the view of ListMode and the sort column of Columns\FSFolder). Pasada r9:
# v3-49 leaned on v3-48 leaving that folder, v3-48 failed, and v3-49 never ran; the harness now writes it itself (the
# owner made this PC a test PC).
#  - <value> 'dword:<n>' writes a REG_DWORD; 'bin32@<offset>:<n>' replaces only the 32-bit word at that byte offset of
#    an existing REG_BINARY (the rest of it, column widths and so on, stays); anything else a REG_SZ. '{Documentos}'
#    expands to the Documents folder.
#  - Only under HKCU\Software, and only a value whose key already exists (the app made it: nothing new is invented); a
#    bin32 value must exist too, long enough.
#  - The app must be closed (it rewrites these values when it exits): casos.json puts app_cerrada before this state.
# Harness only. ASCII only.
param([string]$Arg='')
if(-not (Get-Command Write-Estado -ErrorAction SilentlyContinue)){ . (Join-Path $PSScriptRoot 'comun.ps1') }
. (Join-Path $PSScriptRoot 'decisiones_comun.ps1')
$E="registro_escribe:$Arg"
$d=Get-DecisionRegistroEscribe $Arg ([Environment]::GetFolderPath('MyDocuments'))
if(-not $d.ok){ Write-Estado $E 'sin_argumento' @{ verificado=$false; nota=$d.nota }; return }
$ruta='Registry::HKEY_CURRENT_USER\'+$d.clave
if(-not (Test-Path -LiteralPath $ruta)){ Write-Estado $E 'sin_clave' @{ verificado=$false; nota='la clave no existe: la app nunca la creo' }; return }
$antes=$null
try{ $antes=(Get-ItemProperty -LiteralPath $ruta -Name $d.nombre -ErrorAction Stop).($d.nombre) }catch{}
function Test-Escrito($Valor){
  if($d.tipo -eq 'Bin32'){ return ($Valor -is [byte[]] -and $Valor.Length -ge $d.offset+4 -and [BitConverter]::ToUInt32($Valor,$d.offset) -eq $d.valor) }
  ($null -ne $Valor -and "$Valor" -ceq "$($d.valor)")
}
if(Test-Escrito $antes){ Write-Estado $E 'ok' @{ verificado=$true }; return }
try{
  if($d.tipo -eq 'Bin32'){
    $b=Get-DecisionBinarioParcheado $antes $d.offset $d.valor
    if($null -eq $b){ Write-Estado $E 'sin_valor' @{ verificado=$false; nota='el valor binario no existe o es corto: la app nunca lo escribio' }; return }
    Set-ItemProperty -LiteralPath $ruta -Name $d.nombre -Value $b -Type Binary -ErrorAction Stop
  }
  elseif($null -ne $antes){ Set-ItemProperty -LiteralPath $ruta -Name $d.nombre -Value $d.valor -Type $d.tipo -ErrorAction Stop }
  else{ New-ItemProperty -LiteralPath $ruta -Name $d.nombre -Value $d.valor -PropertyType $d.tipo -ErrorAction Stop | Out-Null }
}catch{ Write-Estado $E 'error' @{ verificado=$false; error=$_.Exception.Message }; return }
$despues=$null
try{ $despues=(Get-ItemProperty -LiteralPath $ruta -Name $d.nombre -ErrorAction Stop).($d.nombre) }catch{}
$ok=(Test-Escrito $despues)
Write-Estado $E ($(if($ok){'corregido'}else{'no_verificado'})) @{ verificado=$ok }
