using Baxy.Contracts;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Mission;
using Baxy.Kernel.Operations;

namespace Baxy.Core;

/// <summary>
/// One request of the core's loop. H9 (engine_no_answer opening Steam cold): an exception a provider threw left the
/// engine, which lets an unexpected one go with the invocation started (its retry asks to reconcile), and ended the core
/// (exit 70); the App saw the channel closed and the turn was lost. It is answered to that request instead, failed with
/// its effect uncertain, and the core reads the next.
/// </summary>
internal static class CoreRequest
{
    internal const string UnexpectedFailureCode = "operation_unexpected_failure";

    /// <summary>
    /// The engine's response, or that request failed with its effect uncertain when the engine threw. What still stops
    /// the core goes on: its own cancellation, and the journal that cannot be trusted (JournalIntegrityException) or
    /// cannot record (JournalCapacityException; the engine already answers the one it can, before the effect), both
    /// IOExceptions. The invocation stays started in the journal, as the engine left it.
    /// </summary>
    internal static async ValueTask<OperationResponse> ExecuteAsync(
        MissionEngine engine,
        OperationRequest request,
        TextWriter diagnostics,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(engine);
        ArgumentNullException.ThrowIfNull(request);
        ArgumentNullException.ThrowIfNull(diagnostics);
        try
        {
            return await engine.ExecuteAsync(request, cancellationToken).ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is not (JournalIntegrityException or JournalCapacityException)
            && (exception is not OperationCanceledException || !cancellationToken.IsCancellationRequested))
        {
            // The type only: an exception's text can carry what the person has (a window's title, a file's path).
            string cause = exception.GetType().Name;
            diagnostics.WriteLine(
                $"BAXY core: {request.Operation} ended in an unexpected {cause}; answered failed, its invocation stays started.");
            return UnexpectedFailure(request, cause);
        }
    }

    private static OperationResponse UnexpectedFailure(OperationRequest request, string cause)
    {
        // It may have thrown after acting: the effect is uncertain, never «nothing happened».
        OperationOutcome outcome = OperationOutcome.Failure(
            UnexpectedFailureCode,
            effectMayHaveOccurred: true,
            causeCode: cause);
        return new OperationResponse(
            ProtocolTypes.OperationResponse,
            request.RequestId,
            request.MissionId,
            request.InvocationId,
            OperationStatuses.Failed,
            OperationVisibleFacts.FromOutcome(request.Operation, outcome),
            Verified: false,
            Replayed: false,
            Result: null,
            UnexpectedFailureCode,
            EffectMayHaveOccurred: true,
            CauseCode: cause);
    }
}
