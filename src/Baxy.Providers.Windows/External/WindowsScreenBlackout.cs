using System.Diagnostics;
using System.Globalization;
using System.Runtime.InteropServices;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// PAN7 (VIVO21, 14-11-2026: on the notebook «apaga la pantalla» posted SC_MONITORPOWER and Kernel-Power logged «The
/// system is entering Modern Standby, reason: SC_MONITORPOWER»; the network went down, BAXY stopped hearing and the PC
/// woke only when touched two hours later). On a Modern Standby PC the display turning off is the standby (Microsoft Learn,
/// «Prepare software for modern standby», consulted 2026-11-14: «A system enters modern standby when the display turns
/// off»; Microsoft Q&amp;A 1665454, accepted answer: «The system is designed to transition into the sleep state after the
/// screen turns off»), and no power request is documented to hold it off (PowerSetRequest: system and execution required
/// requests «are terminated 5 minutes after the system sleep timeout has expired» on battery). So the screen is darkened
/// without turning the display off: one borderless topmost black window over the whole virtual screen and the panel's
/// brightness at its minimum (WMI WmiMonitorBrightnessMethods, as display brightness already is in
/// WindowsDeviceControlAdapter), the way screen-off tools for such PCs do it. The display stays on, so Windows sees no
/// screen off and the PC keeps running; while the window is up its thread holds ES_DISPLAY_REQUIRED (SetThreadExecutionState),
/// so Windows' own display idle timer does not turn the display off under it either. A key or a mouse move (GetLastInputInfo changes) or <see cref="End"/> takes the
/// window off and gives the brightness back. The window lives on a thread of its own with its message loop.
/// </summary>
internal sealed partial class WindowsScreenBlackout
{
    private const uint WsPopup = 0x80000000;
    private const uint WsVisible = 0x10000000;
    private const uint WsExTopmost = 0x00000008;
    private const uint WsExToolWindow = 0x00000080;
    private const uint WsExNoActivate = 0x08000000;
    private const int BlackBrush = 4;
    private const int XVirtualScreen = 76;
    private const int YVirtualScreen = 77;
    private const int CxVirtualScreen = 78;
    private const int CyVirtualScreen = 79;
    private const uint WmTimer = 0x0113;
    private const uint WmEnd = 0x8000 + 0x70; // WM_APP + 0x70: End asks the loop to stop.
    private const uint EsContinuous = 0x80000000;
    private const uint EsDisplayRequired = 0x00000002;
    private const uint EsSystemRequired = 0x00000001;
    private const uint SwpNoSize = 0x0001;
    private const uint SwpNoMove = 0x0002;
    private const uint SwpNoActivate = 0x0010;
    private const string ClassName = "BAXY.ScreenBlackout";
    private static readonly TimeSpan ShowWait = TimeSpan.FromSeconds(15);
    private static readonly TimeSpan BrightnessWait = TimeSpan.FromSeconds(8);

    // Every brightness method gets the same level, as WindowsDeviceControlAdapter.BrightnessScript does; the level the
    // first one had is written out first (revisión ciega PAN7, 2: a set that fails halfway or runs out of time still lets
    // it be given back). Exit 3: Windows exposes no brightness here.
    private const string BrightnessScript = """
        $ErrorActionPreference='Stop'
        try{$now=@(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness);$set=@(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods)}catch{exit 3}
        if($now.Count -eq 0 -or $set.Count -eq 0){exit 3}
        [Console]::Out.Write([int]$now[0].CurrentBrightness);[Console]::Out.Flush()
        foreach($m in $set){Invoke-CimMethod -InputObject $m -MethodName WmiSetBrightness -Arguments @{Timeout=1;Brightness=[byte]$args[0]}|Out-Null}
        """;

    private readonly Lock _gate = new();
    private Thread? _thread;
    private uint _threadId;
    private ScreenBlackout? _shown;

    // Revisión ciega PAN7 (1): whether the window is up now. Cleared by the thread, without the lock, the moment its loop
    // ends (before the brightness is given back), so a new Show never reports a window that is gone.
    private volatile bool _up;

