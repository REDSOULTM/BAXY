using System.Buffers;
using System.Text.Json;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Applications;
using Baxy.Providers.Windows.Windows;

namespace Baxy.Core.Operations;

internal sealed class WindowResolveHandler(
    IWindowControlProvider provider,
    Func<IReadOnlyList<(string Process, string Title)>>? desktop = null,
    Func<(string Name, string Process)?>? browser = null) : IOperationHandler
{
    // How many of the desktop's windows go back with a name that matched nothing (as a look's NamedWindowCandidateLimit).
    internal const int CandidateLimit = 20;

    private readonly Func<IReadOnlyList<(string Process, string Title)>> _desktop = desktop ?? DesktopWindowNames.Visible;
    private readonly Func<(string Name, string Process)?> _browser = browser ?? DesktopWindowNames.PersonBrowser;

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
            // Al máximo, flujos (P252, 22 of 27 runs: «pon esta ventana a la izquierda» → window.resolve {}): with no
            // selector, the person's window in front (BAXY's own left out) is window_active's, as a fact.
            return !hasApplication && !hasProcess
                && Baxy.Providers.Windows.Infrastructure.ModelAids.On(Baxy.Providers.Windows.Infrastructure.ModelAids.SelectorNext)
                ? OperationOutcome.Failure(WindowControlErrorCodes.InvalidSelector, NoSelector())
                : OperationOutcome.Failure(WindowControlErrorCodes.InvalidSelector);
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
        if (result.Succeeded && result.Verified)
        {
            JsonElement found = WindowControlResultJson.Serialize(result.Windows, result.Page);
            // BAXY Renew cu (C13 en el PC): a browser asked by its name may be another than the person's own (a Chrome
            // in full screen chosen for «el navegador», the person's being Opera GX): which one theirs is goes with it.
            return OperationOutcome.Success(hasApplication
                && Baxy.Providers.Windows.Infrastructure.ModelAids.On(Baxy.Providers.Windows.Infrastructure.ModelAids.WindowCandidates)
                ? WithPersonBrowser(found, result.Windows, _browser())
                : found);
        }
        string code = result.ErrorCode ?? "window_resolve_failed";
        // BAXY Renew cu (C13): «Microsoft Word» is no installed name (it is «Word») and the browser open was another
        // than the one guessed; the reply said neither was open. The windows on the desktop go back, as a look's.
        return hasApplication && code is ApplicationOpenErrorCodes.ApplicationNotFound or WindowControlErrorCodes.WindowNotFound
            && Baxy.Providers.Windows.Infrastructure.ModelAids.On(Baxy.Providers.Windows.Infrastructure.ModelAids.WindowCandidates)
            ? OperationOutcome.Failure(code, Candidates(_desktop(), _browser()))
            : OperationOutcome.Failure(code);
    }

    private static JsonElement NoSelector()
    {
        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteString("next", "window_resolve takes exactly one selector, applicationName or process; the window "
                + "the person has in front (BAXY's own left out) and its windowId are given by window_active");
            writer.WriteEndObject();
        }

        using JsonDocument document = JsonDocument.Parse(buffer.WrittenMemory);
        return document.RootElement.Clone();
    }

    // The processes of web browsers, by their executables (identity of the program, never what the person said).
    private static readonly HashSet<string> BrowserProcesses = new(StringComparer.OrdinalIgnoreCase)
    {
        "chrome", "msedge", "brave", "opera", "firefox", "vivaldi",
    };

    internal static JsonElement WithPersonBrowser(
        JsonElement found, IReadOnlyList<WindowCandidate> windows, (string Name, string Process)? browser)
    {
        if (browser is not { } own || windows.Count == 0
            || !windows.All(window => BrowserProcesses.Contains(window.ProcessName))
            || windows.Any(window => string.Equals(window.ProcessName, own.Process, StringComparison.OrdinalIgnoreCase)))
        {
            return found;
        }

        var facts = (System.Text.Json.Nodes.JsonObject)System.Text.Json.Nodes.JsonNode.Parse(found.GetRawText())!;
        facts["personBrowser"] = new System.Text.Json.Nodes.JsonObject { ["name"] = own.Name, ["process"] = own.Process };
        facts["next"] = $"these are windows of {windows[0].ProcessName}; the person's own browser (Windows' default) is "
            + $"{own.Name} (process {own.Process})";
        using JsonDocument document = JsonDocument.Parse(facts.ToJsonString());
        return document.RootElement.Clone();
    }

    internal static JsonElement Candidates(
        IReadOnlyList<(string Process, string Title)> windows, (string Name, string Process)? browser)
    {
        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteNumber("candidateCount", windows.Count);
            if (windows.Count > CandidateLimit)
                writer.WriteBoolean("truncated", true);
            writer.WriteStartArray("candidates");
            foreach ((string process, string title) in windows.Take(CandidateLimit))
            {
                writer.WriteStartObject();
                writer.WriteString("title", title);
                writer.WriteString("process", process);
                writer.WriteEndObject();
            }

            writer.WriteEndArray();
            // «El navegador» is the person's own: which one it is, so a browser window among them is recognized.
            if (browser is { } own)
            {
                writer.WriteStartObject("personBrowser");
                writer.WriteString("name", own.Name);
                writer.WriteString("process", own.Process);
                writer.WriteEndObject();
            }

            writer.WriteString("next", "no window was found under that name; these are the windows open on the desktop "
                + "(top first): if the one meant is among them, resolve it again by its process, or by the application's "
                + "installed name" + (browser is { } named
                    ? $"; the person's web browser is {named.Name} (process {named.Process})"
                    : string.Empty));
            writer.WriteEndObject();
        }

        using JsonDocument document = JsonDocument.Parse(buffer.WrittenMemory);
        return document.RootElement.Clone();
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
        if (result.Succeeded && result.Verified && result.Window is not null && result.AlreadyReached)
        {
            // Ronda final: already as asked, nothing sent: the model reads changed:false.
            var unchanged = (System.Text.Json.Nodes.JsonObject)System.Text.Json.Nodes.JsonNode.Parse(
                WindowControlResultJson.Serialize(result.Window).GetRawText())!;
            unchanged["changed"] = false;
            using JsonDocument document = JsonDocument.Parse(unchanged.ToJsonString());
            return OperationOutcome.Success(document.RootElement.Clone());
        }

        return result.Succeeded && result.Verified && result.Window is not null
            ? OperationOutcome.Success(WindowControlResultJson.Serialize(result.Window))
            : WindowControlResultJson.Failure(
                result.ErrorCode ?? "window_action_failed", result.EffectMayHaveOccurred, result.StateAfter);
    }
}

