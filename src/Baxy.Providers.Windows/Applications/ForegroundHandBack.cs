using System.Runtime.InteropServices;
using Baxy.Providers.Windows.External;

namespace Baxy.Providers.Windows.Applications;

/// <summary>
/// v3 point 0 (arreglo 4): an application opened without the person asking to see it in front never keeps the front.
/// Windows activates some of them by itself (a packaged app through its activation manager, a browser shell that
/// ignores how it was asked to show); the window that had the front gets it back at once, and the opened window stays
/// right behind it.
/// </summary>
internal static partial class ForegroundHandBack
{
    internal static long Foreground() => GetForegroundWindow();

    // Every time BAXY takes the front on purpose (an act of a mission bringing its window up, keys sent to it): the
    // guard that hands back a front an opened application took by itself stops there, so it never undoes BAXY's own
    // act nor the person's (an input of theirs that can move the front ends it as well; r4a M2: typing does not).
    private static long _frontTaken;

    internal static void NoteFrontTaken() => Interlocked.Increment(ref _frontTaken);

    /// <summary>
    /// The front's common gate (r4a M4, w1): the foreground lease brings a window up under it, and a guard reads the
    /// front and hands it back under it, so a guard never hands back, between the lease's bringing and its check, the
    /// front a burst just took (measured: a packaged application just opened refused with input_window_not_in_front 1.2 s
    /// after its opening, inside the opening's guard).
    /// </summary>
    internal static readonly SemaphoreSlim FrontGate = new(1, 1);

    // The fronts an opened application took by itself after its opening was answered, handed back by the guard (v3
    // point 0, fix 4): counted here and told by the next look (view «windowsActivationsReturned»), since the opening's
    // receipt (its «windowsActivation») was already given. Only a hand-back read back as held counts; one Windows
    // refused is counted apart (view «windowsActivationsNotReturned», cu-v3-foco-segunda).
    private static long _guardReturns;
    private static long _guardRefusals;

    internal static void NoteGuardReturn(bool restored) =>
        Interlocked.Increment(ref restored ? ref _guardReturns : ref _guardRefusals);

    internal static long TakeGuardReturns() => Interlocked.Exchange(ref _guardReturns, 0);

    internal static long TakeGuardRefusals() => Interlocked.Exchange(ref _guardRefusals, 0);

    internal readonly record struct GuardStamp(long FrontTaken, long LastPersonInput);

    internal static GuardStamp Stamp() => new(Interlocked.Read(ref _frontTaken), LastPersonInput());

    // True when, since the stamp, BAXY took the front on purpose or the person did something that moves the front.
    internal static bool Interrupted(GuardStamp stamp) =>
        Interlocked.Read(ref _frontTaken) != stamp.FrontTaken || LastPersonInput() != stamp.LastPersonInput;

    // r4a M2: the guard decides by who moved the front, not by whether the person used the keyboard or the mouse. The
    // person typing in their own window does not make the opened application theirs (measured: v11, y11 and s13 kept
    // an application that took the front by itself because the person went on typing); only an input that can move
    // the front (a mouse button, Alt or the Windows key) can. The pause detector of fable/cu-v3-pausa tells it, and
    // falls back to any input of the person when it cannot tell.
    private static long LastPersonInput() => WindowsUserInputPause.Shared.LastFrontMovingInputMs;

    // v3 point 1: the last opening that left the person's window in front, for the looks while the application starts.
    private static readonly object OpeningGate = new();
    private static Opening? _opening;

    private sealed record Opening(long Previous, int ProcessId, long FrontTaken, DateTime NotedUtc)
    {
        internal long LastPersonInput { get; set; }

        // The window in front at the previous look (at the opening: the person's): a front is handed back only when it
        // moved to the application between two looks with no input of the person (review: a person who brought the
        // application up keeps it for the rest of the start, not only for the look right after their input).
        internal long LastFront { get; set; }
    }

    // How long after the opening a look still hands back a front the application took (the mission's start wait).
    internal static readonly TimeSpan StartHandBack = TimeSpan.FromSeconds(30);

