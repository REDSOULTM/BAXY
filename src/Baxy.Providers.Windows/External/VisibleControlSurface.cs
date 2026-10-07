using System.Runtime.InteropServices;
using Baxy.Providers.Windows.Capture;

namespace Baxy.Providers.Windows.External;

internal static partial class VisibleControlSurface
{
    internal static async ValueTask<CapturedWindow?> CaptureForegroundAsync(
        CancellationToken cancellationToken)
    {
        // M132, measured live: the opened client's updater closed while its
        // label was looked for, the front fell to the person's editor, and
        // the word was read and pressed there. A click bound to the opened
        // application reads only that application's window.
        if (RequiredWindow.Value is var required and not 0)
            return ForegroundIs(required) ? await CaptureAsync(required, cancellationToken).ConfigureAwait(false) : null;
        nint hwnd = await ResolveForegroundAsync(cancellationToken).ConfigureAwait(false);
        return hwnd == 0
            ? null
            : await CaptureAsync(hwnd, cancellationToken).ConfigureAwait(false);
    }

    /// <summary>
    /// The window a person acts on right now: the root of the foreground
    /// window, or the topmost foreign window when the foreground is ours or
    /// has no usable surface. The compact view, the click and the scroll all
    /// resolve the window here, so they always mean the same one.
    /// </summary>
    internal static async ValueTask<nint> ResolveForegroundAsync(
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        nint hwnd = GetForegroundWindow();
        // While a window is changing hands (an application was just brought to
        // the front) the foreground is briefly nobody's: wait a little, then
        // take the topmost foreign window rather than answering «no window».
        for (int attempt = 0; hwnd == 0 && attempt < 6; attempt++)
        {
            await Task.Delay(200, cancellationToken).ConfigureAwait(false);
            hwnd = GetForegroundWindow();
        }
        if (hwnd == 0)
            hwnd = TopmostForeignWindow();
        if (hwnd == 0)
            return 0;
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
        // The desktop itself (Progman / WorkerW, «Program Manager») and the
        // taskbar are never the surface a person acts on: when nothing owns the
        // foreground the act lands on the topmost application window.
        if (foregroundProcess == unchecked((uint)Environment.ProcessId) || !HasUsableSurface(hwnd)
            || IsShellSurface(hwnd))
        {
            nint candidate = TopmostForeignWindow();
            if (candidate != 0)
            {
                BringToFront(candidate);
                await Task.Delay(250, cancellationToken).ConfigureAwait(false);
                hwnd = candidate;
            }
        }

        return hwnd;
    }

    /// <summary>
    /// The window of one process: its largest visible top-level window, or the
    /// ApplicationFrameHost frame hosting it (a UWP app such as the Calculator
    /// has no top-level window of its own). Brought to the front so keys and
    /// clicks land on it; 0 when the process shows nothing.
    /// </summary>
    internal static async ValueTask<nint> ResolveProcessWindowAsync(
        int processId,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        nint found = 0;
        for (int attempt = 0; found == 0 && attempt < 8; attempt++)
        {
            if (attempt > 0)
                await Task.Delay(250, cancellationToken).ConfigureAwait(false);
            found = LargestTopLevelWindow(processId);
            if (found == 0 || !HasUsableSurface(found))
                found = FrameHosting(unchecked((uint)processId));
        }

        if (found == 0)
            return 0;
        if (GetForegroundWindow() != found)
        {
            BringToFront(found);
            await Task.Delay(250, cancellationToken).ConfigureAwait(false);
        }

        return found;
    }

