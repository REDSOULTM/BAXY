using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Contracts;
using Baxy.Security.Windows;

namespace Baxy.App;

/// <summary>
/// Flujo de confirmación y recuperación de memoria privada. No conoce la
/// ventana; habla por el <see cref="Host"/>.
/// </summary>
internal sealed class MemoryTurnSession
{
    internal sealed class Host
    {
        internal required Func<CoreProcessClient?> Core { get; init; }

        internal required Func<MemoryOperationProtector?> Protector { get; init; }

        internal required Action<string, UserMessageEvent?> Publish { get; init; }

        internal required Action<string> SetStatus { get; init; }

        internal required Func<bool> HasPendingAudio { get; init; }

        internal required Action<bool> RecoverNotes { get; init; }

        internal required Func<MissionInputRoute, RetryableOperationRegistry, CancellationToken, Task<bool>>
            ContinuePublic
        { get; init; }
    }

    internal sealed record PublicAfterMemory(
        PreparedOperation Predecessor,
        string Objective,
        MissionInputSource Source);

    private readonly Host _host;
    private PendingMemoryConfirmation? _confirmation;
    private bool _confirmationIsDurable;
    private bool _confirmationRequiresReconciliation;
    private PreparedOperation? _pendingOperation;
    private PublicAfterMemory? _publicAfter;
    private bool _recoveryAnnounced;

    internal MemoryTurnSession(Host host)
    {
        _host = host ?? throw new ArgumentNullException(nameof(host));
    }

    internal bool HasConfirmation => _confirmation is not null;

    internal bool HasPendingOperation => _pendingOperation is not null;

    internal PendingMemoryConfirmation? Confirmation => _confirmation;

    internal PreparedOperation? PendingOperation => _pendingOperation;

    internal void ClearConfirmation()
    {
        _confirmation = null;
        _confirmationIsDurable = false;
        _confirmationRequiresReconciliation = false;
    }

    internal void ResetOperation()
    {
        _pendingOperation = null;
        _recoveryAnnounced = false;
    }

    internal async Task HandleConfirmationAsync(
        string text,
        RetryableOperationRegistry registry,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(text);
        ArgumentNullException.ThrowIfNull(registry);
        PendingMemoryConfirmation pending = _confirmation
            ?? throw new InvalidOperationException("No hay una confirmación de memoria activa.");
        switch (ConfirmationReplyParser.Parse(text))
        {
            case ConfirmationReplyKind.Invalid:
                _host.Publish(
                    _confirmationRequiresReconciliation
                        ? TurnVisibleFacts.Confirmation(
                            "memory_reconcile_only",
                            TurnVisibleFacts.ConfirmCancel)
                        : TurnVisibleFacts.Confirmation(
                            "memory_confirm_or_cancel",
                            TurnVisibleFacts.ConfirmCancel),
                    UserMessageEvent.Confirmation);
                return;
            case ConfirmationReplyKind.Cancel:
                if (_confirmationRequiresReconciliation)
                {
                    _host.Publish(
                        TurnVisibleFacts.Confirmation(
                            "cannot_withdraw_uncertain",
                            TurnVisibleFacts.ConfirmCancel),
                        UserMessageEvent.Confirmation);
                    return;
                }

                if (!TryRemove(registry, pending.Prepared))
                {
                    _host.Publish(
                        TurnVisibleFacts.Failure("cannot_withdraw_pending"),
                        UserMessageEvent.Error(UserMessageDiagnosticCodes.ActionNotCompleted));
                    return;
                }

                ClearPublicAfter(pending.Prepared);
                ClearConfirmation();
                _host.Publish(TurnVisibleFacts.Status("memory_cancelled"), null);
                ContinueRecovery(registry);
                return;
            case ConfirmationReplyKind.Confirm:
                PreparedOperation prepared = pending.Prepared;
                if (!_confirmationIsDurable)
                {
                    MemoryOperationProtector protector = _host.Protector()
                        ?? throw new InvalidOperationException("La protección de memoria no está disponible.");
                    prepared = registry.GetOrAdd(protector.AuthenticateForOutbox(prepared));
                    _confirmationIsDurable = true;
                }

                _confirmationRequiresReconciliation = true;
                await SendPreparedAsync(
                    prepared,
                    registry,
                    isDurable: true,
                    pending.Token,
                    cancellationToken);
                return;
            default:
                throw new InvalidDataException("La respuesta de confirmación no es válida.");
        }
    }

