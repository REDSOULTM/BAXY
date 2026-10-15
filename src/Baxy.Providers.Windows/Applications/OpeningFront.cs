namespace Baxy.Providers.Windows.Applications;

/// <summary>
/// r20b palanca 4 (v3-40, v3-43: an opening asked in front while the person typed in their own window took their
/// keyboard for 30 and 51 s), and its review: the one rule every path of app.open follows (an application opened or
/// reused, a new document of it, the packaged Calculator) when the front was asked for. It is read when the opening
/// ended, right before the front would be asked for (never before the launch: the person may move to their window
/// while the application starts), and the window shown without the activation is read back before anything says so.
/// </summary>
internal interface IOpeningFront
{
    // The window in front now (0: unknown, and nothing is handed back).
    long ForegroundWindow() => 0;

    // «window» when the person works in it now: it is not BAXY's own, and an input of theirs reached a window less than
    // their pause ago (ForegroundHandBack.PersonWorkingIn); 0 otherwise.
    long PersonWorkingIn(long window) => 0;

    // The opened window shown above the person's without being activated (a minimized one shown again without the
    // activation), and whether it was read back so: visible, not minimized, and above the person's window in the
    // window order (ForegroundHandBack.ShowAboveWithoutActivation).
    bool ShowAboveWithoutActivation(long window, long personWindow) => false;
}

internal static class OpeningFront
{
    // A window whose thread does not answer would hold the showing without end; past this it is not said shown.
    internal static readonly TimeSpan ShowBudget = TimeSpan.FromSeconds(2);

    /// <summary>
    /// The person's window when the opened one must be shown without taking their keyboard, or 0 when the front is
    /// taken as asked. Read at the end of the opening: the window in front, when it is not the opened application's and
    /// the person works in it; when the opened application holds the front (Windows gave it the front at its start),
    /// the window that was in front before the opening, when the person works in it. A request written in BAXY's own
    /// window, or nobody working, takes the front as before.
    /// </summary>
    internal static long PersonWindow(IOpeningFront platform, bool askedInFront, Func<long, bool> isOpened, long frontBefore)
    {
        if (!askedInFront)
            return 0;
        long front = platform.ForegroundWindow();
        if (front == 0)
            return 0;
        if (!isOpened(front))
            return platform.PersonWorkingIn(front);
        return frontBefore != 0 && frontBefore != front && !isOpened(frontBefore)
            ? platform.PersonWorkingIn(frontBefore)
            : 0;
    }

    /// <summary>
    /// Whether the opened window was read back shown above the person's without the activation, within the budget, and
    /// the person's keyboard is not in the opened application. Review 2 of r20b palanca 4: a front Windows gave the
    /// application at its start, and a hand-back it refused, leave the opened window above the person's and in front;
    /// that is not shown without the focus (their keys go to it), so the front is read after the showing: known, and
    /// none of the opened application's windows (<paramref name="isOpened"/>).
    /// </summary>
    internal static async ValueTask<bool> ShowWithoutActivationAsync(
        IOpeningFront platform,
        long window,
        long personWindow,
        Func<long, bool> isOpened,
        CancellationToken cancellationToken)
    {
        if (window == 0 || personWindow == 0)
            return false;
        Task<bool> show = Task.Factory.StartNew(
            () => platform.ShowAboveWithoutActivation(window, personWindow),
            CancellationToken.None,
            TaskCreationOptions.LongRunning,
            TaskScheduler.Default);
        bool above;
        try
        {
            above = await show.WaitAsync(ShowBudget, cancellationToken).ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is TimeoutException or OverflowException)
        {
            return false;
        }
        return above && KeyboardLeftOut(platform.ForegroundWindow(), window, isOpened);
    }

    // The front read after the showing leaves the opened application without the keyboard: a window is in front, and it
    // is neither the opened window nor another of its application's.
    internal static bool KeyboardLeftOut(long front, long window, Func<long, bool> isOpened) =>
        front != 0 && front != window && !isOpened(front);
}
