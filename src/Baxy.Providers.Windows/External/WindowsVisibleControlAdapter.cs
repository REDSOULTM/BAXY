using System.Diagnostics;
using System.Globalization;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Kernel.Operations;
using Baxy.Kernel.Policy;

namespace Baxy.Providers.Windows.External;

internal interface IVisibleControlLocator
{
    string Stage { get; }

    ValueTask<ExternalCapabilityReceipt?> TryClickAsync(
        string operation,
        string label,
        CancellationToken cancellationToken);

    // The same, offered a press without the mouse at the point it located (the accessible control under it).
    ValueTask<ExternalCapabilityReceipt?> TryClickAsync(
        string operation,
        string label,
        IPointPress? press,
        CancellationToken cancellationToken) => TryClickAsync(operation, label, cancellationToken);
}

/// <summary>How a press at a point without the mouse went.</summary>
internal enum PointPressOutcome
{
    /// <summary>A control there was pressed (or a field there made the text's destination) by its way.</summary>
    Pressed,

    /// <summary>The worker answered that nothing there has a way: nothing was pressed, the pointer may follow.</summary>
    NothingThere,

    /// <summary>
    /// No answer, a timeout, an error or an answer that is neither: the control may have been pressed already (an
    /// Invoke that opened a modal dialog blocks the worker until it is killed), so it is never pressed again.
    /// </summary>
    Unconfirmed,

    /// <summary>
    /// A remembered place (CONTRATO §8.2) holds a control of its size with a name the label does not give: another
    /// control is there now, and neither its way nor the pointer presses it.
    /// </summary>
    Refused,

    /// <summary>
    /// Review of lat-apertura-clic (finding 4): the point lies on the control the accessible tree already pressed in
    /// this click and saw nothing change from: neither its way nor the pointer presses it a second time.
    /// </summary>
    AlreadyPressed,
}

/// <summary>A control pressed at a point of a window without moving the mouse, and how.</summary>
internal sealed record PointPressed(
    PointPressOutcome Outcome,
    string Method = "",
    string Name = "",
    string Kind = "",
    bool Focused = false)
{
    internal static PointPressed NothingThere { get; } = new(PointPressOutcome.NothingThere);

    internal static PointPressed Unconfirmed { get; } = new(PointPressOutcome.Unconfirmed);

    internal static PointPressed Refused { get; } = new(PointPressOutcome.Refused);

    internal static PointPressed AlreadyPressed { get; } = new(PointPressOutcome.AlreadyPressed);
}

/// <summary>
/// The pointer's press at a point: whether it happened, the window captured right before it, why it did not
/// (<c>input_user_not_paused</c>, <c>input_window_not_in_front</c>, <c>input_user_interrupted</c>,
/// <c>visible_surface_changed_while_waiting</c>) and, when it happened, the burst of the foreground lease it was made
/// in: the caller post-reads inside it and always restores it (GOAL_COMPUTER_USE_V3 point 0, fix 3).
/// <see cref="Popups"/> is the window's own popups taken with the image, after the person's pause (null when none were
/// asked for, or when the person acted again before the burst: what was up then says nothing of the press).
/// </summary>
internal readonly record struct PointerPressed(
    bool Pressed,
    VisibleControlSurface.CapturedWindow? Before,
    string? Refusal = null,
    IInputBurst? Burst = null,
    long WaitedMs = 0,
    IReadOnlyList<nint>? Popups = null);

/// <summary>
/// Finds the located point again on a capture taken inside the burst, when the window redrew while the person's pause
/// was waited for (OCR reads the word again); null when it is not there any more.
/// </summary>
internal delegate ValueTask<(int X, int Y)?> PointRelocator(
    VisibleControlSurface.CapturedWindow again, CancellationToken cancellationToken);

/// <summary>
/// A point a locator found on the screen (OCR, vision) pressed through the accessible tree first: the control at the
/// point that has a pattern and whose name (or the text inside it) is the label is invoked, selected, toggled or
/// expanded, or a field there becomes the text's destination. Only when the worker answers that nothing there has a
/// way may the pointer press the point, and only through <see cref="PointerAtAsync"/>, which keeps the pointer's
/// guard (the window in front and holding the point) and captures the window again right before the press.
/// </summary>
internal interface IPointPress
{
    ValueTask<PointPressed> PressAtAsync(
        nint window, int screenX, int screenY, string label, CancellationToken cancellationToken);

    /// <summary>
    /// The same for a control the caller already identified at the point (the tooltip stage, CONTRATO §8.2: a control
    /// without a name whose label its tooltip gave): that control counts as named by the label.
    /// </summary>
    ValueTask<PointPressed> PressControlAtAsync(
        nint window, int screenX, int screenY, string label, string controlId, CancellationToken cancellationToken) =>
        PressAtAsync(window, screenX, screenY, label, cancellationToken);

    /// <summary>
    /// The same for a remembered place of a control without a name, <paramref name="width"/>×<paramref name="height"/>
    /// (the tooltip stage's cache): a control there of about that size with another name refuses the press
    /// (<see cref="PointPressOutcome.Refused"/>), so the pointer does not press it either.
    /// </summary>
    ValueTask<PointPressed> PressRememberedAtAsync(
        nint window, int screenX, int screenY, int width, int height, string label, CancellationToken cancellationToken) =>
        PressAtAsync(window, screenX, screenY, label, cancellationToken);

    ValueTask<PointerPressed> PointerAtAsync(
        nint window,
        int screenX,
        int screenY,
        VisibleControlSurface.CapturedWindow? located,
        PointRelocator? relocate,
        CancellationToken cancellationToken);
}

/// <summary>
/// The press a locator makes at the point it found: without the mouse when a control there has a way; the pointer
/// only when the worker says nothing there has one and the pointer may press now; never again when the first press
/// is unconfirmed.
/// </summary>
internal static class LocatedPointPress
{
    internal readonly record struct Outcome(
        ExternalCapabilityReceipt? Failure,
        string Method,
        bool Focused,
        string Kind,
        VisibleControlSurface.CapturedWindow? Before,
        IInputBurst? Burst = null,
        long WaitedMs = 0);

    internal static ValueTask<Outcome> PressAsync(
        IPointPress? press,
        string operation,
        nint window,
        int screenX,
        int screenY,
        string label,
        CancellationToken cancellationToken) =>
        PressAsync(press, operation, window, screenX, screenY, label, null, null, cancellationToken);

    /// <summary>
    /// <paramref name="located"/> is the capture the point was read on: when the pointer must press, the window is
    /// read again inside the burst, after the wait for the person's pause; moved or resized, nothing is pressed, and
    /// redrawn, the point is found again by <paramref name="relocate"/> or nothing is pressed. A pointer's outcome
    /// carries its burst, which the caller restores after its post-read.
    /// </summary>
    internal static async ValueTask<Outcome> PressAsync(
        IPointPress? press,
        string operation,
        nint window,
        int screenX,
        int screenY,
        string label,
        VisibleControlSurface.CapturedWindow? located,
        PointRelocator? relocate,
        CancellationToken cancellationToken,
        string? controlId = null,
        (int W, int H)? remembered = null)
    {
        IPointPress presser = press ?? PointerOnlyPress.Instance;
        PointPressed pressed = !string.IsNullOrEmpty(controlId)
            ? await presser.PressControlAtAsync(window, screenX, screenY, label, controlId, cancellationToken)
                .ConfigureAwait(false)
            : remembered is { } size
                ? await presser.PressRememberedAtAsync(window, screenX, screenY, size.W, size.H, label, cancellationToken)
                    .ConfigureAwait(false)
                : await presser.PressAtAsync(window, screenX, screenY, label, cancellationToken).ConfigureAwait(false);
        if (pressed.Outcome == PointPressOutcome.Pressed)
            return new Outcome(null, pressed.Method, pressed.Focused, pressed.Kind, null);
        if (pressed.Outcome == PointPressOutcome.Refused)
        {
            return new Outcome(
                ExternalJson.FailureBeforeEffect(operation, "visible_point_named_other"),
                string.Empty, false, string.Empty, null);
        }
        if (pressed.Outcome == PointPressOutcome.AlreadyPressed)
        {
            return new Outcome(
                ExternalJson.FailureBeforeEffect(operation, WindowsVisibleControlAdapter.PointAlreadyPressed),
                string.Empty, false, string.Empty, null);
        }
        if (pressed.Outcome == PointPressOutcome.Unconfirmed)
        {
            return new Outcome(
                ExternalJson.FailureAfterEffect(operation, "visible_point_press_unconfirmed"),
                string.Empty, false, string.Empty, null);
        }

        PointerPressed pointed = await presser.PointerAtAsync(
            window, screenX, screenY, located, relocate, cancellationToken).ConfigureAwait(false);
        return pointed.Pressed
            ? new Outcome(null, "pointer", false, string.Empty, pointed.Before, pointed.Burst, pointed.WaitedMs)
            : new Outcome(
                ExternalJson.FailureBeforeEffect(operation, pointed.Refusal ?? "input_window_not_in_front"),
                string.Empty, false, string.Empty, null);
    }

    /// <summary>
    /// The pointer's press inside a burst of the foreground lease (GOAL_COMPUTER_USE_V3 point 0, fix 3): after a pause
    /// of the person, behind the pointer's guard (for a point read on <paramref name="located"/>, checked against the
    /// window captured again after the wait). r4a M3: the burst is short. The image the post-read compares with is the
    /// window's own drawing taken before the lease, behind the person's window as the post-read will see it (no settle
    /// in front for the caption to repaint), and the burst is given back right after the press: the post-read reads
    /// the window behind. A press hands its burst, already restored, to the caller; anything else restores it here.
    /// fable/cu-v3-reintento-pausa: the burst fits in the person's pause. The simulated user pauses 1 s every 3; the
    /// lease waits 500 ms of quiet, so about 500 ms remain, and the burst measured live on a window without a tree took
    /// 559 ms (banco r6, s12): the point was checked again inside it with a screen copy, which never equals the image
    /// the point was read on (that one is the window's own drawing), so it always read as redrawn and the word was
    /// located again by OCR and captured a third time with the front taken. The check, the locating again and the
    /// baseline now happen after the pause and before the burst (the check on a capture taken the way the point was
    /// read, the baseline on the window's own drawing); the burst only brings the window up, presses and gives it back.
    /// When the person acted between that check and the burst (the lease waited again), the check is made again inside
    /// the burst, as before.
    /// </summary>
    internal static async ValueTask<PointerPressed> PointerAsync(
        IPointerFallback pointer,
        nint window,
        int screenX,
        int screenY,
        VisibleControlSurface.CapturedWindow? located,
        PointRelocator? relocate,
        CancellationToken cancellationToken,
        Func<nint, IReadOnlyList<nint>>? popupsOf = null)
    {
        if (window == 0)
            return new PointerPressed(false, null);
        // Review of fable/cu-v3-rafaga: the person's pause is waited for before the baseline, so a window that redraws
        // by itself while they work (a spinner, a page loading, a clock) is not taken for the press's effect: the image
        // is taken right before the burst, not seconds before it.
        (bool paused, long pausedMs) = await pointer.PauseAsync(cancellationToken).ConfigureAwait(false);
        if (!paused)
            return new PointerPressed(false, null, "input_user_not_paused");
        VisibleControlSurface.CapturedWindow? before;
        VisibleControlSurface.CapturedWindow? checkedOn = null;
        if (located is { } seen)
        {
            // The point was read before the wait, and the person was active during it: moved or resized, no read
            // point holds; redrawn, it is found again on the new capture. Read before the burst, the way the point was
            // read (a screen copy of a window nothing covered is compared with a screen copy, the window's own drawing
            // with its own drawing: the two never match each other); the post-read's baseline is the window's own
            // drawing, as the post-read reads it behind.
            PointerChecked check = await CheckPointAsync(pointer, seen, screenX, screenY, relocate, cancellationToken)
                .ConfigureAwait(false);
            if (check.Refusal is not null)
                return new PointerPressed(false, null, check.Refusal);
            (screenX, screenY, checkedOn) = (check.X, check.Y, check.Again);
            before = await BaselineAsync(pointer, window, check.Again, cancellationToken).ConfigureAwait(false);
        }
        else
        {
            before = await BehindAsync(pointer, window, cancellationToken).ConfigureAwait(false);
        }

        // Review of fable/cu-v3-carga-preguntas (finding 1): the window's own popups are taken with the image, after the
        // person's pause and right before the burst; one the person opened while they worked (a menu of theirs in that
        // application) is not taken for the press's effect.
        IReadOnlyList<nint>? popups = popupsOf?.Invoke(window);
        IInputBurst burst = await pointer.AcquireAsync(window, cancellationToken).ConfigureAwait(false);
        bool handed = false;
        try
        {
            if (burst.Refusal is string refusal)
                return new PointerPressed(false, null, refusal);
            if (burst.WaitedMs > 0)
            {
                // The person acted again between the check and the burst: the window may have changed meanwhile.
                // Without a point to find again no image says what the press changed (the post-read asks the
                // control); a read point is checked again, now inside the burst. Nor does a list of popups taken
                // before the person acted again: the popup evidence is dropped.
                popups = null;
                if (checkedOn is not { } last)
                {
                    before = null;
                }
                else
                {
                    PointerChecked again = await CheckPointAsync(pointer, last, screenX, screenY, relocate, cancellationToken)
                        .ConfigureAwait(false);
                    if (again.Refusal is not null)
                        return new PointerPressed(false, null, again.Refusal);
                    (screenX, screenY) = (again.X, again.Y);
                    if (again.Redrawn)
                        before = await BaselineAsync(pointer, window, again.Again, cancellationToken).ConfigureAwait(false);
                }
            }

            // In front and holding the point is not enough: the point must show this window, never one of another
            // application kept on top over it (safety review r10a), as the drag and the tooltip already require.
            if (!pointer.Prepare(window, screenX, screenY) || !pointer.Shows(window, screenX, screenY))
                return new PointerPressed(false, null, "input_window_not_in_front");
            long ownSeen = burst.OwnInputsSeen;
            if (!pointer.Click(burst, window, screenX, screenY))
                return new PointerPressed(false, null, burst.MayAct ? "input_window_not_in_front" : "input_user_interrupted");
            // Given back right after the press, once Windows routed its press and release to the window under the
            // cursor (review of fable/cu-v3-rafaga: mouse_event is processed later, and a front or a cursor given back
            // before would take the press or the release): the post-read reads the window behind the person's.
            try
            {
                await burst.SettleOwnInputAsync(ownSeen, 2, cancellationToken).ConfigureAwait(false);
            }
            catch (OperationCanceledException)
            {
                // Pressed already: the press is said as such, and the front goes back now.
            }

            _ = burst.Restore();
            handed = true;
            return new PointerPressed(true, before, null, burst, pausedMs + burst.WaitedMs, popups);
        }
        finally
        {
            if (!handed)
                _ = burst.Restore();
        }
    }

    // A point read on a capture, checked on a capture taken now the same way: the point (found again when only the
    // drawing changed) and that capture, or why nothing may be pressed (a capture that cannot be taken says nothing
    // about the point: it refuses).
    private readonly record struct PointerChecked(
        int X, int Y, VisibleControlSurface.CapturedWindow? Again, bool Redrawn, string? Refusal);

    private static async ValueTask<PointerChecked> CheckPointAsync(
        IPointerFallback pointer,
        VisibleControlSurface.CapturedWindow seen,
        int screenX,
        int screenY,
        PointRelocator? relocate,
        CancellationToken cancellationToken)
    {
        Func<nint, CancellationToken, ValueTask<VisibleControlSurface.CapturedWindow?>> capture = seen.SelfDrawn
            ? pointer.CaptureBehindAsync
            : pointer.CaptureAsync;
        VisibleControlSurface.SurfaceAfterWait recheck = await VisibleControlSurface
            .SurfaceAfterWaitAsync(seen, (hwnd, token) => ReadAsync(capture, hwnd, token), cancellationToken)
            .ConfigureAwait(false);
        if (recheck.Again is not { } again || recheck.Moved)
            return new PointerChecked(screenX, screenY, null, false, VisibleControlSurface.SurfaceChangedWhileWaiting);
        if (!recheck.Redrawn)
            return new PointerChecked(screenX, screenY, again, false, null);
        (int X, int Y)? found = relocate is null
            ? null
            : await relocate(again, cancellationToken).ConfigureAwait(false);
        return found is { } point
            ? new PointerChecked(point.X, point.Y, again, true, null)
            : new PointerChecked(screenX, screenY, null, true, VisibleControlSurface.SurfaceChangedWhileWaiting);
    }

    // The post-read's baseline: the check's own capture when it is the window's own drawing, otherwise that drawing
    // taken now.
    private static async ValueTask<VisibleControlSurface.CapturedWindow?> BaselineAsync(
        IPointerFallback pointer, nint window, VisibleControlSurface.CapturedWindow? checkedOn, CancellationToken cancellationToken) =>
        checkedOn is { SelfDrawn: true } own
            ? own
            : await BehindAsync(pointer, window, cancellationToken).ConfigureAwait(false);

    // The window's own drawing now (the post-read's baseline), or null when it cannot be read.
    private static ValueTask<VisibleControlSurface.CapturedWindow?> BehindAsync(
        IPointerFallback pointer, nint window, CancellationToken cancellationToken) =>
        ReadAsync(pointer.CaptureBehindAsync, window, cancellationToken);

    private static async ValueTask<VisibleControlSurface.CapturedWindow?> ReadAsync(
        Func<nint, CancellationToken, ValueTask<VisibleControlSurface.CapturedWindow?>> capture,
        nint window,
        CancellationToken cancellationToken)
    {
        try
        {
            return await capture(window, cancellationToken).ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is IOException or InvalidOperationException)
        {
            return null;
        }
    }

    // A locator offered no press: nothing is pressed without the mouse, and the pointer keeps its guard.
    private sealed class PointerOnlyPress : IPointPress
    {
        internal static PointerOnlyPress Instance { get; } = new();

        private readonly ScreenPointer _pointer = new();

        public ValueTask<PointPressed> PressAtAsync(
            nint window, int screenX, int screenY, string label, CancellationToken cancellationToken) =>
            ValueTask.FromResult(PointPressed.NothingThere);

        public ValueTask<PointerPressed> PointerAtAsync(
            nint window,
            int screenX,
            int screenY,
            VisibleControlSurface.CapturedWindow? located,
            PointRelocator? relocate,
            CancellationToken cancellationToken) =>
            PointerAsync(_pointer, window, screenX, screenY, located, relocate, cancellationToken);
    }
}

/// <summary>
/// The last resort of a click: the cursor on a point of a window, under the pause rule (GOAL_COMPUTER_USE_V3 point 0,
/// fix 3). <see cref="AcquireAsync"/> waits for the person's pause and brings the window up in a burst of the
/// foreground lease; <see cref="Prepare"/> says whether the point may be pressed now (the window bound to the mission
/// is the one in front and holds the point); only then is <see cref="Click"/> called. The burst gives the cursor and
/// the window in front back.
/// </summary>
internal interface IPointerFallback
{
    ValueTask<IInputBurst> AcquireAsync(nint window, CancellationToken cancellationToken);

    bool Prepare(nint window, int screenX, int screenY);

    /// <summary>The window captured inside the burst (a point read before the wait is checked against it).</summary>
    ValueTask<VisibleControlSurface.CapturedWindow?> CaptureAsync(nint window, CancellationToken cancellationToken);

    /// <summary>
    /// The window's own drawing, taken before the burst, behind the person's window (r4a M3: the baseline of the press's
    /// post-read, which reads the window behind once the burst is given back).
    /// </summary>
    ValueTask<VisibleControlSurface.CapturedWindow?> CaptureBehindAsync(nint window, CancellationToken cancellationToken) =>
        CaptureAsync(window, cancellationToken);

    /// <summary>Whether the press was sent: the burst may still act (the person has not touched anything since).</summary>
    bool Click(IInputBurst burst, int screenX, int screenY);

    /// <summary>
    /// Whether the window shown at the point (the one a press there reaches) is <paramref name="window"/>, a window
    /// inside it, its own dialog or its family peer: never a window of another application kept on top over it
    /// (safety review r10a).
    /// </summary>
    bool Shows(nint window, int screenX, int screenY) => true;

    /// <summary>
    /// The press of <see cref="Click(IInputBurst, int, int)"/> with the point checked again against
    /// <paramref name="window"/> right before it goes.
    /// </summary>
    bool Click(IInputBurst burst, nint window, int screenX, int screenY) =>
        Shows(window, screenX, screenY) && Click(burst, screenX, screenY);

    /// <summary>
    /// Waits for the person's pause without taking anything (<see cref="IForegroundLease.WaitForPauseAsync"/>): the
    /// baseline is taken after it, right before the burst.
    /// </summary>
    ValueTask<(bool Paused, long WaitedMs)> PauseAsync(CancellationToken cancellationToken) =>
        ValueTask.FromResult((true, 0L));
}

