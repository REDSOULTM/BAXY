using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Review of 1b9b736e7: what the worker's front net saw reaches the receipt (and the mission's annoyance meter) instead
/// of staying in counters only the ping told.
/// </summary>
[TestFixture]
public sealed class UiaFrontReportTests
{
    [Test]
    public void AFrontGivenBackIsStillAChangeAndAFailedReturnIsNotRestored()
    {
        using JsonDocument back = JsonDocument.Parse("""{"ok":true,"frontChanged":true,"frontRestored":true,"frontReturnFailed":0}""");
        using JsonDocument kept = JsonDocument.Parse("""{"ok":true,"frontChanged":true,"frontRestored":false,"frontReturnFailed":2}""");
        Assert.Multiple(() =>
        {
            Assert.That(UiaFrontReport.Read(back.RootElement), Is.EqualTo(new UiaFrontReport(true, 0)));
            Assert.That(UiaFrontReport.Read(kept.RootElement), Is.EqualTo(new UiaFrontReport(false, 2)));
        });
    }

    [Test]
    public void AnAnswerWithoutAFrontChangeHasNoReport()
    {
        // Counter-cases: nothing moved, or an answer that says it did not.
        using JsonDocument quiet = JsonDocument.Parse("""{"ok":true,"method":"invoke"}""");
        using JsonDocument no = JsonDocument.Parse("""{"ok":true,"frontChanged":false}""");
        Assert.Multiple(() =>
        {
            Assert.That(UiaFrontReport.Read(quiet.RootElement), Is.Null);
            Assert.That(UiaFrontReport.Read(no.RootElement), Is.Null);
        });
    }

    [Test]
    public void ALaterPostReadIsTheLatestWordAndTheReportIsWrittenToTheReceipt()
    {
        UiaFrontReport? latest = UiaFrontReport.Latest(new UiaFrontReport(true, 0), new UiaFrontReport(false, 1));
        UiaFrontReport? kept = UiaFrontReport.Latest(new UiaFrontReport(true, 0), null);
        var node = new JsonObject { ["ok"] = true };
        latest!.Value.Write(node);
        Assert.Multiple(() =>
        {
            Assert.That(latest, Is.EqualTo(new UiaFrontReport(false, 1)));
            Assert.That(kept, Is.EqualTo(new UiaFrontReport(true, 0)), "a post-read that saw nothing keeps the earlier word");
            Assert.That(node.ToJsonString(), Is.EqualTo("""{"ok":true,"frontChanged":true,"frontRestored":false,"frontReturnFailed":1}"""));
        });
    }
}
