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

    /// <summary>The arguments an invalid_arguments refusal names, as the kernel's validation names them.</summary>
    public IReadOnlyList<ArgumentProblem> ArgumentProblems { get; private init; } = [];

    /// <summary>
    /// P5.3: a handler's refusal of the call's arguments, never bare: what the catalog's schema refuses in them (a
    /// handler's own check of what its schema says) or, for arguments the schema takes, what the operation itself
    /// refuses (<paramref name="own"/>: exactly one of two, a pair given together).
    /// </summary>
    public static OperationOutcome InvalidArguments(
        OperationDefinition definition,
        JsonElement arguments,
        params IReadOnlyList<ArgumentProblem> own)
    {
        ArgumentNullException.ThrowIfNull(definition);
        IReadOnlyList<ArgumentProblem> bySchema = definition.ProductDescriptor is { } descriptor
            ? OperationArgumentValidator.Problems(arguments, descriptor.ArgumentsSchema)
            : [];
        return new OperationOutcome(false, false, null, "invalid_arguments")
        {
            ArgumentProblems = bySchema.Count > 0 ? bySchema : own,
        };
    }

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
