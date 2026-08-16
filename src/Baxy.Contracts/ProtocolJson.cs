using System.Text.Json;
using System.Text.Json.Serialization.Metadata;

namespace Baxy.Contracts;

public static class ProtocolJson
{
    public static byte[] SerializeToUtf8Bytes(ProtocolHello value)
    {
        ContractValidator.Validate(value);
        return JsonSerializer.SerializeToUtf8Bytes(value, BaxyJsonContext.Default.ProtocolHello);
    }

    public static byte[] SerializeToUtf8Bytes(OperationRequest value)
    {
        ContractValidator.Validate(value);
        return JsonSerializer.SerializeToUtf8Bytes(value, BaxyJsonContext.Default.OperationRequest);
    }

    public static byte[] SerializeToUtf8Bytes(OperationResponse value)
    {
        ContractValidator.Validate(value);
        return JsonSerializer.SerializeToUtf8Bytes(value, BaxyJsonContext.Default.OperationResponse);
    }

    public static byte[] SerializeToUtf8Bytes(ProtocolError value)
    {
        ContractValidator.Validate(value);
        return JsonSerializer.SerializeToUtf8Bytes(value, BaxyJsonContext.Default.ProtocolError);
    }

    /// <summary>
    /// Serializes a response that has to travel inside a single bounded protocol
    /// line. A response whose evidence payload alone exceeds the line limit is
    /// re-serialized without <see cref="OperationResponse.Result"/> so the
    /// decision, its stable error code and
    /// <see cref="OperationResponse.EffectMayHaveOccurred"/> still reach the
    /// shell: writing an oversized line instead would leave an already executed
    /// effect without any correlated answer.
    /// </summary>
    /// <exception cref="JsonException">
    /// The response cannot fit inside <paramref name="maximumLineBytes"/> even
    /// after its evidence payload is elided.
    /// </exception>
    public static byte[] SerializeBoundedToUtf8Bytes(
        OperationResponse value,
        int maximumLineBytes)
    {
        ArgumentOutOfRangeException.ThrowIfNegativeOrZero(maximumLineBytes);

        byte[] message = SerializeToUtf8Bytes(value);
        if (message.Length <= maximumLineBytes)
        {
            return message;
        }

        byte[] bounded = SerializeToUtf8Bytes(value with { Result = null });
        return bounded.Length <= maximumLineBytes
            ? bounded
            : throw new JsonException(
                "Invalid BAXY protocol message: the response exceeds its line limit "
                + "even without evidence.");
    }

    public static ProtocolHello DeserializeHello(ReadOnlySpan<byte> utf8Json) =>
        DeserializeAndValidate(utf8Json, BaxyJsonContext.Default.ProtocolHello, ContractValidator.Validate);

    public static OperationRequest DeserializeRequest(ReadOnlySpan<byte> utf8Json) =>
        DeserializeAndValidate(utf8Json, BaxyJsonContext.Default.OperationRequest, ContractValidator.Validate);

    public static OperationResponse DeserializeResponse(ReadOnlySpan<byte> utf8Json) =>
        DeserializeAndValidate(utf8Json, BaxyJsonContext.Default.OperationResponse, ContractValidator.Validate);

    public static ProtocolError DeserializeError(ReadOnlySpan<byte> utf8Json) =>
        DeserializeAndValidate(utf8Json, BaxyJsonContext.Default.ProtocolError, ContractValidator.Validate);

    private static T DeserializeAndValidate<T>(
        ReadOnlySpan<byte> utf8Json,
        JsonTypeInfo<T> typeInfo,
        Action<T> validate)
        where T : class
    {
        var value = JsonSerializer.Deserialize(utf8Json, typeInfo)
            ?? throw new JsonException("BAXY protocol message cannot be null.");

        validate(value);
        return value;
    }
}
