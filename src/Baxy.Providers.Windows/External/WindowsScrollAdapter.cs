using System.Runtime.InteropServices;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// <c>input.scroll</c> (CONTRATO_VISTA_ACCION.md §2): scrolls the foreground
/// window with the wheel, aimed at its centre, and counts the step only when
/// the visible surface changed; a panel already at the top or the bottom does
/// not change and says so (<c>scroll_surface_unchanged</c>) instead of faking
/// the movement. Inherited from the parked Fase 4 draft (opus/fase4-wip) and
/// bound to the window resolution the view uses. With <c>index</c>, the control
/// the last view handed out at that index is scrolled instead (a list or a
/// panel that is not under the window's centre): through its ScrollPattern,
/// proved by its scroll percentage, or else with the wheel at its centre on
/// that view's window, proved by the surface.
/// With <c>label</c> (goal v3 point 2, reveal), the element of that name the mission's window holds out of view is
/// brought into it without wheel or pointer (the worker's «reveal»: ScrollItemPattern, ItemContainerPattern with
/// VirtualizedItemPattern, or the window's own ScrollPattern page by page); the proof is the element re-read visible.
/// </summary>
internal sealed partial class WindowsScrollAdapter : IExternalOperationAdapter
{
    private const uint MouseEventWheel = 0x0800;
    private const int WheelDelta = 120;

    private readonly WindowsVisibleControlAdapter? _controls;
    private readonly IForegroundLease? _lease;
    private readonly Func<CancellationToken, ValueTask<nint>> _foreground;
    private readonly Func<nint, CancellationToken, ValueTask<VisibleControlSurface.CapturedWindow?>> _capture;
    private readonly Func<nint, string, string, int, CancellationToken, ValueTask<JsonDocument?>>? _reveal;
    private readonly Func<nint, int, int, bool> _shows;

    internal WindowsScrollAdapter(
        WindowsVisibleControlAdapter? controls = null,
        IForegroundLease? lease = null,
        Func<CancellationToken, ValueTask<nint>>? foreground = null,
        Func<nint, CancellationToken, ValueTask<VisibleControlSurface.CapturedWindow?>>? capture = null,
        Func<nint, string, string, int, CancellationToken, ValueTask<JsonDocument?>>? reveal = null,
        Func<nint, int, int, bool>? shows = null)
    {
        _controls = controls;
        _lease = lease;
        _foreground = foreground ?? VisibleControlSurface.ForegroundTargetAsync;
        _capture = capture ?? ((window, token) => VisibleControlSurface.CaptureAsync(window, token));
        _reveal = reveal ?? (controls is null ? null : controls.RevealAsync);
        _shows = shows ?? VisibleControlSurface.PointShows;
    }

    public bool CanHandle(string operation) => operation is "input.scroll";

    public async ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        string direction;
        int amount;
        int? index = null;
        nint missionWindow = 0;
        string? label = null;
        try
        {
            direction = ExternalJson.RequiredString(arguments, "direction");
            if (arguments.TryGetProperty("label", out JsonElement named0) && named0.ValueKind != JsonValueKind.Null)
            {
                if (named0.ValueKind != JsonValueKind.String || string.IsNullOrWhiteSpace(named0.GetString()))
                    throw new InvalidDataException("The label is not a name.");
                label = named0.GetString()!.Trim();
            }

            amount = ExternalJson.OptionalInt(arguments, "amount", 3);
            if (arguments.TryGetProperty("index", out JsonElement indexValue)
                && indexValue.ValueKind != JsonValueKind.Null)
            {
                if (indexValue.ValueKind != JsonValueKind.Number || !indexValue.TryGetInt32(out int requested))
                    throw new InvalidDataException("The control index is not an integer.");
                index = requested;
            }

            // The mission's window: the hwnd of the view the scroll was decided on (v3 point 0 review).
            if (arguments.TryGetProperty("window", out JsonElement named) && named.ValueKind != JsonValueKind.Null)
            {
                if (named.ValueKind != JsonValueKind.Number || !named.TryGetInt64(out long handle) || handle <= 0)
                    throw new InvalidDataException("The window is not a window handle.");
                missionWindow = (nint)handle;
            }
        }
        catch (InvalidDataException)
        {
            return ExternalJson.FailureBeforeEffect(operation, "scroll_argument_invalid");
        }

        if (direction is not ("down" or "up") || amount is < 1 or > 10)
            return ExternalJson.FailureBeforeEffect(operation, "scroll_argument_invalid");
        if (label is not null)
            return await RevealAsync(operation, label, direction, amount, missionWindow, cancellationToken).ConfigureAwait(false);

