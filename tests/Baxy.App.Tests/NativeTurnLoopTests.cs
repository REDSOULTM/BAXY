using System.Diagnostics;
using System.Reflection;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>The native turn loop's waiting calls (src/Baxy.App/NativeTurnLoop.cs).</summary>
[TestFixture]
public sealed class NativeTurnLoopTests
{
    [Test]
    public void AProposalThatRanOutOfTimeEndsExpiredNotDropped()
    {
        var clock = new ManualClock();
        var outcomes = new List<string>();
        NativeTurnLoop loop = Loop(outcomes, clock);
        WaitingCalls.HoldAskedProposal(loop, clock.GetUtcNow() + NativeTurnLoop.ProposalLifetime);
        Assert.That(loop.HasPendingConfirmation, Is.True);

        clock.Now += NativeTurnLoop.ProposalLifetime + TimeSpan.FromSeconds(1);
        Assert.That(loop.HasPendingConfirmation, Is.False);
        loop.Reset();

        Assert.That(outcomes, Is.EqualTo(new[] { "expired" }));
    }

    [Test]
    public void AProposalStillWaitingThatIsLeftEndsDropped()
    {
        var clock = new ManualClock();
        var outcomes = new List<string>();
        NativeTurnLoop loop = Loop(outcomes, clock);
        WaitingCalls.HoldAskedProposal(loop, clock.GetUtcNow() + NativeTurnLoop.ProposalLifetime);

        clock.Now += NativeTurnLoop.ProposalLifetime - TimeSpan.FromSeconds(1);
        loop.Reset();

        Assert.That(outcomes, Is.EqualTo(new[] { "dropped" }));
        Assert.That(loop.HasPendingConfirmation, Is.False);
    }

