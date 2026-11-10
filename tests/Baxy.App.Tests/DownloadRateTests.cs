using NUnit.Framework;

namespace Baxy.App.Tests;

[TestFixture]
public sealed class DownloadRateTests
{
    // REV_APP DL-a (2026-11-09): a file's download only tells the rate when bytes come (PartFetcher's «moved»), so a network
    // that stops sends no sample at all, and the speed and time left of the last sample stayed on the screen until the
    // fetch gave up. The stall is measured against the clock when the figure is read.
    [Test]
    public void ADownloadThatStopsSendingSaysNoSpeedNorTimeLeftWithNoNewSample()
    {
        var at = new DateTimeOffset(2026, 11, 9, 22, 0, 0, TimeSpan.Zero);
        var rate = new DownloadRate(() => at);
        rate.Saw(0);
        at += TimeSpan.FromSeconds(2);
        rate.Saw(20_000_000);
        at += TimeSpan.FromSeconds(4);
        Assert.Multiple(() =>
        {
            Assert.That(rate.BytesPerSecond, Is.EqualTo(10_000_000), "four seconds with nothing is still a download");
            Assert.That(rate.SecondsLeft(100_000_000), Is.EqualTo(8));
        });

        at += TimeSpan.FromSeconds(2);
        Assert.Multiple(() =>
        {
            Assert.That(rate.BytesPerSecond, Is.EqualTo(0), "six seconds with no byte and no sample: stalled");
            Assert.That(rate.SecondsLeft(100_000_000), Is.Null, "with no speed no time is said");
        });

        at += TimeSpan.FromSeconds(1);
        rate.Saw(21_000_000);
        Assert.That(rate.BytesPerSecond, Is.GreaterThan(0), "bytes came again: it has a speed again");
    }
}