    /// <summary>
    /// The topmost visible window whose title names the application: the
    /// mission's target when its process is unknown (app.open did not verify,
    /// or the application was already there). Brought to the front; 0 when no
    /// window is titled that way. Title matching is generic: the folded
    /// application name inside the folded title.
    /// </summary>
    internal static async ValueTask<nint> ResolveTitledWindowAsync(
        string application,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        string wanted = FoldTitle(application);
        if (wanted.Length == 0)
            return 0;
        nint found = 0;
        uint self = unchecked((uint)Environment.ProcessId);
        EnumWindowsProc callback = (window, _) =>
        {
            if (!IsWindowVisible(window) || GetAncestor(window, 3) != window)
                return true;
            if ((GetWindowLongPtrW(window, -20).ToInt64() & 0x80) != 0)
                return true;
            GetWindowThreadProcessId(window, out uint owner);
            if (owner == 0 || owner == self || !HasUsableSurface(window))
                return true;
            if (!FoldTitle(WindowTitle(window)).Contains(wanted, StringComparison.Ordinal))
                return true;
            found = window;
            return false;
        };
        _ = EnumWindows(callback, nint.Zero);
        if (found == 0)
            return 0;
        if (GetForegroundWindow() != found)
        {
            BringToFront(found);
            await Task.Delay(250, cancellationToken).ConfigureAwait(false);
        }

        return found;
    }

    /// <summary>
    /// The root window of another process drawn over the centre of this one,
    /// or 0 when the window is what a person sees there. Measured: a fullscreen
    /// video player on top of a settings page and of a game launcher; the view read the player
    /// and a click would have landed on it.
    /// </summary>
    internal static nint CoveringWindow(nint hwnd)
    {
        if (!TryBounds(hwnd, out int left, out int top, out int right, out int bottom))
            return 0;
        var centre = new Point((left + right) / 2, (top + bottom) / 2);
        nint hit = WindowFromPoint(centre);
        if (hit == 0)
            return 0;
        nint root = GetAncestor(hit, 2);
        if (root == 0)
            root = hit;
        if (root == hwnd)
            return 0;
        _ = GetWindowThreadProcessId(root, out uint coverOwner);
        _ = GetWindowThreadProcessId(hwnd, out uint owner);
        // A window of the same process (a dialog, a menu, a popup) and this
        // product's own window are not covers.
        if (coverOwner == owner || coverOwner == unchecked((uint)Environment.ProcessId))
            return 0;
        return root;
    }

    internal static string FoldTitle(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
            return string.Empty;
        string decomposed = value.Normalize(System.Text.NormalizationForm.FormD);
        var builder = new System.Text.StringBuilder(decomposed.Length);
        bool pendingSpace = false;
        foreach (char character in decomposed)
        {
            if (System.Globalization.CharUnicodeInfo.GetUnicodeCategory(character)
                == System.Globalization.UnicodeCategory.NonSpacingMark)
            {
                continue;
            }

            if (char.IsWhiteSpace(character))
            {
                pendingSpace = builder.Length > 0;
                continue;
            }

            if (pendingSpace)
            {
                builder.Append(' ');
                pendingSpace = false;
            }

            builder.Append(char.ToLowerInvariant(character));
        }

        return builder.ToString();
    }

    /// <summary>
    /// The visible ApplicationFrameHost frame that hosts this process (a packaged app such as the Calculator, the
    /// Clock or Settings draws inside a frame of another process and has no top-level window of its own); 0 when
    /// none shows it. A cloaked frame (a suspended app) is not on screen.
    /// </summary>
    internal static nint FrameHosting(uint processId)
    {
        nint frame = 0;
        EnumWindowsProc callback = (window, outerParameter) =>
        {
            if (!IsVisibleFrame(window) || !FrameHosts(window, owner => owner == processId))
                return true;
            frame = window;
            return false;
        };
        _ = EnumWindows(callback, nint.Zero);
        return frame;
    }

    /// <summary>Every visible frame by the process it hosts, read in one pass over the desktop.</summary>
    internal static Dictionary<uint, nint> HostedFrames()
    {
        var frames = new Dictionary<uint, nint>();
        EnumWindowsProc callback = (window, outerParameter) =>
        {
            if (!IsVisibleFrame(window))
                return true;
            _ = FrameHosts(window, owner =>
            {
                frames.TryAdd(owner, window);
                return false;
            });
            return true;
        };
        _ = EnumWindows(callback, nint.Zero);
        return frames;
    }

