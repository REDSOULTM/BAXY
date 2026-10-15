# Shared helpers for the harness state scripts (scripts/cu_live/estado/*.ps1). Dot-source it.
# Nothing here types, moves the mouse or brings a window to the front unless a caller asks for it.
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes,System.Drawing
[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ErrorActionPreference='Stop'

if(-not ('EstadoW32' -as [type])){
Add-Type @"
using System; using System.Text; using System.Runtime.InteropServices;
public static class EstadoW32 {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
  [DllImport("user32.dll")] public static extern bool IsWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern int GetWindowThreadProcessId(IntPtr h, out int pid);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool AttachThreadInput(int a, int b, bool attach);
  [DllImport("kernel32.dll")] public static extern int GetCurrentThreadId();
  [DllImport("user32.dll")] public static extern void SwitchToThisWindow(IntPtr h, bool altTab);
  [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, IntPtr extra);
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc f, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr p, EnumProc f, IntPtr l);
  public static string Title(IntPtr h){ var s=new StringBuilder(512); GetWindowText(h,s,512); return s.ToString(); }
  public static string Klass(IntPtr h){ var s=new StringBuilder(256); GetClassName(h,s,256); return s.ToString(); }
  [DllImport("user32.dll")] public static extern bool IsWindowEnabled(IntPtr h);
  [DllImport("user32.dll")] public static extern IntPtr GetWindow(IntPtr h, uint cmd);
  // The visible, enabled window a disabled main window is owned by (its modal dialog: «Abrir», «Guardar como»), or "".
  public static string ModalOf(IntPtr main){
    if(main==IntPtr.Zero || IsWindowEnabled(main)) return "";
    string found="";
    EnumWindows((h,l)=>{ if(GetWindow(h,4)==main && IsWindowVisible(h) && IsWindowEnabled(h)){ found=Title(h); return false; } return true; }, IntPtr.Zero);
    return found;
  }
}
"@
}
if(-not ('EstadoColgada' -as [type])){
Add-Type @"
using System; using System.Runtime.InteropServices;
public static class EstadoColgada {
  // A window whose program stopped answering (Windows shows a ghost of it): any UIA read of its Name waits 10 s and
  // comes back empty (measured 2026-10-08: a hung Resource Monitor made every top-window list take 10 s).
  [DllImport("user32.dll")] public static extern bool IsHungAppWindow(IntPtr h);
}
"@
}

if(-not ('EstadoResponde' -as [type])){
Add-Type @"
using System; using System.Text; using System.Runtime.InteropServices;
public static class EstadoResponde {
  [DllImport("user32.dll", SetLastError=true)] static extern IntPtr SendMessageTimeout(IntPtr h, uint msg, IntPtr w, IntPtr l, uint flags, uint ms, out IntPtr r);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int InternalGetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] static extern bool IsHungAppWindow(IntPtr h);
  // False when the window's thread does not pump messages: Windows already calls it hung, or a WM_NULL is not answered
  // in $ms (SMTO_ABORTIFHUNG). A message refused for another reason (UIPI: an elevated window) is not a hang.
  public static bool Responde(IntPtr h, uint ms){
    if(IsHungAppWindow(h)) return false;
    IntPtr r; if(SendMessageTimeout(h,0,IntPtr.Zero,IntPtr.Zero,0x2,ms,out r)!=IntPtr.Zero) return true;
    return Marshal.GetLastWin32Error()!=1460;
  }
  // The caption Windows keeps for the window: read without sending it a message (GetWindowText would wait on it).
  public static string Titulo(IntPtr h){ var s=new StringBuilder(512); InternalGetWindowText(h,s,512); return s.ToString(); }
}
"@
}

function Test-VentanaResponde([IntPtr]$Hwnd,[int]$Ms=1000){
  # 2026-10-09 (t-menu-1): a secondary explorer.exe hung behind an application error dialog held «--- verify» 11 min.
  # A window that does not answer is skipped before any UIA or COM read of it.
  [EstadoResponde]::Responde($Hwnd,[uint32]$Ms)
}

