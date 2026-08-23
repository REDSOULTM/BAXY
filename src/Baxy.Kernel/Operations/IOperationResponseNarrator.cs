namespace Baxy.Kernel.Operations;

public interface IOperationResponseNarrator
{
    string Narrate(string operation, OperationOutcome outcome);

    string NarrateStatus(string operation, string status, string? errorCode);
}

internal sealed class DefaultOperationResponseNarrator : IOperationResponseNarrator
{
    internal static DefaultOperationResponseNarrator Instance { get; } = new();

    private DefaultOperationResponseNarrator()
    {
    }

    public string Narrate(string operation, OperationOutcome outcome)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(operation);
        ArgumentNullException.ThrowIfNull(outcome);
        return OperationVisibleFacts.FromOutcome(operation, outcome);
    }

    public string NarrateStatus(string operation, string status, string? errorCode)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(operation);
        ArgumentException.ThrowIfNullOrWhiteSpace(status);
        return OperationVisibleFacts.FromStatus(operation, status, errorCode);
    }
}
