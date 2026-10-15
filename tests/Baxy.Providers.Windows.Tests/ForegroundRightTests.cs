using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// cu-v3-foco-segunda: the rule of a hand-back of the front, over fake steps. Each try is read back; a try that did
/// not hold bids for the right (the marked press of this thread's hotkey) and sets the front again; the tries are
/// bounded and a hand-back that never held says so.
/// </summary>
[TestFixture]
public sealed class ForegroundRightTests
{
    [Test]
    public void AHandBackThatHoldsAtOnceNeverBids()
    {
        var steps = new List<string>();

        ForegroundRight.Outcome outcome = ForegroundRight.Give(
            () => steps.Add("set"), () => true, () => { steps.Add("bid"); return true; }, () => steps.Add("pause"));

        Assert.Multiple(() =>
        {
            Assert.That(outcome, Is.EqualTo(new ForegroundRight.Outcome(true, 1, 0)));
            Assert.That(steps, Is.EqualTo(new[] { "set" }));
        });
    }

    // Measured live: SetForegroundWindow refused on the second opening of one process; the bid wins the right.
    [Test]
    public void ARefusedHandBackBidsForTheRightAndSetsTheFrontAgain()
    {
        var steps = new List<string>();
        bool won = false;

        ForegroundRight.Outcome outcome = ForegroundRight.Give(
            () => steps.Add("set"), () => won, () => { steps.Add("bid"); won = true; return true; }, () => steps.Add("pause"));

        Assert.Multiple(() =>
        {
            Assert.That(outcome, Is.EqualTo(new ForegroundRight.Outcome(true, 1, 1)));
            Assert.That(steps, Is.EqualTo(new[] { "set", "bid", "set" }));
        });
    }

    // The opened application may still be activating itself: a later try, after a pause, holds.
    [Test]
    public void ATryThatDidNotHoldIsRetriedAfterAPause()
    {
        var steps = new List<string>();
        int reads = 0;

        ForegroundRight.Outcome outcome = ForegroundRight.Give(
            () => steps.Add("set"), () => ++reads >= 3, () => { steps.Add("bid"); return true; }, () => steps.Add("pause"));

        Assert.Multiple(() =>
        {
            Assert.That(outcome, Is.EqualTo(new ForegroundRight.Outcome(true, 2, 1)));
            Assert.That(steps, Is.EqualTo(new[] { "set", "bid", "set", "pause", "set" }));
        });
    }

    // Bounded: an unanswered bid sets nothing more in its try, and after the last try the hand-back says it failed.
    [Test]
    public void AHandBackThatNeverHoldsStopsAfterItsTriesAndSaysSo()
    {
        var steps = new List<string>();

        ForegroundRight.Outcome outcome = ForegroundRight.Give(
            () => steps.Add("set"), () => false, () => { steps.Add("bid"); return false; }, () => steps.Add("pause"),
            attempts: 2);

        Assert.Multiple(() =>
        {
            Assert.That(outcome, Is.EqualTo(new ForegroundRight.Outcome(false, 2, 2)));
            Assert.That(steps, Is.EqualTo(new[] { "set", "bid", "pause", "set", "bid" }));
        });
    }

    // The worker and BAXY's process may each hold a bid hotkey at once: the same unassigned keys, in the same order.
    [Test]
    public void TheBidKeysAreTheWorkersUnassignedKeys()
    {
        DirectoryInfo? directory = new(AppContext.BaseDirectory);
        while (directory is not null && !File.Exists(Path.Combine(directory.FullName, "Baxy.slnx")))
            directory = directory.Parent;
        Assert.That(directory, Is.Not.Null, "Baxy.slnx");
        string worker = File.ReadAllText(Path.Combine(directory!.FullName,
            "src", "Baxy.Providers.Windows", "External", "DesktopUiaWorker.ps1"));
        string keys = string.Join(", ", ForegroundRight.BidKeys.Select(static key => $"0x{key:X2}"));

        Assert.That(worker, Does.Contain("BidKeys = { " + keys + " }"));
    }
}
