namespace Baxy.Providers.Windows.External;

/// <summary>
/// Goal v3 ventana-misión (t-long-2, pasada r9): a mission is tied to the window it opened, created or was named, not
/// to its application's process. Measured live: Word's one process held the document BAXY created and, after a click on
/// a recent file, the owner's thesis; the look bound to the process took the window in front, the thesis, and Ctrl+A,
/// Escape and ribbon clicks went there. The look of a mission with its windows reads one of them, or a window of the
/// process that was not there when the mission took its window (one that came during the mission: a dialog, a window
/// an act of it opened), which the mission then keeps or refuses; never a window it already knew to be another one.
/// </summary>
internal static partial class VisibleControlSurface
{
    /// <summary>
    /// The window a mission's look reads: a usable top-level window of <paramref name="processId"/> that is neither
    /// one of the mission's windows nor one it knows (the topmost one: it came during the mission, and
    /// <paramref name="born"/> says so), else the first of <paramref name="missionWindows"/> (the latest first) still
    /// alive; 0 when none is. A process drawn inside a packaged app's frame has the frame as its window and its own
    /// top-level windows are its pop-ups: none of them is taken as a new window.
    /// </summary>
    internal static nint MissionWindow(
        IReadOnlyList<nint> missionWindows, IReadOnlySet<nint> known, int processId, out bool born)
    {
        uint process = unchecked((uint)processId);
        nint fresh = process == 0 || FrameHosting(process) != 0
            ? 0
            : BornWindow(TopLevelWindowsOf(process), process, missionWindows, known);
        return ChooseMissionWindow(missionWindows, fresh, IsAlive, out born);
    }

    /// <summary>
    /// The topmost (the Z order of <paramref name="windows"/>, top first) usable window of the process that is not
    /// one of the mission's, nor a known one, nor the family pair of one of them (the content a process the
    /// application started draws over its window is that window); 0 when none is.
    /// </summary>
    internal static nint BornWindow(
        IEnumerable<TopLevelWindow> windows, uint processId, IReadOnlyCollection<nint> missionWindows, IReadOnlySet<nint> known)
    {
        foreach (TopLevelWindow window in windows)
        {
            if (window.ProcessId != processId || !window.Usable || missionWindows.Contains(window.Window)
                || known.Contains(window.Window))
                continue;
            nint peer = FamilyPeer(window.Window);
            if (peer != 0 && (missionWindows.Contains(peer) || known.Contains(peer)))
                continue;
            return window.Window;
        }

        return 0;
    }

    /// <summary>The window that came during the mission when there is one, else the first mission window alive.</summary>
    internal static nint ChooseMissionWindow(
        IReadOnlyList<nint> missionWindows, nint fresh, Func<nint, bool> alive, out bool born)
    {
        born = fresh != 0;
        if (born)
            return fresh;
        foreach (nint window in missionWindows)
        {
            if (alive(window))
                return window;
        }

        return 0;
    }

    /// <summary>
    /// The application's own top-level window behind a surface: the application's window when
    /// <paramref name="surface"/> is the content a process it started draws over it, else the surface itself.
    /// </summary>
    internal static nint ApplicationRoot(nint surface) =>
        SurfaceFamily(surface) is not null && FamilyPeer(surface) is var peer and not 0 ? peer : surface;

    /// <summary>The window that owns <paramref name="window"/> at the root of its owner chain; 0 when it owns itself.</summary>
    internal static nint RootOwner(nint window)
    {
        if (window == 0)
            return 0;
        nint owner = GetAncestor(window, 3);
        return owner == 0 || owner == window ? 0 : owner;
    }

    /// <summary>
    /// The other usable or minimized top-level windows of the process of <paramref name="window"/>, top first: what was
    /// already there when the mission took that window (another document of the same application, the person's). A
    /// minimized one is not usable, and restored later it would come back as born (review of ventana-misión, finding 1).
    /// </summary>
    internal static IReadOnlyList<nint> OtherWindowsOfProcess(nint window)
    {
        if (window == 0 || GetWindowThreadProcessId(window, out uint process) == 0 || process == 0)
            return [];
        return [.. TopLevelWindowsOf(process)
            .Where(other => other.Window != window && (other.Usable || MinimizedDocumentWindow(other.Window)))
            .Select(other => other.Window)];
    }

    // A minimized top-level window a person would restore: titled, uncloaked, no shell surface.
    private static bool MinimizedDocumentWindow(nint window) =>
        IsIconic(window) && GetWindowTextLengthW(window) > 0 && !IsShellSurface(window)
        && !(DwmGetWindowAttribute(window, 14, out int cloaked, sizeof(int)) == 0 && cloaked != 0);

    /// <summary>The process of a window; 0 when it cannot be told.</summary>
    internal static uint ProcessOf(nint window) =>
        window != 0 && GetWindowThreadProcessId(window, out uint process) != 0 ? process : 0;

    /// <summary>The process that holds the desktop and the taskbar (where a person opens or restores a window).</summary>
    internal static uint ShellProcessId => ShellProcess();
}
