using Baxy.Contracts;

namespace Baxy.Kernel.Journal;

public interface IInvocationJournal
{
    ValueTask<string?> FindStartedFingerprintAsync(
        string invocationId,
        CancellationToken cancellationToken);

    ValueTask<CompletedInvocation?> FindCompletedAsync(
        string invocationId,
        CancellationToken cancellationToken);

    /// <summary>
    /// True when the invocation completed but its recorded response is no longer
    /// kept (a rotated journal's retention deleted it). Such an id must be refused,
    /// never executed again.
    /// </summary>
    ValueTask<bool> IsRetiredAsync(
        string invocationId,
        CancellationToken cancellationToken);

    ValueTask RecordStartedAsync(
        OperationRequest request,
        string requestFingerprint,
        CancellationToken cancellationToken);

    ValueTask RecordCompletedAsync(
        OperationRequest request,
        string requestFingerprint,
        OperationResponse response,
        CancellationToken cancellationToken);
}
