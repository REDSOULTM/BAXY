param(
  [int]$TargetHz = 165,
  [int]$MinHz = 120,
  [string]$LogPath = "$env:LOCALAPPDATA\RefreshRateFix\fix.log"
)

$ErrorActionPreference = "Stop"

$source = @"
using System;
using System.Runtime.InteropServices;

public static class DisplayRefreshRate {
  [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Ansi)]
  public struct DISPLAY_DEVICE {
    public int cb;
    [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)] public string DeviceName;
    [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 128)] public string DeviceString;
    public int StateFlags;
    [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 128)] public string DeviceID;
    [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 128)] public string DeviceKey;
  }

  [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Ansi)]
  public struct DEVMODE {
    [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)] public string dmDeviceName;
    public short dmSpecVersion;
    public short dmDriverVersion;
    public short dmSize;
    public short dmDriverExtra;
    public int dmFields;
    public int dmPositionX;
    public int dmPositionY;
    public int dmDisplayOrientation;
    public int dmDisplayFixedOutput;
    public short dmColor;
    public short dmDuplex;
    public short dmYResolution;
    public short dmTTOption;
    public short dmCollate;
    [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)] public string dmFormName;
    public short dmLogPixels;
    public int dmBitsPerPel;
    public int dmPelsWidth;
    public int dmPelsHeight;
    public int dmDisplayFlags;
    public int dmDisplayFrequency;
    public int dmICMMethod;
    public int dmICMIntent;
    public int dmMediaType;
    public int dmDitherType;
    public int dmReserved1;
    public int dmReserved2;
    public int dmPanningWidth;
    public int dmPanningHeight;
  }

  [DllImport("user32.dll", CharSet = CharSet.Ansi)]
  public static extern bool EnumDisplayDevices(string lpDevice, uint iDevNum, ref DISPLAY_DEVICE lpDisplayDevice, uint dwFlags);

  [DllImport("user32.dll", CharSet = CharSet.Ansi)]
  public static extern bool EnumDisplaySettings(string deviceName, int modeNum, ref DEVMODE devMode);

  [DllImport("user32.dll", CharSet = CharSet.Ansi)]
  public static extern int ChangeDisplaySettingsEx(string lpszDeviceName, ref DEVMODE lpDevMode, IntPtr hwnd, int dwflags, IntPtr lParam);
}
"@

Add-Type -TypeDefinition $source -ErrorAction SilentlyContinue

$ENUM_CURRENT_SETTINGS = -1
$DISPLAY_DEVICE_ATTACHED_TO_DESKTOP = 0x1
$DISPLAY_DEVICE_PRIMARY_DEVICE = 0x4
$CDS_UPDATEREGISTRY = 0x1
$DISP_CHANGE_SUCCESSFUL = 0
$DM_BITSPERPEL = 0x00040000
$DM_PELSWIDTH = 0x00080000
$DM_PELSHEIGHT = 0x00100000
$DM_DISPLAYFREQUENCY = 0x00400000

function Write-Log($message) {
  $dir = Split-Path -Parent $LogPath
  if ($dir -and !(Test-Path -LiteralPath $dir)) {
    New-Item -ItemType Directory -Path $dir | Out-Null
  }
  Add-Content -LiteralPath $LogPath -Value ("{0:s} {1}" -f (Get-Date), $message)
}

for ($i = 0; $true; $i++) {
  $display = New-Object DisplayRefreshRate+DISPLAY_DEVICE
  $display.cb = [Runtime.InteropServices.Marshal]::SizeOf($display)
  $nullDisplay = [System.Management.Automation.Language.NullString]::Value
  if (![DisplayRefreshRate]::EnumDisplayDevices($nullDisplay, [uint32]$i, [ref]$display, 0)) {
    break
  }

  $isAttached = ($display.StateFlags -band $DISPLAY_DEVICE_ATTACHED_TO_DESKTOP) -ne 0
  $isPrimary = ($display.StateFlags -band $DISPLAY_DEVICE_PRIMARY_DEVICE) -ne 0
  if (!$isAttached -or !$isPrimary) {
    continue
  }

  $mode = New-Object DisplayRefreshRate+DEVMODE
  $mode.dmSize = [Runtime.InteropServices.Marshal]::SizeOf($mode)
  if (![DisplayRefreshRate]::EnumDisplaySettings($display.DeviceName, $ENUM_CURRENT_SETTINGS, [ref]$mode)) {
    Write-Log "Could not read current settings for $($display.DeviceName)"
    exit 2
  }

  if ($mode.dmDisplayFrequency -ge $MinHz) {
    exit 0
  }

  $oldHz = $mode.dmDisplayFrequency
  $mode.dmFields = $mode.dmFields -bor $DM_BITSPERPEL -bor $DM_PELSWIDTH -bor $DM_PELSHEIGHT -bor $DM_DISPLAYFREQUENCY
  $mode.dmDisplayFrequency = $TargetHz
  $result = [DisplayRefreshRate]::ChangeDisplaySettingsEx($display.DeviceName, [ref]$mode, [IntPtr]::Zero, $CDS_UPDATEREGISTRY, [IntPtr]::Zero)

  if ($result -eq $DISP_CHANGE_SUCCESSFUL) {
    Write-Log "Changed $($display.DeviceName) from $oldHz Hz to $TargetHz Hz"
    exit 0
  }

  Write-Log "Failed to change $($display.DeviceName) from $oldHz Hz to $TargetHz Hz. Result=$result"
  exit $result
}

Write-Log "No attached primary display found"
exit 3
