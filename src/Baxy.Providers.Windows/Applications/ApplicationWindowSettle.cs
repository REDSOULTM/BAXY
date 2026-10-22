using System.Diagnostics;
using System.Runtime.InteropServices;

namespace Baxy.Providers.Windows.Applications;

/// <summary>
/// BAXY Renew cu (C03 en frío): an application that starts behind its own sign-in (Steam: an updater, then «Iniciar
/// sesión en Steam», then its window) shows first a window that goes away; a place handed to it then is lost. This waits
/// until the window the opening verified is gone and a visible window with the application's own name (its window
/// title, as the Start catalog names it) and the size of a main window (Steam's updater, titled «Steam» too, is a small
/// box) has stayed for a moment, and gives that window; 0 when the budget ran out. Al máximo, flujos: it waits without
/// holding a thread (it runs inside app.open, under the engine's one execution at a time).
/// </summary>
public static partial class ApplicationWindowSettle
{
    private static readonly TimeSpan Poll = TimeSpan.FromMilliseconds(250);

    // A main window, not a splash, an updater or a sign-in box (Steam's updater measured about 400 x 180).
    internal const int MainWidth = 600;
    internal const int MainHeight = 400;

    public static async ValueTask<long> WaitSettledAsync(
        long openedWindow, string applicationName, TimeSpan budget, CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(applicationName))
            return 0;
        var watch = Stopwatch.StartNew();
        long seen = 0;
        while (watch.Elapsed < budget)
        {
            cancellationToken.ThrowIfCancellationRequested();
            bool openedGone = openedWindow == 0 || !IsWindow((nint)openedWindow) || !IsWindowVisible((nint)openedWindow);
            long named = openedGone ? Named(applicationName.Trim(), openedWindow) : 0;
            // Seen twice in a row: a window that stayed, not one drawn on the way.
            if (named != 0 && named == seen)
                return named;
            seen = named;
            await Task.Delay(Poll, cancellationToken).ConfigureAwait(false);
        }

        return 0;
    }

    // The first visible root window titled exactly as the application is named (case aside), other than the opened one.
    private static long Named(string name, long openedWindow)
    {
        long found = 0;
        EnumWindowsProc callback = (window, _) =>
        {
            if (window == (nint)openedWindow || !IsWindowVisible(window) || GetAncestor(window, 3) != window)
                return true;
            int length = GetWindowTextLengthW(window);
            if (length != name.Length)
                return true;
            var buffer = new char[length + 1];
            string title = new(buffer, 0, Math.Max(0, GetWindowTextW(window, buffer, buffer.Length)));
            if (!string.Equals(title, name, StringComparison.OrdinalIgnoreCase)
                || !GetWindowRect(window, out Rect box) || box.Right - box.Left < MainWidth || box.Bottom - box.Top < MainHeight)
                return true;
            found = window;
            return false;
        };
        _ = EnumWindows(callback, nint.Zero);
        GC.KeepAlive(callback);
        return found;
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

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool GetWindowRect(nint window, out Rect rect);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool EnumWindows(EnumWindowsProc callback, nint parameter);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsWindow(nint window);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsWindowVisible(nint window);

    [LibraryImport("user32.dll")]
    private static partial nint GetAncestor(nint window, uint flags);

    [LibraryImport("user32.dll")]
    private static partial int GetWindowTextLengthW(nint window);

    [LibraryImport("user32.dll", StringMarshalling = StringMarshalling.Utf16)]
    private static partial int GetWindowTextW(nint window, [Out] char[] text, int count);
}
