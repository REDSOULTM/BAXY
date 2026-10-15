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

internal sealed class AppCloseHandler(IWindowControlProvider provider) : IOperationHandler, IInvocationRiskAssessor
{
    public OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition("app.close");

    // v3 r6 lectores (t2-r4 c04-5 «ya quedó, cierra configuración porfa» → «¿Quieres confirmar…?»): a window that holds
    // no document of the person (data: documentless_applications.v1.json) closes as a low reversible act; any other
    // window, or one the provider cannot place, keeps work_loss and asks. v3 r22 uso real: the provider also counts
    // an application whose content lives in the person's account and a window BAXY launched and never wrote into.
    public OperationRisk? AssessInvocationRisk(JsonElement arguments) =>
        arguments.ValueKind == JsonValueKind.Object
        && arguments.TryGetProperty("windowId", out JsonElement windowId)
        && windowId.ValueKind == JsonValueKind.String
        && provider.HoldsNoDocument(windowId.GetString()!)
            ? OperationRisk.Reversible
            : null;

    public async ValueTask<OperationOutcome> ExecuteAsync(OperationInvocation invocation, CancellationToken cancellationToken)
    {
        string windowId = invocation.Arguments.GetProperty("windowId").GetString()!;
        WindowCloseResult result = await provider.CloseAsync(windowId, cancellationToken).ConfigureAwait(false);
        if (result.ClosePrompted && result.Verified && result.ProcessId is not null)
        {
            // v3 r22 uso real: the application answered the polite close with a dialog of its own (it asks whether
            // to save). The window is still there and BAXY never answers that dialog; the receipt says so.
            return OperationOutcome.Failure(
                WindowControlErrorCodes.ClosePrompted,
                result: Receipt(result.ProcessId.Value, windowClosed: false, closePrompted: true));
        }

        if (!result.Succeeded || !result.Verified || result.ProcessId is null)
        {
            return OperationOutcome.Failure(result.ErrorCode ?? "app_close_failed");
        }

        // Auditoría D7: «closed» only for a window that went away after BAXY's close; one already gone, or hidden instead
        // of closed, says so.
        return OperationOutcome.Success(Receipt(
            result.ProcessId.Value, windowClosed: result.Outcome == WindowCloseOutcomes.Closed, closePrompted: false,
            result.Title, result.Outcome));
    }

    private static JsonElement Receipt(
        int processId, bool windowClosed, bool closePrompted, string? title = null, string? outcome = null)
    {
        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteNumber("processId", processId);
            writer.WriteBoolean("windowClosed", windowClosed);
            if (outcome == WindowCloseOutcomes.AlreadyGone)
            {
                writer.WriteBoolean("alreadyGone", true);
            }

            if (outcome == WindowCloseOutcomes.Hidden)
            {
                writer.WriteBoolean("hidden", true);
            }

            // Encargo H1 (tandas fin1/fin2 t2-c03 t2): what it closed, as Windows wrote the window's title; the final
            // names it from here, never from the request.
            if (!string.IsNullOrWhiteSpace(title))
            {
                writer.WriteString("title", title);
            }

            if (closePrompted)
            {
                writer.WriteBoolean("closePrompted", true);
            }

            writer.WriteEndObject();
        }
        using JsonDocument document = JsonDocument.Parse(buffer.WrittenMemory);
        return document.RootElement.Clone();
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
            // Auditoría D7: never counted as closed.
            writer.WriteNumber("hidden", result.Hidden);
            writer.WriteNumber("alreadyGone", result.AlreadyGone);
            writer.WriteNumber("remainingVisible", result.Remaining);
            writer.WriteNumber("keptOpen", result.Kept);
            writer.WriteStartArray("keptProcesses");
            foreach (string name in result.KeptProcesses) writer.WriteStringValue(name);
            writer.WriteEndArray();
            writer.WriteStartArray("remainingProcesses");
            foreach (string name in result.RemainingProcesses) writer.WriteStringValue(name);
            writer.WriteEndArray();
            writer.WriteBoolean("allClosed", result.Remaining == 0 && result.Hidden == 0);
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
            ? OperationOutcome.Success(WindowControlResultJson.Serialize(
                result.Window, side, result.LargerThanRequested))
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

    public static JsonElement Serialize(
        WindowCandidate window,
        string side,
        WindowRequestedSize? largerThanRequested = null)
    {
        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("side", side);
            writer.WritePropertyName("window");
            WriteCandidate(writer, window);
            if (largerThanRequested is not null)
            {
                // M159 (DEV-I v4w I-s048): the window is flush against the asked side but
                // its own minimum is larger than the half; the half it was asked to take
                // is said beside the size it keeps, never «the half» alone.
                writer.WriteBoolean("fitsInHalf", false);
                if (window.Width > largerThanRequested.Width)
                    writer.WriteNumber("halfWidth", largerThanRequested.Width);
                if (window.Height > largerThanRequested.Height)
                    writer.WriteNumber("halfHeight", largerThanRequested.Height);
            }
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
        if (window.Owned)
            writer.WriteBoolean("owned", true);
        if (window.ZOrder is int zOrder)
            writer.WriteNumber("zOrder", zOrder);
        if (window.Topmost)
            writer.WriteBoolean("topmost", true);
        if (window.WorkAreaWidth is int workWidth && window.WorkAreaHeight is int workHeight)
        {
            writer.WriteNumber("workAreaWidth", workWidth);
            writer.WriteNumber("workAreaHeight", workHeight);
        }
        writer.WriteEndObject();
    }
}
