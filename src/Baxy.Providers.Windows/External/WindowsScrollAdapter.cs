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
/// </summary>
internal sealed partial class WindowsScrollAdapter : IExternalOperationAdapter
{
    private const uint MouseEventWheel = 0x0800;
    private const int WheelDelta = 120;

    private readonly WindowsVisibleControlAdapter? _controls;

    internal WindowsScrollAdapter(WindowsVisibleControlAdapter? controls = null)
    {
        _controls = controls;
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
        try
        {
            direction = ExternalJson.RequiredString(arguments, "direction");
            amount = ExternalJson.OptionalInt(arguments, "amount", 3);
            if (arguments.TryGetProperty("index", out JsonElement indexValue)
                && indexValue.ValueKind != JsonValueKind.Null)
            {
                if (indexValue.ValueKind != JsonValueKind.Number || !indexValue.TryGetInt32(out int requested))
                    throw new InvalidDataException("The control index is not an integer.");
                index = requested;
            }
        }
        catch (InvalidDataException)
        {
            return ExternalJson.FailureBeforeEffect(operation, "scroll_argument_invalid");
        }

        if (direction is not ("down" or "up") || amount is < 1 or > 10)
            return ExternalJson.FailureBeforeEffect(operation, "scroll_argument_invalid");

        // The window and the point the wheel is aimed at: the viewed control's centre on its view's window, or the
        // centre of the window a person acts on.
        nint window = 0;
        VisibleControlSurface.CapturedWindow? before;
        (int X, int Y)? aim = null;
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
                if (!VisibleControlSurface.ForegroundIs(window))
                    VisibleControlSurface.BringToFront(window);
                before = await VisibleControlSurface.CaptureAsync(window, cancellationToken).ConfigureAwait(false);
            }
            else
            {
                before = await VisibleControlSurface.CaptureForegroundAsync(cancellationToken)
                    .ConfigureAwait(false);
            }
        }
        catch (Exception exception) when (exception is IOException or InvalidOperationException)
        {
            before = null;
        }

        if (before is not { } captured)
            return ExternalJson.FailureBeforeEffect(operation, "active_window_not_found");

        var effectBoundary = new ExternalEffectBoundary();
        try
        {
            (int x, int y) = aim ?? (captured.Left + captured.Width / 2, captured.Top + captured.Height / 2);
            effectBoundary.Cross(cancellationToken);
            _ = SetCursorPos(x, y);
            int delta = direction == "down" ? -WheelDelta : WheelDelta;
            for (int step = 0; step < amount; step++)
            {
                mouse_event(MouseEventWheel, 0, 0, unchecked((uint)delta), 0);
                await Task.Delay(40, cancellationToken).ConfigureAwait(false);
            }

            // La superficie se compara tras un respiro: la ventana redibuja
            // después del último evento de rueda, no durante.
            await Task.Delay(350, cancellationToken).ConfigureAwait(false);
            VisibleControlSurface.CapturedWindow? after = null;
            try
            {
                after = await VisibleControlSurface.CaptureAsync(captured.Hwnd, cancellationToken)
                    .ConfigureAwait(false);
            }
            catch (Exception exception) when (exception is IOException or InvalidOperationException)
            {
                after = null;
            }

            bool changed = after is { } later
                && later.Hwnd == captured.Hwnd
                && !string.Equals(later.Sha256, captured.Sha256, StringComparison.Ordinal);
            if (!changed)
                return effectBoundary.Failure(operation, "scroll_surface_unchanged", effectObserved: true);

            return ExternalJson.Success(operation, Result(direction, amount, index, "win32_wheel_surface_postread"), true);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            return effectBoundary.Failure(operation, "scroll_receipt_invalid");
        }
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

    private static JsonElement Result(
        string direction,
        int amount,
        int? index,
        string authority,
        JsonElement? pattern = null) =>
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
            }

            writer.WriteString("authority", authority);
            writer.WriteEndObject();
        });

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool SetCursorPos(int x, int y);

    [LibraryImport("user32.dll")]
    private static partial void mouse_event(
        uint flags, uint dx, uint dy, uint data, nuint extra);
}
