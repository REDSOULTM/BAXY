using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// MissionInputContract measures the text it keeps: the limit is on the trimmed text, so a message within it that a
/// dictation or a paste padded with spaces is not refused as too large.
/// </summary>
[TestFixture]
public sealed class MissionInputTests
{
    [Test]
    public void TheLimitIsOnTheTrimmedText()
    {
        string within = new('a', MissionInputContract.MaximumCharacters);

        string kept = MissionInputContract.ValidateAndTrim(
            new MissionInput("   " + within + "\r\n   ", MissionInputSource.VoiceTranscript));

        Assert.That(kept, Is.EqualTo(within));
    }

    [Test]
    public void ATextOverTheLimitAfterTrimmingIsStillRefused()
    {
        string over = " " + new string('a', MissionInputContract.MaximumCharacters + 1) + " ";

        var refused = Assert.Throws<MissionInputRejectedException>(
            () => MissionInputContract.ValidateAndTrim(new MissionInput(over, MissionInputSource.Text)));

        Assert.That(refused!.Reason, Is.EqualTo(MissionInputRejectionReason.TooLarge));
    }
}
