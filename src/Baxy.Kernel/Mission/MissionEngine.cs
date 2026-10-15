using System.Buffers;
using System.Globalization;
using System.Linq;
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
    private readonly Func<ConfirmationMode> _confirmationMode;
    private readonly SemaphoreSlim _executionGate = new(1, 1);

    /// <summary>
    /// Único constructor. Lo obligatorio va por parámetro; lo opcional, en
    /// <see cref="MissionEngineOptions"/>, para que añadir una dependencia no
    /// vuelva a duplicar el número de combinaciones.
    /// </summary>
    public MissionEngine(
        OperationRegistry registry,
        IInvocationJournal journal,
        MissionEngineOptions? options = null)
    {
        _registry = registry ?? throw new ArgumentNullException(nameof(registry));
        _journal = journal ?? throw new ArgumentNullException(nameof(journal));
        _confirmationAuthority = options?.ConfirmationAuthority
            ?? new InMemoryConfirmationAuthority();
        _privateEnvelopeAuthenticator = options?.PrivateEnvelopeAuthenticator;
        _confirmationMode = options?.ConfirmationMode
            ?? (() => ConfirmationMode.Normal);
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
                    _privateEnvelopeAuthenticator);
            }

            if (await _journal
                    .IsRetiredAsync(request.InvocationId, cancellationToken)
                    .ConfigureAwait(false))
            {
                // It completed long ago and its response left the journal's
                // retention: refused like any reuse of a completed id, never run
                // again (JOURNAL_ROTACION.md).
                return Rejected(request, "idempotency_conflict");
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
                ? RiskPolicy.Evaluate(
                    InvocationRisk(handler, request.Arguments),
                    _confirmationMode(),
                    handler.Definition.Name,
                    // Computer use (CONTRATO_VISTA_ACCION.md §2.1): the step's
                    // exact arguments decide whether it reaches a person.
                    request.Arguments)
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

    private static OperationResponse ToResponse(
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
        string message = OperationVisibleFacts.FromOutcome(request.Operation, outcome);
        return new OperationResponse(
            ProtocolTypes.OperationResponse,
            request.RequestId,
            request.MissionId,
            request.InvocationId,
            status,
            message,
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

    // v3 r6 lectores: the risk of the exact invocation when its handler can tell (IInvocationRiskAssessor), else the
    // declared one. A forbidden operation stays forbidden, and a handler that fails to answer keeps the declared risk.
    private static OperationRisk InvocationRisk(IOperationHandler handler, JsonElement arguments)
    {
        OperationRisk declared = handler.Definition.Risk;
        if (declared == OperationRisk.Forbidden || handler is not IInvocationRiskAssessor assessor)
        {
            return declared;
        }

        try
        {
            return assessor.AssessInvocationRisk(arguments) is { } assessed && assessed != OperationRisk.Forbidden
                ? assessed
                : declared;
        }
        catch (Exception exception) when (exception is InvalidOperationException
            or ArgumentException or JsonException or KeyNotFoundException)
        {
            return declared;
        }
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

    private static OperationResponse Pending(
        OperationRequest request,
        string errorCode,
        JsonElement? result) =>
        new(
            ProtocolTypes.OperationResponse,
            request.RequestId,
            request.MissionId,
            request.InvocationId,
            OperationStatuses.Pending,
            OperationVisibleFacts.FromStatus(
                request.Operation,
                OperationStatuses.Pending,
                errorCode),
            false,
            false,
            result,
            errorCode);

    private static OperationResponse Rejected(
        OperationRequest request,
        string errorCode) =>
        new(
            ProtocolTypes.OperationResponse,
            request.RequestId,
            request.MissionId,
            request.InvocationId,
            OperationStatuses.Rejected,
            OperationVisibleFacts.FromStatus(
                request.Operation,
                OperationStatuses.Rejected,
                errorCode),
            false,
            false,
            null,
            errorCode);

    private static OperationResponse InvalidArguments(OperationRequest request) =>
        new(
            ProtocolTypes.OperationResponse,
            request.RequestId,
            request.MissionId,
            request.InvocationId,
            OperationStatuses.Failed,
            OperationVisibleFacts.FromStatus(
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
