using System.Diagnostics;
using System.Text.Json.Nodes;
using Baxy.Contracts;
using Baxy.Kernel.Operations;
using Baxy.Security.Windows;

namespace Baxy.App;

/// <summary>One call the model made and what came of it, for the trace and the benches' audit against the journal.</summary>
internal sealed record NativeTurnStep(
    string Operation,
    JsonObject Arguments,
    string Status,
    bool Verified,
    string? ErrorCode,
    long ElapsedMs,
    string Observation);

/// <summary>
/// BAXY Renew's harness: the native tool loop (BFCL multi-turn, Qwen function calling, OpenAI Agents run loop). The
/// model decides every move. Each call it makes goes to the kernel, which authorizes it (risk and confirmation), and to
/// the provider, which executes and verifies it; the verified result goes back to the model as that call's result, and
/// the model calls again or answers. What the person reads and hears is what the model wrote: this class publishes it
/// as it is and never words, rewrites or vetoes anything.
/// <para>
/// A risky call the kernel challenges waits for the person: the model asks, and the answer comes back as the
/// <c>confirm_pending</c> call (by voice or text the model reads the answer; the Sí and No buttons are that call
/// directly). The kernel's token is bound to the exact invocation it challenged; anything else the person asks drops it.
/// </para>
/// <para>
/// The heartbeat (owner, 2026-10-15) runs the same loop in a turn nobody asked for: what it does on its own is only the
/// low-risk; a high-risk call (by the catalog's risk) or one that would type or click in the person's windows is held
/// as a proposal and never reaches the kernel until the person says «sí» to that exact invocation.
/// </para>
/// </summary>
internal sealed class NativeTurnLoop
{
    /// <summary>Model moves per turn. Past it the model answers in words from the results it has (turn.continue final).</summary>
    internal const int MaximumModelCalls = 15;

    private static readonly TimeSpan OperationTimeout = TimeSpan.FromSeconds(30);

    internal sealed class Host
    {
        internal required Func<CoreProcessClient?> Core { get; init; }

        internal required Func<MindSidecarClient?> Mind { get; init; }

        internal required Func<RetryableOperationRegistry?> Registry { get; init; }

        internal required Func<MemoryOperationProtector?> MemoryProtector { get; init; }

        /// <summary>Publishes what the model wrote, with its route (conversation, clarification, confirmation).</summary>
        internal required Action<string, string> Publish { get; init; }

        /// <summary>The turn could not reach an answer (mind down, core down): a state for the interface, not prose.</summary>
        internal required Action<string> Fail { get; init; }

        internal Action<NativeTurnStep>? StepCompleted { get; init; }

        internal Action? MemoryChanged { get; init; }
    }

    private static readonly TimeSpan ProposalLifetime = TimeSpan.FromMinutes(10);

    // The catalog risks the heartbeat never takes alone (borrar, enviar, apagar, comprar, instalar, cerrar con trabajo).
    private static readonly HashSet<string> ProposedRisks = new(StringComparer.Ordinal)
    {
        "work_loss", "recoverable_delete", "external_communication", "installation", "monetary",
    };

    private readonly Host _host;
    private PendingOperationConfirmation? _pending;
    private PreparedOperation? _proposal;
    private DateTimeOffset _proposalExpiresUtc;
    private bool _beat;

    internal NativeTurnLoop(Host host)
    {
        _host = host ?? throw new ArgumentNullException(nameof(host));
    }

    /// <summary>A risky call waits for the person's Sí or No (the kernel's challenge or a heartbeat's proposal).</summary>
    internal bool HasPendingConfirmation =>
        (_pending is { } pending && pending.ExpiresAtUtc > DateTimeOffset.UtcNow)
        || (_proposal is not null && _proposalExpiresUtc > DateTimeOffset.UtcNow);

    /// <summary>The person's words open a turn.</summary>
    internal async Task RunAsync(string text, CancellationToken cancellationToken)
    {
        MindSidecarClient? mind = _host.Mind();
        if (mind is not { IsTurnAvailable: true })
        {
            _host.Fail("mind_unavailable");
            return;
        }

        await DriveAsync(mind, await mind.DecideAsync(text, cancellationToken), cancellationToken)
            ;
    }

    /// <summary>The person pressed Sí or No on the pending confirmation.</summary>
    internal async Task AnswerConfirmationAsync(bool approve, string label, CancellationToken cancellationToken)
    {
        MindSidecarClient? mind = _host.Mind();
        if (mind is not { IsTurnAvailable: true })
        {
            _host.Fail("mind_unavailable");
            return;
        }

        await DriveAsync(
                mind,
                await mind.ConfirmAsync(approve, label, cancellationToken),
                cancellationToken)
            ;
    }

