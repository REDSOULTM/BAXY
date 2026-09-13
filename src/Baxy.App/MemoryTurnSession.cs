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
        /// <summary>
        /// Publish with the text whose language and intent the reply answers:
        /// after «confirmar», the final of a continued save answers the original
        /// request, not the closed reply word (MEMORY1247).
        /// </summary>
        internal Action<string, UserMessageEvent?, string?>? PublishForObjective { get; init; }

        internal required Action<string> SetStatus { get; init; }

        internal required Func<bool> HasPendingAudio { get; init; }

        internal required Action<bool> RecoverNotes { get; init; }

        internal required Func<MissionInputRoute, RetryableOperationRegistry, CancellationToken, Task<bool>>
            ContinuePublic
        { get; init; }
    }

    private sealed record MemoryContinuation(
        PreparedOperation Predecessor,
        string? Objective,
        MissionInputSource Source,
        PreparedOperation? SaveAfterEnable = null,
        string? RequestText = null);

    private readonly Host _host;
    private PendingMemoryConfirmation? _confirmation;
    private bool _confirmationIsDurable;
    private bool _confirmationRequiresReconciliation;
    private PreparedOperation? _pendingOperation;
    private MemoryContinuation? _continuation;
    private bool _recoveryAnnounced;
    private MemorySaveSubject? _missingSaveSubject;

    internal MemoryTurnSession(Host host)
    {
        _host = host ?? throw new ArgumentNullException(nameof(host));
    }

    internal bool HasConfirmation => _confirmation is not null;

    internal bool HasPendingOperation => _pendingOperation is not null;

    internal PendingMemoryConfirmation? Confirmation => _confirmation;

    internal PreparedOperation? PendingOperation => _pendingOperation;

    internal void AwaitSaveInput(MemoryParseResult request)
    {
        _missingSaveSubject = request.MissingSaveSubject;
    }

    internal bool TryCancelSaveInput(string text)
    {
        if (_missingSaveSubject is null
            || ConfirmationReplyParser.Parse(text) != ConfirmationReplyKind.Cancel)
        {
            return false;
        }

        _missingSaveSubject = null;
        return true;
    }

    internal bool TryResolveSaveInput(MissionInputRoute input, out MissionInputRoute? bound)
    {
        bound = null;
        if (_missingSaveSubject is not { } subject || HasConfirmation || HasPendingOperation)
        {
            return false;
        }

        if (NaturalMemoryRequestParser.WithdrawsPendingSave(input.Text)
            || input.Memory.Outcome is MemoryParseOutcome.Route
                or MemoryParseOutcome.ConfirmSensitiveSave
                or MemoryParseOutcome.RejectAuthorizationPersistence
                or MemoryParseOutcome.SessionContextOnly)
        {
            _missingSaveSubject = null;
            return false;
        }

        if (!NaturalMemoryRequestParser.TryBindSaveInput(subject, input, out bound))
        {
            return false;
        }

        _missingSaveSubject = null;
        return true;
    }

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
        _missingSaveSubject = null;
    }

    internal void ResetSession()
    {
        ClearConfirmation();
        ResetOperation();
        _continuation = null;
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
                    PrivateOperationNarration.CreateMemoryConfirmationPrompt(
                        pending.Prepared,
                        _confirmationRequiresReconciliation),
                    UserMessageEvent.Confirmation);
                return;
            case ConfirmationReplyKind.Cancel:
                if (_confirmationRequiresReconciliation)
                {
                    _host.Publish(
                        TurnVisibleFacts.Confirmation(
                            "cannot_withdraw_uncertain",
                            ["confirmar", "confirm"],
                            PrivateOperationNarration.PendingMemoryAction(pending.Prepared)),
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

                ClearContinuation(pending.Prepared);
                ClearConfirmation();
                _host.Publish(PrivateOperationNarration.CreateMemoryCancellationMessage(pending.Prepared), null);
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

            ClearContinuation(pending);
            ResetOperation();
            _host.Publish(PrivateOperationNarration.CreateMemoryCancellationMessage(pending), null);
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
        MissionInputSource publicSource = MissionInputSource.Text,
        string? requestText = null)
    {
        ArgumentNullException.ThrowIfNull(routed);
        ArgumentNullException.ThrowIfNull(registry);
        MemoryOperationProtector protector = _host.Protector()
            ?? throw new InvalidOperationException("La protección de memoria no está disponible.");
        ProtectedMemoryOperation protectedOperation = protector.Prepare(routed);
        PreparedOperation prepared = durableBeforeSend
            ? registry.GetOrAdd(protectedOperation)
            : protectedOperation.Prepared;
        if (!string.IsNullOrWhiteSpace(publicObjective)
            || !string.IsNullOrWhiteSpace(requestText))
        {
            // A memory-only request has no public objective; its completion
            // still answers the request text, in the request's language.
            _continuation = new MemoryContinuation(
                prepared,
                publicObjective,
                publicSource,
                RequestText: requestText);
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
        CancellationToken cancellationToken,
        bool allowEnableOffer = true)
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
            ClearContinuation(prepared);
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
                using OpenedBoundProtectedJson arguments = protector.OpenPrivateArguments(prepared);
                if (!MemoryOperationResponseProjection.TryCreateCompleted(
                        prepared.OperationName,
                        opened.Payload,
                        out MemoryOperationResponseProjection? projection,
                        response.Replayed,
                        arguments.Payload)
                    || projection is null)
                {
                    throw new InvalidDataException("La respuesta privada no admite una proyección segura.");
                }

                string? objective = _continuation?.RequestText ?? _continuation?.Objective;
                if (_host.PublishForObjective is { } publishForObjective
                    && !string.IsNullOrWhiteSpace(objective))
                {
                    publishForObjective(projection.Message, null, objective);
                }
                else
                {
                    _host.Publish(projection.Message, null);
                }
            }
            catch
            {
                ClearConfirmationFor(prepared);
                SetPending(registry, prepared);
                throw;
            }

            ClearConfirmationFor(prepared);
            if (Resolve(registry, prepared))
            {
                await ContinueAfterAsync(prepared, registry, cancellationToken);
            }
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

        if (allowEnableOffer
            && prepared.OperationName == "memory.save"
            && response.Status == OperationStatuses.Failed
            && response.ErrorCode == "memory_disabled"
            && protector.InspectForRecovery(prepared).OriginatesInCurrentSession)
        {
            // The failed save is terminal. Enabling has its own invocation and
            // challenge; only a verified enable can create a new save attempt.
            if (!TryRemove(registry, prepared))
            {
                SetPending(registry, prepared);
                return;
            }

            ClearConfirmationFor(prepared);
            if (IsSame(_pendingOperation, prepared))
            {
                ResetOperation();
            }

            MemoryContinuation? previous = _continuation is { } candidate
                && IsSame(candidate.Predecessor, prepared) ? candidate : null;
            PreparedOperation enable = registry.GetOrAdd(protector.Prepare(
                new MemoryRoutedOperation("memory.configure", new JsonObject
                {
                    ["version"] = 1,
                    ["enabled"] = true,
                })));
            _continuation = new MemoryContinuation(
                enable, previous?.Objective, previous?.Source ?? MissionInputSource.Text, prepared,
                previous?.RequestText);
            await SendPreparedAsync(enable, registry, isDurable: true,
                confirmationToken: null, cancellationToken);
            return;
        }

        ClearContinuation(prepared);
        ClearConfirmationFor(prepared);
        Resolve(registry, prepared);
    }

    private async Task ContinueAfterAsync(
        PreparedOperation predecessor,
        RetryableOperationRegistry registry,
        CancellationToken cancellationToken)
    {
        MemoryContinuation? continuation = _continuation;
        if (continuation is null || !IsSame(continuation.Predecessor, predecessor))
        {
            return;
        }

        _continuation = null;
        if (continuation.SaveAfterEnable is { } originalSave)
        {
            MemoryOperationProtector protector = _host.Protector()
                ?? throw new InvalidOperationException("La protección de memoria no está disponible.");
            using OpenedBoundProtectedJson opened = protector.OpenPrivateArguments(originalSave);
            var arguments = JsonNode.Parse(opened.Payload.GetRawText()) as JsonObject
                ?? throw new InvalidDataException("El guardado pendiente perdió sus argumentos privados.");
            PreparedOperation next = registry.GetOrAdd(protector.Prepare(
                new MemoryRoutedOperation("memory.save", arguments)));
            if (!string.IsNullOrWhiteSpace(continuation.Objective)
                || !string.IsNullOrWhiteSpace(continuation.RequestText))
            {
                _continuation = new MemoryContinuation(
                    next, continuation.Objective, continuation.Source, RequestText: continuation.RequestText);
            }

            await SendPreparedAsync(next, registry, isDurable: true,
                confirmationToken: null, cancellationToken, allowEnableOffer: false);
            return;
        }

        if (string.IsNullOrWhiteSpace(continuation.Objective))
        {
            return;
        }

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

    private void ClearContinuation(PreparedOperation predecessor)
    {
        if (_continuation is { } continuation
            && IsSame(continuation.Predecessor, predecessor))
        {
            _continuation = null;
        }
    }

    private bool Resolve(RetryableOperationRegistry registry, PreparedOperation prepared)
    {
        if (!TryRemove(registry, prepared))
        {
            SetPending(registry, prepared);
            return false;
        }

        if (IsSame(_pendingOperation, prepared))
        {
            ResetOperation();
        }

        ContinueRecovery(registry);
        return true;
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
