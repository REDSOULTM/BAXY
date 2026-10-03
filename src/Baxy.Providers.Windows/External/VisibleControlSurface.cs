using System.Runtime.InteropServices;
using Baxy.Providers.Windows.Capture;

namespace Baxy.Providers.Windows.External;

internal static partial class VisibleControlSurface
{
    internal static async ValueTask<CapturedWindow?> CaptureForegroundAsync(
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        nint hwnd = GetForegroundWindow();
        if (hwnd == 0)
            return null;
        // UI1395: a freshly launched UWP app is fronted by its CoreWindow
        // (calculatorapp.exe, no top-level window of its own) and, once a
        // control is invoked, by its ApplicationFrameHost frame. The frame is
        // the root ancestor of both moments, so that one window is compared;
        // a classic top-level window keeps the largest-window rule.
        nint root = GetAncestor(hwnd, 2);
        if (root != 0 && root != hwnd)
        {
            hwnd = root;
        }
        else
        {
            _ = GetWindowThreadProcessId(hwnd, out uint processId);
            nint largest = LargestTopLevelWindow(unchecked((int)processId));
            if (largest != 0)
                hwnd = largest;
        }
        // UI1735: two Chromium-based launchers replace their start-up
        // window with their main window a few seconds after app.open verified
        // the focus, and the foreground fell back to this product's own window
        // (or to a window with no surface); the label was then searched on the
        // wrong surface for the whole budget. The surface a person acts on is
        // the topmost window that is not BAXY: when the foreground is ours or
        // has no usable surface, take that window and bring it to the front,
        // because the click lands on whatever is on top.
        _ = GetWindowThreadProcessId(hwnd, out uint foregroundProcess);
        if (foregroundProcess == unchecked((uint)Environment.ProcessId) || !HasUsableSurface(hwnd))
        {
            nint candidate = TopmostForeignWindow();
            if (candidate != 0)
            {
                _ = SetForegroundWindow(candidate);
                await Task.Delay(250, cancellationToken).ConfigureAwait(false);
                hwnd = candidate;
            }
        }
        if (!TryBounds(hwnd, out int left, out int top, out _, out _))
            return null;
        string directory = Path.Combine(Path.GetTempPath(), "baxy-visible-control");
        var provider = new WindowsScreenshotProvider(directory);
        CaptureResult capture = await provider.CaptureWindowAsync(hwnd, cancellationToken)
            .ConfigureAwait(false);
        string path = Path.Combine(directory, capture.CaptureId + ".bmp");
        if (!File.Exists(path))
            return null;
        return new CapturedWindow(hwnd, path, left, top, capture.Width, capture.Height, capture.Sha256);
    }

    // M132 (owner script t36 «abre … y ve a la biblioteca», launched cold): the opening was verified on the
    // client's updater window (400×129, its own process) and the click looked at the front window for its whole
    // budget, but the main window came seconds later from a helper process the client started, and the front had
    // gone back to whatever was there before. What a click right after an opening acts on is the application that
    // was opened: its process or one it started, the largest usable window of them, brought to the front.
    private static readonly object OpenedGate = new();
    private static OpenedApplication? _opened;

    internal static void NoteOpened(int processId, bool launched)
    {
        if (processId <= 0)
            return;
        DateTime started;
        try
        {
            using var process = System.Diagnostics.Process.GetProcessById(processId);
            started = process.StartTime.ToUniversalTime();
        }
        catch (Exception exception) when (exception is ArgumentException
            or InvalidOperationException or System.ComponentModel.Win32Exception
            or NotSupportedException)
        {
            return;
        }

        lock (OpenedGate)
            _opened = new OpenedApplication(processId, started, DateTime.UtcNow, launched);
    }

    internal static OpenedApplication? TakeOpened(TimeSpan freshness)
    {
        lock (OpenedGate)
        {
            OpenedApplication? opened = _opened;
            _opened = null;
            return opened is { } value && DateTime.UtcNow - value.NotedUtc <= freshness ? value : null;
        }
    }

    internal static OpenedApplication? PeekOpened(TimeSpan freshness)
    {
        lock (OpenedGate)
        {
            return _opened is { } value && DateTime.UtcNow - value.NotedUtc <= freshness ? value : null;
        }
    }

    // True when the opened application shows a usable window and the largest one is now in front (or one of its
    // own windows already was); false while it has none yet (an updater or splash only, or nothing).
    internal static async ValueTask<bool> FrontOpenedAsync(
        OpenedApplication opened,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        HashSet<uint> family = ProcessFamily(opened);
        if (family.Count == 0)
            return false;
        nint foreground = GetForegroundWindow();
        if (foreground != 0)
        {
            nint root = GetAncestor(foreground, 2);
            if (root != 0)
                foreground = root;
            _ = GetWindowThreadProcessId(foreground, out uint owner);
            if (family.Contains(owner) && HasUsableSurface(foreground))
                return true;
        }

        nint target = LargestUsableWindow(family);
        if (target == 0)
            return false;
        BringToFront(target);
        await Task.Delay(250, cancellationToken).ConfigureAwait(false);
        return true;
    }