    /// <summary>
    /// The heartbeat: the moment goes to the model, which says whether to intervene and, if so, acts, proposes or says
    /// something; what it wrote is published on the channel the person's activity allows.
    /// </summary>
    internal async Task RunBeatAsync(JsonObject context, CancellationToken cancellationToken)
    {
        MindSidecarClient? mind = _host.Mind();
        if (mind is not { IsTurnAvailable: true })
        {
            return;
        }

        _beat = true;
        try
        {
            await DriveAsync(mind, await mind.BeatAsync(context, cancellationToken),
                cancellationToken);
        }
        finally
        {
            _beat = false;
            _ = await mind.EndBeatAsync(cancellationToken);
        }
    }

    /// <summary>A new session: nothing pending survives it.</summary>
    internal void Reset()
    {
        DropPending();
    }

    private async Task DriveAsync(MindSidecarClient mind, MindStep? step, CancellationToken cancellationToken)
    {
        for (int calls = 1; ; calls++)
        {
            switch (step)
            {
                case null:
                    _host.Fail("decision_unavailable");
                    return;
                case { Kind: "silence" }:
                    return;
                case { Kind: "reply" }:
                    _host.Publish(step.Text, HasPendingConfirmation
                        ? PublicResponseRoute.Confirmation
                        : PublicResponseRoute.Conversation);
                    return;
                case { Kind: "question" }:
                    // A question about a call that waits for the person's «sí» is that confirmation (Sí/No buttons).
                    _host.Publish(step.Text, HasPendingConfirmation
                        ? PublicResponseRoute.Confirmation
                        : PublicResponseRoute.Clarification);
                    return;
            }

            string observation = await ExecuteAsync(step.Operation!, step.Arguments!, cancellationToken);
            step = await mind.ContinueAsync(observation, final: calls >= MaximumModelCalls, _beat, cancellationToken);
        }
    }

    private async Task<string> ExecuteAsync(string operation, JsonObject arguments, CancellationToken cancellationToken)
    {
        long started = Stopwatch.GetTimestamp();
        if (operation == MindStep.ConfirmationAnswer)
        {
            return await AnswerPendingAsync(arguments, started, cancellationToken);
        }

        // Anything else the person asked for replaces a confirmation still waiting: it is dropped, never run later.
        DropPending();
        CoreProcessClient? core = _host.Core();
        if (core is not { IsReady: true })
        {
            return Record(operation, arguments, started, Observation(operation, "failed", false, "engine_unavailable"));
        }

        if (!ProductCatalog.TryGet(operation, out ProductOperationDescriptor? descriptor) || descriptor is null)
        {
            return Record(operation, arguments, started, Observation(operation, "rejected", false, "unknown_operation"));
        }

        PreparedOperation prepared;
        try
        {
            prepared = MemoryOperationProtector.IsMemoryOperation(operation)
                ? (_host.MemoryProtector() ?? throw new InvalidOperationException("memory_protection_unavailable"))
                    .Prepare(new MemoryRoutedOperation(operation, arguments)).Prepared
                : (_host.Registry() ?? throw new InvalidOperationException("outbox_unavailable"))
                    .GetOrAdd(new RoutedOperation(operation, arguments));
        }
        catch (Exception exception) when (exception is ArgumentException or InvalidOperationException
            or System.IO.InvalidDataException or System.Text.Json.JsonException)
        {
            // Arguments that do not fit the operation are a result the model reads, with what it gave, so it can call
            // again with the right ones; nothing here fills or rewrites them.
            return Record(operation, arguments, started, Observation(operation, "rejected", false,
                "arguments_invalid", new JsonObject { ["argumentsGiven"] = arguments.DeepClone() }));
        }

        if (_beat && (ProposedRisks.Contains(descriptor.Risk) || WritesInThePersonsWindow(operation)))
        {
            // Nobody asked: the call is held for the person's «sí», untouched, and the model words the proposal.
            _proposal = prepared;
            _proposalExpiresUtc = DateTimeOffset.UtcNow + ProposalLifetime;
            return Record(operation, arguments, started, new JsonObject
            {
                ["kind"] = "operation",
                ["operation"] = operation,
                ["status"] = "needs_confirmation",
                ["arguments"] = arguments.DeepClone(),
            }.ToJsonString());
        }

        return await SendAsync(core, prepared, arguments, confirmationToken: null, started, cancellationToken)
            ;
    }

