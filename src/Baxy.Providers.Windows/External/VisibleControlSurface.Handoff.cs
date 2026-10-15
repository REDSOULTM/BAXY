namespace Baxy.Providers.Windows.External;

/// <summary>
/// Ronda 20b, palanca 8, objetivo 3 (pasada r18, v3-44): a click may hand its effect to a window of another process. In
/// the Control Panel «Ver dispositivos e impresoras» makes Windows open Settings in its frame host: the Control Panel's
/// own image stays the same, and the click was told unchanged although its page was in front. The root windows on the
/// desktop are taken before the click; one born during the click's post-read, or one already there that took the front
/// then, of a process that does not draw the clicked window, is the window the click handed its effect to, unless the
/// person gave any input meanwhile (a click, a switch, a key: review 3, B1).
/// </summary>
internal static partial class VisibleControlSurface
{
    /// <summary>A root window of the desktop: its handle and the process a view names for it (the hosted app's for a
    /// packaged app's frame).</summary>
    internal readonly record struct RootWindow(nint Window, int ProcessId);

    /// <summary>The desktop's usable root windows (top of the Z order first), the root window in front, the processes
    /// that draw the clicked window and the person's last input that reaches a window (<see cref="PersonInputMark"/>),
    /// at one moment.</summary>
    internal sealed record RootSnapshot(
        IReadOnlyList<RootWindow> Windows, nint Front, IReadOnlySet<int> Clicked, long PersonInput);

    /// <summary>
    /// Review 3 of palanca 8 (B1): the person's input a handoff is measured against is any that reaches a window (a key
    /// going down or up, a mouse button, the wheel), not only one that moves the front: Ctrl+N in their editor, or Enter
    /// on a file in their folder, opens a window of theirs with no click and no Alt or Windows key.
    /// </summary>
    internal static long PersonInputMark(IUserInputPause pause) => pause.LastReachingInputMs;

    /// <summary>The window a click handed its effect to, as the receipt names it; <paramref name="Born"/> when it came
    /// with the click (not one already open that took the front): only such a window is the mission's to clean up.
    /// <paramref name="PersonInputAgoMs"/>: how long ago the person's last input went to it;
    /// <paramref name="PersonNearAgoMs"/>: to its process or the shell (null when none or not told): what the mission's
    /// guard of the person's windows reads (review 3, B1).</summary>
    internal readonly record struct HandedWindow(
        nint Window, int ProcessId, string Process, string Title, bool Born = false, long? PersonInputAgoMs = null,
        long? PersonNearAgoMs = null);

    /// <summary>
    /// The window <paramref name="now"/> shows that the click handed its effect to: of a process that does not draw
    /// the clicked window, born since <paramref name="before"/> (the topmost one) or, already there, now in front when
    /// it was not; none when the person's input came in between (their own switch, click or key). 0 when none.
    /// </summary>
    internal static RootWindow HandedTo(RootSnapshot before, RootSnapshot now) => HandedTo(before, now, out _);

    /// <inheritdoc cref="HandedTo(RootSnapshot, RootSnapshot)"/>
    internal static RootWindow HandedTo(RootSnapshot before, RootSnapshot now, out bool born)
    {
        born = false;
        if (now.PersonInput != before.PersonInput)
            return default;
        var earlier = new HashSet<nint>(before.Windows.Select(window => window.Window));
        foreach (RootWindow window in now.Windows)
        {
            if (window.Window == 0 || window.ProcessId <= 0 || before.Clicked.Contains(window.ProcessId))
                continue;
            if (!earlier.Contains(window.Window))
            {
                born = true;
                return window;
            }
        }

        if (now.Front != 0 && now.Front != before.Front && earlier.Contains(now.Front)
            && now.Windows.FirstOrDefault(window => window.Window == now.Front) is { Window: not 0 } forward
            && forward.ProcessId > 0 && !before.Clicked.Contains(forward.ProcessId))
            return forward;
        return default;
    }

    /// <summary>The desktop's root windows now, for a click on <paramref name="clicked"/>.</summary>
    internal static RootSnapshot RootWindowsNow(nint clicked)
    {
        var windows = new List<RootWindow>();
        uint self = unchecked((uint)Environment.ProcessId);
        EnumWindowsProc callback = (window, _) =>
        {
            if (!IsWindowVisible(window) || GetAncestor(window, 3) != window
                || (GetWindowLongPtrW(window, -20).ToInt64() & 0x80) != 0)
                return true;
            GetWindowThreadProcessId(window, out uint owner);
            if (owner == 0 || owner == self || IsShellSurface(window) || !HasUsableSurface(window))
                return true;
            uint hosted = HostedProcess(window);
            windows.Add(new RootWindow(window, unchecked((int)(hosted != 0 ? hosted : owner))));
            return true;
        };
        _ = EnumWindows(callback, nint.Zero);
        nint front = GetForegroundWindow();
        var drawing = new HashSet<int>(DrawingProcesses(clicked));
        if (clicked != 0 && ViewProcess(clicked).ProcessId is > 0 and int viewed)
            drawing.Add(viewed);
        return new RootSnapshot(
            windows, front == 0 ? 0 : GetAncestor(front, 2), drawing, PersonInputMark(WindowsUserInputPause.Shared));
    }

    /// <summary>
    /// The handed window as the receipt names it; null when it is gone or is a window the mission never acts on (an
    /// editor, a console, BAXY: «Seguridad v2», told by its process).
    /// </summary>
    internal static HandedWindow? DescribeHanded(RootWindow window)
    {
        if (window.Window == 0 || !IsAlive(window.Window))
            return null;
        string process = ProcessIdentity(unchecked((uint)window.ProcessId)).ProcessName;
        if (ProtectedFrom(process, null))
            return null;
        WindowsUserInputPause pause = WindowsUserInputPause.Shared;
        return new HandedWindow(
            window.Window, window.ProcessId, process, WindowTitle(window.Window),
            PersonInputAgoMs: pause.PersonInputAgoMs(window.Window),
            PersonNearAgoMs: pause.PersonInputToProcessesAgoMs(
                ProcessOf(window.Window), unchecked((uint)window.ProcessId), ShellProcessId));
    }
}
