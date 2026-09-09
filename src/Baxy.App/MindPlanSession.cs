using System.IO;
using System.Text.Json.Nodes;
using Baxy.Contracts;
using Baxy.Kernel.Operations;

namespace Baxy.App;

/// <summary>
/// Máquina de estados de un plan multipaso: persistencia, ejecución, confirmación
/// y replan. No conoce la ventana; habla por el <see cref="Host"/>.
/// </summary>
internal sealed class MindPlanSession
{
    internal sealed class Host
    {
        internal required Func<CoreProcessClient?> Core { get; init; }

        internal required Func<MindSidecarClient?> Mind { get; init; }

        internal required Action<string, UserMessageEvent?> Publish { get; init; }

        internal required Action<string> SetStatus { get; init; }

        internal required Func<RetryableOperationRegistry, PreparedOperation, bool> TryMarkResolved
        {
            get;
            init;
        }
    }

    private readonly Host _host;
    private DurablePlanStore? _store;
    private PendingMindPlanExecution? _pending;

    internal MindPlanSession(Host host)
    {
        _host = host ?? throw new ArgumentNullException(nameof(host));
    }

    internal bool HasPending => _pending is not null;

    internal PendingMindPlanExecution? Current => _pending;

    internal void EnsureStore() => _store ??= DurablePlanStore.CreateDefault();

    internal void UseStore(DurablePlanStore store)
    {
        _store = store ?? throw new ArgumentNullException(nameof(store));
    }

    internal void TryRestore(RetryableOperationRegistry registry)
    {
        ArgumentNullException.ThrowIfNull(registry);
        EnsureStore();
        _pending ??= _store!.Load(registry);
    }

    internal void Begin(PendingMindPlanExecution execution)
    {
        ArgumentNullException.ThrowIfNull(execution);
        _pending = execution;
        Persist(execution);
    }

    internal void Clear()
    {
        _pending = null;
        _store?.Clear();
    }

