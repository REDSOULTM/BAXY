using System.Diagnostics;
using System.Text.Json.Nodes;
using Baxy.Contracts;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Infrastructure;
using Baxy.Security.Windows;

namespace Baxy.App;

/// <summary>One call the model made and what came of it, for the trace, the benches' audit against the journal and
/// the view's step chips. <paramref name="Id"/> names the call from its start (<see cref="NativeTurnLoop.Host.StepStarted"/>);
/// <paramref name="Sent"/>: the call reached its provider (it may have had an effect, or sent something out).</summary>
internal sealed record NativeTurnStep(
    string Operation,
    JsonObject Arguments,
    string Status,
    bool Verified,
    string? ErrorCode,
    long ElapsedMs,
    string Observation,
    string Id = "",
    bool Sent = false);

/// <summary>A call waiting for the person's Sí or No, as its question is published (the view's card).
/// <paramref name="EffectStarted"/>: the kernel asks again for a call whose earlier attempt may have happened
/// (reconciliationRequired). <paramref name="Cause"/>: why the person's own turn held it (NetworkEgress's code).</summary>
internal sealed record NativeTurnConfirmation(
    string Operation,
    JsonObject Arguments,
    string Risk,
    DateTimeOffset ExpiresUtc,
    bool Proposal,
    bool EffectStarted = false,
    string? Cause = null);

/// <summary>
/// BAXY Renew's harness: the native tool loop (BFCL multi-turn, Qwen function calling, OpenAI Agents run loop). The
/// model decides every move. Each call it makes goes to the kernel, which authorizes it (risk and confirmation), and to
/// the provider, which executes and verifies it; the verified result goes back to the model as that call's result, and
/// the model calls again or answers. What the person reads and hears is what the model wrote: this class publishes it
/// as it is and never words, rewrites or vetoes anything.
/// <para>
/// A risky call the kernel challenges waits for the person: the model asks, and the answer comes back as the
/// <c>confirm_pending</c> call (by voice or text the model reads the answer; the Sí and No buttons are that call
/// directly). The kernel's token is bound to the exact invocation it challenged; anything else the person asks drops it,
/// and so does a line of a later turn that is not its question: the person's words answer only BAXY's last question.
/// </para>
/// <para>
/// The heartbeat (owner, 2026-10-15) runs the same loop in a turn nobody asked for: a call that is not harmless and
/// reversible (<see cref="BeatProposes"/>: a risk other than read_only or low_reversible, or one of the catalog's
/// <see cref="OperationEffects"/>) is held as a proposal and never reaches the kernel until the person says «sí» to that
/// exact invocation; any other call runs. A heartbeat never starts while a confirmation waits for the person.
/// </para>
/// <para>
/// In a turn the person opened, a call that sends out to a host nobody gave, or launches a game they did not name
/// (<see cref="NetworkEgress"/>), is held the same way, and asks as a confirmation.
/// </para>
/// <para>
/// A turn the person opened that has published nothing <see cref="SilenceNotice.After"/> after their words or press
/// arrived says the mind's notice, again while it stays silent (<see cref="SilenceNotice"/>); the model's decisions are
/// untouched by it.
/// </para>
/// </summary>
internal sealed class NativeTurnLoop
{
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

        /// <summary>Says the mind's notice aloud (<see cref="SilenceNotice"/>): a line that is not the turn's answer.</summary>
        internal required Action<string> Notice { get; init; }

        internal Action<NativeTurnStep>? StepCompleted { get; init; }

        /// <summary>A call is about to run: its id, operation and arguments (a memory call's arguments stay sealed).</summary>
        internal Action<string, string, JsonObject>? StepStarted { get; init; }

        /// <summary>The question about a waiting call was published: the person can answer it now.</summary>
        internal Action<NativeTurnConfirmation>? ConfirmationAsked { get; init; }

        /// <summary>That call's end: approved, declined, expired, or dropped because the person asked something else.</summary>
        internal Action<string>? ConfirmationResolved { get; init; }

        /// <summary>The owner's switch that refuses a call before it runs (FieldSettings.Refusal), as its code.</summary>
        internal Func<string, JsonObject, string?>? Refuse { get; init; }

        internal Action? MemoryChanged { get; init; }

        /// <summary>The chat forgot everything memory held (memory.forget, scope all): the kept conversations go too.</summary>
        internal Action? ForgotEverything { get; init; }

