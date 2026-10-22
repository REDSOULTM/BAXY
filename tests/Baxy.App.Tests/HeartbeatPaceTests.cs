using Baxy.App;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// Al máximo 10.5 (src/Baxy.App/HeartbeatPace.cs): each change woke a heartbeat of ~2.4 s in the mind's only slot, and
/// the person's words waited behind it; changes now join in one beat every 30 s at most.
/// </summary>
[TestFixture]
public sealed class HeartbeatPaceTests
{
    [Test]
    public void ChangesJoinInOneBeatEveryThirtySeconds()
    {
        var clock = new ManualClock();
        var pace = new HeartbeatPace(clock);
        var beats = new List<int>();
        // A look every 15 s for two minutes, each with something new (an app, a download, the network…).
        for (int second = 15; second <= 120; second += 15)
        {
            clock.Now += TimeSpan.FromSeconds(15);
            if (pace.Due(changed: true))
            {
                pace.Beat();
                beats.Add(second);
            }
        }

        Assert.That(beats, Is.EqualTo(new[] { 30, 60, 90, 120 }));
    }

    [Test]
    public void WithNothingNewTheLookBeatsEveryFiveMinutes()
    {
        var clock = new ManualClock();
        var pace = new HeartbeatPace(clock);
        clock.Now += HeartbeatPace.Tick - TimeSpan.FromSeconds(1);
        Assert.That(pace.Due(changed: false), Is.False);
        clock.Now += TimeSpan.FromSeconds(1);
        Assert.That(pace.Due(changed: false), Is.True);
    }

    private sealed class ManualClock : TimeProvider
    {
        internal DateTimeOffset Now { get; set; } = new(2026, 10, 22, 10, 0, 0, TimeSpan.Zero);

        public override DateTimeOffset GetUtcNow() => Now;
    }
}
