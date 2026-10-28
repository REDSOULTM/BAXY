using System.Runtime.InteropServices;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// <c>input.pointer.drag</c> (feria 2026-10-27: «dibuja unas líneas» in Paint only selected a tool, since nothing held a
/// button down while moving): the left button held down along a path on the body of a window's last view (the canvas,
/// by its index), with the path's points relative to that body's rectangle (0 to 1), never the screen's. The window is
/// brought up in a burst of the foreground lease (after the person's pause, given back after the post-read): button
/// down on the first point, moves through the others, button up on the last, and the button is let go whatever stops
/// the path (the person's input, a cancel). Verified only when the window's image inside the body changed; an image
/// not read is said as such, never as unchanged.
/// </summary>
internal sealed partial class WindowsPointerDragAdapter : IExternalOperationAdapter
{
    private const uint MouseEventLeftDown = 0x0002;
    private const uint MouseEventLeftUp = 0x0004;

    // The pause on each point of the path (about one frame), so the window takes every point and not only the last.
    private const int PointPauseMs = 16;

    private readonly WindowsVisibleControlAdapter? _controls;
    private readonly IForegroundLease? _lease;
    private readonly Func<nint, CancellationToken, ValueTask<VisibleControlSurface.CapturedWindow?>> _capture;
    private readonly Func<nint, int, int, bool> _shows;
    private readonly Func<nint, bool> _inFront;
    private readonly Func<IInputBurst, int, int, bool> _pointAt;
    private readonly Action<bool> _button;
    private readonly Func<nint, (int Left, int Top, int Right, int Bottom)?> _bounds;

    internal WindowsPointerDragAdapter(
        WindowsVisibleControlAdapter? controls = null,
        IForegroundLease? lease = null,
        Func<nint, CancellationToken, ValueTask<VisibleControlSurface.CapturedWindow?>>? capture = null,
        Func<nint, int, int, bool>? shows = null,
        Func<nint, bool>? inFront = null,
        Func<IInputBurst, int, int, bool>? pointAt = null,
        Action<bool>? button = null,
        Func<nint, (int Left, int Top, int Right, int Bottom)?>? bounds = null)
    {
        _controls = controls;
        _lease = lease;
        _capture = capture ?? ((window, token) => VisibleControlSurface.CaptureAsync(window, token));
        _shows = shows ?? VisibleControlSurface.PointShows;
        _inFront = inFront ?? VisibleControlSurface.ForegroundIs;
        _pointAt = pointAt ?? VisibleControlSurface.PointAt;
        _button = button ?? (down => mouse_event(down ? MouseEventLeftDown : MouseEventLeftUp, 0, 0, 0, BaxyInputMark.Value));
        _bounds = bounds ?? WindowsVisibleControlAdapter.WindowBounds;
    }

    public bool CanHandle(string operation) => operation is "input.pointer.drag";

    public async ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        nint named;
        int index;
        List<(double X, double Y)> points;
        try
        {
            if (!arguments.TryGetProperty("window", out JsonElement windowValue)
                || !windowValue.TryGetInt64(out long handle) || handle <= 0
                || !arguments.TryGetProperty("index", out JsonElement indexValue)
                || !indexValue.TryGetInt32(out index) || index < 0)
                throw new InvalidDataException("The window or the index is not a number.");
            named = (nint)handle;
            points = Points(arguments);
        }
        catch (Exception exception) when (exception is InvalidDataException or InvalidOperationException
            or FormatException)
        {
            return ExternalJson.FailureBeforeEffect(operation, "pointer_drag_argument_invalid");
        }

        // The body is the last view's body at that index, of the window the drag names (Renew al máximo B-CU-1: an index
        // of a look at another window is not that window's control). Any other control (a list, a button) is never
        // dragged: a drag there moves items or presses.
        if (_controls is null
            || !_controls.TryViewedControl(index, out nint window, out _, out _)
            || window != named
            || !VisibleControlSurface.IsAlive(window))
            return ExternalJson.FailureBeforeEffect(operation, "visible_control_identity_stale");
        if (!_controls.TryViewedBody(index, out nint bodyWindow, out WindowsVisibleControlAdapter.Rect? rect,
                out (int Left, int Top, int Right, int Bottom)? looked)
            || bodyWindow != window)
            return ExternalJson.FailureBeforeEffect(operation, "pointer_drag_index_not_body");
        if (rect is not { } body || body.W <= 1 || body.H <= 1)
            return ExternalJson.FailureBeforeEffect(operation, "pointer_drag_control_unreachable");
        (int X, int Y)[] path = [.. points.Select(point => (
            body.X + (int)Math.Round(point.X * (body.W - 1)),
            body.Y + (int)Math.Round(point.Y * (body.H - 1))))];

