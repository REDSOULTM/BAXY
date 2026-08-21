using System.Text.Json;
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
            return OperationOutcome.Failure("invalid_arguments");
        }
        catch (ClipboardProviderException exception)
        {
            return OperationOutcome.Failure(exception.Code);
        }
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
            arguments.MaxCharacters ?? 8_192,
            cancellationToken).ConfigureAwait(false);
        var result = new ClipboardReadResult(
            snapshot.Text,
            snapshot.CharacterCount,
            snapshot.Truncated,
            snapshot.SequenceNumber);
        return OperationOutcome.Success(JsonSerializer.SerializeToElement(
            result,
            CoreJsonContext.Default.ClipboardReadResult));
    }
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
        ClipboardTextSnapshot observed = await Provider.ReadTextAsync(
            Math.Max(arguments.Text.Length, 1),
            cancellationToken).ConfigureAwait(false);
        if (!string.Equals(observed.Text, arguments.Text, StringComparison.Ordinal))
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
    uint SequenceNumber);

internal sealed record ClipboardWriteOutcome(
    uint SequenceNumber,
    int CharacterCount,
    bool Changed);
