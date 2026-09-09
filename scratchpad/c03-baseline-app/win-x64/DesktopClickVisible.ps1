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
  [DllImport("user32.dll")] private static extern bool EnumChildWindows(IntPtr parent, EnumProc callback, IntPtr value);
  [DllImport("user32.dll")] private static extern int GetWindowText(IntPtr hwnd, StringBuilder text, int count);
  [DllImport("user32.dll")] private static extern int GetClassName(IntPtr hwnd, StringBuilder text, int count);
  [DllImport("user32.dll")] public static extern bool IsWindow(IntPtr hwnd);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hwnd);
  [DllImport("user32.dll")] public static extern bool IsWindowEnabled(IntPtr hwnd);
  [DllImport("user32.dll")] private static extern IntPtr SendMessage(IntPtr hwnd, uint message, IntPtr wParam, IntPtr lParam);
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
  public static string Text(IntPtr hwnd) { var text=new StringBuilder(512);GetWindowText(hwnd,text,text.Capacity);return text.ToString(); }
}
'@
function Emit([bool]$ok,[bool]$effect,[string]$error,[string]$name,[string]$identity,[bool]$absentOrDisabled){
  [pscustomobject]@{version=1;ok=$ok;effectObserved=$effect;error=$error;name=$name;controlIdentity=$identity;absentOrDisabled=$absentOrDisabled;authority='windows_uia_or_win32_button_postread'}|ConvertTo-Json -Compress
}
try {
  $label=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($LabelBase64)).Trim()
  $aliases=@($label)
  if($label -match '^(?i:accept|aceptar)$'){$aliases=@('Accept','Aceptar')}
  elseif($label -match '^(?i:ok|okay)$'){$aliases=@('OK','Okay','Aceptar')}
  elseif($label -match '^(?i:validate|valider)$'){$aliases=@('Validate','Valider')}
  $hwnd=[BaxyVisibleClickNative]::GetForegroundWindow()
  if($hwnd -eq [IntPtr]::Zero){Emit $false $false 'active_window_not_found' '' '' $false;exit 2}
  $root=[System.Windows.Automation.AutomationElement]::FromHandle($hwnd)
  $condition=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty,[System.Windows.Automation.ControlType]::Button)
  $all=$root.FindAll([System.Windows.Automation.TreeScope]::Descendants,$condition)
  $matches=@()
  foreach($item in $all){
    try {
      $name=$item.Current.Name
      if($item.Current.IsEnabled -and -not $item.Current.IsOffscreen -and @($aliases|Where-Object{[string]::Equals($_,$name,[StringComparison]::OrdinalIgnoreCase)}).Count -gt 0){$matches+=@($item)}
    } catch [System.Windows.Automation.ElementNotAvailableException] {}
  }
  if($matches.Count -eq 0){
    $root=[System.Windows.Automation.AutomationElement]::RootElement
    $all=$root.FindAll([System.Windows.Automation.TreeScope]::Descendants,$condition)
    foreach($item in $all){
      try {
        $name=$item.Current.Name
        if($item.Current.IsEnabled -and -not $item.Current.IsOffscreen -and @($aliases|Where-Object{[string]::Equals($_,$name,[StringComparison]::OrdinalIgnoreCase)}).Count -gt 0){$matches+=@($item)}
      } catch [System.Windows.Automation.ElementNotAvailableException] {}
    }
  }
  if($matches.Count -eq 0){
    $native=@([BaxyVisibleClickNative]::FindVisibleButtons([string[]]$aliases))
    if($native.Count -gt 1){Emit $false $false 'visible_button_ambiguous' '' '' $false;exit 4}
    if($native.Count -eq 1){
      $nativeButton=$native[0];$name=[BaxyVisibleClickNative]::Text($nativeButton);$identity=('hwnd.'+$nativeButton.ToInt64())
      [BaxyVisibleClickNative]::Click($nativeButton)
      $absentOrDisabled=$false
      for($i=0;$i -lt 20;$i++){Start-Sleep -Milliseconds 100;if(-not [BaxyVisibleClickNative]::IsWindow($nativeButton) -or -not [BaxyVisibleClickNative]::IsWindowVisible($nativeButton) -or -not [BaxyVisibleClickNative]::IsWindowEnabled($nativeButton)){$absentOrDisabled=$true;break}}
      if(-not $absentOrDisabled){Emit $false $true 'visible_button_postread_unchanged' $name $identity $false;exit 6}
      Emit $true $true '' $name $identity $true;exit 0
    }
    Emit $false $false 'visible_button_not_found' $root.Current.Name '' $false;exit 3
  }
  if($matches.Count -ne 1){Emit $false $false 'visible_button_ambiguous' '' '' $false;exit 4}
  $button=$matches[0];$name=$button.Current.Name;$identity=($button.GetRuntimeId() -join '.')
  $pattern=$null
  if(-not $button.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern,[ref]$pattern)){Emit $false $false 'visible_button_not_invokable' $name $identity $false;exit 5}
  ([System.Windows.Automation.InvokePattern]$pattern).Invoke()
  $absentOrDisabled=$false
  for($i=0;$i -lt 20;$i++){
    Start-Sleep -Milliseconds 100
    try { if(-not $button.Current.IsEnabled -or $button.Current.IsOffscreen){$absentOrDisabled=$true;break} }
    catch [System.Windows.Automation.ElementNotAvailableException] {$absentOrDisabled=$true;break}
  }
  if(-not $absentOrDisabled){Emit $false $true 'visible_button_postread_unchanged' $name $identity $false;exit 6}
  Emit $true $true '' $name $identity $true
} catch { Emit $false $false 'visible_button_uia_failed' '' '' $false;exit 7 }
