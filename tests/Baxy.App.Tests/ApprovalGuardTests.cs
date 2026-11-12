using Baxy.App;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// OVL1: the rule of a button that authorizes an effect, with every time given: it is lit after its whole wait drawn
/// in its place, and it takes a press only if the press was made after it was drawn lit.
/// </summary>
[TestFixture]
public sealed class ApprovalGuardTests
{
    [Test]
    public void APressCountsOnlyIfMadeAfterTheButtonWasDrawnLit()
    {
        var guard = new ApprovalGuard(1000);
        Assert.That(guard.Takes(0), Is.False);
        Assert.That(guard.Light(5000), Is.False, "not drawn in its place yet: no wait is running, however late it is");
        Assert.That(guard.Left(5000), Is.Null);

        guard.Placed(100);
        guard.Placed(700); // drawn again where it was: the wait is the first one's
        Assert.That(guard.Left(400), Is.EqualTo(700));
        Assert.That(guard.Light(1099), Is.False);
        guard.Armed(1099);
        Assert.That(guard.Takes(1099), Is.False, "nothing arms a button that is not lit");

        Assert.That(guard.Light(1100), Is.True);
        Assert.That(guard.IsLit, Is.True);
        Assert.That(guard.Takes(1100), Is.False, "lit, but not drawn so yet");
        guard.Armed(1130);
        guard.Armed(1900);
        Assert.That(guard.Takes(1129), Is.False, "pressed before it was drawn lit, whenever that press is handled");
        Assert.That(guard.Takes(1130), Is.True);
    }

    [Test]
    public void ARestartTurnsItOffUntilAnotherWholeWait()
    {
        var guard = new ApprovalGuard(1000);
        guard.Placed(0);
        Assert.That(guard.Light(1000), Is.True);
        guard.Armed(1000);

        guard.Restart();
        Assert.That(guard.IsLit, Is.False);
        Assert.That(guard.Takes(2000), Is.False);
        Assert.That(guard.Light(2000), Is.False, "the wait before the restart does not count");
        guard.Placed(2000);
        Assert.That(guard.Light(2999), Is.False);
        Assert.That(guard.Light(3000), Is.True);
        guard.Armed(3001);
        Assert.That(guard.Takes(3001), Is.True);
    }

    [TestCase(500u, 1000)]
    [TestCase(200u, 1000)]
    [TestCase(1000u, 1000)]
    [TestCase(5000u, 5000)]
    public void TheWaitIsOneSecondAndNeverLessThanTheDoubleClickTime(uint doubleClick, int wait) =>
        Assert.That(ApprovalGuard.Wait(doubleClick), Is.EqualTo(wait));
}