    private static HashSet<uint> ProcessFamily(OpenedApplication opened)
    {
        var family = new HashSet<uint>();
        Dictionary<uint, List<uint>> children = ChildrenByParent();
        var pending = new Queue<uint>();
        pending.Enqueue(unchecked((uint)opened.ProcessId));
        while (pending.Count > 0)
        {
            uint current = pending.Dequeue();
            if (!family.Add(current) || !children.TryGetValue(current, out List<uint>? started))
                continue;
            foreach (uint child in started)
            {
                // A parent id can outlive its process and be handed to another one; a child that is older than
                // the opened process was not started by it.
                if (StartedAfter(child, opened.StartedUtc))
                    pending.Enqueue(child);
            }
        }

        if (!ProcessAlive(opened))
            family.Remove(unchecked((uint)opened.ProcessId));
        return family;
    }

    private static bool StartedAfter(uint processId, DateTime startedUtc)
    {
        try
        {
            using var process = System.Diagnostics.Process.GetProcessById(unchecked((int)processId));
            return process.StartTime.ToUniversalTime() >= startedUtc.AddSeconds(-1);
        }
        catch (Exception exception) when (exception is ArgumentException
            or InvalidOperationException or System.ComponentModel.Win32Exception
            or NotSupportedException)
        {
            return false;
        }
    }

    private static bool ProcessAlive(OpenedApplication opened)
    {
        try
        {
            using var process = System.Diagnostics.Process.GetProcessById(opened.ProcessId);
            return !process.HasExited
                && Math.Abs((process.StartTime.ToUniversalTime() - opened.StartedUtc).TotalSeconds) < 1;
        }
        catch (Exception exception) when (exception is ArgumentException
            or InvalidOperationException or System.ComponentModel.Win32Exception
            or NotSupportedException)
        {
            return false;
        }
    }

    private static unsafe Dictionary<uint, List<uint>> ChildrenByParent()
    {
        var children = new Dictionary<uint, List<uint>>();
        nint snapshot = CreateToolhelp32Snapshot(0x00000002, 0);
        if (snapshot == -1 || snapshot == 0)
            return children;
        try
        {
            var entry = new ProcessEntry32 { Size = (uint)sizeof(ProcessEntry32) };
            if (!Process32FirstW(snapshot, ref entry))
                return children;
            do
            {
                if (entry.ProcessId != 0 && entry.ParentProcessId != entry.ProcessId)
                {
                    if (!children.TryGetValue(entry.ParentProcessId, out List<uint>? list))
                        children[entry.ParentProcessId] = list = [];
                    list.Add(entry.ProcessId);
                }
                entry.Size = (uint)sizeof(ProcessEntry32);
            }
            while (Process32NextW(snapshot, ref entry));
        }
        finally
        {
            _ = CloseHandle(snapshot);
        }

        return children;
    }

    private static nint LargestUsableWindow(HashSet<uint> family)
    {
        nint best = 0;
        long bestArea = 0;
        EnumWindowsProc callback = (window, unused) =>
        {
            if (GetAncestor(window, 3) != window || (GetWindowLongPtrW(window, -20).ToInt64() & 0x80) != 0)
                return true;
            _ = GetWindowThreadProcessId(window, out uint owner);
            if (!family.Contains(owner) || !HasUsableSurface(window))
                return true;
            if (!TryBounds(window, out int left, out int top, out int right, out int bottom))
                return true;
            long area = (long)(right - left) * (bottom - top);
            if (area > bestArea)
            {
                bestArea = area;
                best = window;
            }
            return true;
        };
        _ = EnumWindows(callback, nint.Zero);
        return best;
    }

    // A background process may not take the foreground by itself; joined to the input of the thread that holds
    // it, the request is honoured (the same handoff app.open asks for).
    private static void BringToFront(nint window)
    {
        nint foreground = GetForegroundWindow();
        uint current = GetCurrentThreadId();
        uint holder = foreground == 0 ? 0 : GetWindowThreadProcessId(foreground, out _);
        bool attached = holder != 0 && holder != current && AttachThreadInput(current, holder, true);
        try
        {
            if (IsIconic(window))
                _ = ShowWindowAsync(window, 9);
            _ = BringWindowToTop(window);
            _ = SetForegroundWindow(window);
        }
        finally
        {
            if (attached)
                _ = AttachThreadInput(current, holder, false);
        }
    }

    internal static void Click(int screenX, int screenY)
    {
        _ = SetCursorPos(screenX, screenY);
        mouse_event(0x0002, 0, 0, 0, 0);
        mouse_event(0x0004, 0, 0, 0, 0);
    }

    internal static void Delete(string? path)
    {
        if (path is null)
            return;
        try { File.Delete(path); }
        catch (IOException) { }
        catch (UnauthorizedAccessException) { }
    }

