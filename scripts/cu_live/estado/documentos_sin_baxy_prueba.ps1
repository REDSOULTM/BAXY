# State documentos_sin_baxy_prueba: c3 creates D:\Perfil\Documentos\baxy-prueba, so before it the folder must not
# exist (otherwise "ya existe" passes for free). Only that exact folder, and only while empty, is removed.
param([string]$Carpeta='D:\Perfil\Documentos\baxy-prueba')
if(-not ('EstadoW32' -as [type])){ . (Join-Path $PSScriptRoot 'comun.ps1') }
$E='documentos_sin_baxy_prueba'
if(-not (Test-Path -LiteralPath $Carpeta)){ Write-Estado $E 'ok' @{ verificado=$true; ruta=$Carpeta; existe=$false }; return }
$dentro=@(Get-ChildItem -LiteralPath $Carpeta -Force)
if($dentro.Count -gt 0){ Write-Estado $E 'carpeta_con_contenido' @{ verificado=$false; ruta=$Carpeta; elementos=$dentro.Count; nota='no vacia: no se toca' }; return }
Remove-Item -LiteralPath $Carpeta -Force
$existe=Test-Path -LiteralPath $Carpeta
Write-Estado $E ($(if($existe){'no_verificado'}else{'corregido'})) @{ verificado=(-not $existe); ruta=$Carpeta; existe=$existe }
