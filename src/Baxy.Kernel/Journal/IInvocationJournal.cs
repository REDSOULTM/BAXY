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
