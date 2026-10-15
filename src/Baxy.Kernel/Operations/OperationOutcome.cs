using System.Text.Json;

namespace Baxy.Kernel.Operations;

public sealed record OperationOutcome(
    bool Succeeded,
    bool Verified,
    JsonElement? Result,
    string? ErrorCode)
{
    public bool Retryable { get; private init; }

    public bool EffectMayHaveOccurred { get; private init; }

    public string? CauseCode { get; private init; }

    internal bool ProtectedPrivateResult { get; private init; }

    public static OperationOutcome Success(JsonElement? result = null) =>
        new(true, true, result, null);

    public static OperationOutcome PrivateSuccess(JsonElement protectedResult)
    {
        if (protectedResult.ValueKind != JsonValueKind.Object)
        {
            throw new ArgumentException(
                "A protected private result must be a JSON object.",
                nameof(protectedResult));
        }

        return new OperationOutcome(true, true, protectedResult, null)
        {
            ProtectedPrivateResult = true,
        };
    }

    public static OperationOutcome Failure(
        string errorCode,
        JsonElement? result = null,
        bool effectMayHaveOccurred = false,
        string? causeCode = null) =>
        new(false, false, result, errorCode)
        {
            EffectMayHaveOccurred = effectMayHaveOccurred,
            CauseCode = causeCode,
        };

    public static OperationOutcome RetryableFailure(
        string errorCode,
        JsonElement? result = null,
        bool effectMayHaveOccurred = false,
        string? causeCode = null) =>
        new(false, false, result, errorCode)
        {
            Retryable = true,
            EffectMayHaveOccurred = effectMayHaveOccurred,
            CauseCode = causeCode,
        };

    public override string ToString() =>
        $"{nameof(OperationOutcome)} {{ Succeeded = {Succeeded}, Verified = {Verified}, "
        + $"Result = [REDACTED], ErrorCode = {ErrorCode}, Retryable = {Retryable}, "
        + $"EffectMayHaveOccurred = {EffectMayHaveOccurred}, CauseCode = {CauseCode}, "
        + $"ProtectedPrivateResult = {ProtectedPrivateResult} }}";
}