        /// <summary>Where each of the person's known folders is, by its label (SaidFolders; tests point it elsewhere).</summary>
        internal Func<string, string?>? PersonFolder { get; init; }
    }

    /// <summary>How long a heartbeat's proposal waits for the person's Sí or No.</summary>
    internal static readonly TimeSpan ProposalLifetime = TimeSpan.FromMinutes(10);

    /// <summary>How long a call the engine never answered keeps its invocation for an identical retry, at most.</summary>
    internal static readonly TimeSpan UncertainLifetime = TimeSpan.FromMinutes(2);

    private readonly Host _host;
    // 2026-10-22, review of the App: one clock for whether a waiting call is still waiting and how it ended.
    private readonly TimeProvider _time;
    private readonly SilenceNotice _notice;
    private readonly NetworkEgress _egress = new();
    private readonly SaidFolders _said;
    private readonly SaidApplication _saidApp = new();
    // Práctica e2e E014: the place this turn's app.open asked for, told in a look at that application (TurnPlace).
    private readonly TurnPlace _turnPlace = new();
    private PendingOperationConfirmation? _pending;
    private PreparedOperation? _proposal;
    private DateTimeOffset _proposalExpiresUtc;
    // A call held in a heartbeat is its proposal; one held in the person's turn (NetworkEgress) asks as a confirmation,
    // and its card says why (_proposalCause).
    private bool _proposalByBeat;
    private string? _proposalCause;
    // Where the waiting call acts beside the folder the person named (SaidFolders), for its result once approved.
    private (string Key, string Note)? _waitingSaid;
    private bool _beat;
    // The person's answer is the person's: it answers only a call whose question was published before their words or
    // their press arrived (ConfirmationAsk.Answers: _askedAt before _personAt, both Stopwatch timestamps;
    // ConfirmationAsk.Unpublished from the hold or the kernel's challenge until the question is published, and a turn
    // or heartbeat that ends without publishing it drops the call), never one asked in the turn that answers nor in a
    // heartbeat (audit 2026-10-15, App 11), nor a heartbeat's proposal asked while their words waited for the turn
    // (audit, round A: they were said before it existed). In a heartbeat every call that waits was asked in it (none
    // waits when it starts), after the person's last moment.
    private long _personAt;
    private long _askedAt;
    private long _turnStarted;
    // The call running now (its step id) and whether a published question waits for its end.
    private string _stepId = string.Empty;
    private long _stepSequence;
    private bool _asking;
    // Auditoría de confirmaciones (2026-10-23): a line of a later turn was published while the call waited, so its
    // question is no longer the last thing BAXY asked. «Vale, no lo cierro. ¿Guardo algo primero?» left app.close waiting,
    // and the «sí» to the new question reached the model with that call as what the person's words answer.
    private bool _leftBehind;
    // The call DropLeftBehind dropped, until the person's next words (TakeWaitingCall) or another line of BAXY's.
    private string? _droppedOperation;
    // Calls the engine never answered (engine_no_answer: they may have run), still unresolved in the registry so the
    // same call made again is the same invocation (UncertainLifetime, and the person's turn after theirs).
    private readonly List<Uncertain> _uncertain = [];
    private long _personTurns;

    private sealed record Uncertain(PreparedOperation Prepared, DateTimeOffset UntilUtc, long Turn);

    internal NativeTurnLoop(Host host, TimeProvider? time = null)
    {
        _host = host ?? throw new ArgumentNullException(nameof(host));
        _time = time ?? TimeProvider.System;
        _notice = new SilenceNotice(_time);
        _said = new SaidFolders(host.PersonFolder);
    }

    /// <summary>A risky call waits for the person's Sí or No (the kernel's challenge or a heartbeat's proposal).</summary>
    internal bool HasPendingConfirmation =>
        (_pending is { } pending && pending.ExpiresAtUtc > _time.GetUtcNow())
        || (_proposal is not null && _proposalExpiresUtc > _time.GetUtcNow());

    /// <summary>
    /// The person's words open a turn; they arrived at <paramref name="arrivedAt"/> (<see cref="Stopwatch.GetTimestamp"/>).
    /// </summary>
    internal async Task RunAsync(string text, long arrivedAt, CancellationToken cancellationToken)
    {
        MindSidecarClient? mind = _host.Mind();
        if (mind is not { IsTurnAvailable: true })
        {
            _host.Fail("mind_unavailable");
            return;
        }

        // Auditoría de la App (2026-10-23): words that answer the waiting call (asked before they arrived) keep the context
        // of the turn that asked it, as a press on Sí or No does: the folders it named. A spoken «sí» replaced them, so
        // the calls after the approved one were ruled by «sí» alone while the button's were ruled by the turn that asked.
        bool answering = WaitingPrepared() is not null && ConfirmationAsk.Answers(_askedAt, arrivedAt);
        _egress.Heard(text);
        if (answering)
        {
            _said.Answered(text);
            _saidApp.Answered(text);
        }
        else
        {
            _said.Heard(text);
            _saidApp.Heard(text);
            _turnPlace.NewTurn();
        }

        await PersonTurnAsync(mind, arrivedAt,
            () => mind.DecideAsync(text, TakeWaitingCall(), cancellationToken), cancellationToken);
    }

    // A turn the person opened (their words, or their Sí/No: either may start a call that takes long) says the mind's
    // notice when it has published nothing SilenceNotice.After after they arrived (the turn may have waited for a
    // heartbeat to end before it started), unless a call waits for the person's Sí or No and this turn asked for it
    // (asked after the turn started: its question comes next), even when it is the same invocation the person said «sí»
    // to and the kernel asks again; a call left waiting before the turn started, by an earlier turn or by a heartbeat it
    // waited for, does not hold it back. A heartbeat says none: nobody asked and nobody waits for it.
    private async Task PersonTurnAsync(
        MindSidecarClient mind,
        long arrivedAt,
        Func<Task<MindStep?>> decide,
        CancellationToken cancellationToken)
    {
        _personAt = arrivedAt;
        long turn = ++_personTurns;
        long started = Stopwatch.GetTimestamp();
        _turnStarted = started;
        _notice.Open(mind.Notice, arrivedAt, () => WaitingPrepared() is null || _askedAt < started, _host.Notice);
        try
        {
            await DriveAsync(mind, await decide(), cancellationToken);
        }
        finally
        {
            _notice.Close();
            DropUnasked();
            DropLeftBehind();
            ResolveUncertain(endedTurn: turn);
        }
    }

    /// <summary>A line BAXY says (not the notice) began to sound: the notice of the turn that published it closes.</summary>
    internal void AnswerSounded() => _notice.Sounded();

    // The call that waits for the person's «sí», as the mind reads it with their next words when it was asked before
    // they arrived: its operation, and its arguments unless it is a memory call (their values stay sealed). When none
    // waits, the call whose question ended unanswered just before these words, with how it ended (auditoría de
    // confirmaciones, 2026-10-23: a «sí» after the time ran out read nothing_pending in the mind, never «expired»,
    // audit 2026-10-15 App 3): its time ran out (it ends «expired» now), or a later line left it behind
    // (DropLeftBehind). Either is told with the person's next words only.
    private JsonObject? TakeWaitingCall()
    {
        string? dropped = _droppedOperation;
        _droppedOperation = null;
        if (WaitingPrepared() is not { } prepared)
        {
            string? expired = _pending?.Prepared.OperationName ?? _proposal?.OperationName;
            if (expired is not null && _askedAt != ConfirmationAsk.Unpublished
                && ConfirmationAsk.Answers(_askedAt, _personAt))
            {
                var ended = new JsonObject { ["operation"] = expired, ["ended"] = "expired" };
                if (_pending?.ReconciliationRequired == true)
                {
                    ended["effectUncertain"] = true;
                }

                DropPending();
                return ended;
            }

            return dropped is null ? null : new JsonObject { ["operation"] = dropped, ["ended"] = "dropped" };
        }

        if (!ConfirmationAsk.Answers(_askedAt, _personAt))
        {
            return null;
        }

        var call = new JsonObject { ["operation"] = prepared.OperationName };
        if (!MemoryOperationProtector.IsMemoryOperation(prepared.OperationName))
        {
            call["arguments"] = PrivateArguments(prepared);
        }

        return call;
    }

    private PreparedOperation? WaitingPrepared() =>
        _pending is { } pending && pending.ExpiresAtUtc > _time.GetUtcNow() ? pending.Prepared
        : _proposal is not null && _proposalExpiresUtc > _time.GetUtcNow() ? _proposal
        : null;

    /// <summary>
    /// The person pressed Sí or No on the pending confirmation; the press arrived at <paramref name="arrivedAt"/>
    /// (<see cref="Stopwatch.GetTimestamp"/>).
    /// </summary>
    internal async Task AnswerConfirmationAsync(
        bool approve,
        string label,
        long arrivedAt,
        CancellationToken cancellationToken)
    {
        MindSidecarClient? mind = _host.Mind();
        if (mind is not { IsTurnAvailable: true })
        {
            _host.Fail("mind_unavailable");
            return;
        }

        _droppedOperation = null;
        await PersonTurnAsync(mind, arrivedAt,
            () => mind.ConfirmAsync(approve, label, cancellationToken), cancellationToken);
    }

    /// <summary>
    /// The heartbeat: the moment goes to the model, which says whether to intervene and, if so, acts, proposes or says
    /// something; what it wrote is published on the channel the person's activity allows. <paramref name="interrupted"/>:
    /// the person's words arrived, and the heartbeat stops before its next call (al máximo, flujos).
    /// </summary>
    internal async Task RunBeatAsync(JsonObject context, CancellationToken cancellationToken,
        CancellationToken interrupted = default)
    {
        MindSidecarClient? mind = _host.Mind();
        if (mind is not { IsTurnAvailable: true })
        {
            return;
        }

        // The caller holds the turn: a confirmation the person's turn left waiting while the moment was gathered is
        // theirs, and a heartbeat's call would drop it (audit 2, H4).
        if (HasPendingConfirmation)
        {
            return;
        }

        _beat = true;
        _said.Clear();
        _saidApp.Clear();
        _turnPlace.NewTurn();
        _turnStarted = Stopwatch.GetTimestamp();
        try
        {
            await DriveAsync(mind, await mind.BeatAsync(context, cancellationToken),
                cancellationToken, interrupted);
        }
        finally
        {
            _beat = false;
            DropUnasked();
            _ = await mind.EndBeatAsync(cancellationToken);
        }
    }

    /// <summary>
    /// A new session: nothing pending survives it. <paramref name="engineRestarted"/>: the same session goes on with the
    /// engine started again (its journal is the same), and a call it never answered keeps its invocation.
    /// </summary>
    internal void Reset(bool engineRestarted = false)
    {
        _leftBehind = false;
        _droppedOperation = null;
        DropPending();
        _egress.Reset();
        _said.Clear();
        _saidApp.Clear();
        _turnPlace.NewTurn();
        if (!engineRestarted)
        {
            ResolveUncertain(endedTurn: null, all: true);
        }
    }

    // Auditoría de la App (2026-10-23; owner: a call run twice is worse than a replay): a call the engine never answered
    // was resolved at once, so the model's retry was a new invocation and ran again, maybe for the second time. It keeps
    // its invocation while the same session goes on, for UncertainLifetime and until the end of the person's turn after
    // the one it timed out in: the same call made again then reaches the kernel as the same invocation, whose journal
    // replays what it did or, with an attempt that may have run, asks the person first (reconciliationRequired: «un
    // intento anterior pudo haber corrido»). After that it is resolved, and the same request later is a new call.
    private void KeepUncertain(PreparedOperation prepared)
    {
        _uncertain.RemoveAll(entry => ReferenceEquals(entry.Prepared, prepared));
        _uncertain.Add(new Uncertain(prepared, _time.GetUtcNow() + UncertainLifetime, _personTurns));
    }

    private void ResolveUncertain(long? endedTurn, bool all = false)
    {
        DateTimeOffset now = _time.GetUtcNow();
        foreach (Uncertain entry in _uncertain.ToArray())
        {
            if (all || entry.UntilUtc <= now || (endedTurn is { } ended && entry.Turn < ended))
            {
                _uncertain.Remove(entry);
                _host.Registry()?.MarkResolved(entry.Prepared);
            }
        }
    }

    private async Task DriveAsync(MindSidecarClient mind, MindStep? step, CancellationToken cancellationToken,
        CancellationToken interrupted = default)
    {
        var closing = new TurnClosing();
        // The mind was told to answer in words (the moves or the time spent, the engine down, a call waiting for the
        // person): a call it still returns does not run. Auditoría de la App (2026-10-23): only the mind's logit bias held
        // the budget, and a call after it ran, each one final again, with no end (engine down: engine_unavailable for
        // ever; a call waiting: dropped by the next).
        bool answerInWords = false;
        for (int calls = 1; ; calls++)
        {
            switch (step)
            {
                case null:
                    // Ronda final 24 (regla 3): a beat nobody asked for leaves no failed turn on the person's screen;
                    // its unreadable decision is only traced.
                    if (_beat)
                    {
                        ShellTraceSink.Record(ShellTraceScopes.Turn, ShellTraceSink.TurnId, "beat.decision_unavailable", "");
                        return;
                    }

                    // Ronda final 29 (regla 3): after a call was made in this turn the code says so (it may have had an
                    // effect), never only that no decision came.
                    _host.Fail(calls > 1 ? "decision_unavailable_after_call" : "decision_unavailable");
                    return;
                case { Kind: "silence" }:
                    return;
                case { Kind: "reply" }:
                    Publish(step.Text, PublicResponseRoute.Conversation);
                    return;
                case { Kind: "question" }:
                    Publish(step.Text, PublicResponseRoute.Clarification);
                    return;
            }

            if (interrupted.IsCancellationRequested)
            {
                // The mind's end of the heartbeat closes the call it chose (EndBeatAsync).
                ShellTraceSink.Record(ShellTraceScopes.Turn, ShellTraceSink.TurnId, "beat.interrupted", "");
                return;
            }

            if (answerInWords)
            {
                ShellTraceSink.Record(ShellTraceScopes.Turn, ShellTraceSink.TurnId, "loop.call_after_final", "");
                if (!_beat)
                {
                    _host.Fail("decision_unavailable_after_call");
                }

                return;
            }

            string observation = await ExecuteAsync(step.Operation!, step.Arguments!, cancellationToken);
            _egress.Observed(step.Operation!, observation);
            // With the engine down no call can run until it restarts after this turn (e2e p3: 13 calls on a dead core),
            // and with a call waiting for the person's yes nothing moves until they answer (e2e p4 E021: the same
            // terminal call eight times, then «no puedo ejecutar comandos»), so the model answers from what it has, as
            // at the call budget. So it does past the turn's time and after a call that came back the same (TurnClosing).
            bool spent = closing.AfterCall(calls, Stopwatch.GetElapsedTime(_turnStarted), step.Operation!,
                step.Arguments!.ToJsonString(), observation);
            bool final = spent || _host.Core() is not { IsReady: true } || HasPendingConfirmation;
            if (WaitingPrepared() is { } waiting)
            {
                observation = Waiting(observation, waiting.OperationName);
            }

            answerInWords = final;
            step = await mind.ContinueAsync(observation, final, _beat, cancellationToken);
        }
    }

    // A line about a call that waits for the person's «sí» is that confirmation (Sí/No buttons), when the model can be
    // asking about it: the turn's own call (ConfirmationAsk; ronda final 30: a call only offered with the person's
    // words is answered by those words, never by buttons under this turn's line).
    // Its question is asked once it is published: from then on the person's words answer it.
    private void Publish(string text, string route) =>
        _notice.Publish(() =>
        {
            if (!ConfirmationAsk.Asks(HasPendingConfirmation, _askedAt, _turnStarted))
            {
                // A call asked in an earlier turn still waits: this line is not its question, and from now on it is no
                // longer what the person's next words or its card answer (dropped when this turn ends).
                _leftBehind |= HasPendingConfirmation;
                _droppedOperation = null;
                _host.Publish(text, route);
                return;
            }

            _host.Publish(text, PublicResponseRoute.Confirmation);
            if (_askedAt == ConfirmationAsk.Unpublished)
            {
                _askedAt = Stopwatch.GetTimestamp();
                if (Waiting() is { } asked)
                {
                    _asking = true;
                    _host.ConfirmationAsked?.Invoke(asked);
                }
            }
        });

    // The waiting call as the view's card shows it: the kernel's challenge or a heartbeat's proposal.
    private NativeTurnConfirmation? Waiting()
    {
        PreparedOperation? prepared = WaitingPrepared();
        if (prepared is null || !ProductCatalog.TryGet(prepared.OperationName, out ProductOperationDescriptor? descriptor)
            || descriptor is null)
        {
            return null;
        }

        bool held = ReferenceEquals(prepared, _proposal);
        return new NativeTurnConfirmation(prepared.OperationName, PrivateArguments(prepared), descriptor.Risk,
            held ? _proposalExpiresUtc : _pending!.ExpiresAtUtc, held && _proposalByBeat,
            EffectStarted: !held && _pending!.ReconciliationRequired, Cause: held ? _proposalCause : null);
    }

    private void Resolved(string outcome)
    {
        if (_asking)
        {
            _asking = false;
            _host.ConfirmationResolved?.Invoke(outcome);
        }
    }

    private async Task<string> ExecuteAsync(string operation, JsonObject arguments, CancellationToken cancellationToken)
    {
        long started = Stopwatch.GetTimestamp();
        _stepId = "c" + Interlocked.Increment(ref _stepSequence).ToString(System.Globalization.CultureInfo.InvariantCulture);
        if (operation == MindStep.ConfirmationAnswer)
        {
            return await AnswerPendingAsync(arguments, started, cancellationToken);
        }

        _host.StepStarted?.Invoke(_stepId, operation,
            MemoryOperationProtector.IsMemoryOperation(operation) ? new JsonObject() : (JsonObject)arguments.DeepClone());

        // Anything else the person asked for replaces a confirmation still waiting: it is dropped, never run later (a
        // heartbeat never starts with one waiting, RunBeatAsync).
        DropPending();
        CoreProcessClient? core = _host.Core();
        if (core is not { IsReady: true })
        {
            return Record(operation, arguments, started, Observation("failed", "engine_unavailable"));
        }

        if (!ProductCatalog.TryGet(operation, out ProductOperationDescriptor? descriptor) || descriptor is null)
        {
            // A name no catalog operation has: what the model put in it is kept out of the trace and the conductor's
            // events, since no schema says what it may carry (a made-up memory call with the person's values).
            return Record(operation, new JsonObject(), started,
                Observation("rejected", "unknown_operation"));
        }

        // The owner switched this kind of call off in Settings (privacy): it does not run, and the model reads why.
        if (_host.Refuse?.Invoke(operation, arguments) is { } refusal)
        {
            return Record(operation, arguments, started, Observation("rejected", refusal));
        }

        // Renew al máximo (w6, rutas): a file call that leaves out the folder the person named in this turn is routed
        // into it when it only reads, or refused before anything runs with the call that names it (SaidFolders).
        (string Key, string Note)? said = null;
        if (_said.Rule(operation, descriptor, arguments) is { } ruling)
        {
            if (ruling.Refusal is { } leftOut)
            {
                return Record(operation, arguments, started, leftOut.ToJsonString(SaidFolders.AsWritten));
            }

            arguments = ruling.Arguments;
            said = ruling.Note is { } note ? ("saidFolder", note) : null;
        }
        // Renew al máximo (w7, apps): an app.open of an application the person did not name, at a place only another
        // one has, opens that one there (SaidApplication).
        else if (_saidApp.Rule(operation, arguments) is { } owner)
        {
            arguments = owner.Arguments;
            said = (SaidApplication.NoteKey, owner.Note);
        }

        ResolveUncertain(endedTurn: null);
        PreparedOperation prepared;
        try
        {
            prepared = MemoryOperationProtector.IsMemoryOperation(operation)
                ? (_host.MemoryProtector() ?? throw new InvalidOperationException("memory_protection_unavailable"))
                    .Prepare(new MemoryRoutedOperation(operation, arguments)).Prepared
                : (_host.Registry() ?? throw new InvalidOperationException("outbox_unavailable"))
                    .GetOrAdd(new RoutedOperation(operation, arguments));
        }
        catch (MemoryValueNeedsSensitiveChannelException)
        {
            // The result says why and what to call: memory.save keeps a value that looks like a secret only as sensitive.
            return Record(operation, arguments, started, Observation("rejected",
                "memory_value_needs_sensitive_channel",
                new JsonObject { ["detail"] = "This value looks like a secret: save it with memory_sensitive_save." }));
        }
        catch (MemoryRequestRefusedException refused)
        {
            // The protector's own reason, by its code and its words; the call's values stay out of the observation.
            return Record(operation, arguments, started, Observation("rejected", refused.Code,
                new JsonObject { ["detail"] = refused.Message }));
        }
        catch (InvalidOperationException unavailable)
            when (unavailable.Message is "outbox_unavailable" or "memory_protection_unavailable")
        {
            // BAXY's own part that was not ready, never the model's arguments (audit 2026-10-15: it read as
            // arguments_invalid and the model blamed its call).
            return Record(operation, arguments, started, Observation("failed", unavailable.Message));
        }
        catch (Exception exception) when (exception is ArgumentException or InvalidOperationException
            or System.IO.InvalidDataException or System.Text.Json.JsonException)
        {
            // Arguments that do not fit the operation are a result the model reads, with what it gave and, by the
            // catalog's schema, which arguments and what each takes (the kernel's code and shape), so it can call again
            // with the right ones; nothing here fills or rewrites them. A memory call's values stay out of it.
            var facts = new JsonObject();
            using (System.Text.Json.JsonDocument given = System.Text.Json.JsonDocument.Parse(arguments.ToJsonString()))
            {
                IReadOnlyList<ArgumentProblem> problems =
                    OperationArgumentValidator.Problems(given.RootElement, descriptor.ArgumentsSchema);
                if (problems.Count > 0)
                {
                    facts["argumentProblems"] = OperationVisibleFacts.ArgumentProblemsJson(problems);
                }
            }

            return Record(operation, arguments, started, Observation("failed",
                "invalid_arguments", WithArguments(facts, "argumentsGiven", operation, arguments)));
        }

        string? egress = _beat ? null : _egress.Holds(operation, arguments);
        if (egress is not null || (_beat && BeatProposes(descriptor, arguments)))
        {
            // Nobody asked (a heartbeat), or what it sends out is not the person's to send unasked (NetworkEgress): the
            // call is held for the person's «sí», untouched, and the model words the question.
            _proposal = prepared;
            _proposalByBeat = _beat;
            _proposalCause = egress;
            _waitingSaid = said;
            _proposalExpiresUtc = _time.GetUtcNow() + ProposalLifetime;
            _askedAt = ConfirmationAsk.Unpublished;
            var held = new JsonObject { ["status"] = "needs_confirmation" };
            if (egress is not null)
            {
                held["cause"] = egress;
            }

            held["next"] = AskThePersonAbout(operation);
            if (egress == "host_not_from_session" && ModelAids.On(ModelAids.ResultHosts)
                && _egress.ResultHosts is { Count: > 0 } resultHosts)
            {
                held["resultHosts"] = new JsonArray([.. resultHosts.Select(static host => (JsonNode)host)]);
                held["next"] += "; " + ResultHostsNext;
            }

            return Record(operation, arguments, started, WithArguments(held, "arguments", operation, arguments)
                .ToJsonString(SaidFolders.AsWritten));
        }

        return await SendAsync(core, prepared, arguments, confirmationToken: null, answered: false, started,
                cancellationToken, said)
            ;
    }

    // Al máximo 5.1: what the call does besides its risk is the catalog's typed fact (OperationEffects), read with the
    // call's exact arguments; it was a list by name here. A window that may be the person's gets nothing unasked (audit
    // 2026-10-15, App H1; owner, 2026-10-16: minimizing one and restoring it are done alone), and nothing the model wrote
    // leaves the PC unasked: in a heartbeat its words come from the moment, which carries the person's memory, window
    // titles and recent lines (owner, 2026-10-15; audit App H3). What an application syncs or publishes by itself is not
    // the person's data leaving through BAXY (owner, 2026-10-16).
    internal static bool Has(string operation, JsonObject arguments, string effect)
    {
        if (!ProductCatalog.TryGet(operation, out ProductOperationDescriptor? descriptor))
        {
            return false;
        }

        using System.Text.Json.JsonDocument given = System.Text.Json.JsonDocument.Parse(arguments.ToJsonString());
        return descriptor.Has(effect, given.RootElement);
    }

    // R10.1 (owner: a heartbeat acts alone only on what is harmless and reversible, and proposes the rest): a call nobody
    // asked for runs only when the catalog says it reads or changes something reversibly (read_only, low_reversible)
    // and, with these arguments, it has none of the catalog's effects: no window of the person's, nothing out of the PC,
    // no radio, network, pairing, airplane or display mode. Privacy_sensitive ran alone (trace nb-beat-none-pC, P026:
    // airplane mode switched on at 8 % battery), and so did a capture, the clipboard's text or the Wi-Fi radio; writing
    // over what the person copied (clipboard.write.text, audit round A) is privacy_sensitive too.
    // The catalog risks the heartbeat never takes alone (borrar, enviar, apagar, instalar, cerrar con trabajo).
    private static readonly HashSet<string> ProposedRisks = new(StringComparer.Ordinal)
    {
        OperationRisks.WorkLoss, OperationRisks.RecoverableDelete, OperationRisks.ExternalCommunication,
        OperationRisks.Installation,
    };

    internal static bool BeatProposes(ProductOperationDescriptor descriptor, JsonObject arguments)
    {
        // Renew al máximo R10.1, measured (2026-10-22): holding every risk above low_reversible also held lowering the
        // brightness at night or on a low battery and reconnecting the home Wi-Fi (practice scenes P007, P027, P024:
        // act 4/7 → 1/7). What a heartbeat never takes alone is what destroys, reaches a person, installs or writes over
        // what the person copied, plus the catalog's effects: a window, the network, and a system change (airplane
        // mode, a radio, the display mode: P026, airplane mode on at 8 % battery).
        if (ProposedRisks.Contains(descriptor.Risk) || descriptor.Name == "clipboard.write.text")
        {
            return true;
        }

        using System.Text.Json.JsonDocument given = System.Text.Json.JsonDocument.Parse(arguments.ToJsonString());
        return descriptor.Effects.Any(effect => effect.Applies(given.RootElement));
    }

    // Where the call acted, beside the folder the person named (SaidFolders) or the application of its place
    // (SaidApplication).
    private static string WithSaid(string observation, string key, string said)
    {
        try
        {
            if (JsonNode.Parse(observation) is JsonObject facts)
            {
                facts[key] = said;
                return facts.ToJsonString(SaidFolders.AsWritten);
            }
        }
        catch (System.Text.Json.JsonException)
        {
        }

        return observation + "\n(" + said + ")";
    }

    // The turn ends on a call that waits for the person's «sí»: the last result says that call has not run, so the
    // answer cannot tell what it would have done (e2e E021: «Python 3.11.2» after a console command that never ran).
    private static string Waiting(string observation, string operation)
    {
        string note = $"{operation.Replace('.', '_')} waits for the person's yes and has not run";
        try
        {
            if (JsonNode.Parse(observation) is JsonObject facts)
            {
                facts["waiting"] = note;
                return facts.ToJsonString(SaidFolders.AsWritten);
            }
        }
        catch (System.Text.Json.JsonException)
        {
        }

        return observation + "\n(" + note + ")";
    }

    // Auditoría de falsedades (F010): «nothing waiting» was read as «already done» («la borré sin pedirte permiso» after
    // a delete that had failed). The mind's own NOTHING_PENDING says this call did nothing (hub/nb-f010); the App's,
    // for a question that ended between the mind's turn and this answer, says the same, and an expired one that the
    // call it asked about was not sent after the question (a challenge whose effect had started says so in its own
    // earlier result, effectStarted).
    internal const string NothingPendingReason = "no action is waiting for the person's confirmation, and this call did "
        + "nothing; whether anything was done is only what the earlier results of this conversation say";
    internal const string ExpiredReason = "the question ran out of time before this answer: this call did nothing, and "
        + "the call it asked about was not sent after the question";

    // What the model reads with a call that waits for the person: who answers and how the answer comes back.
    private const string AskThePerson =
        "ask the person whether to do it; when they answer, call confirm_pending with their answer";

    // The call held for the person's «sí»: nothing ran, and calling it again is not their answer (e2e E021: after «sí»
    // the model called shell_command_run again instead of confirm_pending). Ronda final: «only asks again» was false
    // in the next turn, where the same call runs (DropPending).
    private static string AskThePersonAbout(string operation) =>
        "nothing ran: ask the person whether to do it; their answer goes in confirm_pending (approve true or false); "
        + $"calling {operation.Replace('.', '_')} again is not their answer: it is a new call";

    // Holdout v5 (H5): what a call held for a host no result gave reads besides, with the hosts the results did give.
    private const string ResultHostsNext =
        "the host of this call came from no result of this session, and a page at one of resultHosts is read "
        + "without asking for its host";

    // What BAXY says of a call it held or could not prepare carries the call's arguments, except a memory call's: they
    // stay sealed (the observation reaches the model and, with the conductor, its local events). A memory call that ran
    // is another thing: MemoryObservation opens its result, and the model reads what the person asked to remember (the
    // value saved, what recall and list read, sensitive values redacted), and so do the conductor's events.
    private static JsonObject WithArguments(JsonObject facts, string key, string operation, JsonObject arguments)
    {
        if (!MemoryOperationProtector.IsMemoryOperation(operation))
        {
            facts[key] = arguments.DeepClone();
        }

        return facts;
    }

    private async Task<string> AnswerPendingAsync(JsonObject arguments, long started, CancellationToken cancellationToken)
    {
        if (arguments["approve"] is not JsonValue value || !value.TryGetValue(out bool approve))
        {
            // Ronda final: an answer without a boolean approve is not the person's «no»; the waiting call stays and
            // the model reads what it gave, as with any other call whose arguments do not fit.
            return Record(MindStep.ConfirmationAnswer, arguments, started, Observation("failed", "invalid_arguments",
                new JsonObject { ["argumentsGiven"] = arguments.DeepClone() }));
        }

        if (HasPendingConfirmation && !ConfirmationAsk.Answers(_askedAt, _personAt))
        {
            // Only the person answers, and only a call asked before their words or their press: the waiting call stays
            // as it is until they do.
            return Record(MindStep.ConfirmationAnswer, arguments, started, new JsonObject
            {
                ["status"] = "rejected",
                ["error"] = "only_the_person_answers",
                ["next"] = AskThePerson,
            }.ToJsonString(SaidFolders.AsWritten));
        }

        if (_proposal is { } proposal && _proposalExpiresUtc > _time.GetUtcNow())
        {
            return await AnswerProposalAsync(proposal, approve, started, cancellationToken);
        }

        PendingOperationConfirmation? pending = HasPendingConfirmation ? _pending : null;
        if (pending is null)
        {
            // A call that waited and ran out of time is not «nothing was asked» (audit 2026-10-15, App 3): the model
            // says the question expired and can ask again.
            // A challenge that started before it asked (reconciliationRequired) may have had its effect (auditoría
            // ronda nb propia, 25).
            string? expired = _pending?.Prepared.OperationName ?? _proposal?.OperationName;
            bool effectStarted = _pending?.ReconciliationRequired == true;
            Resolved("expired");
            DropPending();
            return Record(MindStep.ConfirmationAnswer, arguments, started, expired is null
                ? Observation("failed", "nothing_pending", new JsonObject { ["reason"] = NothingPendingReason })
                : Observation("failed", "confirmation_expired", new JsonObject { ["reason"] = ExpiredReason },
                    about: expired, effectUncertain: effectStarted));
        }

        JsonObject pendingArguments = PrivateArguments(pending.Prepared);
        if (approve && RefusedAtApproval(pending.Prepared, pendingArguments, started) is { } refused)
        {
            return refused;
        }

        (string Key, string Note)? said = _waitingSaid;
        Resolved(approve ? "approved" : "declined");
        if (!approve)
        {
            DropPending();
            return Record(pending.Prepared.OperationName, pendingArguments, started,
                Observation("cancelled", "declined_by_person", about: pending.Prepared.OperationName));
        }

        _pending = null;
        CoreProcessClient? core = _host.Core();
        if (core is not { IsReady: true })
        {
            Release(pending.Prepared);
            return Record(pending.Prepared.OperationName, pendingArguments, started,
                Observation("failed", "engine_unavailable", about: pending.Prepared.OperationName));
        }

        return await SendAsync(core, pending.Prepared, pendingArguments, pending.Token, answered: true, started,
            cancellationToken, said);
    }

    // Auditoría de la App (2026-10-23): the owner's switches (Settings) are read when the call is approved too, by voice
    // or by the button: one switched off while the call waited no longer ran it. The call is dropped, and the model
    // reads why, as when it is refused before it is held.
    private string? RefusedAtApproval(PreparedOperation prepared, JsonObject arguments, long started)
    {
        if (_host.Refuse?.Invoke(prepared.OperationName, arguments) is not { } refusal)
        {
            return null;
        }

        DropPending();
        return Record(prepared.OperationName, arguments, started,
            Observation("rejected", refusal, about: prepared.OperationName));
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
        if (approve && RefusedAtApproval(proposal, arguments, started) is { } refused)
        {
            return refused;
        }

        (string Key, string Note)? said = _waitingSaid;
        _proposal = null;
        Resolved(approve ? "approved" : "declined");
        if (!approve)
        {
            Release(proposal);
            return Record(proposal.OperationName, arguments, started,
                Observation("cancelled", "declined_by_person", about: proposal.OperationName));
        }

        CoreProcessClient? core = _host.Core();
        if (core is not { IsReady: true })
        {
            Release(proposal);
            return Record(proposal.OperationName, arguments, started,
                Observation("failed", "engine_unavailable", about: proposal.OperationName));
        }

        string observation = await SendAsync(core, proposal, arguments, confirmationToken: null, answered: true,
            started, cancellationToken, said);
        if (_pending is { } challenge && ReferenceEquals(challenge.Prepared, proposal))
        {
            _pending = null;
            observation = await SendAsync(core, proposal, arguments, challenge.Token, answered: true, started,
                cancellationToken, said);
        }

        return observation;
    }

    // answered: the call a confirm_pending answered, which BAXY's own result names (Observation's about); the model's
    // own call is the one its result answers.
    private async Task<string> SendAsync(
        CoreProcessClient core,
        PreparedOperation prepared,
        JsonObject arguments,
        string? confirmationToken,
        bool answered,
        long started,
        CancellationToken cancellationToken,
        (string Key, string Note)? said = null)
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
            if (memory)
            {
                Resolve(prepared, memory);
            }
            else
            {
                KeepUncertain(prepared);
            }

            return Record(operation, arguments, started,
                Observation("failed", "engine_no_answer", about: answered ? operation : null, effectUncertain: true),
                sent: true);
        }

        if (PendingOperationConfirmation.TryCreate(response, prepared, _time,
                out PendingOperationConfirmation? challenge) && challenge is not null)
        {
            // The kernel asks for the person's «sí» for this exact invocation: the model asks; the answer comes back
            // as confirm_pending, and only then is this same invocation sent again with the token.
            _pending = challenge;
            _waitingSaid = said;
            _askedAt = ConfirmationAsk.Unpublished;
            JsonObject asked = WithArguments(new JsonObject
            {
                ["status"] = "needs_confirmation",
                ["next"] = AskThePersonAbout(operation),
            }, "arguments", operation, arguments);
            asked["effectStarted"] = challenge.ReconciliationRequired;
            if (said is { } told)
            {
                asked[told.Key] = told.Note;
            }

            return Record(operation, arguments, started, asked.ToJsonString(SaidFolders.AsWritten), response,
                sent: challenge.ReconciliationRequired);
        }

        Resolve(prepared, memory);
        _turnPlace.Ran(operation, arguments, response.Status);
        string body = memory
            ? MemoryObservation(prepared, response)
            : OperationResponseProjection.Create(response, operation, _turnPlace.Asked).Message;
        if (said is { } fact)
        {
            body = WithSaid(body, fact.Key, fact.Note);
        }

        if (memory && response.Status == OperationStatuses.Completed
            && operation is not ("memory.recall" or "memory.list" or "memory.status" or "memory.export"))
        {
            _host.MemoryChanged?.Invoke();
            if (operation == "memory.forget" && ForgetsAll(prepared))
            {
                _host.ForgotEverything?.Invoke();
            }
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
                    : Observation("completed", "result_unreadable");
        }
        catch (Exception exception) when (exception is System.IO.InvalidDataException or MemoryRequestRefusedException
            or ProtectedPayloadException)
        {
            return Observation("completed", "result_unreadable");
        }
    }

    // Whether a memory.forget was the whole memory (its sealed arguments' scope).
    private bool ForgetsAll(PreparedOperation prepared)
    {
        if (_host.MemoryProtector() is not { } protector)
        {
            return false;
        }

        try
        {
            using OpenedBoundProtectedJson opened = protector.OpenPrivateArguments(prepared);
            return opened.Payload.ValueKind == System.Text.Json.JsonValueKind.Object
                && opened.Payload.TryGetProperty("scope", out System.Text.Json.JsonElement scope)
                && scope.ValueKind == System.Text.Json.JsonValueKind.String && scope.GetString() == "all";
        }
        catch (Exception exception) when (exception is System.IO.InvalidDataException or MemoryRequestRefusedException
            or ProtectedPayloadException)
        {
            return false;
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

    // A call that ends without the kernel answering for it now (dropped, declined, the engine down): resolved, unless an
    // attempt of it was never answered (KeepUncertain), whose invocation the same call made again still needs.
    private void Release(PreparedOperation prepared)
    {
        if (!MemoryOperationProtector.IsMemoryOperation(prepared.OperationName)
            && !_uncertain.Exists(entry => ReferenceEquals(entry.Prepared, prepared)))
        {
            _host.Registry()?.MarkResolved(prepared);
        }
    }

    private void Resolve(PreparedOperation prepared, bool memory)
    {
        if (!memory)
        {
            _uncertain.RemoveAll(entry => ReferenceEquals(entry.Prepared, prepared));
            _host.Registry()?.MarkResolved(prepared);
        }
    }

    // A call held or challenged in a turn or heartbeat that ended without publishing its question was asked of nobody:
    // it is dropped, never left for words that did not answer it.
    private void DropUnasked()
    {
        if (_askedAt == ConfirmationAsk.Unpublished)
        {
            DropPending();
        }
    }

    // The person's turn published a line after the question of a call that still waits (Publish): the call is dropped,
    // never left for words that answer that line. Saying it again is the model's: it calls the tool again, and the kernel
    // asks again for that exact invocation.
    private void DropLeftBehind()
    {
        if (_leftBehind)
        {
            _leftBehind = false;
            _droppedOperation = (_pending?.Prepared ?? _proposal)?.OperationName;
            DropPending();
        }
    }

    private void DropPending()
    {
        // 2026-10-22, review of the App: a call whose time ran out before the person answered ended «expired», even when
        // what drops it comes later (their next words, a new session); it read as «dropped», another end.
        bool expired = (_pending is not null || _proposal is not null) && WaitingPrepared() is null;
        Resolved(expired ? "expired" : "dropped");
        _waitingSaid = null;
        if (_proposal is { } proposal)
        {
            _proposal = null;
            Release(proposal);
        }

        if (_pending is { } pending)
        {
            _pending = null;
            Release(pending.Prepared);
        }
    }

    private string Record(
        string operation,
        JsonObject arguments,
        long started,
        string observation,
        OperationResponse? response = null,
        bool? sent = null)
    {
        long elapsed = (long)Stopwatch.GetElapsedTime(started).TotalMilliseconds;
        var step = new NativeTurnStep(
            operation,
            MemoryOperationProtector.IsMemoryOperation(operation) ? new JsonObject() : (JsonObject)arguments.DeepClone(),
            response?.Status ?? StatusOf(observation),
            response?.Verified ?? false,
            response?.ErrorCode,
            elapsed,
            observation,
            _stepId,
            // A call reaches its provider when the kernel let it through, whatever its outcome.
            sent ?? response?.Status is OperationStatuses.Completed or OperationStatuses.Failed);
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

    // Every result the App writes itself goes as SaidFolders.AsWritten writes it, accents and «» as they are (auditoría
    // de la App, 2026-10-23: a held call's arguments, which the model reads back, and a waiting result rewritten here
    // reached it as ó escapes, where the provider's own text and the replayed note did not).
    // What BAXY itself says of a call it did not send or whose answer it could not read, with one header: how it ended
    // (status), its code and, only when they hold, that it may have happened and that a completion is unverified
    // (verification none, OperationVisibleFacts' table).
    // The call is the model's own (the result answers its tool_call_id); about names another one, the call a
    // confirm_pending answered.
    private static string Observation(
        string status,
        string error,
        JsonObject? extra = null,
        string? about = null,
        bool effectUncertain = false)
    {
        var facts = new JsonObject { ["status"] = status };
        if (status == OperationStatuses.Completed)
        {
            facts[OperationVisibleFacts.VerificationKey] = OperationVisibleFacts.VerificationNone;
        }

        facts["error"] = error;
        if (effectUncertain)
        {
            facts["effectUncertain"] = true;
        }

        if (about is not null)
        {
            facts["operation"] = about;
        }

        foreach ((string key, JsonNode? value) in extra ?? [])
        {
            facts[key] = value?.DeepClone();
        }

        return facts.ToJsonString(SaidFolders.AsWritten);
    }
}