    private static bool IsVisibleFrame(nint window) =>
        IsWindowVisible(window) && ClassName(window) == "ApplicationFrameWindow"
        && !(DwmGetWindowAttribute(window, 14, out int cloaked, sizeof(int)) == 0 && cloaked != 0);

    private static bool FrameHosts(nint frame, Func<uint, bool> hosted)
    {
        _ = GetWindowThreadProcessId(frame, out uint host);
        bool hosts = false;
        EnumWindowsProc children = (child, innerParameter) =>
        {
            GetWindowThreadProcessId(child, out uint owner);
            if (owner != host && hosted(owner))
            {
                hosts = true;
                return false;
            }

            return true;
        };
        _ = EnumChildWindows(frame, children, nint.Zero);
        return hosts;
    }

    private static bool IsShellSurface(nint window)
    {
        string className = ClassName(window);
        return className is "Progman" or "WorkerW" or "Shell_TrayWnd" or "Shell_SecondaryTrayWnd";
    }

    internal static string ClassName(nint window)
    {
        var buffer = new char[128];
        int copied = GetClassNameW(window, buffer, buffer.Length);
        return copied <= 0 ? string.Empty : new string(buffer, 0, copied);
    }

    /// <summary>
    /// Brings a window to the front the way the messaging adapter does: attached
    /// to the input of the thread that owns the foreground, so Windows accepts
    /// the request from this background process (a plain SetForegroundWindow is
    /// refused and the typed keys would go elsewhere).
    /// </summary>
    internal static bool BringToFront(nint window)
    {
        nint foreground = GetForegroundWindow();
        uint foregroundThread = GetWindowThreadProcessId(foreground, out _);
        uint currentThread = GetCurrentThreadId();
        bool attached = foregroundThread != 0
            && currentThread != foregroundThread
            && AttachThreadInput(currentThread, foregroundThread, true);
        try
        {
            if (IsIconic(window))
                _ = ShowWindow(window, 9);
            _ = BringWindowToTop(window);
            _ = SetForegroundWindow(window);
            return GetForegroundWindow() == window;
        }
        finally
        {
            if (attached)
                _ = AttachThreadInput(currentThread, foregroundThread, false);
        }
    }

    private static readonly AsyncLocal<nint> RequiredWindow = new();

    // Binds the reads and presses of the calls made inside the scope to one window: while it is not the one in
    // front, nothing is captured, so nothing is read or pressed elsewhere.
    internal static IDisposable RequireWindow(nint window)
    {
        nint previous = RequiredWindow.Value;
        RequiredWindow.Value = window;
        return new RequiredWindowScope(previous);
    }

    // The window in front is this one (or a window inside it).
    internal static bool ForegroundIs(nint window)
    {
        nint foreground = GetForegroundWindow();
        if (foreground == 0 || window == 0)
            return false;
        nint root = GetAncestor(foreground, 2);
        return (root == 0 ? foreground : root) == window;
    }

    private sealed class RequiredWindowScope(nint previous) : IDisposable
    {
        public void Dispose() => RequiredWindow.Value = previous;
    }