        // The window and the point the wheel is aimed at: the viewed control's centre on its view's window, or the
        // centre of the window a person acts on. The wheel moves the real cursor, so it turns only inside a burst of
        // the foreground lease (GOAL_COMPUTER_USE_V3 point 0, fix 3): after a pause of the person, with the front and
        // the cursor given back once the surface was compared.
        nint window = 0;
        VisibleControlSurface.CapturedWindow? before = null;
        (int X, int Y)? aim = null;
        IInputBurst? burst = null;
        try
        {
            try
            {
                if (index is int position)
                {
                    if (_controls is null
                        || !_controls.TryViewedControl(position, out window, out string controlId, out WindowsVisibleControlAdapter.Rect? rect)
                        || !VisibleControlSurface.IsAlive(window))
                    {
                        return ExternalJson.FailureBeforeEffect(operation, "visible_control_identity_stale");
                    }

                    if (controlId.Length > 0)
                    {
                        ExternalCapabilityReceipt? patterned = await ScrollPatternAsync(
                            operation, window, controlId, direction, amount, position, cancellationToken).ConfigureAwait(false);
                        if (patterned is not null)
                            return patterned;
                    }

                    if (rect is not { } bounds || bounds.W <= 0 || bounds.H <= 0)
                        return ExternalJson.FailureBeforeEffect(operation, "scroll_control_unreachable");
                    aim = (bounds.X + bounds.W / 2, bounds.Y + bounds.H / 2);
                    burst = await Lease.AcquireAsync(window, cancellationToken).ConfigureAwait(false);
                    if (burst.Refusal is null)
                        before = await _capture(window, cancellationToken).ConfigureAwait(false);
                }
                else
                {
                    // Review of fable/cu-v3-pausa: the burst comes first and the capture after it. A capture taken
                    // before the wait for the person's pause would aim the wheel at a rectangle the person may have
                    // moved, and a surface the person scrolled or typed in while waited for would pass for the wheel's.
                    // The mission's window when the step names it (v3 point 0 review: a look no longer brings it to the
                    // front, so the wheel never goes to whatever is in front instead), else the window a person acts on.
                    if (missionWindow != 0 && !VisibleControlSurface.IsAlive(missionWindow))
                        return ExternalJson.FailureBeforeEffect(operation, "input_window_not_in_front");
                    window = missionWindow != 0
                        ? missionWindow
                        : await _foreground(cancellationToken).ConfigureAwait(false);
                    if (window != 0)
                    {
                        burst = await Lease.AcquireAsync(window, cancellationToken).ConfigureAwait(false);
                        if (burst.Refusal is null)
                            before = await _capture(window, cancellationToken).ConfigureAwait(false);
                    }
                }
            }
            catch (Exception exception) when (exception is IOException or InvalidOperationException)
            {
                before = null;
            }

            if (burst?.Refusal is string refusal)
                return ExternalJson.FailureBeforeEffect(operation, refusal);
            if (before is not { } captured || burst is null || captured.Hwnd != window)
                return ExternalJson.FailureBeforeEffect(operation, "active_window_not_found");
            return await WheelAsync(operation, direction, amount, index, captured, aim, burst, _capture, _shows, cancellationToken)
                .ConfigureAwait(false);
        }
        finally
        {
            _ = burst?.Restore();
        }
    }

    private IForegroundLease Lease => _lease ?? ForegroundLease.Shared;

    /// <summary>
    /// The wheel's notches, each sent only while the burst may act and the aim still shows the mission's window
    /// (checked right before each notch): how many turned, and whether a window covering the aim stopped them.
    /// </summary>
    internal static async ValueTask<(int Turned, bool Covered)> TurnWhileShownAsync(
        int amount, Func<bool> mayAct, Func<bool> shows, Action notch, CancellationToken cancellationToken,
        int pauseMs = 40)
    {
        int turned = 0;
        while (turned < amount && mayAct())
        {
            if (!shows())
                return (turned, true);
            notch();
            turned++;
            await Task.Delay(pauseMs, cancellationToken).ConfigureAwait(false);
        }

        return (turned, false);
    }

    private static async ValueTask<ExternalCapabilityReceipt> WheelAsync(
        string operation,
        string direction,
        int amount,
        int? index,
        VisibleControlSurface.CapturedWindow captured,
        (int X, int Y)? aim,
        IInputBurst burst,
        Func<nint, CancellationToken, ValueTask<VisibleControlSurface.CapturedWindow?>> capture,
        Func<nint, int, int, bool> shows,
        CancellationToken cancellationToken)
    {
        var effectBoundary = new ExternalEffectBoundary();
        try
        {
            (int x, int y) = aim ?? (captured.Left + captured.Width / 2, captured.Top + captured.Height / 2);
            // The window the wheel is aimed at still holds the front right before it turns (the person may have
            // taken it meanwhile): otherwise the wheel would move what covers it.
            // The person's input since the pause ends the burst first: nothing turns.
            if (!burst.MayAct)
                return ExternalJson.FailureBeforeEffect(operation, "input_user_interrupted");
            // Safety review r10a: the wheel turns what is under the cursor, so the point must show this window, never
            // one of another application kept on top over it (a picture-in-picture, a sticky note).
            if (!shows(captured.Hwnd, x, y))
                return ExternalJson.FailureBeforeEffect(operation, "input_window_not_in_front");
            if (!VisibleControlSurface.ForegroundIs(captured.Hwnd))
                return ExternalJson.FailureBeforeEffect(operation, "input_window_changed");
            effectBoundary.Cross(cancellationToken);
            if (!VisibleControlSurface.PointAt(burst, x, y))
                return ExternalJson.FailureBeforeEffect(operation, "input_user_interrupted");
            int delta = direction == "down" ? -WheelDelta : WheelDelta;
            (int turned, bool covered) = await TurnWhileShownAsync(
                amount,
                () => burst.MayAct,
                () => shows(captured.Hwnd, x, y),
                () => mouse_event(MouseEventWheel, 0, 0, unchecked((uint)delta), BaxyInputMark.Value),
                cancellationToken).ConfigureAwait(false);
            // A window that came over the aim between notches stopped the wheel: what turned is not the scroll asked
            // for, and the receipt says so instead of a whole scroll (review of r10a's fix).
            if (covered)
                return turned == 0
                    ? ExternalJson.FailureBeforeEffect(operation, "input_window_not_in_front")
                    : effectBoundary.Failure(operation, "input_window_not_in_front", effectObserved: true);

            // La superficie se compara tras un respiro: la ventana redibuja
            // después del último evento de rueda, no durante.
            await Task.Delay(350, cancellationToken).ConfigureAwait(false);
            VisibleControlSurface.CapturedWindow? after = null;
            try
            {
                after = await capture(captured.Hwnd, cancellationToken).ConfigureAwait(false);
            }
            catch (Exception exception) when (exception is IOException or InvalidOperationException)
            {
                after = null;
            }

            // A surface that changed after the person acted proves nothing of the wheel.
            if (burst.UserActed)
                return effectBoundary.Failure(operation, "input_user_interrupted", effectObserved: true);
            bool changed = after is { } later
                && later.Hwnd == captured.Hwnd
                && !string.Equals(later.Sha256, captured.Sha256, StringComparison.Ordinal);
            if (!changed)
                return effectBoundary.Failure(operation, "scroll_surface_unchanged", effectObserved: true);
            bool restored = burst.Restore();
            return ExternalJson.Success(
                operation,
                Result(direction, amount, index, "win32_wheel_surface_postread", burst: (burst.WaitedMs, restored)),
                true);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            return effectBoundary.Failure(operation, "scroll_receipt_invalid");
        }
    }

    /// <summary>
    /// The element named <paramref name="label"/> brought into view in the mission's window by UI Automation alone:
    /// no wheel, no pointer, no front (the window may stay behind the person's). Only inside a mission's window; the
    /// pages bound the worker's page-by-page search (<paramref name="amount"/> × 4). Verified when the element is
    /// re-read visible; one already visible is verified without moving anything (<c>method</c> «already»).
    /// </summary>
    private async ValueTask<ExternalCapabilityReceipt> RevealAsync(
        string operation, string label, string direction, int amount, nint window, CancellationToken cancellationToken)
    {
        // A window that is gone answers from the worker before anything moves.
        if (window == 0 || _reveal is null)
            return ExternalJson.FailureBeforeEffect(operation, "scroll_argument_invalid");
        var effectBoundary = new ExternalEffectBoundary();
        effectBoundary.Cross(cancellationToken);
        using JsonDocument? answer = await _reveal(window, label, direction, amount * 4, cancellationToken).ConfigureAwait(false);
        if (answer is null)
            return effectBoundary.Failure(operation, "scroll_receipt_invalid");
        JsonElement root = answer.RootElement;
        string method = root.TryGetProperty("method", out JsonElement how) && how.ValueKind == JsonValueKind.String
            ? how.GetString() ?? string.Empty
            : string.Empty;
        bool visible = root.TryGetProperty("visible", out JsonElement shown) && shown.ValueKind == JsonValueKind.True;
        if (!root.TryGetProperty("ok", out JsonElement ok) || ok.ValueKind != JsonValueKind.True || !visible)
        {
            string error = root.TryGetProperty("error", out JsonElement value) && value.ValueKind == JsonValueKind.String
                ? value.GetString() ?? string.Empty
                : string.Empty;
            // Only a search that turned pages moved anything; the others read the tree and failed before an effect.
            ExternalCapabilityReceipt missing = method.Length > 0
                ? effectBoundary.Failure(operation, "reveal_not_found", effectObserved: true)
                : ExternalJson.FailureBeforeEffect(operation, error is "active_window_not_found" ? error : "reveal_not_found");
            // Auditoría C10: the rows whose name only holds the label were brought to no view; their names go back.
            return root.TryGetProperty("candidates", out JsonElement candidates) && candidates.ValueKind == JsonValueKind.Array
                ? missing with { Result = ExternalJson.Create(writer =>
                {
                    writer.WriteStartObject();
                    writer.WritePropertyName("candidates");
                    candidates.WriteTo(writer);
                    writer.WriteEndObject();
                }) }
                : missing;
        }

        string name = root.TryGetProperty("name", out JsonElement found) && found.ValueKind == JsonValueKind.String
            ? found.GetString() ?? label
            : label;
        bool moved = method != "already";
        UiaFrontReport? keeper = UiaFrontReport.Read(root);
        return ExternalJson.Success(
            operation,
            ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteBoolean("ok", true);
                writer.WriteString("direction", direction);
                writer.WriteNumber("amount", amount);
                writer.WriteString("label", name);
                writer.WriteString("method", method);
                writer.WriteBoolean("revealed", moved);
                writer.WriteBoolean("surfaceChanged", moved);
                keeper?.Write(writer);
                writer.WriteString("authority", "uia_reveal_visible_postread");
                writer.WriteNull("error");
                writer.WriteEndObject();
            }),
            moved);
    }

    // The viewed control's own ScrollPattern; null when it has none (the wheel at its centre takes over).
    private async ValueTask<ExternalCapabilityReceipt?> ScrollPatternAsync(
        string operation,
        nint window,
        string controlId,
        string direction,
        int amount,
        int index,
        CancellationToken cancellationToken)
    {
        var effectBoundary = new ExternalEffectBoundary();
        effectBoundary.Cross(cancellationToken);
        using JsonDocument? answer = await _controls!.ScrollControlAsync(
            window, controlId, direction, amount, cancellationToken).ConfigureAwait(false);
        if (answer is null)
            return effectBoundary.Failure(operation, "scroll_receipt_invalid");
        JsonElement root = answer.RootElement;
        if (!root.TryGetProperty("ok", out JsonElement ok) || ok.ValueKind != JsonValueKind.True)
        {
            string error = root.TryGetProperty("error", out JsonElement value) && value.ValueKind == JsonValueKind.String
                ? value.GetString() ?? string.Empty
                : string.Empty;
            // Nothing was moved: no pattern to scroll by, or the control is gone from the window.
            return error switch
            {
                "scroll_pattern_unavailable" => null,
                "visible_control_identity_stale" or "active_window_not_found" =>
                    ExternalJson.FailureBeforeEffect(operation, error),
                _ => effectBoundary.Failure(operation, "scroll_receipt_invalid"),
            };
        }

        bool scrolled = root.TryGetProperty("scrolled", out JsonElement moved) && moved.ValueKind == JsonValueKind.True;
        if (!scrolled)
            return effectBoundary.Failure(operation, "scroll_surface_unchanged", effectObserved: true);
        return ExternalJson.Success(
            operation,
            Result(direction, amount, index, "uia_scroll_pattern_percent_postread", root),
            true);
    }

    internal static JsonElement Result(
        string direction,
        int amount,
        int? index,
        string authority,
        JsonElement? pattern = null,
        (long WaitedMs, bool Restored)? burst = null) =>
        ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteBoolean("ok", true);
            writer.WriteString("direction", direction);
            writer.WriteNumber("amount", amount);
            if (index is int position)
                writer.WriteNumber("index", position);
            // A scroll percentage that moved is content that moved in the window: the mission counts it as a change.
            writer.WriteBoolean("surfaceChanged", true);
            if (pattern is { } read)
            {
                writer.WriteBoolean("scrolled", true);
                if (read.TryGetProperty("percentBefore", out JsonElement percentBefore))
                {
                    writer.WritePropertyName("percentBefore");
                    percentBefore.WriteTo(writer);
                }

                if (read.TryGetProperty("percentAfter", out JsonElement percentAfter))
                {
                    writer.WritePropertyName("percentAfter");
                    percentAfter.WriteTo(writer);
                }

                // What moved was a container holding the control (the whole page), not the control itself.
                if (read.TryGetProperty("container", out JsonElement container)
                    && container.ValueKind is JsonValueKind.True or JsonValueKind.False)
                    writer.WriteBoolean("container", container.ValueKind == JsonValueKind.True);

                UiaFrontReport.Read(read)?.Write(writer);
            }

            if (burst is { } lease)
            {
                writer.WriteNumber("waitedMs", lease.WaitedMs);
                writer.WriteBoolean("restored", lease.Restored);
            }

            writer.WriteString("authority", authority);
            writer.WriteEndObject();
        });

    [LibraryImport("user32.dll")]
    private static partial void mouse_event(
        uint flags, uint dx, uint dy, uint data, nuint extra);
}
