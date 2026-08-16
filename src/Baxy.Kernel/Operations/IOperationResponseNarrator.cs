namespace Baxy.Kernel.Operations;

public interface IOperationResponseNarrator
{
    string Narrate(string operation, OperationOutcome outcome);

    string NarrateStatus(string operation, string status, string? errorCode);
}

internal sealed class DefaultOperationResponseNarrator : IOperationResponseNarrator
{
    internal const string PrivateSuccessMessage =
        "Completé y verifiqué la petición sobre la memoria local.";
    internal const string PrivateFailureMessage =
        "No pude completar la petición sobre la memoria local.";

    internal static DefaultOperationResponseNarrator Instance { get; } = new();

    private DefaultOperationResponseNarrator()
    {
    }

    public string Narrate(string operation, OperationOutcome outcome)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(operation);
        ArgumentNullException.ThrowIfNull(outcome);
        if (operation.StartsWith("memory.", StringComparison.Ordinal))
        {
            return outcome.Succeeded && outcome.Verified
                ? PrivateSuccessMessage
                : PrivateFailureMessage;
        }

        return outcome.Succeeded && outcome.Verified
            ? "Completé y verifiqué la petición solicitada."
            : "No pude completar la petición solicitada.";
    }

    public string NarrateStatus(string operation, string status, string? errorCode)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(operation);
        ArgumentException.ThrowIfNullOrWhiteSpace(status);
        return operation.StartsWith("memory.", StringComparison.Ordinal)
            ? PrivateFailureMessage
            : string.Equals(status, Baxy.Contracts.OperationStatuses.Pending, StringComparison.Ordinal)
                ? "La petición necesita confirmación antes de continuar."
                : "No pude completar la petición solicitada.";
    }
}
