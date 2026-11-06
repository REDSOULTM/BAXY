using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.External;
using Baxy.Providers.Windows.Windows;

namespace Baxy.Core.Operations;

/// <summary>
/// BAXY Renew cu (C18): clipboard.paste.into pastes the clipboard into a new document of the application it names: the
/// application is opened by app.open (in front, for control, a new document) and the clipboard is pasted into the window
/// it verified, by clipboard.paste. An opening that fails pastes nothing. The model pasted into whatever was in front and
/// never opened the application first; an optional application in clipboard.paste it left out, in three runs.
/// Encargo 94: a window open under the name takes the paste as it is, with nothing opened, and a browser is never opened
/// for it: the document is then the PC's text editor (<see cref="PasteDestinations"/>), and the receipt says which.
/// </summary>
internal sealed class PasteIntoNewDocumentHandler(
    IOperationHandler paste,
    Func<OperationInvocation, CancellationToken, ValueTask<OperationOutcome>> open,
    Func<string, CancellationToken, ValueTask<OfficePasteResult?>>? office = null,
    IInvocationPreflight? openPreflight = null,
    Func<string, CancellationToken, ValueTask<PasteDestination>>? destination = null,
    Func<IReadOnlyList<(string Process, string Title)>>? desktop = null)
    : IOperationHandler, IInvocationPreflight
{
    // As many as a window.resolve that matched nothing lists.
    private const int OpenWindowsLimit = WindowResolveHandler.CandidateLimit;

    // Revisión del núcleo (q-core): the opening this paste makes is app.open's, and so is its guard. Called straight, the
    // engine never read app.open's preflight: «pega en Configuración del sistema» launched msconfig with no yes, the
    // tool the guarda msconfig asks for. The application named is read by app.open's own preflight, bound to this one.
    private readonly IInvocationPreflight? _openPreflight = openPreflight;

    public bool MayRaise(JsonElement arguments) => _openPreflight is not null;

    public ValueTask<InvocationPreflightResult> PreflightAsync(
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        if (_openPreflight is null
            || arguments.ValueKind != JsonValueKind.Object
            || !arguments.TryGetProperty("appId", out JsonElement named)
            || named.ValueKind != JsonValueKind.String
            || named.GetString() is not { Length: > 0 } application)
        {
            return ValueTask.FromResult(InvocationPreflightResult.Proceed);
        }

        return _openPreflight.PreflightAsync(
            JsonSerializer.SerializeToElement(
                new OpenApplicationArguments(application, Foreground: true, ForControl: true, NewDocument: true),
                CoreJsonContext.Default.OpenApplicationArguments),
            cancellationToken);
    }

    // BAXY Renew cu (C18 variante): Word or Excel already running takes its new document and the paste through its own
    // object model (OfficeNewDocumentPaste); null for any other application or a closed one (the ordinary way).
    private readonly Func<string, CancellationToken, ValueTask<OfficePasteResult?>> _office =
        office ?? ((_, _) => ValueTask.FromResult<OfficePasteResult?>(null));

    private readonly Func<string, CancellationToken, ValueTask<PasteDestination>> _destination =
        destination ?? ((name, _) => ValueTask.FromResult(PasteDestination.NewDocument(name)));

    private readonly Func<IReadOnlyList<(string Process, string Title)>> _desktop = desktop ?? DesktopWindowNames.Visible;

    private readonly IOperationHandler _paste = paste ?? throw new ArgumentNullException(nameof(paste));
    private readonly Func<OperationInvocation, CancellationToken, ValueTask<OperationOutcome>> _open =
        open ?? throw new ArgumentNullException(nameof(open));

    public OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition("clipboard.paste.into");

    public async ValueTask<OperationOutcome> ExecuteAsync(
        OperationInvocation invocation,
        CancellationToken cancellationToken)
    {
        if (invocation.Arguments.ValueKind != JsonValueKind.Object
            || !invocation.Arguments.TryGetProperty("appId", out JsonElement named)
            || named.ValueKind != JsonValueKind.String
            || named.GetString() is not { Length: > 0 } asked)
        {
            return OperationOutcome.InvalidArguments(Definition, invocation.Arguments);
        }

        PasteDestination where = await _destination(asked, cancellationToken).ConfigureAwait(false);
        // Nothing was opened: the paste's own receipt names the window that took it (sentTo), and its failure is the answer.
        if (where.Window > 0)
            return await PasteAsync(invocation, where.Window, cancellationToken).ConfigureAwait(false);
        if (where.Application is not { } application)
        {
            return OperationOutcome.Failure("paste_no_text_editor", Facts(new JsonObject
            {
                ["openWindows"] = OpenWindows(),
                ["next"] = $"{WireNames.Of("clipboard.paste.into")} with appId set to the title of one of openWindows pastes "
                    + $"into that window; this call opened nothing and pasted nothing: {asked} is a web browser, which is "
                    + "not opened for a paste, and this PC has no program set for plain text",
            }));
        }

        if (await _office(application, cancellationToken).ConfigureAwait(false) is { } inOffice)
        {
            return inOffice.Verified
                ? OperationOutcome.Success(JsonSerializer.SerializeToElement(
                    new PastedIntoOffice(1, application, inOffice.Document ?? string.Empty, inOffice.Characters, NewDocument: true),
                    CoreJsonContext.Default.PastedIntoOffice))
                : OperationOutcome.Failure(inOffice.ErrorCode ?? "paste_not_read_back", effectMayHaveOccurred: inOffice.EffectObserved);
        }

        OperationOutcome opened = await _open(
            new OperationInvocation(
                invocation.RequestId,
                invocation.MissionId,
                invocation.InvocationId + ":open",
                JsonSerializer.SerializeToElement(
                    new OpenApplicationArguments(application, Foreground: true, ForControl: true, NewDocument: true),
                    CoreJsonContext.Default.OpenApplicationArguments)),
            cancellationToken).ConfigureAwait(false);
        if (!opened.Succeeded)
        {
            // Nothing was pasted: the opening's own refusal (the names closest to one that matched none) is the answer.
            // Live (encargo 94): told only that a new document was not made, the model opened the browser itself by app_open.
            return OperationOutcome.Failure(
                opened.ErrorCode ?? "paste_application_not_opened",
                result: where.InsteadOfBrowser
                    ? BrowserNotOpened(opened.Result, application, asked, $"nothing was pasted: the new document of {application}, "
                        + $"this PC's plain text editor, was not made; {asked} was not opened: it is a web browser, which is not "
                        + "opened for a paste")
                    : opened.ErrorCode == "app_not_found" ? NameUnknown(opened.Result, asked, where.TextEditor) : opened.Result,
                effectMayHaveOccurred: opened.EffectMayHaveOccurred,
                causeCode: "paste_application_not_opened");
        }

        // Auditoría del Core (w8): the paste names the window the opening verified. With no window it went to whatever
        // held the front, and the opening does not always leave its window there: asked in front while the person works
        // in another window it is raised without their keyboard (ShownWithoutFocus), Windows may refuse the front, and
        // the person may click elsewhere meanwhile; the clipboard then went into their own document or chat. Named, the
        // mission's lease brings that window up after the person's pause, or nothing is sent (input_window_not_in_front).
        if (opened.Result is not { ValueKind: JsonValueKind.Object } facts
            || !facts.TryGetProperty("windowHandle", out JsonElement handle)
            || handle.ValueKind != JsonValueKind.Number
            || !handle.TryGetInt64(out long window)
            || window <= 0)
        {
            return OperationOutcome.Failure(
                "verification_failed",
                result: opened.Result,
                effectMayHaveOccurred: true,
                causeCode: "paste_window_unknown");
        }

        OperationOutcome pasted = await PasteAsync(invocation, window, cancellationToken).ConfigureAwait(false);
        if (pasted.Succeeded)
        {
            return where.InsteadOfBrowser
                ? OperationOutcome.Success(BrowserNotOpened(pasted.Result, application, asked, $"it went into a new document of "
                    + $"{application}, this PC's plain text editor; {asked} was not opened: it is a web browser, which is not "
                    + "opened for a paste"))
                : pasted;
        }

        // Renew al máximo (w5): the application was opened before the paste failed (an empty clipboard is refused before
        // any key): the failure says so, with an effect that did occur, never «nothing happened» with a new window open.
        return OperationOutcome.Failure(
            pasted.ErrorCode ?? "paste_not_verified",
            result: Opened(pasted.Result, application),
            effectMayHaveOccurred: true,
            causeCode: pasted.CauseCode);
    }

    private ValueTask<OperationOutcome> PasteAsync(OperationInvocation invocation, long window, CancellationToken cancellationToken)
    {
        using JsonDocument target = JsonDocument.Parse($$"""{"window":{{window}}}""");
        return _paste.ExecuteAsync(
            new OperationInvocation(
                invocation.RequestId, invocation.MissionId, invocation.InvocationId, target.RootElement.Clone()),
            cancellationToken);
    }

    // The receipt says the editor and the browser that was not opened, which the reply would otherwise leave out (a flag
    // alone made the model invent the cause: encargo 59).
    private static JsonElement BrowserNotOpened(JsonElement? result, string editor, string browser, string next)
    {
        JsonObject facts = FactsOf(result);
        facts["textEditor"] = editor;
        facts["browserNotOpened"] = browser;
        facts["next"] = next;
        return Facts(facts);
    }

    private JsonElement NameUnknown(JsonElement? result, string asked, string? editor)
    {
        JsonObject facts = FactsOf(result);
        facts["openWindows"] = OpenWindows();
        if (editor is not null)
            facts["textEditor"] = editor;
        string nothing = $"this call pasted nothing: no open window and no installed application answers to «{asked}»";
        string newDocument = editor is null ? string.Empty
            : $"; if the person wants a new document: {WireNames.Call("clipboard.paste.into", new JsonObject { ["appId"] = editor })} "
                + $"makes it in {editor}, this PC's plain text editor";
        // A title that holds the name: the call first, with its argument written (encargos 20, 28 and 34), and what this one
        // did at the end. With none the fact comes first: led by the editor's call, the model pasted into a new document.
        facts["next"] = TitleHolding(asked) is { } title
            ? $"{WireNames.Call("clipboard.paste.into", new JsonObject { ["appId"] = title })} pastes into that window, whose title "
                + $"holds «{asked}»{newDocument}; {nothing}"
            : $"{nothing}; with appId set to the title of one of openWindows it pastes into that window{newDocument}";
        return Facts(facts);
    }

    private string? TitleHolding(string asked) =>
        _desktop().Select(static window => window.Title).FirstOrDefault(title =>
            title.Contains(asked.Trim(), StringComparison.OrdinalIgnoreCase)) is { } found
            ? found.EndsWith(DesktopWindowNames.MinimizedMark, StringComparison.Ordinal)
                ? found[..^DesktopWindowNames.MinimizedMark.Length]
                : found
            : null;

    private JsonArray OpenWindows()
    {
        var windows = new JsonArray();
        foreach ((string process, string title) in _desktop().Take(OpenWindowsLimit))
            windows.Add((JsonNode)new JsonObject { ["title"] = title, ["process"] = process });
        return windows;
    }

    private static JsonObject FactsOf(JsonElement? result) =>
        result is { ValueKind: JsonValueKind.Object } read && JsonNode.Parse(read.GetRawText()) is JsonObject facts ? facts : [];

    private static JsonElement Facts(JsonObject facts)
    {
        using JsonDocument document = JsonDocument.Parse(facts.ToJsonString());
        return document.RootElement.Clone();
    }

    private static JsonElement Opened(JsonElement? result, string application)
    {
        var buffer = new System.Buffers.ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            if (result is { ValueKind: JsonValueKind.Object } read)
            {
                foreach (JsonProperty property in read.EnumerateObject())
                {
                    if (property.Name != "applicationOpened")
                        property.WriteTo(writer);
                }
            }

            writer.WriteString("applicationOpened", application);
            writer.WriteEndObject();
        }

        using JsonDocument document = JsonDocument.Parse(buffer.WrittenMemory);
        return document.RootElement.Clone();
    }
}
