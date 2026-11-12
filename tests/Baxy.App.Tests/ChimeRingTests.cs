using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// APP2 (REV10 S1, confirmed in REV11): a chime played while an alarm rings cut its tone. PlaySound without SND_NOSTOP
/// «attempts to stop any sound that is currently playing in the same process» (winmm, PlaySound); the ringer believed
/// the tone went on and only put it back up to 10 s later. A chime yields to what already sounds: it plays only when
/// nothing does.
/// </summary>
[TestFixture]
public sealed class ChimeRingTests
{
    private const uint NoStop = 0x10;

    [Test]
    public void AChimeYieldsToTheToneThatAlreadyRings() =>
        Assert.That(Chime.Flags & NoStop, Is.EqualTo(NoStop));
}