internal sealed class ScreenPointer(IForegroundLease? lease = null) : IPointerFallback
{
    // r4a M3: no settle in front any more (it kept the front 250 ms per press). The settle was there because the image
    // before the press was taken in front, right after the window repainted its active caption; the baseline is now
    // the window's own drawing taken behind before the burst (CaptureBehindAsync), as the post-read sees it.
    public ValueTask<IInputBurst> AcquireAsync(nint window, CancellationToken cancellationToken) =>
        (lease ?? ForegroundLease.Shared).AcquireAsync(window, cancellationToken);

    public ValueTask<(bool Paused, long WaitedMs)> PauseAsync(CancellationToken cancellationToken) =>
        (lease ?? ForegroundLease.Shared).WaitForPauseAsync(cancellationToken);

    public ValueTask<VisibleControlSurface.CapturedWindow?> CaptureBehindAsync(
        nint window, CancellationToken cancellationToken) =>
        VisibleControlSurface.CaptureAsync(window, cancellationToken, selfDrawn: true);

    // The lease brought the window up: it must still be the one in front, and hold the point.
    public bool Prepare(nint window, int screenX, int screenY) =>
        VisibleControlSurface.MayPress()
        && VisibleControlSurface.IsAlive(window)
        && VisibleControlSurface.ForegroundIs(window)
        && VisibleControlSurface.TryBounds(window, out int left, out int top, out int right, out int bottom)
        && screenX >= left && screenX < right && screenY >= top && screenY < bottom;

    public ValueTask<VisibleControlSurface.CapturedWindow?> CaptureAsync(nint window, CancellationToken cancellationToken) =>
        VisibleControlSurface.CaptureAsync(window, cancellationToken);

    public bool Click(IInputBurst burst, int screenX, int screenY) => VisibleControlSurface.Click(burst, screenX, screenY);

    public bool Shows(nint window, int screenX, int screenY) => VisibleControlSurface.PointShows(window, screenX, screenY);

    public bool Click(IInputBurst burst, nint window, int screenX, int screenY) =>
        VisibleControlSurface.Click(burst, screenX, screenY, window);
}

// The application app.open brought up moments ago, if any: a click right after an opening acts on it.
internal interface IOpenedApplicationFocus
{
    VisibleControlSurface.OpenedApplication? TakeOpened();

    VisibleControlSurface.OpenedApplication? PeekOpened();

    // The opened application's main window (none yet: Window 0), brought to the front only when bringToFront asks
    // (neither a look nor a click does: both reach it where it is, v3 point 0), and whether it looks drawn (judged
    // only when asked; otherwise drawn).
    ValueTask<VisibleControlSurface.OpenedSurface> FrontAsync(
        VisibleControlSurface.OpenedApplication opened,
        bool judgeDrawn,
        CancellationToken cancellationToken,
        bool bringToFront = false);
}

internal sealed class OpenedApplicationFocus : IOpenedApplicationFocus
{
    // A click asked in the same breath as the opening, or answered after its confirmation, comes well inside this.
    private static readonly TimeSpan Freshness = TimeSpan.FromSeconds(90);

    public VisibleControlSurface.OpenedApplication? TakeOpened() =>
        VisibleControlSurface.TakeOpened(Freshness);

    public VisibleControlSurface.OpenedApplication? PeekOpened() =>
        VisibleControlSurface.PeekOpened(Freshness);

    public ValueTask<VisibleControlSurface.OpenedSurface> FrontAsync(
        VisibleControlSurface.OpenedApplication opened,
        bool judgeDrawn,
        CancellationToken cancellationToken,
        bool bringToFront = false) =>
        VisibleControlSurface.FrontOpenedAsync(opened, judgeDrawn, cancellationToken, bringToFront);
}

internal sealed class NoOpenedApplicationFocus : IOpenedApplicationFocus
{
    public VisibleControlSurface.OpenedApplication? TakeOpened() => null;

    public VisibleControlSurface.OpenedApplication? PeekOpened() => null;

    public ValueTask<VisibleControlSurface.OpenedSurface> FrontAsync(
        VisibleControlSurface.OpenedApplication opened,
        bool judgeDrawn,
        CancellationToken cancellationToken,
        bool bringToFront = false) => ValueTask.FromResult(default(VisibleControlSurface.OpenedSurface));
}

// The person's browser when a mission names «the browser» without naming one (a tab spoken of in passing): the front
// window of their default browser, the window browser.control and browser.tabs.list act on; 0 when it is not running.
internal interface IUserBrowserWindowLocator
{
    nint FrontWindow();

    // «navegador», «el navegador», «mi navegador», «browser», «my browser», «web browser»: the category, not a product.
    internal static bool NamesTheCategory(string? application)
    {
        string[] words = VisibleControlSurface.FoldTitle(application).Split(' ', StringSplitOptions.RemoveEmptyEntries);
        int start = words.Length > 1 && words[0] is "el" or "mi" or "tu" or "su" or "the" or "my" or "your" ? 1 : 0;
        return string.Join(' ', words[start..]) is "navegador" or "navegador web" or "browser" or "web browser";
    }
}

internal sealed class NoUserBrowserWindow : IUserBrowserWindowLocator
{
    public nint FrontWindow() => 0;
}

// How long a click looks for its label. M132 (owner script t42 «En … ve a crash bandicoot», 28 s for «no hay ningún
// elemento visible con ese nombre»): a label is waited on only while the surface may still be drawing — an
// application opened moments ago — and then for a bounded stretch once its window is up; on a window that was
// already there, a second look settles it and the honest «not there» comes at once.
// The post-read of a pressed control: its UIA state is asked every PostreadPeriod for ControlPostread; its window is
// captured from SurfaceFirstSample on, up to SurfacePostread when nothing has settled earlier.
internal sealed record VisibleClickTiming(
    TimeSpan LaunchSurface,
    TimeSpan ReusedSurface,
    TimeSpan OpenedLabel,
    TimeSpan SettledLabel,
    TimeSpan Interval,
    TimeSpan PostreadPeriod,
    TimeSpan ControlPostread,
    TimeSpan SurfaceFirstSample,
    TimeSpan SurfacePostread)
{
    internal static VisibleClickTiming Default { get; } = new(
        LaunchSurface: TimeSpan.FromSeconds(30),
        ReusedSurface: TimeSpan.FromSeconds(5),
        OpenedLabel: TimeSpan.FromSeconds(8),
        SettledLabel: TimeSpan.FromSeconds(3),
        Interval: TimeSpan.FromMilliseconds(1500),
        PostreadPeriod: TimeSpan.FromMilliseconds(50),
        ControlPostread: TimeSpan.FromMilliseconds(500),
        SurfaceFirstSample: TimeSpan.FromMilliseconds(150),
        SurfacePostread: TimeSpan.FromMilliseconds(1500));

    // r8: between two looks for a label on a window that was already there, the window is sampled every StillSample;
    // one that did not change at all for StillFor is not drawing anything new, so the label that no stage found will
    // not appear and «not found» is answered then instead of after the whole SettledLabel stretch (measured on ~50
    // live missions: 13 such clicks at 4.2–4.4 s each).
    internal TimeSpan StillSample { get; init; } = TimeSpan.FromMilliseconds(200);
    internal TimeSpan StillFor { get; init; } = TimeSpan.FromMilliseconds(750);

    // Goal v3, analysis r3a M7: an accessible tree this large is an interface that is up, not a loading screen (a
    // launcher's splash or a blank web view shows a handful of elements); with it still and not growing, the label
    // an opened application's look did not find is not coming.
    internal int InterfaceUp { get; init; } = 20;
}

