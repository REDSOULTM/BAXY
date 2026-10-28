using System.IO;
using System.Runtime.CompilerServices;
using System.Text.Json.Nodes;
using Baxy.Kernel.Operations;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>The App's client of the mind (src/Baxy.App/MindSidecarClient.cs) against the fake mind.</summary>
[TestFixture]
public sealed class MindSidecarClientTests
{
    [Test]
    public async Task ReleasingTheMicrophoneAndReadingTheVoiceDoNotWaitForATurn()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject { ["hold"] = new JsonObject { ["turn.decide"] = "go" } });
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        Task<MindStep?> turn = mind.DecideAsync("hola", null, CancellationToken.None);
        Assert.That(await fake.WaitSeenAsync("turn.decide"), Is.True);

        // The mind answers both on its reader, as it reads them; behind the turn they waited for the model.
        using var meanwhile = new CancellationTokenSource(TimeSpan.FromSeconds(3));
        bool released = await Within(() => mind.VoiceReleaseAsync(TimeSpan.FromSeconds(3), meanwhile.Token));
        bool status = await Within(async () =>
            await mind.VoiceStatusAsync(TimeSpan.FromSeconds(3), meanwhile.Token) is not null);

        fake.Open("go");
        Assert.That(await turn, Is.Not.Null);
        Assert.That(released, Is.True, "voice.release waited behind the turn");
        Assert.That(status, Is.True, "voice.status waited behind the turn");
    }

    [Test]
    public void ALateNoticeIsNotADeadMind()
    {
        // Feria 2026-10-27: the turn's notice waits behind its own decision, which may write a long document.
        Assert.Multiple(() =>
        {
            Assert.That(MindSidecarClient.InvalidatesMind("request_timeout", "turn.notice"), Is.False);
            Assert.That(MindSidecarClient.InvalidatesMind("request_timeout", "turn.continue"), Is.True);
            Assert.That(MindSidecarClient.InvalidatesMind("request_io", "turn.notice"), Is.True);
        });
    }

    [Test]
    public void TheCatalogTheMindReadsCarriesEachToolsEffects()
    {
        // Al máximo 5.1: «corrige» reads them; a tool without one carries no field, as the saved catalogs.
        JsonObject request = MindSidecarClient.CreateCatalogConfigureRequest(
            [.. ProductCatalog.ToolDescriptors.Select(static descriptor =>
                ProductCatalog.CreateToolDescriptor(new OperationDefinition(descriptor)))],
            applicationCatalog: null);
        JsonObject Tool(string name) => request["capabilities"]!.AsArray().OfType<JsonObject>()
            .Single(tool => (string?)tool["name"] == name);

        Assert.Multiple(() =>
        {
            Assert.That(Tool("input.key.press")["effects"]!.ToJsonString(), Is.EqualTo("[\"window_input\"]"));
            Assert.That(Tool("web.search")["effects"]!.ToJsonString(), Is.EqualTo("[\"network\"]"));
            Assert.That(Tool("note.create").ContainsKey("effects"), Is.False);
        });
    }

    [Test]
    public void TheCatalogTheMindReadsCarriesTheModesInWhichTheKernelConfirmsEachTool()
    {
        // P2.41: the mind's doubt asks in words only about a call the kernel would run unasked (mind.py, _unasked), by
        // RiskPolicy.Evaluate itself: a song or a page go direct in both modes, an email asks in normal mode, and a
        // message to a person asks in Bypass too.
        JsonObject request = MindSidecarClient.CreateCatalogConfigureRequest(
            [.. ProductCatalog.ToolDescriptors.Select(static descriptor =>
                ProductCatalog.CreateToolDescriptor(new OperationDefinition(descriptor)))],
            applicationCatalog: null);
        string Confirms(string name) => request["capabilities"]!.AsArray().OfType<JsonObject>()
            .Single(tool => (string?)tool["name"] == name)["confirms"]!.ToJsonString();

        Assert.Multiple(() =>
        {
            Assert.That(Confirms("media.play.query"), Is.EqualTo("[]"));
            Assert.That(Confirms("browser.navigate"), Is.EqualTo("[]"));
            Assert.That(Confirms("email.send"), Is.EqualTo("[\"normal\"]"));
            Assert.That(Confirms("message.send"), Is.EqualTo("[\"normal\",\"bypass\"]"));
            Assert.That(Confirms("system.power"), Is.EqualTo("[]"));
        });
    }

    [Test]
    public void TheCatalogTheMindReadsCarriesEachToolsGroupOfWhatItCanDo()
    {
        // Feria 2026-10-27: asked what it can do, the model named things no tool does; it reads the groups of the panel
        // «Qué puedo hacer» (operation-labels.v1.json), the same words the person sees there.
        JsonObject request = MindSidecarClient.CreateCatalogConfigureRequest(
            [.. ProductCatalog.ToolDescriptors.Select(static descriptor =>
                ProductCatalog.CreateToolDescriptor(new OperationDefinition(descriptor)))],
            applicationCatalog: null);
        JsonObject Tool(string name) => request["capabilities"]!.AsArray().OfType<JsonObject>()
            .Single(tool => (string?)tool["name"] == name);

        Assert.Multiple(() =>
        {
            Assert.That((string?)Tool("web.search")["group"], Is.EqualTo("Web y navegador"));
            Assert.That((string?)Tool("backup.create")["group"], Is.EqualTo("Copias de seguridad"));
        });
    }

    [Test]
    public async Task AFieldOfAnotherTypeFromTheMindEndsNeitherItsReaderNorTheRequest()
    {
        // Revisión de calidad (2026-10-25): a line whose type, text or id was not a string ended the reader with the mind
        // still running (ReadyLost, the mind relaunched), and a reply with such a field threw out of the request instead
        // of being null or false.
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["emit"] = new JsonObject
            {
                ["session.new"] = new JsonArray(
                    new JsonObject { ["type"] = "voice.transcript", ["text"] = 7 },
                    new JsonObject { ["type"] = 5 },
                    new JsonObject { ["type"] = "x", ["id"] = 3 }),
            },
            ["reply"] = new JsonObject
            {
                ["voice.status"] = new JsonObject
                {
                    ["type"] = "voice.status.result",
                    ["status"] = new JsonObject { ["available"] = "yes", ["input"] = true },
                },
            },
        });
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        Assert.That(await mind.NewSessionAsync(CancellationToken.None), Is.True);

        MindVoiceStatus? status = await mind.VoiceStatusAsync(TimeSpan.FromSeconds(5), CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(status, Is.Not.Null, "the reader ended on the lines after session.ready");
            Assert.That(status?.Available, Is.False);
            Assert.That(status?.InputAvailable, Is.True);
            Assert.That(mind.IsReady, Is.True);
        });
    }

    [Test]
    public void AStepWithAFieldOfAnotherTypeIsNoStep()
    {
        Assert.Multiple(() =>
        {
            Assert.That(MindSidecarClient.ParseStep(new JsonObject { ["type"] = "turn.result", ["kind"] = 3 }), Is.Null);
            Assert.That(MindSidecarClient.ParseStep(new JsonObject
            {
                ["type"] = "turn.result", ["kind"] = "action", ["operation"] = 5,
            }), Is.Null);
            Assert.That(MindSidecarClient.ParseStep(new JsonObject { ["type"] = true }), Is.Null);
            Assert.That(MindSidecarClient.ParseStep(new JsonObject
            {
                ["type"] = "turn.result", ["kind"] = "conversation", ["reply"] = "hola",
            })?.Text, Is.EqualTo("hola"));
        });
    }

    // P0.12 (noche 2026-10-27): a turn request the mind answered with an error came back as null, the same as one it
    // never answered; its code reaches the turn's close now.
    [Test]
    public async Task ATurnRequestTheMindAnswersWithAnErrorComesBackWithItsCode()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject { ["fail"] = new JsonArray("turn.decide") });
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();

        MindStep? step = await mind.DecideAsync("hola", null, CancellationToken.None);

        Assert.That((step?.Kind, step?.Text), Is.EqualTo(((string?)MindStep.Error, (string?)"request_failed")));
        Assert.That(mind.IsReady, Is.True, "an answered error is no dead mind");
    }

    [TestCase("Request Failed")]
    [TestCase("código")]
    [TestCase(null)]
    public void AnErrorCodeThatIsNoStableLabelIsNotCopied(string? code)
    {
        var reply = new JsonObject { ["type"] = "error" };
        if (code is not null)
        {
            reply["code"] = code;
        }

        Assert.That(MindSidecarClient.ParseStep(reply)?.Text, Is.EqualTo("invalid"));
        Assert.That(MindSidecarClient.ParseStep(new JsonObject { ["type"] = "error", ["code"] = new string('a', 65) })?.Text,
            Is.EqualTo("invalid"));
    }

    // P0.12: the mind's stderr (baxy_mind_renew_failure:<request>:<error>) was read and dropped; the App keeps it beside
    // the mind's trace, the previous run's once, and forgets both with the trace.
    [Test]
    public async Task TheMindsStderrIsKeptBesideItsTraceAndForgottenWithIt()
    {
        using var fake = new FakeMind();
        File.WriteAllText(fake.StandardErrorLog, "previous run\n");
        fake.Script(new JsonObject
        {
            ["stderr"] = new JsonObject { ["turn.decide"] = new JsonArray("baxy_mind_renew_failure:turn.decide:x") },
        });
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        Assert.That(File.ReadAllText(fake.StandardErrorLog + ".1"), Is.EqualTo("previous run\n"));

        _ = await mind.DecideAsync("hola", null, CancellationToken.None);
        Assert.That(await Eventually(() => Shared(fake.StandardErrorLog).Contains(
            "baxy_mind_renew_failure:turn.decide:x", StringComparison.Ordinal)), Is.True);

        Assert.That(await mind.TraceForgetAsync(CancellationToken.None), Is.True);
        Assert.That(Shared(fake.StandardErrorLog), Is.Empty);
        Assert.That(File.Exists(fake.StandardErrorLog + ".1"), Is.False);
    }

    // P2.34: a log this run could not open still held the previous runs' stderr; forgetting said it was gone.
    [Test]
    public async Task TheStderrLogThisRunCouldNotOpenIsForgottenToo()
    {
        using var fake = new FakeMind();
        File.WriteAllText(fake.StandardErrorLog, "previous run\n");
        File.WriteAllText(fake.StandardErrorLog + ".1", "the run before\n");
        MindSidecarClient mind;
        using (new FileStream(fake.StandardErrorLog, FileMode.Open, FileAccess.Read, FileShare.None))
        {
            mind = await FakeMind.StartClientAsync();
        }

        await using (mind)
        {
            Assert.That(await mind.TraceForgetAsync(CancellationToken.None), Is.True);
            Assert.That((File.Exists(fake.StandardErrorLog), File.Exists(fake.StandardErrorLog + ".1")),
                Is.EqualTo((false, false)));
        }
    }

    [Test]
    public void TheStderrLogStopsAtItsCapWithoutCuttingACharacter()
    {
        string folder = Path.Combine(Path.GetTempPath(), "baxy-app-tests", Guid.NewGuid().ToString("N"));
        string path = Path.Combine(folder, "stderr.log");
        try
        {
            using (BoundedStandardErrorLog log = BoundedStandardErrorLog.Open(path, capBytes: 8)!)
            {
                log.Write("abcdef"u8);
                log.Write("ñññ"u8); // 2 bytes each: one fits whole, the next would cross the cap
                log.Write("z"u8);
            }

            Assert.That(File.ReadAllText(path, new System.Text.UTF8Encoding(false, throwOnInvalidBytes: true)),
                Is.EqualTo("abcdefñ"));

            // A character split across two writes, the cap inside it: its first byte, written before, goes too.
            using (BoundedStandardErrorLog log = BoundedStandardErrorLog.Open(path, capBytes: 3)!)
            {
                byte[] euro = "a€"u8.ToArray(); // 1 + 3 bytes
                log.Write(euro.AsSpan(0, 2));
                log.Write(euro.AsSpan(2));
            }

            Assert.That(File.ReadAllText(path), Is.EqualTo("a"));

            // Forgotten, the log starts again from its first byte.
            using (BoundedStandardErrorLog log = BoundedStandardErrorLog.Open(path, capBytes: 8)!)
            {
                log.Write("abc"u8);
                Assert.That(log.Forget(), Is.True);
                log.Write("q"u8);
            }

            Assert.That((File.ReadAllText(path), File.Exists(path + ".1")), Is.EqualTo(("q", false)));
        }
        finally
        {
            Directory.Delete(folder, recursive: true);
        }
    }

    // The App holds the log open while the mind runs.
    private static string Shared(string path)
    {
        using var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
        using var reader = new StreamReader(stream);
        return reader.ReadToEnd();
    }

    private static async Task<bool> Eventually(Func<bool> condition)
    {
        for (int attempt = 0; attempt < 250; attempt++)
        {
            if (condition())
            {
                return true;
            }

            await Task.Delay(20);
        }

        return false;
    }

    [Test]
    public async Task AStartAbandonedBeforeTheHelloLeavesNoUnobservedFailure()
    {
        // Arreglos de uso real (2026-10-26): a core start that failed gave up on the mind still loading; the hello the
        // pump faulted afterwards was seen by nobody and reached TaskScheduler.UnobservedTaskException on every retry.
        using var fake = new FakeMind();
        fake.Script(new JsonObject { ["delay"] = new JsonObject { ["hello"] = 30 } });
        var unobserved = new List<Exception>();
        void Record(object? sender, UnobservedTaskExceptionEventArgs eventArgs)
        {
            lock (unobserved)
            {
                unobserved.AddRange(eventArgs.Exception.InnerExceptions.Where(static inner => inner is IOException));
            }
        }

        TaskScheduler.UnobservedTaskException += Record;
        try
        {
            await AbandonStartAsync();
            for (int pass = 0; pass < 3; pass++)
            {
                GC.Collect();
                GC.WaitForPendingFinalizers();
            }

            Assert.That(unobserved, Is.Empty);
        }
        finally
        {
            TaskScheduler.UnobservedTaskException -= Record;
        }
    }

    // Its own frame, so nothing of the abandoned start stays reachable from the test's.
    [MethodImpl(MethodImplOptions.NoInlining)]
    private static async Task AbandonStartAsync()
    {
        var mind = new MindSidecarClient();
        using var abandon = new CancellationTokenSource(TimeSpan.FromMilliseconds(500));
        Assert.That(
            async () => await mind.TryStartAsync(Task.FromResult(FakeMind.EmptyCatalog), TimeSpan.FromSeconds(60),
                abandon.Token),
            Throws.InstanceOf<OperationCanceledException>());
        await mind.DisposeAsync();
    }

    // A request that is still waiting when its caller gives up is a false, not an exception.
    private static async Task<bool> Within(Func<Task<bool>> request)
    {
        try
        {
            return await request();
        }
        catch (OperationCanceledException)
        {
            return false;
        }
    }
}
