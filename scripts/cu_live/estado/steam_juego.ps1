# State steam_juego:<appid>:<accion> (encargo imp-steam): a Steam game in the state its case starts from, and given back
# after it (casos.json "precondicion"). Harness only, never product code. ASCII only (PowerShell 5.1 reads it as ANSI).
# Owner order (PROMPT_ESTABILIZACION, decision 9): only "Super Meat Boy" (40800) is ever installed or uninstalled, and it
# ends as it was when the batch found it. Any other game is only read, and closed when a case launched it.
#  - leer_instalado | leer_desinstalado (40800): says whether the order is already fulfilled (cumple_orden) and, the
#    first time, records how the game was (cu-estado\steam_juego_40800.json) so "devolver" puts it back.
#  - instalado | desinstalado (40800): makes it so through Steam's own address (steam://install/<id>,
#    steam://uninstall/<id>) and one real click on the dialog's own button, located by OCR (the button: the bottom-most
#    line that reads exactly the label, below the dialog's title of the same word); read back on the game's manifest.
#    Installed means fully installed (StateFlags with 4), waited for up to 20 min.
#  - devolver (40800): the recorded state, then the record is dropped.
#  - leer_corriendo | cerrado (any appid): whether a process runs from the game's install folder (cumple_orden), and
#    closing those born after this batch started (its ledger CU_LIBRO), by exact PID; one older is the person's and is
#    never touched (verificado=false).
# Steam is never started (steam_no_abierto).
param([string]$Arg='')
if(-not ('EstadoW32' -as [type])){ . (Join-Path $PSScriptRoot 'comun.ps1') }
$ErrorActionPreference='Continue'
$E="steam_juego:$Arg"
$PruebaInstalable='40800'
$appid,$accion=$Arg -split ':',2
if($appid -notmatch '^[1-9][0-9]{0,9}$' -or -not $accion){ Write-Estado $E 'argumento_invalido' @{ verificado=$false }; return }
$Registro=Join-Path $env:LOCALAPPDATA ("BAXY\cu-estado\steam_juego_{0}.json" -f $appid)

if(-not ('SteamJuegoW32' -as [type])){
Add-Type -ReferencedAssemblies System.Drawing @"
using System; using System.Drawing; using System.Drawing.Imaging; using System.Runtime.InteropServices;
public static class SteamJuegoW32 {
  [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X; public int Y; }
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern bool GetCursorPos(out POINT p);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, int x, int y, uint d, IntPtr e);
  [DllImport("user32.dll")] public static extern IntPtr WindowFromPoint(POINT p);
  [DllImport("user32.dll")] public static extern IntPtr GetAncestor(IntPtr h, uint flags);
  // The darker pass the product's OCR locator reads too (WindowsVisibleOcrLocator.Darkened): white text on a blue
  // button is read only there (measured 2026-10-11 on Steam's install and uninstall dialogs).
  public static Bitmap Darkened(Bitmap source){
    var copy = new Bitmap(source.Width, source.Height, PixelFormat.Format32bppArgb);
    using (var g = Graphics.FromImage(copy)) { g.DrawImage(source, 0, 0, source.Width, source.Height); }
    var rect = new Rectangle(0, 0, copy.Width, copy.Height);
    BitmapData data = copy.LockBits(rect, ImageLockMode.ReadWrite, PixelFormat.Format32bppArgb);
    var bytes = new byte[data.Stride * data.Height];
    Marshal.Copy(data.Scan0, bytes, 0, bytes.Length);
    for (int i = 0; i + 3 < bytes.Length; i += 4) {
      double l = 0.114 * bytes[i] + 0.587 * bytes[i + 1] + 0.299 * bytes[i + 2];
      byte v = (byte)Math.Round(255 * Math.Pow(Math.Min(255, Math.Max(0, l)) / 255.0, 2.5));
      bytes[i] = v; bytes[i + 1] = v; bytes[i + 2] = v;
    }
    Marshal.Copy(bytes, 0, data.Scan0, bytes.Length);
    copy.UnlockBits(data);
    return copy;
  }
}
"@
}

