# State paint_con_lienzo:<spec>: Paint open (by the harness) on a known canvas.
#   ''                          a new blank canvas of Paint's default size (Paint launched with no file)
#   '<W>x<H>[,trazo][,marca_roja]'  a white W x H image the harness generates in its own folder
#                               (%LOCALAPPDATA%\BAXY\cu-estado\lienzos, never the person's files) and opens:
#                               trazo = a black horizontal stroke through the middle; marca_roja = a red square
#                               in the top-left corner. The window is titled with that file's name, not "Sin titulo".
# A Paint the harness opened earlier is closed first (unsaved test drawing discarded); one it did not open is the
# person's and is never touched (ajena_abierta).
param([string]$Arg='')
if(-not ('EstadoW32' -as [type])){ . (Join-Path $PSScriptRoot 'comun.ps1') }
. (Join-Path $PSScriptRoot 'apps_comun.ps1')
$E="paint_con_lienzo:$Arg"
$archivo=$null; $w=0; $h=0
if($Arg){
  $partes=@($Arg -split ',' | ForEach-Object { $_.Trim() })
  if($partes[0] -notmatch '^(\d{2,5})x(\d{2,5})$'){ Write-Estado $E 'spec_invalida' @{ verificado=$false; nota='<ancho>x<alto>[,trazo][,marca_roja]' }; return }
  $w=[int]$matches[1]; $h=[int]$matches[2]
  $dir=Join-Path $env:LOCALAPPDATA 'BAXY\cu-estado\lienzos'; if(-not (Test-Path $dir)){ New-Item -ItemType Directory -Force $dir | Out-Null }
  $archivo=Join-Path $dir ('lienzo-{0}.png' -f (($partes -join '-') -replace '[^A-Za-z0-9_-]','_'))
  $b=New-Object Drawing.Bitmap $w,$h; $g=[Drawing.Graphics]::FromImage($b); $g.Clear([Drawing.Color]::White)
  if($partes -contains 'trazo'){ $pen=New-Object Drawing.Pen ([Drawing.Color]::Black),6; $g.DrawLine($pen,[int]($w*0.15),[int]($h/2),[int]($w*0.85),[int]($h/2)); $pen.Dispose() }
  if($partes -contains 'marca_roja'){ $g.FillRectangle([Drawing.Brushes]::Red,0,0,[Math]::Max(10,[int]($w/10)),[Math]::Max(10,[int]($h/10))) }
  $g.Dispose(); $b.Save($archivo,[Drawing.Imaging.ImageFormat]::Png); $b.Dispose()
}
# The harness's copy, and a copy the batch started (a case or BAXY opened it: the ledger proves it), are closed even
# with a dialog inside (pasada r9: t-form-1's resize dialog over a 5760x16200 canvas poisoned t-file-3, t-file-4,
# t-menu-4 and t-long-3): the dialog is cancelled, the window closed without saving or its exact PID stopped. The case
# then gets a NEW Paint process, so its canvas starts at Paint's default size, never at what a case left.
$cerradas=@(Close-AppsPropias 'mspaint')+@(Close-ProcesosDelLote 'mspaint')
if(@(Get-Process mspaint -ErrorAction SilentlyContinue).Count -gt 0){ Write-Estado $E 'ajena_abierta' @{ verificado=$false; cerradas_antes=$cerradas; nota='hay un Paint que el arnes no abrio: no se toca' }; return }
$fg=Get-Foreground
$hAntes=@((Get-TopWindows) | ForEach-Object { $_.hwnd })
$pAntes=@(Get-Process | ForEach-Object { $_.Id })
if($archivo){ Start-Process mspaint.exe -ArgumentList ('"{0}"' -f $archivo) }else{ Start-Process mspaint.exe }
$nuevas=@(Wait-NewWindows $hAntes { $_.app_proceso -eq 'mspaint' } 20)
if($nuevas.Count -eq 0){ Write-Estado $E 'no_abre' @{ verificado=$false }; return }
Add-PropiosApp $nuevas 'Paint' $pAntes
Set-AppAprendida 'Paint' 'mspaint'
$foco=Restore-Foreground $fg @('mspaint')
$titulo=$nuevas[0].titulo
# Paint titles the window with the file name, without its extension when extensions are hidden.
$ok=if($archivo){ $titulo -like ('*{0}*' -f [IO.Path]::GetFileNameWithoutExtension($archivo)) }else{ $true }
# The canvas size Paint's status bar shows ("1152 x 648 px", the sign is U+00D7): with a W x H spec it must match.
$lienzo=''
try{
  $tc=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::Text)
  $re='^\s*(\d+)\s*'+[char]0xD7+'\s*(\d+)'
  foreach($t in @([Windows.Automation.AutomationElement]::FromHandle([IntPtr][long]$nuevas[0].hwnd).FindAll('Descendants',$tc))){
    $m=[regex]::Match([string]$t.Current.Name,$re); if($m.Success){ $lienzo="$($m.Groups[1].Value)x$($m.Groups[2].Value)"; break }
  }
}catch{}
if($archivo -and $lienzo -and $lienzo -ne "$($w)x$($h)"){ $ok=$false }
# Still a dialog over it (none should be: a new process): not the base state.
$dialogos=@(Get-DialogosDeVentana ([long]$nuevas[0].hwnd) | ForEach-Object { try{ [string]$_.Current.Name }catch{ '?' } })
if($dialogos.Count -gt 0){ $ok=$false }
Write-Estado $E ($(if($ok){'corregido'}else{'no_verificado'})) @{ verificado=$ok; ventana=$titulo; archivo=$archivo; ancho=$w; alto=$h; lienzo=$lienzo; dialogos=$dialogos; cerradas_antes=$cerradas; foco=$foco }
