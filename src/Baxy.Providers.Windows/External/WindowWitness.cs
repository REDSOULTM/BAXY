using System.Runtime.InteropServices;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// Ajuste c3 (E017: Ctrl+S sent to Windows 11 Notepad in Spanish, whose «Guardar» is Ctrl+G, came back completed with
/// nothing opened, 16 of 16 times): what a keyboard shortcut can visibly change of the window it went to, read by Win32
/// with no effect: its title (a document saved or closed), whether it is enabled (a modal dialog opened over it), the
/// visible top-level windows of its process (a dialog, a menu, a new window) and the window in front. Equal before and
/// after the shortcut, nothing of that changed: the receipt says so instead of a mute «completed».
/// </summary>
internal readonly partial record struct WindowWitness(string Title, bool Enabled, string Windows, nint Front)
{
    /// <summary>Live: the window's witness now; null for no window.</summary>
    internal static WindowWitness? Read(nint window)
    {
        if (window == 0 || !Native.IsWindow(window))
            return null;
        _ = Native.GetWindowThreadProcessId(window, out uint process);
        var shown = new List<long>();
        Native.EnumProc each = (top, _) =>
        {
            if (Native.IsWindowVisible(top) && Native.GetWindowThreadProcessId(top, out uint owner) != 0 && owner == process)
                shown.Add(top);
            return true;
        };
        _ = Native.EnumWindows(each, 0);
        GC.KeepAlive(each);
        shown.Sort();
        return new WindowWitness(Native.Title(window), Native.IsWindowEnabled(window), string.Join(",", shown),
            Native.GetForegroundWindow());
    }

    private static partial class Native
    {
        internal delegate bool EnumProc(nint hwnd, nint parameter);

        internal static unsafe string Title(nint hwnd)
        {
            char* buffer = stackalloc char[512];
            int length = GetWindowTextW(hwnd, buffer, 512);
            return length <= 0 ? string.Empty : new string(buffer, 0, length);
        }

        [LibraryImport("user32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        internal static partial bool EnumWindows(EnumProc callback, nint parameter);

        [LibraryImport("user32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        internal static partial bool IsWindow(nint hwnd);

        [LibraryImport("user32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        internal static partial bool IsWindowVisible(nint hwnd);

        [LibraryImport("user32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        internal static partial bool IsWindowEnabled(nint hwnd);

        [LibraryImport("user32.dll")]
        internal static partial uint GetWindowThreadProcessId(nint hwnd, out uint processId);

        [LibraryImport("user32.dll")]
        internal static partial nint GetForegroundWindow();

        [LibraryImport("user32.dll", StringMarshalling = StringMarshalling.Utf16)]
        private static unsafe partial int GetWindowTextW(nint hwnd, char* text, int count);
    }
}
