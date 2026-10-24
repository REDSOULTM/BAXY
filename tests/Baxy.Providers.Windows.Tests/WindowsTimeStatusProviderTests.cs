using Baxy.Providers.Windows.SystemStatus;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
public sealed class WindowsTimeStatusProviderTests
{
    [Test]
    public async Task ReadRequiresAConsistentSecondClockObservation()
    {
        DateTimeOffset now = new(2026, 7, 16, 5, 0, 0, TimeSpan.Zero);
        var provider = new WindowsTimeStatusProvider(new FakeProbe(
            new TimeStatusSnapshot(now, -240),
            new TimeStatusSnapshot(now.AddMilliseconds(5), -240)));
        TimeStatusSnapshot? result = await provider.ReadVerifiedAsync(CancellationToken.None);
        Assert.That(result, Is.EqualTo(new TimeStatusSnapshot(now, -240)));
    }

    [Test]
    public async Task ClockMovingBackwardsFailsClosed()
    {
        DateTimeOffset now = new(2026, 7, 16, 5, 0, 0, TimeSpan.Zero);
        var provider = new WindowsTimeStatusProvider(new FakeProbe(
            new TimeStatusSnapshot(now, -240),
            new TimeStatusSnapshot(now.AddSeconds(-1), -240)));
        Assert.That(await provider.ReadVerifiedAsync(CancellationToken.None), Is.Null);
    }

    // Renew al máximo (w8): a zone changed while BAXY runs is the one read, not the one Windows had when it started.
    [Test]
    public void TheZoneIsReadAfreshOnEachRead()
    {
        TimeZoneInfo[] zones =
        [
            TimeZoneInfo.CreateCustomTimeZone("w8-a", TimeSpan.FromHours(-3), "a", "a"),
            TimeZoneInfo.CreateCustomTimeZone("w8-b", TimeSpan.FromHours(1), "b", "b"),
        ];
        int reads = 0;
        var probe = new SystemTimeStatusProbe(() => zones[Math.Min(reads++, 1)]);

        Assert.That(probe.Read().LocalUtcOffsetMinutes, Is.EqualTo(-180));
        Assert.That(probe.Read().LocalUtcOffsetMinutes, Is.EqualTo(60));
        Assert.That(new SystemTimeStatusProbe().Read().LocalUtcOffsetMinutes,
            Is.EqualTo((int)TimeZoneInfo.Local.GetUtcOffset(DateTimeOffset.UtcNow).TotalMinutes));
    }

    private sealed class FakeProbe(params TimeStatusSnapshot[] values) : ITimeStatusProbe
    {
        private readonly Queue<TimeStatusSnapshot> _values = new(values);
        public TimeStatusSnapshot Read() => _values.Dequeue();
    }
}
