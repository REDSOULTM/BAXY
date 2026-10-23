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
