# M122 — comprobación manual, sólo a pedido: abre example.com y un video de
# YouTube en el navegador predeterminado de la persona (dos pestañas nuevas; no
# cierra nada), informa lo que mostraron el campo de dirección y la sesión
# multimedia (SMTC) y pausa el video que ella misma empezó.
# No la ejecutes durante una medición ni mientras la persona usa el navegador
# o los altavoces. documentacion/NAVEGADOR_USUARIO.md
param(
    [string]$Query = 'Rick Astley Never Gonna Give You Up'
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$running = @(Get-Process -Name 'Baxy', 'baxy-core' -ErrorAction SilentlyContinue)
if ($running.Count -gt 0) {
    Write-Output 'check_user_browser_skipped: BAXY esta en marcha (una medicion puede leer la sesion multimedia)'
    exit 2
}
$env:BAXY_USER_BROWSER_LIVE_CHECK = '1'
$env:BAXY_USER_BROWSER_LIVE_QUERY = $Query
try {
    & dotnet test (Join-Path $root 'tests\Baxy.Providers.Windows.Tests') -c Release --nologo `
        -v:minimal --disable-build-servers -p:UseSharedCompilation=false `
        --filter 'FullyQualifiedName=Baxy.Providers.Windows.Tests.UserBrowserLiveCheck.DefaultBrowserOpensVerifiesAndPausesWhatItStarted' `
        --logger 'console;verbosity=detailed'
    $code = $LASTEXITCODE
} finally {
    Remove-Item Env:BAXY_USER_BROWSER_LIVE_CHECK -ErrorAction SilentlyContinue
    Remove-Item Env:BAXY_USER_BROWSER_LIVE_QUERY -ErrorAction SilentlyContinue
    & dotnet build-server shutdown | Out-Null
}
exit $code
