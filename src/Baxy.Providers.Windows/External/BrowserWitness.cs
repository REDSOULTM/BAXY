using System.Diagnostics;
using System.Runtime.InteropServices;

namespace Baxy.Providers.Windows.External;

/// <summary>Encargo 100: a window of a browser, as <see cref="BrowserWitness"/> reads it.</summary>
internal readonly record struct BrowserWindow(long Window, int Process, string Title);

/// <summary>Encargo 100: what a shortcut opened in a browser: a window of its own, or a tab in the window that took the front.</summary>
internal readonly record struct BrowserOpened(nint Window, string Title, bool OwnWindow);

/// <summary>Encargo 100: what the browsers show since a shortcut: what it opened, or that something may still be coming.</summary>
internal readonly record struct BrowserSighting(
    BrowserOpened? Opened, bool FrontMoved, bool Starting, IReadOnlyList<BrowserWindow>? Retitled = null);

/// <summary>
/// Encargo 100: a menu's shortcut can open the person's browser with their selected text in its address (an editor in Spanish
/// binds Ctrl+F to a web search). What a key opened shows only outside the window it went to: the windows of the browsers Windows
/// has registered (Clients\StartMenuInternet and the default one, so no program is named here), read by Win32 with no effect.
/// </summary>
internal sealed partial record BrowserWitness(IReadOnlyList<BrowserWindow> Windows, IReadOnlySet<string> Running, long Front)
{
    internal static BrowserWitness Read()
    {
        IReadOnlySet<string> names = UserBrowserIdentityResolver.RegisteredProcessNames();
        var running = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var owners = new HashSet<int>();
        foreach (Process process in Process.GetProcesses())
        {
            using (process)
            {
                if (names.Contains(process.ProcessName))
                {
                    running.Add(process.ProcessName);
                    owners.Add(process.Id);
                }
            }
        }

        var windows = new List<BrowserWindow>();
        Native.EnumProc each = (top, _) =>
        {
            if (Native.IsWindowVisible(top) && Native.GetWindow(top, GetWindowOwner) == 0
                && Native.GetWindowThreadProcessId(top, out uint owner) != 0 && owners.Contains((int)owner)
                && Native.Title(top) is { Length: > 0 } title)
                windows.Add(new BrowserWindow(top, (int)owner, title));
            return true;
        };
        _ = Native.EnumWindows(each, 0);
        GC.KeepAlive(each);
        return new BrowserWitness(windows, running, Native.GetForegroundWindow());
    }

    /// <summary>
    /// What the key opened, between two reads. A window that was not there is one, and so is another title on the window that
    /// took the front. Behind the front a title alone proves nothing (a chat counts unread messages in it by itself, and closing
    /// on that would lose a tab of the person's): it is only reported, for its tabs to be counted. The process the key went to
    /// is left out: a new tab there is what its own Ctrl+T is for.
    /// </summary>
    internal static BrowserSighting Since(BrowserWitness before, BrowserWitness now, int sentToProcess)
    {
        Dictionary<long, string> known = before.Windows.ToDictionary(static shown => shown.Window, static shown => shown.Title);
        foreach (BrowserWindow shown in now.Windows)
        {
            if (shown.Process != sentToProcess && !known.ContainsKey(shown.Window))
                return new BrowserSighting(new BrowserOpened((nint)shown.Window, shown.Title, true), false, false);
        }

        bool frontMoved = false;
        List<BrowserWindow>? retitled = null;
        foreach (BrowserWindow shown in now.Windows)
        {
            if (shown.Process == sentToProcess || !known.TryGetValue(shown.Window, out string? title))
                continue;
            bool sameTitle = string.Equals(title, shown.Title, StringComparison.Ordinal);
            if (shown.Window != now.Front)
            {
                if (!sameTitle)
                    (retitled ??= []).Add(shown);
                continue;
            }

            if (!sameTitle)
                return new BrowserSighting(new BrowserOpened((nint)shown.Window, shown.Title, false), false, false);
            frontMoved = before.Front != now.Front;
        }

        // A new process of a browser already running is a helper of its tabs: only one that was not running is on its way.
        return new BrowserSighting(null, frontMoved, now.Running.Any(name => !before.Running.Contains(name)), retitled);
    }

    // A window that took the front waits for its page's title; a browser starting cold has no window for seconds.
    private const int FrontWaitMs = 1500;
    private const int StartWaitMs = 8000;
    private const int PollMs = 100;

    /// <summary>The process of a window; 0 when it has none.</summary>
    internal static int ProcessOf(nint window) =>
        Native.GetWindowThreadProcessId(window, out uint process) == 0 ? 0 : (int)process;

    // Measured live: with the browser already open, its new tab does not take the front; half a second after the key its window
    // has one tab more and another title. The tabs are counted before the act, for that to be told from a title changing alone.
    internal async ValueTask<Dictionary<long, int>> TabsBehindAsync(
        int sentToProcess, Func<nint, CancellationToken, ValueTask<int?>> tabCount, CancellationToken cancellationToken)
    {
        var tabs = new Dictionary<long, int>();
        foreach (BrowserWindow shown in Windows)
        {
            if (shown.Process != sentToProcess && await tabCount((nint)shown.Window, cancellationToken).ConfigureAwait(false) is int count)
                tabs[shown.Window] = count;
        }

        return tabs;
    }

    /// <summary>
    /// What an act opened, looked at until it shows: <paramref name="quietMs"/> when nothing is on its way yet. A browser that went
    /// on starting past its wait is said with no title: it did start.
    /// </summary>
    internal static async ValueTask<BrowserOpened?> AwaitOpenedAsync(
        Func<BrowserSighting> sight,
        IReadOnlyDictionary<long, int>? tabsBefore,
        Func<nint, CancellationToken, ValueTask<int?>>? tabCount,
        int quietMs,
        CancellationToken cancellationToken)
    {
        for (int waited = 0; ; waited += PollMs)
        {
            BrowserSighting seen = sight();
            if (seen.Opened is { } opened)
                return opened;
            foreach (BrowserWindow shown in seen.Retitled ?? [])
            {
                if (tabsBefore is not null && tabCount is not null && tabsBefore.TryGetValue(shown.Window, out int tabs)
                    && await tabCount((nint)shown.Window, cancellationToken).ConfigureAwait(false) > tabs)
                    return new BrowserOpened((nint)shown.Window, shown.Title, false);
            }

            if (waited >= (seen.Starting ? StartWaitMs : seen.FrontMoved ? FrontWaitMs : quietMs))
                return seen.Starting ? new BrowserOpened(0, string.Empty, true) : null;
            await Task.Delay(PollMs, cancellationToken).ConfigureAwait(false);
        }
    }

    private const uint GetWindowOwner = 4;

    private static partial class Native
    {
        internal delegate bool EnumProc(nint hwnd, nint parameter);

        [LibraryImport("user32.dll")]
        internal static partial nint GetWindow(nint hwnd, uint command);

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
        internal static partial bool IsWindowVisible(nint hwnd);

        [LibraryImport("user32.dll")]
        internal static partial uint GetWindowThreadProcessId(nint hwnd, out uint processId);

        [LibraryImport("user32.dll")]
        internal static partial nint GetForegroundWindow();

        [LibraryImport("user32.dll", StringMarshalling = StringMarshalling.Utf16)]
        private static unsafe partial int GetWindowTextW(nint hwnd, char* text, int count);
    }
}
