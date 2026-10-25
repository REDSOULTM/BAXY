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

    // Auditoría del núcleo 2026-10-23 (replay never re-executes without the person): the invocations whose last run ended
    // retryable with nothing done (the provider said so), the only started ones a retry runs again unasked; and those
    // whose uncertain start the person is being asked about, so the yes to that question is not revoked again. Both live
    // under the execution gate, in memory only: after a restart every started invocation is uncertain.
    private const int MaximumRememberedRetries = 1024;
    private readonly HashSet<string> _safeRetries = new(StringComparer.Ordinal);
    private readonly HashSet<string> _reconciling = new(StringComparer.Ordinal);

    // Revisión 2026-10-25 (reservas de reintento): a retryable answer leaves its invocation begun, holding a completion
    // reservation (2 MiB of the journal) for the retry; the App resolves the call once answered and never retries it, so
    // each one held its reservation until the Core restarted, and past a few (the volume gives them) every new
    // invocation was refused with journal_capacity_reached. An open retry ends when its window passes, or before the
    // journal would refuse a new invocation: its own last answer, made final, is written first (the journal releases the
    // reservation only once that terminal is on disk), and a retry after that replays it, never runs again.
    internal static readonly TimeSpan RetryWindow = TimeSpan.FromMinutes(10);
    private readonly List<OpenRetry> _openRetries = [];
    private readonly TimeProvider _time;

    // Hallazgo E030 (w9-sha): the versions the responses sent gave, completed or not, under the execution gate too.
    private readonly ToldVersions _toldVersions = new();

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
        _time = options?.Time ?? TimeProvider.System;
    }

    public async ValueTask<OperationResponse> ExecuteAsync(
        OperationRequest request,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(request);
        ContractValidator.Validate(request);
        // Revisión 2026-10-22 (K-5): a string or a name escaped as a lone surrogate («\uD800») parses, and reading it as
        // text throws; past here it escaped the engine before any terminal state and ended the core (exit 70).
        if (!HoldsOnlyText(request.Arguments))
        {
            return Rejected(request, "invalid_arguments");
        }

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
            await CloseOpenRetriesAsync(lapsedOnly: true, keep: null).ConfigureAwait(false);
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
                OperationResponse replayed = PrivateOperationBoundary.NormalizeReplay(
                    request,
                    completed.Response,
                    _privateEnvelopeAuthenticator);
                _toldVersions.Record(replayed);
                return replayed;
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
                ? Evaluate(handler, handler.Definition.Risk, request.Arguments)
                : null;
            // Al máximo, flujos: an invocation that would ask the person is read first (IInvocationPreflight): its own
            // lower risk, or the failure it would end in before any effect, which is answered without asking for a yes.
            // One that started before and was not completed is reconciled as it stands: its effect may have happened.
            OperationOutcome? preflightFailure = null;
            if (policy == PolicyDecision.RequireConfirmation && handler is IInvocationPreflight preflight)
            {
                InvocationPreflightResult found = await Preflight(preflight, request.Arguments, cancellationToken)
                    .ConfigureAwait(false);
                if (found.Failure is { } failure && startedFingerprint is null)
                {
                    preflightFailure = failure;
                    policy = PolicyDecision.Allow;
                }
                else if (found.Risk is { } risk)
                {
                    policy = Evaluate(handler, risk, request.Arguments, landingRead: true);
                }
            }
            // Renew al máximo (guarda msconfig, guarda diálogo destructivo): an invocation whose handler says it may be
            // riskier than declared is read in normal mode though it would go without asking; only a higher risk it
            // finds is taken (it then asks, bound to this invocation), never a failure. Bypass asks as RiskPolicy says.
            else if (policy == PolicyDecision.Allow
                && handler is IInvocationPreflight raising
                && _confirmationMode() == ConfirmationMode.Normal
                && MayRaise(raising, request.Arguments))
            {
                InvocationPreflightResult found = await Preflight(raising, request.Arguments, cancellationToken)
                    .ConfigureAwait(false);
                if (found.Risk is { } risk && risk > handler.Definition.Risk)
                {
                    policy = Evaluate(handler, risk, request.Arguments);
                }
            }

            // Hallazgo E030 (w9-sha): a replacement whose expected version only a refusal or a failure told the mind
            // (ToldVersions) saw nothing of what it replaces; in normal mode it asks, bound to this invocation.
            if (policy == PolicyDecision.Allow
                && preflightFailure is null
                && _confirmationMode() == ConfirmationMode.Normal
                && _toldVersions.OnlyToldBy(request.Operation, request.Arguments))
            {
                policy = PolicyDecision.RequireConfirmation;
            }

            // Auditoría del núcleo 2026-10-23: an invocation that started before and did not end (the handler threw, the core
            // stopped, its last run may have acted) is not run again without the person, in either mode: its effect may
            // stand. It asks, bound to it, with reconciliationRequired; a yes given before that run was for that run only.
            // A retry after a run that said nothing was done goes on as the provider's own retry.
            bool uncertainStart = startedFingerprint is not null
                && knownOperation
                && handler is not null
                && validArguments
                && preflightFailure is null
                && !_safeRetries.Contains(request.InvocationId);
            if (uncertainStart)
            {
                policy = PolicyDecision.RequireConfirmation;
                if (_reconciling.Add(request.InvocationId))
                {
                    _confirmationAuthority.Revoke(ConfirmationBinding.Create(request, fingerprint));
                }
            }

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

            if (!await TryRecordStartedAsync(request, fingerprint, cancellationToken).ConfigureAwait(false))
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
                    InvalidArguments(request, handler),
                    cancellationToken).ConfigureAwait(false);
            }

            var invocation = new OperationInvocation(
                request.RequestId,
                request.MissionId,
                request.InvocationId,
                request.Arguments);
            // This run spends what was known of the earlier one: only its own outcome can make a retry safe again.
            _safeRetries.Remove(request.InvocationId);
            _reconciling.Remove(request.InvocationId);
            _openRetries.RemoveAll(open => open.Is(request.InvocationId));
            OperationOutcome outcome = preflightFailure ?? await handler
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

            // Auditoría del núcleo 2026-10-23 (estados terminales honestos): a handler that says it succeeded but could
            // not verify it did act. It ends failed, never completed, and its effect may stand, as a private operation's
            // already does (PrivateOperationBoundary): «failed» alone read as «nothing happened» and invited a repeat.
            if (outcome is { Succeeded: true, Verified: false, EffectMayHaveOccurred: false })
            {
                outcome = OperationOutcome.Failure(
                    outcome.ErrorCode ?? "verification_failed",
                    outcome.Result,
                    effectMayHaveOccurred: true,
                    causeCode: outcome.CauseCode);
            }

            OperationResponse response = ToResponse(request, outcome);
            _toldVersions.Record(response);
            if (outcome.Retryable)
            {
                // Revisión 2026-10-22 (K-6): a retryable outcome keeps its grant for the retry, unless its effect may
                // have happened: the yes was given to one execution, so the retry asks again (reconciliationRequired)
                // instead of running a second time on the same token.
                if (outcome.EffectMayHaveOccurred && grantedBinding is { } spent)
                {
                    _confirmationAuthority.Revoke(spent);
                }
                else if (!outcome.EffectMayHaveOccurred && !uncertainStart)
                {
                    if (_safeRetries.Count >= MaximumRememberedRetries)
                    {
                        // Forgetting one only makes its retry ask.
                        _safeRetries.Clear();
                    }

                    _safeRetries.Add(request.InvocationId);
                }

                _openRetries.Add(new OpenRetry(request, fingerprint, outcome, _time.GetUtcNow() + RetryWindow));
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
        try
        {
            await _journal
                .RecordCompletedAsync(request, fingerprint, response, cancellationToken)
                .ConfigureAwait(false);
        }
        catch (JournalCapacityException) when (response.Result is not null)
        {
            // Auditoría del núcleo 2026-10-23: evidence larger than what the journal reserved before the effect ended the
            // core after the effect, with no terminal state. The terminal is kept without the evidence, as the protocol
            // line already drops it (ProtocolJson.SerializeBoundedToUtf8Bytes); its facts (the message) stay.
            response = response with { Result = null };
            await _journal
                .RecordCompletedAsync(request, fingerprint, response, cancellationToken)
                .ConfigureAwait(false);
        }
        if (grantedBinding is { } binding)
        {
            _confirmationAuthority.Revoke(binding);
        }

        _safeRetries.Remove(request.InvocationId);
        _reconciling.Remove(request.InvocationId);
        _openRetries.RemoveAll(open => open.Is(request.InvocationId));
        return response;
    }

    // The start of an invocation, recorded with its completion reserved. When the journal has no room for that
    // reservation and retries nobody made hold some, those end (CloseOpenRetriesAsync) and the start is tried once more.
    private async ValueTask<bool> TryRecordStartedAsync(
        OperationRequest request,
        string fingerprint,
        CancellationToken cancellationToken)
    {
        try
        {
            await _journal.RecordStartedAsync(request, fingerprint, cancellationToken).ConfigureAwait(false);
            return true;
        }
        catch (JournalCapacityException) when (_openRetries.Exists(open => !open.Is(request.InvocationId)))
        {
        }
        catch (JournalCapacityException)
        {
            return false;
        }

        await CloseOpenRetriesAsync(lapsedOnly: false, keep: request.InvocationId).ConfigureAwait(false);
        try
        {
            await _journal.RecordStartedAsync(request, fingerprint, cancellationToken).ConfigureAwait(false);
            return true;
        }
        catch (JournalCapacityException)
        {
            return false;
        }
    }

    // Each open retry (all, or only those whose window passed; never keep) ends with its own last answer made final:
    // failed, with its code, its evidence and whether its effect may stand. Written through the journal's completion,
    // which appends the terminal before it gives back the reservation.
    private async ValueTask CloseOpenRetriesAsync(bool lapsedOnly, string? keep)
    {
        if (_openRetries.Count == 0)
        {
            return;
        }

        DateTimeOffset now = _time.GetUtcNow();
        foreach (OpenRetry open in _openRetries.ToArray())
        {
            if ((lapsedOnly && open.Until > now) || (keep is not null && open.Is(keep)))
            {
                continue;
            }

            _openRetries.Remove(open);
            OperationOutcome last = open.Outcome;
            OperationOutcome final = OperationOutcome.Failure(
                last.ErrorCode ?? "operation_failed",
                last.Result,
                last.EffectMayHaveOccurred,
                last.CauseCode);
            using var commit = new CancellationTokenSource(TerminalCommitTimeout);
            await CompleteAsync(open.Request, open.Fingerprint, ToResponse(open.Request, final), commit.Token)
                .ConfigureAwait(false);
        }
    }

    private sealed record OpenRetry(
        OperationRequest Request,
        string Fingerprint,
        OperationOutcome Outcome,
        DateTimeOffset Until)
    {
        public bool Is(string invocationId) =>
            string.Equals(Request.InvocationId, invocationId, StringComparison.Ordinal);
    }

    // K-2 refinada: a risk the preflight lowered read where the invocation lands (landingRead).
    private PolicyDecision Evaluate(
        IOperationHandler handler,
        OperationRisk risk,
        JsonElement arguments,
        bool landingRead = false) =>
        RiskPolicy.Evaluate(
            risk,
            _confirmationMode(),
            handler.Definition.Name,
            // Computer use (CONTRATO_VISTA_ACCION.md §2.1): the step's
            // exact arguments decide whether it reaches a person.
            arguments,
            landingRead);

    // v3 r6 lectores: what the handler reads of the exact invocation. A handler that fails to answer keeps the declared
    // risk, and only a terminal failure with nothing done is taken as the invocation's end (never a success, a retry or
    // a failure after an effect).
    private static async ValueTask<InvocationPreflightResult> Preflight(
        IInvocationPreflight preflight,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        InvocationPreflightResult found;
        try
        {
            found = await preflight.PreflightAsync(arguments, cancellationToken).ConfigureAwait(false);
        }
        // Auditoría del núcleo 2026-10-23: any read that fails keeps the declared risk, not only the four kinds listed
        // before: an IOException or a Win32Exception of a window read escaped the engine before any terminal state and
        // ended the core. Only the caller's own cancellation goes on as one.
        catch (Exception exception) when (exception is not OperationCanceledException
            || !cancellationToken.IsCancellationRequested)
        {
            return InvocationPreflightResult.Proceed;
        }

        return found.Failure is { Succeeded: false, Verified: false, Retryable: false, EffectMayHaveOccurred: false }
            or null
            ? found
            : InvocationPreflightResult.Proceed;
    }

    // Auditoría del núcleo 2026-10-23: whether a handler says this invocation may be riskier than declared. MayRaise is
    // pure by contract; one that throws says nothing, and the invocation keeps its declared risk, as a read that fails
    // does (Preflight), instead of the exception leaving the engine before any terminal state.
    private static bool MayRaise(IInvocationPreflight preflight, JsonElement arguments)
    {
        try
        {
            return preflight.MayRaise(arguments);
        }
        catch (Exception exception) when (exception is not OperationCanceledException)
        {
            return false;
        }
    }

    // Every string and property name decodes to text (no lone surrogate).
    private static bool HoldsOnlyText(JsonElement element)
    {
        try
        {
            return element.ValueKind switch
            {
                JsonValueKind.Object => element.EnumerateObject()
                    .All(static property => property.Name is not null && HoldsOnlyText(property.Value)),
                JsonValueKind.Array => element.EnumerateArray().All(HoldsOnlyText),
                JsonValueKind.String => element.GetString() is not null,
                _ => true,
            };
        }
        catch (InvalidOperationException)
        {
            return false;
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
            // Only Kernel.Tests' definitions have no catalog entry (OperationDefinition's internal seam).
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

    // Which arguments and what each takes, from the catalog's schema; a private operation's arguments travel sealed,
    // so they are named by nothing here.
    private static OperationResponse InvalidArguments(OperationRequest request, IOperationHandler handler) =>
        new(
            ProtocolTypes.OperationResponse,
            request.RequestId,
            request.MissionId,
            request.InvocationId,
            OperationStatuses.Failed,
            OperationVisibleFacts.FromStatus(
                request.Operation,
                OperationStatuses.Failed,
                "invalid_arguments",
                handler.Definition.ProductDescriptor is { } descriptor
                    && !PrivateOperationBoundary.IsPrivateOperation(request.Operation)
                    ? OperationArgumentValidator.Problems(request.Arguments, descriptor.ArgumentsSchema)
                    : null),
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
