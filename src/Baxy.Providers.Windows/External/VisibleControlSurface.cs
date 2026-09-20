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

    internal readonly record struct CapturedWindow(
        nint Hwnd,
        string Path,
        int Left,
        int Top,
        int Width,
        int Height,
        string Sha256);
}