        IInputBurst burst = await Lease.AcquireAsync(window, cancellationToken).ConfigureAwait(false);
        try
        {
            if (burst.Refusal is string refusal)
                return ExternalJson.FailureBeforeEffect(operation, refusal);
            // The body's rectangle is the look's: a window moved or resized since (the person's pause and the lease's
            // wait come between) would put the path on its toolbar or a list. Nothing is pressed.
            if (looked is null || _bounds(window) != looked)
                return ExternalJson.FailureBeforeEffect(operation, "pointer_drag_window_moved");
            return await DragAsync(operation, index, body, path, window, burst, cancellationToken).ConfigureAwait(false);
        }
        finally
        {
            _ = burst.Restore();
        }
    }

    private IForegroundLease Lease => _lease ?? ForegroundLease.Shared;

    // The path's points: «points» is [x0, y0, x1, y1, …], each a fraction of the body's width or height.
    private static List<(double X, double Y)> Points(JsonElement arguments)
    {
        if (!arguments.TryGetProperty("points", out JsonElement values) || values.ValueKind != JsonValueKind.Array)
            throw new InvalidDataException("The path is not a list.");
        int count = values.GetArrayLength();
        if (count < 4 || count % 2 != 0)
            throw new InvalidDataException("The path needs two points, each an x and a y.");
        var points = new List<(double X, double Y)>(count / 2);
        for (int at = 0; at < count; at += 2)
        {
            double x = values[at].GetDouble();
            double y = values[at + 1].GetDouble();
            if (x is < 0 or > 1 || y is < 0 or > 1)
                throw new InvalidDataException("A point lies outside the body.");
            points.Add((x, y));
        }

        return points;
    }

    private async ValueTask<ExternalCapabilityReceipt> DragAsync(
        string operation,
        int index,
        WindowsVisibleControlAdapter.Rect body,
        (int X, int Y)[] path,
        nint window,
        IInputBurst burst,
        CancellationToken cancellationToken)
    {
        var effectBoundary = new ExternalEffectBoundary();
        // The person's input since the pause ends the burst first: nothing is pressed.
        if (!burst.MayAct)
            return ExternalJson.FailureBeforeEffect(operation, "input_user_interrupted");
        // Safety review r10a: every point must show this window, never one of another application kept on top over it;
        // and the window must still hold the front the lease gave it.
        if (path.Any(point => !_shows(window, point.X, point.Y)))
            return ExternalJson.FailureBeforeEffect(operation, "input_window_not_in_front");
        if (!_inFront(window))
            return ExternalJson.FailureBeforeEffect(operation, "input_window_changed");
        if (!_pointAt(burst, path[0].X, path[0].Y))
            return ExternalJson.FailureBeforeEffect(operation, Unplaced(burst));
        // The image the drag is judged against is taken with the cursor already on the first point: what the window
        // redraws for a pointer resting there (a hover, a brush outline) is not the drag's.
        await Task.Delay(PointPauseMs, cancellationToken).ConfigureAwait(false);
        if (await ReadAsync(window, cancellationToken).ConfigureAwait(false) is not { } before || before.Hwnd != window)
            return ExternalJson.FailureBeforeEffect(operation, "active_window_not_found");

        string? stopped;
        try
        {
            stopped = await PressAlongAsync(path, window, burst, effectBoundary, cancellationToken).ConfigureAwait(false);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            return effectBoundary.Failure(operation, "pointer_drag_cancelled");
        }

        if (stopped is not null)
            return effectBoundary.Failure(operation, stopped, effectObserved: true);
        try
        {
            return await PostreadAsync(operation, index, body, path.Length, before, burst, effectBoundary, cancellationToken)
                .ConfigureAwait(false);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            // The whole path was sent: only its image was not looked at.
            return effectBoundary.Failure(operation, "pointer_drag_postread_unread");
        }
    }

    // A cursor not placed: the person's input took the burst, or Windows did not move it (a locked or secure desktop).
    private static string Unplaced(IInputBurst burst) =>
        burst.UserActed ? "input_user_interrupted" : "pointer_drag_cursor_unplaced";

    /// <summary>
    /// The button down on the first point, through the others, and up: why the path stopped partway (a window that came
    /// over it or took the front, the person's input, a cursor not placed), or null when it was sent whole.
    /// </summary>
    private async ValueTask<string?> PressAlongAsync(
        (int X, int Y)[] path,
        nint window,
        IInputBurst burst,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        bool covered = false;
        bool placed = true;
        long ownSeen = burst.OwnInputsSeen;
        effectBoundary.Cross(cancellationToken);
        _button(true);
        try
        {
            // The press is processed by Windows later than the cursor moves (review of fable/cu-v3-rafaga): it is let
            // land on the first point before the cursor leaves it.
            await burst.SettleOwnInputAsync(ownSeen, 1, cancellationToken).ConfigureAwait(false);
            foreach ((int X, int Y) to in path.Skip(1))
            {
                // Safety review r10a, checked at every point as the wheel does at every notch: a window kept on top
                // that came over the path, or one that took the front, stops it there.
                covered = !_shows(window, to.X, to.Y) || !_inFront(window);
                placed = !covered && _pointAt(burst, to.X, to.Y);
                if (!placed)
                    break;
                // A drawing application joins the points it is given; the pause lets it take each one.
                await Task.Delay(PointPauseMs, cancellationToken).ConfigureAwait(false);
            }
        }
        finally
        {
            // Let go whatever stopped the path: a button left down would keep drawing under the person's hand. The
            // release lands before the burst gives the cursor back (else it would land where the cursor went back to).
            _button(false);
            await burst.SettleOwnInputAsync(ownSeen, 2, CancellationToken.None).ConfigureAwait(false);
        }

        return covered ? "input_window_not_in_front"
            : burst.UserActed ? "input_user_interrupted"
            : placed ? null
            : Unplaced(burst);
    }

    /// <summary>
    /// The body's image after the drag, against the one before it. Regla 3: an image not read (or not comparable: the
    /// window moved or was resized) is said unread, never unchanged; an unchanged body is said so; and, as the wheel's
    /// post-read does, a body that goes on changing by itself afterwards (a caret, a video) proves nothing of the drag.
    /// </summary>
    private async ValueTask<ExternalCapabilityReceipt> PostreadAsync(
        string operation,
        int index,
        WindowsVisibleControlAdapter.Rect body,
        int points,
        VisibleControlSurface.CapturedWindow before,
        IInputBurst burst,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        // The window redraws after the last move, not during it.
        await Task.Delay(350, cancellationToken).ConfigureAwait(false);
        VisibleControlSurface.CapturedWindow? after = await ReadAsync(before.Hwnd, cancellationToken).ConfigureAwait(false);
        // An image changed after the person acted proves nothing of the drag.
        if (burst.UserActed)
            return effectBoundary.Failure(operation, "input_user_interrupted", effectObserved: true);
        bool? changed = after is { } drawn ? ChangedInBody(before, drawn, body) : null;
        if (changed is null)
            return effectBoundary.Failure(operation, "pointer_drag_postread_unread");
        if (changed == false)
            return effectBoundary.Failure(operation, "pointer_drag_surface_unchanged", effectObserved: true);
        // Two looks, ~300 ms and ~600 ms after, so a caret's blink (about every 530 ms) falls inside.
        for (int look = 0; look < 2; look++)
        {
            await Task.Delay(300, cancellationToken).ConfigureAwait(false);
            VisibleControlSurface.CapturedWindow? later = await ReadAsync(before.Hwnd, cancellationToken).ConfigureAwait(false);
            bool? moving = later is { } again ? ChangedInBody(after!.Value, again, body) : null;
            if (moving is null)
                return effectBoundary.Failure(operation, "pointer_drag_postread_unread");
            if (moving == true)
                return effectBoundary.Failure(operation, "pointer_drag_surface_unsettled");
        }

        bool restored = burst.Restore();
        return ExternalJson.Success(operation, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteBoolean("ok", true);
            writer.WriteNumber("index", index);
            writer.WriteNumber("points", points);
            writer.WriteBoolean("surfaceChanged", true);
            writer.WriteNumber("waitedMs", burst.WaitedMs);
            writer.WriteBoolean("restored", restored);
            writer.WriteString("authority", "win32_pointer_drag_body_surface_postread");
            writer.WriteEndObject();
        }));
    }

    private static bool? ChangedInBody(
        VisibleControlSurface.CapturedWindow first, VisibleControlSurface.CapturedWindow second, WindowsVisibleControlAdapter.Rect body) =>
        VisibleControlSurface.ChangedWithin(first, second, body.X, body.Y, body.W, body.H);

    private async ValueTask<VisibleControlSurface.CapturedWindow?> ReadAsync(nint window, CancellationToken cancellationToken)
    {
        try
        {
            return await _capture(window, cancellationToken).ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is IOException or InvalidOperationException)
        {
            return null;
        }
    }

    [LibraryImport("user32.dll")]
    private static partial void mouse_event(
        uint flags, uint dx, uint dy, uint data, nuint extra);
}