function Get-VentanasColgadas([int[]]$Pids=@(),[int]$Ms=500){
  # Visible top-level windows whose program does not answer: @{ hwnd; pid; proceso; clase; titulo }. Read without
  # sending them anything but one WM_NULL with a ceiling. -Pids: only windows of those processes.
  $l=New-Object Collections.Generic.List[object]
  $hs=New-Object Collections.Generic.List[IntPtr]
  $cb=[EstadoW32+EnumProc]{ param($h,$x) if([EstadoW32]::IsWindowVisible($h)){ $hs.Add($h) }; $true }
  [void][EstadoW32]::EnumWindows($cb,[IntPtr]::Zero)
  foreach($h in $hs){
    $p=0; [void][EstadoW32]::GetWindowThreadProcessId($h,[ref]$p)
    if($Pids.Count -gt 0 -and $Pids -notcontains $p){ continue }
    if([EstadoResponde]::Responde($h,[uint32]$Ms)){ continue }
    $l.Add([pscustomobject][ordered]@{ hwnd=[long]$h; pid=[int]$p; proceso=[string](Get-Process -Id $p -ErrorAction SilentlyContinue).ProcessName
      clase=[EstadoW32]::Klass($h); titulo=[EstadoResponde]::Titulo($h) })
  }
  $l.ToArray()
}

function Get-PidShell(){
  # The explorer.exe of the shell: the one that owns the taskbar (Shell_TrayWnd). Never closed by the harness.
  $script:pidShellEncontrado=0
  $cb=[EstadoW32+EnumProc]{ param($h,$x)
    if([EstadoW32]::Klass($h) -eq 'Shell_TrayWnd'){ $p=0; [void][EstadoW32]::GetWindowThreadProcessId($h,[ref]$p); $script:pidShellEncontrado=$p; return $false }
    $true }
  [void][EstadoW32]::EnumWindows($cb,[IntPtr]::Zero)
  [int]$script:pidShellEncontrado
}

# These scripts are UTF-8 without BOM, which PowerShell 5.1 reads as ANSI: non-ASCII names are built from code points.
$global:EstadoTituloConfig='Configuraci'+[char]0xF3+'n'

function Write-Estado([string]$Estado,[string]$Resultado,[hashtable]$Datos){
  # One JSON line per state: {"estado":..,"resultado":"ok|corregido|steam_no_abierto|..","verificado":bool,...}
  $o=[ordered]@{ estado=$Estado; resultado=$Resultado }
  if($Datos -and $Datos.ContainsKey('verificado')){ $o['verificado']=$Datos['verificado'] }
  if($Datos){ foreach($k in @($Datos.Keys | Sort-Object)){ if($k -ne 'verificado'){ $o[$k]=$Datos[$k] } } }
  ($o | ConvertTo-Json -Compress -Depth 5)
}

function Get-Foreground(){ [EstadoW32]::GetForegroundWindow() }

