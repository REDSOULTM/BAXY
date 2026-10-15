# State paint_base: no Paint with unsaved changes or a dialog before a Paint case. The tool and colour do not matter
# (owner, 2026-10-07), so a closed Paint is the base state and is not opened.
#  - A Paint the harness opened (propios.jsonl) or the batch started (the ledger proves it: a case or BAXY opened it) is
#    closed, even with a dialog inside it (pasada r9: the resize dialog t-long-3/t-form-1 left in a batch Paint, with a
#    5760x16200 canvas, sat under t-file-3, t-file-4, t-menu-4): the dialog is cancelled, the window closed without
#    saving, or its exact PID stopped (Close-AppsPropias, Close-ProcesosDelLote).
#  - Any other Paint is the person's: never closed or edited; the line says whether its title marks unsaved changes
#    ("*") or a dialog holds it (a Win32 modal dialog, or one drawn inside its window).
if(-not ('EstadoW32' -as [type])){ . (Join-Path $PSScriptRoot 'comun.ps1') }
. (Join-Path $PSScriptRoot 'apps_comun.ps1')
$E='paint_base'
$cerradas=@(Close-AppsPropias 'mspaint')+@(Close-ProcesosDelLote 'mspaint')
$ps=@(Get-Process mspaint -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 })
if($ps.Count -eq 0){ Write-Estado $E $(if($cerradas.Count){'corregido'}else{'ok'}) @{ verificado=$true; ventana='cerrada'; cerradas_antes=$cerradas }; return }
$titulos=@($ps | ForEach-Object { $_.MainWindowTitle })
$sucios=@($titulos | Where-Object { $_ -match '^\*' })
if($sucios.Count -gt 0){ Write-Estado $E 'paint_con_cambios' @{ verificado=$false; ventanas=$titulos; cerradas_antes=$cerradas; nota='Paint abierto con cambios sin guardar: no se toca' }; return }
# 2026-10-08 (regr6): an «Abrir» dialog a v3 case left open at 04:38 UTC disabled Paint for every Paint case after it
# (s07, tanda 3 c19): the cases measured the dialog, not Paint. A Paint held by its own modal dialog is no base state.
$modales=@($ps | ForEach-Object { [EstadoW32]::ModalOf($_.MainWindowHandle) } | Where-Object { $_ })
$modales+=@($ps | ForEach-Object { Get-DialogosDeVentana ([long]$_.MainWindowHandle) } | ForEach-Object { try{ [string]$_.Current.Name }catch{ '?' } })
if($modales.Count -gt 0){ Write-Estado $E 'paint_con_dialogo' @{ verificado=$false; ventanas=$titulos; dialogos=$modales; cerradas_antes=$cerradas; nota='Paint de la persona con un dialogo abierto: no se toca' }; return }
Write-Estado $E 'ok' @{ verificado=$true; ventana='abierta'; ventanas=$titulos; cerradas_antes=$cerradas }
