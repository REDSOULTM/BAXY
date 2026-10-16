using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Runtime.InteropServices;
using System.Text.Json.Nodes;
using Microsoft.Win32;

namespace Baxy.App;

/// <summary>
/// What the heartbeat sees of the moment, observed with generic signals and no list of applications: the time, what the
/// person is doing (in a call when another program holds the microphone, playing or watching when a window fills the
/// screen, with the GPU busy or not, otherwise away when idle), the window in front and the other open ones, and the
/// state of the PC. The model reads it as it is (<c>beat_message</c> in the mind); nothing here decides for it.
/// </summary>
internal static class HeartbeatMoment
{
    internal const string Free = "libre";
    internal const string Away = "ausente";
    internal const string InCall = "llamada";
    internal const string Playing = "jugando";
    internal const string Watching = "viendo";
    // Auditoría final (regla 3): with no reading of the last input the person is not «libre»; as the mind already says.
    internal const string Unknown = "desconocido";

    /// <summary>
    /// Where a heartbeat's words go (owner, 2026-10-16): aloud whatever the person does, except while they are away,
    /// play, are in a call or watch something, or their activity was not read, when they are only a notification on
    /// screen. The heartbeat of their return (<see cref="AwayWatch"/>) follows the same rule: aloud when they come back
    /// to anything else.
    /// </summary>
    internal static bool Speaks(string activity) => activity is not (Away or Playing or InCall or Watching or Unknown);

    internal static string Activity(out bool? fullscreen, out bool? gpuBusy)
    {
        gpuBusy = GpuBusy();
        string activity = Presence(out fullscreen);
        return activity == Watching && gpuBusy == true ? Playing : activity;
    }

    /// <summary>What the person is doing, as far as no GPU reading is needed (a window filling the screen is watching).</summary>
    internal static string Presence(out bool? fullscreen)
    {
        bool? fills = ForegroundFillsTheScreen();
        fullscreen = fills;
        // A call or a film goes on without the person's input: they are read before the idle time, or ten minutes into
        // one the person would read as away and a heartbeat would only notify of what it saw.
        bool? microphone = MicrophoneHeldByAnotherProgram();
        if (microphone == true)
        {
            return InCall;
        }

        if (fills == true)
        {
            return Watching;
        }

        // Auditoría final (regla 3): a reading that failed (the microphone's record, the window's or the monitor's
        // bounds, the last input) leaves the person's activity not known, never «libre».
        if (microphone is null || fills is null)
        {
            return Unknown;
        }

        return ReadIdleTime() is not { } idle ? Unknown : idle >= AwayWatch.After ? Away : Free;
    }

    internal static JsonObject Observe(
        IEnumerable<string> events, IReadOnlyList<ConversationMessage> recent, string? connectivity)
    {
        DateTimeOffset now = DateTimeOffset.Now;
        string activity = Activity(out bool? fullscreen, out bool? gpuBusy);
        var context = new JsonObject
        {
            ["now"] = now.ToString("yyyy-MM-dd'T'HH:mm:sszzz", CultureInfo.InvariantCulture),
            ["weekday"] = now.ToString("dddd", CultureInfo.GetCultureInfo("es-ES")),
            ["owner_activity"] = activity,
        };
        nint front = GetForegroundWindow();
        if (Describe(front) is { } frontWindow)
        {
            // Auditoría final (regla 3): written only when the window's and the monitor's bounds were read.
            if (fullscreen is bool fills)
                frontWindow["fullscreen"] = fills;
            context["foreground"] = frontWindow;
        }

        // Ronda final 6 (regla 3): every open window is listed; a list cut short would read as all of them. Ronda
        // final 8: a window DWM cloaks (on another virtual desktop, or a suspended packaged app) is not on screen, so it
        // is not listed with them, and the list says how many were left out that way.
        var windows = new JsonArray();
        int cloaked = 0;
        foreach (nint window in TopLevelWindows().Where(window => window != front))
        {
            if (IsCloaked(window))
            {
                cloaked++;
            }
            else if (Describe(window) is { } described)
            {
                windows.Add(described);
            }
        }

        if (cloaked > 0)
        {
            windows.Add(new JsonObject
            {
                ["title"] = $"y {cloaked} más fuera de la vista (en otro escritorio o suspendidas)",
                ["process"] = "sin leer",
            });
        }

        context["windows"] = windows;
        context["pc"] = Machine(gpuBusy, connectivity);
        context["events"] = new JsonArray(events.Select(static e => (JsonNode?)JsonValue.Create(e)).ToArray());
        var history = new JsonArray();
        foreach (ConversationMessage message in recent.TakeLast(6))
        {
            history.Add(new JsonObject
            {
                ["role"] = message.IsUser ? "user" : "assistant",
                // Ronda final 7 (regla 3): a message cut at 200 characters says it was cut.
                ["content"] = message.Body.Length > 200 ? message.Body[..200] + "… (cortado)" : message.Body,
                ["ago_min"] = (int)Math.Max(0, (now - message.CreatedAt).TotalMinutes),
            });
        }

        context["history"] = history;
        return context;
    }