function Get-SteamLibraries(){
  $sp=(Get-ItemProperty HKCU:\Software\Valve\Steam -ErrorAction SilentlyContinue).SteamPath
  if(-not $sp){ return @() }
  $libs=@($sp)
  $vdf=Join-Path $sp 'steamapps\libraryfolders.vdf'
  if(Test-Path -LiteralPath $vdf){ foreach($l in (Get-Content -LiteralPath $vdf)){ if($l -match '"path"\s+"([^"]+)"'){ $libs+=($matches[1] -replace '\\\\','\') } } }
  @($libs | ForEach-Object { [IO.Path]::GetFullPath($_) } | Select-Object -Unique)
}

function Get-Manifiesto([string]$Id){
  # @{ ruta; flags; instalado; carpeta } of appmanifest_<id>.acf in any library, or $null.
  foreach($lib in Get-SteamLibraries){
    $f=Join-Path $lib ("steamapps\appmanifest_{0}.acf" -f $Id)
    if(-not (Test-Path -LiteralPath $f)){ continue }
    $t=''; try{ $t=[IO.File]::ReadAllText($f) }catch{}
    $flags=0; if($t -match '"StateFlags"\s+"(\d+)"'){ $flags=[long]$matches[1] }
    $dir=''; if($t -match '"installdir"\s+"([^"]+)"'){ $dir=Join-Path $lib ("steamapps\common\{0}" -f $matches[1]) }
    return [pscustomobject]@{ ruta=$f; flags=$flags; instalado=(($flags -band 4) -ne 0); carpeta=$dir }
  }
  $null
}

function Get-Estado([string]$Id){ $m=Get-Manifiesto $Id; if($m -and $m.instalado){ 'instalado' }elseif($m){ 'a_medias' }else{ 'desinstalado' } }

function Get-SteamTop(){
  $ids=@(Get-Process steamwebhelper -ErrorAction SilentlyContinue | ForEach-Object Id)
  $found=New-Object Collections.ArrayList
  [void][EstadoW32]::EnumWindows({ param($h,$l)
    $p=0; [void][EstadoW32]::GetWindowThreadProcessId($h,[ref]$p)
    if($ids -contains $p -and [EstadoW32]::IsWindowVisible($h) -and -not [EstadoW32]::IsIconic($h)){ [void]$found.Add([long]$h) }
    $true },[IntPtr]::Zero)
  ,@($found)
}

function Find-Boton([IntPtr]$Hwnd,[string[]]$Etiquetas){
  # The dialog's button: the bottom-most OCR line (normal and darker pass) that reads exactly a label, when another
  # such line above it (the dialog's title) proves it is not the title itself. @{x;y} in window pixels, or $null.
  $bmp=Get-WindowBitmap $Hwnd; if(-not $bmp){ return $null }
  $dark=[SteamJuegoW32]::Darkened($bmp)
  $lineas=@(@(Read-BitmapText $bmp | ForEach-Object { $_ }) + @(Read-BitmapText $dark | ForEach-Object { $_ }))
  $bmp.Dispose(); $dark.Dispose()
  $want=@($Etiquetas | ForEach-Object { $_.ToLowerInvariant() })
  $hits=@($lineas | Where-Object { $want -contains ([string]$_.text).Trim().ToLowerInvariant() } | Sort-Object y)
  if($hits.Count -lt 2 -or ($hits[-1].y - $hits[0].y) -lt 40){ return $null }
  $b=$hits[-1]
  [pscustomobject]@{ x=[int]($b.x+$b.w/2); y=[int]($b.y+$b.h/2); texto=$b.text }
}

function Invoke-ActoSteam([string]$Uri,[string[]]$Etiquetas){
  # Steam's address, its dialog's window (one born for it, else Steam's window in front) and one real click on its
  # button, only when the point shows that very window. The cursor and the front go back.
  $fg=Get-Foreground
  $antes=Get-SteamTop
  Start-Process $Uri
  $win=[IntPtr]::Zero; $boton=$null
  for($i=0;$i -lt 30 -and -not $boton;$i++){
    Start-Sleep -Milliseconds 500
    $now=Get-SteamTop
    $nuevas=@($now | Where-Object { $antes -notcontains $_ })
    $front=[long](Get-Foreground)
    $cand=if($nuevas.Count){ if($nuevas -contains $front){ $front }else{ $nuevas[0] } }elseif($i -ge 3 -and $now -contains $front){ $front }else{ 0 }
    if($cand -ne 0){ $win=[IntPtr]$cand; $boton=Find-Boton $win $Etiquetas }
  }
  if(-not $boton){ $f=Restore-Foreground $fg @('steamwebhelper','steam'); return [pscustomobject]@{ clic=$false; motivo='boton_no_visto'; foco=$f } }
  for($i=0;$i -lt 3 -and (Get-Foreground) -ne $win;$i++){ [void][EstadoW32]::SetForegroundWindow($win); Start-Sleep -Milliseconds 300; if((Get-Foreground) -ne $win){ [EstadoW32]::SwitchToThisWindow($win,$true); Start-Sleep -Milliseconds 300 } }
  $r=New-Object EstadoW32+RECT; [void][EstadoW32]::GetWindowRect($win,[ref]$r)
  $pt=New-Object SteamJuegoW32+POINT; $pt.X=$r.Left+$boton.x; $pt.Y=$r.Top+$boton.y
  $raiz=[SteamJuegoW32]::GetAncestor([SteamJuegoW32]::WindowFromPoint($pt),2)
  if((Get-Foreground) -ne $win -or $raiz -ne $win){ $f=Restore-Foreground $fg @('steamwebhelper','steam'); return [pscustomobject]@{ clic=$false; motivo='ventana_tapada'; foco=$f } }
  $cur=New-Object SteamJuegoW32+POINT; [void][SteamJuegoW32]::GetCursorPos([ref]$cur)
  [void][SteamJuegoW32]::SetCursorPos($pt.X,$pt.Y); Start-Sleep -Milliseconds 120
  [SteamJuegoW32]::mouse_event(2,0,0,0,[IntPtr]::Zero); Start-Sleep -Milliseconds 60; [SteamJuegoW32]::mouse_event(4,0,0,0,[IntPtr]::Zero)
  Start-Sleep -Milliseconds 200; [void][SteamJuegoW32]::SetCursorPos($cur.X,$cur.Y)
  Start-Sleep -Milliseconds 800
  $f=Restore-Foreground $fg @('steamwebhelper','steam')
  [pscustomobject]@{ clic=$true; boton=$boton.texto; foco=$f }
}

function Wait-Estado([string]$Id,[string]$Quiero,[int]$Segundos){
  $sw=[Diagnostics.Stopwatch]::StartNew()
  while($sw.Elapsed.TotalSeconds -lt $Segundos){ if((Get-Estado $Id) -eq $Quiero){ return $true }; Start-Sleep -Seconds 2 }
  (Get-Estado $Id) -eq $Quiero
}

function Set-EstadoJuego([string]$Id,[string]$Quiero){
  $antes=Get-Estado $Id
  if($antes -eq $Quiero){ return @{ resultado='ok'; verificado=$true; antes=$antes } }
  # A download under way ends before anything else is asked of it (installed is "fully", uninstalled is "no manifest").
  if($antes -eq 'a_medias' -and $Quiero -eq 'instalado'){ $ok=Wait-Estado $Id 'instalado' 1200; return @{ resultado=$(if($ok){'corregido'}else{'no_verificado'}); verificado=$ok; antes=$antes; via='espera_descarga' } }
  if($Quiero -eq 'instalado'){ $a=Invoke-ActoSteam ("steam://install/{0}" -f $Id) @('Instalar','Install') }
  else{ $a=Invoke-ActoSteam ("steam://uninstall/{0}" -f $Id) @('Desinstalar','Uninstall') }
  $ok=$false
  if($a.clic){ $ok=Wait-Estado $Id $Quiero $(if($Quiero -eq 'instalado'){1200}else{120}) }
  @{ resultado=$(if($ok){'corregido'}else{'no_verificado'}); verificado=$ok; antes=$antes; clic=$a.clic; motivo=$a.motivo; boton=$a.boton; foco=$a.foco }
}

function Get-ProcesosJuego([string]$Id){
  $m=Get-Manifiesto $Id
  if(-not $m -or -not $m.carpeta){ return @() }
  $pre=([IO.Path]::GetFullPath($m.carpeta)).TrimEnd('\')+'\'
  @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith($pre,[StringComparison]::OrdinalIgnoreCase) })
}

if(@(Get-Process steam -ErrorAction SilentlyContinue).Count -eq 0){ Write-Estado $E 'steam_no_abierto' @{ verificado=$false }; return }
$soloLectura=@('leer_corriendo','cerrado')
if($soloLectura -notcontains $accion -and $appid -ne $PruebaInstalable){ Write-Estado $E 'juego_no_permitido' @{ verificado=$false; nota='solo Super Meat Boy (40800) se instala o desinstala' }; return }

switch($accion){
  {$_ -eq 'leer_instalado' -or $_ -eq 'leer_desinstalado'} {
    $ahora=Get-Estado $appid
    if(-not (Test-Path -LiteralPath $Registro)){
      $orig=if($ahora -eq 'desinstalado'){'desinstalado'}else{'instalado'}
      New-Item -ItemType Directory -Force (Split-Path $Registro) | Out-Null
      [IO.File]::WriteAllText($Registro,(@{ original=$orig; desde=(Get-Date -Format o) } | ConvertTo-Json -Compress),(New-Object Text.UTF8Encoding $false))
    }
    $cumple=if($accion -eq 'leer_instalado'){ $ahora -ne 'desinstalado' }else{ $ahora -eq 'desinstalado' }
    Write-Estado $E $ahora @{ verificado=$true; cumple_orden=$cumple }
    return
  }
  {$_ -eq 'instalado' -or $_ -eq 'desinstalado'} {
    $r=Set-EstadoJuego $appid $accion
    Write-Estado $E $r.resultado $r
    return
  }
  {$_ -eq 'devolver' -or $_ -eq 'devolver_pendiente'} {
    if(-not (Test-Path -LiteralPath $Registro)){ Write-Estado $E 'sin_registro' @{ verificado=$true; estado=(Get-Estado $appid) }; return }
    $orig=([IO.File]::ReadAllText($Registro) | ConvertFrom-Json).original
    $r=Set-EstadoJuego $appid $orig
    if($r.verificado){ Remove-Item -LiteralPath $Registro -Force }
    $r['original']=$orig
    Write-Estado $E $r.resultado $r
    return
  }
  'leer_corriendo' {
    $p=@(Get-ProcesosJuego $appid)
    Write-Estado $E $(if($p.Count){'corriendo'}else{'cerrado'}) @{ verificado=$true; cumple_orden=($p.Count -gt 0); pids=@($p | ForEach-Object { [int]$_.ProcessId }) }
    return
  }
  'cerrado' {
    $p=@(Get-ProcesosJuego $appid)
    if($p.Count -eq 0){ Write-Estado $E 'ok' @{ verificado=$true }; return }
    $libro=$env:CU_LIBRO
    $desde=if($libro -and (Test-Path -LiteralPath $libro)){ (Get-Item -LiteralPath $libro).CreationTime }else{ $null }
    $cerrados=@(); $ajenos=@()
    foreach($q in $p){
      $nacio=$q.CreationDate
      if(-not $desde -or -not $nacio -or $nacio -lt $desde){ $ajenos+=[int]$q.ProcessId; continue }
      $proc=Get-Process -Id $q.ProcessId -ErrorAction SilentlyContinue
      if($proc -and $proc.MainWindowHandle -ne [IntPtr]::Zero){ [void]$proc.CloseMainWindow(); Start-Sleep -Seconds 3 }
      if(Get-Process -Id $q.ProcessId -ErrorAction SilentlyContinue){ Stop-Process -Id $q.ProcessId -Force -ErrorAction SilentlyContinue }
      $cerrados+=[int]$q.ProcessId
    }
    Start-Sleep -Seconds 1
    $quedan=@(Get-ProcesosJuego $appid | Where-Object { $ajenos -notcontains [int]$_.ProcessId })
    $ok=($quedan.Count -eq 0 -and $ajenos.Count -eq 0)
    Write-Estado $E $(if($ok){'corregido'}elseif($ajenos.Count){'ajeno_corriendo'}else{'no_verificado'}) @{ verificado=$ok; cerrados=$cerrados; ajenos=$ajenos; quedan=@($quedan | ForEach-Object { [int]$_.ProcessId }) }
    return
  }
  default { Write-Estado $E 'accion_desconocida' @{ verificado=$false } }
}
