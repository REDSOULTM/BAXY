# Records the trailer's real takes (documentacion/STEAM_PUBLICACION.md, section 8) with a BAXY that works on this
# machine (-Exe: the depot's app\Baxy.exe, or an installed one). Runs in the person's desktop session (an interactive
# scheduled task when started over SSH): it launches Baxy.exe with WebView2's debugging port, shows its window (BAXY
# starts in the tray) on the left, and for each take records the screen
# with ffmpeg while it types the phrase into «Escribe a BAXY» through the DevTools protocol, waits for BAXY's answer,
# stops the recording and closes, by PID, what the take opened. The takes land as 01.mp4 ... 05.mp4 in -Output, in
# -Lang: each language's trailer has its takes asked in that language (scripts/steam/make_trailer.py, TEXTS).
# A dedicated machine only: the takes drive the real desktop.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Exe,
    [Parameter(Mandatory = $true)][string]$Output,
    [ValidateSet('es', 'en')][string]$Lang = 'es',
    [string]$Only = '1,2,3,4,5',  # which takes, «2,4»: a string, so it also arrives whole through -File
    [int]$Port = 9339,
    [int]$AnswerSeconds = 90,
    [int]$WindowWidth = 1600,
    [int]$WindowHeight = 1000
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Add-Type -AssemblyName System.Windows.Forms

$phrases = @{
    es = @(
        'Abre Spotify y pon lo-fi para estudiar',
        'En la calculadora calcula 37 por 12',
        'Abre la configuración de colores y dime si el modo es claro u oscuro',
        'Sube el volumen al 40 %',
        'Abre el Bloc de notas y escribe: lista, pan y leche'
    )
    en = @(
        'Open Spotify and play some lo-fi to study',
        'In the calculator, work out 37 times 12',
        'Open the color settings and tell me if the mode is light or dark',
        'Turn the volume up to 40%',
        'Open Notepad and type: list, bread and milk'
    )
}
$takes = $phrases[$Lang]
New-Item -ItemType Directory -Force -Path $Output | Out-Null
$log = Join-Path $Output 'grabar_tomas.log'
function Say([string]$text) { "$(Get-Date -Format 'HH:mm:ss') $text" | Tee-Object -FilePath $log -Append }

Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class Win {
    [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr h, int x, int y, int w, int ht, bool repaint);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int command);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc callback, IntPtr data);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out Rect rect);
    [DllImport("user32.dll")] static extern int GetWindowTextLength(IntPtr h);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint message, IntPtr w, IntPtr l);
    [DllImport("dwmapi.dll")] static extern int DwmGetWindowAttribute(IntPtr h, int attribute, out int value, int size);
    // The visible titled top-level windows: what a take opened, Store apps included (they live in a frame process
    // that was already running, so a take's new processes do not show them). A cloaked window (DWMWA_CLOAKED, 14) is
    // not on screen: a Store app closed earlier keeps its frame cloaked and shows that same window when opened again,
    // so it counts as opened by the take.
    public static System.Collections.Generic.List<long> Visible() {
        var list = new System.Collections.Generic.List<long>();
        EnumWindows((h, d) => {
            int cloaked;
            if (IsWindowVisible(h) && GetWindowTextLength(h) > 0
                && !(DwmGetWindowAttribute(h, 14, out cloaked, 4) == 0 && cloaked != 0)) list.Add((long)h);
            return true; }, IntPtr.Zero);
        return list;
    }
    delegate bool EnumProc(IntPtr h, IntPtr data);
    struct Rect { public int Left, Top, Right, Bottom; }
    // The process's largest titled top-level window, hidden or not (BAXY starts in the tray).
    public static IntPtr LargestWindow(int processId) {
        IntPtr best = IntPtr.Zero; long bestArea = 0;
        EnumWindows((h, d) => {
            uint pid; GetWindowThreadProcessId(h, out pid);
            Rect r;
            if (pid == processId && GetWindowTextLength(h) > 0 && GetWindowRect(h, out r)) {
                long area = (long)(r.Right - r.Left) * (r.Bottom - r.Top);
                if (area > bestArea) { bestArea = area; best = h; }
            }
            return true;
        }, IntPtr.Zero);
        return best;
    }
}
'@