    /// <param name="connectivity">Windows' internet check (internet, constrained, local, none); left out when unread.</param>
    /// <param name="gpuBusy">Left out when nvidia-smi was not read (ronda final: «gpu_busy=False» was said unread).</param>
    internal static JsonObject Machine(bool? gpuBusy, string? connectivity)
    {
        var pc = new JsonObject();
        if (gpuBusy is { } busy)
        {
            pc["gpu_busy"] = busy;
        }

        var memory = new MemoryStatus { Length = (uint)Marshal.SizeOf<MemoryStatus>() };
        if (GlobalMemoryStatusEx(ref memory))
        {
            pc["ram_pct"] = (int)memory.MemoryLoad;
        }

        if (GetSystemPowerStatus(out PowerStatus power) && power.BatteryLifePercent <= 100)
        {
            pc["battery_pct"] = (int)power.BatteryLifePercent;
            // Ronda final: ACLineStatus 255 is «unknown»: the plug is said only when Windows read it (0 or 1).
            if (power.ACLineStatus is 0 or 1)
            {
                pc["plugged"] = power.ACLineStatus == 1;
            }
        }

        try
        {
            var system = new DriveInfo(Path.GetPathRoot(Environment.SystemDirectory)!);
            pc["disk_free_gb"] = (int)(system.AvailableFreeSpace / (1L << 30));
        }
        catch (IOException)
        {
            // The disk's free space is left out when it cannot be read.
        }

        if (connectivity is not null)
        {
            pc["internet"] = connectivity;
        }

        // Ronda final: left out when Windows did not say when the last input was (as gpu_busy and plugged).
        if (ReadIdleTime() is { } idle)
        {
            pc["idle_min"] = (int)idle.TotalMinutes;
        }
        return pc;
    }

    /// <summary>The process that owns a window, or null when it is gone.</summary>
    internal static string? ProcessOf(nint window)
    {
        _ = GetWindowThreadProcessId(window, out uint processId);
        // Ronda final 8 (regla 3): a window gone before its process was read (pid 0 is «Idle») has no process.
        if (processId == 0)
        {
            return null;
        }

        try
        {
            using Process process = Process.GetProcessById((int)processId);
            return process.ProcessName;
        }
        catch (Exception exception) when (exception is ArgumentException or InvalidOperationException)
        {
            return null;
        }
    }

    private static JsonObject? Describe(nint window)
    {
        if (window == 0)
        {
            return null;
        }

        string title = WindowTitle(window);
        _ = GetWindowThreadProcessId(window, out uint processId);
        if (processId == 0)
        {
            return null;
        }

        try
        {
            using Process process = Process.GetProcessById((int)processId);
            return new JsonObject { ["process"] = process.ProcessName, ["title"] = title };
        }
        catch (Exception exception) when (exception is ArgumentException or InvalidOperationException)
        {
            return null;
        }
    }

    internal static IReadOnlyList<nint> TopLevelWindows()
    {
        var windows = new List<nint>();
        _ = EnumWindows((window, _) =>
        {
            if (IsWindowVisible(window) && GetWindow(window, 4) == 0 && WindowTitle(window).Length > 0
                && !IsToolWindow(window))
            {
                windows.Add(window);
            }

            return true;
        }, 0);
        return windows;
    }

    internal static string WindowTitle(nint window)
    {
        int length = GetWindowTextLength(window);
        if (length <= 0)
        {
            return string.Empty;
        }

        char[] buffer = new char[length + 1];
        int read = GetWindowText(window, buffer, buffer.Length);
        return new string(buffer, 0, Math.Max(0, read));
    }

    private static bool IsToolWindow(nint window) => (GetWindowLongPtr(window, -20) & 0x80) != 0;

    // Ronda final 7 (regla 3): DWMWA_CLOAKED (14), a window the shell hides (a suspended packaged app, another virtual
    // desktop's) is visible to Win32 and not on screen, as WindowsInstalledApplicationOpenProvider reads it.
    private static bool IsCloaked(nint window) =>
        DwmGetWindowAttribute(window, 14, out int cloaked, sizeof(int)) == 0 && cloaked != 0;

    internal static TimeSpan? ReadIdleTime()
    {
        var info = new LastInputInfo { Size = (uint)Marshal.SizeOf<LastInputInfo>() };
        return GetLastInputInfo(ref info)
            ? TimeSpan.FromMilliseconds(unchecked((uint)Environment.TickCount - info.Time))
            : null;
    }

    // True or false as read; null when the window's or the monitor's bounds could not be read. No window in front at all
    // is read as no window filling the screen.
    private static bool? ForegroundFillsTheScreen()
    {
        nint front = GetForegroundWindow();
        if (front == 0)
        {
            return false;
        }

        if (!GetWindowRect(front, out Rect window))
        {
            return null;
        }

        nint monitor = MonitorFromWindow(front, 2);
        var info = new MonitorInfo { Size = (uint)Marshal.SizeOf<MonitorInfo>() };
        if (!GetMonitorInfo(monitor, ref info))
        {
            return null;
        }

        string className = ClassName(front);
        return className is not ("Progman" or "WorkerW")
            && window.Left <= info.Monitor.Left && window.Top <= info.Monitor.Top
            && window.Right >= info.Monitor.Right && window.Bottom >= info.Monitor.Bottom;
    }