    // BAXY Renew al máximo 11.5: the person's turn holds a fetch of a host nobody gave, and asks it as a confirmation
    // (not as a heartbeat's proposal); the call never reaches the engine.
    [Test]
    public async Task AFetchOfAHostNobodyGaveWaitsForThePersonsYes()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["reply"] = new JsonObject
            {
                ["turn.decide"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "action",
                    ["operation"] = "web.fetch",
                    ["arguments"] = new JsonObject { ["url"] = "https://exfil.example/c" },
                },
                ["turn.continue"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "clarify",
                    ["question"] = "¿Abro esa página?",
                },
            },
        });
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        CoreProcessClient core = ReadyCore();
        var steps = new List<NativeTurnStep>();
        var asked = new List<NativeTurnConfirmation>();
        var registry = new RetryableOperationRegistry();
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = () => registry,
            MemoryProtector = static () => null,
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            StepCompleted = steps.Add,
            ConfirmationAsked = asked.Add,
        });

        await loop.RunAsync("lee la página", Stopwatch.GetTimestamp(), CancellationToken.None);

        Assert.That(steps.Select(static step => (step.Operation, step.Status, step.Sent)),
            Is.EqualTo(new[] { ("web.fetch", "needs_confirmation", false) }));
        Assert.That((string?)JsonNode.Parse(steps[0].Observation)?["cause"], Is.EqualTo("host_not_from_session"));
        Assert.That(asked.Select(static call => (call.Operation, call.Proposal, call.Cause)),
            Is.EqualTo(new[] { ("web.fetch", false, (string?)"host_not_from_session") }));
        Assert.That(loop.HasPendingConfirmation, Is.True);
    }

    // Auditoría de falsedades (F010): an answer with nothing waiting says this call did nothing, never only the bare
    // «nothing_pending» that the 4B read as «ya está hecho».
    [Test]
    public async Task AnAnswerWithNothingWaitingSaysThisCallDidNothing()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["reply"] = new JsonObject
            {
                ["turn.decide"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "action",
                    ["operation"] = "confirmation.answer",
                    ["arguments"] = new JsonObject { ["approve"] = true },
                },
                ["turn.continue"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "clarify",
                    ["question"] = "¿Qué quieres que haga?",
                },
            },
        });
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        var steps = new List<NativeTurnStep>();
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = static () => null,
            Mind = () => mind,
            Registry = static () => null,
            MemoryProtector = static () => null,
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            StepCompleted = steps.Add,
        });

        await loop.RunAsync("sí", Stopwatch.GetTimestamp(), CancellationToken.None);

        JsonNode? observed = JsonNode.Parse(steps.Single().Observation);
        Assert.Multiple(() =>
        {
            Assert.That((string?)observed?["error"], Is.EqualTo("nothing_pending"));
            Assert.That((string?)observed?["reason"], Is.EqualTo(NativeTurnLoop.NothingPendingReason));
            Assert.That((string?)observed?["reason"], Does.Contain("this call did nothing"));
        });
    }

    // Auditoría de la App (2026-10-23): what the App writes itself reached the model as \u escapes («Pokémon»),
    // the held call's arguments included; the provider's text and SaidFolders' already went as written.
    [Test]
    public async Task AHeldCallReachesTheModelAsItWasWritten()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["reply"] = new JsonObject
            {
                ["turn.decide"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "action",
                    ["operation"] = "game.launch",
                    ["arguments"] = new JsonObject { ["appId"] = "1", ["title"] = "Pokémon «Rojo»" },
                },
                ["turn.continue"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "clarify",
                    ["question"] = "¿Abro ese juego?",
                },
            },
        });
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        CoreProcessClient core = ReadyCore();
        var registry = new RetryableOperationRegistry();
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = () => registry,
            MemoryProtector = static () => null,
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
        });

        await loop.RunAsync("abre un juego", Stopwatch.GetTimestamp(), CancellationToken.None);

        string observation = (string)fake.Requests("turn.continue").Single()["observation"]!;
        Assert.Multiple(() =>
        {
            Assert.That(observation, Does.Contain("\"title\":\"Pokémon «Rojo»\""));
            Assert.That(observation, Does.Not.Contain("\\u"));
            Assert.That((string?)JsonNode.Parse(observation)?["cause"], Is.EqualTo("game_title_not_said"));
        });
    }

    // Auditoría de la App (2026-10-23): the owner's switches are read again when the call is approved; one switched off
    // while it waited does not run it, by the button as by voice.
    [TestCase(true)]
    [TestCase(false)]
    public async Task AnApprovalAfterTheOwnerSwitchedTheCallOffDoesNotRunIt(bool button)
    {
        using var fake = new FakeMind();
        fake.Script(HeldFetch());
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        CoreProcessClient core = ReadyCore();
        var registry = new RetryableOperationRegistry();
        var steps = new List<NativeTurnStep>();
        var outcomes = new List<string>();
        string? switchedOff = null;
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = () => registry,
            MemoryProtector = static () => null,
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            StepCompleted = steps.Add,
            ConfirmationResolved = outcomes.Add,
            Refuse = (operation, _) => operation == "web.fetch" ? switchedOff : null,
        });
        await loop.RunAsync("lee la página", Stopwatch.GetTimestamp(), CancellationToken.None);
        Assert.That(loop.HasPendingConfirmation, Is.True);

        switchedOff = "web_disabled_by_owner";
        var approval = new JsonObject
        {
            ["type"] = "turn.result",
            ["kind"] = "action",
            ["operation"] = "confirmation.answer",
            ["arguments"] = new JsonObject { ["approve"] = true },
        };
        fake.Script(new JsonObject
        {
            ["reply"] = new JsonObject
            {
                [button ? "turn.confirm" : "turn.decide"] = approval,
                ["turn.continue"] = new JsonObject
                {
                    ["type"] = "turn.result", ["kind"] = "conversation", ["reply"] = "La búsqueda web está apagada.",
                },
            },
        });
        if (button)
        {
            await loop.AnswerConfirmationAsync(true, "Sí", Stopwatch.GetTimestamp(), CancellationToken.None);
        }
        else
        {
            await loop.RunAsync("sí", Stopwatch.GetTimestamp(), CancellationToken.None);
        }

        NativeTurnStep last = steps[^1];
        Assert.Multiple(() =>
        {
            Assert.That((last.Operation, last.Status, last.Sent), Is.EqualTo(("web.fetch", "rejected", false)));
            Assert.That((string?)JsonNode.Parse(last.Observation)?["error"], Is.EqualTo("web_disabled_by_owner"));
            Assert.That(loop.HasPendingConfirmation, Is.False);
            Assert.That(outcomes, Is.EqualTo(new[] { "dropped" }));
        });
    }

    // Auditoría de la App (2026-10-23; owner: a call run twice is worse than a replay): a call the engine never
    // answered keeps its invocation through the person's next turn and UncertainLifetime, so the same call made again
    // is the same invocation for the kernel's journal; after that, the same request is a new call.
    [Test]
    public async Task ACallTheEngineNeverAnsweredKeepsItsInvocationForAnIdenticalRetryWithinItsWindow()
    {
        using var fake = new FakeMind();
        fake.Script(CallsThenSays("system.time", new JsonObject()));
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        var clock = new ManualClock();
        var registry = new RetryableOperationRegistry();
        var steps = new List<NativeTurnStep>();
        NativeTurnLoop loop = UncertainLoop(mind, registry, steps, clock);

        await loop.RunAsync("¿qué hora es?", Stopwatch.GetTimestamp(), CancellationToken.None);
        Assert.That((string?)JsonNode.Parse(steps[^1].Observation)?["error"], Is.EqualTo("engine_no_answer"));
        PreparedOperation first = Unresolved(registry).Single();

        // The retry in the next turn: the same invocation, whose window starts again with this attempt.
        await loop.RunAsync("inténtalo de nuevo", Stopwatch.GetTimestamp(), CancellationToken.None);
        Assert.That(Unresolved(registry), Is.EqualTo(new[] { first }));

        // A different call is its own invocation.
        Assert.That(registry.GetOrAdd(new RoutedOperation("system.time", new JsonObject { ["place"] = "Lima" })),
            Is.Not.SameAs(first));

        // The person's turn after it ends with no call: the window closes, and the same request is a new call.
        fake.Script(Says("Listo."));
        await loop.RunAsync("gracias", Stopwatch.GetTimestamp(), CancellationToken.None);
        Assert.That(Unresolved(registry).Where(p => p.OperationName == "system.time" && !p.Arguments.TryGetProperty("place", out _)),
            Is.Empty);
        Assert.That(registry.GetOrAdd(new RoutedOperation("system.time", new JsonObject())).InvocationId,
            Is.Not.EqualTo(first.InvocationId));
    }

    [Test]
    public async Task ACallTheEngineNeverAnsweredIsANewCallAfterItsTimeOrInANewSession()
    {
        using var fake = new FakeMind();
        fake.Script(CallsThenSays("system.time", new JsonObject()));
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        var clock = new ManualClock();
        var registry = new RetryableOperationRegistry();
        var steps = new List<NativeTurnStep>();
        NativeTurnLoop loop = UncertainLoop(mind, registry, steps, clock);

        await loop.RunAsync("¿qué hora es?", Stopwatch.GetTimestamp(), CancellationToken.None);
        PreparedOperation first = Unresolved(registry).Single();
        clock.Now += NativeTurnLoop.UncertainLifetime + TimeSpan.FromSeconds(1);
        await loop.RunAsync("¿y ahora?", Stopwatch.GetTimestamp(), CancellationToken.None);
        PreparedOperation second = Unresolved(registry).Single();
        Assert.That(second.InvocationId, Is.Not.EqualTo(first.InvocationId));

        // The engine started again is the same session; a new one is not.
        loop.Reset(engineRestarted: true);
        Assert.That(Unresolved(registry), Is.EqualTo(new[] { second }));
        loop.Reset();
        Assert.That(Unresolved(registry), Is.Empty);
    }

    private static JsonObject CallsThenSays(string operation, JsonObject arguments) => new()
    {
        ["reply"] = new JsonObject
        {
            ["turn.decide"] = new JsonObject
            {
                ["type"] = "turn.result", ["kind"] = "action", ["operation"] = operation, ["arguments"] = arguments,
            },
            ["turn.continue"] = new JsonObject
            {
                ["type"] = "turn.result", ["kind"] = "conversation", ["reply"] = "El motor no respondió.",
            },
        },
    };

    // An engine said ready whose every call fails in transport (ReadyCore): engine_no_answer.
    private static NativeTurnLoop UncertainLoop(MindSidecarClient mind, RetryableOperationRegistry registry,
        List<NativeTurnStep> steps, TimeProvider clock)
    {
        CoreProcessClient core = ReadyCore();
        return new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = () => registry,
            MemoryProtector = static () => null,
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            StepCompleted = steps.Add,
        }, clock);
    }

    private static PreparedOperation[] Unresolved(RetryableOperationRegistry registry) =>
        [.. ((Dictionary<string, PreparedOperation>)typeof(RetryableOperationRegistry)
            .GetField("_operations", BindingFlags.Instance | BindingFlags.NonPublic)!.GetValue(registry)!).Values];

    // Auditoría de la App (2026-10-23): told to answer in words (here, the engine is down), a mind that still calls does
    // not get that call run; before, each call ran, came back final again, and the turn never ended.
    [Test]
    public async Task ACallAfterTheMindWasToldToAnswerInWordsDoesNotRun()
    {
        using var fake = new FakeMind();
        var call = new JsonObject
        {
            ["type"] = "turn.result",
            ["kind"] = "action",
            ["operation"] = "system.time",
            ["arguments"] = new JsonObject(),
        };
        fake.Script(new JsonObject
        {
            ["reply"] = new JsonObject { ["turn.decide"] = call, ["turn.continue"] = call.DeepClone() },
        });
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        var steps = new List<NativeTurnStep>();
        var failures = new List<string>();
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = static () => null,
            Mind = () => mind,
            Registry = static () => null,
            MemoryProtector = static () => null,
            Publish = static (_, _) => { },
            Fail = failures.Add,
            Notice = static _ => { },
            StepCompleted = steps.Add,
        });

        await loop.RunAsync("¿qué hora es?", Stopwatch.GetTimestamp(), CancellationToken.None)
            .WaitAsync(TimeSpan.FromSeconds(30));

        Assert.Multiple(() =>
        {
            Assert.That(steps.Select(static step => step.Operation), Is.EqualTo(new[] { "system.time" }));
            Assert.That(failures, Is.EqualTo(new[] { "decision_unavailable_after_call" }));
            Assert.That(fake.Requests("turn.continue").Select(static request => (bool?)request["final"]),
                Is.EqualTo(new bool?[] { true }));
        });
    }

    // Auditoría de confirmaciones (2026-10-23): the person's words answer only BAXY's last question. The words right
    // after it still reach the model with the waiting call; a line BAXY publishes in that later turn leaves the question
    // behind, so the call is dropped then and the «sí» to that line is no answer to it.
    [Test]
    public async Task ALineOfALaterTurnLeavesTheQuestionBehindAndDropsTheCall()
    {
        using var fake = new FakeMind();
        fake.Script(HeldFetch());
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        var published = new List<(string Text, string Route)>();
        var outcomes = new List<string>();
        NativeTurnLoop loop = PersonLoop(mind, published, outcomes);

        await loop.RunAsync("lee la página", Stopwatch.GetTimestamp(), CancellationToken.None);
        Assert.That(loop.HasPendingConfirmation, Is.True);
        Assert.That(published[^1].Route, Is.EqualTo(PublicResponseRoute.Confirmation));

        fake.Script(Says("Son las tres. ¿Te pongo una alarma?"));
        await loop.RunAsync("¿qué hora es?", Stopwatch.GetTimestamp(), CancellationToken.None);
        Assert.That((string?)fake.Requests("turn.decide")[1]["pendingConfirmation"]?["operation"], Is.EqualTo("web.fetch"));
        Assert.That(published[^1].Route, Is.EqualTo(PublicResponseRoute.Conversation));
        Assert.That(loop.HasPendingConfirmation, Is.False);
        Assert.That(outcomes, Is.EqualTo(new[] { "dropped" }));

        // The «sí» that follows reads which call was left behind, never that it waits; the words after it, nothing.
        fake.Script(Says("¿A qué hora?"));
        await loop.RunAsync("sí", Stopwatch.GetTimestamp(), CancellationToken.None);
        Assert.That(fake.Requests("turn.decide")[2]["pendingConfirmation"]?.ToJsonString(),
            Is.EqualTo("""{"operation":"web.fetch","ended":"dropped"}"""));
        await loop.RunAsync("a las siete", Stopwatch.GetTimestamp(), CancellationToken.None);
        Assert.That(fake.Requests("turn.decide")[3]["pendingConfirmation"], Is.Null);
        Assert.That(fake.Seen, Has.No.Member("turn.confirm"));
        Assert.That(outcomes, Is.EqualTo(new[] { "dropped" }));
    }

    // Auditoría de confirmaciones (2026-10-23): a «sí» after the time to answer ran out reads that it expired (audit
    // 2026-10-15, App 3), not that nothing was asked; the call ends «expired» then, and the next words read nothing.
    [Test]
    public async Task ASiAfterTheTimeRanOutReadsThatTheQuestionExpired()
    {
        using var fake = new FakeMind();
        fake.Script(HeldFetch());
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        var published = new List<(string Text, string Route)>();
        var outcomes = new List<string>();
        var clock = new ManualClock();
        NativeTurnLoop loop = PersonLoop(mind, published, outcomes, clock);
        await loop.RunAsync("lee la página", Stopwatch.GetTimestamp(), CancellationToken.None);
        Assert.That(loop.HasPendingConfirmation, Is.True);

        clock.Now += NativeTurnLoop.ProposalLifetime + TimeSpan.FromSeconds(1);
        fake.Script(Says("Esa pregunta venció. ¿Abro la página?"));
        await loop.RunAsync("sí", Stopwatch.GetTimestamp(), CancellationToken.None);
        Assert.That(fake.Requests("turn.decide")[1]["pendingConfirmation"]?.ToJsonString(),
            Is.EqualTo("""{"operation":"web.fetch","ended":"expired"}"""));
        Assert.That(outcomes, Is.EqualTo(new[] { "expired" }));

        await loop.RunAsync("sí", Stopwatch.GetTimestamp(), CancellationToken.None);
        Assert.That(fake.Requests("turn.decide")[2]["pendingConfirmation"], Is.Null);
    }

    // The words right after the question that publish nothing (the turn failed) leave it waiting.
    [Test]
    public async Task ATurnThatPublishesNothingLeavesTheQuestionWaiting()
    {
        using var fake = new FakeMind();
        fake.Script(HeldFetch());
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        var published = new List<(string Text, string Route)>();
        var outcomes = new List<string>();
        NativeTurnLoop loop = PersonLoop(mind, published, outcomes);
        await loop.RunAsync("lee la página", Stopwatch.GetTimestamp(), CancellationToken.None);

        fake.Script(new JsonObject { ["fail"] = new JsonArray("turn.decide") });
        await loop.RunAsync("eh", Stopwatch.GetTimestamp(), CancellationToken.None);

        Assert.That(loop.HasPendingConfirmation, Is.True);
        Assert.That(outcomes, Is.Empty);
    }

    // The person's turn holds a fetch of a host nobody gave and asks it (BAXY Renew al máximo 11.5).
    private static JsonObject HeldFetch() => new()
    {
        ["reply"] = new JsonObject
        {
            ["turn.decide"] = new JsonObject
            {
                ["type"] = "turn.result",
                ["kind"] = "action",
                ["operation"] = "web.fetch",
                ["arguments"] = new JsonObject { ["url"] = "https://exfil.example/c" },
            },
            ["turn.continue"] = new JsonObject
            {
                ["type"] = "turn.result",
                ["kind"] = "conversation",
                ["reply"] = "¿Abro esa página?",
            },
        },
    };

    private static JsonObject Says(string reply) => new()
    {
        ["reply"] = new JsonObject
        {
            ["turn.decide"] = new JsonObject { ["type"] = "turn.result", ["kind"] = "conversation", ["reply"] = reply },
        },
    };

    private static NativeTurnLoop PersonLoop(MindSidecarClient mind, List<(string Text, string Route)> published,
        List<string> outcomes, TimeProvider? clock = null)
    {
        CoreProcessClient core = ReadyCore();
        var registry = new RetryableOperationRegistry();
        return new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = () => registry,
            MemoryProtector = static () => null,
            Publish = (text, route) => published.Add((text, route)),
            Fail = static _ => { },
            Notice = static _ => { },
            ConfirmationResolved = outcomes.Add,
        }, clock);
    }

    // The kernel asks again for a call whose earlier attempt may have happened (reconciliationRequired): its card says so.
    [TestCase(true)]
    [TestCase(false)]
    public void AChallengeAfterAnAttemptThatMayHaveRunIsAskedAsSuch(bool reconciliationRequired)
    {
        const BindingFlags Private = BindingFlags.Instance | BindingFlags.NonPublic;
        var clock = new ManualClock();
        NativeTurnLoop loop = Loop([], clock);
        PreparedOperation prepared = new RetryableOperationRegistry().GetOrAdd(
            new RoutedOperation("system.recyclebin.empty", new JsonObject()));
        object pending = typeof(PendingOperationConfirmation)
            .GetConstructor(Private, [typeof(PreparedOperation), typeof(string), typeof(DateTimeOffset), typeof(bool)])!
            .Invoke([prepared, "token", clock.GetUtcNow().AddMinutes(2), reconciliationRequired]);
        typeof(NativeTurnLoop).GetField("_pending", Private)!.SetValue(loop, pending);

        var asked = (NativeTurnConfirmation?)typeof(NativeTurnLoop).GetMethod("Waiting", Private)!.Invoke(loop, null);

        Assert.That(asked?.EffectStarted, Is.EqualTo(reconciliationRequired));
    }

    // An engine that says it is ready and is never sent anything: a held call stops before it.
    private static CoreProcessClient ReadyCore()
    {
        var core = new CoreProcessClient();
        const BindingFlags Private = BindingFlags.Instance | BindingFlags.NonPublic;
        typeof(CoreProcessClient).GetField("_ready", Private)!.SetValue(core, true);
        typeof(CoreProcessClient).GetField("_process", Private)!.SetValue(core, Process.GetCurrentProcess());
        return core;
    }

    private static NativeTurnLoop Loop(List<string> outcomes, TimeProvider clock) => new(new NativeTurnLoop.Host
    {
        Core = static () => null,
        Mind = static () => null,
        Registry = static () => null,
        MemoryProtector = static () => null,
        Publish = static (_, _) => { },
        Fail = static _ => { },
        Notice = static _ => { },
        ConfirmationResolved = outcomes.Add,
    }, clock);

    private sealed class ManualClock : TimeProvider
    {
        internal DateTimeOffset Now { get; set; } = new(2026, 10, 22, 10, 0, 0, TimeSpan.Zero);

        public override DateTimeOffset GetUtcNow() => Now;
    }
}
