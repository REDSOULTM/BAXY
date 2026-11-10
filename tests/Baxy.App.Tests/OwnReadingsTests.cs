using System.Diagnostics;
using System.Reflection;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// assistant.status (f6 estado, 2026-10-25): what the view shows of BAXY itself, asked by voice (src/Baxy.App/OwnReadings.cs).
/// The model's video memory and RAM are the rail's reading (FieldTelemetrySampler), with their unit; the internet exits
/// are this session's log (the transcript's steps that went out), the latest 20 with their total. The App answers the
/// call itself: the engine holds none of it.
/// </summary>
[TestFixture]
[NonParallelizable]
public sealed class OwnReadingsTests
{
    [Test]
    public void TheModelsVideoMemoryAndRamGoWithTheirUnit()
    {
        JsonElement receipt = Completed(OwnReadings.Model(new FieldMetricSnapshot(12, 30, 55, 2.3456, 0.71)));

        Assert.Multiple(() =>
        {
            Assert.That(receipt.GetProperty("scope").GetString(), Is.EqualTo("model"));
            Assert.That(receipt.GetProperty("videoMemory").GetProperty("value").GetDouble(), Is.EqualTo(2.35));
            Assert.That(receipt.GetProperty("videoMemory").GetProperty("unit").GetString(), Is.EqualTo("GB"));
            Assert.That(receipt.GetProperty("ram").GetProperty("value").GetDouble(), Is.EqualTo(0.71));
            Assert.That(receipt.GetProperty("ram").GetProperty("unit").GetString(), Is.EqualTo("GB"));
            // Only the model: the PC's own use is system.status'.
            Assert.That(receipt.TryGetProperty("cpu", out _), Is.False);
        });
    }

    // P1.1 (a): the confirmation mode is read, never said from memory: the same store the engine rereads at each call.
    [TestCase(Baxy.Kernel.Policy.ConfirmationMode.Normal, "normal", true)]
    [TestCase(Baxy.Kernel.Policy.ConfirmationMode.Bypass, "bypass", false)]
    public void TheConfirmationModeIsTheOneTheEngineReads(Baxy.Kernel.Policy.ConfirmationMode mode, string said, bool asks)
    {
        JsonElement receipt = Completed(OwnReadings.Confirmation(mode));

        Assert.Multiple(() =>
        {
            Assert.That(receipt.GetProperty("scope").GetString(), Is.EqualTo("confirmation"));
            Assert.That(receipt.GetProperty("mode").GetString(), Is.EqualTo(said));
            Assert.That(receipt.GetProperty("asksBeforeRiskyCalls").GetBoolean(), Is.EqualTo(asks));
            // REV7: nothing asks in Bypass, so the receipt names nothing that «always» asks (INT5 had added it).
            Assert.That(receipt.TryGetProperty("alwaysAsksBefore", out _), Is.False);
        });
    }

    // A mode file another program holds locked is not taken for «normal»: the call fails.
    [Test]
    public void AnUnreadableConfirmationModeFails()
    {
        OperationOutcome unread = OwnReadings.Confirmation(null);

        Assert.Multiple(() =>
        {
            Assert.That(unread.Succeeded, Is.False);
            Assert.That(unread.ErrorCode, Is.EqualTo(OwnReadings.ConfirmationUnreadable));
        });
    }

    // A reading the PC did not give is left out (the view's «—»), never a zero; with neither, the call fails.
    [Test]
    public void AReadingThePcDidNotGiveIsLeftOutNeverZero()
    {
        JsonElement receipt = Completed(OwnReadings.Model(new FieldMetricSnapshot(null, null, null, null, 0.5)));
        OperationOutcome none = OwnReadings.Model(new FieldMetricSnapshot(1, 1, 1, null, double.NaN));

        Assert.Multiple(() =>
        {
            Assert.That(receipt.TryGetProperty("videoMemory", out _), Is.False);
            Assert.That(receipt.GetProperty("ram").GetProperty("value").GetDouble(), Is.EqualTo(0.5));
            Assert.That(none.Succeeded, Is.False);
            Assert.That(none.ErrorCode, Is.EqualTo(OwnReadings.ModelUnreadable));
        });
    }

