using System.Diagnostics;
using System.Reflection;
using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>The native turn loop's waiting calls (src/Baxy.App/NativeTurnLoop.cs).</summary>
[TestFixture]
public sealed class NativeTurnLoopTests
{
    private const BindingFlags Private = BindingFlags.Instance | BindingFlags.NonPublic;

    [Test]
    public void AProposalThatRanOutOfTimeEndsExpiredNotDropped()
    {
        var clock = new ManualClock();
        var outcomes = new List<string>();
        NativeTurnLoop loop = Loop(outcomes, clock);
        HoldAskedProposal(loop, clock.GetUtcNow() + NativeTurnLoop.ProposalLifetime);
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
        HoldAskedProposal(loop, clock.GetUtcNow() + NativeTurnLoop.ProposalLifetime);

        clock.Now += NativeTurnLoop.ProposalLifetime - TimeSpan.FromSeconds(1);
        loop.Reset();

        Assert.That(outcomes, Is.EqualTo(new[] { "dropped" }));
        Assert.That(loop.HasPendingConfirmation, Is.False);
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

    // A heartbeat's proposal whose question was published (its card shows), as NativeTurnLoop leaves it.
    private static void HoldAskedProposal(NativeTurnLoop loop, DateTimeOffset expiresUtc)
    {
        PreparedOperation proposal = new RetryableOperationRegistry().GetOrAdd(
            new RoutedOperation("web.search", new JsonObject { ["query"] = "clima de mañana" }));
        typeof(NativeTurnLoop).GetField("_proposal", Private)!.SetValue(loop, proposal);
        typeof(NativeTurnLoop).GetField("_proposalExpiresUtc", Private)!.SetValue(loop, expiresUtc);
        typeof(NativeTurnLoop).GetField("_askedAt", Private)!.SetValue(loop, Stopwatch.GetTimestamp());
        typeof(NativeTurnLoop).GetField("_asking", Private)!.SetValue(loop, true);
    }

    private sealed class ManualClock : TimeProvider
    {
        internal DateTimeOffset Now { get; set; } = new(2026, 10, 22, 10, 0, 0, TimeSpan.Zero);

        public override DateTimeOffset GetUtcNow() => Now;
    }
}
