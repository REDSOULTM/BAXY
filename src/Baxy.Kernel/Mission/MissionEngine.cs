using System.Buffers;
using System.Globalization;
using System.Text.Json;
using Baxy.Contracts;
using Baxy.Kernel.Journal;
using Baxy.Kernel.Operations;
using Baxy.Kernel.Policy;

namespace Baxy.Kernel.Mission;

public sealed class MissionEngine : IDisposable
{
    private static readonly TimeSpan TerminalCommitTimeout = TimeSpan.FromSeconds(10);

    private readonly OperationRegistry _registry;
    private readonly IInvocationJournal _journal;
    private readonly InMemoryConfirmationAuthority _confirmationAuthority;
    private readonly IPrivateOperationEnvelopeAuthenticator? _privateEnvelopeAuthenticator;
    private readonly IOperationResponseNarrator _narrator;
    private readonly SemaphoreSlim _executionGate = new(1, 1);

    public MissionEngine(OperationRegistry registry, IInvocationJournal journal)
        : this(
            registry,
            journal,
            new InMemoryConfirmationAuthority(),
            privateEnvelopeAuthenticator: null,
            DefaultOperationResponseNarrator.Instance)
    {
    }

    public MissionEngine(
        OperationRegistry registry,
        IInvocationJournal journal,
        IPrivateOperationEnvelopeAuthenticator privateEnvelopeAuthenticator)
        : this(
            registry,
            journal,
            new InMemoryConfirmationAuthority(),
            privateEnvelopeAuthenticator
                ?? throw new ArgumentNullException(nameof(privateEnvelopeAuthenticator)),
            DefaultOperationResponseNarrator.Instance)
    {
    }

    public MissionEngine(
        OperationRegistry registry,
        IInvocationJournal journal,
        IOperationResponseNarrator narrator)
        : this(
            registry,
            journal,
            new InMemoryConfirmationAuthority(),
            privateEnvelopeAuthenticator: null,
            narrator ?? throw new ArgumentNullException(nameof(narrator)))
    {
    }

    public MissionEngine(
        OperationRegistry registry,
        IInvocationJournal journal,
        IPrivateOperationEnvelopeAuthenticator privateEnvelopeAuthenticator,
        IOperationResponseNarrator narrator)
        : this(
            registry,
            journal,
            new InMemoryConfirmationAuthority(),
            privateEnvelopeAuthenticator
                ?? throw new ArgumentNullException(nameof(privateEnvelopeAuthenticator)),
            narrator ?? throw new ArgumentNullException(nameof(narrator)))
    {
    }

    public MissionEngine(
        OperationRegistry registry,
        IInvocationJournal journal,
        TimeProvider timeProvider)
        : this(
            registry,
            journal,
            new InMemoryConfirmationAuthority(
                timeProvider ?? throw new ArgumentNullException(nameof(timeProvider))),
            privateEnvelopeAuthenticator: null,
            DefaultOperationResponseNarrator.Instance)
    {
    }

    public MissionEngine(
        OperationRegistry registry,
        IInvocationJournal journal,
        TimeProvider timeProvider,
        IPrivateOperationEnvelopeAuthenticator privateEnvelopeAuthenticator)
        : this(
            registry,
            journal,
            new InMemoryConfirmationAuthority(
                timeProvider ?? throw new ArgumentNullException(nameof(timeProvider))),
            privateEnvelopeAuthenticator
                ?? throw new ArgumentNullException(nameof(privateEnvelopeAuthenticator)),
            DefaultOperationResponseNarrator.Instance)
    {
    }

    internal MissionEngine(
        OperationRegistry registry,
        IInvocationJournal journal,
        InMemoryConfirmationAuthority confirmationAuthority)
        : this(
            registry,
            journal,
            confirmationAuthority,
            privateEnvelopeAuthenticator: null,
            DefaultOperationResponseNarrator.Instance)
    {
    }

    internal MissionEngine(
        OperationRegistry registry,
        IInvocationJournal journal,
        InMemoryConfirmationAuthority confirmationAuthority,
        IPrivateOperationEnvelopeAuthenticator? privateEnvelopeAuthenticator,
        IOperationResponseNarrator narrator)
    {
        _registry = registry ?? throw new ArgumentNullException(nameof(registry));
        _journal = journal ?? throw new ArgumentNullException(nameof(journal));
        _confirmationAuthority = confirmationAuthority
            ?? throw new ArgumentNullException(nameof(confirmationAuthority));
        _privateEnvelopeAuthenticator = privateEnvelopeAuthenticator;
        _narrator = narrator ?? throw new ArgumentNullException(nameof(narrator));
    }