    // Windows records which program holds the microphone (Settings > Privacy > Microphone shows it as «in use»): an
    // entry whose last use has started and not stopped. BAXY's own listening (the mind's Python) is not a call.
    // True or false as read; null when Windows' record of the microphone could not be read.
    private static bool? MicrophoneHeldByAnotherProgram()
    {
        const string store = @"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone";
        string? ownPython = Environment.GetEnvironmentVariable(MindSidecarClient.PythonEnvironmentVariable);
        try
        {
            using RegistryKey? root = Registry.CurrentUser.OpenSubKey(store);
            if (root is null)
            {
                return false;
            }

            foreach (string name in root.GetSubKeyNames())
            {
                using RegistryKey? entry = root.OpenSubKey(name);
                if (entry is null)
                {
                    continue;
                }

                IEnumerable<(string Name, RegistryKey Key)> users = name == "NonPackaged"
                    ? entry.GetSubKeyNames().Select(child => (child, entry.OpenSubKey(child)!)).Where(static e => e.Item2 is not null)
                    : [(name, entry)];
                foreach ((string user, RegistryKey key) in users)
                {
                    bool own = ownPython is not null
                        && user.Replace('#', '\\').Equals(ownPython, StringComparison.OrdinalIgnoreCase);
                    if (!own && key.GetValue("LastUsedTimeStart") is long started && started > 0
                        && key.GetValue("LastUsedTimeStop") is long stopped && stopped == 0)
                    {
                        return true;
                    }
                }
            }
        }
        catch (Exception exception) when (exception is System.Security.SecurityException or IOException
            or UnauthorizedAccessException)
        {
            return null;
        }

        return false;
    }

    // The GPU is busy with something else (a game) when its load is high while BAXY is not deciding.
    private static bool? GpuBusy()
    {
        try
        {
            using var smi = Process.Start(new ProcessStartInfo("nvidia-smi",
                "--query-gpu=utilization.gpu --format=csv,noheader,nounits")
            {
                RedirectStandardOutput = true,
                UseShellExecute = false,
                CreateNoWindow = true,
            });
            if (smi is null)
            {
                return null;
            }

            string output = smi.StandardOutput.ReadToEnd();
            smi.WaitForExit(2000);
            return int.TryParse(output.Split('\n')[0].Trim(), out int load) ? load >= 40 : null;
        }
        catch (System.ComponentModel.Win32Exception)
        {
            return null;
        }
    }

    private static string ClassName(nint window)
    {
        char[] buffer = new char[256];
        int read = GetClassName(window, buffer, buffer.Length);
        return new string(buffer, 0, Math.Max(0, read));
    }

    private delegate bool EnumWindowsProc(nint window, nint parameter);

    [StructLayout(LayoutKind.Sequential)]
    private struct Rect
    {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct MonitorInfo
    {
        public uint Size;
        public Rect Monitor;
        public Rect Work;
        public uint Flags;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct LastInputInfo
    {
        public uint Size;
        public uint Time;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct MemoryStatus
    {
        public uint Length;
        public uint MemoryLoad;
        public ulong TotalPhys;
        public ulong AvailPhys;
        public ulong TotalPageFile;
        public ulong AvailPageFile;
        public ulong TotalVirtual;
        public ulong AvailVirtual;
        public ulong AvailExtendedVirtual;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct PowerStatus
    {
        public byte ACLineStatus;
        public byte BatteryFlag;
        public byte BatteryLifePercent;
        public byte SystemStatusFlag;
        public int BatteryLifeTime;
        public int BatteryFullLifeTime;
    }

    [DllImport("user32.dll")] private static extern nint GetForegroundWindow();
    [DllImport("user32.dll")] private static extern uint GetWindowThreadProcessId(nint window, out uint processId);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int GetWindowText(nint window, [Out] char[] text, int count);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] private static extern int GetWindowTextLength(nint window);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int GetClassName(nint window, [Out] char[] text, int count);
    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool EnumWindows(EnumWindowsProc callback, nint parameter);
    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool IsWindowVisible(nint window);
    [DllImport("user32.dll")] private static extern nint GetWindow(nint window, uint command);
    [DllImport("dwmapi.dll")] private static extern int DwmGetWindowAttribute(nint window, int attribute, out int value, int size);
    [DllImport("user32.dll", EntryPoint = "GetWindowLongPtrW")] private static extern nint GetWindowLongPtr(nint window, int index);
    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GetWindowRect(nint window, out Rect rect);
    [DllImport("user32.dll")] private static extern nint MonitorFromWindow(nint window, uint flags);
    [DllImport("user32.dll", EntryPoint = "GetMonitorInfoW")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GetMonitorInfo(nint monitor, ref MonitorInfo info);
    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GetLastInputInfo(ref LastInputInfo info);
    [DllImport("kernel32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GlobalMemoryStatusEx(ref MemoryStatus status);
    [DllImport("kernel32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GetSystemPowerStatus(out PowerStatus status);
}
