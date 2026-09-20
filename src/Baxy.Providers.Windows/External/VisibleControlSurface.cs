using System.Runtime.InteropServices;
using Baxy.Providers.Windows.Capture;

namespace Baxy.Providers.Windows.External;

internal static partial class VisibleControlSurface
{
    internal static async ValueTask<CapturedWindow?> CaptureForegroundAsync(
        CancellationToken cancellationToken)
    {
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

    private static nint FrameHosting(uint processId)
    {
        nint frame = 0;
        EnumWindowsProc callback = (window, outerParameter) =>
        {
            if (!IsWindowVisible(window) || ClassName(window) != "ApplicationFrameWindow")
                return true;
            bool hosts = false;
            EnumWindowsProc children = (child, innerParameter) =>
            {
                GetWindowThreadProcessId(child, out uint owner);
                if (owner == processId)
                {
                    hosts = true;
                    return false;
                }

                return true;
            };
            _ = EnumChildWindows(window, children, nint.Zero);
            if (!hosts)
                return true;
            frame = window;
            return false;
        };
        _ = EnumWindows(callback, nint.Zero);
        return frame;
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

    internal readonly record struct CapturedWindow(
        nint Hwnd,
        string Path,
        int Left,
        int Top,
        int Width,
        int Height,
        string Sha256);
}