# --- the DevTools protocol, over a plain WebSocket -------------------------------------------------------------------
function Open-Page {
    $deadline = (Get-Date).AddMinutes(3)
    while ((Get-Date) -lt $deadline) {
        try {
            $page = Invoke-RestMethod "http://127.0.0.1:$Port/json/list" -TimeoutSec 3 |
                Where-Object { $_.url -like 'https://baxy.local/*' } | Select-Object -First 1
            if ($page) {
                $socket = [Net.WebSockets.ClientWebSocket]::new()
                $socket.ConnectAsync([Uri]$page.webSocketDebuggerUrl, [Threading.CancellationToken]::None).Wait()
                return $socket
            }
        } catch { }
        Start-Sleep -Milliseconds 500
    }
    throw "BAXY's view did not appear on port $Port."
}

$script:messageId = 0
function Send-Cdp($socket, [string]$method, [hashtable]$params = @{}) {
    $script:messageId++
    $json = @{ id = $script:messageId; method = $method; params = $params } | ConvertTo-Json -Depth 6 -Compress
    $bytes = [Text.Encoding]::UTF8.GetBytes($json)
    $socket.SendAsync([ArraySegment[byte]]::new($bytes), 'Text', $true, [Threading.CancellationToken]::None).Wait()
    $buffer = New-Object byte[] 1048576
    while ($true) {
        $text = ''
        do {
            $result = $socket.ReceiveAsync([ArraySegment[byte]]::new($buffer), [Threading.CancellationToken]::None).Result
            $text += [Text.Encoding]::UTF8.GetString($buffer, 0, $result.Count)
        } while (-not $result.EndOfMessage)
        $reply = $text | ConvertFrom-Json
        if (($reply.PSObject.Properties.Name -contains 'id') -and $reply.id -eq $script:messageId) { return $reply }
    }
}

function Eval($socket, [string]$expression) {
    $reply = Send-Cdp $socket 'Runtime.evaluate' @{ expression = $expression; returnByValue = $true }
    # An expression that gives undefined (the view not there yet) comes back without a value.
    $result = $reply.result.result
    if ($result.PSObject.Properties.Name -contains 'value') { return $result.value }
    return $null
}