    private static bool TryBounds(nint hwnd, out int left, out int top, out int right, out int bottom)
    {
        left = top = right = bottom = 0;
        if (DwmGetWindowAttribute(hwnd, 9, out Rect rect, Marshal.SizeOf<Rect>()) != 0
            && !GetWindowRect(hwnd, out rect))
        {
            return false;
        }
        left = rect.Left;
        top = rect.Top;
        right = rect.Right;
        bottom = rect.Bottom;
        return right > left && bottom > top;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct Rect
    {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    private static nint LargestTopLevelWindow(int processId)
    {
        nint best = 0;
        long bestArea = 0;
        EnumWindowsProc callback = (window, _) =>
        {
            if (!IsWindowVisible(window))
                return true;
            GetWindowThreadProcessId(window, out uint owner);
            if (owner != unchecked((uint)processId))
                return true;
            if (!GetWindowRect(window, out Rect rect))
                return true;
            long area = (long)Math.Max(0, rect.Right - rect.Left)
                * Math.Max(0, rect.Bottom - rect.Top);
            if (area > bestArea)
            {
                bestArea = area;
                best = window;
            }
            return true;
        };
        _ = EnumWindows(callback, nint.Zero);
        return best;
    }

    private static bool HasUsableSurface(nint window)
    {
        if (!IsWindowVisible(window) || GetWindowTextLengthW(window) == 0)
            return false;
        if (DwmGetWindowAttribute(window, 14, out int cloaked, sizeof(int)) == 0 && cloaked != 0)
            return false;
        if (!TryBounds(window, out int left, out int top, out int right, out int bottom))
            return false;
        return right - left >= 200 && bottom - top >= 150;
    }

    // EnumWindows walks top-level windows from the top of the Z order down:
    // the first visible, titled, uncloaked, non-tool window of another
    // process with a real surface is what the person sees in front.
    private static nint TopmostForeignWindow()
    {
        nint found = 0;
        uint self = unchecked((uint)Environment.ProcessId);
        EnumWindowsProc callback = (window, _) =>
        {
            if (!IsWindowVisible(window) || GetAncestor(window, 3) != window)
                return true;
            if ((GetWindowLongPtrW(window, -20).ToInt64() & 0x80) != 0)
                return true;
            GetWindowThreadProcessId(window, out uint owner);
            if (owner == 0 || owner == self)
                return true;
            if (!HasUsableSurface(window))
                return true;
            found = window;
            return false;
        };
        _ = EnumWindows(callback, nint.Zero);
        return found;
    }

    [UnmanagedFunctionPointer(CallingConvention.Winapi)]
    private delegate bool EnumWindowsProc(nint window, nint lParam);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool SetForegroundWindow(nint hwnd);

    [LibraryImport("user32.dll")]
    private static partial int GetWindowTextLengthW(nint hwnd);

    [LibraryImport("user32.dll")]
    private static partial nint GetWindowLongPtrW(nint hwnd, int index);

    [LibraryImport("dwmapi.dll")]
    private static partial int DwmGetWindowAttribute(
        nint hwnd, int attribute, out int value, int size);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool EnumWindows(EnumWindowsProc callback, nint lParam);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsWindowVisible(nint window);

    [LibraryImport("user32.dll")]
    private static partial uint GetWindowThreadProcessId(nint window, out uint processId);

    [LibraryImport("user32.dll")]
    private static partial nint GetForegroundWindow();

    [LibraryImport("user32.dll")]
    private static partial nint GetAncestor(nint hwnd, uint flags);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool GetWindowRect(nint hwnd, out Rect rect);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool SetCursorPos(int x, int y);

    [LibraryImport("user32.dll")]
    private static partial void mouse_event(
        uint flags, uint dx, uint dy, uint data, nuint extra);

    [LibraryImport("dwmapi.dll")]
    private static partial int DwmGetWindowAttribute(
        nint hwnd, int attribute, out Rect rect, int size);

    [StructLayout(LayoutKind.Sequential)]
    private unsafe struct ProcessEntry32
    {
        public uint Size;
        public uint Usage;
        public uint ProcessId;
        public nint DefaultHeapId;
        public uint ModuleId;
        public uint Threads;
        public uint ParentProcessId;
        public int PriorityClassBase;
        public uint Flags;
        public fixed ushort ExeFile[260];
    }

    [LibraryImport("kernel32.dll", SetLastError = true)]
    private static partial nint CreateToolhelp32Snapshot(uint flags, uint processId);

    [LibraryImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool Process32FirstW(nint snapshot, ref ProcessEntry32 entry);

    [LibraryImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool Process32NextW(nint snapshot, ref ProcessEntry32 entry);

    [LibraryImport("kernel32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool CloseHandle(nint handle);

    [LibraryImport("kernel32.dll")]
    private static partial uint GetCurrentThreadId();

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool AttachThreadInput(
        uint attach, uint attachTo, [MarshalAs(UnmanagedType.Bool)] bool doAttach);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool BringWindowToTop(nint window);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool ShowWindowAsync(nint window, int command);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsIconic(nint window);

    internal readonly record struct OpenedApplication(
        int ProcessId,
        DateTime StartedUtc,
        DateTime NotedUtc,
        bool Launched);

    internal readonly record struct CapturedWindow(
        nint Hwnd,
        string Path,
        int Left,
        int Top,
        int Width,
        int Height,
        string Sha256);
}
