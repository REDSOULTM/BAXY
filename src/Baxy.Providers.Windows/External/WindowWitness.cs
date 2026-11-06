using System.Runtime.InteropServices;

namespace Baxy.Providers.Windows.External;

/// <summary>Encargo 98: a dialog a shortcut raised, as <see cref="WindowWitness.RaisedSince"/> finds it.</summary>
internal readonly record struct RaisedWindow(nint Window, string Title);

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

    /// <summary>The windows of <paramref name="after"/> that <paramref name="before"/> did not show.</summary>
    internal static IReadOnlyList<long> NewWindows(WindowWitness before, WindowWitness after)
    {
        HashSet<string> known = [.. before.Windows.Split(',')];
        return [.. after.Windows.Split(',', StringSplitOptions.RemoveEmptyEntries)
            .Where(known.Add)
            .Select(long.Parse)];
    }

    /// <summary>
    /// Encargo 98: a dialog that appeared in the window's process since <paramref name="before"/>: owned by another window,
    /// with a caption and a title (WS_CAPTION; a tooltip is owned too and has none); null when none did.
    /// </summary>
    internal static RaisedWindow? RaisedSince(WindowWitness before, nint window)
    {
        if (Read(window) is not { } now)
            return null;
        foreach (long raised in NewWindows(before, now))
        {
            nint handle = (nint)raised;
            if (Native.GetWindow(handle, GetWindowOwner) != 0
                && (Native.GetWindowLongPtrW(handle, WindowStyle) & CaptionStyle) == CaptionStyle
                && Native.Title(handle) is { Length: > 0 } title)
                return new RaisedWindow(handle, title);
        }

        return null;
    }

    /// <summary>
    /// Encargo 98: a dialog takes WM_CLOSE as its Cancel (Dialog Box Default Message Processing: «Posts the BN_CLICKED
    /// notification message to the dialog box, specifying IDCANCEL»); whether it is gone within <see cref="CloseWaitMs"/>.
    /// </summary>
    internal static bool Close(nint raised)
    {
        if (!Native.PostMessageW(raised, WindowClose, 0, 0))
            return false;
        for (int waited = 0; waited < CloseWaitMs; waited += ClosePollMs)
        {
            if (!Native.IsWindow(raised))
                return true;
            Thread.Sleep(ClosePollMs);
        }

        return !Native.IsWindow(raised);
    }

    private const uint GetWindowOwner = 4;
    private const int WindowStyle = -16;
    private const long CaptionStyle = 0x00C00000;
    private const uint WindowClose = 0x0010;
    private const int CloseWaitMs = 1500;
    private const int ClosePollMs = 50;

    private static partial class Native
    {
        internal delegate bool EnumProc(nint hwnd, nint parameter);

        [LibraryImport("user32.dll")]
        internal static partial nint GetWindow(nint hwnd, uint command);

        [LibraryImport("user32.dll")]
        internal static partial nint GetWindowLongPtrW(nint hwnd, int index);

        [LibraryImport("user32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        internal static partial bool PostMessageW(nint hwnd, uint message, nint wParam, nint lParam);

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