internal sealed class AppCloseHandler(IWindowControlProvider provider) : IOperationHandler, IInvocationPreflight
{
    public OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition("app.close");

    // v3 r6 lectores (t2-r4 c04-5 «ya quedó, cierra configuración porfa» → «¿Quieres confirmar…?»): a window that holds
    // no document of the person (data: documentless_applications.v1.json) closes as a low reversible act; any other
    // window, or one the provider cannot place, keeps work_loss and asks. v3 r22 uso real: the provider also counts
    // an application whose content lives in the person's account and a window BAXY launched and never wrote into.
    // Al máximo, flujos: an application asked for by its name that has no window to close (app_not_running) is that
    // failure before any yes; one all of whose windows hold no document closes as one such window does («cierra
    // discord» asked every time), and one window with a document, or one the provider cannot place, keeps the yes.
    public async ValueTask<InvocationPreflightResult> PreflightAsync(
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        if (arguments.ValueKind != JsonValueKind.Object)
            return InvocationPreflightResult.Proceed;
        if (arguments.TryGetProperty("windowId", out JsonElement windowId) && windowId.ValueKind == JsonValueKind.String)
        {
            return provider.HoldsNoDocument(windowId.GetString()!)
                ? InvocationPreflightResult.Lowered(OperationRisk.Reversible)
                : InvocationPreflightResult.Proceed;
        }

        if (!arguments.TryGetProperty("appId", out JsonElement appId) || appId.ValueKind != JsonValueKind.String
            || !ApplicationIds.IsValidRequest(appId.GetString()!))
            return InvocationPreflightResult.Proceed;
        ApplicationWindows found = await ApplicationWindowCloser.ResolveAsync(provider, appId.GetString()!, cancellationToken)
            .ConfigureAwait(false);
        if (found.ErrorCode is { } missing)
        {
            return InvocationPreflightResult.Fails(found.Background.Count == 0
                ? OperationOutcome.Failure(missing)
                : OperationOutcome.Failure(missing, ApplicationReceipt(appId.GetString()!,
                    new ApplicationWindowsClosed(missing, 0, found.Background, [], false, 0, 0))));
        }
        return found.Windows.All(window => provider.HoldsNoDocument(window.WindowId))
            ? InvocationPreflightResult.Lowered(OperationRisk.Reversible)
            : InvocationPreflightResult.Proceed;
    }

