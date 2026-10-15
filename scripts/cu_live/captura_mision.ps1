# Photo of the mission's window taken when the conductor ends, BEFORE the person gets the front back (cu_live.sh).
# usage: captura_mision.ps1 -Dir <evidence dir> [-Excluir "<hwnd> <hwnd>"]
#   after.png is taken by batch.sh after the meter gave the front back to the person's window, so it showed that window
#   (Discord, 2026-10-09 BANCO_72 r23) over the result. This one is taken while nothing has moved yet:
#   - the window: the last top-level window BAXY read or acted on (journal-caso.json "tocadas", journal_caso.py) that
#     still exists, is visible and not minimized, is not excluded (the simulated user's window) and answers; it is
#     photographed with PrintWindow, which reads the window's own pixels behind any other window: no focus, no input;
#   - without one (the mission closed it, or touched none), the screen as it is.
#   Writes <ev>\after-mision.png (half size for the screen, full size for a window) and <ev>\after-mision.json: the
#   method, the window's hwnd, process and title, and the foreground window at that instant (hwnd and process only):
#   verificar.ps1 dumps that one too. VS Code and Opera windows are never photographed (AppsProhibidos).
param([Parameter(Mandatory=$true)][string]$Dir,[string]$Excluir='')
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'estado\comun.ps1')
. (Join-Path $PSScriptRoot 'estado\apps_comun.ps1')
Add-Type -AssemblyName System.Windows.Forms
$ErrorActionPreference='Continue'
$png=Join-Path $Dir 'after-mision.png'; $meta=Join-Path $Dir 'after-mision.json'
Remove-Item -LiteralPath $png,$meta -Force -ErrorAction SilentlyContinue
$fuera=@($Excluir -split '\s+' | Where-Object { $_ } | ForEach-Object { [long]$_ })
function Get-Proceso([IntPtr]$H){ $p=0; [void][EstadoW32]::GetWindowThreadProcessId($H,[ref]$p); [string](Get-Process -Id $p -ErrorAction SilentlyContinue).ProcessName }
$tocadas=@()
$jc=Join-Path $Dir 'journal-caso.json'
if(Test-Path -LiteralPath $jc){ try{ $tocadas=@(([IO.File]::ReadAllText($jc,[Text.Encoding]::UTF8) | ConvertFrom-Json).tocadas | ForEach-Object { [long]$_ }) }catch{} }
$fg=[EstadoW32]::GetForegroundWindow()
$d=[ordered]@{ hora=(Get-Date).ToString('o'); metodo=$null; primer_plano=[ordered]@{ hwnd=[long]$fg; proceso=(Get-Proceso $fg) }; tocadas=$tocadas }
$bmp=$null
foreach($h in $tocadas){
  $ip=[IntPtr]$h
  if($fuera -contains $h -or -not [EstadoW32]::IsWindow($ip) -or -not [EstadoW32]::IsWindowVisible($ip) -or [EstadoW32]::IsIconic($ip)){ continue }
  $proc=Get-Proceso $ip
  if($global:AppsProhibidos -contains $proc -or -not (Test-VentanaResponde $ip)){ continue }
  $bmp=Get-WindowBitmap $ip
  if($bmp){ $d.metodo='ventana'; $d['hwnd']=$h; $d['proceso']=$proc; $d['titulo']=[EstadoResponde]::Titulo($ip); break }
}
if(-not $bmp){
  $b=[Windows.Forms.Screen]::PrimaryScreen.Bounds
  $full=New-Object Drawing.Bitmap $b.Width,$b.Height; $g=[Drawing.Graphics]::FromImage($full); $g.CopyFromScreen($b.X,$b.Y,0,0,$full.Size); $g.Dispose()
  $bmp=New-Object Drawing.Bitmap $full,([int]($b.Width/2)),([int]($b.Height/2)); $full.Dispose()
  $d.metodo='pantalla'
}
$bmp.Save($png,[Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose()
[IO.File]::WriteAllText($meta,(($d | ConvertTo-Json -Depth 4 -Compress)+"`n"),(New-Object Text.UTF8Encoding $false))
"captura_mision: $($d.metodo)$(if($d.Contains('proceso')){ ' '+$d['proceso'] })"