    internal async Task ExecuteAsync(
        PendingMindPlanExecution execution,
        RetryableOperationRegistry registry,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(execution);
        ArgumentNullException.ThrowIfNull(registry);
        CoreProcessClient client = _host.Core()
            ?? throw new InvalidOperationException("El motor local no está disponible.");
        MindSidecarClient mind = _host.Mind()
            ?? throw new InvalidOperationException("La mente local no está disponible.");

        while (execution.NextIndex < execution.Steps.Count)
        {
            MindPlanStep step = execution.CurrentStep;
            _host.SetStatus(
                execution.Steps.Count == 1
                    ? "acting"
                    : $"Ejecutando paso {execution.NextIndex + 1} de {execution.Steps.Count}");
            JsonObject? arguments = step.Arguments?.DeepClone() as JsonObject;
            JsonObject? identityArguments = null;
            JsonArray groundingObservations = [];
            if (string.Equals(
                    step.ArgumentsMode,
                    "after_dependencies",
                    StringComparison.Ordinal))
            {
                if (!PlanObservationProjector.TrySelectVerifiedDependencies(
                        step,
                        execution.Observations,
                        out groundingObservations))
                {
                    FinishWithFailure(execution, TurnVisibleFacts.Failure("step_unverified"));
                    return;
                }

                if (PlanObservationProjector.IsVerifiedEmptyFileSearch(step, groundingObservations))
                {
                    FinishWithFailure(execution, TurnVisibleFacts.Failure("file_search_no_matches"));
                    return;
                }

                if (PlanObservationProjector.TryGroundIdentityArguments(
                        step,
                        groundingObservations,
                        out identityArguments)
                    && identityArguments is not null)
                {
                    arguments ??= new JsonObject();
                    foreach ((string key, JsonNode? value) in identityArguments)
                    {
                        arguments[key] = value?.DeepClone();
                    }
                }
            }

            if (arguments is null
                || !MindPlanBoundary.ArgumentsSatisfyExactSchema(
                    step.Operation,
                    arguments))
            {
                arguments = await mind.GroundPlanStepAsync(
                    execution.Objective,
                    step,
                    groundingObservations,
                    TimeSpan.FromSeconds(30),
                    cancellationToken);

                if (arguments is null)
                {
                    FinishWithFailure(execution, TurnVisibleFacts.Failure("step_data_missing"));
                    return;
                }

                if (identityArguments is not null)
                {
                    foreach ((string key, JsonNode? value) in identityArguments)
                    {
                        arguments[key] = value?.DeepClone();
                    }
                }
            }

            arguments = MindArgumentNormalization.Normalize(
                step.Operation,
                execution.Objective,
                arguments);
            if (string.Equals(
                    step.ArgumentsMode,
                    "after_dependencies",
                    StringComparison.Ordinal)
                && !PlanObservationProjector
                    .ArgumentsUseVerifiedDependencyAuthority(
                        step.Operation,
                        arguments,
                        groundingObservations))
            {
                FinishWithFailure(execution, TurnVisibleFacts.Failure("step_unlinkable"));
                return;
            }

            MindPlanBoundary.ValidateGroundedArguments(step.Operation, arguments);
            var routed = new RoutedOperation(step.Operation, arguments);
            PreparedOperation prepared = execution.PendingOperation
                ?? registry.GetOrAdd(routed);
            execution.PendingOperation = prepared;
            Persist(execution);
            OperationResponse response = await client.SendOperationAsync(
                prepared,
                TimeSpan.FromSeconds(20),
                cancellationToken);
            if (PendingOperationConfirmation.TryCreate(
                    response,
                    prepared,
                    TimeProvider.System,
                    out PendingOperationConfirmation? confirmation)
                && confirmation is not null)
            {
                StageConfirmation(execution, confirmation);
                return;
            }

            if (response.Status == OperationStatuses.Pending)
            {
                execution.PendingEffectMayHaveOccurred |= response.EffectMayHaveOccurred;
                _pending = execution;
                Persist(execution);
                _host.Publish(
                    response.EffectMayHaveOccurred
                        ? TurnVisibleFacts.Failure(
                            "step_uncertain",
                            new JsonObject { ["step"] = execution.NextIndex + 1 })
                        : TurnVisibleFacts.Confirmation(
                            "step_pending_retry",
                            TurnVisibleFacts.ContinueCancel,
                            new JsonObject { ["step"] = execution.NextIndex + 1 }),
                    response.EffectMayHaveOccurred
                        ? UserMessageEvent.Error(
                            UserMessageDiagnosticCodes.ActionNotCompleted)
                        : UserMessageEvent.Confirmation);
                return;
            }

            if (response.Status == OperationStatuses.Completed && response.Verified)
            {
                CompleteStep(execution, registry, prepared, step, response);
                continue;
            }

            if (MindPlanBoundary.MustRetainAmbiguousEffect(response))
            {
                execution.PendingOperation = prepared;
                execution.PendingEffectMayHaveOccurred = true;
                _pending = execution;
                Persist(execution);
                _host.Publish(
                    MissionNarration.CreateUncertainEffectMessage(execution),
                    UserMessageEvent.Error(UserMessageDiagnosticCodes.ActionNotCompleted));
                return;
            }

            _ = _host.TryMarkResolved(registry, prepared);
            execution.PendingOperation = null;
            Persist(execution);

            if (!response.EffectMayHaveOccurred && execution.ReplanCount < 2)
            {
                MindPlanResult? replacement = await TryReplanAsync(
                    execution,
                    step,
                    response,
                    cancellationToken);
                if (replacement is { Kind: "plan" }
                    && MindPlanBoundary.IsSafeReplanSuffix(execution, replacement))
                {
                    try
                    {
                        _ = MindPlanBoundary.ValidateAndConvert(execution.Objective, replacement);
                    }
                    catch (Baxy.Kernel.Planning.MissionPlanValidationException)
                    {
                        FinishWithFailure(execution, TurnVisibleFacts.Failure("continue_unsafe"));
                        return;
                    }

                    var replanned = new PendingMindPlanExecution(
                        execution.Objective,
                        replacement.Steps,
                        execution.ReplanCount + 1);
                    foreach (JsonNode? observation in execution.Observations)
                    {
                        replanned.Observations.Add(observation?.DeepClone());
                    }

                    replanned.CompletedMessages.AddRange(execution.CompletedMessages);
                    _pending = replanned;
                    Persist(replanned);
                    execution = replanned;
                    continue;
                }
            }

            FinishWithFailure(
                execution,
                response.Message);
            return;
        }

        Clear();
        if (execution.CompletedMessages.Count == 1)
        {
            _host.Publish(
                execution.CompletedMessages[0],
                UserMessageEvent.Status);
            return;
        }

        _host.Publish(
            MissionNarration.CreateCompletionMessage(execution.CompletedMessages, execution.Objective),
            null);
    }

