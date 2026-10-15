# State valor_registro:<HKCU key>|<value name>|<text>: read only. Says whether that value of the person's registry
# (HKCU only) contains the text, case-insensitive. Used as the check of a case that needs what an earlier case left
# (casos.json "requiere": 7-Zip remembers the last folder in HKCU\Software\7-Zip\FM PanelPath0). Never writes, and
# never prints the value (only whether it contains the text). Harness only. ASCII only.
param([string]$Arg='')
if(-not ('EstadoW32' -as [type])){ . (Join-Path $PSScriptRoot 'comun.ps1') }
$E="valor_registro:$Arg"
$clave,$nombre,$texto=$Arg -split '\|',3
if(-not $clave -or -not $nombre -or -not $texto -or $clave -notmatch '^HKCU\\'){ Write-Estado $E 'sin_argumento' @{ verificado=$false; nota='HKCU\ruta|nombre|texto' }; return }
$v=$null
try{ $v=(Get-ItemProperty -LiteralPath ('Registry::HKEY_CURRENT_USER\'+$clave.Substring(5)) -Name $nombre -ErrorAction Stop).$nombre }catch{}
if($null -eq $v){ Write-Estado $E 'ausente' @{ verificado=$false; existe=$false }; return }
$si=([string]$v).IndexOf($texto,[StringComparison]::OrdinalIgnoreCase) -ge 0
Write-Estado $E ($(if($si){'ok'}else{'ausente'})) @{ verificado=$si; existe=$true; cumple_orden=$si }
