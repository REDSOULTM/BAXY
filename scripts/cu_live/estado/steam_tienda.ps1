# State steam_tienda: Steam showing the Store (the counter-case of s12/c17: a click that changes nothing must not pass).
# Steam is never started; without it the line says steam_no_abierto. See steam_comun.ps1 for why the protocol is used.
if(-not ('EstadoW32' -as [type])){ . (Join-Path $PSScriptRoot 'comun.ps1') }
. (Join-Path $PSScriptRoot 'steam_comun.ps1')
$E='steam_tienda'
$t=Get-SteamOrReport $E; if($t -isnot [IntPtr]){ $t; return }
$antes=(Read-SteamPage $t).pagina
if($antes -eq 'tienda'){ Write-Estado $E 'ok' @{ verificado=$true; pagina_antes=$antes; pagina='tienda' }; return }
$n=Invoke-SteamNav $t 'steam://store' 'tienda' $null
$ok=($n.page.pagina -eq 'tienda')
Write-Estado $E ($(if($ok){'corregido'}else{'no_verificado'})) @{ verificado=$ok; pagina_antes=$antes; pagina=$n.page.pagina; via='steam://store'; foco=$n.foco; minimizado=$n.minimizado }