    internal async Task HandlePendingOperationAsync(
        string text,
        RetryableOperationRegistry registry,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(text);
        ArgumentNullException.ThrowIfNull(registry);
        PreparedOperation pending = _pendingOperation
            ?? throw new InvalidOperationException("No hay una operación de memoria por reconciliar.");
        NoteChoiceReply reply = NoteChoiceReplyParser.Parse(text);
        if (reply.Kind == NoteChoiceReplyKind.Cancel)
        {
            if (!TryRemove(registry, pending))
            {
                _host.Publish(
                    TurnVisibleFacts.Failure("cannot_withdraw_pending"),
                    UserMessageEvent.Error(UserMessageDiagnosticCodes.ActionNotCompleted));
                return;
            }

            ResetOperation();
            _host.Publish(TurnVisibleFacts.Status("memory_cancelled"), null);
            ContinueRecovery(registry);
            return;
        }

        if (reply.Kind != NoteChoiceReplyKind.Continue)
        {
            _host.Publish(
                PrivateOperationNarration.CreateMemoryRecoveryPrompt(pending),
                UserMessageEvent.Confirmation);
            return;
        }

        await SendPreparedAsync(
            pending,
            registry,
            isDurable: true,
            confirmationToken: null,
            cancellationToken);
    }

    internal async Task ExecuteRouteAsync(
        MemoryRoutedOperation routed,
        RetryableOperationRegistry registry,
        bool durableBeforeSend,
        CancellationToken cancellationToken,
        string? publicObjective = null,
        MissionInputSource publicSource = MissionInputSource.Text)
    {
        ArgumentNullException.ThrowIfNull(routed);
        ArgumentNullException.ThrowIfNull(registry);
        MemoryOperationProtector protector = _host.Protector()
            ?? throw new InvalidOperationException("La protección de memoria no está disponible.");
        ProtectedMemoryOperation protectedOperation = protector.Prepare(routed);
        PreparedOperation prepared = durableBeforeSend
            ? registry.GetOrAdd(protectedOperation)
            : protectedOperation.Prepared;
        if (!string.IsNullOrWhiteSpace(publicObjective))
        {
            _publicAfter = new PublicAfterMemory(
                prepared,
                publicObjective,
                publicSource);
        }

        await SendPreparedAsync(
            prepared,
            registry,
            durableBeforeSend,
            confirmationToken: null,
            cancellationToken);
    }

    internal void RecoverFrom(RetryableOperationRegistry registry, bool announce)
    {
        ArgumentNullException.ThrowIfNull(registry);
        MemoryOperationProtector? protector = _host.Protector();
        if (protector is null || _confirmation is not null)
        {
            return;
        }

        if (_pendingOperation is not null)
        {
            if (announce)
            {
                AnnounceIfReady();
            }

            return;
        }

        PreparedOperation? firstPreserved = null;
        foreach (PreparedOperation operation in registry.SnapshotPendingOperations())
        {
            if (!MemoryOperationProtector.IsMemoryOperation(operation.OperationName))
            {
                continue;
            }

            MemoryOperationInspection inspection = protector.InspectForRecovery(operation);
            if (!inspection.OriginatesInCurrentSession
                && inspection.CancelAfterSessionChange)
            {
                registry.MarkResolved(operation);
                if (registry.SnapshotPendingOperations().Any(
                        candidate => IsSame(candidate, operation)))
                {
                    throw new InvalidDataException(
                        "No se pudo retirar una operación privada vencida de la recuperación.");
                }

                continue;
            }

            firstPreserved ??= operation;
        }

        if (firstPreserved is null)
        {
            return;
        }

        _pendingOperation = firstPreserved;
        _recoveryAnnounced = false;
        if (announce)
        {
            AnnounceIfReady();
        }
    }

    internal void AnnounceIfReady()
    {
        if (_pendingOperation is null
            || _recoveryAnnounced
            || _confirmation is not null
            || _host.HasPendingAudio())
        {
            return;
        }

        _recoveryAnnounced = true;
        _host.SetStatus("Esperando comprobar la memoria");
        _host.Publish(
            PrivateOperationNarration.CreateMemoryRecoveryPrompt(_pendingOperation),
            UserMessageEvent.Confirmation);
    }

