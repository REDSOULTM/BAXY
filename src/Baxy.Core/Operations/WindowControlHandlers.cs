using System.Buffers;
using System.Text.Json;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Windows;

namespace Baxy.Core.Operations;

internal sealed class WindowResolveHandler(IWindowControlProvider provider) : IOperationHandler
{
    public OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition("window.resolve");

    public async ValueTask<OperationOutcome> ExecuteAsync(OperationInvocation invocation, CancellationToken cancellationToken)
    {
        string process = invocation.Arguments.GetProperty("process").GetString()!;
        int limit = invocation.Arguments.TryGetProperty("limit", out JsonElement value) ? value.GetInt32() : 20;
        WindowResolveResult result = await provider.ResolveAsync(process, limit, cancellationToken).ConfigureAwait(false);
        return result.Succeeded && result.Verified
            ? OperationOutcome.Success(WindowControlResultJson.Serialize(result.Windows))
            : OperationOutcome.Failure(result.ErrorCode ?? "window_resolve_failed");
    }
}

internal sealed class WindowActiveHandler(IWindowControlProvider provider) : IOperationHandler
{
    public OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition("window.active");

    public async ValueTask<OperationOutcome> ExecuteAsync(
        OperationInvocation invocation,
        CancellationToken cancellationToken)
    {
        WindowResolveResult result = await provider.ResolveForegroundAsync(cancellationToken)
            .ConfigureAwait(false);
        return result.Succeeded && result.Verified
            ? OperationOutcome.Success(WindowControlResultJson.Serialize(result.Windows))
            : OperationOutcome.Failure(result.ErrorCode ?? "window_active_failed");
    }
}

internal sealed class WindowActionHandler(string operation, WindowControlAction action, IWindowControlProvider provider)
    : IOperationHandler
{
    public OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition(operation);

    public async ValueTask<OperationOutcome> ExecuteAsync(OperationInvocation invocation, CancellationToken cancellationToken)
    {
        string windowId = invocation.Arguments.GetProperty("windowId").GetString()!;
        WindowActionResult result = await provider.ExecuteAsync(windowId, action, cancellationToken).ConfigureAwait(false);
        return result.Succeeded && result.Verified && result.Window is not null
            ? OperationOutcome.Success(WindowControlResultJson.Serialize(result.Window))
            : OperationOutcome.Failure(result.ErrorCode ?? "window_action_failed");
    }
}

internal sealed class AppCloseHandler(IWindowControlProvider provider) : IOperationHandler
{
    public OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition("app.close");

    public async ValueTask<OperationOutcome> ExecuteAsync(OperationInvocation invocation, CancellationToken cancellationToken)
    {
        string windowId = invocation.Arguments.GetProperty("windowId").GetString()!;
        WindowCloseResult result = await provider.CloseAsync(windowId, cancellationToken).ConfigureAwait(false);
        if (!result.Succeeded || !result.Verified || result.ProcessId is null)
        {
            return OperationOutcome.Failure(result.ErrorCode ?? "app_close_failed");
        }

        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteNumber("processId", result.ProcessId.Value);
            writer.WriteBoolean("windowClosed", true);
            writer.WriteEndObject();
        }
        using JsonDocument document = JsonDocument.Parse(buffer.WrittenMemory);
        return OperationOutcome.Success(document.RootElement.Clone());
    }
}

internal sealed class WindowBoundsHandler(string operation, IWindowControlProvider provider)
    : IOperationHandler
{
    public OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition(operation);

    public async ValueTask<OperationOutcome> ExecuteAsync(
        OperationInvocation invocation,
        CancellationToken cancellationToken)
    {
        string windowId = invocation.Arguments.GetProperty("windowId").GetString()!;
        bool move = string.Equals(operation, "window.move", StringComparison.Ordinal);
        WindowActionResult result = await provider.SetBoundsAsync(
            windowId,
            move ? invocation.Arguments.GetProperty("x").GetInt32() : null,
            move ? invocation.Arguments.GetProperty("y").GetInt32() : null,
            move ? null : invocation.Arguments.GetProperty("width").GetInt32(),
            move ? null : invocation.Arguments.GetProperty("height").GetInt32(),
            cancellationToken).ConfigureAwait(false);
        return result.Succeeded && result.Verified && result.Window is not null
            ? OperationOutcome.Success(WindowControlResultJson.Serialize(result.Window))
            : OperationOutcome.Failure(result.ErrorCode ?? "window_bounds_failed");
    }
}

internal static class WindowControlHandlers
{
    public static IOperationHandler[] Create(IWindowControlProvider provider) =>
    [
        new AppCloseHandler(provider),
        new WindowActiveHandler(provider),
        new WindowActionHandler("window.focus", WindowControlAction.Focus, provider),
        new WindowActionHandler("window.maximize", WindowControlAction.Maximize, provider),
        new WindowActionHandler("window.minimize", WindowControlAction.Minimize, provider),
        new WindowBoundsHandler("window.move", provider),
        new WindowBoundsHandler("window.resize", provider),
        new WindowResolveHandler(provider),
        new WindowActionHandler("window.restore", WindowControlAction.Restore, provider),
    ];
}

internal static class WindowControlResultJson
{
    public static JsonElement Serialize(IReadOnlyList<WindowCandidate> windows)
    {
        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WritePropertyName("windows");
            writer.WriteStartArray();
            foreach (WindowCandidate window in windows) WriteCandidate(writer, window);
            writer.WriteEndArray();
            writer.WriteNumber("count", windows.Count);
            writer.WriteEndObject();
        }
        using JsonDocument document = JsonDocument.Parse(buffer.WrittenMemory);
        return document.RootElement.Clone();
    }

    public static JsonElement Serialize(WindowCandidate window)
    {
        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WritePropertyName("window");
            WriteCandidate(writer, window);
            writer.WriteEndObject();
        }
        using JsonDocument document = JsonDocument.Parse(buffer.WrittenMemory);
        return document.RootElement.Clone();
    }

    private static void WriteCandidate(Utf8JsonWriter writer, WindowCandidate window)
    {
        writer.WriteStartObject();
        writer.WriteString("windowId", window.WindowId);
        writer.WriteNumber("processId", window.ProcessId);
        writer.WriteString("processName", window.ProcessName);
        writer.WriteString("state", window.State);
        writer.WriteBoolean("foreground", window.Foreground);
        writer.WriteNumber("x", window.X);
        writer.WriteNumber("y", window.Y);
        writer.WriteNumber("width", window.Width);
        writer.WriteNumber("height", window.Height);
        writer.WriteEndObject();
    }
}
