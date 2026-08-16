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

    private sealed class FakeProbe(params TimeStatusSnapshot[] values) : ITimeStatusProbe
    {
        private readonly Queue<TimeStatusSnapshot> _values = new(values);
        public TimeStatusSnapshot Read() => _values.Dequeue();
    }
}
