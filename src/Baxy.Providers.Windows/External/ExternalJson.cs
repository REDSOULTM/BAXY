using System.Buffers;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

internal static class ExternalJson
{
    internal static JsonElement Create(Action<Utf8JsonWriter> write)
    {
        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            write(writer);
        }

        using JsonDocument document = JsonDocument.Parse(buffer.WrittenMemory);
        return document.RootElement.Clone();
    }

    internal static ExternalCapabilityReceipt Success(
        string operation,
        JsonElement result,
        bool effectObserved = true) =>
        new(operation, effectObserved, true, result, null);

    internal static ExternalCapabilityReceipt Failure(
        string operation,
        string errorCode,
        bool effectObserved = false) =>
        effectObserved
            ? FailureAfterEffect(operation, errorCode, effectObserved: true)
            : FailureBeforeEffect(operation, errorCode);

    internal static ExternalCapabilityReceipt FailureBeforeEffect(
        string operation,
        string errorCode) =>
        new(operation, false, false, null, errorCode);

    internal static ExternalCapabilityReceipt FailureAfterEffect(
        string operation,
        string errorCode,
        bool effectObserved = false) =>
        new(operation, effectObserved, false, null, errorCode)
        {
            EffectMayHaveOccurred = true,
        };

    internal static string RequiredString(JsonElement arguments, string name)
    {
        if (!arguments.TryGetProperty(name, out JsonElement value)
            || value.ValueKind != JsonValueKind.String
            || string.IsNullOrWhiteSpace(value.GetString()))
        {
            throw new InvalidDataException($"Missing string argument: {name}.");
        }

        return value.GetString()!;
    }

    internal static int OptionalInt(JsonElement arguments, string name, int fallback)
    {
        return arguments.TryGetProperty(name, out JsonElement value)
            && value.ValueKind == JsonValueKind.Number
            && value.TryGetInt32(out int result)
                ? result
                : fallback;
    }
}

internal sealed class ExternalEffectBoundary
{
    private bool _crossed;

    internal bool WasCrossed => _crossed;

    internal void Cross() => _crossed = true;

    internal void Cross(CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        _crossed = true;
    }

    internal ExternalCapabilityReceipt Failure(
        string operation,
        string errorCode,
        bool effectObserved = false) =>
        _crossed || effectObserved
            ? ExternalJson.FailureAfterEffect(operation, errorCode, effectObserved)
            : ExternalJson.FailureBeforeEffect(operation, errorCode);
}