    private static bool WritesInThePersonsWindow(string operation) =>
        operation is "input.visible.click" or "input.text.type" or "input.key.press" or "input.pointer.control"
            or "input.select.all" or "input.scroll" or "clipboard.paste" or "message.draft";

    private async Task<string> AnswerPendingAsync(JsonObject arguments, long started, CancellationToken cancellationToken)
    {
        bool approve = arguments["approve"] is JsonValue value && value.TryGetValue(out bool approved) && approved;
        if (_proposal is { } proposal && _proposalExpiresUtc > DateTimeOffset.UtcNow)
        {
            return await AnswerProposalAsync(proposal, approve, started, cancellationToken);
        }

        PendingOperationConfirmation? pending = HasPendingConfirmation ? _pending : null;
        if (pending is null)
        {
            DropPending();
            return Record(MindStep.ConfirmationAnswer, arguments, started,
                Observation(MindStep.ConfirmationAnswer, "failed", false, "nothing_pending"));
        }

        JsonObject pendingArguments = PrivateArguments(pending.Prepared);
        if (!approve)
        {
            DropPending();
            return Record(pending.Prepared.OperationName, pendingArguments, started,
                Observation(pending.Prepared.OperationName, "cancelled", false, "declined_by_person"));
        }

        _pending = null;
        CoreProcessClient? core = _host.Core();
        if (core is not { IsReady: true })
        {
            _host.Registry()?.MarkResolved(pending.Prepared);
            return Record(pending.Prepared.OperationName, pendingArguments, started,
                Observation(pending.Prepared.OperationName, "failed", false, "engine_unavailable"));
        }

        return await SendAsync(core, pending.Prepared, pendingArguments, pending.Token, started, cancellationToken)
            ;
    }

    // A heartbeat's proposal the person answered: «no» drops it; «sí» sends that exact invocation, and when the kernel
    // asks for its confirmation too, the person's «sí» to this invocation is that confirmation (same token binding).
    private async Task<string> AnswerProposalAsync(
        PreparedOperation proposal,
        bool approve,
        long started,
        CancellationToken cancellationToken)
    {
        JsonObject arguments = PrivateArguments(proposal);
        _proposal = null;
        if (!approve)
        {
            Resolve(proposal, MemoryOperationProtector.IsMemoryOperation(proposal.OperationName));
            return Record(proposal.OperationName, arguments, started,
                Observation(proposal.OperationName, "cancelled", false, "declined_by_person"));
        }

        CoreProcessClient? core = _host.Core();
        if (core is not { IsReady: true })
        {
            Resolve(proposal, MemoryOperationProtector.IsMemoryOperation(proposal.OperationName));
            return Record(proposal.OperationName, arguments, started,
                Observation(proposal.OperationName, "failed", false, "engine_unavailable"));
        }

        string observation = await SendAsync(core, proposal, arguments, confirmationToken: null, started,
            cancellationToken);
        if (_pending is { } challenge && ReferenceEquals(challenge.Prepared, proposal))
        {
            _pending = null;
            observation = await SendAsync(core, proposal, arguments, challenge.Token, started, cancellationToken)
                ;
        }

        return observation;
    }

    private async Task<string> SendAsync(
        CoreProcessClient core,
        PreparedOperation prepared,
        JsonObject arguments,
        string? confirmationToken,
        long started,
        CancellationToken cancellationToken)
    {
        string operation = prepared.OperationName;
        bool memory = MemoryOperationProtector.IsMemoryOperation(operation);
        OperationResponse response;
        try
        {
            response = await core.SendOperationAsync(prepared, OperationTimeout, cancellationToken, confirmationToken)
                ;
        }
        catch (Exception exception) when (exception is TimeoutException or System.IO.IOException
            or InvalidOperationException)
        {
            Resolve(prepared, memory);
            return Record(operation, arguments, started,
                Observation(operation, "failed", false, "engine_no_answer", effectUncertain: true));
        }

        if (PendingOperationConfirmation.TryCreate(response, prepared, TimeProvider.System,
                out PendingOperationConfirmation? challenge) && challenge is not null)
        {
            // The kernel asks for the person's «sí» for this exact invocation: the model asks; the answer comes back
            // as confirm_pending, and only then is this same invocation sent again with the token.
            _pending = challenge;
            return Record(operation, arguments, started, new JsonObject
            {
                ["kind"] = "operation",
                ["operation"] = operation,
                ["status"] = "needs_confirmation",
                ["arguments"] = arguments.DeepClone(),
                ["effectStarted"] = challenge.ReconciliationRequired,
            }.ToJsonString(), response);
        }

        Resolve(prepared, memory);
        string body = memory
            ? MemoryObservation(prepared, response)
            : OperationResponseProjection.Create(response, operation).Message;
        if (memory && response.Status == OperationStatuses.Completed
            && operation is not ("memory.recall" or "memory.list" or "memory.status" or "memory.export"))
        {
            _host.MemoryChanged?.Invoke();
        }

        return Record(operation, arguments, started, body, response);
    }

