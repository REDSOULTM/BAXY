using System.IO;
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
    // Al máximo (notebook, engine_no_answer): why the channel to the core ended is written with the trace on.
    [Test]
    public void ADisconnectReportSaysWhatEndedTheCoreAndItsLastStderr()
    {
        string report = CoreProcessClient.DisconnectReport(
            new DateTimeOffset(2026, 10, 24, 4, 40, 0, TimeSpan.FromHours(-3)),
            new System.IO.InvalidDataException("El core devolvió un tipo de mensaje desconocido."),
            exitCode: null,
            ["warn: steam", "fail: provider"]);

        using var document = System.Text.Json.JsonDocument.Parse(report);
        System.Text.Json.JsonElement root = document.RootElement;
        Assert.Multiple(() =>
        {
            Assert.That(root.GetProperty("exception").GetString(), Is.EqualTo("InvalidDataException"));
            Assert.That(root.GetProperty("message").GetString(), Does.Contain("tipo de mensaje desconocido"));
            Assert.That(root.GetProperty("exitCode").ValueKind, Is.EqualTo(System.Text.Json.JsonValueKind.Null));
            Assert.That(root.GetProperty("stderr").GetArrayLength(), Is.EqualTo(2));
            Assert.That(root.GetProperty("at").GetString(), Does.StartWith("2026-10-24T04:40:00"));
        });
    }
    // Stopping the core waited for its stdout/stderr readers with no bound: a program the core launched inherits the
    // pipe's write end, so the read never ends and the stop never returned. The reap gives the reader a bounded wait,
    // closes the stream, waits once more and moves on (LocalJsonlSidecarProcess.ReapPumpWithinAsync).
    [Test]
    public async Task StoppingTheCoreDoesNotWaitForeverForAReaderAProgramItLaunchedKeepsOpen()
    {
        var neverEnds = new TaskCompletionSource();
        int closed = 0;

        Task reap = CoreProcessClient.ReapPumpAsync(neverEnds.Task, () => closed++, TimeSpan.FromMilliseconds(50));

        Assert.That(await Task.WhenAny(reap, Task.Delay(TimeSpan.FromSeconds(10))), Is.SameAs(reap));
        Assert.That(closed, Is.EqualTo(1));
    }

    [Test]
    public async Task AReaderThatEndsOrFailsIsObservedWithoutClosingAnything()
    {
        int closed = 0;

        await CoreProcessClient.ReapPumpAsync(Task.CompletedTask, () => closed++, TimeSpan.FromSeconds(1));
        await CoreProcessClient.ReapPumpAsync(Task.FromException(new IOException("pipe")), () => closed++, TimeSpan.FromSeconds(1));
        await CoreProcessClient.ReapPumpAsync(null, () => closed++, TimeSpan.FromSeconds(1));

        Assert.That(closed, Is.Zero);
    }
}
