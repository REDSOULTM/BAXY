# State explorador_este_equipo: the harness's own Explorer window showing Este equipo (shell:MyComputerFolder), for the
# cases whose target is Descargas (s04, e4, y5), so that going there is a real navigation and never "ya estaba".
if(-not ('EstadoW32' -as [type])){ . (Join-Path $PSScriptRoot 'comun.ps1') }
. (Join-Path $PSScriptRoot 'explorador_comun.ps1')
Set-ExplorerAt 'explorador_este_equipo' 'shell:MyComputerFolder' 'Este equipo'