    [Test]
    public void TheSessionsInternetExitsAreItsStepsThatWentOutWithTheirTime()
    {
        var transcript = new FieldTranscript();
        transcript.You("busca el clima");
        transcript.Step(new JsonObject { ["id"] = "c1", ["net"] = "búsqueda «clima viña»" });
        transcript.Step(new JsonObject { ["id"] = "c2" });
        transcript.Step(new JsonObject { ["id"] = "c3", ["net"] = "página de example.org" });
        transcript.Words("Listo.", null);
        transcript.You("hola");
        transcript.Words("Hola.", null);
        string at = (string)transcript.Items[1]["ts"]!;

        JsonElement receipt = Completed(OwnReadings.Internet(transcript.Items));

        Assert.Multiple(() =>
        {
            Assert.That(receipt.GetProperty("scope").GetString(), Is.EqualTo("internet"));
            Assert.That(receipt.GetProperty("total").GetInt32(), Is.EqualTo(2));
            Assert.That(receipt.GetProperty("exits").EnumerateArray()
                    .Select(static exit => (exit.GetProperty("destination").GetString(), exit.GetProperty("at").GetString())),
                Is.EqualTo(new[] { ("búsqueda «clima viña»", at), ("página de example.org", at) }));
            Assert.That(receipt.TryGetProperty("shown", out _), Is.False);
        });
    }

    // Nothing went out: none, and the total says so.
    [Test]
    public void ASessionWithNoExitsSaysNone()
    {
        var transcript = new FieldTranscript();
        transcript.You("hola");
        transcript.Words("Hola.", null);

        JsonElement receipt = Completed(OwnReadings.Internet(transcript.Items));

        Assert.Multiple(() =>
        {
            Assert.That(receipt.GetProperty("total").GetInt32(), Is.Zero);
            Assert.That(receipt.GetProperty("exits").GetArrayLength(), Is.Zero);
        });
    }

    // Bounded: the latest 20, oldest first, with how many there were.
    [Test]
    public void ManyExitsListTheLatestWithTheTotal()
    {
        var transcript = new FieldTranscript();
        for (int index = 1; index <= 25; index++)
        {
            transcript.You("busca " + index);
            transcript.Step(new JsonObject { ["id"] = "c" + index, ["net"] = "búsqueda «" + index + "»" });
            transcript.Words("Listo.", null);
        }

        JsonElement receipt = Completed(OwnReadings.Internet(transcript.Items));
        string?[] destinations = [.. receipt.GetProperty("exits").EnumerateArray()
            .Select(static exit => exit.GetProperty("destination").GetString())];

        Assert.Multiple(() =>
        {
            Assert.That(receipt.GetProperty("total").GetInt32(), Is.EqualTo(25));
            Assert.That(destinations, Has.Length.EqualTo(OwnReadings.ExitsShown));
            Assert.That(destinations[0], Is.EqualTo("búsqueda «6»"));
            Assert.That(destinations[^1], Is.EqualTo("búsqueda «25»"));
            Assert.That(receipt.GetProperty("shown").GetString(), Is.EqualTo("latest 20"));
        });
    }

    // Only this session: a session opened or started replaces the transcript, and an earlier one's exits are gone.
    [Test]
    public void AnotherSessionsExitsAreNotRead()
    {
        var transcript = new FieldTranscript();
        transcript.You("busca algo");
        transcript.Step(new JsonObject { ["id"] = "c1", ["net"] = "búsqueda «algo»" });
        transcript.Words("Listo.", null);
        transcript.Replace([]);

        Assert.That(Completed(OwnReadings.Internet(transcript.Items)).GetProperty("total").GetInt32(), Is.Zero);
    }

    // In the turn loop: the call is read by the App by its scope, never sent to the engine, and the model reads the
    // kernel's own receipt (completed, output_only, the facts observed).
    [Test]
    public async Task TheTurnLoopReadsItInTheAppAndTheModelReadsTheReceipt()
    {
        var asked = new List<string>();
        List<NativeTurnStep> steps = await RunAsync(new JsonObject { ["scope"] = "model" }, asked);

        NativeTurnStep step = steps.Single();
        JsonNode observation = JsonNode.Parse(step.Observation)!;
        Assert.Multiple(() =>
        {
            Assert.That(asked, Is.EqualTo(new[] { "model" }));
            Assert.That(step.Operation, Is.EqualTo("assistant.status"));
            Assert.That(step.Status, Is.EqualTo("completed"));
            Assert.That(step.Verified, Is.True);
            Assert.That((string?)observation["verification"], Is.EqualTo("output_only"));
            Assert.That((double?)observation["observed"]?["videoMemory"]?["value"], Is.EqualTo(1.5));
            Assert.That((string?)observation["observed"]?["ram"]?["unit"], Is.EqualTo("GB"));
        });
    }

