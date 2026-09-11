using System.Buffers;
using System.Text.Json;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Capture;

namespace Baxy.Core.Operations;

internal sealed class ScreenshotCaptureHandler(
    IScreenshotProvider provider,
    string operation = "capture.screenshot",
    bool activeWindow = false) : IOperationHandler
{
    public OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition(operation);

    public async ValueTask<OperationOutcome> ExecuteAsync(
        OperationInvocation invocation,
        CancellationToken cancellationToken)
    {
        CaptureResult result;
        if (activeWindow)
            result = await provider.CaptureActiveWindowAsync(cancellationToken).ConfigureAwait(false);
        else
            result = await provider.CaptureAsync(cancellationToken).ConfigureAwait(false);
        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("captureId", result.CaptureId); writer.WriteNumber("width", result.Width);
            writer.WriteNumber("height", result.Height); writer.WriteString("sha256", result.Sha256);
            writer.WriteString("scope", activeWindow ? "active_window" : "virtual_screen");
            writer.WriteString("createdAtUtc", result.CreatedAtUtc);
            if (result.ActiveWindow is { } window)
            {
                writer.WriteStartObject("activeWindow");
                writer.WriteNumber("windowHandle", window.WindowHandle);
                writer.WriteNumber("processId", window.ProcessId);
                writer.WriteString("processCreatedAtUtc", window.ProcessCreatedAtUtc);
                WriteBounds(writer, "windowBounds", window.WindowBounds);
                WriteBounds(writer, "captureBounds", window.CaptureBounds);
                writer.WriteBoolean("isClipped", window.IsClipped);
                writer.WriteString("captureStartedAtUtc", window.CaptureStartedAtUtc);
                writer.WriteString("captureCompletedAtUtc", window.CaptureCompletedAtUtc);
                writer.WriteEndObject();
            }
            writer.WriteEndObject();
        }
        using JsonDocument document = JsonDocument.Parse(buffer.WrittenMemory);
        return OperationOutcome.Success(document.RootElement.Clone());
    }

    private static void WriteBounds(Utf8JsonWriter writer, string name, CaptureBounds bounds)
    {
        writer.WriteStartObject(name);
        writer.WriteNumber("left", bounds.Left); writer.WriteNumber("top", bounds.Top);
        writer.WriteNumber("width", bounds.Width); writer.WriteNumber("height", bounds.Height);
        writer.WriteEndObject();
    }
}
