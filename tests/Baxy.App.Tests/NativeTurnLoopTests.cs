using Baxy.App;
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