    private async Task SendPreparedAsync(
        PreparedOperation prepared,
        RetryableOperationRegistry registry,
        bool isDurable,
        string? confirmationToken,
        CancellationToken cancellationToken)
    {
        CoreProcessClient client = _host.Core()
            ?? throw new InvalidOperationException("El motor local no está disponible.");
        MemoryOperationProtector protector = _host.Protector()
            ?? throw new InvalidOperationException("La protección de memoria no está disponible.");
        OperationResponse response = await client.SendOperationAsync(
            prepared,
            TimeSpan.FromSeconds(20),
            cancellationToken,
            confirmationToken);

        if (PendingMemoryConfirmation.TryCreate(
                response,
                prepared,
                TimeProvider.System,
                out PendingMemoryConfirmation? challenge)
            && challenge is not null)
        {
            _confirmation = challenge;
            _confirmationIsDurable = isDurable;
            _confirmationRequiresReconciliation = challenge.ReconciliationRequired;
            if (IsSame(_pendingOperation, prepared))
            {
                ResetOperation();
            }

            _host.Publish(
                PrivateOperationNarration.CreateMemoryConfirmationPrompt(
                    prepared,
                    challenge.ReconciliationRequired),
                UserMessageEvent.Confirmation);
            return;
        }

        if (!isDurable)
        {
            ClearPublicAfter(prepared);
            _host.Publish(
                "No recibí una confirmación segura para guardar ese dato sensible. No lo añadí a la cola de recuperación.",
                UserMessageEvent.Error(UserMessageDiagnosticCodes.ActionNotCompleted));
            return;
        }

        if (string.Equals(response.Status, OperationStatuses.Completed, StringComparison.Ordinal))
        {
            try
            {
                using OpenedBoundProtectedJson opened = protector.OpenResult(response, prepared);
                if (!MemoryOperationResponseProjection.TryCreateCompleted(
                        prepared.OperationName,
                        opened.Payload,
                        out MemoryOperationResponseProjection? projection,
                        response.Replayed)
                    || projection is null)
                {
                    throw new InvalidDataException("La respuesta privada no admite una proyección segura.");
                }

                _host.Publish(projection.Message, null);
            }
            catch
            {
                ClearConfirmationFor(prepared);
                SetPending(registry, prepared);
                throw;
            }

            ClearConfirmationFor(prepared);
            Resolve(registry, prepared);
            await ContinuePublicAfterAsync(prepared, registry, cancellationToken);
            return;
        }

        _host.Publish(
            PrivateOperationNarration.CreateMemoryFailureMessage(prepared.OperationName, response),
            UserMessageEvent.Error(UserMessageDiagnosticCodes.ActionNotCompleted));
        if (MainWindowViewModel.ShouldRetainRetryIdentity(response))
        {
            if (confirmationToken is null || _confirmation is null)
            {
                SetPending(registry, prepared);
            }

            return;
        }

        ClearPublicAfter(prepared);
        ClearConfirmationFor(prepared);
        Resolve(registry, prepared);
    }

    private async Task ContinuePublicAfterAsync(
        PreparedOperation predecessor,
        RetryableOperationRegistry registry,
        CancellationToken cancellationToken)
    {
        PublicAfterMemory? continuation = _publicAfter;
        if (continuation is null || !IsSame(continuation.Predecessor, predecessor))
        {
            return;
        }

        _publicAfter = null;
        var publicRoute = new MissionInputRoute(
            continuation.Objective,
            continuation.Source,
            MemoryParseResult.NoRoute());
        if (!await _host.ContinuePublic(publicRoute, registry, cancellationToken))
        {
            _host.Publish(
                TurnVisibleFacts.Failure("ambiguous_request"),
                UserMessageEvent.Error(UserMessageDiagnosticCodes.ActionNotCompleted));
        }
    }

    private void ClearPublicAfter(PreparedOperation predecessor)
    {
        if (_publicAfter is { } continuation
            && IsSame(continuation.Predecessor, predecessor))
        {
            _publicAfter = null;
        }
    }

    private void Resolve(RetryableOperationRegistry registry, PreparedOperation prepared)
    {
        if (!TryRemove(registry, prepared))
        {
            SetPending(registry, prepared);
            return;
        }

        if (IsSame(_pendingOperation, prepared))
        {
            ResetOperation();
        }

        ContinueRecovery(registry);
    }

    private bool TryRemove(RetryableOperationRegistry registry, PreparedOperation prepared)
    {
        try
        {
            PreparedOperation? registered = registry
                .SnapshotPendingOperations()
                .FirstOrDefault(candidate => IsSame(candidate, prepared));
            if (registered is null)
            {
                return true;
            }

            registry.MarkResolved(registered);
            return !registry
                .SnapshotPendingOperations()
                .Any(candidate => IsSame(candidate, prepared));
        }
        catch (Exception exception) when (IsDurableStoreFailure(exception))
        {
            _host.Publish(
                TurnVisibleFacts.Failure("recovery_journal_unclosed"),
                UserMessageEvent.Error(UserMessageDiagnosticCodes.ActionNotCompleted));
            return false;
        }
    }

    private void SetPending(RetryableOperationRegistry registry, PreparedOperation prepared)
    {
        _pendingOperation = registry
            .SnapshotPendingOperations()
            .FirstOrDefault(candidate => IsSame(candidate, prepared))
            ?? prepared;
        _recoveryAnnounced = false;
        AnnounceIfReady();
    }

    private void ContinueRecovery(RetryableOperationRegistry registry)
    {
        RecoverFrom(registry, announce: true);
        _host.RecoverNotes(true);
    }

    private void ClearConfirmationFor(PreparedOperation prepared)
    {
        if (_confirmation is not null && IsSame(_confirmation.Prepared, prepared))
        {
            ClearConfirmation();
        }
    }

    internal static bool IsSame(PreparedOperation? left, PreparedOperation right) =>
        left is not null
        && string.Equals(left.IdentityKey, right.IdentityKey, StringComparison.Ordinal)
        && string.Equals(left.MissionId, right.MissionId, StringComparison.Ordinal)
        && string.Equals(left.InvocationId, right.InvocationId, StringComparison.Ordinal);

    private static bool IsDurableStoreFailure(Exception exception) =>
        exception is IOException
            or InvalidDataException
            or InvalidOperationException
            or JsonException
            or UnauthorizedAccessException;
}