    internal async Task HandlePendingAsync(
        string text,
        RetryableOperationRegistry registry,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(text);
        ArgumentNullException.ThrowIfNull(registry);
        PendingMindPlanExecution execution = _pending
            ?? throw new InvalidOperationException("No hay un plan pendiente.");
        if (execution.Confirmation is { } confirmation)
        {
            switch (ConfirmationReplyParser.Parse(text))
            {
                case ConfirmationReplyKind.Invalid:
                    _host.Publish(
                        confirmation.ReconciliationRequired
                            ? MissionNarration.CreateConfirmationMessage(execution,
                                "step_started_needs_check",
                                TurnVisibleFacts.ConfirmCancel)
                            : MissionNarration.CreateConfirmationMessage(execution,
                                "step_confirm_or_cancel",
                                TurnVisibleFacts.ConfirmCancel),
                        UserMessageEvent.Confirmation);
                    return;
                case ConfirmationReplyKind.Cancel:
                    if (!execution.CanAbandonConfirmation)
                    {
                        Persist(execution);
                        _host.Publish(
                            MissionNarration.CreateConfirmationMessage(execution,
                                "cannot_cancel_started_step",
                                TurnVisibleFacts.ConfirmCancel),
                            UserMessageEvent.Confirmation);
                        return;
                    }

                    registry.MarkResolved(confirmation.Prepared);
                    Clear();
                    _host.Publish(
                        MissionNarration.CreateCancellationMessage(execution),
                        null);
                    return;
                case ConfirmationReplyKind.Confirm:
                    CoreProcessClient client = _host.Core()
                        ?? throw new InvalidOperationException("El motor local no está disponible.");
                    OperationResponse response = await client.SendOperationAsync(
                        confirmation.Prepared,
                        TimeSpan.FromSeconds(20),
                        cancellationToken,
                        confirmation.Token);
                    execution.Confirmation = null;
                    if (response.Status == OperationStatuses.Completed && response.Verified)
                    {
                        CompleteStep(
                            execution,
                            registry,
                            confirmation.Prepared,
                            execution.CurrentStep,
                            response);
                        await ExecuteAsync(execution, registry, cancellationToken);
                        return;
                    }

                    if (PendingOperationConfirmation.TryCreate(
                            response,
                            confirmation.Prepared,
                            TimeProvider.System,
                            out PendingOperationConfirmation? refreshed)
                        && refreshed is not null)
                    {
                        StageConfirmation(execution, refreshed);
                        return;
                    }

                    if (MainWindowViewModel.ShouldRetainRetryIdentity(response))
                    {
                        execution.PendingOperation = confirmation.Prepared;
                        execution.PendingEffectMayHaveOccurred |=
                            response.EffectMayHaveOccurred;
                        _pending = execution;
                        Persist(execution);
                        _host.Publish(
                            response.EffectMayHaveOccurred
                                ? MissionNarration.CreateUncertainEffectMessage(execution)
                                : MissionNarration.CreateConfirmationMessage(execution,
                                    "confirmed_pending",
                                    TurnVisibleFacts.ContinueCancel),
                            null);
                        return;
                    }

                    _ = _host.TryMarkResolved(registry, confirmation.Prepared);
                    execution.PendingOperation = null;
                    FinishWithFailure(
                        execution,
                        TurnVisibleFacts.Failure("confirmed_no_effect"));
                    return;
                default:
                    throw new InvalidDataException("La respuesta de confirmación no es válida.");
            }
        }

        ConfirmationReplyKind reply = ConfirmationReplyParser.Parse(text);
        if (reply == ConfirmationReplyKind.Cancel)
        {
            if (execution.PendingEffectMayHaveOccurred)
            {
                Persist(execution);
                _host.Publish(
                    MissionNarration.CreateUncertainEffectMessage(execution),
                    UserMessageEvent.Error(UserMessageDiagnosticCodes.ActionNotCompleted));
            }
            else
            {
                if (execution.PendingOperation is not null)
                {
                    registry.MarkResolved(execution.PendingOperation);
                }

                Clear();
                _host.Publish(MissionNarration.CreateCancellationMessage(execution), null);
            }

            return;
        }

        if (execution.PendingEffectMayHaveOccurred)
        {
            if ((reply == ConfirmationReplyKind.Confirm
                    || string.Equals(
                        text.Trim(),
                        "continuar",
                        StringComparison.OrdinalIgnoreCase)
                    || string.Equals(
                        text.Trim(),
                        "continue",
                        StringComparison.OrdinalIgnoreCase))
                && MindPlanBoundary.CanRefreshConfirmationChallenge(execution))
            {
                await ExecuteAsync(execution, registry, cancellationToken);
                return;
            }

            _host.Publish(
                MindPlanBoundary.CanRefreshConfirmationChallenge(execution)
                    ? MissionNarration.CreateConfirmationMessage(execution,
                                "keep_recovery_evidence",
                        TurnVisibleFacts.ConfirmCancel)
                    : MissionNarration.CreateUncertainEffectMessage(execution),
                MindPlanBoundary.CanRefreshConfirmationChallenge(execution)
                    ? UserMessageEvent.Confirmation
                    : UserMessageEvent.Error(UserMessageDiagnosticCodes.ActionNotCompleted));
            return;
        }

        if (reply != ConfirmationReplyKind.Confirm
            && !string.Equals(text.Trim(), "continuar", StringComparison.OrdinalIgnoreCase)
            && !string.Equals(text.Trim(), "continue", StringComparison.OrdinalIgnoreCase))
        {
            _host.Publish(
                MissionNarration.CreateConfirmationMessage(execution,
                    "confirmed_pending", TurnVisibleFacts.ContinueCancel),
                UserMessageEvent.Confirmation);
            return;
        }

        await ExecuteAsync(execution, registry, cancellationToken);
    }

