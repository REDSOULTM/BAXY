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

    // A move is sent at most this many physical pixels after the one before, so a drawing application sees a stroke
    // and not a jump; the pause between moves lets it take each one.
    private const int StepPixels = 6;
    private const int StepPauseMs = 4;

    private readonly WindowsVisibleControlAdapter? _controls;
    private readonly IForegroundLease? _lease;
    private readonly Func<nint, CancellationToken, ValueTask<VisibleControlSurface.CapturedWindow?>> _capture;
    private readonly Func<nint, int, int, bool> _shows;
    private readonly Func<nint, bool> _inFront;
    private readonly Func<IInputBurst, int, int, bool> _pointAt;
    private readonly Action<bool> _button;

    internal WindowsPointerDragAdapter(
        WindowsVisibleControlAdapter? controls = null,
        IForegroundLease? lease = null,
        Func<nint, CancellationToken, ValueTask<VisibleControlSurface.CapturedWindow?>>? capture = null,
        Func<nint, int, int, bool>? shows = null,
        Func<nint, bool>? inFront = null,
        Func<IInputBurst, int, int, bool>? pointAt = null,
        Action<bool>? button = null)
    {
        _controls = controls;
        _lease = lease;
        _capture = capture ?? ((window, token) => VisibleControlSurface.CaptureAsync(window, token));
        _shows = shows ?? VisibleControlSurface.PointShows;
        _inFront = inFront ?? VisibleControlSurface.ForegroundIs;
        _pointAt = pointAt ?? VisibleControlSurface.PointAt;
        _button = button ?? (down => mouse_event(down ? MouseEventLeftDown : MouseEventLeftUp, 0, 0, 0, BaxyInputMark.Value));
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
        if (!_controls.TryViewedBody(index, out _, out WindowsVisibleControlAdapter.Rect? rect))
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
            VisibleControlSurface.CapturedWindow? before = await ReadAsync(window, cancellationToken).ConfigureAwait(false);
            if (before is not { } captured || captured.Hwnd != window)
                return ExternalJson.FailureBeforeEffect(operation, "active_window_not_found");
            return await DragAsync(operation, index, body, path, captured, burst, cancellationToken).ConfigureAwait(false);
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
        VisibleControlSurface.CapturedWindow captured,
        IInputBurst burst,
        CancellationToken cancellationToken)
    {
        var effectBoundary = new ExternalEffectBoundary();
        nint window = captured.Hwnd;
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
            return ExternalJson.FailureBeforeEffect(operation, "input_user_interrupted");

        try
        {
            return await PressAlongAsync(operation, index, body, path, captured, burst, effectBoundary, cancellationToken)
                .ConfigureAwait(false);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            return effectBoundary.Failure(operation, "pointer_drag_cancelled");
        }
    }

    private async ValueTask<ExternalCapabilityReceipt> PressAlongAsync(
        string operation,
        int index,
        WindowsVisibleControlAdapter.Rect body,
        (int X, int Y)[] path,
        VisibleControlSurface.CapturedWindow captured,
        IInputBurst burst,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        nint window = captured.Hwnd;
        bool whole = true;
        effectBoundary.Cross(cancellationToken);
        _button(true);
        try
        {
            (int X, int Y) from = path[0];
            foreach ((int X, int Y) to in path.Skip(1))
            {
                int steps = Math.Max(1, (int)Math.Ceiling(Math.Max(Math.Abs(to.X - from.X), Math.Abs(to.Y - from.Y))
                    / (double)StepPixels));
                for (int step = 1; step <= steps && whole; step++)
                {
                    whole = _pointAt(burst,
                        from.X + (int)Math.Round((to.X - from.X) * step / (double)steps),
                        from.Y + (int)Math.Round((to.Y - from.Y) * step / (double)steps));
                    await Task.Delay(StepPauseMs, cancellationToken).ConfigureAwait(false);
                }

                if (!whole)
                    break;
                from = to;
            }
        }
        finally
        {
            // Let go whatever stopped the path: a button left down would keep drawing under the person's hand.
            _button(false);
        }

        // The person's input stopped the path partway: what was drawn is not the path asked for.
        if (!whole || burst.UserActed)
            return effectBoundary.Failure(operation, "input_user_interrupted", effectObserved: true);
        // The window redraws after the last move, not during it.
        await Task.Delay(350, cancellationToken).ConfigureAwait(false);
        VisibleControlSurface.CapturedWindow? after = await ReadAsync(window, cancellationToken).ConfigureAwait(false);
        // An image changed after the person acted proves nothing of the drag.
        if (burst.UserActed)
            return effectBoundary.Failure(operation, "input_user_interrupted", effectObserved: true);
        bool? changed = after is { } read
            ? VisibleControlSurface.ChangedWithin(captured, read, body.X, body.Y, body.W, body.H)
            : null;
        // Regla 3: an image not read (or not comparable: the window moved or was resized) is said unread, never
        // unchanged; an unchanged body is said so, and the drag is never told as drawn.
        if (changed is null)
            return effectBoundary.Failure(operation, "pointer_drag_postread_unread", effectObserved: true);
        if (changed == false)
            return effectBoundary.Failure(operation, "pointer_drag_surface_unchanged", effectObserved: true);
        bool restored = burst.Restore();
        return ExternalJson.Success(operation, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteBoolean("ok", true);
            writer.WriteNumber("index", index);
            writer.WriteNumber("points", path.Length);
            writer.WriteBoolean("surfaceChanged", true);
            writer.WriteNumber("waitedMs", burst.WaitedMs);
            writer.WriteBoolean("restored", restored);
            writer.WriteString("authority", "win32_pointer_drag_body_surface_postread");
            writer.WriteEndObject();
        }));
    }

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
