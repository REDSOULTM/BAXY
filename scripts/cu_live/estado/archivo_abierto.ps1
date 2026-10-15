# State archivo_abierto:<ruta>: a harness fixture file open in its default app, in a window the harness opened.
# <ruta> is absolute or relative to the Documents folder, and must be inside a "baxy-prueba*" folder (only test files
# are ever opened). The file is opened the way a double click does (its default verb); the new window is recorded in
# propios.jsonl under the opening app's process, so app_cerrada:<that app> closes it. The file is only opened, never
# changed. Run after fixtures_prueba_v3 and after closing the harness's earlier copy of that app.
param([string]$Arg='')
if(-not ('EstadoW32' -as [type])){ . (Join-Path $PSScriptRoot 'comun.ps1') }
. (Join-Path $PSScriptRoot 'apps_comun.ps1')
$E="archivo_abierto:$Arg"
$ruta=if([IO.Path]::IsPathRooted($Arg)){ $Arg }else{ Join-Path ([Environment]::GetFolderPath('MyDocuments')) $Arg }
if($ruta -notmatch '\\baxy-prueba[^\\]*\\'){ Write-Estado $E 'fuera_de_prueba' @{ verificado=$false; ruta=$ruta }; return }
if(-not (Test-Path -LiteralPath $ruta -PathType Leaf)){ Write-Estado $E 'no_existe' @{ verificado=$false; ruta=$ruta }; return }
$hoja=Split-Path $ruta -Leaf
$antes=(Get-Item -LiteralPath $ruta).LastWriteTimeUtc
$fg=Get-Foreground
$hAntes=@((Get-TopWindows) | ForEach-Object { $_.hwnd })
$pAntes=@(Get-Process | ForEach-Object { $_.Id })
Start-Process -FilePath $ruta
$nuevas=@(Wait-NewWindows $hAntes { $_.titulo -like "*$hoja*" -or $_.titulo -like ('*{0}*' -f [IO.Path]::GetFileNameWithoutExtension($hoja)) } 30)
if($nuevas.Count -eq 0){ Write-Estado $E 'no_abre' @{ verificado=$false; ruta=$ruta }; return }
$proc=@($nuevas | Group-Object app_proceso | Sort-Object Count -Descending)[0].Name
# The opening app's Start-menu name, when the title ends with it ("paisaje.jpg - Fotos"), is learned for that process,
# so app_cerrada:<that name> closes this window; otherwise the item goes under its process name.
$tit=($nuevas[0].titulo -replace '[\u200E\u200F\u202A-\u202E]','').Trim()
# The title only proposes the name: it is learned only when the process is proven to be that entry.
$nombre=$null
foreach($s in @(Get-StartApps | Where-Object { $tit -like ('* - {0}' -f $_.Name) } | Sort-Object { $_.Name.Length } -Descending)){
  if(Test-IdentidadVentana $nuevas[0] (Get-IdentidadApp $s) $s.Name){ $nombre=$s.Name; break }
}
if(-not $nombre){ $s=Resolve-StartAppForProcess ([int]$nuevas[0].app_pid); if($s){ $nombre=$s.Name } }
if($nombre){ Set-AppAprendida $nombre $proc }else{ $nombre=$proc }
Add-PropiosApp $nuevas $nombre $pAntes
$foco=Restore-Foreground $fg @($nuevas | ForEach-Object { $_.proceso; $_.app_proceso } | Select-Object -Unique)
$igual=((Get-Item -LiteralPath $ruta).LastWriteTimeUtc -eq $antes)
Write-Estado $E ($(if($igual){'corregido'}else{'no_verificado'})) @{ verificado=$igual; ruta=$ruta; proceso=$proc; app=$nombre; ventanas=@($nuevas | ForEach-Object { $_.titulo }); archivo_sin_cambios=$igual; foco=$foco }
