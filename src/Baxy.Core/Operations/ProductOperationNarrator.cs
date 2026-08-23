using Baxy.Kernel.Operations;

namespace Baxy.Core.Operations;

internal sealed class ProductOperationNarrator : IOperationResponseNarrator
{
    internal static ProductOperationNarrator Instance { get; } = new();

    private ProductOperationNarrator()
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