function Restore-Foreground([IntPtr]$Before,[string[]]$Apps,[switch]$TrasCerrar){
  # When the app this state touched ($Apps: process names) took the foreground, it goes back to the window that had it
  # (best effort, no input). If anything else is in front now (the person, or another agent's window), it is left alone.
  # -TrasCerrar: the harness just closed the window it had opened, which was in front, and Windows activated some
  # other window in its place; that window goes back to the one that had the foreground before.
  # Returns 'sin_cambio' | 'devuelto' | 'ajeno' | 'fallo'.
  if([EstadoW32]::GetForegroundWindow() -eq $Before){ return 'sin_cambio' }
  if($Before -eq [IntPtr]::Zero -or -not [EstadoW32]::IsWindow($Before)){ return 'ajeno' }
  # The app may still be activating when this runs (measured: Steam re-took the foreground after one restore), so it
  # tries a few times, and stops as soon as a window of some other program is in front.
  for($try=0;$try -lt 5;$try++){
    $cur=[EstadoW32]::GetForegroundWindow()
    if($cur -eq $Before){ return 'devuelto' }
    if($cur -ne [IntPtr]::Zero){
      $p=0; $other=[EstadoW32]::GetWindowThreadProcessId($cur,[ref]$p)
      $name=(Get-Process -Id $p -ErrorAction SilentlyContinue).ProcessName
      if(-not $TrasCerrar -and (-not $Apps -or $Apps -notcontains $name)){ return 'ajeno' }
      [void][EstadoW32]::SetForegroundWindow($Before); Start-Sleep -Milliseconds 120
      if([EstadoW32]::GetForegroundWindow() -ne $Before){
        # Foreground lock: share the input state of the thread that owns the foreground for one call, then let go.
        $mine=[EstadoW32]::GetCurrentThreadId()
        if($other -ne 0 -and $other -ne $mine){
          [void][EstadoW32]::AttachThreadInput($mine,$other,$true)
          [void][EstadoW32]::SetForegroundWindow($Before)
          [void][EstadoW32]::AttachThreadInput($mine,$other,$false)
          Start-Sleep -Milliseconds 120
        }
      }
      if([EstadoW32]::GetForegroundWindow() -ne $Before){ [EstadoW32]::SwitchToThisWindow($Before,$true); Start-Sleep -Milliseconds 120 }
      if($try -ge 1 -and [EstadoW32]::GetForegroundWindow() -eq $cur -and $Apps -contains $name){
        # Last resort, measured needed after Steam and Calculator launches: Windows only lets the process that made
        # the last input event move the foreground. One press of an UNASSIGNED virtual key (0xE8, no meaning in any
        # app) goes to the window in front, which was just checked to be the app this state touched, and then the
        # foreground is handed back.
        [EstadoW32]::keybd_event(0xE8,0,0,[IntPtr]::Zero); [EstadoW32]::keybd_event(0xE8,0,2,[IntPtr]::Zero)
        [void][EstadoW32]::SetForegroundWindow($Before); Start-Sleep -Milliseconds 120
      }
    }
    Start-Sleep -Milliseconds 300
  }
  if([EstadoW32]::GetForegroundWindow() -eq $Before){ 'devuelto' }else{ 'fallo' }
}

function Send-EscapeEnFrente([IntPtr]$Hwnd){
  # ONE Escape for a layer the caller just read over that exact window (a search dialog, an open menu): Chromium
  # offers no pattern to close them. The key goes to whatever is in front, so the window is brought there first and
  # nothing is pressed unless it is (the same rule as discord_escape.ps1). The caller gives the foreground back.
  # Returns 'escape' | 'sin_frente'.
  if($Hwnd -eq [IntPtr]::Zero -or -not [EstadoW32]::IsWindow($Hwnd)){ return 'sin_frente' }
  for($i=0;$i -lt 3 -and [EstadoW32]::GetForegroundWindow() -ne $Hwnd;$i++){
    if($i -eq 0){ [void][EstadoW32]::SetForegroundWindow($Hwnd) }else{ [EstadoW32]::SwitchToThisWindow($Hwnd,$true) }
    Start-Sleep -Milliseconds 300
  }
  if([EstadoW32]::GetForegroundWindow() -ne $Hwnd){ return 'sin_frente' }
  [EstadoW32]::keybd_event(0x1B,0,0,[IntPtr]::Zero); [EstadoW32]::keybd_event(0x1B,0,2,[IntPtr]::Zero)
  'escape'
}

function Find-TopWindowByName([string]$Name){
  # Exact top-level name (UIA), never a substring. A hung window is skipped before its Name is read (EstadoColgada):
  # a Name condition evaluated on it waited 10 s and never matched.
  @([Windows.Automation.AutomationElement]::RootElement.FindAll('Children',[Windows.Automation.Condition]::TrueCondition) | Where-Object {
    $h=[IntPtr]$_.Current.NativeWindowHandle
    -not ($h -ne [IntPtr]::Zero -and [EstadoColgada]::IsHungAppWindow($h)) -and $_.Current.Name -ceq $Name })
}

function Find-ById($Element,[string]$AutomationId){
  $c=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::AutomationIdProperty,$AutomationId)
  $Element.FindFirst('Descendants',$c)
}

function Find-ByName($Element,[string]$Name){
  $c=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::NameProperty,$Name)
  $Element.FindFirst('Descendants',$c)
}

