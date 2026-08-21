<#
.SYNOPSIS
Instala los perfiles de Codex de BAXY (sol-efficient y sol-deep) en $CODEX_HOME.

.DESCRIPTION
Codex ignora `profiles` en un config con ámbito de proyecto, así que los dos
modos no pueden vivir activos dentro del repositorio. Este script copia las
plantillas de .codex/profiles/ a $CODEX_HOME (por defecto ~/.codex) con el
nombre que Codex espera: <perfil>.config.toml.

No toca ~/.codex/config.toml ni ninguna credencial.

.EXAMPLE
.\.codex\profiles\install.ps1
.\.codex\profiles\install.ps1 -Force      # sobrescribe perfiles ya instalados
#>
param(
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$sourceRoot = Split-Path -Parent $PSCommandPath

$codexHome = if ([string]::IsNullOrWhiteSpace($env:CODEX_HOME)) {
    Join-Path $HOME '.codex'
} else {
    $env:CODEX_HOME
}

if (-not (Test-Path -LiteralPath $codexHome)) {
    New-Item -ItemType Directory -Path $codexHome | Out-Null
    Write-Output "codex_home_created: $codexHome"
}

$installed = 0
$skipped = 0

foreach ($profileName in @('sol-efficient', 'sol-deep')) {
    $source = Join-Path $sourceRoot "$profileName.config.toml"
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "profile_template_missing: $source"
    }

    $target = Join-Path $codexHome "$profileName.config.toml"
    if ((Test-Path -LiteralPath $target) -and -not $Force) {
        Write-Output "profile_skipped_exists: $target (usa -Force para sobrescribir)"
        $skipped++
        continue
    }

    Copy-Item -LiteralPath $source -Destination $target -Force
    Write-Output "profile_installed: $target"
    $installed++
}

Write-Output "codex_profiles_done: installed=$installed skipped=$skipped"
Write-Output ''
Write-Output 'Uso:'
Write-Output '  codex --profile sol-efficient    # trabajo normal'
Write-Output '  codex --profile sol-deep         # auditoría transversal / ventana 1M'
Write-Output ''
Write-Output 'Requiere ChatGPT Pro: gpt-5.6-sol no está disponible con cuentas Plus.'
