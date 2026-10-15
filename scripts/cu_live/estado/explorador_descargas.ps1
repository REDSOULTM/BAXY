# State explorador_descargas: the harness's own Explorer window showing Descargas (shell:Downloads).
if(-not ('EstadoW32' -as [type])){ . (Join-Path $PSScriptRoot 'comun.ps1') }
. (Join-Path $PSScriptRoot 'explorador_comun.ps1')
Set-ExplorerAt 'explorador_descargas' 'shell:Downloads' 'Descargas'
