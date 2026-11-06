using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.Json.Serialization;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Clipboard;

namespace Baxy.Core.Operations;

internal static class ClipboardHandlers
{
    public static IOperationHandler[] Create(IClipboardProvider provider) =>
    [
        new ClipboardReadTextHandler(provider),
        new ClipboardWriteTextHandler(provider),
    ];
}

internal abstract class ClipboardHandlerBase(IClipboardProvider provider) : IOperationHandler
{
    protected IClipboardProvider Provider { get; } =
        provider ?? throw new ArgumentNullException(nameof(provider));

    public abstract OperationDefinition Definition { get; }

    public async ValueTask<OperationOutcome> ExecuteAsync(
        OperationInvocation invocation,
        CancellationToken cancellationToken)
    {
        try
        {
            return await ExecuteCoreAsync(invocation, cancellationToken).ConfigureAwait(false);
        }
        catch (JsonException)
        {
            return OperationOutcome.InvalidArguments(Definition, invocation.Arguments);
        }
        catch (ClipboardProviderException exception)
        {
            return OperationOutcome.Failure(
                exception.Code,
                result: HoldsFacts(exception.Holds),
                effectMayHaveOccurred: exception.EffectMayHaveOccurred);
        }
    }

    // B11: a clipboard with no text is not told as an empty one. An empty one adds nothing to the code it always had.
    private static JsonElement? HoldsFacts(ClipboardHolds? holds)
    {
        if (holds is null)
            return null;
        var facts = new JsonObject { ["holds"] = holds.Kind };
        if (holds.Count is { } count)
            facts["count"] = count;
        using JsonDocument document = JsonDocument.Parse(facts.ToJsonString());
        return document.RootElement.Clone();
    }

    protected abstract ValueTask<OperationOutcome> ExecuteCoreAsync(
        OperationInvocation invocation,
        CancellationToken cancellationToken);

    protected static T Parse<T>(
        JsonElement arguments,
        System.Text.Json.Serialization.Metadata.JsonTypeInfo<T> typeInfo)
        where T : class =>
        JsonSerializer.Deserialize(arguments, typeInfo)
        ?? throw new JsonException("Arguments cannot be null.");
}

internal sealed class ClipboardReadTextHandler(IClipboardProvider provider)
    : ClipboardHandlerBase(provider)
{
    public override OperationDefinition Definition { get; } =
        ProductCatalog.CreateDefinition("clipboard.read.text");

    protected override async ValueTask<OperationOutcome> ExecuteCoreAsync(
        OperationInvocation invocation,
        CancellationToken cancellationToken)
    {
        ClipboardReadArguments arguments = Parse(
            invocation.Arguments,
            CoreJsonContext.Default.ClipboardReadArguments);
        ClipboardTextSnapshot snapshot = await Provider.ReadTextAsync(
            arguments.MaxCharacters ?? 6_000,
            cancellationToken).ConfigureAwait(false);
        // Banco de uso 05-11 (S07): what the model reads is the clipboard without what its owner marked private or what looks
        // like a key by its form, and it says so; a paste goes on with the real text, which never passes through the model.
        int secretParts = 0;
        string shown = snapshot.MarkedPrivate ? SecretShape.Shown : SecretShape.Mask(snapshot.Text, out secretParts);
        var result = new ClipboardReadResult(
            shown,
            snapshot.CharacterCount,
            snapshot.Truncated,
            snapshot.SequenceNumber,
            secretParts > 0 ? SecretLike(secretParts) : null,
            snapshot.MarkedPrivate ? MarkedPrivate : null);
        return OperationOutcome.Success(JsonSerializer.SerializeToElement(
            result,
            CoreJsonContext.Default.ClipboardReadResult));
    }

    private const string MarkedPrivate = "the application that copied this marked it to be left out of clipboard monitors, as "
        + "password managers do: its text is not given here, so it is not read aloud; say that";

    private static string SecretLike(int parts) =>
        $"«{SecretShape.Shown}» stands for {(parts == 1 ? "1 part that looks" : $"{parts} parts that look")} like a key or a "
        + "password by the form: the characters are not given here, so they are not read aloud; say that they are there";
}

internal sealed class ClipboardWriteTextHandler(IClipboardProvider provider)
    : ClipboardHandlerBase(provider)
{
    public override OperationDefinition Definition { get; } =
        ProductCatalog.CreateDefinition("clipboard.write.text");

    protected override async ValueTask<OperationOutcome> ExecuteCoreAsync(
        OperationInvocation invocation,
        CancellationToken cancellationToken)
    {
        ClipboardWriteArguments arguments = Parse(
            invocation.Arguments,
            CoreJsonContext.Default.ClipboardWriteArguments);
        ClipboardWriteResult written = await Provider.WriteTextAsync(
            arguments.Text,
            cancellationToken).ConfigureAwait(false);
        ClipboardTextSnapshot observed;
        try
        {
            observed = await Provider.ReadTextAsync(
                Math.Max(arguments.Text.Length, 1),
                cancellationToken).ConfigureAwait(false);
        }
        catch (ClipboardProviderException exception)
        {
            // Round A: the text was written; a read-back that did not answer does not undo it.
            return OperationOutcome.Failure(exception.Code, effectMayHaveOccurred: true);
        }

        // Revisión 2026-10-22 (C-6): the read-back is bounded by the written text's length, so a longer text the
        // clipboard holds comes back cut to it (truncated); it is not the text written.
        if (observed.Truncated || !string.Equals(observed.Text, arguments.Text, StringComparison.Ordinal))
        {
            return OperationOutcome.Failure(
                "verification_failed",
                effectMayHaveOccurred: true);
        }

        var result = new ClipboardWriteOutcome(
            written.SequenceNumber,
            written.CharacterCount,
            written.Changed);
        return OperationOutcome.Success(JsonSerializer.SerializeToElement(
            result,
            CoreJsonContext.Default.ClipboardWriteOutcome));
    }
}

internal sealed record ClipboardReadArguments(int? MaxCharacters);

internal sealed record ClipboardWriteArguments(string Text);

internal sealed record ClipboardReadResult(
    string Text,
    int CharacterCount,
    bool Truncated,
    uint SequenceNumber,
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)] string? SecretLike,
    [property: JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)] string? MarkedPrivate);

internal sealed record ClipboardWriteOutcome(
    uint SequenceNumber,
    int CharacterCount,
    bool Changed);