/// <summary>
/// Perception and the click of the computer-use engine
/// (documentacion/computer-use/CONTRATO_VISTA_ACCION.md §1, §2).
/// <c>input.visible.controls</c> is the compact view of the foreground window:
/// up to sixty actionable controls with index, kind, label, state, rectangle,
/// zone and dominant colour, the written text by zone (OCR), the window's
/// title and process. <c>input.visible.click</c> invokes one control by label
/// or by the identity the view handed out, through the persistent UIA worker,
/// then OCR, then vision, and demands a post-read.
/// </summary>
internal sealed class WindowsVisibleControlAdapter
    : IExternalOperationAdapter, IViewedFields, IPointPress, ISearchBurstActs, IDisposable
{
    // The code of a click refused because its window runs as administrator (contract §4, «window_elevated»).
    internal const string WindowElevated = "window_elevated";

    // Encargo V: the worker found the control to press and its name asks for the person's word while no label of the click
    // does (RiskPolicy.PressedNameAsksMoreThanItsLabel): nothing is pressed, by this stage or a later one, and the receipt
    // names it, so the step that names it is the one RiskPolicy asks for.
    internal const string NeedsConfirmation = "visible_control_needs_confirmation";

    private static readonly HashSet<string> CascadeAfter = new(StringComparer.Ordinal)
    {
        "visible_button_not_found",
        "visible_button_uia_failed",
        "visible_click_no_receipt",
        "active_window_not_found",
    };

    // H0096 «aprieta en Among Us»: el worker sólo emite este código después de
    // recorrer el árbol y los botones nativos y no encontrar nada con ese
    // nombre, es decir, antes de tocar nada. Marcarlo como «pudo haber efecto»
    // sólo porque la frontera se cruza al arrancar convertía una ausencia
    // medida en una duda, y el turno la contaba como un resultado sin
    // confirmar en vez de decir que ahí no había nada así.
    private static readonly HashSet<string> BeforeAnyPress = new(StringComparer.Ordinal)
    {
        "visible_button_not_found",
        "visible_control_identity_stale",
        "visible_control_label_mismatch",
        "visible_click_argument_invalid",
        // Goal v3 B3: the control has no way to be pressed in the manner asked (no ExpandCollapse to open, no context
        // menu, no message route for a double click): nothing was sent.
        "visible_control_cannot_open",
        "visible_control_no_context_menu",
        "visible_control_no_double_click",
        // Review of B3, finding 6: the arrow's list was already open; this step opened nothing.
        "visible_control_already_open",
        // Ronda 20b, palanca 6 (review finding 1): the list to collapse was no longer open; nothing was sent.
        "visible_control_not_open",
        // Ronda 21 (pasada r18 v3-65, v3-25): the worker's walk of what is shown ran out of its own time before it found
        // the control, and said so before the host's limit: nothing was pressed.
        "visible_lookup_timeout",
        // Ronda 24b (banco r23 u9): a list, tree, grid or table with neither Invoke nor SelectionItem is no thing to press
        // (its pointer click chose whatever row was at its centre): refused before anything was sent.
        "visible_control_is_container",
    };

    // Encargo IMP4: the lines a look read with their places keeps (a chat's whole pane: 79 lines measured on redpc); encargo
    // WA-LEER: as many as the mission's facts carry (OperationVisibleFacts.ChatLines).
    private const int PlacedLinesRead = OperationVisibleFacts.ChatLines;
    private static readonly TimeSpan LabelWaitBudget = TimeSpan.FromSeconds(24);
    private static readonly TimeSpan LabelWaitInterval = TimeSpan.FromMilliseconds(1500);
    private static readonly TimeSpan WorkerViewBudget = TimeSpan.FromSeconds(20);
    private static readonly TimeSpan WorkerClickBudget = TimeSpan.FromSeconds(15);

    private readonly IUiaWorker _worker;
    private readonly IVisibleControlLocator? _ocr;
    private readonly IVisibleControlLocator? _vision;
    // CONTRATO_VISTA_ACCION.md §8.2: between OCR and vision, the tooltips of the controls that are only an icon.
    private readonly IVisibleControlLocator? _tooltip;
    private readonly IOpenedApplicationFocus _focus;
    private readonly VisibleClickTiming _timing;
    private readonly IUserBrowserWindowLocator _browserWindow;
    private readonly Func<nint, CancellationToken, ValueTask<string?>>? _surfaceHash;
    private readonly IPointerFallback _pointer;
    // The image of a window a click compares before and after (selfDrawn: taken the way the earlier one was).
    private readonly Func<nint, bool?, CancellationToken, ValueTask<VisibleControlSurface.CapturedWindow?>> _capture;
    private readonly object _viewLock = new();
    private LastView? _lastView;
    // Whether a window's process runs with more rights than BAXY (UIPI): nothing can be read or pressed there.
    private readonly Func<nint, bool> _elevated;
    // The content windows of a window's process family a posted press may reach (fable/cu-v3-clic-chromium).
    private readonly Func<nint, IReadOnlyList<nint>> _renderHosts;
    private const long RenderHostsKeptMs = 2_000;
    private RenderHostsSeen? _renderHostsSeen;

    private sealed record RenderHostsSeen(nint Window, long At, IReadOnlyList<nint> Hosts);

    // Review r10: the window the last look by label read (the one its click targets) and when a click last changed
    // the screen. A page the previous click navigated to may still be loading behind a still frame: the first click
    // after it keeps the full wait instead of answering «not found» after one still look.
    private static readonly TimeSpan ScreenChangeFreshness = TimeSpan.FromSeconds(30);
    private nint _lookedWindow;
    private DateTime _screenChangedUtc = DateTime.MinValue;
    // Goal v3, analysis r3a M7: how many elements the accessible tree had when the last look by label did not find the
    // label (-1: not said). After an opening the label is waited for only while that tree grows.
    private int _lookedTreeSize = -1;

    internal WindowsVisibleControlAdapter()
        : this(new UiaWorkerHost())
    {
    }

    /// <summary>
    /// The lease of a search burst and of the burst that reopens what an opener showed (<see cref="SearchBurst"/>); null
    /// (the test seams that name none) runs neither.
    /// </summary>
    internal IForegroundLease? BurstLease { get; init; }

    /// <summary>
    /// The text of a search burst (<see cref="SearchBurst"/>), typed into the mission's window as
    /// <c>input.text.type</c> types it (by its field's value or a message when it takes one, else by the keyboard, which
    /// stops at the person's first input); null (the test seams that name none) types nothing.
    /// </summary>
    internal Func<nint, string, CancellationToken, ValueTask<ExternalCapabilityReceipt>>? TypeInWindow { get; set; }

    /// <summary>
    /// The window's own popups (<see cref="VisibleControlSurface.PopupsOf"/>), taken before a click and during its
    /// post-read; a test seam names its own.
    /// </summary>
    internal Func<nint, IReadOnlyList<nint>> PopupsOf { get; init; } = VisibleControlSurface.PopupsOf;

    /// <summary>
    /// Whether the person's pointer rests on the window now (<see cref="VisibleControlSurface.PointerRestsOn"/>): a popup
    /// born then may be the hover's, not the click's. A test seam names its own.
    /// </summary>
    internal Func<nint, bool> PointerRestsOn { get; init; } = VisibleControlSurface.PointerRestsOn;

    /// <summary>
    /// Ronda 20b, palanca 8, objetivo 3 (v3-44): the desktop's root windows for a click on a window
    /// (<see cref="VisibleControlSurface.RootWindowsNow"/>), taken before it and during its post-read; null (the test
    /// seams that name none) watches no other process's window.
    /// </summary>
    internal Func<nint, VisibleControlSurface.RootSnapshot>? RootWindows { get; init; }

    /// <summary>The window a click handed its effect to, as its receipt names it
    /// (<see cref="VisibleControlSurface.DescribeHanded"/>).</summary>
    internal Func<VisibleControlSurface.RootWindow, VisibleControlSurface.HandedWindow?> DescribeHanded { get; init; } =
        VisibleControlSurface.DescribeHanded;

    /// <summary>Whether a popup is up now that was not before the click (<paramref name="now"/> against
    /// <paramref name="before"/>).</summary>
    internal static bool PopupBorn(IReadOnlyList<nint> before, IReadOnlyList<nint> now) =>
        now.Any(popup => popup != 0 && !before.Contains(popup));

    /// <summary>The clock of a search burst's ceiling (fakes advance it in tests).</summary>
    internal ILeaseClock SearchClock { get; init; } = new SystemLeaseClock();


    // The tooltip stage asks the same worker for the controls without a name and for the tooltips shown (and, TZ-DC2,
    // the messaging clients' probe, WindowsExternalCapabilityProvider).
    internal WindowsVisibleControlAdapter(UiaWorkerHost worker)
        : this(
            worker,
            new WindowsVisibleOcrLocator(),
            new WindowsVisibleVisionLocator(),
            new OpenedApplicationFocus(),
            VisibleClickTiming.Default,
            new UserBrowserSurface(new WindowsUserBrowserPlatform()),
            WindowSurfaceHashAsync,
            tooltip: new WindowsVisibleTooltipLocator(worker))
    {
        RootWindows = VisibleControlSurface.RootWindowsNow;
        BurstLease = ForegroundLease.Shared;
    }

    internal WindowsVisibleControlAdapter(
        IUiaWorker worker,
        IVisibleControlLocator? ocr,
        IVisibleControlLocator? vision,
        IOpenedApplicationFocus? focus = null,
        VisibleClickTiming? timing = null,
        IUserBrowserWindowLocator? browserWindow = null,
        Func<nint, CancellationToken, ValueTask<string?>>? surfaceHash = null,
        IPointerFallback? pointer = null,
        Func<nint, bool?, CancellationToken, ValueTask<VisibleControlSurface.CapturedWindow?>>? capture = null,
        IVisibleControlLocator? tooltip = null,
        Func<nint, bool>? elevated = null,
        Func<nint, IReadOnlyList<nint>>? renderHosts = null)
    {
        _worker = worker ?? throw new ArgumentNullException(nameof(worker));
        _renderHosts = renderHosts ?? VisibleControlSurface.FamilyContentWindows;
        _elevated = elevated ?? (window => VisibleControlSurface.RunsAboveUs(VisibleControlSurface.WindowProcess(window).ProcessId));
        _tooltip = tooltip;
        _pointer = pointer ?? new ScreenPointer();
        _surfaceHash = surfaceHash;
        _capture = capture ?? ((window, selfDrawn, token) =>
            VisibleControlSurface.CaptureAsync(window, token, selfDrawn: selfDrawn));
        _ocr = ocr;
        _vision = vision;
        _focus = focus ?? new NoOpenedApplicationFocus();
        _timing = timing ?? VisibleClickTiming.Default;
        _browserWindow = browserWindow ?? new NoUserBrowserWindow();
    }

    public bool CanHandle(string operation) =>
        operation is "input.visible.click" or "input.visible.controls";

    private long _clicks;

    /// <summary>Revision 3 of r24b (finding 3): the clicks this adapter has made (IViewedFields).</summary>
    public long Clicks => Interlocked.Read(ref _clicks);

    public async ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        if (operation == "input.visible.controls")
            return await ListAsync(operation, arguments, cancellationToken).ConfigureAwait(false);

        ExternalCapabilityReceipt receipt;
        _pressedUnchanged = null;
        // Revision 3 of r24b (finding 3): counted before it acts, so a focus owed to a field is void after any click.
        Interlocked.Increment(ref _clicks);
        try
        {
            receipt = await ClickAsync(operation, arguments, cancellationToken).ConfigureAwait(false);
        }
        finally
        {
            _pressedUnchanged = null;
        }

        if (receipt.Verified
            && receipt.Result is { ValueKind: JsonValueKind.Object } result
            && result.TryGetProperty("surfaceChanged", out JsonElement changed)
            && changed.ValueKind == JsonValueKind.True)
        {
            _screenChangedUtc = DateTime.UtcNow;
        }

        return receipt;
    }

    private async ValueTask<ExternalCapabilityReceipt> ClickAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        string label;
        int? index = null;
        string? controlId = null;
        nint missionWindow = 0;
        string? search;
        string? choose;
        string? manner;
        try
        {
            label = ExternalJson.RequiredString(arguments, "label").Trim();
            search = OptionalText(arguments, "search");
            choose = OptionalText(arguments, "choose");
            manner = OptionalText(arguments, "manner");
            if (manner is not (null or "collapse" or "dismiss" or "double" or "menu" or "open"))
                throw new InvalidDataException("manner");
            // Revisión 1 de la ronda 21 (hallazgo 2): choose names the result of a search burst, never an item of an
            // opening: without search it would be dropped and the control pressed by its own action (a split button's
            // Invoke opens another tab, v3-37). Nothing is pressed.
            if (choose is not null && search is null)
                throw new InvalidDataException("choose");
            if (arguments.TryGetProperty("index", out JsonElement indexValue)
                && indexValue.ValueKind == JsonValueKind.Number
                && indexValue.TryGetInt32(out int requestedIndex))
            {
                index = requestedIndex;
            }

            if (arguments.TryGetProperty("controlId", out JsonElement identity)
                && identity.ValueKind == JsonValueKind.String
                && !string.IsNullOrWhiteSpace(identity.GetString()))
            {
                controlId = identity.GetString()!.Trim();
            }

            // The mission's window: the hwnd of the view the click was decided on (v3 point 0 review).
            if (arguments.TryGetProperty("window", out JsonElement named) && named.ValueKind != JsonValueKind.Null)
            {
                if (named.ValueKind != JsonValueKind.Number || !named.TryGetInt64(out long handle) || handle <= 0)
                    throw new InvalidDataException("window");
                missionWindow = (nint)handle;
            }
        }
        catch (InvalidDataException)
        {
            return ExternalJson.FailureBeforeEffect(operation, "visible_click_argument_invalid");
        }

        // The engine clicks by the identity the last view handed out. The
        // index is resolved against that view, and the label must name the
        // same control: an index that drifted is refused, never clicked.
        if (index is int position && controlId is null)
        {
            LastView? view;
            lock (_viewLock)
            {
                view = _lastView;
            }

            ViewControl? chosen = view?.Controls.FirstOrDefault(control => control.Index == position);
            if (chosen is null)
                return ExternalJson.FailureBeforeEffect(operation, "visible_control_identity_stale");
            // Auditoría P3: the label is the index's name as the view gave it (folded), and the receipt says that name.
            if (!SameLabel(label, chosen.Name))
                return NotNamed(operation, "visible_control_label_mismatch", [chosen.Name]);
            controlId = chosen.Id.Length > 0 ? chosen.Id : null;
        }

        // Ronda 20 (P7): the opener the previous click noted is taken before any branch, so every click right after it
        // (by identity, by its manner, by a label of the last view) may reopen what it showed, and any other click takes it
        // away. A click by a label alone right after an opener presses the one control of the mission's last view that the
        // label names by its identity, so an item of the opening that closed is answered stale and reopened, never looked
        // for by a cascade on a closed menu. It names it by the mind's own rule (NamedInView), never a descriptive
        // sentence that merely mentions it, and a press of that identity that failed before any effect leaves the label
        // to its cascade (revision 1 of the branch).
        (nint Window, string Id, string Label, HashSet<string> NamesBefore, string? Manner)? opener = TakeOpener();
        bool namedByLabel = false;
        if (controlId is null && index is null && search is null && manner is null && opener is not null)
        {
            controlId = NamedInView(missionWindow, label);
            namedByLabel = controlId is not null;
        }

        if (search is not null)
            return await SearchInBurstAsync(operation, label, controlId, missionWindow, search, choose, cancellationToken)
                .ConfigureAwait(false);

        // Goal v3 B3: a control opened by its arrow, its context menu or a double click is pressed only by the identity
        // the view handed out, through the accessible tree or a message, never by the pointer nor by the label's
        // cascade (OCR, vision): a press found that way would be the ordinary click the manner exists to avoid (the
        // split button's Invoke opened another tab, v3-37). A control that moved since the view is not pressed.
        if (manner is not null)
        {
            if (search is not null || controlId is null)
                return ExternalJson.FailureBeforeEffect(operation, "visible_control_identity_stale");
            HashSet<string>? shownBefore = ChainedNames(opener, missionWindow, controlId, ViewNames(missionWindow));
            ExternalCapabilityReceipt pressed = await InvokeUiaAsync(operation, label, controlId, missionWindow, cancellationToken, manner)
                .ConfigureAwait(false);
            // Ronda 20 (P7, v3-09): an item the opener showed (a collapsed ribbon's gallery) that the act's manner (its
            // arrow) found closed: the opener and the item, in that manner, go in one burst of the lease.
            if (await ReopenShownAsync(operation, opener, pressed, label, controlId, missionWindow, manner, cancellationToken)
                    .ConfigureAwait(false) is { } reopenedInManner)
                return reopenedInManner;
            // An arrow or a context menu opens a list or a menu by definition: noted as the opener of what it showed,
            // with its manner, so the burst that reopens it presses its arrow again, never its own action (v3-37).
            if (pressed.Verified && pressed.ErrorCode is null)
                NoteOpenerIn(missionWindow, controlId, label, shownBefore, manner is "open" or "menu", manner);
            return pressed;
        }

        // The window of the view the identity came from. The click by identity no longer brings it forward, so when
        // the identity went stale the cascade by label stays on that window: never on whatever the person has in
        // front meanwhile (their editor, a chat), where its label would be looked for, read and pressed. A click a
        // mission named its window for (v3 point 0 review, «window») stays on that one. Neither is brought to the
        // front here: the accessible tree reaches it behind the person's window, and only the pointer, last, takes
        // the front, inside a burst of the foreground lease after the person's pause (fable/cu-v3-pausa).
        nint viewWindow = 0;
        if (controlId is not null)
        {
            LastView? viewed;
            lock (_viewLock)
            {
                viewed = _lastView;
            }

            if (viewed is not null && VisibleControlSurface.IsAlive(viewed.Hwnd))
                viewWindow = viewed.Hwnd;
        }

        if (controlId is not null)
        {
            HashSet<string>? namesBefore = ChainedNames(opener, missionWindow, controlId, ViewNames(missionWindow));
            bool opens = OpensAgain(missionWindow, controlId);
            ExternalCapabilityReceipt identified = await InvokeUiaAsync(
                operation, label, controlId, missionWindow, cancellationToken).ConfigureAwait(false);
            if (await ReopenShownAsync(operation, opener, identified, label, controlId, missionWindow, null, cancellationToken)
                    .ConfigureAwait(false) is { } reopened)
                return reopened;

            if (identified.Verified && identified.ErrorCode is null)
                NoteOpener(missionWindow, controlId, label, namesBefore, opens);
            // Revision 1 of the branch: an identity this adapter took from the label itself (NamedInView) that failed
            // before any effect leaves the label to its ordinary cascade, as a click by label alone always had.
            bool cascadeAfterNamed = namedByLabel && !identified.Verified && !identified.EffectObserved
                && !identified.EffectMayHaveOccurred && identified.ErrorCode is not null;
            if (identified.ErrorCode != "visible_control_identity_stale" && !cascadeAfterNamed)
            {
                // A control of the view pressed by its identity: the application opened is drawn and answering, so a
                // later click by label does not wait for it to finish opening. v2-u3 «abrí Fotos y andá a Carpetas»:
                // the search field was pressed by identity 2 s after the opening, and the next click by label still
                // waited 26 s for the dark gallery to stop looking blank.
                if (identified.EffectObserved)
                    _ = _focus.TakeOpened();
                return identified;
            }
            // The control moved or was redrawn since the view: the ordinary
            // cascade by label, which is what the reviewer saw, takes over.
        }

        // UI1731 → UI1735: an application that was just opened draws its
        // interface over several seconds (the Epic Games Launcher shows its
        // navigation about ten seconds after its window exists). A label that
        // no stage finds yet is looked for again, bounded, before the click is
        // declared not found — the way a person waits for a screen to load.
        // M132: that wait belongs to the application just opened, on its own
        // window. Its window is waited for (a client that updates itself shows
        // only a small updater at first) and, when it was launched now, its
        // page is waited on until it is drawn — nothing is looked at or pressed
        // meanwhile; then the label for a bounded stretch on each new main
        // window. Any other click looks two or three times and answers.
        VisibleControlSurface.OpenedApplication? opened = _focus.TakeOpened();
        if (opened is { } seenOpening && _openedLooked is { } looked
            && looked.Shows(seenOpening, missionWindow, label))
        {
            // lat-apertura-clic: a look already read the opened application's window after its wait for it, the click
            // names that very window, and the look showed its label (a control so named, or a written line that is
            // the label): the page the label is on is drawn. Its label is looked for there as on any such window,
            // without waiting for the application to finish opening again. Review of the branch (finding 6): a look of
            // a splash that does not show the label (a launcher drawing its navigation seconds later, UI1731) keeps
            // the opening's wait.
            opened = null;
        }

        _openedLooked = null;
        // The first click after one that changed the screen waits the whole stretch (review r10).
        bool afterScreenChange = DateTime.UtcNow - _screenChangedUtc < ScreenChangeFreshness;
        _screenChangedUtc = DateTime.MinValue;
        _lookedWindow = 0;
        nint surfaceWindow = 0;
        bool hovered = false;
        // The window the last look was bound to, where the tooltip stage hovers once the label's wait is over.
        nint hoverWindow = 0;
        DateTime? lookingSince = null;
        // The tree the previous look read on the opened application's window (-1: none yet, or not said).
        int previousTree = -1;
        ExternalCapabilityReceipt? uia = null;
        TimeSpan labelBudget = opened is null ? _timing.SettledLabel : _timing.OpenedLabel;
        DateTime settled = opened is { } noted
            ? noted.NotedUtc + (noted.Launched ? _timing.LaunchSurface : _timing.ReusedSurface)
            : DateTime.MinValue;
        // Whatever happens to the opened application's windows, the click ends by here.
        DateTime cap = (settled > DateTime.UtcNow ? settled : DateTime.UtcNow) + labelBudget;
        while (true)
        {
            bool look = true;
            if (opened is { } application)
            {
                // Located where it is, never brought up (v3 point 0, fix 1): the accessible tree presses the opened
                // window behind the person's, and only the pointer, last, takes the front inside a burst of the lease.
                VisibleControlSurface.OpenedSurface surface = await _focus.FrontAsync(
                    application, judgeDrawn: application.Launched, cancellationToken)
                    .ConfigureAwait(false);
                if (surface.Window != 0 && surface.Window != surfaceWindow)
                {
                    // A login window replaced by the main one is a new surface: its label gets its own wait.
                    surfaceWindow = surface.Window;
                    lookingSince = null;
                    previousTree = -1;
                }
                bool settling = DateTime.UtcNow < settled;
                look = surface.Window != 0 && (surface.Drawn || !settling);
                if (!look && !settling && lookingSince is null)
                    break;
                if (DateTime.UtcNow >= cap)
                {
                    if (await HoverOnceAsync().ConfigureAwait(false) is { } capped)
                        return capped;
                    break;
                }
            }

            if (look)
            {
                lookingSince ??= DateTime.UtcNow;
                // Bound to the opened application's window, to the mission's window or to the window of the view
                // whose identity went stale: nothing is read or pressed on whatever else holds the front (the person
                // took it). The accessible tree reaches the bound window behind; OCR and vision read its own image
                // and press through the tree at the point, or with the pointer only inside a burst of the lease.
                nint boundWindow = opened is not null ? surfaceWindow : missionWindow != 0 ? missionWindow : viewWindow;
                using IDisposable bound = VisibleControlSurface.RequireWindow(boundWindow);
                _lookedTreeSize = -1;
                uia = await InvokeUiaAsync(operation, label, null, boundWindow, cancellationToken)
                    .ConfigureAwait(false);
                if (ShouldKeep(uia))
                    return uia;
                // An administrator's window refuses every stage alike (UIPI): no OCR, tooltip or vision is tried on it.
                if (uia.ErrorCode is WindowElevated or NeedsConfirmation)
                    return uia;
                // lat-apertura-clic (r13a), review of the branch (finding 4): the tree found the control and pressed it,
                // and its post-read saw nothing change. A later stage still looks for the label (the tree may have
                // pressed a hidden duplicate of the visible control, or an Invoke the application accepted and
                // ignored, rescued since 956a89ace), but none presses that same control again (a second press undoes
                // a toggle, sends twice): the worker refuses a point on it before any effect, and the click answers
                // with the tree's own press, without the stage's post-read. The post-read noted the control's identity.
                if (uia.EffectObserved && uia.ErrorCode == "visible_button_postread_unchanged")
                    _pressedUnchanged ??= ControlIdentity(uia);

                if (_ocr is not null)
                {
                    ExternalCapabilityReceipt? ocr = PressedAgain(await _ocr.TryClickAsync(
                        operation, label, this, cancellationToken).ConfigureAwait(false));
                    if (ocr is not null && ShouldKeep(ocr))
                        return ocr;
                    if (ocr is not null && !ShouldCascade(ocr))
                        return ocr;
                }

                // A label no stage found yet may be an icon's: its tooltip is read once per click, on the window the
                // click is bound to only (never the person's window outside a mission), in pauses of the person, and
                // only on the last look: a page still drawing (UI1731: the navigation ten seconds after the window)
                // shows its label to a later look first, and its controls are not hovered half drawn. On a look made
                // when the label's wait is already over, before vision.
                hoverWindow = boundWindow;
                if (DateTime.UtcNow >= lookingSince.Value + labelBudget
                    && await HoverOnceAsync().ConfigureAwait(false) is { } tooltip)
                    return tooltip;

                if (_vision is not null)
                {
                    ExternalCapabilityReceipt? vision = PressedAgain(await _vision.TryClickAsync(
                        operation, label, this, cancellationToken).ConfigureAwait(false));
                    if (vision is not null)
                        return vision;
                }
            }

            // UI1765: a cascade answer («not found yet», no accessible tree)
            // is worth waiting on; any other error (no surface, no window,
            // cancelled) ends the wait.
            if (look && uia?.ErrorCode is { } code && !CascadeAfter.Contains(code))
                break;
            if (lookingSince is { } since && DateTime.UtcNow >= since + labelBudget)
            {
                if (await HoverOnceAsync().ConfigureAwait(false) is { } waited)
                    return waited;
                break;
            }
            // Goal v3, analysis r3a M7 (t-scroll-2, 31 s for a label a system tool just opened never had): after an
            // opening the label is waited for only while the application is still building its interface. Once it was
            // looked for SettledLabel, an interface that is up (its tree holds InterfaceUp elements or more), whose
            // tree did not grow since the previous look and whose window stays still is not drawing the label: «not
            // found» now. A loading screen (a small tree) or a window that changes keeps the whole wait (a client
            // launched cold, UI1731).
            if (opened is not null && look && _surfaceHash is not null && _lookedWindow != 0
                && lookingSince is { } lookedFor && DateTime.UtcNow >= lookedFor + _timing.SettledLabel)
            {
                int tree = _lookedTreeSize;
                bool built = tree >= _timing.InterfaceUp && previousTree >= 0 && tree <= previousTree;
                previousTree = tree;
                if (built)
                {
                    nint watched = _lookedWindow;
                    if (await StaysStillAsync(token => _surfaceHash(watched, token), cancellationToken).ConfigureAwait(false))
                    {
                        if (await HoverOnceAsync().ConfigureAwait(false) is { } settledTip)
                            return settledTip;
                        break;
                    }

                    continue;
                }
            }
            else if (opened is not null && look)
            {
                previousTree = _lookedTreeSize;
            }

            if (opened is null && _surfaceHash is not null && !afterScreenChange && _lookedWindow != 0)
            {
                // A window that was already there and stays still is not drawing the label: answer now. One that
                // changes is looked at again at once. The window watched is the one the look read and the click
                // targets, never whatever holds the front meanwhile (review r10).
                nint watched = _lookedWindow;
                if (await StaysStillAsync(token => _surfaceHash(watched, token), cancellationToken).ConfigureAwait(false))
                {
                    if (await HoverOnceAsync().ConfigureAwait(false) is { } still)
                        return still;
                    break;
                }

                continue;
            }
            await Task.Delay(_timing.Interval, cancellationToken).ConfigureAwait(false);
        }

        // Nothing looked at means nothing pressed: no window of the opened application ever showed.
        if (uia is null)
            return ExternalJson.FailureBeforeEffect(operation, "visible_button_not_found");
        return uia.ErrorCode is null
            ? ExternalJson.Failure(operation, "visible_button_not_found")
            : uia;

        // The tooltip stage, once per click, when the label's wait is over (its time is not the wait's): on the window
        // the last look was bound to, never without one.
        async ValueTask<ExternalCapabilityReceipt?> HoverOnceAsync()
        {
            if (_tooltip is null || hovered || hoverWindow == 0)
                return null;
            hovered = true;
            using IDisposable boundToLook = VisibleControlSurface.RequireWindow(hoverWindow);
            return PressedAgain(await _tooltip.TryClickAsync(operation, label, this, cancellationToken).ConfigureAwait(false));
        }

        // A later stage's point on the control the tree already pressed: the click is the tree's press, as it went.
        ExternalCapabilityReceipt? PressedAgain(ExternalCapabilityReceipt? stage) =>
            stage?.ErrorCode == PointAlreadyPressed && uia is not null ? uia : stage;
    }

    // Watches the window in front for up to Interval: true when it stayed exactly the same for StillFor, false as soon
    // as it changes, when it cannot be captured (then the whole interval is waited, as before) or at the interval.
    private async ValueTask<bool> StaysStillAsync(
        Func<CancellationToken, ValueTask<string?>> surfaceHash,
        CancellationToken cancellationToken)
    {
        var watch = Stopwatch.StartNew();
        string? first = await surfaceHash(cancellationToken).ConfigureAwait(false);
        if (first is null)
        {
            TimeSpan rest = _timing.Interval - watch.Elapsed;
            if (rest > TimeSpan.Zero)
                await Task.Delay(rest, cancellationToken).ConfigureAwait(false);
            return false;
        }

        var still = Stopwatch.StartNew();
        while (watch.Elapsed < _timing.Interval)
        {
            await Task.Delay(_timing.StillSample, cancellationToken).ConfigureAwait(false);
            string? now = await surfaceHash(cancellationToken).ConfigureAwait(false);
            if (now is null || !string.Equals(now, first, StringComparison.Ordinal))
                return false;
            if (still.Elapsed >= _timing.StillFor)
                return true;
        }

        return false;
    }

    private static async ValueTask<string?> WindowSurfaceHashAsync(nint window, CancellationToken cancellationToken)
    {
        if (!VisibleControlSurface.IsAlive(window))
            return null;
        try
        {
            return (await VisibleControlSurface.CaptureAsync(window, cancellationToken).ConfigureAwait(false))?.Sha256;
        }
        catch (Exception exception) when (exception is IOException or InvalidOperationException)
        {
            return null;
        }
    }

    // ---------------------------------------------------------------- view

    // How long a tied look waits for a window of the mission's process when its own closed: 8 × 250 ms.
    private const int MissionWindowWaits = 8;
    private static readonly TimeSpan MissionWindowWaitInterval = TimeSpan.FromMilliseconds(250);

    // Window handles a look names (a mission's windows, the windows it knows are not its): positive numbers only.
    private static List<nint> Handles(JsonElement arguments, string name)
    {
        var handles = new List<nint>();
        if (!arguments.TryGetProperty(name, out JsonElement list) || list.ValueKind != JsonValueKind.Array)
            return handles;
        foreach (JsonElement item in list.EnumerateArray())
        {
            if (item.ValueKind == JsonValueKind.Number && item.TryGetInt64(out long handle) && handle > 0)
                handles.Add((nint)handle);
        }

        return handles;
    }

    private async ValueTask<ExternalCapabilityReceipt> ListAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        int limit = 60;
        bool includeText = false;
        string? waitForLabel = null;
        int processId = 0;
        string? application = null;
        bool starting = false;
        bool identityIfAbsent = false;
        bool tail = false;
        bool lines = false;
        // Goal v3 ventana-misión: the windows the mission is tied to (the latest first) and the ones it knows are not its.
        List<nint> missionWindows = [];
        HashSet<nint> knownWindows = [];
        IReadOnlyList<string> wanted = [];
        if (arguments.ValueKind == JsonValueKind.Object)
        {
            wanted = WantedWords(arguments);
            missionWindows = Handles(arguments, "windows");
            knownWindows = [.. Handles(arguments, "known")];
            if (arguments.TryGetProperty("application", out JsonElement named)
                && named.ValueKind == JsonValueKind.String
                && !string.IsNullOrWhiteSpace(named.GetString()))
            {
                application = named.GetString()!.Trim();
            }

            if (arguments.TryGetProperty("processId", out JsonElement owner)
                && owner.ValueKind == JsonValueKind.Number
                && owner.TryGetInt32(out int requestedProcess) && requestedProcess > 0)
            {
                processId = requestedProcess;
            }

            if (arguments.TryGetProperty("limit", out JsonElement requested)
                && requested.ValueKind == JsonValueKind.Number
                && requested.TryGetInt32(out int value))
            {
                limit = Math.Clamp(value, 1, 60);
            }

            includeText = arguments.TryGetProperty("includeText", out JsonElement wantsText)
                && wantsText.ValueKind == JsonValueKind.True;
            starting = arguments.TryGetProperty("starting", out JsonElement startingValue)
                && startingValue.ValueKind == JsonValueKind.True;
            identityIfAbsent = arguments.TryGetProperty("identityIfAbsent", out JsonElement identityValue)
                && identityValue.ValueKind == JsonValueKind.True;
            tail = arguments.TryGetProperty("tail", out JsonElement tailValue) && tailValue.ValueKind == JsonValueKind.True;
            lines = arguments.TryGetProperty("lines", out JsonElement linesValue) && linesValue.ValueKind == JsonValueKind.True;
            includeText |= lines;
            if (arguments.TryGetProperty("waitForLabel", out JsonElement waited)
                && waited.ValueKind == JsonValueKind.String
                && !string.IsNullOrWhiteSpace(waited.GetString()))
            {
                waitForLabel = waited.GetString()!.Trim();
            }

            // Ronda 21, destino por contenido: a mission with no application and no window of its own asks for the
            // windows on the desktop, each with a cheap signature of its tree, to find the one its request's referent
            // is in. Nothing is brought to the front nor captured.
            if (AsksForCandidates(arguments, missionWindows.Count, processId, application))
            {
                return await DestinationCandidatesAsync(limit, cancellationToken).ConfigureAwait(false);
            }
        }

        // M132: a look right after an opening reads the application opened, not what was in front before it. A look
        // bound to the mission's process reads that process's window whatever is in front, so the opened application
        // is not looked for first (about 275 ms on every view of a mission, measured). Neither is brought to the
        // front (v3 point 0): the accessible tree and the window's own image are read behind the person's window.
        nint openedWindow = 0;
        if (processId == 0 && _focus.PeekOpened() is { } opened)
        {
            openedWindow = (await _focus.FrontAsync(opened, judgeDrawn: false, cancellationToken)
                .ConfigureAwait(false)).Window;
        }

        // v3 point 1: a look while the application opened cold is starting hands back a front it took by itself
        // (measured: a game launcher activated its window when it was created and again when it maximized, 4.5 s and
        // 6.3 s after the opening, past the opening's own guard), and the view says so for the annoyance count.
        bool frontReturned = starting && processId > 0
            && Applications.ForegroundHandBack.ReturnIfTakenAtStart(processId, VisibleControlSurface.InApplicationFamily);
        DateTime deadline = DateTime.UtcNow + LabelWaitBudget;
        while (true)
        {
            ViewResult view = await BuildViewAsync(
                    limit, includeText, processId, application, openedWindow, cancellationToken, frontReturned,
                    missionWindows, knownWindows, wanted, identityIfAbsent, tail, lines)
                .ConfigureAwait(false);
            if (view.Receipt.ErrorCode is not null)
                return view.Receipt;
            if (waitForLabel is null || view.Names.Any(name => SameLabel(waitForLabel, name))
                || DateTime.UtcNow >= deadline)
            {
                NoteOpenedLooked(view.Receipt, processId, view.Names);
                return view.Receipt;
            }

            await Task.Delay(LabelWaitInterval, cancellationToken).ConfigureAwait(false);
        }
    }

    // lat-apertura-clic (r13a: Epic 27.3 s on a click by label, its view of 0 controls): the opening a look read the
    // window of (its process, or one of the processes that draw it). The look's caller waited for that window already
    // (the mission's bounded wait after app.open): the click decided on that look does not wait for the application to
    // finish opening again.
    private OpenedLook? _openedLooked;

    /// <summary>A look of the opened application's window: the opening, the window read and what it showed (its
    /// controls' names and its written lines).</summary>
    private sealed record OpenedLook(int ProcessId, DateTime NotedUtc, nint Window, IReadOnlyList<string> Names)
    {
        /// <summary>Whether a click on <paramref name="window"/> by <paramref name="label"/> was decided on this look
        /// of <paramref name="opening"/>: the same opening, the same window, and the label shown on it as a whole
        /// control's name or written line; never inside a longer one («Cargando tu biblioteca» on a splash is not the
        /// «Biblioteca» of its navigation).</summary>
        internal bool Shows(VisibleControlSurface.OpenedApplication opening, nint window, string label)
        {
            if (window == 0 || window != Window || opening.ProcessId != ProcessId || opening.NotedUtc != NotedUtc)
                return false;
            string wanted = WindowsVisibleOcrLocator.Fold(label);
            return wanted.Length > 0 && Names.Any(name =>
                string.Equals(WindowsVisibleOcrLocator.Fold(name), wanted, StringComparison.Ordinal));
        }
    }

    internal void NoteOpenedLooked(ExternalCapabilityReceipt receipt, int requestedProcess, IReadOnlyList<string> names)
    {
        if (_focus.PeekOpened() is not { } opened
            || receipt.Result is not { ValueKind: JsonValueKind.Object } result
            || !result.TryGetProperty("window", out JsonElement window)
            || window.ValueKind != JsonValueKind.Object
            || !window.TryGetProperty("hwnd", out JsonElement handle) || !handle.TryGetInt64(out long hwnd) || hwnd <= 0)
            return;
        bool ofIt = (requestedProcess == opened.ProcessId
                && window.TryGetProperty("requested", out JsonElement requested) && requested.ValueKind == JsonValueKind.True)
            || (window.TryGetProperty("processId", out JsonElement owner) && owner.ValueKind == JsonValueKind.Number
                && owner.TryGetInt32(out int ownerId) && ownerId == opened.ProcessId)
            || (window.TryGetProperty("family", out JsonElement family) && family.ValueKind == JsonValueKind.Array
                && family.EnumerateArray().Any(member => member.ValueKind == JsonValueKind.Number
                    && member.TryGetInt64(out long id) && id == opened.ProcessId));
        if (ofIt)
            _openedLooked = new OpenedLook(opened.ProcessId, opened.NotedUtc, (nint)hwnd, [.. names]);
    }

    /// <summary>How many windows on the desktop a request's referent is looked for in (top of the Z order first).</summary>
    internal const int DestinationCandidateLimit = 8;

    /// <summary>
    /// Revision 1 of r21 (B4): the whole listing's budget. Each window's signature is read under what is left of it (at
    /// most <see cref="DestinationWindowBudgetMs"/>); a window not read in time goes out marked <c>unread</c>, never
    /// guessed, and the listing always answers well inside the App's own timeout.
    /// </summary>
    internal const int DestinationBudgetMs = 4000;

    /// <summary>Revision 1 of r21 (B4): one window's signature budget; the worker's own walk stops at it.</summary>
    internal const int DestinationWindowBudgetMs = 1200;

    // Below this much budget left a window is not asked for: its answer could not come in time.
    private const int DestinationWindowMinimumMs = 200;

    // How much after the window's budget the worker's answer may still come (its own reading of the clock, the pipe).
    private static readonly TimeSpan DestinationAnswerMargin = TimeSpan.FromMilliseconds(1500);

    /// <summary>
    /// Revision 1 of r21 (B5): the desktop as the destination's search reads it (a test names its own windows).
    /// </summary>
    internal Func<(IReadOnlyList<VisibleControlSurface.DestinationWindow> Windows, nint Front)> DestinationDesktop { get; init; } =
        VisibleControlSurface.DestinationDesktop;

    /// <summary>Revision 1 of r21 (B5): the listing's clock in milliseconds (a test advances its own).</summary>
    internal Func<long> DestinationClockMs { get; init; } = static () => Environment.TickCount64;

    /// <summary>
    /// Ronda 21, destino por contenido: whether a look asks for the desktop's windows instead of one window. Only a look
    /// of a mission with no window of its own, no process and no application does: one that has any of them reads it as
    /// always, and the request for candidates is ignored.
    /// </summary>
    internal static bool AsksForCandidates(JsonElement arguments, int missionWindows, int processId, string? application) =>
        arguments.ValueKind == JsonValueKind.Object
        && arguments.TryGetProperty("candidates", out JsonElement candidates) && candidates.ValueKind == JsonValueKind.True
        && missionWindows == 0 && processId == 0 && application is null;

    /// <summary>
    /// Ronda 21, destino por contenido: the desktop's windows (top of the Z order first, cloaked ones left out), each
    /// with its title, process, whether it holds the front, whether it is a developer's or BAXY's own (<c>protected</c>,
    /// listed without its tree), the person's input to it, and a signature of its accessible tree (no capture, no OCR).
    /// The App weighs them against the request's referent; the provider decides nothing. Revision 1 of r21 (B2, B4): the
    /// signature is the worker's cheap one (<c>signature</c>: a walk bounded in nodes and in time, without the client
    /// re-read, the HMENU entries or the disabled re-read, and leaving the worker's last view alone), with
    /// <c>selection</c> read from the text pattern of the window's documents and fields (a non-empty selected range);
    /// the whole listing runs under <see cref="DestinationBudgetMs"/>, and a window it could not read goes out
    /// <c>unread</c>.
    /// </summary>
    private async ValueTask<ExternalCapabilityReceipt> DestinationCandidatesAsync(int limit, CancellationToken cancellationToken)
    {
        const string operation = "input.visible.controls";
        long started = DestinationClockMs();
        (IReadOnlyList<VisibleControlSurface.DestinationWindow> desktop, nint front) = DestinationDesktop();
        var read = new List<(VisibleControlSurface.DestinationWindow Window, bool Protected, bool Unread, bool Selection, List<ViewControl> Controls)>();
        foreach (VisibleControlSurface.DestinationWindow window in desktop.Where(window => !window.Cloaked).Take(DestinationCandidateLimit))
        {
            cancellationToken.ThrowIfCancellationRequested();
            List<ViewControl> controls = [];
            bool selection = false;
            bool unread = false;
            bool isProtected = VisibleControlSurface.ProtectedFrom(window.Process, null);
            // A developer's or BAXY's own window is listed without its tree: nothing of it is read for a mission.
            if (!isProtected)
            {
                long left = DestinationBudgetMs - (DestinationClockMs() - started);
                if (left < DestinationWindowMinimumMs)
                {
                    unread = true;
                }
                else
                {
                    int budget = (int)Math.Min(DestinationWindowBudgetMs, left);
                    using JsonDocument? answer = await _worker.SendAsync(
                            new JsonObject { ["cmd"] = "signature", ["hwnd"] = window.Window, ["limit"] = limit, ["budgetMs"] = budget }
                                .ToJsonString(),
                            TimeSpan.FromMilliseconds(budget) + DestinationAnswerMargin, cancellationToken)
                        .ConfigureAwait(false);
                    if (answer is not null && answer.RootElement.TryGetProperty("ok", out JsonElement ok) && ok.ValueKind == JsonValueKind.True)
                    {
                        controls = ParseControls(answer.RootElement);
                        selection = answer.RootElement.TryGetProperty("selection", out JsonElement selected)
                            && selected.ValueKind == JsonValueKind.True;
                        // A walk the budget cut before any control came is no reading of the window.
                        unread = controls.Count == 0 && !selection
                            && answer.RootElement.TryGetProperty("complete", out JsonElement complete)
                            && complete.ValueKind == JsonValueKind.False;
                    }
                    else
                    {
                        unread = true;
                    }
                }
            }

            read.Add((window, isProtected, unread, selection, controls));
        }

        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 2);
            writer.WriteStartArray("candidateWindows");
            foreach ((VisibleControlSurface.DestinationWindow window, bool isProtected, bool unread, bool selection, List<ViewControl> controls) in read)
            {
                writer.WriteStartObject();
                writer.WriteNumber("hwnd", window.Window);
                writer.WriteNumber("processId", window.ProcessId);
                writer.WriteString("process", window.Process);
                writer.WriteString("title", window.Title);
                writer.WriteBoolean("foreground", window.Window == front);
                if (isProtected)
                    writer.WriteBoolean("protected", true);
                if (unread)
                    writer.WriteBoolean("unread", true);
                if (selection)
                    writer.WriteBoolean("selection", true);
                if (window.PersonInputAgoMs is long ago)
                    writer.WriteNumber("personInputAgoMs", ago);
                writer.WriteStartArray("controls");
                foreach (ViewControl control in controls)
                {
                    writer.WriteStartObject();
                    writer.WriteString("kind", control.Kind);
                    writer.WriteString("name", control.Name);
                    // Revision 1 of ronda 24 (B1): a control inside a Document is the content the window shows, never
                    // its frame (a page's «Guardar» or «Archivo»).
                    if (control.Content)
                        writer.WriteBoolean("content", true);
                    writer.WriteEndObject();
                }

                writer.WriteEndArray();
                writer.WriteEndObject();
            }

            writer.WriteEndArray();
            if (WindowsUserInputPause.Shared.UnknownInputAgoMs is long unknownAgo)
                writer.WriteNumber("personInputUnknownAgoMs", unknownAgo);
            writer.WriteNumber("elapsedMs", DestinationClockMs() - started);
            writer.WriteString("authority", "windows_uia_snapshot_candidates");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, false);
    }

    /// <summary>Ronda 21: the goal's words the mission's look carries («wanted», declared in the catalog), at most 24
    /// non-empty texts of at most 64 characters; anything else is no word.</summary>
    internal static IReadOnlyList<string> WantedWords(JsonElement arguments)
    {
        if (arguments.ValueKind != JsonValueKind.Object
            || !arguments.TryGetProperty("wanted", out JsonElement given)
            || given.ValueKind != JsonValueKind.Array)
        {
            return [];
        }

        List<string> words = [];
        foreach (JsonElement item in given.EnumerateArray())
        {
            if (item.ValueKind == JsonValueKind.String && item.GetString() is { } word
                && !string.IsNullOrWhiteSpace(word) && System.Text.Encoding.UTF8.GetByteCount(word.Trim()) <= 64
                && words.Count < 24)
            {
                words.Add(word.Trim());
            }
        }

        return words;
    }

    /// <summary>Encargo WA5: the answer a look goes on with when the worker's walk of the tree threw
    /// (<c>visible_controls_uia_failed</c>) on a window that is still there (<paramref name="alive"/>): a window without a
    /// tree, read from what it draws, carrying the worker's reason («uiaFailed»). Null for any other answer, and for a
    /// window that is gone (its look fails as before).</summary>
    internal static JsonDocument? WithoutTree(JsonElement answer, nint window, Func<nint, bool> alive)
    {
        if (!answer.TryGetProperty("error", out JsonElement error) || error.ValueKind != JsonValueKind.String
            || error.GetString() != "visible_controls_uia_failed"
            || (answer.TryGetProperty("ok", out JsonElement ok) && ok.ValueKind == JsonValueKind.True)
            || !alive(window))
        {
            return null;
        }

        string reason = answer.TryGetProperty("detail", out JsonElement detail) && detail.ValueKind == JsonValueKind.String
            ? detail.GetString() ?? string.Empty
            : string.Empty;
        return JsonDocument.Parse(
            new JsonObject { ["ok"] = true, ["controls"] = new JsonArray(), ["uiaFailed"] = reason }.ToJsonString());
    }

    /// <summary>The worker's «view» request; the goal's words go only when there are some (a look outside a mission is
    /// the one it always was).</summary>
    internal static string ViewCommand(nint hwnd, int limit, IReadOnlyList<string>? wanted, bool tail = false)
    {
        var command = new JsonObject { ["cmd"] = "view", ["hwnd"] = hwnd, ["limit"] = limit };
        if (tail)
        {
            // Encargo IMP3: the cut keeps the last entries of the tree (what the window drew last), not the first.
            command["tail"] = true;
        }

        if (wanted is { Count: > 0 })
        {
            command["wanted"] = new JsonArray([.. wanted.Select(static word => (JsonNode?)JsonValue.Create(word))]);
        }

        return command.ToJsonString();
    }

    private async ValueTask<ViewResult> BuildViewAsync(
        int limit,
        bool includeText,
        int processId,
        string? application,
        nint openedWindow,
        CancellationToken cancellationToken,
        bool frontReturned = false,
        IReadOnlyList<nint>? missionWindows = null,
        IReadOnlySet<nint>? knownWindows = null,
        IReadOnlyList<string>? wanted = null,
        bool identityIfAbsent = false,
        bool tail = false,
        bool lines = false) =>
        await BuildViewOfAsync(
            limit, includeText, processId, application, openedWindow, frontReturned,
            missionWindows ?? [], knownWindows ?? new HashSet<nint>(), wanted ?? [], identityIfAbsent, tail, lines,
            cancellationToken)
            .ConfigureAwait(false);

    private async ValueTask<ViewResult> BuildViewOfAsync(
        int limit,
        bool includeText,
        int processId,
        string? application,
        nint openedWindow,
        bool frontReturned,
        IReadOnlyList<nint> missionWindows,
        IReadOnlySet<nint> knownWindows,
        IReadOnlyList<string> wanted,
        bool identityIfAbsent,
        bool tail,
        bool lines,
        CancellationToken cancellationToken)
    {
        const string operation = "input.visible.controls";
        var stopwatch = Stopwatch.StartNew();
        nint hwnd = 0;
        nint cover = 0;
        bool requested = false;
        // Encargo EX: the window was read through the modal dialog that disabled it (ModalSurface).
        bool modal = false;
        bool born = false;
        bool frontOnly = false;
        // The top-level window the look is of, before its modal dialog is taken: what a mission ties itself to.
        nint windowRoot = 0;
        try
        {
            // Goal v3 ventana-misión: a mission tied to its windows reads one of them, or a window of its process that
            // came during the mission (said «born», for the mission to keep or refuse); never another window of the
            // process it already knew (another document of the same application), never the window in front instead.
            bool tied = missionWindows.Count > 0;
            if (tied)
            {
                // Review of ventana-misión (finding 11): the mission's window closed and the next of its process (a
                // sign-in giving way to the main window) may not be there yet: waited for, bounded, before failing.
                for (int wait = 0; ; wait++)
                {
                    windowRoot = VisibleControlSurface.MissionWindow(missionWindows, knownWindows, processId, out born);
                    hwnd = windowRoot == 0 ? 0 : VisibleControlSurface.FamilySurface(windowRoot);
                    if (hwnd != 0 || processId <= 0 || wait >= MissionWindowWaits)
                        break;
                    await Task.Delay(MissionWindowWaitInterval, cancellationToken).ConfigureAwait(false);
                }

                if (hwnd == 0)
                    return new ViewResult(ExternalJson.Failure(operation, "mission_window_closed"), []);
            }

            // «The browser» without a name is the person's own: the front
            // window of their default browser, whichever of its windows the
            // process holds and whatever is in front (read where it is).
            bool theBrowser = !tied && IUserBrowserWindowLocator.NamesTheCategory(application);
            if (theBrowser)
                hwnd = _browserWindow.FrontWindow();

            // The application the mission works on (the one it just opened, or
            // the one named when its process is unknown) is the surface even
            // when another window holds the foreground.
            if (hwnd == 0 && !tied && processId > 0)
            {
                hwnd = await VisibleControlSurface.ResolveProcessWindowAsync(processId, cancellationToken)
                    .ConfigureAwait(false);
            }

            // The category is no title: a window whose title says «navegador»
            // is not the person's browser.
            if (hwnd == 0 && !tied && application is not null && !theBrowser)
            {
                hwnd = await VisibleControlSurface.ResolveTitledWindowAsync(application, cancellationToken)
                    .ConfigureAwait(false);
            }

            // Whether the window is the mission's application (its process, its
            // title, the person's browser) and not just what holds the front.
            requested = hwnd != 0;
            // The application just opened, where it is (behind the person's window, as it was opened).
            if (hwnd == 0 && openedWindow != 0 && VisibleControlSurface.IsAlive(openedWindow))
                hwnd = openedWindow;
            // Ronda 26 (banco c24b: 54 first looks of 1.2 s read the person's window before an opening already decided):
            // the application has no window and the look asked only who is in front then: no tree, capture or text.
            frontOnly = identityIfAbsent && hwnd == 0;
            if (hwnd == 0)
            {
                hwnd = await VisibleControlSurface.ResolveForegroundAsync(cancellationToken)
                    .ConfigureAwait(false);
            }

            // Another process drawn over the window (a fullscreen player, the
            // person's own window): the view is read all the same, since the
            // accessible tree and the window's own image are the window's (v3
            // point 0). The cover is said for the acts by coordinates only,
            // which land on whatever is on top.
            if (hwnd != 0)
            {
                windowRoot = VisibleControlSurface.ApplicationRoot(hwnd);
                // A window its own modal dialog disabled is seen, and then acted on, through that dialog.
                nint disabled = hwnd;
                hwnd = VisibleControlSurface.ModalSurface(hwnd);
                modal = hwnd != disabled;
                // A minimized window is shown behind the person's own before its tree is read (it shrinks while
                // minimized) and before it is captured.
                VisibleControlSurface.ShowBehind(hwnd);
                cover = VisibleControlSurface.CoveringWindow(hwnd);
            }
        }
        catch (Exception exception) when (exception is IOException or InvalidOperationException)
        {
            hwnd = 0;
        }

        if (hwnd == 0)
            return new ViewResult(ExternalJson.Failure(operation, "active_window_not_found"), []);

        string command = ViewCommand(hwnd, limit, wanted, tail);
        // One capture serves the colours, the written text and the surface
        // hash; a window without an accessible tree (CEF, SDL, canvas) is
        // read from what is drawn, the case measured in a game launcher (UI1731).
        // The capture, and the text when it is asked for, are read while the
        // worker walks the accessible tree: they do not wait on each other.
        // A window another process draws over is captured as it draws itself, never the screen where the cover is.
        // Encargo IMP4: the written lines with their place («lines») are read from the window's own drawing, never from
        // the screen (imp3: the screen copy of a chat client covered by another window read the other window's text).
        bool covered = cover != 0 || lines;
        nint firstLooked = hwnd;
        Task<VisibleControlSurface.CapturedWindow?> captureTask = frontOnly
            ? Task.FromResult<VisibleControlSurface.CapturedWindow?>(null)
            : Task.Run(() => CaptureQuietlyAsync(firstLooked, covered, cancellationToken), CancellationToken.None);
        Task<WrittenText>? textTask = includeText && !frontOnly ? ReadTextAsync(captureTask, lines ? PlacedLinesRead : limit, cancellationToken, placed: lines) : null;
        JsonDocument? answer = frontOnly
            ? JsonDocument.Parse("""{"ok":true,"controls":[]}""")
            : await _worker.SendAsync(command, WorkerViewBudget, cancellationToken).ConfigureAwait(false);
        if (answer is null)
        {
            return new ViewResult(ExternalJson.Failure(operation, "visible_controls_unavailable"), []);
        }

        // Ronda 20 P6 (v3-15, v3-16, v3-17): an application's window whose tree is only its caption parts (title bar,
        // caption buttons, the non-client input, a busy indicator) over the content window a process it started draws
        // under it (measured: a WinUI frame activated by a click lay above its WebView2 editor, and the view kept the
        // caption parts while the person saw the editor) is read through that content window, linked to it as the
        // family surface over it is: the mission stays tied to the application's window. What was found, or why nothing
        // was, is said.
        VisibleControlSurface.ContentChoice? surfaceChoice = null;
        if (!frontOnly && hwnd == windowRoot && VisibleControlSurface.SurfaceFamily(hwnd) is null
            && answer.RootElement.TryGetProperty("ok", out JsonElement frameOk) && frameOk.ValueKind == JsonValueKind.True
            && VisibleControlSurface.TryBounds(hwnd, out int frameLeft, out int frameTop, out int frameRight, out int frameBottom))
        {
            var frame = (frameLeft, frameTop, frameRight, frameBottom);
            var frameControls = CaptionReading(answer.RootElement);
            if (VisibleControlSurface.MayShowOnlyCaption(frame, frameControls))
            {
                VisibleControlSurface.ContentChoice choice = VisibleControlSurface.TakeContentWindow(
                    hwnd, content => VisibleControlSurface.ShowsOnlyCaption(frame, content, frameControls));
                surfaceChoice = choice;
                if (choice.Window != 0)
                {
                    answer.Dispose();
                    Discard(captureTask, textTask);
                    nint content = choice.Window;
                    hwnd = content;
                    cover = VisibleControlSurface.CoveringWindow(content);
                    bool contentCovered = cover != 0 || lines;
                    captureTask = Task.Run(
                        () => CaptureQuietlyAsync(content, contentCovered, cancellationToken), CancellationToken.None);
                    textTask = includeText ? ReadTextAsync(captureTask, lines ? PlacedLinesRead : limit, cancellationToken, placed: lines) : null;
                    answer = await _worker.SendAsync(
                            ViewCommand(content, limit, wanted, tail),
                            WorkerViewBudget, cancellationToken)
                        .ConfigureAwait(false);
                    if (answer is null)
                        return new ViewResult(ExternalJson.Failure(operation, "visible_controls_unavailable"), []);
                }
            }
        }

        // Encargo WA5 (wab3, 4 de 4): the worker's walk of a window that is still there threw. The look is not lost: the
        // window is read as one without a tree, from what it draws (its text, below), and the look says why. A window
        // that is gone fails as before.
        if (WithoutTree(answer.RootElement, hwnd, VisibleControlSurface.IsAlive) is { } withoutTree)
        {
            answer.Dispose();
            answer = withoutTree;
        }

        long uiaMs = stopwatch.ElapsedMilliseconds;
        using (answer)
        {
            JsonElement root = answer.RootElement;
            if (!root.TryGetProperty("ok", out JsonElement ok) || ok.ValueKind != JsonValueKind.True)
            {
                string code = root.TryGetProperty("error", out JsonElement error)
                    && error.ValueKind == JsonValueKind.String
                    && error.GetString() is { Length: > 0 } text
                        ? text
                        : "visible_controls_unavailable";
                return new ViewResult(ExternalJson.Failure(operation, code), []);
            }

            List<ViewControl> controls = ParseControls(root);
            // Pasada r15b (v3-27, v3-29): the actionables the window shows disabled (a «Copy» waiting for text), apart:
            // the mind knows they exist and wait for input; nothing presses them (no identity).
            List<ViewControl> disabled = ParseControls(root, "disabled");
            // Whether the window held the front when its tree was read: only then can its keyboard focus be told.
            bool inFront = VisibleControlSurface.ForegroundIs(hwnd);
            int counted = root.TryGetProperty("controlCount", out JsonElement total)
                && total.ValueKind == JsonValueKind.Number && total.TryGetInt32(out int totalValue)
                    ? totalValue
                    : controls.Count;
            string title = root.TryGetProperty("window", out JsonElement named)
                && named.ValueKind == JsonValueKind.String
                    ? named.GetString() ?? string.Empty
                    : string.Empty;
            if (title.Length == 0)
                title = VisibleControlSurface.WindowTitle(hwnd);
            // A packaged app's frame names the app it hosts, never the frame host every packaged app shares.
            (int ownerProcessId, string processName) = VisibleControlSurface.ViewProcess(hwnd);
            VisibleControlSurface.TryBounds(hwnd, out int left, out int top, out int right, out int bottom);
            var windowRect = new Rect(left, top, right - left, bottom - top);

            VisibleControlSurface.CapturedWindow? captured = await captureTask.ConfigureAwait(false);
            long colorMs = 0;
            long ocrMs = 0;
            Dictionary<string, List<string>> textZones = new(StringComparer.Ordinal);
            string? textAuthority = null;
            List<VisibleTextMarks.Mark>? textMarks = null;
            IReadOnlyList<WindowsVisibleOcrLocator.LayoutLine>? placedLines = null;
            (int Width, int Height) placedIn = (0, 0);
            var names = new List<string>();
            if (captured is { } capture)
            {
                var colourWatch = Stopwatch.StartNew();
                VisibleControlColors.Assign(capture, controls);
                colorMs = colourWatch.ElapsedMilliseconds;
                // Not asked for, the text is still read when the tree shows nothing to act on.
                if (textTask is null && controls.Count <= 1)
                    textTask = ReadTextAsync(captureTask, limit, cancellationToken);
                if (textTask is not null)
                {
                    (IReadOnlyList<WindowsVisibleOcrLocator.LayoutLine>? read, ocrMs) =
                        await textTask.ConfigureAwait(false);
                    if (read is not null)
                    {
                        if (lines)
                        {
                            placedLines = read;
                            placedIn = (capture.Width, capture.Height);
                        }

                        textAuthority = "windows_media_ocr_lines";
                        foreach (WindowsVisibleOcrLocator.LayoutLine line in ScreenStateLines.Grouped(read))
                        {
                            string zone = Zone(
                                line.X + line.Width / 2, line.Y + line.Height / 2,
                                new Rect(0, 0, capture.Width, capture.Height));
                            if (!textZones.TryGetValue(zone, out List<string>? bucket))
                            {
                                bucket = [];
                                textZones[zone] = bucket;
                            }

                            bucket.Add(line.Text);
                            names.Add(line.Text);
                        }

                        // Where the written text is all the window shows, each label carries the colour of its ink
                        // (contract §1.7): the item a row of navigation labels marks is read from it (check atom mark:).
                        if (controls.Count <= 1)
                            textMarks = VisibleTextMarks.Read(capture.Bmp, capture.Left, capture.Top, read);
                    }
                    else
                    {
                        textAuthority = "unavailable";
                    }
                }
            }

            foreach (ViewControl control in disabled)
            {
                control.Zone = control.RectValue is { } rect
                    ? Zone(rect.X + rect.W / 2, rect.Y + rect.H / 2, windowRect)
                    : string.Empty;
            }

            foreach (ViewControl control in controls)
            {
                control.Zone = control.RectValue is { } rect
                    ? Zone(rect.X + rect.W / 2, rect.Y + rect.H / 2, windowRect)
                    : string.Empty;
                names.Add(control.Name);
            }

            lock (_viewLock)
            {
                _lastView = new LastView(hwnd, controls);
                _viewsRead++;
            }

            JsonElement result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 2);
                writer.WriteBoolean("ok", true);
                writer.WriteString("error", string.Empty);
                if (frontOnly)
                    writer.WriteBoolean("identityOnly", true);
                // r29 (pasada r27 v3-20, v3-22, v3-72): the application the look was asked for is a live process
                // raised above this one that shows no window a lower process can find: the look says so, and the
                // mission stops with that cause instead of reading the window in front in its place.
                if (frontOnly && VisibleControlSurface.LiveProcessRunsAboveUs(processId))
                    writer.WriteBoolean("applicationElevated", true);
                // Fronts an application opened just before took by itself and the guard handed back (v3 point 0), and
                // those Windows refused to hand back (the application kept the front).
                long activationsReturned = Applications.ForegroundHandBack.TakeGuardReturns();
                if (activationsReturned > 0)
                    writer.WriteNumber("windowsActivationsReturned", activationsReturned);
                long activationsKept = Applications.ForegroundHandBack.TakeGuardRefusals();
                if (activationsKept > 0)
                    writer.WriteNumber("windowsActivationsNotReturned", activationsKept);
                writer.WriteStartObject("window");
                writer.WriteString("title", title);
                writer.WriteString("process", processName);
                writer.WriteNumber("processId", ownerProcessId);
                writer.WriteNumber("hwnd", hwnd);
                writer.WriteBoolean("requested", requested);
                // Goal v3 ventana-misión: the top-level window the mission ties itself to (the window behind its modal
                // dialog, the application's window behind its family surface), the window owning that one, whether it
                // came during the mission, the other windows of its process when a mission takes its window, and how
                // long ago the person's last input went to it (the window they work in).
                if (windowRoot != 0)
                    writer.WriteNumber("root", windowRoot);
                // Encargo EX (tanda n6 t4-c06: Excel held «Guardar este archivo» from an earlier turn): the view is of
                // the modal dialog that disabled the window, not of the window itself.
                if (modal)
                    writer.WriteBoolean("modal", true);
                if (VisibleControlSurface.RootOwner(windowRoot) is var owner and not 0)
                    writer.WriteNumber("owner", owner);
                if (born)
                    writer.WriteBoolean("born", true);
                // Review of ventana-misión (finding 1): how long ago the person's input last reached a window of its
                // process or of the shell (they may have opened, restored or started it themselves). Said of a born
                // window and of a look that names no window: after the mission's window closed, the window it is tied
                // to again is judged as one born (review of ronda 19b).
                if ((born || missionWindows.Count == 0)
                    && WindowsUserInputPause.Shared.PersonInputToProcessesAgoMs(
                        VisibleControlSurface.ProcessOf(windowRoot), VisibleControlSurface.ShellProcessId) is long nearAgo)
                    writer.WriteNumber("personNearAgoMs", nearAgo);

                // Every look a mission may tie itself to says the other windows of its process, whichever way it
                // reached the window (resolved for it or of its family): a look without them counts as several
                // (review of ventana-misión, finding 6).
                if (missionWindows.Count == 0 && windowRoot != 0)
                {
                    writer.WriteStartArray("others");
                    foreach (nint other in VisibleControlSurface.OtherWindowsOfProcess(windowRoot))
                        writer.WriteNumberValue(other);
                    writer.WriteEndArray();
                }

                if ((WindowsUserInputPause.Shared.PersonInputAgoMs(windowRoot) ?? WindowsUserInputPause.Shared.PersonInputAgoMs(hwnd))
                    is long personAgo)
                    writer.WriteNumber("personInputAgoMs", personAgo);
                // Ronda 20 P2: without Raw Input no window of the person is known, only how long ago the session's last
                // input came (the App weighs it on a look nobody asked for, in front, with no application named).
                else if (WindowsUserInputPause.Shared.UnknownInputAgoMs is long unknownAgo)
                    writer.WriteNumber("personInputUnknownAgoMs", unknownAgo);
                // Contract «Seguridad v2»: a developer's or BAXY's own window (an editor, an IDE, a terminal, a console,
                // BAXY) that the request did not name, told by its process, never by its title. The mission acts on
                // no such window, also when it names no application and works on the window in front.
                if (VisibleControlSurface.ProtectedFrom(processName, application))
                    writer.WriteBoolean("protected", true);
                // v3 point 1: the content of the application's window drawn by a process it started (WebView2, CEF):
                // the application's process first, then the processes it started. The mission's keys and text are
                // bound to this family and to no other process.
                if (VisibleControlSurface.SurfaceFamily(hwnd) is { Length: > 0 } family)
                {
                    writer.WriteStartArray("family");
                    foreach (uint member in family)
                        writer.WriteNumberValue(member);
                    writer.WriteEndArray();
                }

                // Ronda 20 P6: a frame showing only its caption parts says whether its family's content window was read
                // instead, or why not, with that window's extended style and owner (the trace «computer_use.surface»).
                if (surfaceChoice is { } surfaceRead)
                {
                    writer.WriteStartObject("surface");
                    writer.WriteString("reason", surfaceRead.Reason);
                    writer.WriteString("exStyle", surfaceRead.ExStyle.ToString("x8", CultureInfo.InvariantCulture));
                    writer.WriteNumber("owner", surfaceRead.Owner);
                    writer.WriteEndObject();
                }

                if (frontReturned)
                    writer.WriteBoolean("frontReturned", true);
                // Read in front or behind the person's window (v3 point 0): behind, «focused» cannot say where the
                // keyboard will be once the window comes up.
                writer.WriteBoolean("foreground", inFront);
                if (VisibleControlSurface.RunsAboveUs(ownerProcessId))
                {
                    writer.WriteBoolean("elevated", true);
                    // Review of M5: the limit offers to reopen it without administrator rights only when its program
                    // would stay unraised (its manifest, InvokerLaunch.ManifestElevation.ReopensUnraised).
                    if (Applications.InvokerLaunch.WindowReopensUnraised(ownerProcessId))
                        writer.WriteBoolean("reopensUnraised", true);
                }
                WriteRect(writer, "rect", windowRect);
                if (cover != 0)
                {
                    (_, string coverProcess) = VisibleControlSurface.WindowProcess(cover);
                    writer.WriteStartObject("coveredBy");
                    writer.WriteString("title", VisibleControlSurface.WindowTitle(cover));
                    writer.WriteString("process", coverProcess);
                    writer.WriteEndObject();
                }
                if (root.TryGetProperty("focused", out JsonElement focused)
                    && focused.ValueKind == JsonValueKind.Object)
                {
                    writer.WritePropertyName("focused");
                    focused.WriteTo(writer);
                }
                else
                {
                    writer.WriteNull("focused");
                }

                writer.WriteEndObject();
                writer.WriteStartArray("controls");
                foreach (ViewControl control in controls)
                {
                    writer.WriteStartObject();
                    writer.WriteNumber("i", control.Index);
                    writer.WriteString("kind", control.Kind);
                    writer.WriteString("name", control.Name);
                    // Where a name came from when the control had no Name of its own (helpText, labeledBy,
                    // automationId): absent for a control's own Name.
                    if (control.NameSource.Length > 0)
                        writer.WriteString("nameSource", control.NameSource);
                    writer.WriteString("id", control.Id);
                    writer.WriteString("state", control.State);
                    if (control.Value is null)
                        writer.WriteNull("value");
                    else
                        writer.WriteString("value", control.Value);
                    // What a list, grid or tree item is as its application reports it (a folder, a shortcut).
                    if (control.ItemType.Length > 0)
                        writer.WriteString("itemType", control.ItemType);
                    // Goal v3 B3: the key the application declares for the control (AcceleratorKey or AccessKey).
                    if (control.Shortcut.Length > 0)
                        writer.WriteString("shortcut", control.Shortcut);
                    if (control.RectValue is { } rect)
                        WriteRect(writer, "rect", rect);
                    else
                        writer.WriteNull("rect");
                    writer.WriteString("zone", control.Zone);
                    writer.WriteString("color", control.Color);
                    if (control.Repeated > 0)
                        writer.WriteNumber("repeated", control.Repeated);
                    // Ronda 20b, palanca 8 (v3-62): the window's system menu chain under its title bar.
                    if (control.SystemMenu)
                        writer.WriteBoolean("systemMenu", true);
                    // Ronda 21: the window's content surface, listed past the cap.
                    if (control.Body)
                        writer.WriteBoolean("body", true);
                    // Revision 1 of ronda 21: listed past the cut only because it names the goal's words («wanted»).
                    if (control.Reserved)
                        writer.WriteBoolean("reserved", true);
                    writer.WriteEndObject();
                }

                writer.WriteEndArray();
                if (disabled.Count > 0)
                {
                    writer.WriteStartArray("disabled");
                    foreach (ViewControl control in disabled)
                    {
                        writer.WriteStartObject();
                        writer.WriteString("kind", control.Kind);
                        writer.WriteString("name", control.Name);
                        writer.WriteString("state", "disabled");
                        writer.WriteString("zone", control.Zone);
                        writer.WriteEndObject();
                    }

                    writer.WriteEndArray();
                }

                writer.WriteNumber("controlCount", counted);
                // Goal v3, analysis r3a M1: whether the worker read the classic Win32 controls through the client-side
                // providers (a combo box, a tree, a list as themselves) or, without them, as opaque panes.
                if (root.TryGetProperty("clientProviders", out JsonElement providers)
                    && providers.ValueKind is JsonValueKind.True or JsonValueKind.False)
                {
                    writer.WriteBoolean("clientProviders", providers.GetBoolean());
                }

                // Ronda 20b, palanca 8 (v3-51, v3-62): a look that brought only the window's frame was read again,
                // under the same root without the offscreen filter («unfiltered») or under the owner window
                // («owner»); «frameOnly» when neither brought content.
                if (root.TryGetProperty("clientFrom", out JsonElement clientFrom)
                    && clientFrom.ValueKind == JsonValueKind.String && clientFrom.GetString() is { Length: > 0 } from)
                {
                    writer.WriteString("clientFrom", from);
                }

                if (root.TryGetProperty("frameOnly", out JsonElement frameOnly) && frameOnly.ValueKind == JsonValueKind.True)
                {
                    writer.WriteBoolean("frameOnly", true);
                }

                // Review 1 of ronda 21 (finding 3): the worker's walk of what is shown ran out of its own time and the
                // look lists what was read until then; what it does not list may be there (controlCount counts only
                // what was walked).
                if (root.TryGetProperty("partial", out JsonElement partial) && partial.ValueKind == JsonValueKind.True)
                {
                    writer.WriteBoolean("partial", true);
                }

                if (root.TryGetProperty("uiaFailed", out JsonElement walkFailed) && walkFailed.ValueKind == JsonValueKind.String)
                {
                    writer.WriteString("uiaFailed", walkFailed.GetString());
                }

                if (textAuthority is not null)
                {
                    writer.WriteStartObject("text");
                    foreach (string zone in ZoneOrder)
                    {
                        if (!textZones.TryGetValue(zone, out List<string>? bucket) || bucket.Count == 0)
                            continue;
                        writer.WriteStartArray(zone);
                        foreach (string line in bucket)
                            writer.WriteStringValue(line);
                        writer.WriteEndArray();
                    }

                    writer.WriteEndObject();
                    writer.WriteString("textAuthority", textAuthority);
                    if (placedLines is not null && placedIn.Width > 0 && placedIn.Height > 0)
                    {
                        // Encargo IMP4: each line read with its box, in fractions of the window's own drawing, in the
                        // order read (a chat without an accessible tree is read from them: semantic.chat_lines).
                        writer.WriteStartArray("textLines");
                        foreach (WindowsVisibleOcrLocator.LayoutLine line in placedLines)
                        {
                            writer.WriteStartObject();
                            writer.WriteString("text", line.Text);
                            writer.WriteNumber("x", Math.Round(line.X / placedIn.Width, 4));
                            writer.WriteNumber("y", Math.Round(line.Y / placedIn.Height, 4));
                            writer.WriteNumber("w", Math.Round(line.Width / placedIn.Width, 4));
                            writer.WriteNumber("h", Math.Round(line.Height / placedIn.Height, 4));
                            writer.WriteEndObject();
                        }

                        writer.WriteEndArray();
                    }

                    if (textMarks is { Count: > 0 })
                    {
                        writer.WriteStartArray("textMarks");
                        foreach (VisibleTextMarks.Mark mark in textMarks)
                        {
                            writer.WriteStartObject();
                            writer.WriteString("text", mark.Text);
                            writer.WriteString("zone", mark.Zone);
                            WriteRect(writer, "rect", new Rect(mark.X, mark.Y, mark.W, mark.H));
                            writer.WriteString("ink", mark.Ink);
                            writer.WriteNumber("inkV", mark.InkValue);
                            writer.WriteNumber("bgV", mark.BackgroundValue);
                            writer.WriteEndObject();
                        }

                        writer.WriteEndArray();
                    }
                }

                writer.WriteString("surface", captured?.Sha256 ?? string.Empty);
                writer.WriteStartObject("elapsedMs");
                writer.WriteNumber("uia", uiaMs);
                writer.WriteNumber("ocr", ocrMs);
                writer.WriteNumber("color", colorMs);
                writer.WriteNumber("total", stopwatch.ElapsedMilliseconds);
                writer.WriteEndObject();
                writer.WriteString("authority", controls.Count <= 1 && textAuthority == "windows_media_ocr_lines"
                    ? "windows_media_ocr_lines"
                    : "windows_uia_snapshot_ocr_zones");
                writer.WriteEndObject();
            });
            return new ViewResult(ExternalJson.Success(operation, result, false), names);
        }
    }

    private readonly record struct WrittenText(
        IReadOnlyList<WindowsVisibleOcrLocator.LayoutLine>? Lines,
        long Milliseconds);

    private static async Task<VisibleControlSurface.CapturedWindow?> CaptureQuietlyAsync(
        nint hwnd,
        bool covered,
        CancellationToken cancellationToken)
    {
        try
        {
            return await VisibleControlSurface.CaptureAsync(hwnd, cancellationToken, covered).ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is IOException or InvalidOperationException)
        {
            return null;
        }
    }

    private static async Task<WrittenText> ReadTextAsync(
        Task<VisibleControlSurface.CapturedWindow?> captureTask,
        int limit,
        CancellationToken cancellationToken,
        bool placed = false)
    {
        if (await captureTask.ConfigureAwait(false) is not { } capture)
            return default;
        var watch = Stopwatch.StartNew();
        IReadOnlyList<WindowsVisibleOcrLocator.LayoutLine>? lines = await WindowsVisibleOcrLocator.ReadLayoutAsync(
            capture.Bmp, Math.Max(limit, 40), cancellationToken, placed).ConfigureAwait(false);
        return new WrittenText(lines, watch.ElapsedMilliseconds);
    }

    /// <summary>
    /// Ronda 20 P6: the kind and rectangle (left, top, right, bottom) of every control a view of a window listed,
    /// actionable or disabled, as <see cref="VisibleControlSurface.ShowsOnlyCaption"/> reads them.
    /// </summary>
    private static List<(string Kind, (int Left, int Top, int Right, int Bottom)? Box)> CaptionReading(JsonElement root) =>
        ParseControls(root).Concat(ParseControls(root, "disabled"))
            .Select(control => (control.Kind, control.RectValue is { } rect
                ? ((int, int, int, int)?)(rect.X, rect.Y, rect.X + rect.W, rect.Y + rect.H)
                : null))
            .ToList();

    // A look read again on another window leaves the first one's capture and text: their faults are observed, never
    // thrown where nothing waits for them.
    private static void Discard(Task first, Task? second)
    {
        _ = first.ContinueWith(static task => _ = task.Exception, CancellationToken.None,
            TaskContinuationOptions.OnlyOnFaulted, TaskScheduler.Default);
        _ = second?.ContinueWith(static task => _ = task.Exception, CancellationToken.None,
            TaskContinuationOptions.OnlyOnFaulted, TaskScheduler.Default);
    }

    internal static List<ViewControl> ParseControls(JsonElement root, string property = "controls")
    {
        var controls = new List<ViewControl>();
        if (!root.TryGetProperty(property, out JsonElement listed)
            || listed.ValueKind != JsonValueKind.Array)
        {
            return controls;
        }

        foreach (JsonElement item in listed.EnumerateArray())
        {
            if (item.ValueKind != JsonValueKind.Object)
                continue;
            string name = ReadString(item, "name");
            if (name.Length == 0)
                continue;
            Rect? rect = null;
            if (item.TryGetProperty("rect", out JsonElement box) && box.ValueKind == JsonValueKind.Object)
            {
                rect = new Rect(ReadInt(box, "x"), ReadInt(box, "y"), ReadInt(box, "w"), ReadInt(box, "h"));
            }

            controls.Add(new ViewControl
            {
                Index = controls.Count,
                Kind = ReadString(item, "kind"),
                Name = name,
                NameSource = ReadString(item, "nameSource"),
                Id = ReadString(item, "id"),
                State = ReadString(item, "state"),
                Value = item.TryGetProperty("value", out JsonElement value)
                    && value.ValueKind == JsonValueKind.String
                        ? value.GetString()
                        : null,
                ItemType = ReadString(item, "itemType"),
                Shortcut = ReadString(item, "shortcut"),
                RectValue = rect,
                Repeated = ReadInt(item, "repeated"),
                SystemMenu = item.TryGetProperty("systemMenu", out JsonElement systemMenu)
                    && systemMenu.ValueKind == JsonValueKind.True,
                Body = item.TryGetProperty("body", out JsonElement body) && body.ValueKind == JsonValueKind.True,
                Reserved = item.TryGetProperty("reserved", out JsonElement reserved) && reserved.ValueKind == JsonValueKind.True,
                Content = item.TryGetProperty("content", out JsonElement content) && content.ValueKind == JsonValueKind.True,
            });
        }

        return controls;
    }

    private static string ReadString(JsonElement item, string name) =>
        item.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.String
            ? value.GetString() ?? string.Empty
            : string.Empty;

    private static int ReadInt(JsonElement item, string name) =>
        item.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.Number
            && value.TryGetInt32(out int number)
            ? number
            : 0;

    private static void WriteRect(Utf8JsonWriter writer, string name, Rect rect)
    {
        writer.WriteStartObject(name);
        writer.WriteNumber("x", rect.X);
        writer.WriteNumber("y", rect.Y);
        writer.WriteNumber("w", rect.W);
        writer.WriteNumber("h", rect.H);
        writer.WriteEndObject();
    }

    private static readonly string[] ZoneOrder = ["TL", "T", "TR", "L", "C", "R", "BL", "B", "BR"];

    // Rejilla 3×3 sobre la ventana (contrato §1.4): la zona del centro.
    internal static string Zone(double centerX, double centerY, Rect window)
    {
        if (window.W <= 0 || window.H <= 0)
            return string.Empty;
        double fx = (centerX - window.X) / window.W;
        double fy = (centerY - window.Y) / window.H;
        string row = fy < 1.0 / 3 ? "T" : fy < 2.0 / 3 ? string.Empty : "B";
        string column = fx < 1.0 / 3 ? "L" : fx < 2.0 / 3 ? string.Empty : "R";
        string zone = row + column;
        return zone.Length == 0 ? "C" : zone;
    }

    // ---------------------------------------------------------------- click

    private async ValueTask<ExternalCapabilityReceipt> InvokeUiaAsync(
        string operation,
        string label,
        string? controlId,
        nint window,
        CancellationToken cancellationToken,
        string? manner = null)
    {
        var effectBoundary = new ExternalEffectBoundary();
        nint hwnd = 0;
        try
        {
            // A click by the identity of the last view lands on that view's
            // window while it still exists, whatever holds the foreground now,
            // and without bringing it to the front: the patterns reach a
            // window that is behind (only the pointer, last, needs the front).
            LastView? recent;
            lock (_viewLock)
            {
                recent = _lastView;
            }

            // M132: a click bound to the application just opened acts on that
            // window, never on whatever happens to be in front.
            if (window != 0)
            {
                hwnd = window;
            }
            else if (controlId is not null && recent is not null && VisibleControlSurface.IsAlive(recent.Hwnd))
            {
                hwnd = recent.Hwnd;
            }

            // Without a window named (a direct order outside a mission), the window in front, as the descriptor says.
            if (hwnd == 0)
            {
                // Read where it is: the worker no longer presses by coordinates (fable/cu-v3-clic), and the pointer
                // takes the front itself inside a burst of the foreground lease (fable/cu-v3-pausa).
                hwnd = await VisibleControlSurface.ResolveForegroundAsync(cancellationToken).ConfigureAwait(false);
            }
        }
        catch (Exception exception) when (exception is IOException or InvalidOperationException)
        {
            hwnd = 0;
        }

        if (hwnd == 0)
            return ExternalJson.FailureBeforeEffect(operation, "active_window_not_found");
        // v3 limits (M3): a window of a process that runs as administrator (Task Manager) refuses UI Automation and
        // input from BAXY. Every click route says so before acting, never «nothing on the screen is called that»
        // (live v3-21: «add the command line column» answered as a missing label). Only the view marked it before.
        if (_elevated(hwnd))
            return ExternalJson.FailureBeforeEffect(operation, WindowElevated);
        _lookedWindow = hwnd;

        return await PressUiaAsync(operation, label, controlId, hwnd, effectBoundary, cancellationToken, manner)
            .ConfigureAwait(false);
    }

    /// <summary>
    /// A click that names a search (<c>search</c>, goal v3 point 0, fix 3): the opener of the mission's window, by its
    /// identity in the last view, then the text and the result inside one burst of the lease (<see cref="SearchBurst"/>).
    /// Only inside a mission (its window named) and on a control the view identified; nothing is pressed otherwise.
    /// </summary>
    private async ValueTask<ExternalCapabilityReceipt> SearchInBurstAsync(
        string operation,
        string label,
        string? controlId,
        nint window,
        string search,
        string? choose,
        CancellationToken cancellationToken)
    {
        if (window == 0 || !VisibleControlSurface.IsAlive(window))
            return ExternalJson.FailureBeforeEffect(operation, "visible_click_argument_invalid");
        if (controlId is null)
            return ExternalJson.FailureBeforeEffect(operation, "visible_control_identity_stale");
        if (BurstLease is not { } lease || TypeInWindow is null)
            return ExternalJson.FailureBeforeEffect(operation, "visible_search_unavailable");
        if (_elevated(window))
            return ExternalJson.FailureBeforeEffect(operation, WindowElevated);
        IReadOnlyList<ViewControl> before;
        lock (_viewLock)
        {
            before = _lastView is { } view && view.Hwnd == window ? view.Controls : [];
        }

        _lookedWindow = window;
        return await new SearchBurst(lease, SearchClock, this)
            .RunAsync(operation, window, label, controlId, before, search, choose, cancellationToken)
            .ConfigureAwait(false);
    }

    // The burst holds the window's front: each press says so again to the worker's net (its mark lasts two seconds), so
    // the net never hands that front back in the middle of the burst.
    ValueTask<ExternalCapabilityReceipt> ISearchBurstActs.OpenAsync(
        nint window, string label, string controlId, CancellationToken cancellationToken)
    {
        LeaseFrontSignal.Mark(window);
        return PressUiaAsync("input.visible.click", label, controlId, window, new ExternalEffectBoundary(), cancellationToken);
    }

    ValueTask<ExternalCapabilityReceipt> ISearchBurstActs.ChooseAsync(
        nint window, string label, string controlId, CancellationToken cancellationToken)
    {
        LeaseFrontSignal.Mark(window);
        return PressUiaAsync("input.visible.click", label, controlId, window, new ExternalEffectBoundary(), cancellationToken);
    }

    ValueTask<ExternalCapabilityReceipt> ISearchBurstActs.PressInMannerAsync(
        nint window, string label, string controlId, string manner, CancellationToken cancellationToken)
    {
        LeaseFrontSignal.Mark(window);
        return PressUiaAsync("input.visible.click", label, controlId, window, new ExternalEffectBoundary(), cancellationToken, manner);
    }

    IReadOnlyList<nint> ISearchBurstActs.PopupsOfWindow(nint window) => PopupsOf(window);

    ValueTask<ExternalCapabilityReceipt> ISearchBurstActs.TypeAsync(nint window, string text, CancellationToken cancellationToken) =>
        TypeInWindow!(window, text, cancellationToken);

    // The controls only (no capture, no text): what the burst needs to find the focus and the result, read quickly.
    async ValueTask<IReadOnlyList<ViewControl>?> ISearchBurstActs.LookAsync(nint window, CancellationToken cancellationToken)
    {
        // Without the disabled ones (review of the branch, finding 6): the burst looks for controls to press, on the
        // lease's time.
        string command = new JsonObject { ["cmd"] = "view", ["hwnd"] = window, ["limit"] = 60, ["disabled"] = false }.ToJsonString();
        using JsonDocument? answer = await _worker.SendAsync(command, WorkerViewBudget, cancellationToken).ConfigureAwait(false);
        if (answer is null || !answer.RootElement.TryGetProperty("ok", out JsonElement ok) || ok.ValueKind != JsonValueKind.True)
            return null;
        return ParseControls(answer.RootElement);
    }

    private static string? OptionalText(JsonElement arguments, string name)
    {
        if (!arguments.TryGetProperty(name, out JsonElement value) || value.ValueKind == JsonValueKind.Null)
            return null;
        if (value.ValueKind != JsonValueKind.String)
            throw new InvalidDataException(name);
        string text = value.GetString()!.Trim();
        return text.Length == 0 ? null : text;
    }

    /// <summary>
    /// Whether a control opens something that lives only while its window is active: a combo box (its list), a control
    /// that says it is collapsed (a drop-down, a menu with a submenu, a split button), by the structure a view read,
    /// never by a name.
    /// </summary>
    internal static bool OpensWhileActive(string kind, string state) =>
        kind == "ComboBox"
        || state.Split(' ', StringSplitOptions.RemoveEmptyEntries).Contains("collapsed", StringComparer.Ordinal);

    /// <summary>
    /// Pasada r15b (v3-09): what the last click showed (a collapsed ribbon's gallery) closed before its item was pressed,
    /// the window having lost the activation to the person's. Its opener and the item go in one burst of the lease, inside
    /// their pause (SearchBurst.ReopenAsync), never by a cascade on a closed menu. Menus-efímeros (t-form-2, t-file-4):
    /// also when the item lived in the opener's own popup (a menu bar's popup host), which died with the activation; the
    /// burst reopens it on the opener's window. Ronda 20 (P7): the opener is pressed again in the manner it was pressed
    /// (its arrow), and the item in the manner the act asked for. Null when nothing is reopened (ReopensShownItem).
    /// </summary>
    private async ValueTask<ExternalCapabilityReceipt?> ReopenShownAsync(
        string operation,
        (nint Window, string Id, string Label, HashSet<string> NamesBefore, string? Manner)? opener,
        ExternalCapabilityReceipt pressed,
        string label,
        string controlId,
        nint missionWindow,
        string? manner,
        CancellationToken cancellationToken)
    {
        if (missionWindow == 0 || opener is not { } shownBy || BurstLease is not { } reopenLease
            || !VisibleControlSurface.IsAlive(shownBy.Window) || _elevated(shownBy.Window)
            || !ReopensShownItem(pressed.ErrorCode, label, controlId, missionWindow,
                shownBy.Window, shownBy.Id, shownBy.NamesBefore, VisibleControlSurface.IsAlive(missionWindow),
                missionWindow == shownBy.Window ? [] : PopupsOf(shownBy.Window), (shownBy.NamesBefore as OpenerNames)?.Described))
            return null;
        _lookedWindow = shownBy.Window;
        return await new SearchBurst(reopenLease, SearchClock, this)
            .ReopenAsync(operation, shownBy.Window, shownBy.Label, shownBy.Id, label, cancellationToken,
                shownIn: missionWindow == shownBy.Window ? 0 : missionWindow, openerManner: shownBy.Manner, itemManner: manner)
            .ConfigureAwait(false);
    }

    /// <summary>
    /// The one control of the mission's last view a label names, by its identity: the only control of exactly that name
    /// (<see cref="SameLabel"/>). Null when the last view is of another window, the label names none or several, or the
    /// control has no identity: the label is then left to its cascade, which presses nothing it does not name exactly.
    /// Auditoría P3: a control whose name only holds the label is never chosen for it.
    /// </summary>
    private string? NamedInView(nint window, string label)
    {
        lock (_viewLock)
        {
            if (window == 0 || _lastView is not { } view || view.Hwnd != window)
                return null;
            ViewControl[] exact = [.. view.Controls.Where(control => SameLabel(label, control.Name))];
            return exact.Length == 1 && exact[0].Id.Length > 0 ? exact[0].Id : null;
        }
    }

    // The kinds that describe rather than act: a name only they show is no name of an acting control (OpenerNames).
    private static readonly HashSet<string> NamedDescriptiveKinds = new(StringComparer.Ordinal)
    {
        "Text", "Group", "Pane", "Custom", "Document",
    };

    // The last control of a mission's window pressed by its identity, with the names its view showed before the press:
    // a control of the next view that is none of those appeared with that press (v3-09: the gallery of a ribbon tab).
    // Review of the branch (finding 3): only a control that opens something by its structure (a tab, a combo box, one
    // that says it is collapsed: OpensAgain) is noted, and it holds for the very next view and click only (Views: the
    // count of views read when it was pressed), so a press that creates or deletes («Nuevo», «Eliminar») is never pressed
    // again, and neither is any opener after a text, a key, another click or another mission's look.
    // Ronda 20 (P7): with the manner it was pressed in (an arrow, a context menu), so it is reopened the same way.
    private (nint Window, string Id, string Label, HashSet<string> NamesBefore, long Views, string? Manner)? _opener;

    // How many views this adapter has read (the mission reads one after every act).
    private long _viewsRead;

    private void NoteOpener(nint window, string controlId, string label, HashSet<string>? namesBefore, bool opens) =>
        NoteOpenerIn(window, controlId, label, namesBefore, opens, null);

    private void NoteOpenerIn(nint window, string controlId, string label, HashSet<string>? namesBefore, bool opens, string? manner)
    {
        lock (_viewLock)
        {
            _opener = namesBefore is not null && opens ? (window, controlId, label, namesBefore, _viewsRead, manner) : null;
        }
    }

    // The names the last view of this window showed; null when the last view is of another window (or none).
    private HashSet<string>? ViewNames(nint window)
    {
        lock (_viewLock)
        {
            return window != 0 && _lastView is { } view && view.Hwnd == window ? OpenerNames.Of(view.Controls) : null;
        }
    }

    /// <summary>
    /// Ronda 24 (t-menu-3): the names a window showed before its opener was pressed, split by what showed them. The set
    /// itself holds the names of the controls that act (a button, a menu entry): never an item an opening showed,
    /// wherever the item lives. A name held only by a control that describes (<see cref="Described"/>: a status bar's
    /// text «Zoom») says so only of an item of that same window: the entry «Zoom» of the popup the menu «Ver» opened is
    /// no text of the window under it. By the kinds the view read, never by a name.
    /// </summary>
    internal sealed class OpenerNames : HashSet<string>
    {
        internal OpenerNames(IEnumerable<string> acting, IEnumerable<string> described)
            : base(acting, StringComparer.Ordinal)
        {
            Described = new HashSet<string>(described, StringComparer.Ordinal);
            Described.ExceptWith(this);
        }

        /// <summary>The names only a control that describes showed.</summary>
        internal HashSet<string> Described { get; }

        internal static OpenerNames Of(IEnumerable<ViewControl> controls)
        {
            ViewControl[] all = [.. controls];
            return new OpenerNames(
                all.Where(control => !NamedDescriptiveKinds.Contains(control.Kind)).Select(control => control.Name),
                all.Where(control => NamedDescriptiveKinds.Contains(control.Kind)).Select(control => control.Name));
        }
    }

    /// <summary>
    /// Ronda 24 (v3-11 t3, t-menu-3): the names before a press of an opener. A press of the very opener the previous click
    /// noted (same window, same identity) keeps the names of the chain's first press: the view it was decided on already
    /// showed what that first press opened, and those items are no names the window showed before. Any other press (another
    /// control in between, another window) takes the names of its own last view.
    /// </summary>
    internal static HashSet<string>? ChainedNames(
        (nint Window, string Id, string Label, HashSet<string> NamesBefore, string? Manner)? opener,
        nint window,
        string controlId,
        HashSet<string>? viewNames) =>
        opener is { } noted && noted.Window == window && noted.Window != 0 && noted.Id == controlId ? noted.NamesBefore : viewNames;

    // Whether the control of the last view of this window opens something a second press shows again unchanged: a tab
    // (selected again, not toggled), a combo box or a control that says it is collapsed (OpensWhileActive). By the
    // structure the view read, never by a name; a button that acts («Nuevo», «Eliminar») is none of them.
    private bool OpensAgain(nint window, string controlId)
    {
        lock (_viewLock)
        {
            ViewControl? seen = window != 0 && _lastView is { } view && view.Hwnd == window
                ? view.Controls.FirstOrDefault(control => control.Id == controlId)
                : null;
            return seen is not null && OpensAgain(seen.Kind, seen.State);
        }
    }

    /// <summary>The structural rule of <see cref="OpensAgain(nint, string)"/> on a control's kind and state.</summary>
    internal static bool OpensAgain(string kind, string state) => kind == "TabItem" || OpensWhileActive(kind, state);

    /// <summary>
    /// Whether an item the click right after its opener could not press (gone stale, or not found) is the opener's
    /// opening that closed (menus-efímeros, t-form-2, t-file-4, t-form-3): the item is no name the window showed before
    /// the opener's press, it is not the opener itself, and it was shown in the opener's window, or in a window of its
    /// own born of that press: one of the opener window's popups now (<paramref name="openerPopups"/>), or one that no
    /// longer lives (a menu's popup host dies with the activation). Any other window is never reopened into.
    /// </summary>
    internal static bool ReopensShownItem(
        string? errorCode,
        string label,
        string controlId,
        nint itemWindow,
        nint openerWindow,
        string openerId,
        IReadOnlySet<string> namesBefore,
        bool itemWindowAlive,
        IReadOnlyList<nint> openerPopups,
        IReadOnlySet<string>? describedBefore = null) =>
        errorCode is "visible_control_identity_stale" or "visible_button_not_found"
        && itemWindow != 0 && openerWindow != 0
        && openerId != controlId && !namesBefore.Contains(label)
        && (itemWindow != openerWindow || describedBefore is null || !describedBefore.Contains(label))
        && (itemWindow == openerWindow || !itemWindowAlive || openerPopups.Contains(itemWindow));

    // The opener noted by the previous click, once and only right after it: the press, then exactly one view, then this
    // click. Any later click takes it away.
    private (nint Window, string Id, string Label, HashSet<string> NamesBefore, string? Manner)? TakeOpener()
    {
        lock (_viewLock)
        {
            var opener = _opener;
            _opener = null;
            return opener is { } noted && _viewsRead == noted.Views + 1
                ? (noted.Window, noted.Id, noted.Label, noted.NamesBefore, noted.Manner)
                : null;
        }
    }

    private async ValueTask<ExternalCapabilityReceipt> PressUiaAsync(
        string operation,
        string label,
        string? controlId,
        nint hwnd,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken,
        string? manner = null)
    {
        // The descriptor admits «surface changed» as post-read. A Calculator
        // digit stays enabled and unselected after Invoke, so the surface is
        // the only evidence (UI1273); it is compared before/after the click.
        VisibleControlSurface.CapturedWindow? before = null;
        try
        {
            before = await _capture(hwnd, null, cancellationToken).ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is IOException or InvalidOperationException)
        {
            before = null;
        }

        // Pasada r15b B2 (v3-17): the window's own popups before the click; one born of it is its effect.
        IReadOnlyList<nint> popupsBefore = PopupsOf(hwnd);
        // Ronda 20b, palanca 8, objetivo 3 (v3-44): the desktop's root windows before the click.
        HandoffWatch? roots = RootsBefore(hwnd);
        var clickRequest = new JsonObject
        {
            ["cmd"] = "click",
            ["hwnd"] = hwnd,
            // Auditoría P3: the label as the model wrote it, never a translation of it.
            ["aliases"] = new JsonArray(label),
            ["controlId"] = controlId ?? string.Empty,
            ["asks"] = AsksRequest(),
        };
        if (manner is not null)
            clickRequest["manner"] = manner;
        AddRenderHosts(clickRequest, hwnd);
        string command = clickRequest.ToJsonString();
        try
        {
            effectBoundary.Cross(cancellationToken);
            JsonDocument? answer = await _worker.SendAsync(command, WorkerClickBudget, cancellationToken)
                .ConfigureAwait(false);
            if (answer is null)
                return effectBoundary.Failure(operation, "visible_click_no_receipt");
            using (answer)
            {
                if (answer.RootElement.TryGetProperty("pending", out JsonElement pending)
                    && pending.ValueKind == JsonValueKind.True)
                {
                    return await PostreadAsync(
                            operation, answer.RootElement, before, effectBoundary, (hwnd, popupsBefore), cancellationToken,
                            roots)
                        .ConfigureAwait(false);
                }

                if (answer.RootElement.TryGetProperty("needsPointer", out JsonElement needsPointer)
                    && needsPointer.ValueKind == JsonValueKind.True)
                {
                    return await PointerAsync(operation, answer.RootElement, hwnd, effectBoundary, cancellationToken)
                        .ConfigureAwait(false);
                }

                _lookedTreeSize = answer.RootElement.TryGetProperty("treeSize", out JsonElement size)
                    && size.ValueKind == JsonValueKind.Number && size.TryGetInt32(out int elements)
                        ? elements
                        : -1;
                return ReceiptFromWorker(operation, answer.RootElement, effectBoundary);
            }
        }
        catch (OperationCanceledException) when (
            cancellationToken.IsCancellationRequested && effectBoundary.WasCrossed)
        {
            return effectBoundary.Failure(operation, "visible_click_receipt_invalid");
        }
        catch (Exception exception) when (exception is IOException or JsonException or TimeoutException)
        {
            return effectBoundary.Failure(operation, "visible_click_receipt_invalid");
        }
    }

    /// <summary>
    /// The control has no way to be pressed but the cursor (no pattern, no default action, not a classic window): the
    /// worker pressed nothing and handed its point. The pointer presses it only while the window may take it, and the
    /// surface is captured again right before, since bringing a window forward changes what the screen shows.
    /// </summary>
    private async ValueTask<ExternalCapabilityReceipt> PointerAsync(
        string operation,
        JsonElement answer,
        nint hwnd,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        if (!answer.TryGetProperty("point", out JsonElement point)
            || point.ValueKind != JsonValueKind.Object
            || !point.TryGetProperty("x", out JsonElement xValue) || !xValue.TryGetInt32(out int x)
            || !point.TryGetProperty("y", out JsonElement yValue) || !yValue.TryGetInt32(out int y))
        {
            return ExternalJson.FailureBeforeEffect(operation, "visible_button_not_invokable");
        }

        HandoffWatch? roots = RootsBefore(hwnd);
        PointerPressed pointed = await LocatedPointPress.PointerAsync(
            _pointer, hwnd, x, y, null, null, cancellationToken, PopupsOf).ConfigureAwait(false);
        if (!pointed.Pressed)
            return ExternalJson.FailureBeforeEffect(operation, pointed.Refusal ?? "input_window_not_in_front");

        VisibleControlSurface.CapturedWindow? before = pointed.Before;
        JsonObject node = JsonNode.Parse(answer.GetRawText())!.AsObject();
        node.Remove("needsPointer");
        node["pending"] = true;
        node["effectObserved"] = true;
        node["error"] = "visible_button_postread_pending";
        node["method"] = "pointer";
        node["waitedMs"] = pointed.WaitedMs;
        using JsonDocument clicked = JsonDocument.Parse(node.ToJsonString());
        // r4a M3: the burst was given back right after the press; the post-read reads the window behind the person's,
        // its surface taken the way the baseline was (the window's own drawing). The restore below only confirms it.
        try
        {
            return await PostreadAsync(
                    operation, clicked.RootElement.Clone(), before, effectBoundary,
                    pointed.Popups is { } popupsBefore ? (hwnd, popupsBefore) : null, cancellationToken, roots)
                .ConfigureAwait(false);
        }
        finally
        {
            _ = pointed.Burst?.Restore();
        }
    }

    /// <summary>
    /// A point a locator read on a window, pressed by the worker through the accessible control there that the label
    /// names. Only the worker's explicit «nothing there has a way» leaves the point to the pointer; a silence, a
    /// timeout or an error may come after the press began, and is never followed by another press.
    /// </summary>
    public ValueTask<PointPressed> PressAtAsync(
        nint window,
        int screenX,
        int screenY,
        string label,
        CancellationToken cancellationToken) => PressAtAsync(window, screenX, screenY, label, null, cancellationToken);

    /// <inheritdoc />
    public ValueTask<PointPressed> PressControlAtAsync(
        nint window,
        int screenX,
        int screenY,
        string label,
        string controlId,
        CancellationToken cancellationToken) => PressAtAsync(window, screenX, screenY, label, controlId, cancellationToken);

    /// <inheritdoc />
    public ValueTask<PointPressed> PressRememberedAtAsync(
        nint window,
        int screenX,
        int screenY,
        int width,
        int height,
        string label,
        CancellationToken cancellationToken) =>
        PressAtAsync(window, screenX, screenY, label, null, cancellationToken, (width, height));

    private async ValueTask<PointPressed> PressAtAsync(
        nint window,
        int screenX,
        int screenY,
        string label,
        string? controlId,
        CancellationToken cancellationToken,
        (int W, int H)? remembered = null)
    {
        if (window == 0)
            return PointPressed.NothingThere;
        var request = new JsonObject
        {
            ["cmd"] = "at",
            ["hwnd"] = window,
            ["x"] = screenX,
            ["y"] = screenY,
            ["aliases"] = new JsonArray(label),
            ["asks"] = AsksRequest(),
        };
        if (!string.IsNullOrEmpty(controlId))
            request["controlId"] = controlId;
        if (_pressedUnchanged is { Length: > 0 } pressedBefore)
            request["pressed"] = pressedBefore;
        if (remembered is { } size)
        {
            request["remembered"] = true;
            request["w"] = size.W;
            request["h"] = size.H;
        }
        AddRenderHosts(request, window);
        string command = request.ToJsonString();
        try
        {
            using JsonDocument? answer = await _worker.SendAsync(command, WorkerClickBudget, cancellationToken)
                .ConfigureAwait(false);
            return answer is null ? PointPressed.Unconfirmed : PointPressFrom(answer.RootElement);
        }
        catch (Exception exception) when (exception is IOException or JsonException or TimeoutException)
        {
            return PointPressed.Unconfirmed;
        }
    }

    /// <summary>
    /// fable/cu-v3-clic-chromium: the content windows of the window's process family
    /// (<see cref="VisibleControlSurface.FamilyContentWindows"/>), handed to the worker as «hosts»: a press it posts to
    /// a Chromium render surface may reach the content a frame lies over (measured: the activated frame of a WebView2
    /// client above its content in the Z order). Said only when there is one, so every other request stays as it was.
    /// </summary>
    private void AddRenderHosts(JsonObject request, nint window)
    {
        IReadOnlyList<nint> hosts;
        long now = Environment.TickCount64;
        // Review of fable/cu-v3-clic-chromium (finding 8): the family's windows are enumerated once per window every
        // RenderHostsKeptMs, not on every click and look of a cascade (the worker checks each handle is still a window).
        if (_renderHostsSeen is { } seen && seen.Window == window && now - seen.At < RenderHostsKeptMs)
        {
            hosts = seen.Hosts;
        }
        else
        {
            try
            {
                hosts = _renderHosts(window);
            }
            catch (Exception exception) when (exception is InvalidOperationException or System.ComponentModel.Win32Exception)
            {
                return;
            }

            _renderHostsSeen = new RenderHostsSeen(window, now, hosts);
        }

        if (hosts.Count == 0)
            return;
        var list = new JsonArray();
        foreach (nint host in hosts)
            list.Add((JsonNode?)JsonValue.Create((long)host));
        request["hosts"] = list;
    }

    /// <inheritdoc />
    public ValueTask<PointerPressed> PointerAtAsync(
        nint window,
        int screenX,
        int screenY,
        VisibleControlSurface.CapturedWindow? located,
        PointRelocator? relocate,
        CancellationToken cancellationToken) =>
        LocatedPointPress.PointerAsync(_pointer, window, screenX, screenY, located, relocate, cancellationToken);

    internal static PointPressed PointPressFrom(JsonElement root)
    {
        string? method = root.TryGetProperty("method", out JsonElement methodValue)
            && methodValue.ValueKind == JsonValueKind.String
                ? methodValue.GetString()
                : null;
        string? error = root.TryGetProperty("error", out JsonElement errorValue)
            && errorValue.ValueKind == JsonValueKind.String
                ? errorValue.GetString()
                : null;
        bool effect = root.TryGetProperty("effectObserved", out JsonElement effectValue)
            && effectValue.ValueKind == JsonValueKind.True;
        bool pressed = (root.TryGetProperty("pending", out JsonElement pending) && pending.ValueKind == JsonValueKind.True)
            || (root.TryGetProperty("ok", out JsonElement ok) && ok.ValueKind == JsonValueKind.True);
        if (!pressed)
        {
            if (!effect && error is "visible_point_named_other" or NeedsConfirmation)
                return PointPressed.Refused;
            if (!effect && error == PointAlreadyPressed)
                return PointPressed.AlreadyPressed;
            return !effect && error is "visible_point_no_pattern" or "visible_click_needs_pointer"
                ? PointPressed.NothingThere
                : PointPressed.Unconfirmed;
        }

        string name = root.TryGetProperty("name", out JsonElement nameValue) && nameValue.ValueKind == JsonValueKind.String
            ? nameValue.GetString() ?? string.Empty
            : string.Empty;
        string kind = root.TryGetProperty("kind", out JsonElement kindValue) && kindValue.ValueKind == JsonValueKind.String
            ? kindValue.GetString() ?? string.Empty
            : string.Empty;
        bool focused = root.TryGetProperty("focused", out JsonElement focusedValue)
            && focusedValue.ValueKind == JsonValueKind.True;
        // «render»: a press posted to a Chromium render surface at the point (fable/cu-v3-clic-chromium); its proof is the
        // surface that changes, as for any press at a point.
        if (method is "invoke" or "select" or "toggle" or "expand" or "render")
            return new PointPressed(PointPressOutcome.Pressed, method, name, kind);
        // A field is the text's destination only with the keyboard's focus; any other answer is not known to be safe.
        return method == "target" && focused
            ? new PointPressed(PointPressOutcome.Pressed, method, name, kind, Focused: true)
            : PointPressed.Unconfirmed;
    }

    /// <summary>
    /// The post-read of a click the worker has just invoked. The control's own state is asked every 50 ms for up to
    /// half a second; meanwhile the window is captured from about 150 ms on, and the first capture that differs from
    /// the one before the click settles it at once (a Calculator digit stays enabled and unselected after Invoke, so
    /// the surface is its only evidence, UI1273). Only a window that never differs is watched up to the surface
    /// budget, and leaves the click unconfirmed.
    /// </summary>
    private async ValueTask<ExternalCapabilityReceipt> PostreadAsync(
        string operation,
        JsonElement clicked,
        VisibleControlSurface.CapturedWindow? before,
        ExternalEffectBoundary effectBoundary,
        (nint Window, IReadOnlyList<nint> Before)? popups,
        CancellationToken cancellationToken,
        HandoffWatch? roots = null)
    {
        var watch = Stopwatch.StartNew();
        bool askControl = true;
        // The front net's report: the click's own answer, then each post-read (they also see the tail after it).
        UiaFrontReport? front = UiaFrontReport.Read(clicked);
        TimeSpan budget = before is null ? _timing.ControlPostread : _timing.SurfacePostread;
        while (true)
        {
            if (askControl && watch.Elapsed < _timing.ControlPostread)
            {
                using JsonDocument? read = await _worker.SendAsync(
                        "{\"cmd\":\"postread\"}", WorkerClickBudget, cancellationToken)
                    .ConfigureAwait(false);
                // The control was invoked already: a silence here is not a «not found» to look for again.
                if (read is null)
                    return effectBoundary.Failure(operation, "visible_click_postread_no_receipt");
                JsonElement root = read.RootElement;
                front = UiaFrontReport.Latest(front, UiaFrontReport.Read(root));
                if (root.TryGetProperty("ok", out JsonElement ok) && ok.ValueKind == JsonValueKind.True)
                    return NotedPress(ReceiptFromWorker(operation, root, effectBoundary), clicked);
                // Ronda 20b, palanca 7 (v3-53): a toggle the control took without its sibling's mark appearing is no
                // receipt, and the box's own redraw must not become one through the surface: the effect is uncertain.
                // Review of ronda 20b (finding 3): so is a choice whose Select marked the row without moving the place
                // (v3-52): the row's redrawn mark is no surface change of the posted press.
                if (root.TryGetProperty("error", out JsonElement doubt) && doubt.ValueKind == JsonValueKind.String
                    && doubt.GetString() is ToggleUncorroborated or ChoiceUncorroborated)
                    return NotedPress(ReceiptFromWorker(operation, root, effectBoundary), clicked);
                // Anything but «not yet» ends the questions to the control; the surface may still answer.
                askControl = root.TryGetProperty("error", out JsonElement error)
                    && error.ValueKind == JsonValueKind.String
                    && error.GetString() == "visible_button_postread_unchanged";
            }

            if (before is { } captured && watch.Elapsed >= _timing.SurfaceFirstSample)
            {
                string? surface = await SurfaceAsync(captured.Hwnd, captured.SelfDrawn, cancellationToken)
                    .ConfigureAwait(false);
                // lat-apertura-clic (r13a, 33 right clicks at 1.5–2.6 s, 94 s): the first image that differs from the
                // one before the click answers «changed». The verdict was already that (an image that differed once
                // ended as changed at the budget); waiting for two equal images only paid the whole budget on a window
                // that animates (a caret, a spinner). Only «unchanged» needs the whole budget watched.
                if (surface is not null && !string.Equals(surface, captured.Sha256, StringComparison.Ordinal))
                {
                    // Review of the branch (finding 7): the control is asked once more first, so a selection or a
                    // toggle it now reports is the receipt's, not the state the click's own answer had before it.
                    (ExternalCapabilityReceipt? held, front) = await LastAnswerAsync(
                        operation, askControl && watch.Elapsed < _timing.ControlPostread, front, effectBoundary,
                        cancellationToken).ConfigureAwait(false);
                    return held is { } answered ? NotedPress(answered, clicked) : SurfaceChanged(operation, clicked, front);
                }
            }

            // Pasada r15b B2 (v3-17): a popup of the window's own born after the click (a menu's popup host, a dialog)
            // is the click's effect, while the window's own image may stay the same: the post-read looks at it too.
            // Review of fable/cu-v3-carga-preguntas (finding 2): not while the person's pointer rests on the window (a
            // hover shows a tooltip or a link's status bubble by itself, in a popup of the same kind as a menu's), and
            // the control is asked once more first, as for an image that changed.
            if (popups is { } watched && watch.Elapsed >= _timing.SurfaceFirstSample
                && PopupBorn(watched.Before, PopupsOf(watched.Window)) && !PointerRestsOn(watched.Window))
            {
                (ExternalCapabilityReceipt? held, front) = await LastAnswerAsync(
                    operation, askControl && watch.Elapsed < _timing.ControlPostread, front, effectBoundary,
                    cancellationToken).ConfigureAwait(false);
                return held is { } answered ? NotedPress(answered, clicked) : SurfaceChanged(operation, clicked, front, popupBorn: true);
            }

            // Ronda 20b, palanca 8, objetivo 3 (v3-44): a window of another process born or brought to the front within
            // the click's post-read is where the click handed its effect, while the clicked window may stay the same.
            // r27: looked for up to the post-read's own budget and no longer (the fixed 1.2 s tail after it was paid whole
            // by the 20 unchanged clicks of 3 runs of the bank and found no window in any).
            if (watch.Elapsed >= _timing.SurfaceFirstSample && Handed(roots) is { } handedNow)
                return HandedOff(operation, clicked, front, handedNow);

            if (watch.Elapsed >= budget)
                break;
            await Task.Delay(_timing.PostreadPeriod, cancellationToken).ConfigureAwait(false);
        }

        // Pressed and seen unchanged: no later stage of this click presses that control again (finding 4).
        _pressedUnchanged = PressedIdentity(clicked);
        return effectBoundary.Failure(operation, "visible_button_postread_unchanged", effectObserved: true);
    }

    /// <summary>The clicked window and the desktop's root windows before the click (ronda 20b, palanca 8,
    /// objetivo 3).</summary>
    internal sealed record HandoffWatch(nint Window, VisibleControlSurface.RootSnapshot Before);

    private HandoffWatch? RootsBefore(nint window)
    {
        if (RootWindows is not { } roots || window == 0)
            return null;
        try
        {
            return new HandoffWatch(window, roots(window));
        }
        catch (Exception exception) when (exception is IOException or InvalidOperationException)
        {
            return null;
        }
    }

    // The window of another process the click handed its effect to now; null when none (or no watch).
    private VisibleControlSurface.HandedWindow? Handed(HandoffWatch? watch)
    {
        if (watch is null || RootWindows is not { } roots)
            return null;
        try
        {
            VisibleControlSurface.RootWindow found = VisibleControlSurface.HandedTo(watch.Before, roots(watch.Window), out bool born);
            return found.Window == 0 ? null : DescribeHanded(found) is { } named ? named with { Born = born } : null;
        }
        catch (Exception exception) when (exception is IOException or InvalidOperationException)
        {
            return null;
        }
    }

    /// <summary>
    /// The receipt of a click that handed its effect to another process's window: done, the clicked window not said to
    /// have changed, and <c>handedTo</c> naming that window (its handle, title, process and process id) for the mission
    /// to follow (ronda 20b, palanca 8, objetivo 3).
    /// </summary>
    private static ExternalCapabilityReceipt HandedOff(
        string operation, JsonElement clicked, UiaFrontReport? front, VisibleControlSurface.HandedWindow handed)
    {
        JsonObject node = JsonNode.Parse(clicked.GetRawText())!.AsObject();
        front?.Write(node);
        node.Remove("pending");
        node["ok"] = true;
        node["error"] = "";
        node["handedTo"] = new JsonObject
        {
            ["hwnd"] = (long)handed.Window,
            ["title"] = handed.Title,
            ["process"] = handed.Process,
            ["processId"] = handed.ProcessId,
            ["born"] = handed.Born,
        };
        // Review 3 of palanca 8 (B1): where the person's input last went, for the mission's guard of their windows.
        if (handed.PersonInputAgoMs is long personAgo)
            ((JsonObject)node["handedTo"]!)["personInputAgoMs"] = personAgo;
        if (handed.PersonNearAgoMs is long nearAgo)
            ((JsonObject)node["handedTo"]!)["personNearAgoMs"] = nearAgo;
        node["cascadeStage"] = "uia_handoff";
        using JsonDocument verified = JsonDocument.Parse(node.ToJsonString());
        return ExternalJson.Success(operation, verified.RootElement.Clone(), true);
    }

    // Taken the way the image before the click was (the window's own drawing or the screen), never the other way.
    private async ValueTask<string?> SurfaceAsync(nint window, bool selfDrawn, CancellationToken cancellationToken)
    {
        try
        {
            VisibleControlSurface.CapturedWindow? capture =
                await _capture(window, selfDrawn, cancellationToken).ConfigureAwait(false);
            return capture is { } taken && taken.Hwnd == window ? taken.Sha256 : null;
        }
        catch (Exception exception) when (exception is IOException or InvalidOperationException)
        {
            return null;
        }
    }

    // The control's own answer once more, before a changed surface (or a popup born) closes the post-read: a selection or
    // a toggle it reports now is the receipt's (review finding 7). Null when it was not asked or does not hold yet.
    private async ValueTask<(ExternalCapabilityReceipt? Held, UiaFrontReport? Front)> LastAnswerAsync(
        string operation,
        bool ask,
        UiaFrontReport? front,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        if (!ask)
            return (null, front);
        using JsonDocument? last = await _worker.SendAsync("{\"cmd\":\"postread\"}", WorkerClickBudget, cancellationToken)
            .ConfigureAwait(false);
        if (last?.RootElement is not { } lastRoot)
            return (null, front);
        front = UiaFrontReport.Latest(front, UiaFrontReport.Read(lastRoot));
        return lastRoot.TryGetProperty("ok", out JsonElement held) && held.ValueKind == JsonValueKind.True
            ? (ReceiptFromWorker(operation, lastRoot, effectBoundary), front)
            : (null, front);
    }

    // Review of fable/cu-v3-recibo-del-clic-por-estado (finding 1): an answer the worker gave as done and the adapter
    // could not take as proof («visible_click_postread_invalid») still pressed the control; like a press seen unchanged,
    // no later stage of this click (OCR, vision) presses that same control again.
    private ExternalCapabilityReceipt NotedPress(ExternalCapabilityReceipt receipt, JsonElement clicked)
    {
        if (!receipt.Verified && receipt.EffectMayHaveOccurred)
            _pressedUnchanged ??= PressedIdentity(clicked);
        return receipt;
    }

    private static string? PressedIdentity(JsonElement clicked) =>
        clicked.ValueKind == JsonValueKind.Object
        && clicked.TryGetProperty("controlIdentity", out JsonElement pressedId)
        && pressedId.ValueKind == JsonValueKind.String
        && pressedId.GetString() is { Length: > 0 } pressedIdentity
            ? pressedIdentity
            : null;

    private static ExternalCapabilityReceipt SurfaceChanged(
        string operation, JsonElement clicked, UiaFrontReport? front = null, bool popupBorn = false)
    {
        JsonObject node = JsonNode.Parse(clicked.GetRawText())!.AsObject();
        front?.Write(node);
        node.Remove("pending");
        node["ok"] = true;
        node["error"] = "";
        node["surfaceChanged"] = true;
        if (popupBorn)
            node["popupBorn"] = true;
        node["cascadeStage"] = "uia_surface";
        using JsonDocument verified = JsonDocument.Parse(node.ToJsonString());
        return ExternalJson.Success(operation, verified.RootElement.Clone(), true);
    }

    internal static bool PostreadHolds(JsonElement root)
    {
        bool dismissed = root.TryGetProperty("absentOrDisabled", out JsonElement dismissedValue)
            && dismissedValue.ValueKind == JsonValueKind.True;
        bool selected = root.TryGetProperty("selected", out JsonElement selectedValue)
            && selectedValue.ValueKind == JsonValueKind.True;
        bool toggled = root.TryGetProperty("toggled", out JsonElement toggledValue)
            && toggledValue.ValueKind == JsonValueKind.True;
        bool surface = root.TryGetProperty("surfaceChanged", out JsonElement surfaceValue)
            && surfaceValue.ValueKind == JsonValueKind.True;
        // A field that takes text was made the text's destination, not pressed: the designation is what happened,
        // but only with the keyboard's focus on it (until the text reaches a field by its value, the next typing goes
        // wherever its window's focus is).
        bool targeted = root.TryGetProperty("targeted", out JsonElement targetedValue)
            && targetedValue.ValueKind == JsonValueKind.True
            && root.TryGetProperty("focused", out JsonElement focusedValue)
            && focusedValue.ValueKind == JsonValueKind.True;
        // Goal v3 B3: the list a control's arrow opened, or the context menu asked for, read open after the press.
        bool opened = root.TryGetProperty("opened", out JsonElement openedValue)
            && openedValue.ValueKind == JsonValueKind.True;
        // Ronda 20b, palanca 6 (review finding 1): the list a failed mission left open, read closed after its collapse.
        bool closed = root.TryGetProperty("closed", out JsonElement closedValue)
            && closedValue.ValueKind == JsonValueKind.True;
        // Recibo del clic por estado (r15b v3-42, v3-51), review finding 1: a field (Edit, Document, ComboBox) that took
        // the keyboard's focus or changed its value with the press, and the click's window disabled by the modal dialog
        // the press opened, are the worker's post-read proofs, each under its own key.
        bool fieldTook = root.TryGetProperty("fieldTook", out JsonElement fieldValue)
            && fieldValue.ValueKind == JsonValueKind.True;
        bool dialogOpened = root.TryGetProperty("dialogOpened", out JsonElement dialogValue)
            && dialogValue.ValueKind == JsonValueKind.True;
        return dismissed || selected || toggled || surface || targeted || opened || closed || fieldTook || dialogOpened;
    }

    private static ExternalCapabilityReceipt ReceiptFromWorker(
        string operation,
        JsonElement root,
        ExternalEffectBoundary effectBoundary)
    {
        bool effect = root.TryGetProperty("effectObserved", out JsonElement observed)
            && observed.ValueKind == JsonValueKind.True;
        bool ok = root.TryGetProperty("ok", out JsonElement accepted)
            && accepted.ValueKind == JsonValueKind.True;
        if (!ok)
        {
            string error = root.TryGetProperty("error", out JsonElement errorValue)
                && errorValue.ValueKind == JsonValueKind.String
                    ? errorValue.GetString() ?? "visible_click_failed"
                    : "visible_click_failed";
            if (error.Length == 0)
                error = "visible_click_failed";
            // The control left unpressed is named («name»), for the step that names it.
            if (!effect && error == NeedsConfirmation)
                return new ExternalCapabilityReceipt(operation, false, false, root.Clone(), error);
            // Auditoría P3 y C10: the controls whose name holds the label, none of them pressed, go with the «not found»
            // so the model can name one exactly.
            if (!effect && BeforeAnyPress.Contains(error)
                && root.TryGetProperty("candidates", out JsonElement candidates) && candidates.ValueKind == JsonValueKind.Array)
                return NotNamed(operation, error, [.. candidates.EnumerateArray()
                    .Where(candidate => candidate.ValueKind == JsonValueKind.String).Select(candidate => candidate.GetString()!)]);
            return !effect && BeforeAnyPress.Contains(error)
                ? ExternalJson.FailureBeforeEffect(operation, error)
                : effectBoundary.Failure(operation, error, effect);
        }

        if (!effect || !PostreadHolds(root))
            return effectBoundary.Failure(operation, "visible_click_postread_invalid", effect);
        return ExternalJson.Success(operation, root.Clone(), true);
    }

    // Etiqueta pedida frente a nombre visto (auditoría P3): iguales tras plegar mayúsculas, tildes y espacios. Ni alias,
    // ni «contiene», ni erratas: el modelo copia la etiqueta tal como la vio en la vista.
    internal static bool SameLabel(string label, string name)
    {
        string wanted = WindowsVisibleOcrLocator.Fold(label);
        return wanted.Length > 0 && string.Equals(wanted, WindowsVisibleOcrLocator.Fold(name), StringComparison.Ordinal);
    }

    // Nothing was pressed: the failure says the names seen instead (auditoría P3), for the model to name one exactly.
    internal static ExternalCapabilityReceipt NotNamed(string operation, string error, IReadOnlyList<string> candidates) =>
        candidates.Count == 0
            ? ExternalJson.FailureBeforeEffect(operation, error)
            : new ExternalCapabilityReceipt(operation, false, false, ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteStartArray("candidates");
                foreach (string candidate in candidates)
                    writer.WriteStringValue(candidate);
                writer.WriteEndArray();
                writer.WriteEndObject();
            }), error);

    internal static int EditDistance(string left, string right, int cap)
    {
        if (Math.Abs(left.Length - right.Length) > cap)
            return cap + 1;
        int[] previous = new int[right.Length + 1];
        int[] current = new int[right.Length + 1];
        for (int column = 0; column <= right.Length; column++)
            previous[column] = column;
        for (int row = 1; row <= left.Length; row++)
        {
            current[0] = row;
            int best = current[0];
            for (int column = 1; column <= right.Length; column++)
            {
                int cost = left[row - 1] == right[column - 1] ? 0 : 1;
                current[column] = Math.Min(
                    Math.Min(previous[column] + 1, current[column - 1] + 1),
                    previous[column - 1] + cost);
                best = Math.Min(best, current[column]);
            }

            if (best > cap)
                return cap + 1;
            (previous, current) = (current, previous);
        }

        return previous[right.Length];
    }

    // What the worker must not press without its name in the invocation (the worker's Test-AsksMore), RiskPolicy's own.
    private static JsonObject AsksRequest() => new()
    {
        ["pattern"] = RiskPolicy.AsksPattern,
        ["hint"] = RiskPolicy.FoldHint,
    };

    private static bool ShouldKeep(ExternalCapabilityReceipt receipt) =>
        receipt.Verified && receipt.ErrorCode is null;

    /// <summary>The worker's answer to a toggle whose sibling's mark did not appear for it (ronda 20b, palanca 7).</summary>
    internal const string ToggleUncorroborated = "visible_toggle_uncorroborated";

    /// <summary>The worker's answer to a choice whose place did not move after its posted press (review of ronda 20b, finding 3).</summary>
    internal const string ChoiceUncorroborated = "visible_choice_uncorroborated";

    /// <summary>The worker's answer to a point on the control the tree already pressed in this click.</summary>
    internal const string PointAlreadyPressed = "visible_point_already_pressed";

    // The identity of the control the tree pressed in the running click and saw nothing change from (finding 4).
    private string? _pressedUnchanged;

    private static string? ControlIdentity(ExternalCapabilityReceipt receipt) =>
        receipt.Result is { ValueKind: JsonValueKind.Object } result
        && result.TryGetProperty("controlIdentity", out JsonElement identity)
        && identity.ValueKind == JsonValueKind.String
        && identity.GetString() is { Length: > 0 } id
            ? id
            : null;

    private static bool ShouldCascade(ExternalCapabilityReceipt receipt) =>
        receipt.ErrorCode is not null && CascadeAfter.Contains(receipt.ErrorCode);

    /// <summary>
    /// The window the warm-up look reads (<see cref="VisibleControlSurface.ShellWindow"/>: the shell's own desktop,
    /// never an application's window nor the one in front); a test seam names its own.
    /// </summary>
    internal Func<nint> WarmupWindow { get; init; } = VisibleControlSurface.ShellWindow;

    /// <summary>
    /// Ronda 28 (banco Br27: the first whole look of a session cost 1 041–1 200 ms, 190–340 ms once warm, with the worker
    /// already started): the worker is started and asked one look ahead of the first mission, so what a first look
    /// compiles and loads (the worker's view functions, UI Automation's client) is paid while the mind is still loading.
    /// The look is of the shell's desktop window, by the read-only «view» (no front, no key, no click, no capture, no
    /// text) and asks for one control; its answer is dropped here, never journaled nor handed to anyone. With no shell
    /// window nothing is asked: a look without a window would read the one in front, which is the person's.
    /// </summary>
    internal async ValueTask PrewarmAsync()
    {
        await _worker.PrewarmAsync(CancellationToken.None).ConfigureAwait(false);
        nint shell = WarmupWindow();
        if (shell == 0)
            return;
        using JsonDocument? dropped = await _worker
            .SendAsync(ViewCommand(shell, 1, null), WorkerViewBudget, CancellationToken.None)
            .ConfigureAwait(false);
    }

    /// <summary>The control the last view handed out at this index, and that view's window: what input.scroll's
    /// «index» names. False when no view handed it out.</summary>
    internal bool TryViewedControl(int index, out nint window, out string controlId, out Rect? rect)
    {
        LastView? view;
        lock (_viewLock)
        {
            view = _lastView;
        }

        ViewControl? chosen = view?.Controls.FirstOrDefault(control => control.Index == index);
        window = chosen is null ? 0 : view!.Hwnd;
        controlId = chosen?.Id ?? string.Empty;
        rect = chosen?.RectValue;
        return chosen is not null;
    }

    /// <summary>The field the last view handed out at this index, and that view's window: what input.text.type's
    /// «index» names. False when no view handed it out or it carries no identity.</summary>
    public bool TryViewedField(int index, out nint window, out string controlId)
    {
        bool viewed = TryViewedControl(index, out window, out controlId, out _);
        return viewed && controlId.Length > 0;
    }

    /// <summary>A text delivered to a viewed field through UI Automation (the worker's «field»: ValuePattern.SetValue
    /// where replacing is the same as typing), or only its description when <paramref name="text"/> is null; null
    /// when the worker did not answer.</summary>
    public ValueTask<JsonDocument?> FieldAsync(
        nint window,
        string controlId,
        string? text,
        bool replace,
        CancellationToken cancellationToken) =>
        _worker.SendAsync(
            new JsonObject
            {
                ["cmd"] = "field",
                ["hwnd"] = window,
                ["controlId"] = controlId,
                ["text"] = text,
                ["replace"] = replace,
            }.ToJsonString(),
            WorkerClickBudget,
            cancellationToken);

    /// <summary>A list box's own entry chosen by pattern (the worker's «field» with «entry»); null when the worker did
    /// not answer.</summary>
    public ValueTask<JsonDocument?> EntryAsync(
        nint window,
        string controlId,
        string text,
        CancellationToken cancellationToken) =>
        _worker.SendAsync(
            new JsonObject
            {
                ["cmd"] = "field",
                ["hwnd"] = window,
                ["controlId"] = controlId,
                ["text"] = text,
                ["entry"] = true,
            }.ToJsonString(),
            WorkerClickBudget,
            cancellationToken);

    /// <summary>Revision 1 of r24b (v1): the keyboard's focus put on a viewed field through UI Automation (the worker's
    /// «focus», only with its window in front); null when the worker did not answer.</summary>
    public ValueTask<JsonDocument?> FocusAsync(
        nint window,
        string controlId,
        CancellationToken cancellationToken) =>
        _worker.SendAsync(
            new JsonObject
            {
                ["cmd"] = "focus",
                ["hwnd"] = window,
                ["controlId"] = controlId,
            }.ToJsonString(),
            WorkerClickBudget,
            cancellationToken);

    /// <summary>Brings the element named <paramref name="label"/> into view in <paramref name="window"/> through UI
    /// Automation (the worker's «reveal»); null when the worker did not answer.</summary>
    internal ValueTask<JsonDocument?> RevealAsync(
        nint window,
        string label,
        string direction,
        int pages,
        CancellationToken cancellationToken) =>
        _worker.SendAsync(
            new JsonObject
            {
                ["cmd"] = "reveal",
                ["hwnd"] = window,
                ["aliases"] = new JsonArray(label),
                ["direction"] = direction,
                ["amount"] = pages,
            }.ToJsonString(),
            RevealBudget,
            cancellationToken);

    // A page-by-page search re-reads the tree after every page.
    private static readonly TimeSpan RevealBudget = TimeSpan.FromSeconds(15);

    /// <summary>Scrolls a viewed control through its UI Automation ScrollPattern; null when the worker did not answer.</summary>
    internal ValueTask<JsonDocument?> ScrollControlAsync(
        nint window,
        string controlId,
        string direction,
        int amount,
        CancellationToken cancellationToken) =>
        _worker.SendAsync(
            new JsonObject
            {
                ["cmd"] = "scroll",
                ["hwnd"] = window,
                ["controlId"] = controlId,
                ["direction"] = direction,
                ["amount"] = amount,
            }.ToJsonString(),
            WorkerClickBudget,
            cancellationToken);

    public void Dispose()
    {
        (_worker as IDisposable)?.Dispose();
    }

    internal readonly record struct Rect(int X, int Y, int W, int H);

    internal sealed class ViewControl
    {
        internal int Index { get; set; }
        internal string Kind { get; set; } = string.Empty;
        internal string Name { get; set; } = string.Empty;
        internal string NameSource { get; set; } = string.Empty;
        internal string Id { get; set; } = string.Empty;
        internal string State { get; set; } = string.Empty;
        internal string? Value { get; set; }
        internal string ItemType { get; set; } = string.Empty;
        internal string Shortcut { get; set; } = string.Empty;
        internal Rect? RectValue { get; set; }
        internal int Repeated { get; set; }
        internal string Zone { get; set; } = string.Empty;
        internal string Color { get; set; } = string.Empty;
        internal bool SystemMenu { get; set; }
        // Ronda 21: the window's content surface (the largest pane, canvas or document that holds no control), listed
        // past the cap by its kind and rectangle.
        internal bool Body { get; set; }
        internal bool Reserved { get; set; }
        // Revision 1 of ronda 24 (B1): the signature's control lies inside a Document (a page's content, never the
        // window's frame).
        internal bool Content { get; set; }
    }

    private sealed record LastView(nint Hwnd, IReadOnlyList<ViewControl> Controls);

    private readonly record struct ViewResult(ExternalCapabilityReceipt Receipt, IReadOnlyList<string> Names);
}

