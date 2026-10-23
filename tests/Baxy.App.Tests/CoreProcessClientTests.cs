using Baxy.App;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// Al máximo, flujos (audit of the daily flows, finding 2): the App waited 30 + 70 s for every call and then took the
/// engine as stuck and restarted it (mpv, window ids and provenance lost), whatever the call's provider takes.
/// </summary>
[TestFixture]
public sealed class CoreProcessClientTests
{
    [Test]
    public void ACallWhoseProviderTakesLongIsWaitedForItsBudget()
    {
        TimeSpan asked = TimeSpan.FromSeconds(30);

        Assert.That(CoreProcessClient.ResponseBudget("file.read", asked), Is.EqualTo(TimeSpan.FromSeconds(90)));
        Assert.That(CoreProcessClient.ResponseBudget("media.play.query", asked), Is.EqualTo(TimeSpan.FromSeconds(85)));
    }

    [Test]
    public void AnOrdinaryCallOrALongerWaitKeepsTheCallersTime()
    {
        Assert.That(CoreProcessClient.ResponseBudget("system.time", TimeSpan.FromSeconds(30)),
            Is.EqualTo(TimeSpan.FromSeconds(30)));
        Assert.That(CoreProcessClient.ResponseBudget("file.read", TimeSpan.FromSeconds(120)),
            Is.EqualTo(TimeSpan.FromSeconds(120)));
    }
}