    /// <summary>Shows the black window (once: while one is up, what it did is said again) and lowers the brightness;
    /// null when no window could be shown.</summary>
    internal ScreenBlackout? Show(Func<uint?> lastInput)
    {
        lock (_gate)
        {
            if (_thread is { IsAlive: true } old)
            {
                if (_up && _shown is { } up)
                {
                    return up;
                }

                // Revisión ciega PAN7 (1): one ending is still giving the brightness back; a new one would race it.
                _ = old.Join(BrightnessWait + TimeSpan.FromSeconds(2));
            }

            // A monitor, not an event: the thread may answer after the wait gave up, and nothing it touches is disposed.
            var signal = new object();
            ScreenBlackout? result = null;
            var thread = new Thread(() => Run(lastInput, shown =>
            {
                lock (signal)
                {
                    result = shown;
                    Monitor.PulseAll(signal);
                }
            }))
            {
                IsBackground = true,
                Name = "BAXY screen blackout",
            };
            thread.SetApartmentState(ApartmentState.STA);
            // Revisión ciega PAN7 (7): known before the wait, so a window that comes up after it gave up is ended.
            _thread = thread;
            _shown = null;
            lock (signal)
            {
                thread.Start();
                _ = Monitor.Wait(signal, ShowWait);
            }

            if (result is null)
            {
                _ = PostThreadMessage(_threadId, WmEnd, 0, 0);
                return null;
            }

            _shown = result;
            return result;
        }
    }

    /// <summary>Takes the window off and gives the brightness back; whether one was up and that came to an end.</summary>
    internal bool End()
    {
        Thread? thread;
        lock (_gate)
        {
            thread = _thread;
            if (thread is not { IsAlive: true } || !_up)
            {
                return false;
            }

            _ = PostThreadMessage(_threadId, WmEnd, 0, 0);
        }

        return thread.Join(BrightnessWait + TimeSpan.FromSeconds(2));
    }

    private void Run(Func<uint?> lastInput, Action<ScreenBlackout?> shown)
    {
        _threadId = GetCurrentThreadId();
        // Revisión ciega PAN7 (9): the core process has no DPI manifest; per monitor aware, the window covers the screens
        // in their own pixels, with no rounded edge left lit.
        _ = SetThreadDpiAwarenessContext(-4);
        nint window = Create();
        if (window == 0)
        {
            shown(null);
            return;
        }

        _up = true;
        // Revisión ciega PAN7 (6): the display idle timer would turn the display off under the window and, on a Modern
        // Standby PC, that is the standby (Microsoft Learn, «SetThreadExecutionState»: «ES_DISPLAY_REQUIRED Forces the
        // display to be on by resetting the display idle timer»); held by this thread while the window is up.
        _ = SetThreadExecutionState(EsContinuous | EsDisplayRequired | EsSystemRequired);
        uint? input = lastInput();
        int? before = Brightness(0);
        shown(new ScreenBlackout(before, input));
        nuint timer = SetTimer(0, 0, 250, 0);
        while (GetMessage(out Msg message, 0, 0, 0) > 0)
        {
            if (message.Message == WmEnd)
            {
                break;
            }

            // A key or a mouse move anywhere in the session (GetLastInputInfo, PAN5) lights the screen again.
            if (message.Message == WmTimer && message.Window == 0)
            {
                if (lastInput() is { } now && input is { } then && now != then)
                {
                    break;
                }

                // Revisión ciega PAN7 (8): above whatever topmost window came up since (taskbar, flyouts, toasts).
                _ = SetWindowPos(window, -1, 0, 0, 0, 0, SwpNoMove | SwpNoSize | SwpNoActivate);
                continue;
            }

            _ = TranslateMessage(in message);
            _ = DispatchMessage(in message);
        }

        _up = false;
        _ = KillTimer(0, timer);
        _ = DestroyWindow(window);
        _ = SetThreadExecutionState(EsContinuous);
        if (before is { } level)
        {
            _ = Brightness(level);
        }
    }

    private static unsafe nint Create()
    {
        nint instance = GetModuleHandle(null);
        fixed (char* name = ClassName)
        {
            var type = new WndClassEx
            {
                Size = (uint)sizeof(WndClassEx),
                Procedure = GetProcAddress(GetModuleHandle("user32.dll"), "DefWindowProcW"),
                Instance = instance,
                Background = GetStockObject(BlackBrush),
                ClassName = (nint)name,
            };
            // A second blackout finds the class already there (ERROR_CLASS_ALREADY_EXISTS): the window still opens.
            _ = RegisterClassEx(in type);
            nint window = CreateWindowEx(
                WsExTopmost | WsExToolWindow | WsExNoActivate,
                (nint)name,
                0,
                WsPopup | WsVisible,
                GetSystemMetrics(XVirtualScreen),
                GetSystemMetrics(YVirtualScreen),
                GetSystemMetrics(CxVirtualScreen),
                GetSystemMetrics(CyVirtualScreen),
                0,
                0,
                instance,
                0);
            if (window != 0)
            {
                _ = UpdateWindow(window);
            }

            return window;
        }
    }