/// <summary>
/// Dominant colour of each control's rectangle over the window capture
/// (CONTRATO_VISTA_ACCION.md §1.5): an HSV histogram over the pixels, so
/// «el botón rojo» resolves without a model.
/// </summary>
internal static class VisibleControlColors
{
    internal static readonly string[] Names =
        ["red", "orange", "yellow", "green", "cyan", "blue", "purple", "pink", "white", "black", "gray"];

    internal static void Assign(
        VisibleControlSurface.CapturedWindow capture,
        IReadOnlyList<WindowsVisibleControlAdapter.ViewControl> controls)
    {
        byte[] bmp = capture.Bmp;
        if (!TryParse(bmp, out int offset, out int width, out int height) || width <= 0 || height <= 0)
            return;
        foreach (WindowsVisibleControlAdapter.ViewControl control in controls)
        {
            if (control.RectValue is not { } rect)
                continue;
            int left = rect.X - capture.Left;
            int top = rect.Y - capture.Top;
            control.Color = Dominant(bmp, offset, width, height, left, top, rect.W, rect.H);
        }
    }

    internal static bool TryParse(byte[] bmp, out int offset, out int width, out int height)
    {
        offset = width = height = 0;
        if (bmp.Length < 54 || bmp[0] != (byte)'B' || bmp[1] != (byte)'M')
            return false;
        offset = BitConverter.ToInt32(bmp, 10);
        width = BitConverter.ToInt32(bmp, 18);
        height = BitConverter.ToInt32(bmp, 22);
        short bits = BitConverter.ToInt16(bmp, 28);
        if (bits != 32 || offset <= 0 || offset >= bmp.Length)
            return false;
        long needed = (long)offset + (long)Math.Abs(width) * Math.Abs(height) * 4;
        return needed <= bmp.Length;
    }

