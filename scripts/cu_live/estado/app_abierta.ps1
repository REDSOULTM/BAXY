# State app_abierta:<Start menu name>: that app freshly open, in a window the harness opened.
#  - The app is launched through shell:AppsFolder\<AppID> (the same entry the Start menu uses), so any app the Start
#    menu lists works, desktop or packaged. The harness waits for its window and gives the foreground back.
#  - A copy the harness opened earlier is closed first (a case may have changed it), so the case starts fresh.
#  - A copy the harness did not open is the person's: it is never touched, and the line says ajena_abierta.
#  - Every window opened goes to propios.jsonl, so app_cerrada closes exactly those.
param([string]$Arg='')
if(-not ('EstadoW32' -as [type])){ . (Join-Path $PSScriptRoot 'comun.ps1') }
. (Join-Path $PSScriptRoot 'apps_comun.ps1')
$E="app_abierta:$Arg"
$app=Resolve-StartApp $Arg
if(-not $app){ Write-Estado $E 'app_desconocida' @{ verificado=$false; nota='no hay una sola entrada del menu Inicio con ese nombre' }; return }
$nombre=$app.Name
$cerradas=@(Close-AppsPropias $nombre)
$ajenas=@(Get-AjenasDe $nombre '')
# Inside a batch, a copy an earlier case left (born in the batch) is not the person's: it exits first.
if($ajenas.Count -gt 0){ $cerradas+=@(Close-AjenasDelLote $ajenas); $ajenas=@(Get-AjenasDe $nombre '') }
if($ajenas.Count -gt 0){ Write-Estado $E 'ajena_abierta' @{ verificado=$false; ventanas=@($ajenas | ForEach-Object { $_.titulo }); nota='abierta por la persona: no se toca' }; return }

$fg=Get-Foreground
$hAntes=@((Get-TopWindows) | ForEach-Object { $_.hwnd })
$pAntes=@(Get-Process | ForEach-Object { $_.Id })
# Only a window whose process is PROVEN to be this Start-menu entry (its AppUserModelID or its executable, see
# Get-IdentidadApp) is taken as the app's: a window the person opens meanwhile is never recorded as the harness's.
$ident=Get-IdentidadApp $app
if($ident.tipo -eq 'desconocida'){ Write-Estado $E 'sin_identidad' @{ verificado=$false; app=$nombre; nota='la entrada del menu Inicio no dice que proceso es la app: no se abre' }; return }
# v3 r5a M5: a program Windows would raise unasked opens with the person's rights (as BAXY opens it).
if(-not (Start-AppComoPersona $app)){ Start-Process explorer.exe -ArgumentList ('shell:AppsFolder\{0}' -f $app.AppID) }
$filtro={ $_.clase -ne 'Shell_TrayWnd' -and $global:AppsProhibidos -notcontains $_.app_proceso -and $_.app_proceso -ne 'Baxy' -and (Test-IdentidadVentana $_ $ident $nombre) }
$nuevas=@(Wait-NewWindows $hAntes $filtro 40)
if($nuevas.Count -eq 0){ Write-Estado $E 'no_abre' @{ verificado=$false; app=$nombre; cerradas_antes=$cerradas }; return }
Add-PropiosApp $nuevas $nombre $pAntes
$proc=@($nuevas | Group-Object app_proceso | Sort-Object Count -Descending)[0].Name
# The case starts on a loaded app: wait (8 s at most) until the main window's UIA tree stops growing.
# Measured 2026-10-07: Task Manager and the MMC consoles (Event Viewer, Services) opened through the shell run ELEVATED
# here, and UIA from a non-elevated process (this harness, and BAXY) sees only their empty panes; since r5a M5 they
# open with the person's rights (Start-AppComoPersona), so an elevated window is one the person opened.
$principal=[Windows.Automation.AutomationElement]::FromHandle([IntPtr][long]$nuevas[0].hwnd)
# An elevated app shows only empty panes to UIA from here: nothing to wait for.
$elevada=Test-Elevada ([int]$nuevas[0].app_pid)
$antes=-1; $fin=(Get-Date).AddSeconds($(if($elevada){0}else{8}))
while((Get-Date) -lt $fin){
  $n=-1; try{ $n=$principal.FindAll('Descendants',[Windows.Automation.Condition]::TrueCondition).Count }catch{}
  if($n -gt 20 -and $n -eq $antes){ break }
  $antes=$n; Start-Sleep -Milliseconds 700
}
Set-AppAprendida $nombre $proc
$foco=Restore-Foreground $fg @($nuevas | ForEach-Object { $_.proceso; $_.app_proceso } | Select-Object -Unique)
$vivas=@($nuevas | Where-Object { [EstadoW32]::IsWindow([IntPtr][long]$_.hwnd) })
Write-Estado $E ($(if($vivas.Count -gt 0){'corregido'}else{'no_verificado'})) @{ verificado=($vivas.Count -gt 0); app=$nombre; proceso=$proc; elevada=$elevada; ventanas=@($vivas | ForEach-Object { $_.titulo }); cerradas_antes=$cerradas; foco=$foco }
