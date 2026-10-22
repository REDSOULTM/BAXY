using System.Diagnostics;
using System.Text.Json.Nodes;
using Baxy.Contracts;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.External;
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

/// <summary>A call waiting for the person's Sí or No, as its question is published (the view's card).</summary>
internal sealed record NativeTurnConfirmation(
    string Operation,
    JsonObject Arguments,
    string Risk,
    DateTimeOffset ExpiresUtc,
    bool Proposal);

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
/// The heartbeat (owner, 2026-10-15) runs the same loop in a turn nobody asked for: a call with one of the catalog's
/// risks in <see cref="ProposedRisks"/>, one that sends keys, clicks or commands to a window
/// (<see cref="SendsInputToAWindow"/>), one that sends something out of the PC (<see cref="ReachesTheNetwork"/>), or one
/// that writes over what the person copied (<see cref="ReplacesThePersonsClipboard"/>), is held as a proposal and never reaches the kernel until the person says «sí» to that exact invocation; any other call
/// runs. A heartbeat never starts while a confirmation waits for the person.
/// </para>
/// <para>
/// A turn the person opened that has published nothing <see cref="SilenceNotice.After"/> after their words or press
/// arrived says the mind's notice once (<see cref="SilenceNotice"/>); the model's decisions are untouched by it.
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
    }

    /// <summary>How long a heartbeat's proposal waits for the person's Sí or No.</summary>
    internal static readonly TimeSpan ProposalLifetime = TimeSpan.FromMinutes(10);

    // The catalog risks the heartbeat never takes alone (borrar, enviar, apagar, instalar, cerrar con trabajo).
    private static readonly HashSet<string> ProposedRisks = new(StringComparer.Ordinal)
    {
        "work_loss", "recoverable_delete", "external_communication", "installation",
    };

    private readonly Host _host;
    // 2026-10-22, review of the App: one clock for whether a waiting call is still waiting and how it ended.
    private readonly TimeProvider _time;
    private readonly SilenceNotice _notice;
    private PendingOperationConfirmation? _pending;
    private PreparedOperation? _proposal;
    private DateTimeOffset _proposalExpiresUtc;
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

    internal NativeTurnLoop(Host host, TimeProvider? time = null)
    {
        _host = host ?? throw new ArgumentNullException(nameof(host));
        _time = time ?? TimeProvider.System;
        _notice = new SilenceNotice(_time);
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

        await PersonTurnAsync(mind, arrivedAt, () => mind.DecideAsync(text, WaitingCall(), cancellationToken),
            cancellationToken);
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
        }
    }

    // The call that waits for the person's «sí», as the mind reads it with their next words when it was asked before
    // they arrived: its operation, and its arguments unless it is a memory call (their values stay sealed).
    private JsonObject? WaitingCall()
    {
        if (WaitingPrepared() is not { } prepared || !ConfirmationAsk.Answers(_askedAt, _personAt))
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

        await PersonTurnAsync(mind, arrivedAt, () => mind.ConfirmAsync(approve, label, cancellationToken),
            cancellationToken);
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

        // The caller holds the turn: a confirmation the person's turn left waiting while the moment was gathered is
        // theirs, and a heartbeat's call would drop it (audit 2, H4).
        if (HasPendingConfirmation)
        {
            return;
        }

        _beat = true;
        _turnStarted = Stopwatch.GetTimestamp();
        try
        {
            await DriveAsync(mind, await mind.BeatAsync(context, cancellationToken),
                cancellationToken);
        }
        finally
        {
            _beat = false;
            DropUnasked();
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
        var closing = new TurnClosing();
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

            string observation = await ExecuteAsync(step.Operation!, step.Arguments!, cancellationToken);
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

        bool proposal = ReferenceEquals(prepared, _proposal);
        return new NativeTurnConfirmation(prepared.OperationName, PrivateArguments(prepared), descriptor.Risk,
            proposal ? _proposalExpiresUtc : _pending!.ExpiresAtUtc, proposal);
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

        if (_beat && (ProposedRisks.Contains(descriptor.Risk) || SendsInputToAWindow(operation, arguments)
                || ReachesTheNetwork(operation, arguments) || ReplacesThePersonsClipboard(operation)))
        {
            // Nobody asked: the call is held for the person's «sí», untouched, and the model words the proposal.
            _proposal = prepared;
            _proposalExpiresUtc = _time.GetUtcNow() + ProposalLifetime;
            _askedAt = ConfirmationAsk.Unpublished;
            return Record(operation, arguments, started, WithArguments(new JsonObject
            {
                ["status"] = "needs_confirmation",
                ["next"] = AskThePersonAbout(operation),
            }, "arguments", operation, arguments).ToJsonString());
        }

        return await SendAsync(core, prepared, arguments, confirmationToken: null, answered: false, started,
                cancellationToken)
            ;
    }

    // Every operation whose provider sends keys, clicks, window commands or a script (SendInput, UI Automation's Invoke
    // or SetValue, posted messages, ShowWindow/SetWindowPos, a script run in a page as a user gesture) to a window that
    // may be the person's. The catalog has no typed fact for it yet, so the list is by name: an operation that starts
    // sending input joins it (audit 2026-10-15, App H1: input.keyboard.layout posts WM_INPUTLANGCHANGEREQUEST to the
    // focused window, and window.* move, size, show or focus the person's windows; owner, 2026-10-16: minimizing one and
    // restoring it are done alone). media.control goes to BAXY's own player (mpv, by the pipe BAXY opened for it), then
    // to the system's media controls (SMTC: the owner's channel for a heartbeat, 2026-10-16), then to the YouTube tab of
    // BAXY's browser, which CDP drives by running a script in the page as a user gesture, in a window that holds the
    // person's session: it is held unless its sourceApp names a session other than that tab, which the tab's adapter
    // refuses before any effect (WebBrowserAdapter.ControlYouTubeTabAsync). media.seek.relative has only SMTC.
    // game.launch is held only because it clicks «Jugar» in the dialog Steam opens for the game's address (the data's
    // «confirm», SteamLocalAdapter.LaunchAsync): what Steam publishes by itself (its «playing») is not the person's
    // data leaving through BAXY (owner, 2026-10-16). app.open reuses the window of an application that already runs, and
    // brings it to the front (foreground: ShowWindow and SetForegroundWindow), presses Ctrl+N in it (newDocument) or
    // hands it a place's address, which the application opens in its window and raises (place, ApplicationPlaceOpener);
    // whether one runs is read only as it opens, so without those three it is not held: the window that runs is left as
    // it is, or a new process starts and the front goes back where it was. input.keyboard.open starts osk.exe, which
    // sends nothing to any window and does not take the focus (DesktopKeyPress.ps1): it is not held either. file.open
    // is held always (ronda final 8): with an application named or foreground it raises a window, and without them the
    // default application may be one that already runs and takes the file in the person's window (a single-instance
    // editor), or a packaged app Windows activates by itself. filesystem.file.open.latest opens the same way, and
    // filesystem.folder.open starts or raises an Explorer window in front (ronda final 14): held too. browser.page.read
    // and browser.tabs.list read BAXY's own browser when its session is the one in use, and start it in front when it
    // is not running (ronda final 15): held too.
    // system.settings.set with do_not_disturb opens ms-settings:notifications (it takes the front) and presses its switch
    // by UI Automation's Toggle (WindowsDeviceControlAdapter's DoNotDisturbScript): held; with airplane_mode it goes
    // through the radios API and reaches no window. The setting is a string by then: the catalog's schema checked it.
    private static bool SendsInputToAWindow(string operation, JsonObject arguments) =>
        operation is "input.visible.click" or "input.text.type" or "input.key.press" or "input.pointer.control"
            or "input.select.all" or "input.scroll" or "input.keyboard.layout" or "clipboard.copy" or "clipboard.paste"
            or "message.draft" or "message.send" or "client.channel.locate" or "browser.control" or "calculator.expression.evaluate"
            or "game.launch" or "window.focus" or "window.maximize" or "window.minimize.all" or "window.move"
            or "window.resize" or "window.snap" or "file.open" or "filesystem.file.open.latest" or "filesystem.folder.open"
            or "browser.page.read" or "browser.tabs.list" or "game.store.page" or "game.store.search" or "client.microphone.set" or "clipboard.paste.into" or "office.format.apply"
        || (operation == "app.open" && arguments["foreground"] is JsonValue front && IsTrue(front))
        || (operation == "app.open" && arguments["newDocument"] is JsonValue fresh && IsTrue(fresh))
        || (operation == "app.open" && arguments["place"] is JsonValue place && Named(place))
        || (operation == "system.settings.set" && (string?)arguments["setting"] == "do_not_disturb")
        // Ronda final 25: a look at an application by its name shows its window behind the person's when it is
        // minimized (ShowBehind), and it stays shown: held in a beat, as a window raised unasked.
        || (operation == "input.visible.controls" && arguments["application"] is JsonValue looked && Named(looked))
        || (operation == "media.control" && !(arguments["sourceApp"] is JsonValue source && Named(source)
            && !string.Equals((string?)source, WindowsExternalCapabilityProvider.YouTubeTabMediaSource,
                StringComparison.OrdinalIgnoreCase)));

    // Every operation whose provider sends what the model wrote out of the PC (a query, an address, a host, a place, a
    // title) and whose risk the kernel does not already challenge: in a heartbeat its words come from the moment, which
    // carries the person's memory, window titles and recent lines, and nothing of theirs leaves unasked (owner,
    // 2026-10-15; audit App H3). By name, read from the providers that use HTTP or ping: web.search's sources, web.fetch
    // and web.download, Open-Meteo for the weather and for a place's clock, the Steam store for whether a game is owned,
    // ICMP to the host named, a console command (one that only reads still reaches \\host\share or another computer
    // by name), and a print (the printer may be on the network). What an application syncs or publishes by itself (a
    // memory export in a folder OneDrive syncs) is not the person's data leaving through BAXY (owner, 2026-10-16). The
    // ones with an external_communication or installation risk are held by ProposedRisks already, and app.open with a
    // place (app_places builds spotify:search:{value} and Steam's store search from its value) by SendsInputToAWindow.
    internal static bool ReachesTheNetwork(string operation, JsonObject arguments) =>
        operation is "web.search" or "web.fetch" or "web.download" or "weather.current" or "network.ping"
            or "game.entitlement.named" or "shell.command.run" or "peripheral.print"
        || (operation == "system.time" && arguments["place"] is JsonValue place && Named(place));

    // The clipboard holds what the person copied: writing over it unasked is an effect on their data (audit, round A).
    private static bool ReplacesThePersonsClipboard(string operation) => operation is "clipboard.write.text";

    private static bool Named(JsonValue value) =>
        value.TryGetValue(out string? text) && !string.IsNullOrWhiteSpace(text);

    private static bool IsTrue(JsonValue value) => value.TryGetValue(out bool set) && set;

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
                return facts.ToJsonString();
            }
        }
        catch (System.Text.Json.JsonException)
        {
        }

        return observation + "\n(" + note + ")";
    }

    // What the model reads with a call that waits for the person: who answers and how the answer comes back.
    private const string AskThePerson =
        "ask the person whether to do it; when they answer, call confirm_pending with their answer";

    // The call held for the person's «sí»: nothing ran, and calling it again is not their answer (e2e E021: after «sí»
    // the model called shell_command_run again instead of confirm_pending). Ronda final: «only asks again» was false
    // in the next turn, where the same call runs (DropPending).
    private static string AskThePersonAbout(string operation) =>
        "nothing ran: ask the person whether to do it; their answer goes in confirm_pending (approve true or false); "
        + $"calling {operation.Replace('.', '_')} again is not their answer: it is a new call";

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
            }.ToJsonString());
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
            string? expired = _pending?.Prepared.OperationName ?? _proposal?.OperationName;
            Resolved("expired");
            DropPending();
            return Record(MindStep.ConfirmationAnswer, arguments, started, expired is null
                ? Observation("failed", "nothing_pending")
                : Observation("failed", "confirmation_expired", about: expired));
        }

        JsonObject pendingArguments = PrivateArguments(pending.Prepared);
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
            _host.Registry()?.MarkResolved(pending.Prepared);
            return Record(pending.Prepared.OperationName, pendingArguments, started,
                Observation("failed", "engine_unavailable", about: pending.Prepared.OperationName));
        }

        return await SendAsync(core, pending.Prepared, pendingArguments, pending.Token, answered: true, started,
                cancellationToken)
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
        Resolved(approve ? "approved" : "declined");
        if (!approve)
        {
            Resolve(proposal, MemoryOperationProtector.IsMemoryOperation(proposal.OperationName));
            return Record(proposal.OperationName, arguments, started,
                Observation("cancelled", "declined_by_person", about: proposal.OperationName));
        }

        CoreProcessClient? core = _host.Core();
        if (core is not { IsReady: true })
        {
            Resolve(proposal, MemoryOperationProtector.IsMemoryOperation(proposal.OperationName));
            return Record(proposal.OperationName, arguments, started,
                Observation("failed", "engine_unavailable", about: proposal.OperationName));
        }

        string observation = await SendAsync(core, proposal, arguments, confirmationToken: null, answered: true,
            started, cancellationToken);
        if (_pending is { } challenge && ReferenceEquals(challenge.Prepared, proposal))
        {
            _pending = null;
            observation = await SendAsync(core, proposal, arguments, challenge.Token, answered: true, started,
                    cancellationToken)
                ;
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
                Observation("failed", "engine_no_answer", about: answered ? operation : null, effectUncertain: true),
                sent: true);
        }

        if (PendingOperationConfirmation.TryCreate(response, prepared, _time,
                out PendingOperationConfirmation? challenge) && challenge is not null)
        {
            // The kernel asks for the person's «sí» for this exact invocation: the model asks; the answer comes back
            // as confirm_pending, and only then is this same invocation sent again with the token.
            _pending = challenge;
            _askedAt = ConfirmationAsk.Unpublished;
            JsonObject asked = WithArguments(new JsonObject
            {
                ["status"] = "needs_confirmation",
                ["next"] = AskThePersonAbout(operation),
            }, "arguments", operation, arguments);
            asked["effectStarted"] = challenge.ReconciliationRequired;
            return Record(operation, arguments, started, asked.ToJsonString(), response, sent: challenge.ReconciliationRequired);
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
                    : Observation("completed", "result_unreadable");
        }
        catch (Exception exception) when (exception is System.IO.InvalidDataException or MemoryRequestRefusedException
            or ProtectedPayloadException)
        {
            return Observation("completed", "result_unreadable");
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

    // A call held or challenged in a turn or heartbeat that ended without publishing its question was asked of nobody:
    // it is dropped, never left for words that did not answer it.
    private void DropUnasked()
    {
        if (_askedAt == ConfirmationAsk.Unpublished)
        {
            DropPending();
        }
    }

    private void DropPending()
    {
        // 2026-10-22, review of the App: a call whose time ran out before the person answered ended «expired», even when
        // what drops it comes later (their next words, a new session); it read as «dropped», another end.
        bool expired = (_pending is not null || _proposal is not null) && WaitingPrepared() is null;
        Resolved(expired ? "expired" : "dropped");
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

    // What BAXY itself says of a call it did not send or whose answer it could not read, with one header: how it ended
    // (status), its code and, only when they hold, that it may have happened and that a completion is unverified.
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
            facts["verified"] = false;
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

        return facts.ToJsonString();
    }
}