    internal static string Dominant(
        byte[] bmp, int offset, int width, int height,
        int left, int top, int boxWidth, int boxHeight)
    {
        if (boxWidth <= 0 || boxHeight <= 0)
            return string.Empty;
        // Recorte del 10 % por lado: el borde de un control es su contorno,
        // no su color.
        int insetX = boxWidth / 10;
        int insetY = boxHeight / 10;
        int x0 = Math.Max(0, left + insetX);
        int y0 = Math.Max(0, top + insetY);
        int x1 = Math.Min(width, left + boxWidth - insetX);
        int y1 = Math.Min(height, top + boxHeight - insetY);
        if (x1 <= x0 || y1 <= y0)
            return string.Empty;
        int stepX = Math.Max(1, (x1 - x0) / 64);
        int stepY = Math.Max(1, (y1 - y0) / 64);
        bool bottomUp = height > 0;
        int rows = Math.Abs(height);
        int stride = width * 4;
        int[] histogram = new int[Names.Length];
        for (int y = y0; y < y1; y += stepY)
        {
            int row = bottomUp ? rows - 1 - y : y;
            if (row < 0 || row >= rows)
                continue;
            for (int x = x0; x < x1; x += stepX)
            {
                int index = offset + row * stride + x * 4;
                if (index + 2 >= bmp.Length)
                    continue;
                histogram[Classify(bmp[index + 2], bmp[index + 1], bmp[index])]++;
            }
        }

        int best = 0;
        for (int index = 1; index < histogram.Length; index++)
        {
            if (histogram[index] > histogram[best])
                best = index;
        }

        return histogram[best] == 0 ? string.Empty : Names[best];
    }

