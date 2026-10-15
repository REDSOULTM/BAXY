# State outlook_listo: Outlook (classic) freshly open (app_abierta), its profile LOADED, on the mail module, with
# nothing over it. Pasada r9: v3-05/06/07 met only "Configuracion de cuenta de correo electronico" (account setup,
# address prefilled, Conectar) and "Abriendo - Cargando perfil"; the cases never saw the main window. Measured
# 2026-10-08 16:02: the profile ("Outlook", account of the university) loads in about 30 s and then the Reminders
# window ("86 aviso(s)") opens over it.
#  - Each window of OUTLOOK.EXE is classed by Get-DecisionVentanaOutlook. An account setup window is closed (its own
#    close: nothing is connected or added) and the profile load is waited for; the Reminders window is closed, never
#    "Descartar todo" (that would change the person's calendar in their account). Both closes are -SinConfirmar: a
#    dialog the close raised is cancelled, never confirmed (no button of Outlook's that says yes is ever pressed).
#  - When the account setup closes Outlook with it, it is opened once more.
#  - Verified: the main window loaded, on the inbox (Correo), and no account or loading window left.
# Harness only. ASCII only.
param([string]$Arg='')
if(-not (Get-Command Write-Estado -ErrorAction SilentlyContinue)){ . (Join-Path $PSScriptRoot 'comun.ps1') }
. (Join-Path $PSScriptRoot 'apps_comun.ps1')
. (Join-Path $PSScriptRoot 'decisiones_comun.ps1')
$E='outlook_listo'
$nombre='Outlook (classic)'
$fg=Get-Foreground

function Get-VentanasOutlook(){
  @((Get-TopWindows) | Where-Object { $_.app_proceso -eq 'OUTLOOK' } | ForEach-Object {
    [pscustomobject]@{ hwnd=[long]$_.hwnd; titulo=[string]$_.titulo; tipo=(Get-DecisionVentanaOutlook ([string]$_.titulo) ([string]$_.clase)) } })
}
function Open-Outlook(){
  $a=@(& (Join-Path $PSScriptRoot 'app_abierta.ps1') -Arg $nombre | Where-Object { "$_" -match '^\{"estado"' } | ForEach-Object { "$_" | ConvertFrom-Json })
  ($a.Count -gt 0 -and $a[-1].verificado)
}

$cerradas=@(); $intentos=0; $v=@(); $listo=$false
while($intentos -lt 2){
  $intentos++
  if(-not (Open-Outlook)){ continue }
  $fin=(Get-Date).AddSeconds(75)
  do{
    $v=@(Get-VentanasOutlook)
    foreach($x in @($v | Where-Object { $_.tipo -eq 'cuenta' -or $_.tipo -eq 'avisos' })){
      try{ Close-WindowExact ([Windows.Automation.AutomationElement]::FromHandle([IntPtr]$x.hwnd)) -SinConfirmar; $cerradas+="$($x.tipo):$($x.titulo)" }catch{}
    }
    $v=@(Get-VentanasOutlook)
    $listo=(@($v | Where-Object { $_.tipo -eq 'principal' }).Count -gt 0 -and @($v | Where-Object { $_.tipo -in 'cuenta','cargando','avisos' }).Count -eq 0)
    if($listo -or @(Get-Process OUTLOOK -ErrorAction SilentlyContinue).Count -eq 0){ break }
    Start-Sleep -Milliseconds 1500
  }while((Get-Date) -lt $fin)
  # Reminders may open a moment after the main window: one more look.
  if($listo){ Start-Sleep -Seconds 3; foreach($x in @(Get-VentanasOutlook | Where-Object { $_.tipo -eq 'avisos' })){ try{ Close-WindowExact ([Windows.Automation.AutomationElement]::FromHandle([IntPtr]$x.hwnd)) -SinConfirmar; $cerradas+="avisos:$($x.titulo)" }catch{} } }
  if(@(Get-Process OUTLOOK -ErrorAction SilentlyContinue).Count){ break }
}
$v=@(Get-VentanasOutlook)
$principal=@($v | Where-Object { $_.tipo -eq 'principal' })[0]
$quedan=@($v | Where-Object { $_.tipo -in 'cuenta','cargando','avisos' } | ForEach-Object { $_.titulo })
$correo=($principal -and (Get-DecisionOutlookEnCorreo $principal.titulo))
$foco=Restore-Foreground $fg @('OUTLOOK')
$ok=([bool]$principal -and $quedan.Count -eq 0 -and $correo)
Write-Estado $E ($(if($ok){'corregido'}elseif(-not $principal){'sin_perfil_cargado'}else{'no_verificado'})) @{ verificado=$ok
  principal=$(if($principal){ $principal.titulo }else{ '' }); en_correo=[bool]$correo; cerradas=$cerradas; quedan=$quedan; intentos=$intentos; foco=$foco }