    private void StageConfirmation(
        PendingMindPlanExecution execution,
        PendingOperationConfirmation confirmation)
    {
        execution.RequireConfirmation(confirmation);
        _pending = execution;
        Persist(execution);
        _host.Publish(
            MissionNarration.CreateConfirmationMessage(execution,
                confirmation.ReconciliationRequired
                    ? "step_interrupted_uncertain"
                    : "step_needs_confirmation",
                TurnVisibleFacts.ConfirmCancel),
            UserMessageEvent.Confirmation);
    }

    private void CompleteStep(
        PendingMindPlanExecution execution,
        RetryableOperationRegistry registry,
        PreparedOperation prepared,
        MindPlanStep step,
        OperationResponse response)
    {
        _ = _host.TryMarkResolved(registry, prepared);
        execution.PendingOperation = null;
        execution.PendingEffectMayHaveOccurred = false;
        execution.Observations.Add(
            PlanObservationProjector.Create(step.Id, step.Operation, response));
        execution.CompletedMessages.Add(
            OperationResponseProjection.Create(response, step.Operation).Message);
        execution.NextIndex++;
        if (execution.NextIndex < execution.Steps.Count)
        {
            Persist(execution);
        }
    }

    private async Task<MindPlanResult?> TryReplanAsync(
        PendingMindPlanExecution execution,
        MindPlanStep failedStep,
        OperationResponse response,
        CancellationToken cancellationToken)
    {
        MindSidecarClient? mind = _host.Mind();
        if (mind is null || !mind.IsReady)
        {
            return null;
        }

        MindReplanSuffixContract pendingSuffix =
            MindPlanBoundary.CapturePendingSuffix(execution);
        var recovery = new JsonObject
        {
            ["failedOperation"] = failedStep.Operation,
            ["errorCode"] = response.ErrorCode ?? "operation_failed",
            ["effectMayHaveOccurred"] = false,
            ["completed"] = execution.Observations.DeepClone(),
            ["instruction"] =
                "Conserva los pasos completados; propone solo el sufijo pendiente y preserva exactamente la operación, el propósito y los argumentos literales declarados para cada paso.",
        };
        return await mind.PlanAsync(
            execution.Objective,
            [],
            TimeSpan.FromSeconds(60),
            cancellationToken,
            recovery,
            expectedSuffix: pendingSuffix);
    }

    private void FinishWithFailure(PendingMindPlanExecution execution, string reason)
    {
        Clear();
        _host.Publish(
            MissionNarration.CreateFailureMessage(execution.CompletedMessages, reason),
            UserMessageEvent.Error(UserMessageDiagnosticCodes.ActionNotCompleted));
    }

    private void Persist(PendingMindPlanExecution execution)
    {
        DurablePlanStore store = _store
            ?? throw new InvalidOperationException("El store durable del planner no está disponible.");
        store.Save(execution);
    }
}