    internal static int Classify(byte red, byte green, byte blue)
    {
        double r = red / 255.0;
        double g = green / 255.0;
        double b = blue / 255.0;
        double max = Math.Max(r, Math.Max(g, b));
        double min = Math.Min(r, Math.Min(g, b));
        double delta = max - min;
        double saturation = max <= 0 ? 0 : delta / max;
        double value = max;
        if (saturation < 0.18)
        {
            if (value >= 0.85)
                return 8; // white
            if (value <= 0.2)
                return 9; // black
            return 10; // gray
        }

        double hue;
        if (delta <= 0)
            hue = 0;
        else if (max == r)
            hue = 60 * (((g - b) / delta) % 6);
        else if (max == g)
            hue = 60 * ((b - r) / delta + 2);
        else
            hue = 60 * ((r - g) / delta + 4);
        if (hue < 0)
            hue += 360;
        if (hue < 15 || hue >= 330)
            return hue >= 330 && saturation < 0.55 ? 7 : 0; // pink or red
        if (hue < 40)
            return 1; // orange
        if (hue < 70)
            return 2; // yellow
        if (hue < 170)
            return 3; // green
        if (hue < 200)
            return 4; // cyan
        if (hue < 270)
            return 5; // blue
        return hue < 300 ? 6 : 7; // purple / pink
    }
}
