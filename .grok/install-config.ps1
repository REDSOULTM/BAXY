<#
.SYNOPSIS
Instala en ~/.grok/config.toml el bloque [skills] de BAXY: apaga las skills
bundled que no son de este proyecto.

.DESCRIPTION
Grok lee skills, modelo, esfuerzo y subagentes SOLO del config de usuario. Un
.grok/config.toml de proyecto admite unicamente [mcp_servers], asi que este
bloque no puede vivir activo dentro del repositorio y hay que instalarlo.

Hace copia de seguridad antes de tocar nada y no escribe BOM. No toca
credenciales, ni auth.json, ni ninguna otra clave del config.

Comprueba el resultado con `grok inspect`: las apagadas salen como [disabled].

Fichero sin caracteres no ASCII a proposito: PowerShell 5.1 lee un .ps1 sin BOM
como ANSI y rompe el script.

.EXAMPLE
.\.grok\install-config.ps1
.\.grok\install-config.ps1 -Force      # sustituye un [skills] ya existente
#>
param(
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$sourceRoot = Split-Path -Parent $PSCommandPath
$template = Join-Path $sourceRoot 'config-usuario.toml'
if (-not (Test-Path -LiteralPath $template -PathType Leaf)) {
    throw "template_missing: $template"
}

$grokHome = if ([string]::IsNullOrWhiteSpace($env:GROK_HOME)) {
    Join-Path $HOME '.grok'
} else {
    $env:GROK_HOME
}
if (-not (Test-Path -LiteralPath $grokHome)) {
    throw "grok_home_missing: $grokHome (instala Grok primero)"
}

$configPath = Join-Path $grokHome 'config.toml'
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

# Del template solo viaja el bloque, no la cabecera de comentarios del repo.
$templateText = [System.IO.File]::ReadAllText($template)
$idx = $templateText.IndexOf('[skills]')
if ($idx -lt 0) { throw 'template_sin_bloque_skills' }
$block = $templateText.Substring($idx).TrimEnd()
$header = '# Instalado por BAXY con .\.grok\install-config.ps1 - ver .grok/README.md'
$block = $header + "`r`n" + $block

if (-not (Test-Path -LiteralPath $configPath)) {
    [System.IO.File]::WriteAllText($configPath, $block + "`r`n", $utf8NoBom)
    Write-Output "config_creado: $configPath"
    Write-Output 'comprueba: grok inspect'
    return
}

$current = [System.IO.File]::ReadAllText($configPath)

if ($current -match '(?m)^\s*\[skills\]') {
    if (-not $Force) {
        Write-Output "skills_ya_presente: $configPath (usa -Force para sustituirlo)"
        return
    }
    # Quita el bloque [skills] existente: de su cabecera a la siguiente tabla.
    $lines = $current -split "`r?`n"
    $out = New-Object System.Collections.Generic.List[string]
    $inSkills = $false
    foreach ($line in $lines) {
        if ($line -match '^\s*\[skills\]') { $inSkills = $true; continue }
        if ($inSkills -and $line -match '^\s*\[') { $inSkills = $false }
        if (-not $inSkills) { $out.Add($line) }
    }
    $current = ($out -join "`r`n")
}

$backup = "$configPath.bak-" + (Get-Date -Format 'yyyyMMdd-HHmmss')
Copy-Item -LiteralPath $configPath -Destination $backup -Force
Write-Output "copia_de_seguridad: $backup"

$merged = $current.TrimEnd() + "`r`n`r`n" + $block + "`r`n"
[System.IO.File]::WriteAllText($configPath, $merged, $utf8NoBom)

Write-Output "skills_instalado: $configPath"
Write-Output 'comprueba: grok inspect   (las apagadas salen como [disabled])'
