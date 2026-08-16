param(
    [Parameter(Mandatory = $true)]
    [int]$ProcessId,
    [Parameter(Mandatory = $true)]
    [string]$Text
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class BaxyAuditUiNative
{
    [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr handle);
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr handle, out uint processId);
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint flags, uint dx, uint dy, uint data, UIntPtr extra);
    [DllImport("user32.dll")] public static extern void keybd_event(byte key, byte scan, uint flags, UIntPtr extra);
}
'@

[BaxyAuditUiNative]::SetProcessDPIAware() | Out-Null
$process = Get-Process -Id $ProcessId
$shell = New-Object -ComObject WScript.Shell
if (-not $shell.AppActivate($ProcessId)) {
    throw 'BAXY could not be activated.'
}
[BaxyAuditUiNative]::SetForegroundWindow($process.MainWindowHandle) | Out-Null
Start-Sleep -Milliseconds 350

# Coordinates are inside the installed 1.0.8 Field input in logical pixels.
# Convert them to physical coordinates because SetProcessDPIAware makes
# SetCursorPos operate in the physical 1280x720 desktop at 150% scaling.
$logicalWidth = 1920.0
$physicalWidth = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width
$scale = $physicalWidth / $logicalWidth
$inputX = [int][Math]::Round(800 * $scale)
$inputY = [int][Math]::Round(838 * $scale)
[BaxyAuditUiNative]::SetCursorPos($inputX, $inputY) | Out-Null
[BaxyAuditUiNative]::mouse_event(2, 0, 0, 0, [UIntPtr]::Zero)
[BaxyAuditUiNative]::mouse_event(4, 0, 0, 0, [UIntPtr]::Zero)
Start-Sleep -Milliseconds 200

$foreground = [BaxyAuditUiNative]::GetForegroundWindow()
$foregroundProcessId = [uint32]0
[BaxyAuditUiNative]::GetWindowThreadProcessId(
    $foreground,
    [ref]$foregroundProcessId) | Out-Null
if ($foregroundProcessId -ne $ProcessId) {
    throw "Foreground process mismatch: $foregroundProcessId."
}

$clipboard = [System.Windows.Forms.Clipboard]::GetDataObject()
try {
    [System.Windows.Forms.Clipboard]::SetText($Text)
    Start-Sleep -Milliseconds 100
    [BaxyAuditUiNative]::keybd_event(0x11, 0, 0, [UIntPtr]::Zero)
    [BaxyAuditUiNative]::keybd_event(0x56, 0, 0, [UIntPtr]::Zero)
    [BaxyAuditUiNative]::keybd_event(0x56, 0, 2, [UIntPtr]::Zero)
    [BaxyAuditUiNative]::keybd_event(0x11, 0, 2, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 200
    [System.Windows.Forms.SendKeys]::SendWait('{ENTER}')
}
finally {
    if ($null -ne $clipboard) {
        [System.Windows.Forms.Clipboard]::SetDataObject($clipboard, $true)
    }
    else {
        [System.Windows.Forms.Clipboard]::Clear()
    }
}

[pscustomobject]@{
    sent = $true
    process_id = $ProcessId
    text_length = $Text.Length
    utc = [DateTimeOffset]::UtcNow.ToString('O')
} | ConvertTo-Json -Compress
