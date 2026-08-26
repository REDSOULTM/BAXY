param([Parameter(Mandatory=$true)][string]$LabelBase64)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
public static class BaxyVisibleClickNative {
  private delegate bool EnumProc(IntPtr hwnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] private static extern bool EnumWindows(EnumProc callback, IntPtr value);
  [DllImport("user32.dll")] private static extern bool EnumChildWindows(IntPtr parent, EnumProc callback, IntPtr lParam);
  [DllImport("user32.dll")] private static extern int GetWindowText(IntPtr hwnd, StringBuilder text, int count);
  [DllImport("user32.dll")] private static extern int GetClassName(IntPtr hwnd, StringBuilder text, int count);
  [DllImport("user32.dll")] public static extern bool IsWindow(IntPtr hwnd);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hwnd);
  [DllImport("user32.dll")] public static extern bool IsWindowEnabled(IntPtr hwnd);
  [DllImport("user32.dll")] private static extern IntPtr SendMessage(IntPtr hwnd, uint message, IntPtr wParam, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint flags, uint dx, uint dy, uint data, UIntPtr extra);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint procId);
  public static uint ProcessIdOf(IntPtr hwnd) { uint procId; GetWindowThreadProcessId(hwnd, out procId); return procId; }
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hwnd, out RECT rect);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
  public static IntPtr LargestVisible(IntPtr hwnd) {
    uint procId; GetWindowThreadProcessId(hwnd, out procId);
    IntPtr best=hwnd; long bestArea=0;
    EnumWindows((top,unused)=>{
      if(!IsWindowVisible(top)) return true;
      uint owner; GetWindowThreadProcessId(top, out owner);
      if(owner!=procId) return true;
      RECT r; if(!GetWindowRect(top,out r)) return true;
      long area=(long)Math.Max(0,r.Right-r.Left)*Math.Max(0,r.Bottom-r.Top);
      if(area>bestArea){bestArea=area;best=top;}
      return true;
    },IntPtr.Zero);
    return best;
  }
  public static IntPtr[] TopVisibleWindows() {
    var list=new List<IntPtr>();
    EnumWindows((top,unused)=>{ if(IsWindowVisible(top)) list.Add(top); return true; },IntPtr.Zero);
    return list.ToArray();
  }
  public static IntPtr[] FindVisibleButtons(string[] labels) {
    var matches=new List<IntPtr>();
    EnumWindows((top,unused)=>{
      if(!IsWindowVisible(top)) return true;
      var topMatches=new List<IntPtr>();
      EnumChildWindows(top,(child,unusedChild)=>{
        var cls=new StringBuilder(128);GetClassName(child,cls,cls.Capacity);
        if(cls.ToString().IndexOf("BUTTON",StringComparison.OrdinalIgnoreCase)<0
            || !IsWindowVisible(child) || !IsWindowEnabled(child)) return true;
        var name=new StringBuilder(512);GetWindowText(child,name,name.Capacity);
        foreach(string label in labels) if(string.Equals(label,name.ToString(),StringComparison.OrdinalIgnoreCase)) {topMatches.Add(child);break;}
        return true;
      },IntPtr.Zero);
      if(topMatches.Count>0){matches.AddRange(topMatches);return false;}
      return true;
    },IntPtr.Zero);
    return matches.ToArray();
  }
  public static void Click(IntPtr hwnd) { SendMessage(hwnd,0x00F5,IntPtr.Zero,IntPtr.Zero); }
  public static void ClickPoint(int x, int y) { SetCursorPos(x,y); mouse_event(0x0002,0,0,0,UIntPtr.Zero); mouse_event(0x0004,0,0,0,UIntPtr.Zero); }
  public static string Text(IntPtr hwnd) { var text=new StringBuilder(512);GetWindowText(hwnd,text,text.Capacity);return text.ToString(); }
}
'@
function Emit([bool]$ok,[bool]$effect,[string]$error,[string]$name,[string]$identity,[bool]$absentOrDisabled,[bool]$selected,[bool]$toggled,[string]$stage){
  [pscustomobject]@{version=1;ok=$ok;effectObserved=$effect;error=$error;name=$name;controlIdentity=$identity;absentOrDisabled=$absentOrDisabled;selected=$selected;toggled=$toggled;surfaceChanged=$false;cascadeStage=$stage;authority='windows_uia_or_win32_button_postread'}|ConvertTo-Json -Compress
}
function Invoke-NamedControl($el){
  $pattern=$null
  if($el.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern,[ref]$pattern)){
    ([System.Windows.Automation.InvokePattern]$pattern).Invoke()
    return 'invoke'
  }
  if($el.TryGetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern,[ref]$pattern)){
    ([System.Windows.Automation.SelectionItemPattern]$pattern).Select()
    return 'select'
  }
  if($el.TryGetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern,[ref]$pattern)){
    ([System.Windows.Automation.TogglePattern]$pattern).Toggle()
    return 'toggle'
  }
  $point=$el.GetClickablePoint()
  [BaxyVisibleClickNative]::ClickPoint([int]$point.X,[int]$point.Y)
  return 'click'
}
function Test-Selected($el){
  try {
    $pattern=$null
    if($el.TryGetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern,[ref]$pattern)){
      return ([System.Windows.Automation.SelectionItemPattern]$pattern).Current.IsSelected
    }
  } catch [System.Windows.Automation.ElementNotAvailableException] {}
  return $false
}
function Get-ToggleState($el){
  try {
    $pattern=$null
    if($el.TryGetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern,[ref]$pattern)){
      return ([System.Windows.Automation.TogglePattern]$pattern).Current.ToggleState
    }
  } catch [System.Windows.Automation.ElementNotAvailableException] {}
  return $null
}
function Get-WindowProcessName([IntPtr]$hwnd){
  $procId=[BaxyVisibleClickNative]::ProcessIdOf($hwnd)
  if($procId -le 0){ return '' }
  try { return (Get-Process -Id $procId -ErrorAction Stop).ProcessName } catch { return '' }
}
function Test-ReplayHostProcess([string]$name){
  return $name -match '^(?i:testhost|Baxy|baxy-core)$'
}
function Get-ControlIdentity($el){
  try { return ($el.GetRuntimeId() -join '.') } catch { return '' }
}
function Find-NamedControls($root,[string[]]$aliases){
  $matches=@()
  $seen=@{}
  if($null -eq $root){ return $matches }
  foreach($alias in $aliases){
    if([string]::IsNullOrWhiteSpace($alias)){ continue }
    $nameCond=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty,$alias)
    $enabledCond=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::IsEnabledProperty,$true)
    $condition=New-Object System.Windows.Automation.AndCondition($nameCond,$enabledCond)
    try {
      $hits=$root.FindAll([System.Windows.Automation.TreeScope]::Descendants,$condition)
    } catch { continue }
    foreach($item in $hits){
      try {
        if($item.Current.IsOffscreen){ continue }
        $identity=Get-ControlIdentity $item
        if($identity -and $seen.ContainsKey($identity)){ continue }
        if($identity){ $seen[$identity]=$true }
        $matches+=@($item)
      } catch [System.Windows.Automation.ElementNotAvailableException] {}
    }
  }
  return $matches
}
function Select-PreferredNamedControl($items){
  if($null -eq $items -or $items.Count -le 1){ return $items }
  $toggles=@()
  foreach($el in $items){
    try {
      $pattern=$null
      if($el.TryGetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern,[ref]$pattern)){
        $toggles+=@($el)
      }
    } catch [System.Windows.Automation.ElementNotAvailableException] {}
  }
  if($toggles.Count -eq 1){ return $toggles }
  return $items
}
function Find-NamedControlsAcrossWindows([string[]]$aliases,[IntPtr]$skip){
  $found=@()
  $scanned=0
  foreach($top in [BaxyVisibleClickNative]::TopVisibleWindows()){
    if($top -eq $skip){ continue }
    $proc=Get-WindowProcessName $top
    if(Test-ReplayHostProcess $proc){ continue }
    $scanned++
    if($scanned -gt 16){ break }
    try {
      $root=[System.Windows.Automation.AutomationElement]::FromHandle($top)
      if($null -eq $root){ continue }
      $hits=@(Find-NamedControls $root $aliases)
      if($hits.Count -gt 0){ $found += $hits; if($found.Count -gt 1){ break } }
    } catch {}
  }
  return $found
}
try {
  $label=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($LabelBase64)).Trim()
  if([string]::IsNullOrWhiteSpace($label)){ Emit $false $false 'visible_click_argument_invalid' '' '' $false $false $false 'uia'; exit 2 }
  $aliases=@($label)
  if($label -match '^(?i:accept|aceptar)$'){$aliases=@('Accept','Aceptar')}
  elseif($label -match '^(?i:ok|okay)$'){$aliases=@('OK','Okay','Aceptar')}
  elseif($label -match '^(?i:validate|valider)$'){$aliases=@('Validate','Valider')}
  elseif($label -match '^(?i:biblioteca|library)$'){$aliases=@('Biblioteca','Library')}
  elseif($label -match '^(?i:configuracion|settings)$'){$aliases=@('Configuracion','Settings')}
  elseif($label -match '^(?i:silenciar|mute)$'){$aliases=@('Silenciar','Mute','Deafen')}
  elseif($label -match '^(?i:enviar|send)$'){$aliases=@('Enviar','Send')}
  $hwnd=[BaxyVisibleClickNative]::GetForegroundWindow()
  if($hwnd -eq [IntPtr]::Zero){Emit $false $false 'active_window_not_found' '' '' $false $false $false 'uia';exit 2}
  $hwnd=[BaxyVisibleClickNative]::LargestVisible($hwnd)
  $hostForeground=Test-ReplayHostProcess (Get-WindowProcessName $hwnd)
  $matches=@()
  $root=$null
  if(-not $hostForeground){
    $root=[System.Windows.Automation.AutomationElement]::FromHandle($hwnd)
    $matches=@(Find-NamedControls $root $aliases)
    if($matches.Count -eq 0){
      Start-Sleep -Milliseconds 400
      $root=[System.Windows.Automation.AutomationElement]::FromHandle($hwnd)
      $matches=@(Find-NamedControls $root $aliases)
    }
  }
  if($matches.Count -eq 0){
    $matches=@(Find-NamedControlsAcrossWindows $aliases $hwnd)
  }
  if($matches.Count -eq 0){
    $native=@([BaxyVisibleClickNative]::FindVisibleButtons([string[]]$aliases))
    if($native.Count -gt 1){Emit $false $false 'visible_button_ambiguous' '' '' $false $false $false 'uia';exit 4}
    if($native.Count -eq 1){
      $nativeButton=$native[0];$name=[BaxyVisibleClickNative]::Text($nativeButton);$identity=('hwnd.'+$nativeButton.ToInt64())
      [BaxyVisibleClickNative]::Click($nativeButton)
      $absentOrDisabled=$false
      for($i=0;$i -lt 20;$i++){Start-Sleep -Milliseconds 100;if(-not [BaxyVisibleClickNative]::IsWindow($nativeButton) -or -not [BaxyVisibleClickNative]::IsWindowVisible($nativeButton) -or -not [BaxyVisibleClickNative]::IsWindowEnabled($nativeButton)){$absentOrDisabled=$true;break}}
      if(-not $absentOrDisabled){Emit $false $true 'visible_button_postread_unchanged' $name $identity $false $false $false 'uia';exit 6}
      Emit $true $true '' $name $identity $true $false $false 'uia';exit 0
    }
    $rootName=''
    try { if($null -ne $root){ $rootName=$root.Current.Name } } catch {}
    Emit $false $false 'visible_button_not_found' $rootName '' $false $false $false 'uia';exit 3
  }
  $matches=@(Select-PreferredNamedControl $matches)
  if($matches.Count -ne 1){Emit $false $false 'visible_button_ambiguous' '' '' $false $false $false 'uia';exit 4}
  $button=$matches[0];$name=$button.Current.Name;$identity=Get-ControlIdentity $button
  $beforeToggle=Get-ToggleState $button
  try { Invoke-NamedControl $button | Out-Null }
  catch { Emit $false $false 'visible_button_not_invokable' $name $identity $false $false $false 'uia';exit 5 }
  $absentOrDisabled=$false
  $selected=$false
  $toggled=$false
  for($i=0;$i -lt 20;$i++){
    Start-Sleep -Milliseconds 100
    try {
      if(-not $button.Current.IsEnabled -or $button.Current.IsOffscreen){$absentOrDisabled=$true;break}
      if(Test-Selected $button){$selected=$true;break}
      $afterToggle=Get-ToggleState $button
      if($null -ne $beforeToggle -and $null -ne $afterToggle -and $afterToggle -ne $beforeToggle){$toggled=$true;break}
    }
    catch [System.Windows.Automation.ElementNotAvailableException] {$absentOrDisabled=$true;break}
  }
  if(-not $absentOrDisabled -and -not $selected -and -not $toggled){Emit $false $true 'visible_button_postread_unchanged' $name $identity $false $false $false 'uia';exit 6}
  Emit $true $true '' $name $identity $absentOrDisabled $selected $toggled 'uia'
} catch { Emit $false $false 'visible_button_uia_failed' '' '' $false $false $false 'uia';exit 7 }
