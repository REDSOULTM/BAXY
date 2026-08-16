using System.Globalization;
using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// El registro del camino visible es diagnóstico: está apagado por defecto,
/// nunca escribe contenido de una persona ni prosa del modelo, y un fallo suyo
/// jamás puede alcanzar la ruta de producto.
/// </summary>
[TestFixture]
public sealed class ShellTraceTests
{
    [Test]
    public void TheTraceIsDisabledWithoutAnExplicitPath()
    {
        Assert.That(ShellTrace.TryCreate(null), Is.Null);
        Assert.That(ShellTrace.TryCreate("   "), Is.Null);
    }

    [Test]
    public void EveryRecordIsOneBoundedJsonLineWithMonotonicTime()
    {
        string path = Path.Combine(
            Path.GetTempPath(),
            "baxy-shell-trace-" + Guid.NewGuid().ToString("N") + ".jsonl");
        try
        {
            using (ShellTrace? trace = ShellTrace.TryCreate(path))
            {
                Assert.That(trace, Is.Not.Null);
                trace!.Record(
                    ShellTraceScopes.Turn,
                    "t1",
                    ShellTraceStages.DecisionStart);
                trace.Record(
                    ShellTraceScopes.Turn,
                    "t1",
                    ShellTraceStages.DecisionReady,
                    "action");
            }

            string[] lines = File.ReadAllLines(path);
            Assert.That(lines, Has.Length.EqualTo(2));

            JsonObject first = (JsonObject)JsonNode.Parse(lines[0])!;
            JsonObject second = (JsonObject)JsonNode.Parse(lines[1])!;
            Assert.That((long?)first["seq"], Is.EqualTo(1));
            Assert.That((long?)second["seq"], Is.EqualTo(2));
            Assert.That((string?)first["scope"], Is.EqualTo(ShellTraceScopes.Turn));
            Assert.That((string?)first["id"], Is.EqualTo("t1"));
            Assert.That(
                (string?)first["stage"],
                Is.EqualTo(ShellTraceStages.DecisionStart));
            Assert.That(first["detail"], Is.Null);
            Assert.That((string?)second["detail"], Is.EqualTo("action"));
            Assert.That(
                (double)second["ms"]!,
                Is.GreaterThanOrEqualTo((double)first["ms"]!));
        }
        finally
        {
            File.Delete(path);
        }
    }

    [Test]
    public void UserTextAndModelProseCanNeverReachTheTrace()
    {
        foreach (string hostile in new[]
        {
            "Hola, ¿cuánta batería queda?",
            "{\"leak\":true}",
            "a\nb",
            new string('x', ShellTrace.MaximumLabelLength + 1),
            "MiXeD",
        })
        {
            Assert.That(ShellTrace.SanitizeLabel(hostile), Is.EqualTo("invalid"), hostile);
        }

        Assert.That(
            ShellTrace.SanitizeLabel(ShellTraceStages.VisibleText),
            Is.EqualTo(ShellTraceStages.VisibleText));
    }

    [Test]
    public void CorrelationIdentifiersAcceptOnlyStableTokens()
    {
        Assert.That(ShellTrace.SanitizeId("t42"), Is.EqualTo("t42"));
        Assert.That(ShellTrace.SanitizeId("turn-04"), Is.EqualTo("turn-04"));
        Assert.That(ShellTrace.SanitizeId("t 42"), Is.EqualTo("invalid"));
        Assert.That(ShellTrace.SanitizeId(null), Is.EqualTo("invalid"));
    }

    [Test]
    public void EveryDeclaredStageSurvivesSanitization()
    {
        foreach (string stage in ShellTraceStages.All)
        {
            Assert.That(ShellTrace.SanitizeLabel(stage), Is.EqualTo(stage), stage);
        }
    }

    [Test]
    public void RecordingAfterDisposeIsSilentAndNeverThrows()
    {
        string path = Path.Combine(
            Path.GetTempPath(),
            "baxy-shell-trace-" + Guid.NewGuid().ToString("N") + ".jsonl");
        try
        {
            ShellTrace? trace = ShellTrace.TryCreate(path);
            Assert.That(trace, Is.Not.Null);
            trace!.Dispose();

            Assert.DoesNotThrow(() => trace.Record(
                ShellTraceScopes.Turn,
                "t1",
                ShellTraceStages.ResponseFinal));
            trace.Dispose();

            Assert.That(File.ReadAllText(path), Is.Empty);
        }
        finally
        {
            File.Delete(path);
        }
    }

    [Test]
    public void TheSinkStaysSilentUntilAnOverrideIsInstalled()
    {
        string path = Path.Combine(
            Path.GetTempPath(),
            "baxy-shell-trace-" + Guid.NewGuid().ToString("N") + ".jsonl");
        try
        {
            using ShellTrace? trace = ShellTrace.TryCreate(path);
            Assert.That(trace, Is.Not.Null);
            using (ShellTraceSink.Use(trace!))
            {
                ShellTraceSink.Record(
                    ShellTraceScopes.Bridge,
                    "t7",
                    ShellTraceStages.SubmitReceived);
            }

            ShellTraceSink.Record(
                ShellTraceScopes.Bridge,
                "t8",
                ShellTraceStages.SubmitReceived);
            trace!.Dispose();

            string content = File.ReadAllText(path);
            Assert.That(content, Does.Contain("\"id\":\"t7\""));
            Assert.That(content, Does.Not.Contain("\"id\":\"t8\""));
        }
        finally
        {
            File.Delete(path);
        }
    }

    [Test]
    public void ConcurrentWritersProduceWellFormedIndependentLines()
    {
        string path = Path.Combine(
            Path.GetTempPath(),
            "baxy-shell-trace-" + Guid.NewGuid().ToString("N") + ".jsonl");
        try
        {
            using (ShellTrace? trace = ShellTrace.TryCreate(path))
            {
                Assert.That(trace, Is.Not.Null);
                using var ready = new Barrier(4);
                Task[] writers = Enumerable.Range(0, 4)
                    .Select(index => Task.Run(() =>
                    {
                        ready.SignalAndWait();
                        for (int record = 0; record < 50; record++)
                        {
                            trace!.Record(
                                ShellTraceScopes.Turn,
                                "t" + index.ToString(CultureInfo.InvariantCulture),
                                ShellTraceStages.VisibleIndication);
                        }
                    }))
                    .ToArray();
                Assert.That(Task.WaitAll(writers, TimeSpan.FromSeconds(30)), Is.True);
            }

            string[] lines = File.ReadAllLines(path);
            Assert.That(lines, Has.Length.EqualTo(200));
            var sequences = new HashSet<long>();
            foreach (string line in lines)
            {
                JsonObject record = (JsonObject)JsonNode.Parse(line)!;
                Assert.That(sequences.Add((long)record["seq"]!), Is.True, line);
            }
        }
        catch (JsonException exception)
        {
            Assert.Fail("una línea concurrente quedó entrelazada: " + exception.Message);
        }
        finally
        {
            File.Delete(path);
        }
    }
}