    /// <summary>An application was opened behind the person's window <paramref name="previous"/>.</summary>
    internal static void NoteOpening(long previous, int processId) => NoteOpening(previous, processId, LastPersonInput());

    internal static void NoteOpening(long previous, int processId, long personInput)
    {
        if (previous == 0 || processId <= 0)
            return;
        lock (OpeningGate)
            _opening = new Opening(previous, processId, Interlocked.Read(ref _frontTaken), DateTime.UtcNow)
            {
                LastPersonInput = personInput,
                LastFront = previous,
            };
    }

    /// <summary>
    /// A look at the application <paramref name="applicationProcess"/> while it starts: when the noted opening is
    /// that application's (its process or one it started, <paramref name="inFamily"/> of application and process),
    /// the window in front is the application's and it moved there by itself (BAXY took no front on purpose since the
    /// opening, and since the previous look the front changed to it with no input of the person), the front goes back
    /// to the person's window; whether it holds there (a refused hand-back is not fought again). A look at another application never uses the opening (review: the
    /// looks of an application opened in front after one opened behind handed the front the person asked to see back
    /// to the window that was in front before the first). Measured: a game launcher activated its window when it was
    /// created and again when it maximized, 4.5 s and 6.3 s after the opening, past the opening's own guard.
    /// </summary>
    internal static bool ReturnIfTakenAtStart(int applicationProcess, Func<uint, uint, bool> inFamily)
    {
        // Under the front's gate: a burst of the lease bringing a window up meanwhile is never undone (a busy gate
        // leaves this look without a hand-back; the next one decides).
        if (!FrontGate.Wait(0))
            return false;
        try
        {
            return ReturnIfTakenAtStart(applicationProcess, inFamily, Foreground, ProcessOf, LastPersonInput, Return);
        }
        finally
        {
            _ = FrontGate.Release();
        }
    }

    internal static bool ReturnIfTakenAtStart(
        int applicationProcess,
        Func<uint, uint, bool> inFamily,
        Func<long> foreground,
        Func<long, int> processOf,
        Func<long> lastPersonInput,
        Func<long, long, bool> giveBack)
    {
        Opening? opening;
        lock (OpeningGate)
            opening = _opening;
        if (opening is null || applicationProcess <= 0 || DateTime.UtcNow - opening.NotedUtc > StartHandBack
            || Interlocked.Read(ref _frontTaken) != opening.FrontTaken
            || !inFamily(unchecked((uint)opening.ProcessId), unchecked((uint)applicationProcess)))
            return false;
        long personInput = lastPersonInput();
        bool personActed = personInput != opening.LastPersonInput;
        opening.LastPersonInput = personInput;
        long front = foreground();
        long seenBefore = opening.LastFront;
        opening.LastFront = front;
        // The person's input since the previous look may be what brought the application up; a front already the
        // application's at the previous look stayed there (by the person's choice or after a hand-back that failed:
        // never fought over).
        if (personActed || front == 0 || front == opening.Previous || front == seenBefore)
            return false;
        int process = processOf(front);
        if (process <= 0 || !inFamily(unchecked((uint)applicationProcess), unchecked((uint)process)))
            return false;
        if (!giveBack(opening.Previous, front))
            return false;
        opening.LastFront = opening.Previous;
        return true;
    }

    internal static void ForgetOpening()
    {
        lock (OpeningGate)
            _opening = null;
    }

    internal static int ProcessOf(long window)
    {
        _ = GetWindowThreadProcessId(checked((nint)window), out uint processId);
        return unchecked((int)processId);
    }

    internal static bool Return(long previous, long opened) => Return(previous, opened, CancellationToken.None);

