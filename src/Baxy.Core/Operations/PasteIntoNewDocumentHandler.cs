using System.Text.Json;
using Baxy.Kernel.Operations;

namespace Baxy.Core.Operations;

/// <summary>
/// BAXY Renew cu (C18): clipboard.paste.into pastes the clipboard into a new document of the application it names: the
/// application is opened by app.open (in front, for control, a new document) and the clipboard is pasted into the window
/// it verified, by clipboard.paste. An opening that fails pastes nothing. The model pasted into whatever was in front and
/// never opened the application first; an optional application in clipboard.paste it left out, in three runs.
/// </summary>
internal sealed class PasteIntoNewDocumentHandler(
    IOperationHandler paste,
    Func<OperationInvocation, CancellationToken, ValueTask<OperationOutcome>> open,
    Func<string, CancellationToken, ValueTask<Baxy.Providers.Windows.External.OfficePasteResult?>>? office = null,
    IInvocationPreflight? openPreflight = null)
    : IOperationHandler, IInvocationPreflight
{
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
    private readonly Func<string, CancellationToken, ValueTask<Baxy.Providers.Windows.External.OfficePasteResult?>> _office =
        office ?? ((_, _) => ValueTask.FromResult<Baxy.Providers.Windows.External.OfficePasteResult?>(null));

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
            || named.GetString() is not { Length: > 0 } application)
        {
            return OperationOutcome.InvalidArguments(Definition, invocation.Arguments);
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
            return OperationOutcome.Failure(
                opened.ErrorCode ?? "paste_application_not_opened",
                result: opened.Result,
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

        using JsonDocument target = JsonDocument.Parse($$"""{"window":{{window}}}""");
        OperationOutcome pasted = await _paste.ExecuteAsync(
            new OperationInvocation(
                invocation.RequestId, invocation.MissionId, invocation.InvocationId, target.RootElement.Clone()),
            cancellationToken).ConfigureAwait(false);
        if (pasted.Succeeded)
            return pasted;

        // Renew al máximo (w5): the application was opened before the paste failed (an empty clipboard is refused before
        // any key): the failure says so, with an effect that did occur, never «nothing happened» with a new window open.
        return OperationOutcome.Failure(
            pasted.ErrorCode ?? "paste_not_verified",
            result: Opened(pasted.Result, application),
            effectMayHaveOccurred: true,
            causeCode: pasted.CauseCode);
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
