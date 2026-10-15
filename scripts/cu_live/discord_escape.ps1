# Presses Escape once on the Discord window (closes its settings overlay left by a test), only if Discord is in front.
Add-Type @'
using System; using System.Runtime.InteropServices; using System.Text;
public static class DE {
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
 [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte sc, uint fl, UIntPtr ex);
}
'@
$p = Get-Process Discord -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1
if(-not $p){ "no Discord window"; exit 1 }
[void][DE]::SetForegroundWindow($p.MainWindowHandle); Start-Sleep -Milliseconds 400
if([DE]::GetForegroundWindow() -ne $p.MainWindowHandle){ "Discord not in front; nothing sent"; exit 1 }
[DE]::keybd_event(0x1B,0,0,[UIntPtr]::Zero); [DE]::keybd_event(0x1B,0,2,[UIntPtr]::Zero)
"escape sent to $($p.MainWindowTitle)"
