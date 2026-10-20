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
    Func<string, CancellationToken, ValueTask<Baxy.Providers.Windows.External.OfficePasteResult?>>? office = null)
    : IOperationHandler
{
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
            return OperationOutcome.Failure("invalid_arguments");
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

        using JsonDocument empty = JsonDocument.Parse("{}");
        return await _paste.ExecuteAsync(
            new OperationInvocation(
                invocation.RequestId, invocation.MissionId, invocation.InvocationId, empty.RootElement.Clone()),
            cancellationToken).ConfigureAwait(false);
    }
}
