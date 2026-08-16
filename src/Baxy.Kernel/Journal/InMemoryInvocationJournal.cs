using Baxy.Contracts;

namespace Baxy.Kernel.Journal;

public sealed class InMemoryInvocationJournal : IInvocationJournal, IDisposable
{
    private readonly Dictionary<string, CompletedInvocation> _completed =
        new(StringComparer.Ordinal);
    private readonly Dictionary<string, string> _started = new(StringComparer.Ordinal);
    private readonly SemaphoreSlim _gate = new(1, 1);

    public async ValueTask<string?> FindStartedFingerprintAsync(
        string invocationId,
        CancellationToken cancellationToken)
    {
        await _gate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            return _started.GetValueOrDefault(invocationId);
        }
        finally
        {
            _gate.Release();
        }
    }

    public async ValueTask<CompletedInvocation?> FindCompletedAsync(
        string invocationId,
        CancellationToken cancellationToken)
    {
        await _gate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            return _completed.GetValueOrDefault(invocationId);
        }
        finally
        {
            _gate.Release();
        }
    }

    public async ValueTask RecordStartedAsync(
        OperationRequest request,
        string requestFingerprint,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(request);
        ArgumentException.ThrowIfNullOrWhiteSpace(requestFingerprint);

        await _gate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            if (_started.TryGetValue(request.InvocationId, out string? previousFingerprint) &&
                !string.Equals(previousFingerprint, requestFingerprint, StringComparison.Ordinal))
            {
                throw new InvalidOperationException(
                    "Invocation was already started with a different request fingerprint.");
            }

            _started[request.InvocationId] = requestFingerprint;
        }
        finally
        {
            _gate.Release();
        }
    }

    public async ValueTask RecordCompletedAsync(
        OperationRequest request,
        string requestFingerprint,
        OperationResponse response,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(request);
        ArgumentException.ThrowIfNullOrWhiteSpace(requestFingerprint);
        ArgumentNullException.ThrowIfNull(response);
        if (!OperationStatuses.IsTerminal(response.Status))
        {
            throw new ArgumentException(
                "Only terminal responses can complete an invocation.",
                nameof(response));
        }

        await _gate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            if (!_started.TryGetValue(request.InvocationId, out string? startedFingerprint) ||
                !string.Equals(startedFingerprint, requestFingerprint, StringComparison.Ordinal))
            {
                throw new InvalidOperationException("Invocation was not recorded as started.");
            }

            if (!_completed.TryAdd(
                    request.InvocationId,
                    new CompletedInvocation(requestFingerprint, response)))
            {
                throw new InvalidOperationException("Invocation is already complete.");
            }
        }
        finally
        {
            _gate.Release();
        }
    }

    public void Dispose() => _gate.Dispose();
}