    // Arguments the catalog's schema refuses are refused as the kernel refuses them, and nothing is read.
    [Test]
    public async Task AScopeTheCatalogDoesNotListIsRefusedUnread()
    {
        var asked = new List<string>();
        List<NativeTurnStep> steps = await RunAsync(new JsonObject { ["scope"] = "gpu" }, asked);

        JsonNode observation = JsonNode.Parse(steps.Single().Observation)!;
        Assert.Multiple(() =>
        {
            Assert.That(asked, Is.Empty);
            Assert.That((string?)observation["status"], Is.EqualTo("failed"));
            Assert.That((string?)observation["error"], Is.EqualTo("invalid_arguments"));
            Assert.That((string?)observation["argumentProblems"]?[0]?["argument"], Is.EqualTo("scope"));
        });
    }

    // The view's channel answers it from what it serves the view: the model's reading is GET /metrics' own sampler.
    [Test]
    public async Task TheChannelReadsWhatTheViewIsShown()
    {
        var measured = 0;
        await using var telemetry = new FieldTelemetrySampler(static () => null, _ =>
        {
            Interlocked.Increment(ref measured);
            return Task.FromResult(new FieldMetricSnapshot(10, 20, 50, 1.25, 0.5));
        });
        await using var viewModel = new MainWindowViewModel { Sound = static _ => { } };
        var sink = new ChannelHarness.RecordingSink();
        await using var channel = new FieldProductChannel(viewModel, sink, telemetry, CancellationToken.None);

        FieldHttpResponse metrics = await channel.HandleHttpAsync("GET", "/metrics", null);
        OperationOutcome model = await viewModel.OwnReader!("model", CancellationToken.None);
        OperationOutcome internet = await viewModel.OwnReader!("internet", CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That((double?)JsonNode.Parse(metrics.Body)?["model_vram_gb"], Is.EqualTo(1.25));
            Assert.That(Completed(model).GetProperty("videoMemory").GetProperty("value").GetDouble(), Is.EqualTo(1.25));
            Assert.That(Completed(model).GetProperty("ram").GetProperty("value").GetDouble(), Is.EqualTo(0.5));
            Assert.That(measured, Is.EqualTo(1), "the voice's reading is the view's, not a new measure");
            Assert.That(Completed(internet).GetProperty("total").GetInt32(), Is.Zero);
        });
    }

    private static async Task<List<NativeTurnStep>> RunAsync(JsonObject arguments, List<string> asked)
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["reply"] = new JsonObject
            {
                ["turn.decide"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "action",
                    ["operation"] = "assistant.status",
                    ["arguments"] = arguments,
                },
                ["turn.continue"] = new JsonObject
                {
                    ["type"] = "turn.result",
                    ["kind"] = "conversation",
                    ["reply"] = "Listo.",
                },
            },
        });
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        var core = new CoreProcessClient();
        const BindingFlags Private = BindingFlags.Instance | BindingFlags.NonPublic;
        typeof(CoreProcessClient).GetField("_ready", Private)!.SetValue(core, true);
        typeof(CoreProcessClient).GetField("_process", Private)!.SetValue(core, Process.GetCurrentProcess());
        var steps = new List<NativeTurnStep>();
        var registry = new RetryableOperationRegistry();
        var loop = new NativeTurnLoop(new NativeTurnLoop.Host
        {
            Core = () => core,
            Mind = () => mind,
            Registry = () => registry,
            MemoryProtector = static () => null,
            Publish = static (_, _) => { },
            Fail = static _ => { },
            Notice = static _ => { },
            NoticeHeard = static () => false,
            StepCompleted = steps.Add,
            OwnReading = (scope, _) =>
            {
                asked.Add(scope);
                return Task.FromResult(OwnReadings.Model(new FieldMetricSnapshot(null, null, null, 1.5, 0.25)));
            },
        });

        await loop.RunAsync("¿cuánta memoria estás usando?", Stopwatch.GetTimestamp(), CancellationToken.None);
        return steps;
    }

    private static JsonElement Completed(OperationOutcome outcome)
    {
        Assert.That(outcome is { Succeeded: true, Verified: true }, outcome.ErrorCode);
        return outcome.Result!.Value;
    }
}