    // A memory result travels sealed: it is opened here and only its safe projection reaches the model.
    private string MemoryObservation(PreparedOperation prepared, OperationResponse response)
    {
        MemoryOperationProtector? protector = _host.MemoryProtector();
        if (protector is null || response.Status != OperationStatuses.Completed)
        {
            return OperationResponseProjection.Create(response, prepared.OperationName).Message;
        }

        try
        {
            using OpenedBoundProtectedJson opened = protector.OpenResult(response, prepared);
            using OpenedBoundProtectedJson privateArguments = protector.OpenPrivateArguments(prepared);
            return MemoryOperationResponseProjection.TryCreateCompleted(
                    prepared.OperationName,
                    opened.Payload,
                    out MemoryOperationResponseProjection? projection,
                    response.Replayed,
                    privateArguments.Payload)
                && projection is not null
                    ? projection.Message
                    : Observation(prepared.OperationName, "completed", false, "result_unreadable");
        }
        catch (Exception exception) when (exception is System.IO.InvalidDataException or ProtectedPayloadException)
        {
            return Observation(prepared.OperationName, "completed", false, "result_unreadable");
        }
    }

    private static JsonObject PrivateArguments(PreparedOperation prepared)
    {
        if (!MemoryOperationProtector.IsMemoryOperation(prepared.OperationName))
        {
            return JsonNode.Parse(prepared.Arguments.GetRawText()) as JsonObject ?? new JsonObject();
        }

        // A memory call's arguments stay sealed; the trace and the model see the operation, not its private values.
        return new JsonObject();
    }

    private void Resolve(PreparedOperation prepared, bool memory)
    {
        if (!memory)
        {
            _host.Registry()?.MarkResolved(prepared);
        }
    }

    private void DropPending()
    {
        if (_proposal is { } proposal)
        {
            _proposal = null;
            Resolve(proposal, MemoryOperationProtector.IsMemoryOperation(proposal.OperationName));
        }

        if (_pending is { } pending)
        {
            _pending = null;
            if (!MemoryOperationProtector.IsMemoryOperation(pending.Prepared.OperationName))
            {
                _host.Registry()?.MarkResolved(pending.Prepared);
            }
        }
    }

    private string Record(
        string operation,
        JsonObject arguments,
        long started,
        string observation,
        OperationResponse? response = null)
    {
        long elapsed = (long)Stopwatch.GetElapsedTime(started).TotalMilliseconds;
        var step = new NativeTurnStep(
            operation,
            MemoryOperationProtector.IsMemoryOperation(operation) ? new JsonObject() : (JsonObject)arguments.DeepClone(),
            response?.Status ?? StatusOf(observation),
            response?.Verified ?? false,
            response?.ErrorCode,
            elapsed,
            observation);
        ShellTraceSink.Record(ShellTraceScopes.Turn, ShellTraceSink.TurnId, "loop.step",
            $"{operation}.{step.Status}.{(step.Verified ? "verified" : "unverified")}.ms.{elapsed}");
        _host.StepCompleted?.Invoke(step);
        return observation;
    }

    private static string StatusOf(string observation)
    {
        try
        {
            return (string?)JsonNode.Parse(observation)?["status"] ?? "unknown";
        }
        catch (System.Text.Json.JsonException)
        {
            return "unknown";
        }
    }

    private static string Observation(
        string operation,
        string status,
        bool verified,
        string error,
        JsonObject? extra = null,
        bool effectUncertain = false)
    {
        var facts = new JsonObject
        {
            ["kind"] = "operation",
            ["operation"] = operation,
            ["status"] = status,
            ["verified"] = verified,
            ["succeeded"] = false,
            ["error"] = error,
            ["effectUncertain"] = effectUncertain,
        };
        foreach ((string key, JsonNode? value) in extra ?? [])
        {
            facts[key] = value?.DeepClone();
        }

        return facts.ToJsonString();
    }
}
