# State steam_busqueda_vacia: the Library's search box is empty (g1 left "Cuphead" typed in it).
# The box has no UIA tree and Steam ignores posted keys, so nothing is typed anywhere: steam://open/games empties it
# (measured 2026-10-07: "Resultados de la búsqueda / Cuphead" -> "Juegos y Software / FAVORITOS"). It leaves Steam on
# the Library; a page state listed after this one (steam_tienda) moves it on.
if(-not ('EstadoW32' -as [type])){ . (Join-Path $PSScriptRoot 'comun.ps1') }
. (Join-Path $PSScriptRoot 'steam_comun.ps1')
$E='steam_busqueda_vacia'
$t=Get-SteamOrReport $E; if($t -isnot [IntPtr]){ $t; return }
$p=Read-SteamPage $t
$antes=Test-SteamSearch $p
if($antes -eq 'vacia'){ Write-Estado $E 'ok' @{ verificado=$true; busqueda_antes=$antes; busqueda='vacia'; pagina=$p.pagina }; return }
$n=Invoke-SteamNav $t 'steam://open/games' 'biblioteca' { param($pg) (Test-SteamSearch $pg) -eq 'vacia' }
$despues=Test-SteamSearch $n.page
$ok=($despues -eq 'vacia')
Write-Estado $E ($(if($ok){'corregido'}else{'no_verificado'})) @{ verificado=$ok; busqueda_antes=$antes; busqueda=$despues; pagina_antes=$p.pagina; pagina=$n.page.pagina; via='steam://open/games'; foco=$n.foco; minimizado=$n.minimizado }