function Invoke-Element($Element){
  $p=$null
  if($Element.TryGetCurrentPattern([Windows.Automation.InvokePattern]::Pattern,[ref]$p)){ $p.Invoke(); return 'invoke' }
  if($Element.TryGetCurrentPattern([Windows.Automation.SelectionItemPattern]::Pattern,[ref]$p)){ $p.Select(); return 'select' }
  if($Element.TryGetCurrentPattern([Windows.Automation.TogglePattern]::Pattern,[ref]$p)){ $p.Toggle(); return 'toggle' }
  if($Element.TryGetCurrentPattern([Windows.Automation.ExpandCollapsePattern]::Pattern,[ref]$p)){ $p.Expand(); return 'expand' }
  throw "sin patron para $($Element.Current.Name)"
}

function Get-Selected($Element){
  # Names of the selected SelectionItems under $Element.
  $out=@()
  foreach($e in $Element.FindAll('Descendants',(New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::IsSelectionItemPatternAvailableProperty,$true)))){
    try{ if($e.GetCurrentPattern([Windows.Automation.SelectionItemPattern]::Pattern).Current.IsSelected){ $out+=$e.Current.Name } }catch{}
  }
  $out
}

function Get-Value($Element){
  $p=$null; if($Element -and $Element.TryGetCurrentPattern([Windows.Automation.ValuePattern]::Pattern,[ref]$p)){ return $p.Current.Value }; return $null
}

if(-not ('EstadoDialogo' -as [type])){
Add-Type @"
using System; using System.Collections.Generic; using System.Runtime.InteropServices;
public static class EstadoDialogo {
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc f, IntPtr l);
  [DllImport("user32.dll")] static extern IntPtr GetWindow(IntPtr h, uint cmd);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
  // Visible top-level windows whose owner (GW_OWNER) is that window: its Win32 dialogs.
  public static long[] Owned(IntPtr owner){
    var o=new List<long>();
    EnumWindows((h,l)=>{ if(GetWindow(h,4)==owner && IsWindowVisible(h)){ o.Add(h.ToInt64()); } return true; }, IntPtr.Zero);
    return o.ToArray();
  }
}
"@
}

function Get-DialogosDeVentana([long]$Hwnd){
  # The dialogs over one window, as UIA elements: the Win32 dialogs it owns, and the dialogs drawn INSIDE it (a XAML
  # ContentDialog: Paint's «Cambiar de tamano y sesgar», Windows Terminal's «cerrar todas las pestanas»), which leave
  # the window enabled, so ModalOf never saw them (pasada r9: one sat in Paint over t-file-3, t-file-4, t-menu-4 and
  # t-long-3; another in a Terminal over v3-46..v3-53). In-window: a descendant of type Window that is modal or whose
  # class is a dialog's.
  $h=[IntPtr]$Hwnd
  if($Hwnd -eq 0 -or -not [EstadoW32]::IsWindow($h)){ return }
  foreach($d in [EstadoDialogo]::Owned($h)){ try{ [Windows.Automation.AutomationElement]::FromHandle([IntPtr]$d) }catch{} }
  try{
    $e=[Windows.Automation.AutomationElement]::FromHandle($h)
    $c=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::Window)
    foreach($d in @($e.FindAll('Descendants',$c))){
      $p=$null; $modal=$false
      try{ if($d.TryGetCurrentPattern([Windows.Automation.WindowPattern]::Pattern,[ref]$p)){ $modal=$p.Current.IsModal } }catch{}
      if($modal -or @('ContentDialog','#32770') -contains [string]$d.Current.ClassName){ $d }
    }
  }catch{}
}

