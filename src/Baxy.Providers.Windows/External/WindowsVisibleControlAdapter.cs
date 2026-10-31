using System.Diagnostics;
using System.Globalization;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Kernel.Operations;
using Baxy.Kernel.Policy;
using Baxy.Providers.Windows.Infrastructure;

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
    /// <summary>
    /// Ronda final 21 (seguridad, el cauce del incidente del 2026-10-15): the window the point is on is a protected one
    /// (a system configuration tool, a developer's or BAXY's own window no look named): nothing was pressed.
    /// </summary>
    Protected,

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
    /// Ronda final 18 (regla 3): the control at the point is one RiskPolicy holds for the person's «yes»: nothing was
    /// pressed, and the receipt says so with its code (visible_control_needs_confirmation), never «another control».
    /// </summary>
    NeedsConfirmation,

    /// <summary>
    /// Review of lat-apertura-clic (finding 4): the point lies on the control the accessible tree already pressed in
    /// this click and saw nothing change from: neither its way nor the pointer presses it a second time.
    /// </summary>
    AlreadyPressed,

    /// <summary>
    /// Auditoría final (regla 3): the field there already had the keyboard's focus (the worker's «prefocused»):
    /// nothing was pressed and the state asked for was already reached, said as that (changed:false), never as the
    /// control not found.
    /// </summary>
    AlreadyFocused,
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

    internal static PointPressed HeldForConfirmation { get; } = new(PointPressOutcome.NeedsConfirmation);

    internal static PointPressed InProtectedWindow { get; } = new(PointPressOutcome.Protected);

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
    /// Ronda final 21 (regla 3): the desktop's root windows before a stage's press on <paramref name="window"/>, so a
    /// window of another process that comes with it is not told «unchanged» (<see cref="AnotherWindowCame"/>); null
    /// watches nothing.
    /// </summary>
    object? WatchRoots(nint window) => null;

    /// <summary>A window of another process came since <paramref name="watch"/> (handed to, or of unproved cause).</summary>
    bool AnotherWindowCame(object? watch) => false;

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
    /// (<see cref="PointPressOutcome.Refused"/>, or <see cref="PointPressOutcome.NeedsConfirmation"/> for a control
    /// held for the person's «yes»), so the pointer does not press it either.
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
        if (pressed.Outcome == PointPressOutcome.NeedsConfirmation)
        {
            return new Outcome(
                ExternalJson.FailureBeforeEffect(operation, WindowsVisibleControlAdapter.NeedsConfirmation),
                string.Empty, false, string.Empty, null);
        }
        if (pressed.Outcome == PointPressOutcome.Protected)
        {
            return new Outcome(
                ExternalJson.FailureBeforeEffect(operation, "protected_window"),
                string.Empty, false, string.Empty, null);
        }
        if (pressed.Outcome == PointPressOutcome.AlreadyPressed)
        {
            return new Outcome(
                ExternalJson.FailureBeforeEffect(operation, WindowsVisibleControlAdapter.PointAlreadyPressed),
                string.Empty, false, string.Empty, null);
        }
        if (pressed.Outcome == PointPressOutcome.AlreadyFocused)
        {
            JsonElement reached = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteString("label", label);
                writer.WriteString("method", "target");
                writer.WriteString("name", pressed.Name);
                writer.WriteString("kind", pressed.Kind);
                writer.WriteBoolean("focused", true);
                writer.WriteBoolean("alreadyFocused", true);
                writer.WriteString("authority", "uia_keyboard_focus_preread");
                writer.WriteEndObject();
            });
            return new Outcome(
                ExternalJson.Switched(operation, reached, effectObserved: false),
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
        // Ronda final 18 (regla 3): a window not read again is said unread, never «changed».
        if (recheck.Again is not { } again)
            return new PointerChecked(screenX, screenY, null, false, VisibleControlSurface.SurfaceUnread);
        if (!recheck.Moved && !recheck.Redrawn)
            return new PointerChecked(screenX, screenY, again, false, null);
        // PLAN_GENERAL A3 (e2e del notebook: Epic's store video never stops): only parts away from the point redrew; the
        // point still means the same control, and the new capture is the post-read's baseline.
        if (!recheck.Moved && VisibleControlSurface.SameAround(seen, again, screenX - again.Left, screenY - again.Top))
            return new PointerChecked(screenX, screenY, again, true, null);
        (int X, int Y)? found = relocate is null || recheck.Moved
            ? null
            : await relocate(again, cancellationToken).ConfigureAwait(false);
        if (found is { } point)
            return new PointerChecked(point.X, point.Y, again, true, null);
        // PLAN_GENERAL A3: the surface was still changing (an animation, a page loading, the window moved): it is waited
        // on until two captures in a row are the same, and the label is located again on that still capture.
        if (relocate is not null
            && await VisibleControlSurface.StableSurfaceAsync(
                    again, (hwnd, token) => ReadAsync(capture, hwnd, token),
                    (ms, token) => Task.Delay(ms, token), cancellationToken).ConfigureAwait(false) is { } still
            && await relocate(still, cancellationToken).ConfigureAwait(false) is { } settled)
            return new PointerChecked(settled.X, settled.Y, still, true, null);
        return new PointerChecked(screenX, screenY, null, true, VisibleControlSurface.SurfaceChangedWhileWaiting);
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
/// foreground lease; <see cref="Prepare"/> says whether the point may be pressed now (the window the click is bound to
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

internal sealed class ScreenPointer : IPointerFallback
{
    // r4a M3: no settle in front any more (it kept the front 250 ms per press). The settle was there because the image
    // before the press was taken in front, right after the window repainted its active caption; the baseline is now
    // the window's own drawing taken behind before the burst (CaptureBehindAsync), as the post-read sees it.
    public ValueTask<IInputBurst> AcquireAsync(nint window, CancellationToken cancellationToken) =>
        ForegroundLease.Shared.AcquireAsync(window, cancellationToken);

    public ValueTask<(bool Paused, long WaitedMs)> PauseAsync(CancellationToken cancellationToken) =>
        ForegroundLease.Shared.WaitForPauseAsync(cancellationToken);

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

    // FT/proveedores goal (E6): the opened application's minimized window (0: none), for a keyboard act to restore it.
    nint MinimizedWindow(VisibleControlSurface.OpenedApplication opened) => 0;
}

internal sealed class OpenedApplicationFocus : IOpenedApplicationFocus
{
    // A click asked in the same breath as the opening, or answered after its confirmation, comes well inside this.
    private static readonly TimeSpan Freshness = TimeSpan.FromSeconds(90);

    public VisibleControlSurface.OpenedApplication? TakeOpened() =>
        VisibleControlSurface.TakeOpened(Freshness);

    public VisibleControlSurface.OpenedApplication? PeekOpened() =>
        VisibleControlSurface.PeekOpened(Freshness);

    public nint MinimizedWindow(VisibleControlSurface.OpenedApplication opened) =>
        VisibleControlSurface.MinimizedOpenedWindow(opened);

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
/// Perception and the click of the computer-use engine.
/// <c>input.visible.controls</c> is the view of a window: up to sixty controls
/// (actionable ones first, then the rest, then the classic menu's entries; a «tail»
/// look keeps the last ones in tree order), plus, when the cut left them out, up to
/// ten more whose names carry a word of «wanted», and the window's body when the
/// view lists more than one control, with index, kind, label, state, value and
/// shortcut, the disabled ones
/// by kind and label, the written text by zone (OCR), the window's title and
/// process. <c>input.visible.click</c> invokes one control by label, by the index
/// of the last view (resolved here to that control's identity, kept with the view
/// and not written in it) or by an identity given as <c>controlId</c>, through the
/// persistent UIA worker, then OCR, then vision, and demands a post-read.
/// </summary>
internal sealed class WindowsVisibleControlAdapter
    : IExternalOperationAdapter, IViewedFields, IPointPress, ISearchBurstActs, IDisposable
{
    // The code of a click refused because its window runs as administrator (contract §4, «window_elevated»).
    internal const string WindowElevated = "window_elevated";
    // Auditoría final (regla 3): a window whose process token could not be read is not said to run as administrator;
    // it is refused all the same (nothing is pressed where UIPI may block it), as not read.
    internal const string WindowElevationUnread = "window_elevation_unread";

    // Whether the window changes by itself after the capture `first` (VisibleControlSurface.AnimationProbes).
    private async ValueTask<bool> AnimatesFromAsync(
        nint hwnd, VisibleControlSurface.CapturedWindow first, CancellationToken cancellationToken)
    {
        foreach (TimeSpan wait in VisibleControlSurface.AnimationProbes)
        {
            await Task.Delay(wait, cancellationToken).ConfigureAwait(false);
            VisibleControlSurface.CapturedWindow? again = await _capture(hwnd, first.SelfDrawn, cancellationToken)
                .ConfigureAwait(false);
            if (again is not { } next || !string.Equals(next.Sha256, first.Sha256, StringComparison.Ordinal))
                return true;
        }
        return false;
    }

    private static string ElevatedCode(nint window)
    {
        int processId = VisibleControlSurface.WindowProcess(window).ProcessId;
        return processId > 0 && VisibleControlSurface.Elevated(processId) is null ? WindowElevationUnread : WindowElevated;
    }

    // Encargo V: the worker found the control to press and its name asks for the person's word while no label of the click
    // does (RiskPolicy.PressedNameAsksMoreThanItsLabel): nothing is pressed, by this stage or a later one, and the receipt
    // names it, so the step that names it is the one RiskPolicy asks for.
    internal const string NeedsConfirmation = "visible_control_needs_confirmation";

    private static readonly HashSet<string> CascadeAfter = new(StringComparer.Ordinal)
    {
        "visible_button_not_found",
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
        // Ronda 21 (pasada r18 v3-65, v3-25): the worker's walk of what is shown ran out of its own time before it found
        // the control, and said so before the host's limit: nothing was pressed.
        "visible_lookup_timeout",
        // Ronda 24b (banco r23 u9): a list, tree, grid or table with neither Invoke nor SelectionItem is no thing to press
        // (its pointer click chose whatever row was at its centre): refused before anything was sent.
        "visible_control_is_container",
        // Ronda B (falta 3): a toolbar button seen through its MSAA proxy whose bar answers another window or another
        // button at its point: nothing was sent, neither as a message nor by the pointer.
        "visible_control_covered",
        // BAXY Renew cu (C02): a switch of Windows' own Settings, refused before anything was pressed.
        SettingsSwitchRefused,
    };

    /// <summary>
    /// BAXY Renew cu (C02): the worker found the control a switch (On/Off) of Windows' own Settings, which changes the
    /// machine (its Wi-Fi radio, its Bluetooth, airplane mode) and no click presses: «mira si el wifi está conectado»
    /// pressed the «Wi-Fi» switch (on → off) and the radio stayed off. Refused before anything was pressed, with its state.
    /// </summary>
    internal const string SettingsSwitchRefused = "visible_settings_switch_refused";

    internal static JsonElement SettingsSwitchFacts(JsonElement root) => ExternalJson.Create(writer =>
    {
        writer.WriteStartObject();
        if (root.TryGetProperty("name", out JsonElement name) && name.ValueKind == JsonValueKind.String)
            writer.WriteString("name", name.GetString());
        string? state = root.TryGetProperty("switchState", out JsonElement value) && value.ValueKind == JsonValueKind.String
            ? value.GetString()
            : null;
        if (state is "On" or "Off")
            writer.WriteString("switch", state == "On" ? "on" : "off");
        writer.WriteString("next", "nothing was pressed: a switch of Windows' Settings changes the machine, so a click "
            + "never flips it; its state is the one shown (on or off). When the person asks it, wifi_radio_set and "
            + "bluetooth_radio_set change those radios, and system_settings_set the settings airplane_mode, "
            + "do_not_disturb or brightness; a switch none of them covers is the person's to flip");
        writer.WriteEndObject();
    });

    // Encargo IMP4: the lines a look that asks for «lines» reads, each by its place (a chat's whole pane: 79 lines
    // measured on redpc); encargo WA-LEER: up to OperationVisibleFacts.ChatLines.
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
    // The window of the application a look names (exactly); 0 when none shows.
    private readonly Func<string?, CancellationToken, ValueTask<nint>> _requestedWindow;
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
    // The clock the label's wait runs on: when a click changed the screen, the opening's settling and the label's
    // budget, the pause between looks and the still window's watch (the opened application's NotedUtc is on it too).
    private readonly TimeProvider _time;

    private DateTime Now => _time.GetUtcNow().UtcDateTime;

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
    /// The text of a search burst (<see cref="SearchBurst"/>), typed into the named window as
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

    /// <summary>
    /// Ronda final 21 (seguridad, el cauce del incidente del 2026-10-15): the provider's gate judges the window an act
    /// names or the one in front, and this adapter acts, without a window named, in the application just opened, the
    /// window of the last look or the one a control's identity belongs to. Every act of it is judged again on the window
    /// it resolved, right before it is sent (<see cref="VisibleControlSurface.ActRefused"/>); null (the test seams that
    /// name none) judges nothing.
    /// </summary>
    internal Func<nint, bool>? ActRefused { get; init; }

    /// <summary>
    /// Renew al máximo (aislamiento de pruebas): the window in front a look or a click without a window named takes
    /// (<see cref="VisibleControlSurface.ResolveForegroundAsync"/>, the product's). A test seam names its own, so the
    /// desktop's real front (an elevated msconfig or Task Manager answered «window_elevated») never decides it.
    /// </summary>
    internal Func<CancellationToken, ValueTask<nint>> WindowInFront { get; init; } =
        VisibleControlSurface.ResolveForegroundAsync;

    /// <summary>
    /// Ronda final 22-24: whether a window is the opened application's (drawn or hosted by its process, or, when the
    /// opening launched it, by the family of processes its launch started, as a launcher's child): a click that names
    /// another process's window is not bound to the application just opened. Null (the test seams that name none)
    /// binds as before.
    /// </summary>
    internal Func<nint, VisibleControlSurface.OpenedApplication, bool>? WindowOfProcess { get; init; }

    private bool Refuses(nint window) => window != 0 && ActRefused?.Invoke(window) == true;

    // A worker answer for an act refused before it is sent: nothing reached the window.
    private static JsonDocument RefusedAnswer() =>
        JsonDocument.Parse("{\"ok\":false,\"effectObserved\":false,\"error\":\"protected_window\"}");

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

    /// <summary>
    /// Renew al máximo (7.1): whether a completed act reads its window again (<see cref="AfterActAsync"/>); the test
    /// seams that name none read nothing after.
    /// </summary>
    internal bool ReadsAfterAct { get; init; }

    // Renew al máximo (7.1): the read after an act walks the tree for at most AfterReadSeconds (the worker answers
    // «partial» then) and is waited for AfterReadBudget; at most AfterViewCap entries of the difference are written.
    internal const double AfterReadSeconds = 1.5;
    private static readonly TimeSpan AfterReadBudget = TimeSpan.FromSeconds(3);
    internal const int AfterViewCap = 20;

    // The window the running click pressed in (by the tree, at a point or by the pointer); 0 before any press.
    private nint _actedWindow;

    // Revisión de nb-w11-revision: the desktop's root windows before the last click (its handoff watch), so a click whose
    // view after it differs only in the focus is not told unchanged when a window of another process came meanwhile.
    private HandoffWatch? _clickRoots;

    /// <summary>
    /// Renew al máximo (7.1): the window of the last view read again after a completed act, by the look's own request
    /// (the worker's «view», with that look's limit, words and cut, so its numbering is a look's) and bounded in time.
    /// It becomes the last view (an index of the view before that is no longer there is refused as after any look) and
    /// its difference from that view is returned (<see cref="ViewDifference"/>). Nothing is pressed, brought up, shown
    /// or captured. Null, with the last view left as it was, when the last view is of another window, a modal dialog
    /// now disables the window (the effect is in the dialog), or the read does not answer, fails or is cut.
    /// </summary>
    public async ValueTask<JsonElement?> AfterActAsync(nint window, CancellationToken cancellationToken)
    {
        if (!ReadsAfterAct || window == 0)
            return null;
        LastView? before;
        lock (_viewLock)
        {
            before = _lastView;
        }

        if (before is null || before.Hwnd != window || VisibleControlSurface.ModalSurface(window) != window)
            return null;
        JsonDocument? answer;
        try
        {
            answer = await _worker.SendAsync(
                    ViewCommand(window, before.Limit, before.Wanted, before.Tail, AfterReadSeconds),
                    AfterReadBudget, cancellationToken)
                .ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is IOException or JsonException or TimeoutException
            or InvalidOperationException or OperationCanceledException)
        {
            return null;
        }

        if (answer is null)
            return null;
        using (answer)
        {
            JsonElement root = answer.RootElement;
            // A walk cut by its deadline does not prove what it did not list is gone.
            if (root.ValueKind != JsonValueKind.Object
                || !root.TryGetProperty("ok", out JsonElement ok) || ok.ValueKind != JsonValueKind.True
                || (root.TryGetProperty("partial", out JsonElement partial) && partial.ValueKind == JsonValueKind.True))
                return null;
            List<ViewControl> controls = ParseControls(root);
            List<ViewControl> disabled = ParseControls(root, "disabled");
            string title = ReadString(root, "window");
            bool afterCut = root.TryGetProperty("controlCount", out JsonElement total) && total.ValueKind == JsonValueKind.Number
                && total.TryGetInt32(out int counted) && counted > controls.Count;
            lock (_viewLock)
            {
                if (!ReferenceEquals(_lastView, before))
                    return null;
                _lastView = new LastView(window, controls)
                {
                    Cut = afterCut,
                    TreeTitle = title,
                    Limit = before.Limit,
                    Wanted = before.Wanted,
                    Tail = before.Tail,
                    Application = before.Application,
                };
                _viewsRead++;
            }

            return ViewDifference(before.Controls, before.TreeTitle, controls, disabled, title, cut: before.Cut || afterCut);
        }
    }

    /// <summary>
    /// Renew al máximo (7.1): what a view of a window shows that the one before it did not, by control: «changed»
    /// (the same control, by its identity or else its kind and name, with another name, state or value), «appeared»,
    /// «gone» (no longer listed; «disabled» when the window now lists it disabled) and «moved» (the same control at
    /// another index), each with its index in the new view; «title» when the window's name changed. At most
    /// <paramref name="cap"/> entries, in that order, and «omitted» the rest; «same» when nothing differs.
    /// Renew al máximo (w8): with either view cut at its cap (<paramref name="cut"/>: the window had more controls than
    /// it listed), a control not listed after is not «gone» (a click that adds three pushes three others past the cap)
    /// and nothing unlisted is known the same: no «gone», «sameListed» in place of «same», and «cut».
    /// Holdout v5 V5E029: a changed state is written as it was and as it is («focused → (none)»), and a whole view whose
    /// only difference is the keyboard's focus (controls that took or lost it, nothing else) says «focusOnly».
    /// A cut view never says it (revisión w11): what it did not list may have changed (a message sent, an item deleted
    /// past the cap), and «focusOnly» turns the click unchanged, which would have the model press it again.
    /// </summary>
    internal static JsonElement ViewDifference(
        IReadOnlyList<ViewControl> before,
        string beforeTitle,
        IReadOnlyList<ViewControl> after,
        IReadOnlyList<ViewControl> disabledAfter,
        string afterTitle,
        int cap = AfterViewCap,
        bool cut = false)
    {
        var matched = new ViewControl?[after.Count];
        var used = new HashSet<ViewControl>(ReferenceEqualityComparer.Instance);
        for (int i = 0; i < after.Count; i++)
        {
            ViewControl now = after[i];
            if (now.Id.Length > 0
                && before.FirstOrDefault(was => was.Id == now.Id && !used.Contains(was)) is { } same)
            {
                matched[i] = same;
                used.Add(same);
            }
        }

        for (int i = 0; i < after.Count; i++)
        {
            ViewControl now = after[i];
            if (matched[i] is null
                && before.FirstOrDefault(was => !used.Contains(was) && was.Kind == now.Kind && was.Name == now.Name) is { } same)
            {
                matched[i] = same;
                used.Add(same);
            }
        }

        List<string> changed = [], appeared = [], moved = [];
        bool focusOnly = true;
        for (int i = 0; i < after.Count; i++)
        {
            ViewControl now = after[i];
            if (matched[i] is not { } was)
                appeared.Add(Entry(now));
            else if (was.Kind != now.Kind || was.Name != now.Name || was.State != now.State
                || (was.Value ?? string.Empty) != (now.Value ?? string.Empty))
            {
                changed.Add(Entry(now, was));
                focusOnly &= was.Kind == now.Kind && was.Name == now.Name
                    && (was.Value ?? string.Empty) == (now.Value ?? string.Empty)
                    && WithoutFocus(was.State) == WithoutFocus(now.State);
            }
            else if (was.Index != now.Index)
                moved.Add($"[{now.Index}] {now.Kind} «{now.Name}» was [{was.Index}]");
        }

        List<string> gone = cut ? [] : [.. before.Where(was => !used.Contains(was)).Select(was =>
            $"{was.Kind} «{was.Name}»"
            + (disabledAfter.Any(off => off.Kind == was.Kind && off.Name == was.Name) ? " disabled" : string.Empty))];
        bool titled = beforeTitle.Length > 0 && afterTitle.Length > 0 && beforeTitle != afterTitle;
        // A cut view does not know its unlisted controls the same.
        focusOnly &= changed.Count > 0 && appeared.Count + gone.Count + moved.Count == 0 && !titled && !cut;
        int room = cap;
        return ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            if (!titled && changed.Count + appeared.Count + gone.Count + moved.Count == 0)
            {
                writer.WriteBoolean(cut ? "sameListed" : "same", true);
                if (cut)
                    writer.WriteBoolean("cut", true);
                writer.WriteEndObject();
                return;
            }

            if (titled)
                writer.WriteString("title", afterTitle);
            WriteList("changed", changed);
            WriteList("appeared", appeared);
            WriteList("gone", gone);
            WriteList("moved", moved);
            int omitted = changed.Count + appeared.Count + gone.Count + moved.Count - (cap - room);
            if (omitted > 0)
                writer.WriteNumber("omitted", omitted);
            if (cut)
                writer.WriteBoolean("cut", true);
            if (focusOnly)
                writer.WriteBoolean("focusOnly", true);
            writer.WriteEndObject();

            void WriteList(string name, List<string> entries)
            {
                int shown = Math.Min(entries.Count, room);
                if (shown == 0)
                    return;
                room -= shown;
                writer.WriteStartArray(name);
                foreach (string entry in entries.Take(shown))
                    writer.WriteStringValue(entry);
                writer.WriteEndArray();
            }
        });

        static string Entry(ViewControl control, ViewControl? was = null) =>
            $"[{control.Index}] {control.Kind} «{control.Name}»"
            + (control.NameCut > 0 ? $" (nombre cortado: faltan {control.NameCut} caracteres)" : string.Empty)
            + (was is not null && was.State != control.State
                ? $" {StateOrNone(was.State)} → {StateOrNone(control.State)}"
                : control.State.Length > 0 ? " " + control.State : string.Empty)
            + (control.Value is { Length: > 0 } value
                ? " = " + (value.Length > 60 ? value[..60] + "…" : value)
                : string.Empty);

        static string StateOrNone(string state) => state.Length > 0 ? state : "(none)";

        static string WithoutFocus(string state) =>
            string.Join(' ', state.Split(' ', StringSplitOptions.RemoveEmptyEntries).Where(word => word != "focused"));
    }

    /// <summary>Renew al máximo (7.1): the receipt with the view after its act («after»), its own facts as they were.</summary>
    internal static ExternalCapabilityReceipt WithAfter(ExternalCapabilityReceipt receipt, JsonElement after)
    {
        if (receipt.Result is not { ValueKind: JsonValueKind.Object } result)
            return receipt;
        JsonObject node = JsonNode.Parse(result.GetRawText())!.AsObject();
        node["after"] = JsonNode.Parse(after.GetRawText());
        using JsonDocument merged = JsonDocument.Parse(node.ToJsonString());
        return receipt with { Result = merged.RootElement.Clone() };
    }

    // Renew al máximo (7.1): a click whose effect went to another window (a dialog it opened, a popup born, the list or
    // menu its manner opened, a window of another process) is not read again: the window's own tree does not show it.
    private static bool EffectElsewhere(JsonElement? result) =>
        result is { ValueKind: JsonValueKind.Object } facts
        && (facts.TryGetProperty("handedTo", out _)
            || (facts.TryGetProperty("popupBorn", out JsonElement popup) && popup.ValueKind == JsonValueKind.True)
            || (facts.TryGetProperty("dialogOpened", out JsonElement dialog) && dialog.ValueKind == JsonValueKind.True)
            || (facts.TryGetProperty("opened", out JsonElement opened) && opened.ValueKind == JsonValueKind.True));


    // The tooltip stage asks the same worker for the controls without a name and for the tooltips shown (and, TZ-DC2,
    // the messaging clients' probe, WindowsExternalCapabilityProvider).
    internal WindowsVisibleControlAdapter(UiaWorkerHost worker)
        : this(
            worker,
            new WindowsVisibleOcrLocator(),
            new WindowsVisibleVisionLocator(),
            new OpenedApplicationFocus(),
            VisibleClickTiming.Default,
            surfaceHash: WindowSurfaceHashAsync,
            tooltip: new WindowsVisibleTooltipLocator(worker))
    {
        RootWindows = VisibleControlSurface.RootWindowsNow;
        ActRefused = VisibleControlSurface.ActRefused;
        WindowOfProcess = IsWindowOfOpened;
        BurstLease = ForegroundLease.Shared;
        ReadsAfterAct = true;
    }

    /// <summary>The product's <see cref="WindowOfProcess"/> (FT/proveedores goal (E6): the keyboard's too,
    /// <see cref="OpenedApplicationKeyboard"/>).</summary>
    internal static bool IsWindowOfOpened(nint window, VisibleControlSurface.OpenedApplication opened)
    {
        // Ronda final 24: the family of processes counts only for an application this opening launched (as
        // FrontOpenedAsync's); a reused one (the Explorer, Steam) is the parent of much the person started.
        HashSet<uint> family = opened.Launched ? VisibleControlSurface.ProcessFamily(opened) : [];
        family.Add(unchecked((uint)opened.ProcessId));
        return family.Contains(unchecked((uint)VisibleControlSurface.ViewProcess(window).ProcessId))
            || VisibleControlSurface.DrawingProcesses(window).Any(process => family.Contains(unchecked((uint)process)));
    }

    internal WindowsVisibleControlAdapter(
        IUiaWorker worker,
        IVisibleControlLocator? ocr,
        IVisibleControlLocator? vision,
        IOpenedApplicationFocus? focus = null,
        VisibleClickTiming? timing = null,
        Func<string?, CancellationToken, ValueTask<nint>>? requestedWindow = null,
        Func<nint, CancellationToken, ValueTask<string?>>? surfaceHash = null,
        IPointerFallback? pointer = null,
        Func<nint, bool?, CancellationToken, ValueTask<VisibleControlSurface.CapturedWindow?>>? capture = null,
        IVisibleControlLocator? tooltip = null,
        Func<nint, bool>? elevated = null,
        Func<nint, IReadOnlyList<nint>>? renderHosts = null,
        TimeProvider? time = null)
    {
        _worker = worker ?? throw new ArgumentNullException(nameof(worker));
        _time = time ?? TimeProvider.System;
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
        _requestedWindow = requestedWindow ?? RequestedWindowAsync;
    }

    public bool CanHandle(string operation) =>
        operation is "input.visible.click" or "input.visible.controls";

    // Renew al máximo (guarda diálogo destructivo): falsedades F013, «Sí» pressed in «Confirmar Guardar como: prueba.txt
    // ya existe. ¿Quieres reemplazarlo?» wrote over the file unasked; the policy reads only the label. A click whose label
    // is a dialog's yes (VisibleControlSurface.AffirmativeAnswer) is read before it goes: a «No» or a «Cancelar» never is.
    public bool PreflightMayRaise(string operation, JsonElement arguments) =>
        operation == "input.visible.click"
        && arguments.ValueKind == JsonValueKind.Object
        && !(arguments.TryGetProperty("search", out JsonElement search) && search.ValueKind == JsonValueKind.String
            && search.GetString()!.Trim().Length > 0)
        && arguments.TryGetProperty("label", out JsonElement label) && label.ValueKind == JsonValueKind.String
        && VisibleControlSurface.AffirmativeAnswer(label.GetString());

    /// <summary>
    /// Renew al máximo (guarda diálogo destructivo): read only. The click's window (the one it names, or the last look's,
    /// or the one in front), through the modal dialog that disables it, is a dialog whose own words ask about
    /// replacing, overwriting, deleting, discarding, not saving or losing changes, and the label is that dialog's
    /// affirmative button: the receipt says the call needs the person's yes (NeedsConfirmation). The dialog's words are
    /// those of the last look when it was of that dialog, else of a read of it bounded in time (nothing pressed, brought
    /// up or captured). Null when it is not so or cannot be read.
    /// </summary>
    public async ValueTask<ExternalCapabilityReceipt?> PreflightAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        if (!PreflightMayRaise(operation, arguments))
            return null;
        string label = arguments.GetProperty("label").GetString()!.Trim();
        nint named = arguments.TryGetProperty("window", out JsonElement window) && window.ValueKind == JsonValueKind.Number
            && window.TryGetInt64(out long handle) && handle > 0
                ? (nint)handle
                : 0;
        LastView? view;
        lock (_viewLock)
        {
            view = _lastView;
        }

        nint target = named != 0 ? named
            : view is not null && VisibleControlSurface.IsAlive(view.Hwnd) ? view.Hwnd
            : VisibleControlSurface.FrontWindow();
        return await AnswersDestructiveDialogAsync(target, label, view, cancellationToken).ConfigureAwait(false)
            ? new ExternalCapabilityReceipt(operation, false, false, null, null) { NeedsConfirmation = true }
            : null;
    }

    /// <summary>
    /// Revisión de la guarda F013 (teclas): Enter or space on the focused «Reemplazar» of «¿Reemplazar?» wrote over the
    /// file as the click F013 asks for did, unless the model declared it. Read only: the window the key goes to (the one
    /// it names, or the one in front), through the modal dialog that disables it, must be a dialog; then the control
    /// that would take the key (the worker's «focuskind», its name as a look gives it) is judged as a click on it is
    /// (<see cref="AnswersDestructiveDialogAsync"/>). A focused button that is no yes («No», «Cancelar») never asks; space
    /// on any other control toggles, types or selects, and presses nothing. Enter on any other control goes to the
    /// dialog's default button, which UI Automation does not tell, and a focus not read inside the dialog is not known:
    /// both are judged as a click on any yes of that dialog.
    /// </summary>
    public async ValueTask<bool> KeyAnswersDestructiveDialogAsync(
        nint window, string key, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        if (key is not ("enter" or "space"))
            return false;
        nint target = window != 0 ? window : VisibleControlSurface.FrontWindow();
        nint dialog = target == 0 ? 0 : VisibleControlSurface.ModalSurface(target);
        if (dialog == 0 || !VisibleControlSurface.IsDialogWindow(dialog))
            return false;

        FocusRead? focus;
        try
        {
            using JsonDocument? answer = await FocusKindAsync(dialog, cancellationToken).ConfigureAwait(false);
            focus = DeclaredTextFieldPress.Read(answer);
        }
        catch (Exception exception) when (exception is IOException or JsonException or TimeoutException
            or InvalidOperationException)
        {
            focus = null;
        }

        string? label = null;
        if (focus is { Inside: true } read && read.IsPressedByAKey)
        {
            if (!VisibleControlSurface.AffirmativeAnswer(read.Name))
                return false;
            label = read.Name.Trim();
        }
        else if (focus is { Inside: true } && key == "space")
        {
            return false;
        }

        LastView? view;
        lock (_viewLock)
        {
            view = _lastView;
        }

        return await AnswersDestructiveDialogAsync(dialog, label, view, cancellationToken).ConfigureAwait(false);
    }

    /// <summary>
    /// F013's reading, for a click and for a key: <paramref name="target"/>, through the modal dialog that disables it,
    /// is a dialog whose own words ask about replacing, overwriting, deleting, discarding, not saving or losing changes,
    /// and <paramref name="label"/> is one of its buttons (null: any of its affirmative ones). The dialog's words are
    /// those of the last look when it was of that dialog, else of a read of it bounded in time. False when it is not so
    /// or cannot be read.
    /// </summary>
    private async ValueTask<bool> AnswersDestructiveDialogAsync(
        nint target, string? label, LastView? view, CancellationToken cancellationToken)
    {
        nint dialog = target == 0 ? 0 : VisibleControlSurface.ModalSurface(target);
        if (dialog == 0 || !VisibleControlSurface.IsDialogWindow(dialog))
            return false;

        IReadOnlyList<ViewControl> controls;
        string title;
        if (view is not null && view.Hwnd == dialog)
        {
            (controls, title) = (view.Controls, view.TreeTitle);
        }
        else
        {
            JsonDocument? answer;
            try
            {
                answer = await _worker.SendAsync(
                        ViewCommand(dialog, view?.Limit ?? 60, [], tail: false, AfterReadSeconds),
                        AfterReadBudget, cancellationToken)
                    .ConfigureAwait(false);
            }
            catch (Exception exception) when (exception is IOException or JsonException or TimeoutException
                or InvalidOperationException)
            {
                return false;
            }

            if (answer is null)
                return false;
            using (answer)
            {
                if (!answer.RootElement.TryGetProperty("ok", out JsonElement ok) || ok.ValueKind != JsonValueKind.True)
                    return false;
                (controls, title) = (ParseControls(answer.RootElement), ReadString(answer.RootElement, "window"));
            }
        }

        if (title.Length == 0)
            title = VisibleControlSurface.WindowTitle(dialog);
        bool itsButton = controls.Any(control => control.Kind is not ("Text" or "Document")
            && (label is null ? VisibleControlSurface.AffirmativeAnswer(control.Name) : SameLabel(label, control.Name)));
        IEnumerable<string?> said = controls.Where(static control => control.Kind is "Text" or "Document")
            .Select(static control => (string?)control.Name)
            .Append(title);
        return itsButton && VisibleControlSurface.AsksToDestroy(said);
    }

    private long _clicks;

    /// <summary>Revision 3 of r24b (finding 3): the clicks this adapter has made (IViewedFields).</summary>
    public long Clicks => Interlocked.Read(ref _clicks);

    public async ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        if (operation == "input.visible.controls")
            return await ListAsync(arguments, cancellationToken).ConfigureAwait(false);

        ExternalCapabilityReceipt receipt;
        _pressedUnchanged = null;
        _actedWindow = 0;
        _clickRoots = null;
        // BAXY Renew cu (C11): the grid item a click names by its index, as the look called it («Encabezado de columna»).
        // Only when that index's control is the one the click goes to (ClickAsync notes it): an index the label does not
        // name, or of a look of another window, leaves the label to its cascade, which presses another control.
        _indexedType = null;

        // Revision 3 of r24b (finding 3): counted before it acts, so a focus owed to a field is void after any click.
        Interlocked.Increment(ref _clicks);
        // Ajuste c3 (E017): a common file dialog the click may confirm, read before it (CommonFileDialog).
        CommonFileDialog.Facts? fileDialog = FileDialogBefore(arguments);
        DateTime actedUtc = DateTime.UtcNow;
        try
        {
            receipt = await ClickAsync(operation, arguments, cancellationToken).ConfigureAwait(false);
            // Live on the notebook (Paint's «Guardar como», 30-10): «Guardar» by its label alone was ambiguous (another
            // element of the dialog has that name) and nothing was pressed. The dialog's own button that saves or opens
            // is known by its structure (IDOK): the same click goes to it by its identity.
            if (fileDialog is not null && receipt.ErrorCode == "visible_button_ambiguous"
                && AcceptByIdentity(fileDialog, arguments) is { } byIdentity)
                receipt = await ClickAsync(operation, byIdentity, cancellationToken).ConfigureAwait(false);
        }
        finally
        {
            _pressedUnchanged = null;
        }

        if (fileDialog is not null && _actedWindow == fileDialog.Dialog
            && (receipt.Verified || receipt.EffectObserved || receipt.EffectMayHaveOccurred)
            && PressedAccept(fileDialog, receipt.Result, arguments))
        {
            CommonFileDialog.Outcome outcome = await CommonFileDialog.AwaitAsync(fileDialog, actedUtc, cancellationToken)
                .ConfigureAwait(false);
            receipt = CommonFileDialog.Apply(receipt, fileDialog, outcome,
                Infrastructure.ModelAids.On(Infrastructure.ModelAids.SaveDialogNext));
            if (outcome.Ending == CommonFileDialog.Ending.Closed)
                return receipt;
        }

        string? clickedType = _indexedType;
        _indexedType = null;

        // BAXY Renew cu (C11): Excel in a normal window folds its ribbon groups into collapsed entries («Fuente»), and a
        // click on «Negrita» by its label found nothing, three times. The refusal says which collapsed entries the last
        // look showed: what a narrow window keeps folded may be inside one.
        // BAXY Renew cu (C11): the column header «A» pressed for «la fila 1» was told back as «la fila 1»; the receipt
        // says what the pressed item is, in the window's own words.
        if (receipt.Verified && clickedType is { Length: > 0 } && receipt.Result is { ValueKind: JsonValueKind.Object } pressedResult
            && !pressedResult.TryGetProperty("itemType", out _))
        {
            System.Text.Json.Nodes.JsonObject withType = System.Text.Json.Nodes.JsonNode.Parse(pressedResult.GetRawText())!.AsObject();
            withType["itemType"] = clickedType;
            receipt = receipt with { Result = JsonDocument.Parse(withType.ToJsonString()).RootElement.Clone() };
        }

        if (receipt.ErrorCode == "visible_button_not_found" && receipt.Result is null
            && Infrastructure.ModelAids.On(Infrastructure.ModelAids.CollapsedNext))
        {
            LastView? seen;
            lock (_viewLock)
            {
                seen = _lastView;
            }

            if (seen is not null && CollapsedHint(seen.Controls) is { } hint)
                receipt = receipt with { Result = hint };
        }

        // Renew al máximo (7.1): a completed click carries the view of its window after it, which becomes the last view.
        if (receipt.Verified && receipt.ErrorCode is null && receipt.EffectObserved && _actedWindow != 0
            && !EffectElsewhere(receipt.Result)
            && await AfterActAsync(_actedWindow, cancellationToken).ConfigureAwait(false) is { } after)
        {
            // A window of another process that came since the click (a browser it opened) left this one inactive: its
            // lost focus is the click's effect elsewhere, never «unchanged» (the model would press again).
            receipt = FocusOnly(receipt, after) is { } unchanged && !AnotherWindowCame(_clickRoots)
                ? unchanged
                : WithAfter(receipt, ListedSameWhenSurfaceChanged(receipt.Result, after));
        }

        if (receipt.Verified
            && receipt.Result is { ValueKind: JsonValueKind.Object } result
            && result.TryGetProperty("surfaceChanged", out JsonElement changed)
            && changed.ValueKind == JsonValueKind.True)
        {
            _screenChangedUtc = Now;
        }

        return RepeatedUnchanged(receipt, arguments);
    }

    /// <summary>Ajuste c3 (E017): a look's facts of a common file dialog: the folder its address shows (a path of the disk,
    /// else as shown), the name its field holds, the path they make, its button that saves or opens, and the indexes the
    /// look gave its name field and that button (UI Automation's id of a window's element is «42.» and its handle).</summary>
    internal static void WriteFileDialog(Utf8JsonWriter writer, CommonFileDialog.Facts facts, IReadOnlyList<ViewControl> controls)
    {
        int? IndexOf(nint handle) => controls.FirstOrDefault(control =>
            control.Id == "42." + handle.ToString(CultureInfo.InvariantCulture))?.Index;
        writer.WriteStartObject("fileDialog");
        if (facts.Folder is { } folder)
            writer.WriteString("folder", folder);
        else if (facts.Address is { } shown)
            writer.WriteString("shown", shown);
        if (facts.NameField != 0)
        {
            writer.WriteString("name", facts.Name ?? string.Empty);
            if (IndexOf(facts.NameField) is int nameIndex)
                writer.WriteNumber("nameIndex", nameIndex);
        }

        if (facts.Path is { } path)
            writer.WriteString("path", path);
        writer.WriteString("accept", facts.AcceptText);
        if (IndexOf(facts.Accept) is int acceptIndex)
            writer.WriteNumber("acceptIndex", acceptIndex);
        writer.WriteEndObject();
    }

    // Ajuste c3 (E017): the window the click will act in (the one it names, else the last look's, else the one in front),
    // when it is a common file dialog.
    private CommonFileDialog.Facts? FileDialogBefore(JsonElement arguments)
    {
        nint window = arguments.ValueKind == JsonValueKind.Object && arguments.TryGetProperty("window", out JsonElement named)
            && named.ValueKind == JsonValueKind.Number && named.TryGetInt64(out long handle) && handle > 0
                ? (nint)handle
                : 0;
        if (window == 0)
        {
            lock (_viewLock)
            {
                window = _lastView?.Hwnd ?? 0;
            }
        }

        return CommonFileDialog.Read(window) ?? (window == VisibleControlSurface.FrontWindow()
            ? null
            : CommonFileDialog.Read(VisibleControlSurface.FrontWindow()));
    }

    /// <summary>Ajuste c3 (E017): a click by the label of the dialog's button that saves or opens, with no index, control or
    /// manner of its own, as the same click by that button's identity (UI Automation's «42.» and its handle); null for
    /// any other click.</summary>
    internal static JsonElement? AcceptByIdentity(CommonFileDialog.Facts facts, JsonElement arguments)
    {
        if (arguments.ValueKind != JsonValueKind.Object || arguments.TryGetProperty("index", out _)
            || arguments.TryGetProperty("controlId", out _) || arguments.TryGetProperty("manner", out _)
            || arguments.TryGetProperty("search", out _)
            || !arguments.TryGetProperty("label", out JsonElement label) || label.ValueKind != JsonValueKind.String
            || !CommonFileDialog.PressedAccept(facts, null, label.GetString(), "Button"))
            return null;
        return ExternalJson.Extended(arguments, writer =>
            writer.WriteString("controlId", "42." + facts.Accept.ToString(CultureInfo.InvariantCulture)));
    }

    /// <summary>Ajuste c3 (E017): whether the click pressed the dialog's button that saves or opens: by the pressed control
    /// the receipt names, or, when the receipt names none (its post-read was lost), by the label the click asked for.</summary>
    internal static bool PressedAccept(CommonFileDialog.Facts facts, JsonElement? result, JsonElement arguments)
    {
        static string? Text(JsonElement node, string name) =>
            node.ValueKind == JsonValueKind.Object && node.TryGetProperty(name, out JsonElement value)
            && value.ValueKind == JsonValueKind.String ? value.GetString() : null;
        if (result is { ValueKind: JsonValueKind.Object } pressed
            && (Text(pressed, "controlIdentity") is not null || Text(pressed, "name") is not null))
            return CommonFileDialog.PressedAccept(facts, Text(pressed, "controlIdentity"), Text(pressed, "name"),
                Text(pressed, "kind"));
        return CommonFileDialog.PressedAccept(facts, null, Text(arguments, "label"), "Button");
    }

    // C67 (R8-NB-5): a click proved by the window's image (surfaceChanged) on a browser whose tree lists only an old
    // document came back with after «same», read as «the window did not change», and the model pressed it again. The tree
    // did not see what the image did: its view says only that the listed controls are the same («sameListed»).
    private static JsonElement ListedSameWhenSurfaceChanged(JsonElement? result, JsonElement after) =>
        result is { ValueKind: JsonValueKind.Object } facts
        && facts.TryGetProperty("surfaceChanged", out JsonElement changed) && changed.ValueKind == JsonValueKind.True
        && after.TryGetProperty("same", out JsonElement same) && same.ValueKind == JsonValueKind.True
            ? ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteBoolean("sameListed", true);
                writer.WriteEndObject();
            })
            : after;

    // Holdout v5 V5E029 (s1): «Modo de calculadora Estándar», a Text and not a button, was clicked; the window's image
    // changed only because the display lost the focus ring, and the click came back completed (surfaceChanged), so the
    // model read that it worked. A click the tree pressed whose only proof is that image («uia_surface»), with the view
    // after it differing only in the focus, changed nothing: unchanged, with that view. Null for any other receipt.
    private static ExternalCapabilityReceipt? FocusOnly(ExternalCapabilityReceipt receipt, JsonElement after)
    {
        if (receipt.Result is not { ValueKind: JsonValueKind.Object } result
            || !result.TryGetProperty("cascadeStage", out JsonElement stage) || stage.ValueKind != JsonValueKind.String
            || stage.GetString() != "uia_surface"
            || !after.TryGetProperty("focusOnly", out JsonElement focusOnly) || focusOnly.ValueKind != JsonValueKind.True)
            return null;
        ExternalCapabilityReceipt unchanged =
            ExternalJson.FailureAfterEffect(receipt.Operation, "visible_button_postread_unchanged", effectObserved: true);
        return unchanged with
        {
            Result = ExternalJson.Extended(null, writer =>
            {
                writer.WritePropertyName("after");
                after.WriteTo(writer);
            }),
        };
    }

    // Holdout v4 (en vivo: «abre la biblioteca de Steam» opened Steam without app_open's place and pressed «Biblioteca» 7
    // times, each visible_button_postread_unchanged, 50 s): the same click (its label, index, control, manner and window)
    // seen unchanged again right after the last one says how many times in a row (unchangedInARow), and from the second,
    // as a fact, that the click changed nothing that many times and, when the application of the window (the one the
    // look named, else its process) has places of its own (ApplicationPlaces), that app_open with place opens them
    // without pressing. Any other result of a click starts the count again.
    private string? _unchangedClick;
    private int _unchangedInARow;

    // The item type of the last view's control a click by index goes to (BAXY Renew cu, C11); null for any other click.
    private string? _indexedType;

    private ExternalCapabilityReceipt RepeatedUnchanged(ExternalCapabilityReceipt receipt, JsonElement arguments)
    {
        if (receipt.ErrorCode != "visible_button_postread_unchanged")
        {
            _unchangedClick = null;
            _unchangedInARow = 0;
            return receipt;
        }

        string click = ClickIdentity(arguments, _actedWindow);
        _unchangedInARow = click == _unchangedClick ? _unchangedInARow + 1 : 1;
        _unchangedClick = click;
        int times = _unchangedInARow;
        // A result that already says what comes next (alreadySelected: a control that selects, so never a text) is left
        // as it is: a key written twice would void the observation.
        if (receipt.Result is { ValueKind: JsonValueKind.Object } result && result.TryGetProperty("next", out _))
            return receipt;
        LastView? seen;
        lock (_viewLock)
        {
            seen = _lastView is { } view && (view.Hwnd == _actedWindow || _actedWindow == 0) ? view : null;
        }

        string label = arguments.ValueKind == JsonValueKind.Object && arguments.TryGetProperty("label", out JsonElement named)
            && named.ValueKind == JsonValueKind.String ? named.GetString()!.Trim() : string.Empty;
        string? textNext = seen is not null && Infrastructure.ModelAids.On(Infrastructure.ModelAids.TextClickNext)
            ? TextClickNext(seen.Controls, label, arguments) : null;
        if (times < 2 && textNext is null)
            return receipt;
        string? application = times < 2 ? null
            : seen?.Application ?? (_actedWindow != 0 ? VisibleControlSurface.ViewProcess(_actedWindow).ProcessName : null);
        return receipt with
        {
            Result = ExternalJson.Extended(receipt.Result, writer =>
            {
                // The count goes with every «next» it brings, the first one's on a text too, so the same call's
                // comparisons (mind.py _result_key, TurnClosing), which leave out both, see the first click as today.
                writer.WriteNumber("unchangedInARow", times);
                string? repeated = times >= 2 && Infrastructure.ModelAids.On(Infrastructure.ModelAids.RepeatedUnchangedNext)
                    ? RepeatedUnchangedNext(label, times, application) : null;
                string? next = repeated is null ? textNext : textNext is null ? repeated : repeated + "; " + textNext;
                if (next is not null)
                    writer.WriteString("next", next);
            }),
        };
    }

    // Práctica V5E029 («cambia la calculadora a modo científico»: «Modo de calculadora Estándar», a Text, clicked 3 times,
    // unchanged each time, while «Abrir navegación», beside it, opens the list of modes; never tried): the click the last
    // look named (by index, identity, else label) is a static text (kind Text, with no state of a control that toggles,
    // selects or opens), so the receipt says so and names, from that look, the controls nearest it (a collapsed one
    // marked), or the window's collapsed entries when the text has no place. Null for anything else.
    internal static string? TextClickNext(IReadOnlyList<ViewControl> controls, string label, JsonElement arguments)
    {
        bool given = arguments.ValueKind == JsonValueKind.Object;
        ViewControl[] named = given && arguments.TryGetProperty("index", out JsonElement index)
            && index.ValueKind == JsonValueKind.Number && index.TryGetInt32(out int at)
                ? [.. controls.Where(control => control.Index == at)]
            : given && arguments.TryGetProperty("controlId", out JsonElement identity)
                && identity.ValueKind == JsonValueKind.String && identity.GetString()!.Trim() is { Length: > 0 } id
                ? [.. controls.Where(control => control.Id == id)]
            : [.. controls.Where(control => SameLabel(label, control.Name))];
        if (named.Length == 0 || !named.All(static control => control.Kind == "Text"
                && !control.State.Split(' ').Any(static part => part is "on" or "off" or "selected" or "expanded" or "collapsed")))
            return null;
        ViewControl text = named[0];
        string said = $"«{text.Name}» is a text the window shows, not a control: clicking it changes nothing";
        string Entry(ViewControl control) => $"[{control.Index}] {control.Kind} «{control.Name}»"
            + (Folded(control) ? " (collapsed)" : string.Empty);
        if (text.RectValue is not { } box)
        {
            ViewControl[] folded = [.. controls.Where(Folded).Take(TextClickLimit)];
            return folded.Length == 0 ? said : said + "; the window's collapsed entries are " + string.Join(", ", folded.Select(Entry));
        }

        static long Gap(Rect a, Rect b)
        {
            long dx = Math.Max(0, Math.Max(a.X - (b.X + b.W), b.X - (a.X + a.W)));
            long dy = Math.Max(0, Math.Max(a.Y - (b.Y + b.H), b.Y - (a.Y + a.H)));
            return dx * dx + dy * dy;
        }

        ViewControl[] nearest = [.. controls
            .Where(static control => PressesOrOpens(control) && control.RectValue is not null)
            .OrderBy(control => Gap(box, control.RectValue!.Value))
            .ThenBy(static control => control.Index)
            .Take(TextClickLimit)];
        return nearest.Length == 0 ? said : said + "; the controls nearest it are " + string.Join(", ", nearest.Select(Entry));
    }

    internal const int TextClickLimit = 3;

    // The click as the model asked for it: the same label, index, control, manner and window (the one acted on when the
    // call named none).
    internal static string ClickIdentity(JsonElement arguments, nint actedWindow)
    {
        string Part(string name) => arguments.ValueKind == JsonValueKind.Object
            && arguments.TryGetProperty(name, out JsonElement value) && value.ValueKind != JsonValueKind.Null
                ? value.ToString().Trim().ToLowerInvariant() : string.Empty;
        string window = Part("window");
        return string.Join(" | ", Part("label"), Part("index"), Part("controlId"), Part("manner"), Part("choose"),
            Part("search"), window.Length > 0 ? window : actedWindow.ToString(System.Globalization.CultureInfo.InvariantCulture));
    }

    internal static string RepeatedUnchangedNext(string label, int times, string? application)
    {
        string said = $"this click on «{label}» changed nothing {times} times in a row: each time the window looked the "
            + "same after it as before it";
        IReadOnlyList<(string Place, string? Takes)> places = ApplicationPlaces.PlacesOf(application);
        if (places.Count == 0)
            return said;
        string squeezed = new([.. label.ToLowerInvariant().Where(char.IsLetterOrDigit)]);
        IEnumerable<(string Place, string? Takes)> ordered = places
            .OrderBy(place => place.Place == squeezed ? 0 : 1)
            .ThenBy(place => place.Place, StringComparer.Ordinal);
        string listed = string.Join(", ", ordered.Select(place => place.Takes is null
            ? $"\"{place.Place}\"" : $"\"{place.Place}\" (placeValue: the {place.Takes})"));
        return said + $"; {application} opens straight at its places without pressing: app_open with appId "
            + $"\"{application}\" and place {listed}";
    }

    private async ValueTask<ExternalCapabilityReceipt> ClickAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        string label;
        int? index = null;
        string? controlId = null;
        nint namedWindow = 0;
        string? search;
        string? choose;
        string? manner;
        try
        {
            label = ExternalJson.RequiredString(arguments, "label").Trim();
            search = OptionalText(arguments, "search");
            choose = OptionalText(arguments, "choose");
            manner = OptionalText(arguments, "manner");
            if (manner is not (null or "double" or "menu" or "open"))
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
                // Prueba en vivo de la versión final (renew_v6, «abre Paint»): the model wrote the look's index in
                // controlId («0» for [0] «Archivo»). No look or click gives a bare number as an identity (the tree's
                // runtime id is dotted, «42.1234»; the others say their kind, «hmenu.», «hwnd.», «ocr.»), so the worker
                // answered visible_control_identity_stale twice, a cause nothing showed, and the person was told one
                // nobody saw. A bare number there is the look's index: read as the index when the click gives none, with
                // the index's own guard below (the label must name that control).
                if (controlId.All(char.IsAsciiDigit))
                {
                    if (index is null && int.TryParse(controlId, NumberStyles.None, CultureInfo.InvariantCulture, out int written))
                        index = written;
                    controlId = null;
                }
            }

            // The window the click names: the hwnd of the view it was decided on (v3 point 0 review).
            if (arguments.TryGetProperty("window", out JsonElement named) && named.ValueKind != JsonValueKind.Null)
            {
                if (named.ValueKind != JsonValueKind.Number || !named.TryGetInt64(out long handle) || handle <= 0)
                    throw new InvalidDataException("window");
                namedWindow = (nint)handle;
            }
        }
        catch (InvalidDataException)
        {
            return ExternalJson.FailureBeforeEffect(operation, "visible_click_argument_invalid");
        }

        // The engine clicks by the identity the last view kept for the index. The
        // index is resolved against that view, and the label must name the
        // same control: an index that drifted is refused, never clicked.
        if (index is int position && controlId is null)
        {
            LastView? view;
            lock (_viewLock)
            {
                view = _lastView;
            }

            // Renew al máximo (B-CU-1): an index is of the last view's window; with the click naming another one it is
            // not that window's control (it was pressed in the window looked at before, behind the named one).
            ViewControl? chosen = view is not null && (namedWindow == 0 || view.Hwnd == namedWindow)
                ? view.Controls.FirstOrDefault(control => control.Index == position)
                : null;
            if (chosen is not null && SameLabel(label, chosen.Name))
            {
                controlId = chosen.Id.Length > 0 ? chosen.Id : null;
                _indexedType = chosen.ItemType;
            }
            else
            {
                // Uso real 2026-10-21 (notebook e2e): the model gave an index the view did not have (Epic's view held no
                // control, only written lines) or one that named another control (Steam's «Chrome Legacy Window» at 0
                // for «Buscar en la tienda»), and the click ended there five and seven times while the label was on
                // screen. The index's control is never pressed (auditoría P3); the label is looked for by its ordinary
                // cascade, bound to the window the click names or the last view's, never to whatever is in front. With
                // no such window the click is refused as before.
                nint known = namedWindow != 0 ? namedWindow
                    : view is not null && VisibleControlSurface.IsAlive(view.Hwnd) ? view.Hwnd : 0;
                if (known == 0)
                {
                    // BAXY Renew cu (C03): with no window to look in, the refusal says what the last look held at that
                    // index and how a text it read is pressed (Steam's page gave one control and its words only as text).
                    if (chosen is null)
                        return view is not null && view.Controls.Count > 0
                            && Infrastructure.ModelAids.On(Infrastructure.ModelAids.IndexLabelNext)
                            ? new ExternalCapabilityReceipt(operation, false, false, ExternalJson.Create(writer =>
                            {
                                writer.WriteStartObject();
                                writer.WriteString("next", $"nothing was pressed: your last look listed no control [{position}] "
                                    + $"(its controls go from [0] to [{view.Controls.Max(control => control.Index)}]); a text it read "
                                    + "that is not in its list of controls is clicked by its label alone, without index");
                                writer.WriteEndObject();
                            }), "visible_control_identity_stale")
                            : ExternalJson.FailureBeforeEffect(operation, "visible_control_identity_stale");
                    return NotNamed(operation, "visible_control_label_mismatch", [chosen.Name],
                        next: Infrastructure.ModelAids.On(Infrastructure.ModelAids.IndexLabelNext)
                            ? $"nothing was pressed: index {position} is «{chosen.Name}», not «{label}»; a text your look read "
                                + "that is not in its list of controls is clicked by its label alone, without index"
                            : null);
                }

                namedWindow = known;
                index = null;
            }
        }

        // Ronda 20 (P7): the opener the previous click noted is taken before any branch, so every click right after it
        // (by identity, by its manner, by a label of the last view) may reopen what it showed, and any other click takes it
        // away. A click by a label alone right after an opener presses the one control of the named window's last view
        // that the label names by its identity, so an item of the opening that closed is answered stale and reopened,
        // never looked for by a cascade on a closed menu. It names it by its exact name (NamedInView), never a sentence
        // that merely mentions it, and a press of that identity that failed before any effect leaves the label to its
        // cascade (revision 1 of the branch).
        (nint Window, string Id, string Label, HashSet<string> NamesBefore, string? Manner)? opener = TakeOpener();
        bool namedByLabel = false;
        if (controlId is null && index is null && search is null && manner is null && opener is not null)
        {
            controlId = NamedInView(namedWindow, label);
            namedByLabel = controlId is not null;
        }

        if (search is not null)
            return await SearchInBurstAsync(operation, label, controlId, namedWindow, search, choose, cancellationToken)
                .ConfigureAwait(false);

        // Goal v3 B3: a control opened by its arrow, its context menu or a double click is pressed only by its identity
        // (its index's in the last view, or a controlId), through the accessible tree or a message, never by the
        // pointer nor by the label's cascade (OCR, vision): a press found that way would be the ordinary click the
        // manner exists to avoid (the split button's Invoke opened another tab, v3-37). A control that moved since
        // the view is not pressed.
        if (manner is not null)
        {
            // BAXY Renew cu (C11): «Fuente» opened by its manner with no index answered stale three times, though the last
            // look showed exactly one control of that name: the identity is that control's (by its exact name only,
            // never a sentence that mentions it), as a label alone after an opener takes it.
            if (controlId is null && index is null && search is null)
            {
                nint mannerWindow;
                lock (_viewLock)
                {
                    mannerWindow = namedWindow != 0 ? namedWindow : _lastView?.Hwnd ?? 0;
                }

                controlId = NamedInView(mannerWindow, label);
            }

            if (search is not null || controlId is null)
                return ExternalJson.FailureBeforeEffect(operation, "visible_control_identity_stale");
            HashSet<string>? shownBefore = ChainedNames(opener, namedWindow, controlId, ViewNames(namedWindow));
            ExternalCapabilityReceipt pressed = await InvokeUiaAsync(operation, label, controlId, namedWindow, cancellationToken, manner)
                .ConfigureAwait(false);
            // Ronda 20 (P7, v3-09): an item the opener showed (a collapsed ribbon's gallery) that the act's manner (its
            // arrow) found closed: the opener and the item, in that manner, go in one burst of the lease.
            if (await ReopenShownAsync(operation, opener, pressed, label, controlId, namedWindow, manner, cancellationToken)
                    .ConfigureAwait(false) is { } reopenedInManner)
                return reopenedInManner;
            // An arrow or a context menu opens a list or a menu by definition: noted as the opener of what it showed,
            // with its manner, so the burst that reopens it presses its arrow again, never its own action (v3-37).
            if (pressed.Verified && pressed.ErrorCode is null)
                NoteOpenerIn(namedWindow, controlId, label, shownBefore, manner is "open" or "menu", manner);
            return pressed;
        }

        // The window of the view the identity came from. The click by identity no longer brings it forward, so when
        // the identity went stale the cascade by label stays on that window: never on whatever the person has in
        // front meanwhile (their editor, a chat), where its label would be looked for, read and pressed. A click that
        // names its window (v3 point 0 review, «window») stays on that one. Neither is brought to the
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
            HashSet<string>? namesBefore = ChainedNames(opener, namedWindow, controlId, ViewNames(namedWindow));
            bool opens = OpensAgain(namedWindow, controlId);
            ExternalCapabilityReceipt identified = await InvokeUiaAsync(
                operation, label, controlId, namedWindow, cancellationToken).ConfigureAwait(false);
            if (await ReopenShownAsync(operation, opener, identified, label, controlId, namedWindow, null, cancellationToken)
                    .ConfigureAwait(false) is { } reopened)
                return reopened;

            if (identified.Verified && identified.ErrorCode is null)
                NoteOpener(namedWindow, controlId, label, namesBefore, opens);
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
        // Ronda final 22 (regla 3): a click that names a window of another process than the application just opened
        // («abre Spotify», then «en Chrome pulsa Aceptar» with Chrome's window) acts in the window it names, never in
        // the opened one.
        // Ronda final 23: the same for a click by index without a window, whose identity went stale: the window of the
        // last look, not the opened application, when that look was of another process.
        nint askedWindow = namedWindow != 0 ? namedWindow : viewWindow;
        if (opened is { } openedNow && askedWindow != 0 && WindowOfProcess is { } ofProcess
            && !ofProcess(askedWindow, openedNow))
            opened = null;
        if (opened is { } seenOpening && _openedLooked is { } looked
            && looked.Shows(seenOpening, namedWindow, label))
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
        bool afterScreenChange = Now - _screenChangedUtc < ScreenChangeFreshness;
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
        DateTime cap = (settled > Now ? settled : Now) + labelBudget;
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
                bool settling = Now < settled;
                look = surface.Window != 0 && (surface.Drawn || !settling);
                if (!look && !settling && lookingSince is null)
                    break;
                if (Now >= cap)
                {
                    if (await HoverOnceAsync().ConfigureAwait(false) is { } capped)
                        return capped;
                    break;
                }
            }

            if (look)
            {
                lookingSince ??= Now;
                // Bound to the opened application's window, to the window the click names or to the window of the view
                // whose identity went stale: nothing is read or pressed on whatever else holds the front (the person
                // took it). The accessible tree reaches the bound window behind; OCR and vision read its own image
                // and press through the tree at the point, or with the pointer only inside a burst of the lease.
                nint boundWindow = opened is not null ? surfaceWindow : namedWindow != 0 ? namedWindow : viewWindow;
                using IDisposable bound = VisibleControlSurface.RequireWindow(boundWindow);
                _lookedTreeSize = -1;
                _stillSince = null;
                uia = await InvokeUiaAsync(operation, label, null, boundWindow, cancellationToken)
                    .ConfigureAwait(false);
                if (ShouldKeep(uia))
                    return uia;
                // An administrator's window refuses every stage alike (UIPI): no OCR, tooltip or vision is tried on it.
                if (uia.ErrorCode is WindowElevated or WindowElevationUnread or NeedsConfirmation)
                    return uia;
                // Ronda B (falta 1) and ronda final 18 (regla 3): any failure of a press that may have acted (no
                // receipt, an unreadable one, a raise once sent, a read-back not read, the person's touch, no answer to
                // the post-read) ends the click with that press: no later stage presses again. Only a press seen
                // unchanged goes on, to a stage that never presses that same control (below).
                if ((uia.EffectMayHaveOccurred || uia.EffectObserved)
                    && uia.ErrorCode != "visible_button_postread_unchanged")
                    return uia;
                // lat-apertura-clic (r13a), review of the branch (finding 4): the tree found the control and pressed it,
                // and its post-read saw nothing change. A later stage still looks for the label (the tree may have
                // pressed a hidden duplicate of the visible control, or an Invoke the application accepted and
                // ignored, rescued since 956a89ace), but none presses that same control again (a second press undoes
                // a toggle, sends twice): the worker refuses a point on it before any effect, and the click answers
                // with the tree's own press, without the stage's post-read. The post-read noted the control's identity
                // (_pressedUnchanged, in PostreadAsync).

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
                // click is bound to only (never whatever the person has in front), in pauses of the person, and
                // only on the last look: a page still drawing (UI1731: the navigation ten seconds after the window)
                // shows its label to a later look first, and its controls are not hovered half drawn. On a look made
                // when the label's wait is already over, before vision.
                hoverWindow = boundWindow;
                if (Now >= lookingSince.Value + labelBudget
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
            if (lookingSince is { } since && Now >= since + labelBudget)
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
                && lookingSince is { } lookedFor && Now >= lookedFor + _timing.SettledLabel)
            {
                int tree = _lookedTreeSize;
                bool built = tree >= _timing.InterfaceUp && previousTree >= 0 && tree <= previousTree;
                previousTree = tree;
                if (built)
                {
                    nint watched = _lookedWindow;
                    if (await StaysStillAsync(token => _surfaceHash(watched, token), StillSeen(watched, uia), cancellationToken)
                        .ConfigureAwait(false))
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
                if (await StaysStillAsync(token => _surfaceHash(watched, token), StillSeen(watched, uia), cancellationToken)
                    .ConfigureAwait(false))
                {
                    if (await HoverOnceAsync().ConfigureAwait(false) is { } still)
                        return still;
                    break;
                }

                continue;
            }
            await Task.Delay(_timing.Interval, _time, cancellationToken).ConfigureAwait(false);
        }

        // Nothing looked at means nothing pressed: no window of the opened application ever showed (ronda final 18:
        // said so, never «no such button», which was never looked for).
        if (uia is null)
            return ExternalJson.FailureBeforeEffect(operation, "visible_opened_window_not_shown");
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
        // Ronda final 19 (regla 3): so is any other answer of a later stage that pressed nothing and ends the click (a
        // refusal, a person not paused, a vision request failed): the tree's press stands, never «nothing pressed».
        ExternalCapabilityReceipt? PressedAgain(ExternalCapabilityReceipt? stage) =>
            uia is { EffectObserved: true } pressed
            && stage is { Verified: false, EffectObserved: false, EffectMayHaveOccurred: false }
            && (stage.ErrorCode == PointAlreadyPressed || !ShouldCascade(stage))
                ? pressed
                : stage;
    }

    // Watches the window in front for up to Interval: true when it stayed exactly the same for StillFor, false as soon
    // as it changes, when it cannot be captured (then the whole interval is waited, as before) or at the interval.
    // An image the probe of the look's own press found still (seen) that the window still shows counts from that probe:
    // e2e c3-final4/5 dv6, a label not found in Configuración took 2.0 s, of it the probe's 600 ms of the same image and
    // then the 750 ms of StillFor watched again from zero.
    private async ValueTask<bool> StaysStillAsync(
        Func<CancellationToken, ValueTask<string?>> surfaceHash,
        (string Sha256, long At)? seen,
        CancellationToken cancellationToken)
    {
        long watch = _time.GetTimestamp();
        string? first = await surfaceHash(cancellationToken).ConfigureAwait(false);
        if (first is null)
        {
            TimeSpan rest = _timing.Interval - _time.GetElapsedTime(watch);
            if (rest > TimeSpan.Zero)
                await Task.Delay(rest, _time, cancellationToken).ConfigureAwait(false);
            return false;
        }

        long still = seen is { } probe && string.Equals(probe.Sha256, first, StringComparison.Ordinal)
            ? probe.At
            : _time.GetTimestamp();
        if (_time.GetElapsedTime(still) >= _timing.StillFor)
            return true;
        while (_time.GetElapsedTime(watch) < _timing.Interval)
        {
            await Task.Delay(_timing.StillSample, _time, cancellationToken).ConfigureAwait(false);
            string? now = await surfaceHash(cancellationToken).ConfigureAwait(false);
            if (now is null || !string.Equals(now, first, StringComparison.Ordinal))
                return false;
            if (_time.GetElapsedTime(still) >= _timing.StillFor)
                return true;
        }

        return false;
    }

    // The still image the look's press probed on that window, when the look pressed nothing (a press seen unchanged
    // may have moved the window between the probe and now).
    private (string Sha256, long At)? StillSeen(nint window, ExternalCapabilityReceipt? look) =>
        look is { EffectObserved: false, EffectMayHaveOccurred: false } && _stillSince is { } seen && seen.Window == window
            ? (seen.Sha256, seen.At)
            : null;

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

    private async ValueTask<ExternalCapabilityReceipt> ListAsync(
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        int limit = 60;
        bool includeText = false;
        string? waitForLabel = null;
        string? application = null;
        bool tail = false;
        bool lines = false;
        IReadOnlyList<string> wanted = [];
        if (arguments.ValueKind == JsonValueKind.Object)
        {
            wanted = WantedWords(arguments);
            if (arguments.TryGetProperty("application", out JsonElement named)
                && named.ValueKind == JsonValueKind.String
                && !string.IsNullOrWhiteSpace(named.GetString()))
            {
                application = named.GetString()!.Trim();
            }

            if (arguments.TryGetProperty("limit", out JsonElement requested)
                && requested.ValueKind == JsonValueKind.Number
                && requested.TryGetInt32(out int value))
            {
                limit = Math.Clamp(value, 1, 60);
            }

            includeText = arguments.TryGetProperty("includeText", out JsonElement wantsText)
                && wantsText.ValueKind == JsonValueKind.True;
            tail = arguments.TryGetProperty("tail", out JsonElement tailValue) && tailValue.ValueKind == JsonValueKind.True;
            lines = arguments.TryGetProperty("lines", out JsonElement linesValue) && linesValue.ValueKind == JsonValueKind.True;
            includeText |= lines;
            if (arguments.TryGetProperty("waitForLabel", out JsonElement waited)
                && waited.ValueKind == JsonValueKind.String
                && !string.IsNullOrWhiteSpace(waited.GetString()))
            {
                waitForLabel = waited.GetString()!.Trim();
            }
        }

        // M132: a look right after an opening reads the application opened, not what was in front before it. It is not
        // brought to the front (v3 point 0): the accessible tree and the window's own image are read behind the
        // person's window.
        nint openedWindow = 0;
        if (_focus.PeekOpened() is { } opened)
        {
            openedWindow = (await _focus.FrontAsync(opened, judgeDrawn: false, cancellationToken)
                .ConfigureAwait(false)).Window;
        }

        DateTime deadline = DateTime.UtcNow + LabelWaitBudget;
        while (true)
        {
            ViewResult view = await BuildViewAsync(
                    limit, includeText, application, openedWindow, wanted, tail, lines, cancellationToken)
                .ConfigureAwait(false);
            if (view.Receipt.ErrorCode is not null)
                return view.Receipt;
            // A walk that did not end is not waited on again: each look may take the worker's budget once more.
            if (waitForLabel is null || view.Unfinished || view.Names.Any(name => SameLabel(waitForLabel, name))
                || DateTime.UtcNow >= deadline)
            {
                NoteOpenedLooked(view.Receipt, view.Names);
                return view.Receipt;
            }

            await Task.Delay(LabelWaitInterval, cancellationToken).ConfigureAwait(false);
        }
    }

    // lat-apertura-clic (r13a: Epic 27.3 s on a click by label, its view of 0 controls): the opening a look read the
    // window of (its process, or one of the processes that draw it). The look read that window already: the click
    // decided on that look does not wait for the application to finish opening again.
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

    internal void NoteOpenedLooked(ExternalCapabilityReceipt receipt, IReadOnlyList<string> names)
    {
        if (_focus.PeekOpened() is not { } opened
            || receipt.Result is not { ValueKind: JsonValueKind.Object } result
            || !result.TryGetProperty("window", out JsonElement window)
            || window.ValueKind != JsonValueKind.Object
            || !window.TryGetProperty("hwnd", out JsonElement handle) || !handle.TryGetInt64(out long hwnd) || hwnd <= 0)
            return;
        bool ofIt = (window.TryGetProperty("processId", out JsonElement owner) && owner.ValueKind == JsonValueKind.Number
                && owner.TryGetInt32(out int ownerId) && ownerId == opened.ProcessId)
            || (window.TryGetProperty("family", out JsonElement family) && family.ValueKind == JsonValueKind.Array
                && family.EnumerateArray().Any(member => member.ValueKind == JsonValueKind.Number
                    && member.TryGetInt64(out long id) && id == opened.ProcessId));
        if (ofIt)
            _openedLooked = new OpenedLook(opened.ProcessId, opened.NotedUtc, (nint)hwnd, [.. names]);
    }

    /// <summary>Ronda 21: the words of what is looked for that a look carries («wanted», declared in the catalog), at
    /// most 24 non-empty texts of at most 64 characters; anything else is no word.</summary>
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

    /// <summary>The reason a look whose walk did not end gives the model («uiaFailed»).</summary>
    internal const string UnfinishedWalkReason = "la lectura del árbol accesible no terminó en su plazo";

    /// <summary>Whether a worker that answered nothing (<paramref name="asked"/> the timestamp the walk was asked at) spent
    /// <see cref="WorkerViewBudget"/> on it: a slow walk, not a worker missing or broken (those answer nothing at once).
    /// The budget's timer is allowed a second of slack.</summary>
    internal static bool PastWalkBudget(long asked) =>
        Stopwatch.GetElapsedTime(asked) >= WorkerViewBudget - TimeSpan.FromSeconds(1);

    /// <summary>P2.17: the answer a look goes on with when the worker did not answer its walk within
    /// <see cref="WorkerViewBudget"/> (a slow tree; the worker was ended) on a window that is still there
    /// (<paramref name="alive"/>): as <see cref="WithoutTree"/>, read from what it draws, and «partial». Null for a window
    /// that is gone (its look fails as before).</summary>
    internal static JsonDocument? UnfinishedWalk(nint window, Func<nint, bool> alive) =>
        alive(window)
            ? JsonDocument.Parse(new JsonObject
            {
                ["ok"] = true, ["controls"] = new JsonArray(), ["partial"] = true, ["uiaFailed"] = UnfinishedWalkReason,
            }.ToJsonString())
            : null;

    // The window of the application a look names (exactly: VisibleControlSurface.ResolveTitledWindowAsync); 0 when none
    // shows one.
    private static async ValueTask<nint> RequestedWindowAsync(string? application, CancellationToken cancellationToken) =>
        application is null
            ? 0
            : await VisibleControlSurface.ResolveTitledWindowAsync(application, cancellationToken).ConfigureAwait(false);

    /// <summary>A tree read with at most this many controls may still be being built (PLAN_GENERAL A2).</summary>
    internal const int SleepingTreeControls = 3;

    internal const int TreeSettleIntervalMs = 400;

    internal const int TreeSettleReads = 5;

    /// <summary>
    /// PLAN_GENERAL A2: a tree that read almost empty is read again after a pause; while each read counts more controls
    /// than the last, the newest is kept and read again; the first read that does not grow ends it (a tree that never
    /// comes costs one pause). Whether the tree grew, and the answer kept.
    /// </summary>
    internal static async Task<(JsonDocument Answer, bool Woken)> SettleTreeAsync(
        JsonDocument first, Func<Task<JsonDocument?>> read, Func<int, Task> delay)
    {
        int count = ControlCount(first);
        if (count < 0 || count > SleepingTreeControls)
            return (first, false);
        JsonDocument current = first;
        bool grew = false;
        for (int attempt = 0; attempt < TreeSettleReads; attempt++)
        {
            await delay(TreeSettleIntervalMs).ConfigureAwait(false);
            JsonDocument? again = await read().ConfigureAwait(false);
            if (again is null)
                break;
            int next = ControlCount(again);
            if (next <= count)
            {
                again.Dispose();
                break;
            }

            current.Dispose();
            current = again;
            count = next;
            grew = true;
        }

        return (current, grew);
    }

    // The controls a worker's view counted; -1 when the view did not succeed.
    private static int ControlCount(JsonDocument view)
    {
        JsonElement root = view.RootElement;
        if (root.ValueKind != JsonValueKind.Object || !root.TryGetProperty("ok", out JsonElement ok)
            || ok.ValueKind != JsonValueKind.True)
            return -1;
        if (root.TryGetProperty("controlCount", out JsonElement total) && total.TryGetInt32(out int counted))
            return counted;
        return root.TryGetProperty("controls", out JsonElement list) && list.ValueKind == JsonValueKind.Array
            ? list.GetArrayLength()
            : 0;
    }

    /// <summary>How many of the desktop's windows go back with a name no window is.</summary>
    internal const int NamedWindowCandidateLimit = 20;

    /// <summary>
    /// Auditoría final V3: the named application is no window on the desktop. Nothing was read nor done; the visible
    /// windows (title and process, top of the Z order first, cloaked ones left out) go back for the model to name one
    /// exactly.
    /// </summary>
    internal static ExternalCapabilityReceipt NamedWindowNotFound(
        string operation, IReadOnlyList<VisibleControlSurface.DestinationWindow> desktop) =>
        new(operation, false, false, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            // Ronda final 19 (regla 3): how many windows there are, the first ones listed.
            int count = desktop.Count;
            writer.WriteNumber("candidateCount", count);
            if (count > NamedWindowCandidateLimit)
                writer.WriteBoolean("truncated", true);
            writer.WriteStartArray("candidates");
            foreach (VisibleControlSurface.DestinationWindow window in desktop.Take(NamedWindowCandidateLimit))
            {
                writer.WriteStartObject();
                writer.WriteString("title", window.Title);
                writer.WriteString("process", window.Process);
                writer.WriteEndObject();
            }

            writer.WriteEndArray();
            writer.WriteEndObject();
        }), "application_window_not_found");

    /// <summary>The worker's «view» request; the words looked for go only when the look carries some (without them the
    /// view is the usual one).</summary>
    internal static string ViewCommand(
        nint hwnd, int limit, IReadOnlyList<string>? wanted, bool tail = false, double? seconds = null)
    {
        var command = new JsonObject { ["cmd"] = "view", ["hwnd"] = hwnd, ["limit"] = limit };
        // Renew al máximo (7.1): the read after an act walks the tree within its own deadline.
        if (seconds is double walk)
            command["seconds"] = walk;
        if (tail)
        {
            // Encargo IMP3: the cut keeps the last entries of the tree (what the window drew last), not the first.
            command["tail"] = true;
        }

        if (wanted is { Count: > 0 })
        {
            command["wanted"] = new JsonArray([.. wanted.Select(static word => (JsonNode?)JsonValue.Create(word))]);
        }

        // Aid caret_place off: the worker reads no caret (revisión de nb-w11-cursor: it read it on every look).
        if (!Infrastructure.ModelAids.On(Infrastructure.ModelAids.CaretPlace))
            command["caret"] = false;
        return command.ToJsonString();
    }

    private async ValueTask<ViewResult> BuildViewAsync(
        int limit,
        bool includeText,
        string? application,
        nint openedWindow,
        IReadOnlyList<string> wanted,
        bool tail,
        bool lines,
        CancellationToken cancellationToken)
    {
        const string operation = "input.visible.controls";
        var stopwatch = Stopwatch.StartNew();
        nint hwnd = 0;
        nint cover = 0;
        // Encargo EX: the window was read through the modal dialog that disabled it (ModalSurface).
        bool modal = false;
        bool shownBehind = false;
        // The top-level window the look is of, before its modal dialog is taken.
        nint windowRoot = 0;
        try
        {
            // The application the look names is the surface even when another
            // window holds the foreground.
            hwnd = await _requestedWindow(application, cancellationToken).ConfigureAwait(false);

            // The application just opened, where it is (behind the person's window, as it was opened).
            if (hwnd == 0 && openedWindow != 0 && VisibleControlSurface.IsAlive(openedWindow))
                hwnd = openedWindow;
            // Auditoría final V3: an application named that no window is, exactly, is never read in another window's
            // place (the person's in front): the visible windows go back as candidates and nothing is looked at.
            if (hwnd == 0 && application is not null)
                return new ViewResult(NamedWindowNotFound(operation, VisibleControlSurface.DestinationDesktop()), []);
            if (hwnd == 0)
            {
                hwnd = await WindowInFront(cancellationToken)
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
                // Ajuste c3 (E017, live: Chrome draws its «Guardar como» from another of its processes): the common file
                // dialog the window owns is seen as its modal dialog, whatever process draws it.
                if (!modal && CommonFileDialog.OwnedBy(hwnd) is var ownedDialog and not 0)
                {
                    hwnd = ownedDialog;
                    modal = true;
                }
                // A minimized window is shown behind the person's own before its tree is read (it shrinks while
                // minimized) and before it is captured.
                shownBehind = VisibleControlSurface.ShowBehind(hwnd);
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
        // The capture serves the written text, asked for or read when the tree shows nothing to act on;
        // a window without an accessible tree (CEF, SDL, canvas) is
        // read from what is drawn, the case measured in a game launcher (UI1731).
        // The capture, and the text when it is asked for, are read while the
        // worker walks the accessible tree: they do not wait on each other.
        // A window another process draws over is captured as it draws itself, never the screen where the cover is.
        // Encargo IMP4: the written lines a look asks for («lines») are read from the window's own drawing, never from
        // the screen (imp3: the screen copy of a chat client covered by another window read the other window's text).
        bool covered = cover != 0 || lines;
        nint firstLooked = hwnd;
        Task<VisibleControlSurface.CapturedWindow?> captureTask =
            Task.Run(() => CaptureQuietlyAsync(firstLooked, covered, cancellationToken), CancellationToken.None);
        Task<WrittenText>? textTask = includeText ? ReadTextAsync(captureTask, lines ? PlacedLinesRead : limit, cancellationToken, placed: lines) : null;
        long asked = Stopwatch.GetTimestamp();
        JsonDocument? answer = await _worker.SendAsync(command, WorkerViewBudget, cancellationToken).ConfigureAwait(false);
        bool unfinished = answer is null && PastWalkBudget(asked);
        if (unfinished)
            answer = UnfinishedWalk(hwnd, VisibleControlSurface.IsAlive);
        if (answer is null)
        {
            return new ViewResult(ExternalJson.Failure(operation, "visible_controls_unavailable"), []);
        }

        // Ronda 20 P6 (v3-15, v3-16, v3-17): an application's window whose tree is only its caption parts (title bar,
        // caption buttons, the non-client input, a busy indicator) over the content window a process it started draws
        // under it (measured: a WinUI frame activated by a click lay above its WebView2 editor, and the view kept the
        // caption parts while the person saw the editor) is read through that content window, linked to it as the
        // family surface over it is: the look's root stays the application's window.
        if (!unfinished && hwnd == windowRoot && VisibleControlSurface.SurfaceFamily(hwnd) is null
            && answer.RootElement.TryGetProperty("ok", out JsonElement frameOk) && frameOk.ValueKind == JsonValueKind.True
            && VisibleControlSurface.TryBounds(hwnd, out int frameLeft, out int frameTop, out int frameRight, out int frameBottom))
        {
            var frame = (frameLeft, frameTop, frameRight, frameBottom);
            var frameControls = CaptionReading(answer.RootElement);
            if (VisibleControlSurface.MayShowOnlyCaption(frame, frameControls))
            {
                nint content = VisibleControlSurface.TakeContentWindow(
                    hwnd, box => VisibleControlSurface.ShowsOnlyCaption(frame, box, frameControls));
                if (content != 0)
                {
                    answer.Dispose();
                    Discard(captureTask, textTask);
                    hwnd = content;
                    cover = VisibleControlSurface.CoveringWindow(content);
                    bool contentCovered = cover != 0 || lines;
                    captureTask = Task.Run(
                        () => CaptureQuietlyAsync(content, contentCovered, cancellationToken), CancellationToken.None);
                    textTask = includeText ? ReadTextAsync(captureTask, lines ? PlacedLinesRead : limit, cancellationToken, placed: lines) : null;
                    asked = Stopwatch.GetTimestamp();
                    answer = await _worker.SendAsync(
                            ViewCommand(content, limit, wanted, tail),
                            WorkerViewBudget, cancellationToken)
                        .ConfigureAwait(false);
                    unfinished = answer is null && PastWalkBudget(asked);
                    if (unfinished)
                        answer = UnfinishedWalk(content, VisibleControlSurface.IsAlive);
                    if (answer is null)
                        return new ViewResult(ExternalJson.Failure(operation, "visible_controls_unavailable"), []);
                }
            }
        }

        // PLAN_GENERAL A2: a toolkit that builds its tree on demand (Chromium, CEF, Qt, Flutter) starts building it at
        // the first WM_GETOBJECT, which this very read sent, and fills it asynchronously: a read with almost nothing is
        // taken again until the count of controls stops growing, within a bound.
        string toolkit = VisibleControlSurface.Toolkit(hwnd);
        bool treeWoken = false;
        // A walk that did not end is not read again: each read may take the budget once more.
        if (!unfinished && toolkit is "chromium" or "cef" or "qt" or "flutter")
        {
            nint settling = hwnd;
            (answer, treeWoken) = await SettleTreeAsync(
                answer,
                () => _worker.SendAsync(ViewCommand(settling, limit, wanted, tail), WorkerViewBudget, cancellationToken)
                    .AsTask(),
                ms => Task.Delay(ms, cancellationToken)).ConfigureAwait(false);
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
            // Renew al máximo (7.3): the window's box the worker read with the rectangles, for each control's zone.
            Rect? windowBox = ReadRect(root, "box");
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
            // Renew al máximo (7.1): the tree's own name of the window, which the read after an act compares.
            string treeTitle = title;
            if (title.Length == 0)
                title = VisibleControlSurface.WindowTitle(hwnd);
            // A packaged app's frame names the app it hosts, never the frame host every packaged app shares.
            (int ownerProcessId, string processName) = VisibleControlSurface.ViewProcess(hwnd);

            VisibleControlSurface.CapturedWindow? captured = await captureTask.ConfigureAwait(false);
            long ocrMs = 0;
            Dictionary<string, List<string>> textZones = new(StringComparer.Ordinal);
            string? textAuthority = null;
            int textOmitted = 0;
            var names = new List<string>();
            if (captured is { } capture)
            {
                // Not asked for, the text is still read when the tree shows nothing to act on.
                if (textTask is null && controls.Count <= 1)
                    textTask = ReadTextAsync(captureTask, limit, cancellationToken);
                if (textTask is not null)
                {
                    (IReadOnlyList<WindowsVisibleOcrLocator.LayoutLine>? read, ocrMs, textOmitted) =
                        await textTask.ConfigureAwait(false);
                    if (read is not null)
                    {
                        textAuthority = "windows_media_ocr_lines";
                        foreach (WindowsVisibleOcrLocator.LayoutLine line in read)
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
                    }
                    else
                    {
                        textAuthority = "unavailable";
                    }
                }
            }
            // Ronda final 18 (regla 3): the text asked for (or due, the tree showing nothing) with no capture to read it
            // from is said unread, never an empty window.
            else if (textTask is not null || controls.Count <= 1)
            {
                textAuthority = "unavailable";
            }

            foreach (ViewControl control in controls)
                names.Add(control.Name);

            // BAXY Renew al máximo (F019, E015): Steam's library was told «la página principal» or «la tienda» in every
            // practice run: its window is drawn without a tree, titled «Steam» on every page, and its tab strip read by
            // OCR does not say which tab is chosen. Which of the named application's places the look shows is said as a
            // fact, from what only that place shows (the data's «shows», ApplicationPlaces.PlaceShown).
            ApplicationPlaces.ShownPlace? place = ApplicationPlaces.PlaceShown(application, names);

            lock (_viewLock)
            {
                _lastView = new LastView(hwnd, controls)
                {
                    Cut = counted > controls.Count,
                    TreeTitle = treeTitle,
                    Limit = limit,
                    Wanted = wanted,
                    Tail = tail,
                    Application = application,
                };
                _viewsRead++;
            }

            CommonFileDialog.Facts? fileDialog = CommonFileDialog.Read(hwnd);
            JsonElement result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 2);
                writer.WriteBoolean("ok", true);
                writer.WriteString("error", string.Empty);
                writer.WriteStartObject("window");
                writer.WriteString("title", title);
                writer.WriteString("process", processName);
                writer.WriteNumber("processId", ownerProcessId);
                writer.WriteNumber("hwnd", hwnd);
                // Encargo EX (tanda n6 t4-c06: Excel held «Guardar este archivo» from an earlier turn): the view is of
                // the modal dialog that disabled the window, not of the window itself.
                if (modal)
                    writer.WriteBoolean("modal", true);
                // Ajuste c3 (E017): a common file dialog, by its structure (CommonFileDialog), with the folder its address
                // shows and the name its field holds, whatever the look's limit listed (E017's looks of 10 and 15 never
                // reached the address bar, and the model saved into the dialog's last folder).
                if (fileDialog is { } dialogFacts)
                    WriteFileDialog(writer, dialogFacts, controls);
                // Ronda final 22 (regla 3): the window was minimized; the look showed it behind the person's own,
                // without activating it, and it stays so.
                if (shownBehind)
                    writer.WriteBoolean("shownFromMinimized", true);
                // Contract «Seguridad v2»: a developer's or BAXY's own window (an editor, an IDE, a terminal, a console,
                // BAXY) that the request did not name, told by its process, never by its title. No act reaches such a
                // window (protected_window, VisibleControlSurface.ActRefused); one this look named by its application
                // may be acted on.
                // Renew al máximo (lote 4, c): a Control Panel applet that configures Windows (rundll32, explorer).
                bool systemApplet = VisibleControlSurface.SystemToolWindow(windowRoot != 0 ? windowRoot : hwnd);
                if (systemApplet || VisibleControlSurface.ProtectedFrom(processName, application,
                        () => VisibleControlSurface.ProcessDescription(unchecked((uint)ownerProcessId))))
                {
                    writer.WriteBoolean("protected", true);
                    // Incidente del 2026-10-15: a system configuration tool, which no name opens to acts.
                    if (systemApplet || VisibleControlSurface.SystemTool(processName))
                        writer.WriteBoolean("systemTool", true);
                }
                else
                    VisibleControlSurface.NoteNamedProtected(windowRoot != 0 ? windowRoot : hwnd, processName);
                // v3 point 1: the content of the application's window drawn by a process it started (WebView2, CEF):
                // the application's process first, then the processes it started. A look at it is the opened
                // application's when that application's process is one of them (NoteOpenedLooked).
                if (VisibleControlSurface.SurfaceFamily(hwnd) is { Length: > 0 } family)
                {
                    writer.WriteStartArray("family");
                    foreach (uint member in family)
                        writer.WriteNumberValue(member);
                    writer.WriteEndArray();
                }

                // PLAN_GENERAL A1: what the window is built with, which says whether a tree can come at all.
                if (toolkit.Length > 0)
                    writer.WriteString("toolkit", toolkit);
                // PLAN_GENERAL A2: the tree was still being built at the first read and was read again until it settled.
                if (treeWoken)
                    writer.WriteBoolean("treeWoken", true);
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
                if (place is not null)
                {
                    writer.WriteStartObject("place");
                    writer.WriteString("application", application);
                    writer.WriteString("name", place.Place);
                    writer.WriteString("shown", place.Shown);
                    writer.WriteEndObject();
                }

                writer.WriteStartArray("controls");
                foreach (ViewControl control in controls)
                {
                    writer.WriteStartObject();
                    writer.WriteNumber("i", control.Index);
                    writer.WriteString("kind", control.Kind);
                    writer.WriteString("name", control.Name);
                    // R6-NB-5: the characters a long name lost at its end (DesktopUiaWorker.ps1 Format-Name).
                    if (control.NameCut > 0)
                        writer.WriteNumber("nameCut", control.NameCut);
                    writer.WriteString("state", control.State);
                    if (control.Value is null)
                        writer.WriteNull("value");
                    else
                        writer.WriteString("value", control.Value);
                    // Goal v3 B3: the key the application declares for the control (AcceleratorKey or AccessKey).
                    if (control.Shortcut.Length > 0)
                        writer.WriteString("shortcut", control.Shortcut);
                    if (control.Repeated > 0)
                        writer.WriteNumber("repeated", control.Repeated);
                    // BAXY Renew cu (C11): what the grid itself says a DataItem is («Encabezado de fila», «Celda»).
                    if (control.ItemType.Length > 0)
                        writer.WriteString("itemType", control.ItemType);
                    // Renew al máximo (7.3): where in the window it lies (two «Buscar», «the first result»).
                    if (ControlZone(control.RectValue, windowBox) is { Length: > 0 } zone)
                        writer.WriteString("zone", zone);
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
                        writer.WriteEndObject();
                    }

                    writer.WriteEndArray();
                }

                // Ronda final 20 (regla 3): disabled controls left unlisted (a large tree, or past the cap) are said.
                if (root.TryGetProperty("disabledCut", out JsonElement disabledCut) && disabledCut.ValueKind == JsonValueKind.True)
                    writer.WriteBoolean("disabledCut", true);

                writer.WriteNumber("controlCount", counted);
                // Ronda 20b, palanca 8 (v3-51, v3-62): a look that brought only the window's frame, read again by the
                // worker under the same root without the offscreen filter, then under the owner window, is «frameOnly»
                // when neither brought content.
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
                    // Ronda final 19 (regla 3): lines read and not listed (too long, or past the limit).
                    if (textOmitted > 0)
                        writer.WriteNumber("textOmittedLines", textOmitted);
                }
                else
                {
                    // Ronda final 19 (regla 3): the text was not asked for and not read: said, never an empty window.
                    writer.WriteString("textAuthority", "not_read");
                }

                writer.WriteStartObject("elapsedMs");
                writer.WriteNumber("uia", uiaMs);
                writer.WriteNumber("ocr", ocrMs);
                writer.WriteNumber("total", stopwatch.ElapsedMilliseconds);
                writer.WriteEndObject();
                writer.WriteString("authority", controls.Count <= 1 && textAuthority == "windows_media_ocr_lines"
                    ? "windows_media_ocr_lines"
                    : "windows_uia_snapshot_ocr_zones");
                writer.WriteEndObject();
            });
            return new ViewResult(ExternalJson.Success(operation, result, false), names, unfinished);
        }
    }

    private readonly record struct WrittenText(
        IReadOnlyList<WindowsVisibleOcrLocator.LayoutLine>? Lines,
        long Milliseconds,
        int Omitted = 0);

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
        var omitted = new System.Runtime.CompilerServices.StrongBox<int>();
        IReadOnlyList<WindowsVisibleOcrLocator.LayoutLine>? lines = await WindowsVisibleOcrLocator.ReadLayoutAsync(
            capture.Bmp, Math.Max(limit, 40), cancellationToken, placed, omitted).ConfigureAwait(false);
        return new WrittenText(lines, watch.ElapsedMilliseconds, omitted.Value);
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
            Rect? rect = ReadRect(item, "rect");
            controls.Add(new ViewControl
            {
                Index = controls.Count,
                Kind = ReadString(item, "kind"),
                Name = name,
                NameCut = ReadInt(item, "nameCut"),
                Id = ReadString(item, "id"),
                State = ReadString(item, "state"),
                Value = item.TryGetProperty("value", out JsonElement value)
                    && value.ValueKind == JsonValueKind.String
                        ? value.GetString()
                        : null,
                Shortcut = ReadString(item, "shortcut"),
                ItemType = ReadString(item, "itemType"),
                RectValue = rect,
                Repeated = ReadInt(item, "repeated"),
            });
        }

        return controls;
    }

    private static string ReadString(JsonElement item, string name) =>
        item.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.String
            ? value.GetString() ?? string.Empty
            : string.Empty;

    private static Rect? ReadRect(JsonElement item, string name) =>
        item.TryGetProperty(name, out JsonElement box) && box.ValueKind == JsonValueKind.Object
            ? new Rect(ReadInt(box, "x"), ReadInt(box, "y"), ReadInt(box, "w"), ReadInt(box, "h"))
            : null;

    private static int ReadInt(JsonElement item, string name) =>
        item.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.Number
            && value.TryGetInt32(out int number)
            ? number
            : 0;

    private static readonly string[] ZoneOrder = ["TL", "T", "TR", "L", "C", "R", "BL", "B", "BR"];

    // Rejilla 3×3 sobre la ventana: la zona del centro de una línea leída (el texto por zonas de la vista).
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

    // Renew al máximo (7.3): the zone of the window a control's centre lies in; none without its rectangle, without the
    // window's box, or with its centre outside that box (never guessed).
    internal static string ControlZone(Rect? control, Rect? window)
    {
        if (control is not { } rect || window is not { } box)
            return string.Empty;
        double x = rect.X + rect.W / 2.0;
        double y = rect.Y + rect.H / 2.0;
        return x < box.X || y < box.Y || x >= box.X + box.W || y >= box.Y + box.H ? string.Empty : Zone(x, y, box);
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

            // Without a window named, the window in front, as the descriptor says.
            if (hwnd == 0)
            {
                // Read where it is: the worker no longer presses by coordinates (fable/cu-v3-clic), and the pointer
                // takes the front itself inside a burst of the foreground lease (fable/cu-v3-pausa).
                hwnd = await WindowInFront(cancellationToken).ConfigureAwait(false);
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
            return ExternalJson.FailureBeforeEffect(operation, ElevatedCode(hwnd));
        // Ronda final 21 (seguridad): judged on the window resolved, not only on the one the provider's gate saw.
        if (Refuses(hwnd))
            return ExternalJson.FailureBeforeEffect(operation, "protected_window");
        _lookedWindow = hwnd;
        _actedWindow = hwnd;

        return await PressUiaAsync(operation, label, controlId, hwnd, effectBoundary, cancellationToken, manner)
            .ConfigureAwait(false);
    }

    /// <summary>
    /// A click that names a search (<c>search</c>, goal v3 point 0, fix 3): the opener of the named window, by its
    /// identity in the last view, then the text and the result inside one burst of the lease (<see cref="SearchBurst"/>).
    /// Only when the click names its window and on a control with an identity; nothing is pressed otherwise.
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
        if (Refuses(window))
            return ExternalJson.FailureBeforeEffect(operation, "protected_window");
        if (controlId is null)
            return ExternalJson.FailureBeforeEffect(operation, "visible_control_identity_stale");
        if (BurstLease is not { } lease || TypeInWindow is null)
            return ExternalJson.FailureBeforeEffect(operation, "visible_search_unavailable");
        if (_elevated(window))
            return ExternalJson.FailureBeforeEffect(operation, ElevatedCode(window));
        IReadOnlyList<ViewControl> before;
        lock (_viewLock)
        {
            before = _lastView is { } view && view.Hwnd == window ? view.Controls : [];
        }

        _lookedWindow = window;
        _actedWindow = window;
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
        string command = new JsonObject
        {
            ["cmd"] = "view", ["hwnd"] = window, ["limit"] = 60, ["disabled"] = false, ["caret"] = false,
        }.ToJsonString();
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
        nint namedWindow,
        string? manner,
        CancellationToken cancellationToken)
    {
        if (namedWindow == 0 || opener is not { } shownBy || BurstLease is not { } reopenLease
            || !VisibleControlSurface.IsAlive(shownBy.Window) || _elevated(shownBy.Window) || Refuses(shownBy.Window)
            || !ReopensShownItem(pressed.ErrorCode, label, controlId, namedWindow,
                shownBy.Window, shownBy.Id, shownBy.NamesBefore, VisibleControlSurface.IsAlive(namedWindow),
                namedWindow == shownBy.Window ? [] : PopupsOf(shownBy.Window), (shownBy.NamesBefore as OpenerNames)?.Described))
            return null;
        _lookedWindow = shownBy.Window;
        // Renew al máximo (7.1): the item's window is the one read again after the burst.
        _actedWindow = namedWindow;
        return await new SearchBurst(reopenLease, SearchClock, this)
            .ReopenAsync(operation, shownBy.Window, shownBy.Label, shownBy.Id, label, cancellationToken,
                shownIn: namedWindow == shownBy.Window ? 0 : namedWindow, openerManner: shownBy.Manner, itemManner: manner)
            .ConfigureAwait(false);
    }

    /// <summary>
    /// The one control of the last view of <paramref name="window"/> a label names, by its identity: the only control
    /// of exactly that name (<see cref="SameLabel"/>). Null when the last view is of another window, the label names
    /// none or several, or the control has no identity: the label is then left to its cascade, which presses nothing it
    /// does not name exactly.
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

    // The last control of a named window pressed by its identity, with the names its view showed before the press:
    // a control of the next view that is none of those appeared with that press (v3-09: the gallery of a ribbon tab).
    // Review of the branch (finding 3): only a control that opens something by its structure (a tab, a combo box, one
    // that says it is collapsed: OpensAgain) is noted, and it holds for the very next view and click only (Views: the
    // count of views read when it was pressed), so a press that creates or deletes («Nuevo», «Eliminar») is never pressed
    // again, and neither is any opener after a text, a key, another click or a second look.
    // Ronda 20 (P7): with the manner it was pressed in (an arrow, a context menu), so it is reopened the same way.
    private (nint Window, string Id, string Label, HashSet<string> NamesBefore, long Views, string? Manner)? _opener;

    // How many views this adapter has read (an opener holds for the very next one only).
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
        // Auditoría final (regla 3): the person's touch of the window counts from here, before anything is sent.
        _pressStartedMs = Environment.TickCount64;
        // The descriptor admits «surface changed» as post-read. A Calculator
        // digit stays enabled and unselected after Invoke, so the surface is
        // the only evidence (UI1273); it is compared before/after the click.
        VisibleControlSurface.CapturedWindow? before = null;
        long probed = _time.GetTimestamp();
        try
        {
            before = await _capture(hwnd, null, cancellationToken).ConfigureAwait(false);
            // Auditoría final (regla 3): a window that changes by itself (a video, a caret, a spinner) gives no proof of
            // the click by its image: captures before it that differ leave the surface out of the post-read (the
            // control's own answer, a popup or a window it handed to still prove it).
            if (before is { } first && await AnimatesFromAsync(hwnd, first, cancellationToken).ConfigureAwait(false))
                before = null;
        }
        catch (Exception exception) when (exception is IOException or InvalidOperationException)
        {
            before = null;
        }

        _stillSince = before is { } still ? (hwnd, still.Sha256, probed) : null;

        // Pasada r15b B2 (v3-17): the window's own popups before the click; one born of it is its effect.
        IReadOnlyList<nint> popupsBefore = PopupsOf(hwnd);
        // Ronda 20b, palanca 8, objetivo 3 (v3-44): the desktop's root windows before the click.
        HandoffWatch? roots = _clickRoots = RootsBefore(hwnd);
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
                    return await PointerAsync(
                            operation, answer.RootElement, hwnd, animated: before is null, effectBoundary, cancellationToken)
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
    /// <paramref name="animated"/> is the verdict of the probe the tree's press made on that window right before it
    /// asked the worker (no image, or one that changed by itself): the worker pressed nothing since.
    /// </summary>
    private async ValueTask<ExternalCapabilityReceipt> PointerAsync(
        string operation,
        JsonElement answer,
        nint hwnd,
        bool animated,
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

        // Auditoría final (regla 3): a window that changes by itself gives no proof of the press by its image. Its probe
        // is the tree's press's (animated), not a second one: e2e c3-final5 dv6, five pointer clicks in Configuración
        // took 2.0-2.2 s, about 0.7 s of each the same 150 + 450 ms probe and its captures again.
        // Ronda final 19: the desktop's roots as close to the press as this path can take them.
        HandoffWatch? roots = _clickRoots = RootsBefore(hwnd);
        PointerPressed pointed = await LocatedPointPress.PointerAsync(
            _pointer, hwnd, x, y, null, null, cancellationToken, PopupsOf).ConfigureAwait(false);
        if (!pointed.Pressed)
            return ExternalJson.FailureBeforeEffect(operation, pointed.Refusal ?? "input_window_not_in_front");

        VisibleControlSurface.CapturedWindow? before = animated ? null : pointed.Before;
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
        // Ronda final 21 (seguridad): neither by its way nor by the pointer.
        if (Refuses(window))
            return PointPressed.InProtectedWindow;
        _actedWindow = window;
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
        CancellationToken cancellationToken)
    {
        _actedWindow = window;
        return LocatedPointPress.PointerAsync(_pointer, window, screenX, screenY, located, relocate, cancellationToken);
    }

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
            if (!effect && error == NeedsConfirmation)
                return PointPressed.HeldForConfirmation;
            if (!effect && error == "visible_point_named_other")
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
        // Auditoría final: a field that already had the focus was not pressed (via «prefocused»): the state reached.
        if (method == "target" && focused && root.TryGetProperty("via", out JsonElement via)
            && via.ValueKind == JsonValueKind.String && via.GetString() == "prefocused")
            return new PointPressed(PointPressOutcome.AlreadyFocused, method, name, kind, Focused: true);
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
        bool surfaceRead = false;
        bool controlWasSelected = false;
        bool arrivedUncaused = false;
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
                    return ReceiptFromWorker(operation, root, effectBoundary);
                // Ronda 20b, palanca 7 (v3-53): a toggle the control took without its sibling's mark appearing is no
                // receipt, and the box's own redraw must not become one through the surface: the effect is uncertain.
                // Review of ronda 20b (finding 3): so is a choice whose Select marked the row without moving the place
                // (v3-52): the row's redrawn mark is no surface change of the posted press.
                if (root.TryGetProperty("error", out JsonElement doubt) && doubt.ValueKind == JsonValueKind.String
                    && doubt.GetString() is ToggleUncorroborated or ChoiceUncorroborated)
                    return ReceiptFromWorker(operation, root, effectBoundary);
                controlWasSelected |= root.TryGetProperty("alreadySelected", out JsonElement chosen)
                    && chosen.ValueKind == JsonValueKind.True;
                // Anything but «not yet» ends the questions to the control; the surface may still answer.
                askControl = root.TryGetProperty("error", out JsonElement error)
                    && error.ValueKind == JsonValueKind.String
                    && error.GetString() == "visible_button_postread_unchanged";
            }

            if (before is { } captured && watch.Elapsed >= _timing.SurfaceFirstSample)
            {
                string? surface = await SurfaceAsync(captured.Hwnd, captured.SelfDrawn, cancellationToken)
                    .ConfigureAwait(false);
                surfaceRead |= surface is not null;
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
                    if (held is { } answered)
                        return answered;
                    // An image the person may have changed (their input to that window, their pointer over it) proves
                    // nothing of the press.
                    return WindowsUserInputPause.PersonTouched(captured.Hwnd, _pressStartedMs)
                        ? effectBoundary.Failure(operation, "input_user_interrupted", effectObserved: true)
                        : SurfaceChanged(operation, clicked, front);
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
                if (held is { } answered)
                    return answered;
                return WindowsUserInputPause.PersonTouched(watched.Window, _pressStartedMs)
                    ? effectBoundary.Failure(operation, "input_user_interrupted", effectObserved: true)
                    : SurfaceChanged(operation, clicked, front, popupBorn: true);
            }

            // Ronda 20b, palanca 8, objetivo 3 (v3-44): a window of another process born or brought to the front within
            // the click's post-read is where the click handed its effect, while the clicked window may stay the same.
            // r27: looked for up to the post-read's own budget and no longer (the fixed 1.2 s tail after it was paid whole
            // by the 20 unchanged clicks of 3 runs of the bank and found no window in any).
            if (watch.Elapsed >= _timing.SurfaceFirstSample && Handed(roots) is { } handedNow)
                return HandedOff(operation, clicked, front, handedNow);
            if (!arrivedUncaused && watch.Elapsed >= _timing.SurfaceFirstSample)
                arrivedUncaused = ArrivedUncaused(roots);

            if (watch.Elapsed >= budget)
                break;
            await Task.Delay(_timing.PostreadPeriod, cancellationToken).ConfigureAwait(false);
        }

        // Ronda final 18 (regla 3): «unchanged» only from a read-back that was read; none read is said as such.
        // Feria 2026-10-27: a calculator's clicks were said «unchanged» with no image of its window read. A control that
        // stays enabled and unselected after Invoke says «unchanged» whatever the click did, so only the window's image,
        // read after the click, can say it, or the control itself read as already chosen before the click (C02).
        if (!surfaceRead && !controlWasSelected)
            return effectBoundary.Failure(operation, "visible_click_postread_unread", effectObserved: true);
        // Ronda final 20 (regla 3): another process's window came meanwhile with nothing showing the click caused it:
        // the click's effect is uncertain, never «unchanged» (the model would press again: a second browser tab).
        if (arrivedUncaused)
            return effectBoundary.Failure(operation, "visible_click_handoff_uncertain", effectObserved: true);
        // Pressed and seen unchanged: no later stage of this click presses that control again (finding 4).
        _pressedUnchanged = PressedIdentity(clicked);
        ExternalCapabilityReceipt unchanged =
            effectBoundary.Failure(operation, "visible_button_postread_unchanged", effectObserved: true);
        return controlWasSelected && ModelAids.On(ModelAids.AlreadySelected)
            ? unchanged with { Result = AlreadySelected() }
            : unchanged;
    }

    // BAXY Renew cu (C02): the control was already the chosen one before the click (a section the window already
    // showed): said, so the window's view is read for what was asked instead of pressing it again (five presses of the
    // section Settings had opened at, its device list unread in the look the model already had).
    internal static JsonElement AlreadySelected() => ExternalJson.Create(writer =>
    {
        writer.WriteStartObject();
        writer.WriteBoolean("alreadySelected", true);
        writer.WriteString("next", "it was already selected before this click: the window already shows it, and the "
            + "last look's controls are what it shows");
        writer.WriteEndObject();
    });

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

    /// <inheritdoc/>
    public object? WatchRoots(nint window) => RootsBefore(window);

    /// <inheritdoc/>
    public bool AnotherWindowCame(object? watch) =>
        watch is HandoffWatch roots && (Handed(roots) is not null || ArrivedUncaused(roots));

    // Ronda final 20: a window of another process that came now without proof the click caused it (or no watch: false).
    private bool ArrivedUncaused(HandoffWatch? watch)
    {
        if (watch is null || RootWindows is not { } roots)
            return false;
        try
        {
            return VisibleControlSurface.ArrivedUncaused(watch.Before, roots(watch.Window)) != 0;
        }
        catch (Exception exception) when (exception is IOException or InvalidOperationException)
        {
            return false;
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
    /// have changed, and <c>handedTo</c> naming that window (its handle, title, process and process id, whether it was
    /// born with the click, and how long ago the person's input went to it and to its process or the shell) (ronda 20b,
    /// palanca 8, objetivo 3).
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
        // Review 3 of palanca 8 (B1): how long ago the person's input went to that window, and to its process or the
        // shell.
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
        // Recibo del clic por estado (r15b v3-42, v3-51), review finding 1: a field (Edit, Document, ComboBox) that took
        // the keyboard's focus or changed its value with the press, and the click's window disabled by the modal dialog
        // the press opened, are the worker's post-read proofs, each under its own key.
        bool fieldTook = root.TryGetProperty("fieldTook", out JsonElement fieldValue)
            && fieldValue.ValueKind == JsonValueKind.True;
        bool dialogOpened = root.TryGetProperty("dialogOpened", out JsonElement dialogValue)
            && dialogValue.ValueKind == JsonValueKind.True;
        // Ajuste c3 (F09, M3): the pressed control itself renamed by the press («Iniciar» became «Pausa»), or a control
        // the last look read as chosen that names the pressed one now and did not before («Color 1: Rojo oscuro»).
        bool renamed = root.TryGetProperty("renamed", out JsonElement renamedValue)
            && renamedValue.ValueKind == JsonValueKind.True;
        bool chosenNamed = root.TryGetProperty("chosenNamed", out JsonElement chosenValue)
            && chosenValue.ValueKind == JsonValueKind.True;
        return dismissed || selected || toggled || surface || targeted || opened || fieldTook || dialogOpened
            || renamed || chosenNamed;
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
            if (!effect && error == SettingsSwitchRefused)
                return new ExternalCapabilityReceipt(operation, false, false, SettingsSwitchFacts(root), error);
            // Auditoría P3 y C10: the controls whose name holds the label, none of them pressed, go with the «not found»
            // so the model can name one exactly.
            if (!effect && BeforeAnyPress.Contains(error)
                && root.TryGetProperty("candidates", out JsonElement candidates) && candidates.ValueKind == JsonValueKind.Array)
                return NotNamed(operation, error, [.. candidates.EnumerateArray()
                    .Where(candidate => candidate.ValueKind == JsonValueKind.String).Select(candidate => candidate.GetString()!)],
                    root.TryGetProperty("candidateCount", out JsonElement all) && all.TryGetInt32(out int count) ? count : null);
            return !effect && BeforeAnyPress.Contains(error)
                ? ExternalJson.FailureBeforeEffect(operation, error)
                : effectBoundary.Failure(operation, error, effect);
        }

        // Ronda final: a field that already had the keyboard's focus was not pressed: the state reached (changed:false).
        if (!effect && root.TryGetProperty("alreadyReached", out JsonElement reached)
            && reached.ValueKind == JsonValueKind.True && PostreadHolds(root))
            return ExternalJson.Switched(operation, root.Clone(), effectObserved: false);
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
    // Ronda final 19 (regla 3): with the count of all of them when the list is a first part (<paramref name="total"/>).
    /// <summary>The collapsed entries of a look (a folded ribbon group, a closed menu or list), by index and name, as a
    /// fact for a label no control had; null when the look showed none.</summary>
    internal static JsonElement? CollapsedHint(IReadOnlyList<ViewControl> controls)
    {
        ViewControl[] folded = [.. controls.Where(Folded).Take(CollapsedHintLimit)];
        if (folded.Length == 0)
            return null;
        return ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteStartArray("collapsed");
            foreach (ViewControl control in folded)
                writer.WriteStringValue($"[{control.Index}] {control.Kind} «{control.Name}»");
            writer.WriteEndArray();
            writer.WriteString("next", "nothing was pressed: no control of the window has that name now; your last look "
                + "showed these collapsed entries, and what a window keeps folded may be inside one (open it with "
                + "manner open, then look again)");
            writer.WriteEndObject();
        });
    }

    internal const int CollapsedHintLimit = 12;

    // The kinds a look lists that are pressed or opened (an entry, a button, a split button, a list), and of them the
    // collapsed ones: what opens a folded group, menu or list.
    private static bool PressesOrOpens(ViewControl control) => control.Kind is "MenuItem" or "SplitButton" or "Button" or "ComboBox";

    private static bool Folded(ViewControl control) =>
        PressesOrOpens(control) && control.State.Contains("collapsed", StringComparison.Ordinal);

    internal static ExternalCapabilityReceipt NotNamed(
        string operation, string error, IReadOnlyList<string> candidates, int? total = null, string? next = null) =>
        candidates.Count == 0
            ? ExternalJson.FailureBeforeEffect(operation, error)
            : new ExternalCapabilityReceipt(operation, false, false, ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                if (total is int all && all > candidates.Count)
                {
                    writer.WriteNumber("candidateCount", all);
                    writer.WriteBoolean("truncated", true);
                }
                writer.WriteStartArray("candidates");
                foreach (string candidate in candidates)
                    writer.WriteStringValue(candidate);
                writer.WriteEndArray();
                if (next is not null)
                    writer.WriteString("next", next);
                writer.WriteEndObject();
            }), error);

    // What the worker must not press without its name in the invocation (the worker's Get-AskingName), RiskPolicy's own.
    private static JsonObject AsksRequest() => new()
    {
        ["pattern"] = RiskPolicy.AsksPattern,
        ["hint"] = RiskPolicy.FoldHint,
        ["confusables"] = RiskPolicy.Confusables,
    };

    private static bool ShouldKeep(ExternalCapabilityReceipt receipt) =>
        receipt.Verified && receipt.ErrorCode is null;

    /// <summary>The worker's answer to a toggle whose sibling's mark did not appear for it (ronda 20b, palanca 7).</summary>
    internal const string ToggleUncorroborated = "visible_toggle_uncorroborated";

    /// <summary>The worker's answer to a choice whose place did not move after its posted press (review of ronda 20b, finding 3).</summary>
    internal const string ChoiceUncorroborated = "visible_choice_uncorroborated";

    /// <summary>The worker's answer to a point on the control the tree already pressed in this click.</summary>
    internal const string PointAlreadyPressed = "visible_point_already_pressed";

    // When the running press started (Environment.TickCount64): the person's touch of the window since then is theirs.
    private long _pressStartedMs;

    // The image the probe of the running look's press found still on its window, and when that probe began (the
    // adapter's clock); null when the probe saw it change or read nothing, or the look reached no press.
    private (nint Window, string Sha256, long At)? _stillSince;

    // The identity of the control the tree pressed in the running click and saw nothing change from (finding 4).
    private string? _pressedUnchanged;

    private static bool ShouldCascade(ExternalCapabilityReceipt receipt) =>
        receipt.ErrorCode is not null && CascadeAfter.Contains(receipt.ErrorCode);

    /// <summary>
    /// The window the warm-up look reads (<see cref="VisibleControlSurface.ShellWindow"/>: the shell's own desktop,
    /// never an application's window nor the one in front); a test seam names its own.
    /// </summary>
    internal Func<nint> WarmupWindow { get; init; } = VisibleControlSurface.ShellWindow;

    /// <summary>
    /// Ronda 28 (banco Br27: the first whole look of a session cost 1 041–1 200 ms, 190–340 ms once warm, with the worker
    /// already started): the worker is started and asked one look ahead of the first one, so what a first look
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
        Refuses(window) ? ValueTask.FromResult<JsonDocument?>(RefusedAnswer()) : _worker.SendAsync(
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
        Refuses(window) ? ValueTask.FromResult<JsonDocument?>(RefusedAnswer()) : _worker.SendAsync(
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
        Refuses(window) ? ValueTask.FromResult<JsonDocument?>(RefusedAnswer()) : _worker.SendAsync(
            new JsonObject
            {
                ["cmd"] = "focus",
                ["hwnd"] = window,
                ["controlId"] = controlId,
            }.ToJsonString(),
            WorkerClickBudget,
            cancellationToken);

    /// <summary>FT/proveedores goal (E2): the paragraph at the caret of the keyboard's focus of <paramref name="window"/>,
    /// of <paramref name="processId"/> only, read by TextPattern (the worker's «textcaret», a read: no front kept, no
    /// pattern invoked); null when the worker did not answer.</summary>
    public ValueTask<JsonDocument?> CaretTextAsync(
        nint window,
        int processId,
        int maximum,
        CancellationToken cancellationToken) =>
        Refuses(window) ? ValueTask.FromResult<JsonDocument?>(RefusedAnswer()) : _worker.SendAsync(
            new JsonObject
            {
                ["cmd"] = "textcaret",
                ["hwnd"] = window,
                ["processId"] = processId,
                ["max"] = maximum,
            }.ToJsonString(),
            WorkerClickBudget,
            cancellationToken);

    /// <summary>Ajuste c3 (F09, M1 and M2): the value of the field with the keyboard's focus inside
    /// <paramref name="window"/>'s tree, read by ValuePattern (the worker's «focusvalue», a read: no front kept, no
    /// pattern invoked); null when the worker did not answer.</summary>
    public ValueTask<JsonDocument?> FocusedValueAsync(
        nint window,
        int maximum,
        CancellationToken cancellationToken) =>
        Refuses(window) ? ValueTask.FromResult<JsonDocument?>(RefusedAnswer()) : _worker.SendAsync(
            new JsonObject
            {
                ["cmd"] = "focusvalue",
                ["hwnd"] = window,
                ["max"] = maximum,
            }.ToJsonString(),
            WorkerClickBudget,
            cancellationToken);

    /// <summary>Auditoría del núcleo 2026-10-23: what holds the keyboard's focus and whether it lies inside
    /// <paramref name="window"/> (0: the one in front), read by UI Automation (the worker's «focuskind»: nothing pressed,
    /// focused or brought up); null when the worker did not answer.</summary>
    public ValueTask<JsonDocument?> FocusKindAsync(nint window, CancellationToken cancellationToken) =>
        _worker.SendAsync(
            new JsonObject
            {
                ["cmd"] = "focuskind",
                ["hwnd"] = window,
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
        Refuses(window) ? ValueTask.FromResult<JsonDocument?>(RefusedAnswer()) : _worker.SendAsync(
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
        Refuses(window) ? ValueTask.FromResult<JsonDocument?>(RefusedAnswer()) : _worker.SendAsync(
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
        internal int NameCut { get; set; }
        internal string Id { get; set; } = string.Empty;
        internal string State { get; set; } = string.Empty;
        internal string? Value { get; set; }
        internal string Shortcut { get; set; } = string.Empty;
        internal string ItemType { get; set; } = string.Empty;
        internal Rect? RectValue { get; set; }
        internal int Repeated { get; set; }
    }

    private sealed record LastView(nint Hwnd, IReadOnlyList<ViewControl> Controls)
    {
        // Renew al máximo (7.1): how the look read the window (its limit, words and cut), so the read after an act reads
        // it the same way and numbers it alike, and the window's name in its tree, which that read compares.
        internal string TreeTitle { get; init; } = string.Empty;

        // Renew al máximo (w8): the window had more controls than this view listed (its cap).
        internal bool Cut { get; init; }

        internal int Limit { get; init; } = 60;

        internal IReadOnlyList<string> Wanted { get; init; } = [];

        internal bool Tail { get; init; }

        // Holdout v4 (en vivo, the Steam library): the application the look named, whose places a repeated unchanged
        // click is told with.
        internal string? Application { get; init; }
    }

    // Unfinished: the worker's walk did not end within its budget (P2.17), so the look is not taken again.
    private readonly record struct ViewResult(
        ExternalCapabilityReceipt Receipt, IReadOnlyList<string> Names, bool Unfinished = false);
}