    // Sets every panel's brightness to level and gives the level the first one had; null when Windows exposes no
    // brightness here (a desktop monitor) or the script did not answer in time.
    private static int? Brightness(int level)
    {
        var start = new ProcessStartInfo("powershell.exe")
        {
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        };
        foreach (string argument in new[]
        {
            "-NoProfile", "-NonInteractive", "-Command", "& {\n" + BrightnessScript + "\n}",
            level.ToString(CultureInfo.InvariantCulture),
        })
        {
            start.ArgumentList.Add(argument);
        }

        try
        {
            using Process process = Process.Start(start)!;
            Task<string> output = process.StandardOutput.ReadToEndAsync();
            _ = process.StandardError.ReadToEndAsync();
            if (!process.WaitForExit(BrightnessWait))
            {
                process.Kill(entireProcessTree: true);
                process.WaitForExit();
            }

            // Whatever the exit: a level written before the set began is the one to give back.
            return int.TryParse(output.GetAwaiter().GetResult().Trim(), NumberStyles.Integer, CultureInfo.InvariantCulture, out int before)
                ? before
                : null;
        }
        catch (Exception exception) when (exception is System.ComponentModel.Win32Exception or InvalidOperationException)
        {
            return null;
        }
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct WndClassEx
    {
        public uint Size;
        public uint Style;
        public nint Procedure;
        public int ClassExtra;
        public int WindowExtra;
        public nint Instance;
        public nint Icon;
        public nint Cursor;
        public nint Background;
        public nint MenuName;
        public nint ClassName;
        public nint SmallIcon;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct Msg
    {
        public nint Window;
        public uint Message;
        public nint WParam;
        public nint LParam;
        public uint Time;
        public int X;
        public int Y;
        public uint Private;
    }

    [LibraryImport("kernel32.dll", EntryPoint = "GetModuleHandleW", StringMarshalling = StringMarshalling.Utf16)]
    private static partial nint GetModuleHandle(string? name);

    [LibraryImport("kernel32.dll", StringMarshalling = StringMarshalling.Utf8)]
    private static partial nint GetProcAddress(nint module, string name);

    [LibraryImport("kernel32.dll")]
    private static partial uint GetCurrentThreadId();

    [LibraryImport("gdi32.dll")]
    private static partial nint GetStockObject(int index);

    [LibraryImport("user32.dll")]
    private static partial int GetSystemMetrics(int index);

    [LibraryImport("user32.dll", EntryPoint = "RegisterClassExW")]
    private static partial ushort RegisterClassEx(in WndClassEx type);

    [LibraryImport("user32.dll", EntryPoint = "CreateWindowExW")]
    private static partial nint CreateWindowEx(
        uint extendedStyle,
        nint className,
        nint windowName,
        uint style,
        int x,
        int y,
        int width,
        int height,
        nint parent,
        nint menu,
        nint instance,
        nint parameter);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool UpdateWindow(nint window);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool DestroyWindow(nint window);

    [LibraryImport("user32.dll")]
    private static partial nuint SetTimer(nint window, nuint id, uint milliseconds, nint callback);

    [LibraryImport("user32.dll", EntryPoint = "GetMessageW")]
    private static partial int GetMessage(out Msg message, nint window, uint first, uint last);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool TranslateMessage(in Msg message);

    [LibraryImport("user32.dll", EntryPoint = "DispatchMessageW")]
    private static partial nint DispatchMessage(in Msg message);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool KillTimer(nint window, nuint id);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool SetWindowPos(nint window, nint after, int x, int y, int width, int height, uint flags);

    [LibraryImport("user32.dll")]
    private static partial nint SetThreadDpiAwarenessContext(nint context);

    [LibraryImport("kernel32.dll")]
    private static partial uint SetThreadExecutionState(uint flags);

    [LibraryImport("user32.dll", EntryPoint = "PostThreadMessageW")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool PostThreadMessage(uint thread, uint message, nint wParam, nint lParam);
}