function Close-DialogosDeVentana([long]$Hwnd,[string]$Modo){
  # Answers the dialogs over one window the caller already decided is the harness's, pressing ONE button through UIA
  # (no keys, no mouse) chosen by Get-DecisionBotonDialogo (decisiones_comun.ps1): 'cancelar' (a dialog left open
  # over it), 'confirmar' (the close confirmation its own close raised), 'sin_guardar' (its save prompt). A dialog with
  # no such button is left as it is. Returns one line per dialog.
  if(-not (Get-Command Get-DecisionBotonDialogo -ErrorAction SilentlyContinue)){ . (Join-Path $PSScriptRoot 'decisiones_comun.ps1') }
  $bc=New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::Button)
  foreach($d in @(Get-DialogosDeVentana $Hwnd)){
    $t=''; try{ $t=[string]$d.Current.Name }catch{}
    $botones=@(try{ @($d.FindAll('Descendants',$bc)) }catch{ @() })
    $nombre=Get-DecisionBotonDialogo @($botones | ForEach-Object { try{ [string]$_.Current.Name }catch{ '' } }) $Modo
    if(-not $nombre){ "dialogo:$($t):sin_boton_$Modo"; continue }
    $b=@($botones | Where-Object { try{ [string]$_.Current.Name -ceq $nombre }catch{ $false } })[0]
    $p=$null
    try{ if($b.TryGetCurrentPattern([Windows.Automation.InvokePattern]::Pattern,[ref]$p)){ $p.Invoke(); "dialogo:$($t):$($nombre)" }else{ "dialogo:$($t):sin_invoke" } }catch{ "dialogo:$($t):fallo" }
    Start-Sleep -Milliseconds 400
  }
}

function Close-WindowExact($Element,[switch]$SinGuardar,[switch]$SinConfirmar){
  # Normal close (WindowPattern) of one exact window; refuses VS Code, Opera and titles under 4 characters.
  # A window still there 1.5 s later is checked for the close confirmation its own close raised (pasada r9: a Windows
  # Terminal with several tabs left «cerrar todas las pestanas» over v3-46..v3-53): it is confirmed through UIA on
  # that same window, never left up. A save prompt is no confirmation: it stays, unless -SinGuardar (a caller that
  # proved the window the harness's: its test document is discarded). -SinConfirmar: a window that is not the
  # harness's own (Outlook's reminders, an account prompt): whatever dialog its close raised is CANCELLED, never
  # confirmed (Get-DecisionModoTrasCerrar).
  $n=$Element.Current.Name
  if([string]::IsNullOrWhiteSpace($n) -or $n.Length -lt 4){ throw "cerrar: titulo de menos de 4 caracteres" }
  if($n -like '*Visual Studio Code*' -or $n -like '*Opera*'){ throw "cerrar: nunca $n" }
  $h=[long]0; try{ $h=[long]$Element.Current.NativeWindowHandle }catch{}
  $Element.GetCurrentPattern([Windows.Automation.WindowPattern]::Pattern).Close()
  if($h -eq 0){ return }
  for($i=0;$i -lt 6 -and [EstadoW32]::IsWindow([IntPtr]$h);$i++){ Start-Sleep -Milliseconds 250 }
  if(-not [EstadoW32]::IsWindow([IntPtr]$h)){ return }
  if(-not (Get-Command Get-DecisionModoTrasCerrar -ErrorAction SilentlyContinue)){ . (Join-Path $PSScriptRoot 'decisiones_comun.ps1') }
  [void]@(Close-DialogosDeVentana $h (Get-DecisionModoTrasCerrar ([bool]$SinGuardar) ([bool]$SinConfirmar)))
  for($i=0;$i -lt 12 -and [EstadoW32]::IsWindow([IntPtr]$h);$i++){ Start-Sleep -Milliseconds 250 }
}