# --- BAXY ---------------------------------------------------------------------------------------------------------------
$before = @(Get-Process | Select-Object -ExpandProperty Id)
# Off the screen, BAXY's view keeps painting: Chromium's occlusion tracking would otherwise stop it.
$env:WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS = "--remote-debugging-port=$Port --disable-features=CalculateNativeWinOcclusion"
$baxy = Start-Process -FilePath $Exe -WorkingDirectory (Split-Path -Parent $Exe) -PassThru
Say "BAXY lanzado: $Exe (PID $($baxy.Id))"
# Whatever happens to the takes, the BAXY this script started is closed at the end (the next language starts its own).
try {
$socket = Open-Page
$deadline = (Get-Date).AddMinutes(4)
while ((Eval $socket "document.querySelector('[aria-label=""Escribe a BAXY""],[aria-label=""Message BAXY""]')?.dataset.ready") -ne 'true') {
    if ((Get-Date) -gt $deadline) { throw 'BAXY did not become ready to take text.' }
    Start-Sleep -Seconds 1
}
Say 'BAXY listo para escribirle'
# The interface in the take's language (the person's choice in Settings, kept by the host), so the English take shows
# no Spanish of BAXY's own; the view reads it back within its 4 s settings reading.
Eval $socket "fetch('/settings/language',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({lang:'$Lang'})}).then(r=>r.status)" | Out-Null
$deadline = (Get-Date).AddSeconds(20)
while ((Eval $socket "document.documentElement.lang") -ne $Lang) {
    if ((Get-Date) -gt $deadline) { throw "BAXY's interface did not switch to $Lang." }
    Start-Sleep -Milliseconds 500
}
Say "Interfaz de BAXY en $Lang"
$screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$window = [Win]::LargestWindow($baxy.Id)
if ($window -eq [IntPtr]::Zero) { throw "BAXY's window was not found." }
[Win]::ShowWindow($window, 9) | Out-Null  # SW_RESTORE: shown from the tray
# BAXY's window goes just off the right edge of the screen: the desktop is recorded clean, and the window on its own
# (Windows Graphics Capture reads it wherever it is), so the trailer lays it over the desktop like a streamer's camera.
# The desktop starts clean (every window minimized, as a person would show it), and BAXY comes back to its place.
(New-Object -ComObject Shell.Application).MinimizeAll()
Start-Sleep -Milliseconds 1500
[Win]::ShowWindow($window, 9) | Out-Null
[Win]::MoveWindow($window, $screen.Width + 40, 0, $WindowWidth, $WindowHeight, $true) | Out-Null
Say "Ventana de BAXY fuera de la pantalla (${WindowWidth}x$WindowHeight)"

# The sound of the speakers, when this machine has a loopback device (Stereo Mix); otherwise the takes are silent and
# the trailer's music carries them.
# ffmpeg lists the devices on stderr and exits with an error: PowerShell 5.1 would stop on its first stderr line.
$ErrorActionPreference = 'Continue'
$devices = & ffmpeg -hide_banner -list_devices true -f dshow -i dummy 2>&1 | Out-String
$ErrorActionPreference = 'Stop'
$loopback = [regex]::Match($devices, '"((?:Stereo Mix|Mezcla est[eé]reo)[^"]*)"\s*\(audio\)').Groups[1].Value
Say ("Audio: " + $(if ($loopback) { $loopback } else { 'ninguno (sin Mezcla estéreo)' }))

foreach ($number in ($Only -split ',' | ForEach-Object { [int]$_ })) {
    $phrase = $takes[$number - 1]
    $file = Join-Path $Output ('{0:D2}.mp4' -f $number)
    $windowFile = Join-Path $Output ('{0:D2}_baxy.mp4' -f $number)
    $openedBefore = @(Get-Process | Select-Object -ExpandProperty Id)
    $windowsBefore = [Win]::Visible()
    # Each take in its own conversation, so its panel shows only what this take did.
    Eval $socket "document.querySelector('button[title=""Nueva conversación""],button[title=""New conversation""]')?.click()" | Out-Null
    Start-Sleep -Seconds 1
    $audio = if ($loopback) { @('-f', 'dshow', '-i', "audio=$loopback") } else { @() }
    # Records until BAXY is back to idle (at most -AnswerSeconds), then ffmpeg is told «q» on its input so it closes
    # the file itself (a recording stopped by PID loses its index and does not play).
    # One ffmpeg, two inputs, two files: the desktop (with the sound, if any) and BAXY's window, in step.
    $capture = "gfxcapture=hwnd=$([int64]$window):max_framerate=30:capture_cursor=0,hwdownload,format=bgra," +
        'fps=30,scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p'
    $arguments = @('-hide_banner', '-nostats', '-loglevel', 'error', '-y', '-f', 'gdigrab', '-framerate', '30',
        '-i', 'desktop', '-f', 'lavfi', '-i', $capture) + $audio + @(
        '-map', '1:v', '-t', [string]($AnswerSeconds + 5), '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '16',
        $windowFile, '-map', '0:v') + $(if ($loopback) { @('-map', '2:a') } else { @() }) + @(
        '-t', [string]($AnswerSeconds + 5),
        '-vf', 'scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,format=yuv420p',
        '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '16', '-c:a', 'aac', '-b:a', '160k', $file)
    $start = [Diagnostics.ProcessStartInfo]::new('ffmpeg', (($arguments | ForEach-Object { '"' + $_ + '"' }) -join ' '))
    $start.UseShellExecute = $false
    $start.RedirectStandardInput = $true
    $start.CreateNoWindow = $true
    $recorder = [Diagnostics.Process]::Start($start)
    Start-Sleep -Seconds 2
    [Win]::SetForegroundWindow($window) | Out-Null
    Eval $socket "document.querySelector('[aria-label=""Escribe a BAXY""],[aria-label=""Message BAXY""]').focus()" | Out-Null
    Send-Cdp $socket 'Input.insertText' @{ text = $phrase } | Out-Null
    Start-Sleep -Milliseconds 600
    foreach ($type in 'rawKeyDown', 'char', 'keyUp') {
        $key = @{ type = $type; key = 'Enter'; code = 'Enter'; windowsVirtualKeyCode = 13 }
        if ($type -eq 'char') { $key.text = "`r" }
        Send-Cdp $socket 'Input.dispatchKeyEvent' $key | Out-Null
    }
    Say "Toma $number enviada: $phrase"
    # The view's status label carries BAXY's state as a class: busy first, then idle again (or asking for an ok).
    $sent = Get-Date
    $busy = $false
    $state = ''
    while (((Get-Date) - $sent).TotalSeconds -lt $AnswerSeconds) {
        $state = [string](Eval $socket "document.querySelector('.bx-statel')?.className")
        if ($state -match 'thinking|speaking|listening') { $busy = $true }
        # BAXY asks before what needs an ok (going online, say): the take answers «Sí» as a person would, a moment
        # later so the question is seen, and keeps recording.
        elseif ($state -match 'confirm') {
            Start-Sleep -Milliseconds 2500
            Eval $socket "[...document.querySelectorAll('button.bx-btn.yes')].pop()?.click()" | Out-Null
            Say "Toma ${number}: BAXY pidió el ok y se le dio"
            Start-Sleep -Seconds 1
        }
        elseif ($busy -and $state -match 'idle|error') { break }
        Start-Sleep -Milliseconds 500
    }
    Say ("Toma $number respondida en {0:N0} s (estado: $state)" -f ((Get-Date) - $sent).TotalSeconds)
    Start-Sleep -Seconds 4  # the answer stays on screen a moment
    if (-not $recorder.HasExited) { $recorder.StandardInput.Write('q'); $recorder.StandardInput.Close() }
    $recorder.WaitForExit(15000) | Out-Null
    Say "Toma $number grabada en $file"
    # The windows the take opened are asked to close (WM_CLOSE), then what is left of its new processes goes by PID;
    # BAXY stays.
    foreach ($handle in [Win]::Visible()) {
        if ($windowsBefore -notcontains $handle -and $handle -ne [int64]$window) {
            [Win]::PostMessage([IntPtr]$handle, 0x10, [IntPtr]::Zero, [IntPtr]::Zero) | Out-Null
        }
    }
    Start-Sleep -Seconds 2
    Get-Process | Where-Object { $openedBefore -notcontains $_.Id -and $_.Id -ne $baxy.Id -and $_.MainWindowHandle -ne 0 } |
        ForEach-Object { Say "Cierro $($_.ProcessName) (PID $($_.Id))"; Stop-Process -Id $_.Id -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 3
}
} finally {
Say 'Cierro BAXY y todo lo que lanzó (su árbol de procesos, por PID)'
$all = @(Get-CimInstance Win32_Process)
$tree = @($baxy.Id)
do {
    $grew = @($all | Where-Object { $tree -contains $_.ParentProcessId -and $tree -notcontains $_.ProcessId })
    $tree += @($grew | ForEach-Object { $_.ProcessId })
} while ($grew.Count -gt 0)
[array]::Reverse($tree)
foreach ($id in $tree) { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue }
Say 'Listo'
}
