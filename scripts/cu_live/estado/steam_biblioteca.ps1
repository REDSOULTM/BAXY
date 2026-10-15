# State steam_biblioteca: Steam already showing the Library (s12/c17 "ya estaba en la biblioteca").
# Steam is never started; without it the line says steam_no_abierto. See steam_comun.ps1 for why the protocol is used.
if(-not ('EstadoW32' -as [type])){ . (Join-Path $PSScriptRoot 'comun.ps1') }
. (Join-Path $PSScriptRoot 'steam_comun.ps1')
$E='steam_biblioteca'
$t=Get-SteamOrReport $E; if($t -isnot [IntPtr]){ $t; return }
$antes=(Read-SteamPage $t).pagina
if($antes -eq 'biblioteca'){ Write-Estado $E 'ok' @{ verificado=$true; pagina_antes=$antes; pagina='biblioteca' }; return }
$n=Invoke-SteamNav $t 'steam://open/games' 'biblioteca' $null
$ok=($n.page.pagina -eq 'biblioteca')
Write-Estado $E ($(if($ok){'corregido'}else{'no_verificado'})) @{ verificado=$ok; pagina_antes=$antes; pagina=$n.page.pagina; via='steam://open/games'; foco=$n.foco; minimizado=$n.minimizado }