# Harness-owned windows/processes, so later runs only ever close what the harness opened.
$global:EstadoPropiosPath=Join-Path $env:LOCALAPPDATA 'BAXY\cu-estado\propios.jsonl'
function Get-Propios(){
  # Items @{ tipo; pid; hwnd; desde }, one per line of JSON (PowerShell 5.1 mangles nested arrays in ConvertTo-Json).
  $out=New-Object Collections.ArrayList
  if(Test-Path $global:EstadoPropiosPath){
    foreach($l in [IO.File]::ReadAllLines($global:EstadoPropiosPath)){ if($l.Trim()){ try{ [void]$out.Add(($l | ConvertFrom-Json)) }catch{} } }
  }
  # Items one by one (a comma-wrapped array piped into Where-Object is ONE object: with two or more items, $_.hwnd
  # became an array). Callers collect with @(Get-Propios).
  $out.ToArray()
}
function Set-Propios($Items){
  $d=Split-Path $global:EstadoPropiosPath; if(-not (Test-Path $d)){ New-Item -ItemType Directory -Force $d | Out-Null }
  # App items (tipo 'app', apps_comun.ps1) also carry: proceso (process name), nombre (Start menu name) and nuevo (the
  # process did not exist before the harness launched it: only then may it be stopped by PID).
  $lines=@(foreach($i in @($Items)){ if($i){
    $o=[ordered]@{ tipo=[string]$i.tipo; pid=[int]$i.pid; hwnd=[long]$i.hwnd; desde=[string]$i.desde }
    foreach($k in 'proceso','nombre','nuevo'){ if($i.PSObject.Properties[$k]){ $o[$k]=$i.$k } }
    [pscustomobject]$o | ConvertTo-Json -Compress
  } })
  [IO.File]::WriteAllText($global:EstadoPropiosPath,(($lines -join "`n")+"`n"),(New-Object Text.UTF8Encoding $false))
}

function Get-WindowBitmap([IntPtr]$Hwnd){
  # The window's own pixels through PrintWindow(PW_RENDERFULLCONTENT): works behind other windows, never for a minimized one.
  $r=New-Object EstadoW32+RECT; [void][EstadoW32]::GetWindowRect($Hwnd,[ref]$r)
  $w=$r.Right-$r.Left; $h=$r.Bottom-$r.Top
  if($w -le 0 -or $h -le 0){ return $null }
  $bmp=New-Object Drawing.Bitmap $w,$h
  $g=[Drawing.Graphics]::FromImage($bmp); $hdc=$g.GetHdc()
  $ok=[EstadoW32]::PrintWindow($Hwnd,$hdc,2)
  $g.ReleaseHdc($hdc); $g.Dispose()
  if(-not $ok){ $bmp.Dispose(); return $null }
  $bmp
}

$global:EstadoOcrReady=$false
function Initialize-Ocr(){
  if($global:EstadoOcrReady){ return }
  Add-Type -AssemblyName System.Runtime.WindowsRuntime
  [void][Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime]
  [void][Windows.Graphics.Imaging.BitmapDecoder,Windows.Foundation,ContentType=WindowsRuntime]
  [void][Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime]
  $global:EstadoAsTask=([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
  $global:EstadoOcrReady=$true
}
function Wait-WinRt($Op,[Type]$ResultType){ $task=$global:EstadoAsTask.MakeGenericMethod($ResultType).Invoke($null,@($Op)); [void]$task.Wait(-1); $task.Result }

function Read-BitmapText($Bitmap){
  # Local Windows OCR (no network). Returns lines: @{ text; x; y; w; h } in bitmap pixels.
  Initialize-Ocr
  $tmp=Join-Path $env:TEMP ("baxy-estado-ocr-{0}.png" -f [guid]::NewGuid().ToString('N'))
  $Bitmap.Save($tmp,[Drawing.Imaging.ImageFormat]::Png)
  try{
    $file=Wait-WinRt ([Windows.Storage.StorageFile]::GetFileFromPathAsync($tmp)) ([Windows.Storage.StorageFile])
    $stream=Wait-WinRt ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
    $dec=Wait-WinRt ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $sb=Wait-WinRt ($dec.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $eng=[Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
    $res=Wait-WinRt ($eng.RecognizeAsync($sb)) ([Windows.Media.Ocr.OcrResult])
    $stream.Dispose()
    $lines=@()
    foreach($l in $res.Lines){
      $x1=1e9;$y1=1e9;$x2=0;$y2=0
      foreach($wd in $l.Words){ $b=$wd.BoundingRect; $x1=[Math]::Min($x1,$b.X); $y1=[Math]::Min($y1,$b.Y); $x2=[Math]::Max($x2,$b.X+$b.Width); $y2=[Math]::Max($y2,$b.Y+$b.Height) }
      $lines+=[pscustomobject]@{ text=$l.Text; x=[int]$x1; y=[int]$y1; w=[int]($x2-$x1); h=[int]($y2-$y1) }
    }
    ,$lines
  } finally { Remove-Item $tmp -ErrorAction SilentlyContinue }
}
