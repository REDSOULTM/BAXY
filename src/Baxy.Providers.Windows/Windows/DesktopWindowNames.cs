using System.Diagnostics;
using System.Runtime.InteropServices;

namespace Baxy.Providers.Windows.Windows;

/// <summary>
/// BAXY Renew cu (C13): the windows open on the desktop, top of the Z order first, by process and title, for a
/// window.resolve whose application name matched nothing to name one exactly, with the person's browser. Unlike a look's list
/// (VisibleControlSurface.DestinationDesktop) a minimized window is listed too, marked: «el navegador» was a minimized
/// Opera. Root windows only: visible, not a tool window, not cloaked, with a title, not BAXY's own process.
/// </summary>
public static partial class DesktopWindowNames
{
    public static IReadOnlyList<(string Process, string Title)> Visible()
    {
        var windows = new List<(string, string)>();
        EnumWindowsProc callback = (window, _) =>
        {
            if (!IsWindowVisible(window) || GetAncestor(window, 3) != window
                || (GetWindowLongPtrW(window, -20).ToInt64() & 0x80) != 0
                || (DwmGetWindowAttribute(window, 14, out int cloaked, sizeof(int)) == 0 && cloaked != 0))
                return true;
            int length = GetWindowTextLengthW(window);
            if (length == 0)
                return true;
            var buffer = new char[length + 1];
            string title = new(buffer, 0, Math.Max(0, GetWindowTextW(window, buffer, buffer.Length)));
            WindowThreadProcessId(window, out uint owner);
            if (owner == 0)
                return true;
            string process;
            try
            {
                using Process running = Process.GetProcessById(unchecked((int)owner));
                process = running.ProcessName;
            }
            catch (ArgumentException)
            {
                return true;
            }

            // Renew al máximo (B-CU-2): BAXY's chat is Baxy.exe's window, not this process's.
            if (WindowsWindowControlProvider.OwnProcessNames.Contains(process))
                return true;
            windows.Add((process, IsIconic(window) ? title + " (minimizada)" : title));
            return true;
        };
        _ = EnumWindows(callback, nint.Zero);
        GC.KeepAlive(callback);
        return windows;
    }

    /// <summary>The person's web browser (the one Windows opens a link with): its name and process; null if unknown.</summary>
    public static (string Name, string Process)? PersonBrowser() =>
        External.UserBrowserIdentityResolver.ResolveFromRegistry() is { } browser
            ? (browser.DisplayName, browser.ProcessName)
            : null;

    private delegate bool EnumWindowsProc(nint window, nint parameter);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool EnumWindows(EnumWindowsProc callback, nint parameter);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsWindowVisible(nint window);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsIconic(nint window);

    [LibraryImport("user32.dll")]
    private static partial nint GetAncestor(nint window, uint flags);

    [LibraryImport("user32.dll")]
    private static partial nint GetWindowLongPtrW(nint window, int index);

    [LibraryImport("user32.dll")]
    private static partial int GetWindowTextLengthW(nint window);

    [LibraryImport("user32.dll", StringMarshalling = StringMarshalling.Utf16)]
    private static partial int GetWindowTextW(nint window, [Out] char[] text, int count);

    [LibraryImport("user32.dll", EntryPoint = "GetWindowThreadProcessId")]
    private static partial uint WindowThreadProcessId(nint window, out uint processId);

    [LibraryImport("dwmapi.dll")]
    private static partial int DwmGetWindowAttribute(nint window, int attribute, out int value, int size);
}
