# Machine state the semantic replay presets and restores around a conversation with real effects.
# usage: semantic_replay_state.ps1 volume|mic get|set <0-100>|mute <0|1>
#        semantic_replay_state.ps1 brightness get|set <0-100>
param([string]$Kind = 'volume', [string]$Mode = 'get', [int]$Value = -1)
$ErrorActionPreference = 'Stop'

if ($Kind -eq 'brightness') {
    function Read-Levels { @(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness -ErrorAction SilentlyContinue | ForEach-Object { [int]$_.CurrentBrightness }) }
    if ($Mode -eq 'set') {
        foreach ($m in @(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods -ErrorAction SilentlyContinue)) {
            Invoke-CimMethod -InputObject $m -MethodName WmiSetBrightness -Arguments @{ Timeout = 1; Brightness = [byte]$Value } | Out-Null
        }
        Start-Sleep -Milliseconds 300
    }
    [pscustomobject]@{ levels = @(Read-Levels) } | ConvertTo-Json -Compress
    exit 0
}

$code = @'
using System;
using System.Runtime.InteropServices;
[Guid("5CDF2C82-841E-4546-9722-0CF74078229A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IAudioEndpointVolume {
  int RegisterControlChangeNotify(IntPtr p); int UnregisterControlChangeNotify(IntPtr p); int GetChannelCount(out int n);
  int SetMasterVolumeLevel(float l, ref Guid c); int SetMasterVolumeLevelScalar(float l, ref Guid c);
  int GetMasterVolumeLevel(out float l); int GetMasterVolumeLevelScalar(out float l);
  int SetChannelVolumeLevel(uint i, float l, ref Guid c); int SetChannelVolumeLevelScalar(uint i, float l, ref Guid c);
  int GetChannelVolumeLevel(uint i, out float l); int GetChannelVolumeLevelScalar(uint i, out float l);
  int SetMute([MarshalAs(UnmanagedType.Bool)] bool m, ref Guid c); int GetMute(out bool m);
}
[Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IMMDevice { int Activate(ref Guid id, int cls, IntPtr p, [MarshalAs(UnmanagedType.IUnknown)] out object o); }
[Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IMMDeviceEnumerator { int NotImpl1(); int GetDefaultAudioEndpoint(int flow, int role, out IMMDevice d); }
[ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")] public class MMDeviceEnumeratorComObject { }
public static class SemanticReplayEndpoint {
  static IAudioEndpointVolume Get(int flow) {
    var e = (IMMDeviceEnumerator)(new MMDeviceEnumeratorComObject());
    IMMDevice d; e.GetDefaultAudioEndpoint(flow, 1, out d);
    Guid iid = typeof(IAudioEndpointVolume).GUID; object o; d.Activate(ref iid, 23, IntPtr.Zero, out o);
    return (IAudioEndpointVolume)o;
  }
  public static int GetLevel(int flow) { float l; Get(flow).GetMasterVolumeLevelScalar(out l); return (int)Math.Round(l * 100); }
  public static bool GetMute(int flow) { bool m; Get(flow).GetMute(out m); return m; }
  public static void SetLevel(int flow, int level) { Guid g = Guid.Empty; Get(flow).SetMasterVolumeLevelScalar(level / 100f, ref g); }
  public static void SetMute(int flow, bool mute) { Guid g = Guid.Empty; Get(flow).SetMute(mute, ref g); }
}
'@
if (-not ([System.Management.Automation.PSTypeName]'SemanticReplayEndpoint').Type) { Add-Type -TypeDefinition $code }
$flow = if ($Kind -eq 'mic') { 1 } else { 0 }
switch ($Mode) {
    'set'  { [SemanticReplayEndpoint]::SetLevel($flow, $Value) }
    'mute' { [SemanticReplayEndpoint]::SetMute($flow, $Value -ne 0) }
}
[pscustomobject]@{ level = [SemanticReplayEndpoint]::GetLevel($flow); muted = [SemanticReplayEndpoint]::GetMute($flow) } | ConvertTo-Json -Compress
