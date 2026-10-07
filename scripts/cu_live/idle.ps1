# Seconds since the last keyboard/mouse input, fullscreen foreground flag, battery.
Add-Type @'
using System; using System.Runtime.InteropServices;
public static class BaxyIdle {
  [StructLayout(LayoutKind.Sequential)] struct LII { public uint cbSize; public uint dwTime; }
  [DllImport("user32.dll")] static extern bool GetLastInputInfo(ref LII p);
  [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L,T,R,B; }
  public static double Idle(){ var l=new LII(); l.cbSize=(uint)Marshal.SizeOf(l); GetLastInputInfo(ref l); return (Environment.TickCount - (int)l.dwTime)/1000.0; }
  public static bool Fullscreen(){ RECT r; var h=GetForegroundWindow(); if(h==IntPtr.Zero||!GetWindowRect(h,out r)) return false; var s=System.Windows.Forms.Screen.PrimaryScreen.Bounds; return r.L<=s.Left&&r.T<=s.Top&&r.R>=s.Right&&r.B>=s.Bottom; }
}
'@ -ReferencedAssemblies System.Windows.Forms,System.Drawing
$b = Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue | Select-Object -First 1
[pscustomobject]@{ idle=[math]::Round([BaxyIdle]::Idle(),1); fullscreen=[BaxyIdle]::Fullscreen(); battery=$b.EstimatedChargeRemaining; charging=($b.BatteryStatus -eq 2) } | ConvertTo-Json -Compress
