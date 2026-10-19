# The window in front now and its program, and whether it is visible: "front <process> visible=<bool>". Exit 1 when
# the front is held by an invisible window or by GameInputSvc (the desktop of an e2e seed is then not clean).
Add-Type -Name F -Namespace Frente -MemberDefinition @'
[DllImport("user32.dll")] public static extern System.IntPtr GetForegroundWindow();
[DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(System.IntPtr h, out uint p);
[DllImport("user32.dll")] public static extern bool IsWindowVisible(System.IntPtr h);
'@
$h = [Frente.F]::GetForegroundWindow()
$p = 0
[void][Frente.F]::GetWindowThreadProcessId($h, [ref]$p)
$name = try { (Get-Process -Id $p -ErrorAction Stop).ProcessName } catch { '?' }
$visible = $h -ne [IntPtr]::Zero -and [Frente.F]::IsWindowVisible($h)
"front $name visible=$visible"
if ($name -eq 'GameInputSvc' -or ($h -ne [IntPtr]::Zero -and -not $visible)) { exit 1 }
exit 0
