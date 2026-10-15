# State explorador_en:<carpeta>: the harness's own Explorer window showing <carpeta>, sorted by name ascending.
# <carpeta> is a shell path (shell:Downloads), an absolute path, or a path relative to the Documents folder
# ("baxy-prueba-v3"). Same window rules as explorador_descargas (explorador_comun.ps1): the person's Explorer windows
# are never navigated or closed. The sort is set through the folder view (ShellFolderView.SortColumns), no clicks.
param([string]$Arg='')
if(-not ('EstadoW32' -as [type])){ . (Join-Path $PSScriptRoot 'comun.ps1') }
. (Join-Path $PSScriptRoot 'explorador_comun.ps1')
$E="explorador_en:$Arg"
if(-not $Arg){ Write-Estado $E 'sin_argumento' @{ verificado=$false }; return }
$target=if($Arg -like 'shell:*' -or [IO.Path]::IsPathRooted($Arg)){ $Arg }else{ Join-Path ([Environment]::GetFolderPath('MyDocuments')) $Arg }
if($target -notlike 'shell:*' -and -not (Test-Path -LiteralPath $target)){ Write-Estado $E 'carpeta_no_existe' @{ verificado=$false; ruta=$target }; return }
Set-ExplorerAt $E $target $Arg
$h=@(Get-Propios | Where-Object { $_.tipo -eq 'explorador' } | ForEach-Object { [long]$_.hwnd })[0]
$win=@(Get-ShellExplorerWindows | Where-Object { [long]$_.HWND -eq $h })[0]
if(-not $win){ return }
$orden=$null
try{
  if($win.Document.SortColumns -ne 'prop:System.ItemNameDisplay;'){ $win.Document.SortColumns='prop:System.ItemNameDisplay;'; Start-Sleep -Milliseconds 300 }
  $orden=$win.Document.SortColumns
}catch{ $orden="error:$($_.Exception.Message)" }
Write-Estado "$E|orden" ($(if($orden -eq 'prop:System.ItemNameDisplay;'){'ok'}else{'no_verificado'})) @{ verificado=($orden -eq 'prop:System.ItemNameDisplay;'); orden=$orden }