    internal static async ValueTask<CapturedWindow?> CaptureAsync(
        nint hwnd,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        if (hwnd == 0 || !TryBounds(hwnd, out int left, out int top, out _, out _))
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

    // The opened application's largest usable window, brought to the front, and whether it looks drawn; no window
    // while it has none yet (an updater or splash only, or nothing). Measured on a cold client launch: its main
    // window came up with the navigation bar over a black page (one colour on 76–96 % of the window) for about
    // three seconds, and a click on the bar then was undone when the client loaded its start page; once the page
    // is drawn, one colour covers about a third. A pop-up of the same application over the main window (a chat)
    // is not what a person opening the application acts on: the main window is brought back in front.
    internal static async ValueTask<OpenedSurface> FrontOpenedAsync(
        OpenedApplication opened,
        bool judgeDrawn,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        HashSet<uint> family = ProcessFamily(opened);
        if (family.Count == 0)
            return default;
        nint target = LargestUsableWindow(family);
        if (target == 0)
            return default;
        nint foreground = GetForegroundWindow();
        nint root = foreground == 0 ? 0 : GetAncestor(foreground, 2);
        // Measured: the chat pop-up came up over the main window without taking the focus, so the main window was
        // the foreground and still covered where its navigation is.
        if ((root == 0 ? foreground : root) != target || CoveredFromAbove(target))
        {
            BringToFront(target);
            await Task.Delay(250, cancellationToken).ConfigureAwait(false);
        }

        if (!judgeDrawn)
            return new OpenedSurface(target, Drawn: true);
        double? share = await DominantColourShareAsync(target, cancellationToken).ConfigureAwait(false);
        return new OpenedSurface(target, Drawn: share is not { } measured || measured < BlankShare);
    }

    // One colour over this share of a window is a page still to be drawn (black, white or a spinner on a plain
    // background); a drawn page measured about a third.
    private const double BlankShare = 0.7;

    private static async ValueTask<double?> DominantColourShareAsync(
        nint window,
        CancellationToken cancellationToken)
    {
        string directory = Path.Combine(Path.GetTempPath(), "baxy-visible-control");
        string? path = null;
        try
        {
            var provider = new WindowsScreenshotProvider(directory);
            CaptureResult capture = await provider.CaptureWindowAsync(window, cancellationToken)
                .ConfigureAwait(false);
            path = Path.Combine(directory, capture.CaptureId + ".bmp");
            byte[] bmp = await File.ReadAllBytesAsync(path, cancellationToken).ConfigureAwait(false);
            return DominantColourShare(bmp);
        }
        catch (Exception exception) when (exception is IOException or InvalidOperationException
            or UnauthorizedAccessException or ArgumentException)
        {
            return null;
        }
        finally
        {
            Delete(path);
        }
    }

    // 32-bit BGRA bitmap (the capture's own encoding): the share of sampled pixels in the commonest colour, each
    // channel quantised to sixteen levels.
    internal static double? DominantColourShare(byte[] bmp)
    {
        const int header = 54;
        if (bmp.Length <= header || bmp[0] != (byte)'B' || bmp[1] != (byte)'M'
            || BitConverter.ToInt16(bmp, 28) != 32)
        {
            return null;
        }
        int pixels = (bmp.Length - header) / 4;
        if (pixels == 0)
            return null;
        int step = Math.Max(1, pixels / 40_000);
        var counts = new int[4096];
        int sampled = 0;
        int best = 0;
        for (int index = 0; index < pixels; index += step)
        {
            int offset = header + index * 4;
            int bin = ((bmp[offset + 2] >> 4) << 8) | ((bmp[offset + 1] >> 4) << 4) | (bmp[offset] >> 4);
            best = Math.Max(best, ++counts[bin]);
            sampled++;
        }
        return (double)best / sampled;
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
            // A packaged app opened is drawn inside the frame that hosts it (its own process has no top-level window).
            bool owned = family.Contains(owner) || (IsVisibleFrame(window) && FrameHosts(window, family.Contains));
            if (!owned || !HasUsableSurface(window))
                return true;
            if (!TryBounds(window, out int left, out int top, out int right, out int bottom))
                return true;
            // An updater or splash (measured 500×161) is not the application's surface yet.
            if (right - left < 300 || bottom - top < 200)
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

    // A visible, uncloaked window that is not always-on-top and sits above the target in the Z order over part
    // of it (always-on-top windows stay above whatever is brought forward, so they are not counted).
    private static bool CoveredFromAbove(nint target)
    {
        if (!TryBounds(target, out int left, out int top, out int right, out int bottom))
            return false;
        bool covered = false;
        EnumWindowsProc callback = (window, unused) =>
        {
            if (window == target)
                return false;
            if (!IsWindowVisible(window) || (GetWindowLongPtrW(window, -20).ToInt64() & 0x8) != 0)
                return true;
            if (DwmGetWindowAttribute(window, 14, out int cloaked, sizeof(int)) == 0 && cloaked != 0)
                return true;
            if (!TryBounds(window, out int otherLeft, out int otherTop, out int otherRight, out int otherBottom))
                return true;
            if (otherLeft < right && otherRight > left && otherTop < bottom && otherBottom > top)
            {
                covered = true;
                return false;
            }
            return true;
        };
        _ = EnumWindows(callback, nint.Zero);
        return covered;
    }

    // A click bound to the opened application lands only while its window is still the one in front.
    internal static bool MayPress() =>
        RequiredWindow.Value == 0 || ForegroundIs(RequiredWindow.Value);

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

    internal static bool IsAlive(nint hwnd) => hwnd != 0 && IsWindow(hwnd) && IsWindowVisible(hwnd);

    internal static string WindowTitle(nint hwnd)
    {
        int length = GetWindowTextLengthW(hwnd);
        if (length <= 0)
            return string.Empty;
        var buffer = new char[Math.Min(length, 512) + 1];
        int copied = GetWindowTextW(hwnd, buffer, buffer.Length);
        return copied <= 0 ? string.Empty : new string(buffer, 0, copied);
    }

    internal static (int ProcessId, string ProcessName) WindowProcess(nint hwnd)
    {
        _ = GetWindowThreadProcessId(hwnd, out uint processId);
        if (processId == 0)
            return (0, string.Empty);
        try
        {
            using var process = System.Diagnostics.Process.GetProcessById(unchecked((int)processId));
            return (unchecked((int)processId), process.ProcessName);
        }
        catch (Exception exception) when (exception is ArgumentException or InvalidOperationException)
        {
            return (unchecked((int)processId), string.Empty);
        }
    }

    internal static bool TryBounds(nint hwnd, out int left, out int top, out int right, out int bottom)
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
            // Measured live: a File Explorer window belongs to explorer.exe, which also owns the desktop and the
            // taskbar; the desktop is the largest of them and is always covered. Shell surfaces are never the
            // window of an application.
            if (IsShellSurface(window) || !GetWindowRect(window, out Rect rect))
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

    [LibraryImport("user32.dll", StringMarshalling = StringMarshalling.Utf16)]
    private static partial int GetClassNameW(nint hwnd, [Out] char[] text, int count);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool AttachThreadInput(uint idAttach, uint idAttachTo, [MarshalAs(UnmanagedType.Bool)] bool attach);

    [LibraryImport("kernel32.dll")]
    private static partial uint GetCurrentThreadId();

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool BringWindowToTop(nint hwnd);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool ShowWindow(nint hwnd, int command);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsIconic(nint hwnd);

    [LibraryImport("user32.dll", StringMarshalling = StringMarshalling.Utf16)]
    private static partial int GetWindowTextW(nint hwnd, [Out] char[] text, int count);

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
    private static partial bool EnumChildWindows(nint parent, EnumWindowsProc callback, nint lParam);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsWindowVisible(nint window);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsWindow(nint window);

    [LibraryImport("user32.dll")]
    private static partial uint GetWindowThreadProcessId(nint window, out uint processId);

    [LibraryImport("user32.dll")]
    private static partial nint GetForegroundWindow();

    [LibraryImport("user32.dll")]
    private static partial nint WindowFromPoint(Point point);

    [StructLayout(LayoutKind.Sequential)]
    private struct Point(int x, int y)
    {
        public int X = x;
        public int Y = y;
    }

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

    internal readonly record struct OpenedSurface(nint Window, bool Drawn);

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
