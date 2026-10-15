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
        try
        {
            if (activeWindow)
                result = await provider.CaptureActiveWindowAsync(cancellationToken).ConfigureAwait(false);
            else
                result = await provider.CaptureAsync(cancellationToken).ConfigureAwait(false);
        }
        // A capture that cannot be taken is an operation failure, not a core
        // fault: an escaping exception ended baxy-core and left the App without
        // a kernel (2026-09-28, Steam's helper window parked off-screen held
        // the foreground). The provider never stores a partial image.
        catch (ScreenshotUnavailableException exception)
        {
            return OperationOutcome.Failure(exception.Code);
        }
        catch (Exception exception) when (
            exception is IOException or UnauthorizedAccessException or OverflowException)
        {
            return OperationOutcome.Failure(activeWindow
                ? "active_window_capture_failed"
                : "screen_capture_failed");
        }
        // Ronda 22: a capture the person asked to keep is also saved where they said (the catalog's known folder),
        // verified on disk; without «folder» it stays private. A copy that could not be saved is the request's
        // failure, never a capture told as kept.
        SavedCaptureCopy? saved = null;
        if (RequestedFolder(invocation) is { } folder)
        {
            try
            {
                saved = await provider.SaveCopyAsync(result.CaptureId, folder, cancellationToken).ConfigureAwait(false);
            }
            catch (ScreenshotUnavailableException exception)
            {
                return OperationOutcome.Failure(exception.Code);
            }
            catch (Exception exception) when (
                exception is IOException or UnauthorizedAccessException or NotSupportedException)
            {
                return OperationOutcome.Failure("capture_save_failed");
            }
        }
        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("captureId", result.CaptureId); writer.WriteNumber("width", result.Width);
            writer.WriteNumber("height", result.Height); writer.WriteString("sha256", result.Sha256);
            writer.WriteString("scope", activeWindow ? "active_window" : "virtual_screen");
            writer.WriteString("createdAtUtc", result.CreatedAtUtc);
            if (saved is not null)
            {
                writer.WriteString("savedFolder", saved.Folder);
                writer.WriteString("fileName", saved.FileName);
                writer.WriteString("savedSha256", saved.Sha256);
            }
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

    private static string? RequestedFolder(OperationInvocation? invocation) =>
        invocation is { Arguments.ValueKind: JsonValueKind.Object }
        && invocation.Arguments.TryGetProperty("folder", out JsonElement folder)
        && folder.ValueKind == JsonValueKind.String
        && folder.GetString() is { Length: > 0 } name
            ? name
            : null;

    private static void WriteBounds(Utf8JsonWriter writer, string name, CaptureBounds bounds)
    {
        writer.WriteStartObject(name);
        writer.WriteNumber("left", bounds.Left); writer.WriteNumber("top", bounds.Top);
        writer.WriteNumber("width", bounds.Width); writer.WriteNumber("height", bounds.Height);
        writer.WriteEndObject();
    }
}