    /// <summary>
    /// Hands the front back to <paramref name="previous"/> and, once it holds it, puts <paramref name="opened"/> right
    /// behind it; whether the front is back (read, not assumed: cu-v3-foco-segunda measured Windows refusing the
    /// hand-backs after the first in one process). A hand-back that ran past its budget is <paramref name="late"/>:
    /// nothing more is done (r4a M4: a late hand-back would take the front a burst of the lease took meanwhile).
    /// </summary>
    internal static bool Return(long previous, long opened, CancellationToken late)
    {
        nint back = checked((nint)previous);
        nint taken = checked((nint)opened);
        if (late.IsCancellationRequested || !IsWindow(back) || !IsWindowVisible(back))
            return false;
        // The right to set the foreground is won when this process lacks it, and each try is read back.
        if (!ForegroundRight.Give(back).Held)
            return false;
        // SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE: the opened window right behind the person's (a return that failed
        // leaves the order alone, so the window the keyboard goes to is never drawn under another one).
        if (taken != 0 && taken != back && !late.IsCancellationRequested)
            _ = SetWindowPos(taken, back, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010);
        return true;
    }

    /// <summary>
    /// r20b palanca 4 (v3-40, v3-43: an opening asked in front while the person typed in their own window took their
    /// keyboard for 30 and 51 s): «window» when the person is working in it, or 0. Working: an input of theirs that
    /// reaches a window's content (a key, a mouse button, the wheel) less than their pause ago
    /// (<see cref="ForegroundLease.QuietMs"/>), and the window is not BAXY's own (a request written in BAXY's chat leaves
    /// BAXY in front, and the opening takes the front as before). Read at the end of an opening (OpeningFront).
    /// </summary>
    internal static long PersonWorkingIn(long window)
    {
        if (window == 0)
            return 0;
        int process = ProcessOf(window);
        bool product = process <= 0 || process == Environment.ProcessId
            || (WindowsInstalledApplicationPlatform.ExecutableImagePath(process) is { } path
                && Windows.WindowsWindowControlProvider.OwnProcessNames.Contains(Path.GetFileNameWithoutExtension(path)));
        return PersonWorksIn(product, WindowsUserInputPause.Shared.LastReachingInputMs, Environment.TickCount64) ? window : 0;
    }

    // The rule of PersonWorkingIn on what it read: a window not BAXY's and an input of the person that reaches less
    // than their pause ago.
    internal static bool PersonWorksIn(bool productWindow, long lastReachingMs, long nowMs) =>
        !productWindow && lastReachingMs > 0 && nowMs - lastReachingMs < ForegroundLease.QuietMs;

    /// <summary>
    /// r20b palanca 4 review: the opened window shown above the person's without being activated. A minimized one is
    /// shown again without the activation (SW_SHOWNOACTIVATE: the SW_RESTORE of a front request activates), then it goes
    /// to the top of the window order (SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE). Nothing is assumed: true only when it
    /// is read back visible, not minimized, and above the person's window (a raised window Windows refuses to move, or a
    /// person's window that stays on top, says false).
    /// </summary>
    internal static bool ShowAboveWithoutActivation(long window, long personWindow)
    {
        nint shown = checked((nint)window);
        nint person = checked((nint)personWindow);
        if (shown == 0 || !IsWindow(shown))
            return false;
        if (IsIconic(shown))
            _ = ShowWindow(shown, 4);
        _ = SetWindowPos(shown, 0, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010);
        return ShownAbove(IsWindowVisible(shown), IsIconic(shown), Above(shown, person));
    }

    // The read-back of ShowAboveWithoutActivation: visible, not minimized, above the person's window.
    internal static bool ShownAbove(bool visible, bool minimized, bool above) => visible && !minimized && above;

    // Whether «window» comes before «other» in the window order (walked down from «window», bounded).
    private static bool Above(nint window, nint other)
    {
        if (other == 0 || other == window || !IsWindow(other))
            return false;
        nint next = window;
        for (int step = 0; step < 4096; step++)
        {
            next = GetWindow(next, 2);
            if (next == 0)
                return false;
            if (next == other)
                return true;
        }

        return false;
    }

    [LibraryImport("user32.dll")]
    private static partial nint GetForegroundWindow();

    [LibraryImport("user32.dll")]
    private static partial uint GetWindowThreadProcessId(nint window, out uint processId);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsWindow(nint window);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsWindowVisible(nint window);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool SetWindowPos(nint window, nint insertAfter, int x, int y, int width, int height, uint flags);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsIconic(nint window);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool ShowWindow(nint window, int command);

    [LibraryImport("user32.dll")]
    private static partial nint GetWindow(nint window, uint command);
}
