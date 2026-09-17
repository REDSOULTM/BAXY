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
        bool hasApplication = invocation.Arguments.TryGetProperty("applicationName", out JsonElement application);
        bool hasProcess = invocation.Arguments.TryGetProperty("process", out JsonElement process);
        // The flat public schema types each selector. Enforce their exclusive
        // semantics here before any OS read, including an explicit false byTitle.
        if (hasApplication == hasProcess
            || (hasApplication && (invocation.Arguments.TryGetProperty("byTitle", out _)
                || invocation.Arguments.TryGetProperty("offset", out _))))
        {
            return OperationOutcome.Failure(WindowControlErrorCodes.InvalidSelector);
        }
        int limit = invocation.Arguments.TryGetProperty("limit", out JsonElement value) ? value.GetInt32() : 20;
        int offset = invocation.Arguments.TryGetProperty("offset", out JsonElement offsetValue) ? offsetValue.GetInt32() : 0;
        bool byTitle = invocation.Arguments.TryGetProperty("byTitle", out JsonElement titleValue)
            && titleValue.GetBoolean();
        WindowResolveResult result = hasApplication
            ? await provider.ResolveApplicationAsync(application.GetString()!, limit, cancellationToken)
                .ConfigureAwait(false)
            : await provider.ResolveAsync(process.GetString()!, limit, cancellationToken, byTitle, offset)
                .ConfigureAwait(false);
        return result.Succeeded && result.Verified
            ? OperationOutcome.Success(WindowControlResultJson.Serialize(result.Windows, result.Page))
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

internal sealed class WindowMinimizeAllHandler(IWindowControlProvider provider) : IOperationHandler
{
    public OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition("window.minimize.all");

    public async ValueTask<OperationOutcome> ExecuteAsync(OperationInvocation invocation, CancellationToken cancellationToken)
    {
        WindowMinimizeAllResult result = await provider.MinimizeAllAsync(cancellationToken).ConfigureAwait(false);
        if (!result.Succeeded || !result.Verified)
        {
            return OperationOutcome.Failure(result.ErrorCode ?? "window_minimize_all_failed");
        }

        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteNumber("desktopWindows", result.Found);
            writer.WriteNumber("minimized", result.Minimized);
            writer.WriteNumber("remainingVisible", result.Remaining);
            writer.WriteBoolean("allMinimized", true);
            writer.WriteString("authority", "win32_desktop_windows_postread");
            writer.WriteEndObject();
        }
        using JsonDocument document = JsonDocument.Parse(buffer.WrittenMemory);
        return OperationOutcome.Success(document.RootElement.Clone());
    }
}

internal sealed class WindowCloseAllHandler(IWindowControlProvider provider) : IOperationHandler
{
    public OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition("window.close.all");

    public async ValueTask<OperationOutcome> ExecuteAsync(OperationInvocation invocation, CancellationToken cancellationToken)
    {
        WindowCloseAllResult result = await provider.CloseAllAsync(cancellationToken).ConfigureAwait(false);
        if (!result.Succeeded || !result.Verified)
        {
            return OperationOutcome.Failure(result.ErrorCode ?? "window_close_all_failed");
        }

        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteNumber("desktopWindows", result.Found);
            writer.WriteNumber("closed", result.Closed);
            writer.WriteNumber("remainingVisible", result.Remaining);
            writer.WriteNumber("keptOpen", result.Kept);
            writer.WriteStartArray("keptProcesses");
            foreach (string name in result.KeptProcesses) writer.WriteStringValue(name);
            writer.WriteEndArray();
            writer.WriteStartArray("remainingProcesses");
            foreach (string name in result.RemainingProcesses) writer.WriteStringValue(name);
            writer.WriteEndArray();
            writer.WriteBoolean("allClosed", result.Remaining == 0);
            writer.WriteBoolean("editorKeptOpen", result.Kept > 0);
            writer.WriteString("authority", "win32_desktop_windows_close_postread");
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

internal sealed class WindowSnapHandler(IWindowControlProvider provider) : IOperationHandler
{
    public OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition("window.snap");

    public async ValueTask<OperationOutcome> ExecuteAsync(
        OperationInvocation invocation,
        CancellationToken cancellationToken)
    {
        string windowId = invocation.Arguments.GetProperty("windowId").GetString()!;
        string side = invocation.Arguments.GetProperty("side").GetString()!;
        WindowActionResult result = await provider.SnapAsync(
            windowId, side, cancellationToken).ConfigureAwait(false);
        return result.Succeeded && result.Verified && result.Window is not null
            ? OperationOutcome.Success(WindowControlResultJson.Serialize(result.Window, side))
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
        new WindowMinimizeAllHandler(provider),
        new WindowCloseAllHandler(provider),
        new WindowBoundsHandler("window.move", provider),
        new WindowBoundsHandler("window.resize", provider),
        new WindowSnapHandler(provider),
        new WindowResolveHandler(provider),
        new WindowActionHandler("window.restore", WindowControlAction.Restore, provider),
    ];
}

internal static class WindowControlResultJson
{
    public static JsonElement Serialize(IReadOnlyList<WindowCandidate> windows, WindowInventoryPage? page = null)
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
            if (page is not null)
            {
                writer.WriteNumber("limit", page.Limit);
                writer.WriteNumber("offset", page.Offset);
                writer.WriteNumber("observedCount", page.ObservedCount);
                writer.WriteBoolean("complete", page.Complete);
                if (page.Complete) writer.WriteNumber("totalCount", page.ObservedCount);
                else writer.WriteNull("totalCount");
                writer.WriteBoolean("hasMore", page.NextOffset.HasValue);
                if (page.NextOffset is int nextOffset) writer.WriteNumber("nextOffset", nextOffset);
                else writer.WriteNull("nextOffset");
                writer.WriteString("observationScope", "visible_top_level_windows");
                writer.WriteString("pageConsistency", "fresh_enumeration_per_request");
            }
            writer.WriteEndObject();
        }
        using JsonDocument document = JsonDocument.Parse(buffer.WrittenMemory);
        return document.RootElement.Clone();
    }

    public static JsonElement Serialize(WindowCandidate window, string side)
    {
        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("side", side);
            writer.WritePropertyName("window");
            WriteCandidate(writer, window);
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
        if (window.Title is not null)
            writer.WriteString("title", window.Title);
        writer.WriteString("state", window.State);
        writer.WriteBoolean("foreground", window.Foreground);
        writer.WriteNumber("x", window.X);
        writer.WriteNumber("y", window.Y);
        writer.WriteNumber("width", window.Width);
        writer.WriteNumber("height", window.Height);
        writer.WriteEndObject();
    }
}