    public async ValueTask<OperationOutcome> ExecuteAsync(OperationInvocation invocation, CancellationToken cancellationToken)
    {
        // Auditoría de los pedidos reales (2026-10-17): exactly one of windowId (a window resolved before) and appId (the
        // application by its name, whose windows are resolved here: the 4B model invented windowId «1» instead of
        // resolving the window first).
        JsonElement arguments = invocation.Arguments;
        bool byWindow = arguments.TryGetProperty("windowId", out JsonElement windowValue)
            && windowValue.ValueKind == JsonValueKind.String;
        bool byApplication = arguments.TryGetProperty("appId", out JsonElement appValue)
            && appValue.ValueKind == JsonValueKind.String;
        if (byWindow == byApplication)
        {
            return OperationOutcome.InvalidArguments(Definition, arguments, ArgumentProblem.ExactlyOneOf("appId", "windowId"));
        }

        if (byApplication)
        {
            return await CloseApplicationAsync(appValue.GetString()!, cancellationToken).ConfigureAwait(false);
        }

        string windowId = windowValue.GetString()!;
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
            return WindowControlResultJson.Failure(
                result.ErrorCode ?? "app_close_failed", result.EffectMayHaveOccurred, result.StateAfter);
        }

        // Auditoría D7: «closed» only for a window that went away after BAXY's close; one already gone, or hidden instead
        // of closed, says so.
        return OperationOutcome.Success(Receipt(
            result.ProcessId.Value, windowClosed: result.Outcome == WindowCloseOutcomes.Closed, closePrompted: false,
            result.Title, result.Outcome));
    }

    private async ValueTask<OperationOutcome> CloseApplicationAsync(string appId, CancellationToken cancellationToken)
    {
        if (!ApplicationIds.IsValidRequest(appId))
        {
            return OperationOutcome.Failure("invalid_application");
        }

        ApplicationWindowsClosed closing = await ApplicationWindowCloser.CloseAllAsync(provider, appId, cancellationToken)
            .ConfigureAwait(false);
        if (closing.ErrorCode is { } stopped)
        {
            // Renew al máximo (auditoría de flujos): with no window, the processes running in the background are said.
            return closing.Frames == 0 && closing.ProcessIds.Count == 0
                ? OperationOutcome.Failure(stopped)
                : OperationOutcome.Failure(stopped, ApplicationReceipt(appId, closing),
                    effectMayHaveOccurred: closing.EffectMayHaveOccurred);
        }

        return OperationOutcome.Success(ApplicationReceipt(appId, closing));
    }

    private static JsonElement ApplicationReceipt(string appId, ApplicationWindowsClosed closing)
    {
        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteString("appId", appId);
            // FT/proveedores goal (review of receipts): how many windows the application had, so a close that stopped
            // at the first says how many were never tried; with none closed nor hidden (all gone meanwhile) nothing
            // changed.
            writer.WriteNumber("windows", closing.Frames);
            writer.WriteNumber("closedWindows", closing.ClosedWindows);
            if (closing.ErrorCode is null && closing.ClosedWindows == 0 && closing.HiddenWindows == 0)
                writer.WriteBoolean("changed", false);
            if (closing.HiddenWindows > 0)
            {
                // Windows that hid instead of closing (the application stays in the notification area).
                writer.WriteNumber("hiddenWindows", closing.HiddenWindows);
            }

            writer.WriteStartArray("processIds");
            foreach (int processId in closing.ProcessIds)
                writer.WriteNumberValue(processId);
            writer.WriteEndArray();
            writer.WriteStartArray("titles");
            foreach (string title in closing.Titles)
                writer.WriteStringValue(title);
            writer.WriteEndArray();
            if (closing.ErrorCode == WindowControlErrorCodes.ClosePrompted)
            {
                writer.WriteBoolean("closePrompted", true);
            }

            writer.WriteEndObject();
        }
        using JsonDocument document = JsonDocument.Parse(buffer.WrittenMemory);
        return document.RootElement.Clone();
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
            // FT/proveedores goal (review of receipts): nine of ten minimized and one that refused was a bare failure,
            // read as «could not minimize»; what was done travels with the failure, never as success.
            return OperationOutcome.Failure(
                result.ErrorCode ?? "window_minimize_all_failed",
                result: result.Minimized > 0 ? PartialCounts(result) : null,
                effectMayHaveOccurred: result.EffectMayHaveOccurred || result.Minimized > 0);
        }

        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteNumber("desktopWindows", result.Found);
            writer.WriteNumber("minimized", result.Minimized);
            writer.WriteNumber("remainingVisible", result.Remaining);
            if (result.Gone > 0)
                writer.WriteNumber("goneMeanwhile", result.Gone);
            // Auditoría final (regla 3): a desktop window that was there and not read leaves «all» unsaid.
            if (result.Unread > 0) writer.WriteNumber("unreadWindows", result.Unread);
            // Ronda final 11 (regla 3): windows Windows hides (another desktop) were not minimized: no «all».
            if (result.Cloaked > 0) writer.WriteNumber("cloakedWindows", result.Cloaked);
            if (result.Unread == 0 && result.Cloaked == 0) writer.WriteBoolean("allMinimized", true);
            // Auditoría final (regla 3): nothing was sent to (no window to minimize, none gone meanwhile), so the
            // desktop was already that way; a window that hid itself when sent the minimize was changed by it.
            if (result.Minimized == 0 && result.Gone == 0)
                writer.WriteBoolean("changed", false);
            writer.WriteString("authority", "win32_desktop_windows_postread");
            writer.WriteEndObject();
        }
        using JsonDocument document = JsonDocument.Parse(buffer.WrittenMemory);
        return OperationOutcome.Success(document.RootElement.Clone());
    }
    private static JsonElement PartialCounts(WindowMinimizeAllResult result)
    {
        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            writer.WriteNumber("desktopWindows", result.Found);
            writer.WriteNumber("minimized", result.Minimized);
            writer.WriteNumber("remainingVisible", result.Remaining);
            writer.WriteEndObject();
        }
        using JsonDocument document = JsonDocument.Parse(buffer.WrittenMemory);
        return document.RootElement.Clone();
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
            // Round A: what is kept open is BAXY's own windows (keptProcesses names them), never an editor of the
            // person's; the «editorKeptOpen» that said so is gone.
            writer.WriteNumber("keptOpen", result.Kept);
            writer.WriteStartArray("keptProcesses");
            foreach (string name in result.KeptProcesses) writer.WriteStringValue(name);
            writer.WriteEndArray();
            writer.WriteStartArray("remainingProcesses");
            foreach (string name in result.RemainingProcesses) writer.WriteStringValue(name);
            writer.WriteEndArray();
            if (result.Unread > 0) writer.WriteNumber("unreadWindows", result.Unread);
            // Ronda final 11 (regla 3): windows Windows hides (another desktop) were not closed: no «all».
            if (result.Cloaked > 0) writer.WriteNumber("cloakedWindows", result.Cloaked);
            // Renew al máximo: a protected window (a terminal, an editor, a system tool) is never asked to close and
            // stays open, yet allClosed said true beside it. BAXY's own windows are not counted among the protected.
            if (result.Unread == 0 && result.Cloaked == 0)
                writer.WriteBoolean(
                    "allClosed", result.Remaining == 0 && result.Hidden == 0 && result.ProtectedKept == 0);
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
            ? OperationOutcome.Success(WindowControlResultJson.Unchanged(
                WindowControlResultJson.Serialize(result.Window), result.AlreadyReached))
            : WindowControlResultJson.Failure(
                result.ErrorCode ?? "window_bounds_failed", result.EffectMayHaveOccurred, result.StateAfter);
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
            ? OperationOutcome.Success(WindowControlResultJson.Unchanged(WindowControlResultJson.Serialize(
                result.Window, side, result.LargerThanRequested), result.AlreadyReached))
            : WindowControlResultJson.SpentWindowId(result.ErrorCode ?? string.Empty) ?? OperationOutcome.Failure(
                result.ErrorCode ?? "window_bounds_failed", effectMayHaveOccurred: result.EffectMayHaveOccurred);
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

    // Ronda final: the window already was as asked and nothing was sent: the model reads changed:false.
    public static JsonElement Unchanged(JsonElement result, bool alreadyReached)
    {
        if (!alreadyReached)
            return result;
        var unchanged = (System.Text.Json.Nodes.JsonObject)System.Text.Json.Nodes.JsonNode.Parse(result.GetRawText())!;
        unchanged["changed"] = false;
        // BAXY Renew cu (C13 en el PC): «changed false» was read as a failure («Word no se pudo poner a la derecha»).
        unchanged["next"] = "it already was so: done, nothing needed to change";
        using JsonDocument document = JsonDocument.Parse(unchanged.ToJsonString());
        return document.RootElement.Clone();
    }

    // Auditoría de falsedades (F001, nb-t2-C s0): a windowId is used up by the window action it is given to (the action
    // gives back a new one) and ends after 5 minutes. A window.focus with the id of an earlier focus failed
    // invalid_or_expired_window_id with Steam still open, and BAXY told «la ventana se cerró». The failure says what
    // the code means and that the window itself was neither touched nor read; the code stays.
    internal const string SpentWindowIdNext = "nothing was done to the window: this windowId cannot be used again (each "
        + "window action uses up the windowId it is given and gives back a new one, and any windowId ends after 5 "
        + "minutes); the window itself was not looked at, so whether it is still open is not known: window_resolve "
        + "gives its windowId now if it is";

    public static OperationOutcome? SpentWindowId(string errorCode)
    {
        if (errorCode != WindowControlErrorCodes.InvalidOrExpiredWindowId
            || !Baxy.Providers.Windows.Infrastructure.ModelAids.On(Baxy.Providers.Windows.Infrastructure.ModelAids.WindowIdSpent))
            return null;
        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteString("next", SpentWindowIdNext);
            writer.WriteEndObject();
        }
        using JsonDocument document = JsonDocument.Parse(buffer.WrittenMemory);
        return OperationOutcome.Failure(errorCode, document.RootElement.Clone());
    }

    // Renew al máximo (8.3): an ambiguous failure (the act reached the window and its verification did not hold)
    // carries the window as the provider's one read found it after, so the mind can say how it stayed instead of a
    // bare «could not». Still a failure with its code and uncertainty; without that read, the bare failure.
    public static OperationOutcome Failure(string errorCode, bool effectMayHaveOccurred, WindowStateAfter? stateAfter)
    {
        if (SpentWindowId(errorCode) is { } spent)
            return spent;
        if (!effectMayHaveOccurred || stateAfter is null)
            return OperationOutcome.Failure(errorCode, effectMayHaveOccurred: effectMayHaveOccurred);
        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteStartObject("stateAfter");
            writer.WriteBoolean("present", stateAfter.Present);
            writer.WriteBoolean("hidden", stateAfter.Hidden);
            // A window gone, or hidden, has no state nor bounds read: only what the read gave is said.
            if (stateAfter.State is not null) writer.WriteString("state", stateAfter.State);
            if (stateAfter.Foreground is bool foreground) writer.WriteBoolean("foreground", foreground);
            if (stateAfter.X is int x) writer.WriteNumber("x", x);
            if (stateAfter.Y is int y) writer.WriteNumber("y", y);
            if (stateAfter.Width is int width) writer.WriteNumber("width", width);
            if (stateAfter.Height is int height) writer.WriteNumber("height", height);
            writer.WriteBoolean("requestedStateReached", stateAfter.RequestedStateReached);
            writer.WriteString("authority", stateAfter.Authority);
            writer.WriteEndObject();
            writer.WriteEndObject();
        }
        using JsonDocument document = JsonDocument.Parse(buffer.WrittenMemory);
        return OperationOutcome.Failure(errorCode, document.RootElement.Clone(), effectMayHaveOccurred: true);
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
