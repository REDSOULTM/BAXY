using Baxy.App;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

/// <summary>
/// The heartbeat's reading of the person's absence and return (src/Baxy.App/AwayWatch.cs, linked here: the App has no
/// test project).
/// </summary>
[TestFixture]
public sealed class AwayWatchTests
{
    private static readonly DateTimeOffset Start = new(2026, 10, 16, 18, 0, 0, TimeSpan.Zero);

    [Test]
    public void TheReturnSaysHowLongThePersonWasGoneFromTheirLastInputToTheirFirstBack()
    {
        var watch = new AwayWatch();

        Assert.That(watch.Look(Start, TimeSpan.FromMinutes(3), away: false), Is.Null);
        Assert.That(watch.Look(Start.AddMinutes(9), TimeSpan.FromMinutes(12), away: true), Is.EqualTo("user idle: 12 min"));
        Assert.That(watch.Look(Start.AddMinutes(20), TimeSpan.FromMinutes(23), away: true), Is.Null);
        // Last input at 17:57, first one back at 18:38.
        Assert.That(watch.Look(Start.AddMinutes(39), TimeSpan.FromMinutes(1), away: false),
            Is.EqualTo("volvió tras 41 min ausente"));
        Assert.That(watch.Look(Start.AddMinutes(40), TimeSpan.FromMinutes(1), away: false), Is.Null);
    }

    [Test]
    public void ACallThatStartsWhileThePersonIsAwayIsNoReturn()
    {
        var watch = new AwayWatch();

        Assert.That(watch.Look(Start, TimeSpan.FromMinutes(10), away: true), Is.EqualTo("user idle: 10 min"));
        // The microphone is held now (the moment reads a call, not away), but no input came.
        Assert.That(watch.Look(Start.AddMinutes(5), TimeSpan.FromMinutes(15), away: false), Is.Null);
        Assert.That(watch.Look(Start.AddMinutes(30), TimeSpan.Zero, away: false), Is.EqualTo("volvió tras 40 min ausente"));
    }

    [Test]
    public void IdleTimeWithoutTheMomentReadingThemAwayIsNoAbsence()
    {
        var watch = new AwayWatch();

        // A film at full screen with no input for half an hour: the person is watching, not away.
        Assert.That(watch.Look(Start, TimeSpan.FromMinutes(30), away: false), Is.Null);
        Assert.That(watch.Look(Start.AddMinutes(1), TimeSpan.Zero, away: false), Is.Null);
    }
}
