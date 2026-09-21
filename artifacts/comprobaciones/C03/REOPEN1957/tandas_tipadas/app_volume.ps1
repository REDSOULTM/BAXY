# Root helper (Fase 8, D18): read or set one application's own audio sessions on the default output, and read the
# SMTC (system media transport) session state. Mirrors WindowsCoreAudioPlatform (IAudioSessionManager2 → sessions
# by process name → ISimpleAudioVolume); never touches the endpoint's master volume.
# usage: app_volume.ps1 get <process>          → {process, sessions:[{pid,state,level,muted}]}
#        app_volume.ps1 set <process> <0-100>  → sets every session of that process, then reads back
#        app_volume.ps1 smtc                   → {sessions:[{app,status,title,artist}]}
param([Parameter(Mandatory)][string]$Mode, [string]$Process = 'Spotify', [int]$Level = -1)
$code = @'
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Runtime.InteropServices;
[Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IMMDevice { int Activate(ref Guid id, int cls, IntPtr p, [MarshalAs(UnmanagedType.IUnknown)] out object o); }
[Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IMMDeviceEnumerator { int NotImpl1(); int GetDefaultAudioEndpoint(int flow, int role, out IMMDevice d); }
[ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")] public class MMDeviceEnumeratorComObject { }
[Guid("77AA99A0-1BD6-484F-8BC7-2C654C9A9B6F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IAudioSessionManager2 {
  int GetAudioSessionControl(ref Guid g, uint f, out IntPtr c); int GetSimpleAudioVolume(ref Guid g, uint f, out IntPtr v);
  int GetSessionEnumerator(out IAudioSessionEnumerator e);
}
[Guid("E2F5BB11-0570-40CA-ACDD-3AA01277DEE8"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IAudioSessionEnumerator { int GetCount(out int n); int GetSession(int i, out IAudioSessionControl2 s); }
[Guid("BFB7FF88-7239-4FC9-8FA2-07C950BE9C6D"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IAudioSessionControl2 {
  int GetState(out int s); int GetDisplayName([MarshalAs(UnmanagedType.LPWStr)] out string n); int SetDisplayName(IntPtr n, ref Guid c);
  int GetIconPath([MarshalAs(UnmanagedType.LPWStr)] out string p); int SetIconPath(IntPtr p, ref Guid c); int GetGroupingParam(out Guid g);
  int SetGroupingParam(ref Guid g, ref Guid c); int RegisterAudioSessionNotification(IntPtr n); int UnregisterAudioSessionNotification(IntPtr n);
  int GetSessionIdentifier([MarshalAs(UnmanagedType.LPWStr)] out string i); int GetSessionInstanceIdentifier([MarshalAs(UnmanagedType.LPWStr)] out string i);
  int GetProcessId(out uint p); int IsSystemSoundsSession(); int SetDuckingPreference(bool o);
}
[Guid("87CE5498-68D6-44E5-9215-6DA47EF883D8"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface ISimpleAudioVolume {
  int SetMasterVolume(float l, ref Guid c); int GetMasterVolume(out float l); int SetMute(bool m, ref Guid c); int GetMute(out bool m);
}
public class AppSession { public uint Pid; public int State; public int Level; public bool Muted; public object Volume; }
public static class AppVol {
  static IAudioSessionEnumerator Sessions() {
    var e = (IMMDeviceEnumerator)(new MMDeviceEnumeratorComObject());
    IMMDevice d; e.GetDefaultAudioEndpoint(0, 1, out d);
    Guid iid = typeof(IAudioSessionManager2).GUID; object o; d.Activate(ref iid, 23, IntPtr.Zero, out o);
    IAudioSessionEnumerator en; ((IAudioSessionManager2)o).GetSessionEnumerator(out en); return en;
  }
  public static List<AppSession> Find(string process) {
    var found = new List<AppSession>(); var en = Sessions(); int n; en.GetCount(out n);
    for (int i = 0; i < n; i++) {
      IAudioSessionControl2 c; if (en.GetSession(i, out c) < 0 || c == null) continue;
      if (c.IsSystemSoundsSession() == 0) continue;
      uint pid; c.GetProcessId(out pid); if (pid == 0) continue;
      string name; try { name = Process.GetProcessById((int)pid).ProcessName; } catch { continue; }
      if (!string.Equals(name, process, StringComparison.OrdinalIgnoreCase)) continue;
      int state; c.GetState(out state);
      var v = (ISimpleAudioVolume)c; float l; v.GetMasterVolume(out l); bool m; v.GetMute(out m);
      found.Add(new AppSession { Pid = pid, State = state, Level = (int)Math.Round(l * 100), Muted = m, Volume = v });
    }
    return found;
  }
  public static void Set(AppSession s, int level) { Guid g = Guid.NewGuid(); ((ISimpleAudioVolume)s.Volume).SetMasterVolume(level / 100f, ref g); }
}
'@
if (-not ([System.Management.Automation.PSTypeName]'AppVol').Type) { Add-Type -TypeDefinition $code }
function Dump($process) {
  $rows = @(); foreach ($s in [AppVol]::Find($process)) { $rows += @{ pid = $s.Pid; state = @('inactive','active','expired')[$s.State]; level = $s.Level; muted = $s.Muted } }
  @{ process = $process; sessions = $rows } | ConvertTo-Json -Compress -Depth 4
}
switch ($Mode) {
  'get' { Dump $Process }
  'set' {
    if ($Level -lt 0 -or $Level -gt 100) { throw 'level must be 0-100' }
    $sessions = [AppVol]::Find($Process)
    foreach ($s in $sessions) { [AppVol]::Set($s, $Level) }
    Dump $Process
  }
  'smtc' {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $null = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager, Windows.Media.Control, ContentType = WindowsRuntime]
    $asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
    function Await($op, $type) { $t = $asTask.MakeGenericMethod($type).Invoke($null, @($op)); $t.Wait(-1) | Out-Null; $t.Result }
    $mgr = Await ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]::RequestAsync()) ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager])
    $rows = @()
    foreach ($s in $mgr.GetSessions()) {
      $info = $s.GetPlaybackInfo(); $props = $null
      try { $props = Await ($s.TryGetMediaPropertiesAsync()) ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionMediaProperties]) } catch {}
      $rows += @{ app = $s.SourceAppUserModelId; status = [string]$info.PlaybackStatus; title = $(if ($props) { $props.Title } else { $null }); artist = $(if ($props) { $props.Artist } else { $null }) }
    }
    @{ sessions = $rows } | ConvertTo-Json -Compress -Depth 4
  }
  { $_ -in @('smtc-play', 'smtc-pause') } {
    # $Process = a fragment of the SMTC source app id (Spotify → «SpotifyAB.SpotifyMusic…» or «Spotify.exe»).
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $null = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager, Windows.Media.Control, ContentType = WindowsRuntime]
    $asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
    function Await($op, $type) { $t = $asTask.MakeGenericMethod($type).Invoke($null, @($op)); $t.Wait(-1) | Out-Null; $t.Result }
    $mgr = Await ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]::RequestAsync()) ([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager])
    $target = $mgr.GetSessions() | Where-Object { $_.SourceAppUserModelId -like "*$Process*" } | Select-Object -First 1
    if ($null -eq $target) { @{ ok = $false; error = 'no smtc session for ' + $Process } | ConvertTo-Json -Compress; break }
    $result = $(if ($Mode -eq 'smtc-play') { Await ($target.TryPlayAsync()) ([bool]) } else { Await ($target.TryPauseAsync()) ([bool]) })
    Start-Sleep -Milliseconds 500
    @{ ok = [bool]$result; app = $target.SourceAppUserModelId; status = [string]$target.GetPlaybackInfo().PlaybackStatus } | ConvertTo-Json -Compress
  }
  default { throw "unknown mode $Mode" }
}
