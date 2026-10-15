using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Ronda 22 (r18 t4-c05: the weather's 5.3 s were one number): the trace of a core call tells where a provider
/// says its time went, beside the M106 cut of the observation.
/// </summary>
[TestFixture]
public sealed class CoreCallElapsedTraceTests
{
    [Test]
    public void AProviderElapsedSplitReachesTheCoreCallTrace()
    {
        const string message =
            """{"status":"succeeded","observed":{"location":"Buenos Aires","elapsedMs":{"place":120,"forecast":640,"total":700}}}""";

        Assert.That(
            CoreProcessClient.CoreCallEndDetail(message),
            Is.EqualTo("elapsed.place.120.forecast.640.total.700"));
    }

    [Test]
    public void ACallWithoutElapsedKeepsTheTraceItHad()
    {
        Assert.Multiple(() =>
        {
            Assert.That(CoreProcessClient.CoreCallEndDetail("""{"status":"succeeded","observed":{"value":40}}"""), Is.Null);
            Assert.That(CoreProcessClient.CoreCallEndDetail("""{"status":"succeeded","observedLimit":"omitted"}"""),
                Is.EqualTo("observed.omitted"));
            Assert.That(CoreProcessClient.CoreCallEndDetail(null), Is.Null);
            Assert.That(CoreProcessClient.CoreCallEndDetail("no json"), Is.Null);
        });
    }

    [Test]
    public void TheObservationCutIsKeptWhenBothDoNotFitOneLabel()
    {
        const string message =
            """{"status":"succeeded","observedLimit":"projected","observed":{"elapsedMs":{"uia":12345,"ocr":12345,"color":12345,"total":12345}}}""";

        Assert.That(CoreProcessClient.CoreCallEndDetail(message), Is.EqualTo("observed.projected"));
    }
}
