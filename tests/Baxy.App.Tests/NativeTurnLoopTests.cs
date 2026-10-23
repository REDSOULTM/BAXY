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
        Assert.That(asked.Select(static call => (call.Operation, call.Proposal)),
            Is.EqualTo(new[] { ("web.fetch", false) }));
        Assert.That(loop.HasPendingConfirmation, Is.True);
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

        fake.Script(Says("¿A qué hora?"));
        await loop.RunAsync("sí", Stopwatch.GetTimestamp(), CancellationToken.None);
        Assert.That(fake.Requests("turn.decide")[2]["pendingConfirmation"], Is.Null);
        Assert.That(fake.Seen, Has.No.Member("turn.confirm"));
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
