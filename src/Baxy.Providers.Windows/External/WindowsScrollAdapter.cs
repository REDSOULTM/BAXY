using System.Runtime.InteropServices;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// <c>input.scroll</c> (CONTRATO_VISTA_ACCION.md §2): scrolls the foreground
/// window with the wheel, aimed at its centre, and counts the step only when
/// the visible surface changed; a panel already at the top or the bottom does
/// not change and says so (<c>scroll_surface_unchanged</c>) instead of faking
/// the movement. Inherited from the parked Fase 4 draft (opus/fase4-wip) and
/// bound to the window resolution the view uses.
/// </summary>
internal sealed partial class WindowsScrollAdapter : IExternalOperationAdapter
{
    private const uint MouseEventWheel = 0x0800;
    private const int WheelDelta = 120;

    public bool CanHandle(string operation) => operation is "input.scroll";

    public async ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        string direction;
        int amount;
        try
        {
            direction = ExternalJson.RequiredString(arguments, "direction");
            amount = ExternalJson.OptionalInt(arguments, "amount", 3);
        }
        catch (InvalidDataException)
        {
            return ExternalJson.FailureBeforeEffect(operation, "scroll_argument_invalid");
        }

        if (direction is not ("down" or "up") || amount is < 1 or > 10)
            return ExternalJson.FailureBeforeEffect(operation, "scroll_argument_invalid");

        VisibleControlSurface.CapturedWindow? before;
        try
        {
            before = await VisibleControlSurface.CaptureForegroundAsync(cancellationToken)
                .ConfigureAwait(false);
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
            int centerX = captured.Left + captured.Width / 2;
            int centerY = captured.Top + captured.Height / 2;
            effectBoundary.Cross(cancellationToken);
            _ = SetCursorPos(centerX, centerY);
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
            VisibleControlSurface.Delete(after?.Path);
            if (!changed)
                return effectBoundary.Failure(operation, "scroll_surface_unchanged", effectObserved: true);

            JsonElement result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteBoolean("ok", true);
                writer.WriteString("direction", direction);
                writer.WriteNumber("amount", amount);
                writer.WriteBoolean("surfaceChanged", true);
                writer.WriteString("authority", "win32_wheel_surface_postread");
                writer.WriteEndObject();
            });
            return ExternalJson.Success(operation, result, true);
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            return effectBoundary.Failure(operation, "scroll_receipt_invalid");
        }
        finally
        {
            VisibleControlSurface.Delete(captured.Path);
        }
    }

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool SetCursorPos(int x, int y);

    [LibraryImport("user32.dll")]
    private static partial void mouse_event(
        uint flags, uint dx, uint dy, uint data, nuint extra);
}