    public async ValueTask<OperationResponse> ExecuteAsync(
        OperationRequest request,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(request);
        ContractValidator.Validate(request);
        if (PrivateOperationBoundary.IsPrivateOperation(request.Operation)
            && (!PrivateOperationBoundary.HasProtectedArguments(request)
                || !AuthenticatePrivateArguments(request)))
        {
            return Rejected(
                request,
                "invalid_private_envelope");
        }

        await _executionGate.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            string fingerprint = RequestFingerprint.Compute(request);
            CompletedInvocation? completed = await _journal
                .FindCompletedAsync(request.InvocationId, cancellationToken)
                .ConfigureAwait(false);
            if (completed is not null)
            {
                if (!string.Equals(completed.RequestFingerprint, fingerprint, StringComparison.Ordinal))
                {
                    return Rejected(request, "idempotency_conflict");
                }

                _confirmationAuthority.Revoke(ConfirmationBinding.Create(request, fingerprint));
                return PrivateOperationBoundary.NormalizeReplay(
                    request,
                    completed.Response,
                    _privateEnvelopeAuthenticator,
                    _narrator);
            }

            string? startedFingerprint = await _journal
                .FindStartedFingerprintAsync(request.InvocationId, cancellationToken)
                .ConfigureAwait(false);
            if (startedFingerprint is not null
                && !string.Equals(startedFingerprint, fingerprint, StringComparison.Ordinal))
            {
                return Rejected(request, "idempotency_conflict");
            }

            bool knownOperation = _registry.TryGet(
                request.Operation,
                out IOperationHandler? handler);
            bool validArguments = !knownOperation
                || handler is null
                || HasValidArguments(request, handler);
            PolicyDecision? policy = knownOperation && handler is not null && validArguments
                ? RiskPolicy.Evaluate(handler.Definition.Risk)
                : null;
            ConfirmationBinding? grantedBinding = null;
            if (policy == PolicyDecision.RequireConfirmation)
            {
                ConfirmationBinding binding = ConfirmationBinding.Create(request, fingerprint);
                ConfirmationAuthorization authorization = _confirmationAuthority.AuthorizeOrIssue(
                    binding,
                    request.ConfirmationToken);
                if (authorization.Status == ConfirmationAuthorizationStatus.ChallengeRequired)
                {
                    return Pending(
                        request,
                        ConfirmationChallengeContract.RequiredErrorCode,
                        BuildConfirmationResult(
                            authorization.Challenge!,
                            reconciliationRequired: startedFingerprint is not null));
                }

                grantedBinding = binding;
            }

            try
            {
                await _journal
                    .RecordStartedAsync(request, fingerprint, cancellationToken)
                    .ConfigureAwait(false);
            }
            catch (JournalCapacityException)
            {
                return Rejected(
                    request,
                    "journal_capacity_reached");
            }

            if (!knownOperation || handler is null)
            {
                return await CompleteAsync(
                    request,
                    fingerprint,
                    Rejected(request, "unknown_operation"),
                    cancellationToken).ConfigureAwait(false);
            }

            if (!validArguments)
            {
                return await CompleteAsync(
                    request,
                    fingerprint,
                    InvalidArguments(request),
                    cancellationToken).ConfigureAwait(false);
            }

            if (policy == PolicyDecision.Deny)
            {
                return await CompleteAsync(
                    request,
                    fingerprint,
                    Rejected(request, "operation_forbidden"),
                    cancellationToken).ConfigureAwait(false);
            }

            var invocation = new OperationInvocation(
                request.RequestId,
                request.MissionId,
                request.InvocationId,
                request.Arguments);
            OperationOutcome outcome = await handler
                .ExecuteAsync(invocation, cancellationToken)
                .ConfigureAwait(false);
            outcome = PrivateOperationBoundary.NormalizeOutcome(
                request,
                outcome,
                _privateEnvelopeAuthenticator);
            if (outcome.Retryable
                && (outcome.Succeeded
                    || outcome.Verified
                    || string.IsNullOrWhiteSpace(outcome.ErrorCode)))
            {
                throw new InvalidOperationException(
                    "A retryable outcome must be unverified, unsuccessful, and contain an error code.");
            }

            OperationResponse response = ToResponse(request, outcome);
            if (outcome.Retryable)
            {
                return response;
            }

            using var completionCancellation =
                new CancellationTokenSource(TerminalCommitTimeout);
            OperationResponse completedResponse = await CompleteAsync(
                    request,
                    fingerprint,
                    response,
                    completionCancellation.Token,
                    grantedBinding)
                .ConfigureAwait(false);
            // Orden deliberado: el terminal se asienta en el journal ANTES de
            // propagar la cancelación. El efecto nunca queda sin registrar, y
            // el llamador que canceló recupera el resultado exacto —incluidos
            // EffectMayHaveOccurred y CauseCode— repitiendo el mismo
            // invocationId. Entregar aquí la respuesta rompería el contrato de
            // cancelación; perder el asiento rompería la verdad. Se conservan
            // ambos. Caracterizado en MissionEngineCancellationTests y en
            // FileInvocationJournalTests.
            cancellationToken.ThrowIfCancellationRequested();
            return completedResponse;
        }
        finally
        {
            _executionGate.Release();
        }
    }

    private OperationResponse ToResponse(
        OperationRequest request,
        OperationOutcome outcome)
    {
        bool completed = outcome.Succeeded && outcome.Verified;
        string status = outcome.Retryable
            ? OperationStatuses.Pending
            : completed
                ? OperationStatuses.Completed
                : OperationStatuses.Failed;
        string? errorCode = completed
            ? null
            : outcome.ErrorCode ?? (outcome.Succeeded ? "verification_failed" : "operation_failed");

        return new OperationResponse(
            ProtocolTypes.OperationResponse,
            request.RequestId,
            request.MissionId,
            request.InvocationId,
            status,
            _narrator.Narrate(request.Operation, outcome),
            completed,
            false,
            outcome.Result,
            errorCode,
            outcome.EffectMayHaveOccurred,
            outcome.CauseCode);
    }

    private async ValueTask<OperationResponse> CompleteAsync(
        OperationRequest request,
        string fingerprint,
        OperationResponse response,
        CancellationToken cancellationToken,
        ConfirmationBinding? grantedBinding = null)
    {
        await _journal
            .RecordCompletedAsync(request, fingerprint, response, cancellationToken)
            .ConfigureAwait(false);
        if (grantedBinding is { } binding)
        {
            _confirmationAuthority.Revoke(binding);
        }

        return response;
    }

    private bool AuthenticatePrivateArguments(OperationRequest request)
    {
        if (_privateEnvelopeAuthenticator is null)
        {
            return false;
        }

        try
        {
            return _privateEnvelopeAuthenticator.AuthenticateArguments(request);
        }
        catch (Exception)
        {
            return false;
        }
    }

    private bool HasValidArguments(OperationRequest request, IOperationHandler handler)
    {
        ProductOperationDescriptor? descriptor = handler.Definition.ProductDescriptor;
        if (descriptor is null)
        {
            return true;
        }

        if (!PrivateOperationBoundary.IsPrivateOperation(request.Operation))
        {
            return OperationArgumentValidator.IsValid(
                request.Arguments,
                descriptor.ArgumentsSchema);
        }

        if (_privateEnvelopeAuthenticator is not IPrivateOperationArgumentSchemaValidator validator)
        {
            return false;
        }

        try
        {
            return validator.ValidateArguments(request, descriptor.ArgumentsSchema);
        }
        catch (Exception)
        {
            return false;
        }
    }

    private static JsonElement BuildConfirmationResult(
        ConfirmationChallenge challenge,
        bool reconciliationRequired)
    {
        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", ConfirmationChallengeContract.CurrentVersion);
            writer.WriteString("token", challenge.Token);
            writer.WriteString(
                "expiresAtUtc",
                challenge.ExpiresAtUtc.ToUniversalTime().ToString("O", CultureInfo.InvariantCulture));
            writer.WriteBoolean("reconciliationRequired", reconciliationRequired);
            writer.WriteEndObject();
        }

        using JsonDocument document = JsonDocument.Parse(buffer.WrittenMemory);
        return document.RootElement.Clone();
    }

    private OperationResponse Pending(
        OperationRequest request,
        string errorCode,
        JsonElement? result) =>
        new(
            ProtocolTypes.OperationResponse,
            request.RequestId,
            request.MissionId,
            request.InvocationId,
            OperationStatuses.Pending,
            _narrator.NarrateStatus(
                request.Operation,
                OperationStatuses.Pending,
                errorCode),
            false,
            false,
            result,
            errorCode);

    private OperationResponse Rejected(
        OperationRequest request,
        string errorCode) =>
        new(
            ProtocolTypes.OperationResponse,
            request.RequestId,
            request.MissionId,
            request.InvocationId,
            OperationStatuses.Rejected,
            _narrator.NarrateStatus(
                request.Operation,
                OperationStatuses.Rejected,
                errorCode),
            false,
            false,
            null,
            errorCode);

    private OperationResponse InvalidArguments(OperationRequest request) =>
        new(
            ProtocolTypes.OperationResponse,
            request.RequestId,
            request.MissionId,
            request.InvocationId,
            OperationStatuses.Failed,
            _narrator.NarrateStatus(
                request.Operation,
                OperationStatuses.Failed,
                "invalid_arguments"),
            false,
            false,
            null,
            "invalid_arguments");

    public void Dispose()
    {
        _confirmationAuthority.Dispose();
        _executionGate.Dispose();
    }
}
