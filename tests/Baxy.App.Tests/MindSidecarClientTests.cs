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
    public void ATurnsRequestSaysHowLongTheWordsWereInTheApp()
    {
        JsonObject request = MindSidecarClient.DecideRequest("hola", null, TimeSpan.FromMilliseconds(8123.9));

        Assert.That(request["waitedMs"]!.GetValue<long>(), Is.EqualTo(8123));
        Assert.That(request.ContainsKey("pendingConfirmation"), Is.False);
    }

    // uso-82 (AMD e2e 2026-11-04): the App asks the mind to speak, and waits for each answer to sound
    // (MainWindowViewModel.CanSpeak, ProductConductorHost), only while the mind offers voice.speak. A mind with no voice
    // does not offer it; one whose voice failed after the hello says so in its voice.speak.result, and from then on the
    // App neither asks it nor waits for it (each turn on the AMD PC ended 10 s after its answer).
    [TestCase(false, true)]
    [TestCase(true, false)]
    public async Task TheVoiceIsAvailableOnlyWhileTheMindOffersIt(bool withoutVoice, bool available)
    {
        using var fake = new FakeMind();
        if (withoutVoice)
        {
            fake.Script(new JsonObject { ["unoffered"] = new JsonArray("voice.speak") });
        }

        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        Assert.That(mind.IsVoiceAvailable, Is.EqualTo(available));
    }

    [Test]
    public async Task AVoiceThatFailedAfterTheHelloIsNoLongerAvailable()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["reply"] = new JsonObject
            {
                ["voice.speak"] = new JsonObject
                {
                    ["type"] = "voice.speak.result", ["accepted"] = false, ["speaks"] = false,
                },
            },
        });
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        bool before = mind.IsVoiceAvailable;

        bool accepted = await mind.VoiceSpeakAsync("Son las tres.", TimeSpan.FromSeconds(5), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(before, Is.True);
            Assert.That(accepted, Is.False);
            Assert.That(mind.IsVoiceAvailable, Is.False);
            Assert.That(mind.IsReady, Is.True);
        });
    }

    // Ajuste c3 (humos del 31-10): the mind configured without the installed applications (the core's hello had none)
    // gets them when the core says them, once; the same list again sends nothing.
    [Test]
    public async Task AMindConfiguredWithoutTheInstalledListGetsItWhenItArrivesOnce()
    {
        using var fake = new FakeMind();
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();
        var arrived = new Baxy.Contracts.ApplicationCatalogSnapshot(
            Baxy.Contracts.ApplicationCatalogContract.CurrentVersion, true, true, ["Bloc de notas", "Configuración"]);

        bool first = await mind.UpdateApplicationCatalogAsync(arrived, TimeSpan.FromSeconds(10), CancellationToken.None);
        bool again = await mind.UpdateApplicationCatalogAsync(arrived, TimeSpan.FromSeconds(10), CancellationToken.None);

        IReadOnlyList<JsonObject> configured = fake.Requests("catalog.configure");
        Assert.Multiple(() =>
        {
            Assert.That(first, Is.True);
            Assert.That(again, Is.True);
            Assert.That(configured, Has.Count.EqualTo(2));
            Assert.That(configured[^1]["applicationCatalog"]?["names"]?.AsArray().Select(static n => (string?)n),
                Is.EqualTo(new[] { "Bloc de notas", "Configuración" }));
        });
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
        // RiskPolicy.Evaluate itself: a song or a page go direct in both modes, and an email or a message to a person
        // ask in normal mode only (decisión del dueño 2026-11-02: Bypass asks nothing).
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
            Assert.That(Confirms("message.send"), Is.EqualTo("[\"normal\"]"));
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

    [Test]
    [NonParallelizable]
    public void AStderrLogThatCannotOpenOrStopsWritingSaysSoOnce()
    {
        string folder = Path.Combine(Path.GetTempPath(), "baxy-app-tests", Guid.NewGuid().ToString("N"));
        string path = Path.Combine(folder, "stderr.log");
        var warnings = new WarningListener();
        System.Diagnostics.Trace.Listeners.Add(warnings);
        try
        {
            // A file where its folder should be: the log cannot open.
            Directory.CreateDirectory(folder);
            File.WriteAllText(Path.Combine(folder, "taken"), "");
            Assert.That(BoundedStandardErrorLog.Open(Path.Combine(folder, "taken", "stderr.log")), Is.Null);
            Assert.That(warnings.Lines, Has.Count.EqualTo(1).And.Some.StartsWith("mind_stderr_log_unavailable"));

            // Another handle locks the file: the write fails and the log ends, said once however many writes follow.
            warnings.Lines.Clear();
            using (BoundedStandardErrorLog log = BoundedStandardErrorLog.Open(path)!)
            using (var other = new FileStream(path, FileMode.Open, FileAccess.ReadWrite, FileShare.ReadWrite | FileShare.Delete))
            {
                other.Lock(0, 1024);
                log.Write("abc"u8);
                log.Write("def"u8);
                other.Unlock(0, 1024);
            }

            Assert.That(warnings.Lines, Has.Count.EqualTo(1).And.Some.StartsWith("mind_stderr_log_stopped"));
            Assert.That(new FileInfo(path).Length, Is.Zero);

            // Nothing on the disk to forget, not even its folder: none is kept.
            Assert.That(BoundedStandardErrorLog.ForgetFiles(Path.Combine(folder, "missing", "stderr.log")), Is.True);
        }
        finally
        {
            System.Diagnostics.Trace.Listeners.Remove(warnings);
            Directory.Delete(folder, recursive: true);
        }
    }

    private sealed class WarningListener : System.Diagnostics.TraceListener
    {
        internal List<string> Lines { get; } = [];

        public override void Write(string? message)
        {
        }

        public override void WriteLine(string? message)
        {
        }

        public override void TraceEvent(System.Diagnostics.TraceEventCache? eventCache, string source,
            System.Diagnostics.TraceEventType eventType, int id, string? format, params object?[]? args)
        {
            if (eventType == System.Diagnostics.TraceEventType.Warning)
            {
                Lines.Add(args is null ? format ?? "" : string.Format(System.Globalization.CultureInfo.InvariantCulture, format ?? "", args));
            }
        }

        public override void TraceEvent(System.Diagnostics.TraceEventCache? eventCache, string source,
            System.Diagnostics.TraceEventType eventType, int id, string? message)
        {
            if (eventType == System.Diagnostics.TraceEventType.Warning)
            {
                Lines.Add(message ?? "");
            }
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

    // Uso 84 (AMD RX 7600, 2026-11-04): a cold start read its prompt prefix in 167.5 s, against the App's fixed budget.
    // Scaled down: a window of 1 s stands for the start's 600 s, and the mind reads its prefix for 3 s, telling each
    // advance. It is waited for, on the one process it started (no retry, nothing killed).
    [Test]
    public async Task AStartWhoseModelKeepsAdvancingIsWaitedForPastItsWindow()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["progress"] = new JsonObject
            {
                ["catalog.configure"] = new JsonObject { ["every"] = 0.25, ["count"] = 12 },
            },
        });
        await using var mind = new MindSidecarClient();
        var clock = System.Diagnostics.Stopwatch.StartNew();

        bool started = await mind.TryStartAsync(
            Task.FromResult(FakeMind.EmptyCatalog), TimeSpan.FromSeconds(1), CancellationToken.None);

        Assert.That(started, Is.True, "a model still advancing was taken for a failed start");
        Assert.That(clock.Elapsed, Is.GreaterThan(TimeSpan.FromSeconds(2.5)));
        Assert.That(mind.IsReady, Is.True);
        Assert.That(fake.Seen.Count(static seen => seen == "catalog.configure"), Is.EqualTo(1));
        Assert.That(fake.LiveProcesses, Has.Count.EqualTo(1));
    }

    // A model that stops advancing still fails at its window, as before.
    [Test]
    public async Task AStartWhoseModelStopsAdvancingFailsAtItsWindow()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["delay"] = new JsonObject { ["catalog.configure"] = 4 },
            ["progress"] = new JsonObject
            {
                ["catalog.configure"] = new JsonObject { ["every"] = 0, ["count"] = 1 },
            },
        });
        await using var mind = new MindSidecarClient();
        var clock = System.Diagnostics.Stopwatch.StartNew();

        bool started = await mind.TryStartAsync(
            Task.FromResult(FakeMind.EmptyCatalog), TimeSpan.FromSeconds(1), CancellationToken.None);

        Assert.That(started, Is.False);
        Assert.That(clock.Elapsed, Is.LessThan(TimeSpan.FromSeconds(3.5)));
    }

    // However long it keeps advancing, a start ends at its safety ceiling.
    [Test]
    public async Task AStartPastItsCeilingFailsEvenWhileItsModelAdvances()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["progress"] = new JsonObject
            {
                ["catalog.configure"] = new JsonObject { ["every"] = 0.2, ["count"] = 100 },
            },
        });
        await using var mind = new MindSidecarClient();
        var clock = System.Diagnostics.Stopwatch.StartNew();

        bool started = await mind.TryStartAsync(
            Task.FromResult(FakeMind.EmptyCatalog), TimeSpan.FromSeconds(1), CancellationToken.None,
            ceiling: TimeSpan.FromSeconds(2.5));

        Assert.That(started, Is.False);
        Assert.That(clock.Elapsed, Is.LessThan(TimeSpan.FromSeconds(5)));
    }

    // Uso-124 (RX 7600 on Vulkan): a turn's request whose model is still reading a long result ended at its fixed 30 s.
    // Scaled down: a window of 1 s stands for the 30 s, and the mind reads for 3 s, telling each advance.
    [Test]
    public async Task ATurnWhoseModelKeepsAdvancingIsWaitedForPastItsWindow()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["progress"] = new JsonObject { ["turn.decide"] = new JsonObject { ["every"] = 0.25, ["count"] = 12 } },
        });
        await using MindSidecarClient mind = await ScaledAsync(TimeSpan.FromSeconds(30));
        var clock = System.Diagnostics.Stopwatch.StartNew();

        MindStep? step = await mind.DecideAsync("hola", null, CancellationToken.None);

        Assert.That(step?.Kind, Is.EqualTo("reply"), "a model still advancing was taken for a dead mind");
        Assert.That(clock.Elapsed, Is.GreaterThan(TimeSpan.FromSeconds(2.5)));
        Assert.That(mind.IsReady, Is.True);
    }

    // A mind that says nothing, or stops saying it advances, is given up on at its window, as before.
    [Test]
    public async Task ATurnWhoseModelStopsAdvancingFailsAtItsWindow()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["progress"] = new JsonObject { ["turn.decide"] = new JsonObject { ["every"] = 0.5, ["count"] = 1 } },
            ["delay"] = new JsonObject { ["turn.decide"] = 0 },
            ["hold"] = new JsonObject { ["turn.continue"] = "nunca" },
        });
        await using MindSidecarClient mind = await ScaledAsync(TimeSpan.FromSeconds(30));
        var clock = System.Diagnostics.Stopwatch.StartNew();

        MindStep? step = await mind.ContinueAsync("{}", false, false, CancellationToken.None);

        Assert.That(step, Is.Null);
        Assert.That(clock.Elapsed, Is.LessThan(TimeSpan.FromSeconds(3)));
        Assert.That(mind.IsReady, Is.False, "a turn past its window takes the mind for lost, as before");
    }

    // However long the model advances, a turn's request ends at its ceiling, past the mind's own (REQUEST_CEILING_S).
    [Test]
    public async Task ATurnPastItsCeilingFailsEvenWhileItsModelAdvances()
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["progress"] = new JsonObject { ["turn.decide"] = new JsonObject { ["every"] = 0.2, ["count"] = 100 } },
        });
        await using MindSidecarClient mind = await ScaledAsync(TimeSpan.FromSeconds(2.5));
        var clock = System.Diagnostics.Stopwatch.StartNew();

        MindStep? step = await mind.DecideAsync("hola", null, CancellationToken.None);

        Assert.That(step, Is.Null);
        Assert.That(clock.Elapsed, Is.GreaterThan(TimeSpan.FromSeconds(2)));
        Assert.That(clock.Elapsed, Is.LessThan(TimeSpan.FromSeconds(5)));
    }

    [Test]
    public void TheTurnsCeilingLeavesTheMindItsOwnFirst()
    {
        // The mind ends a request at 24 s without an advance and, until its catalog.ready says its own ceiling, 120 s in
        // all (LlmServer): the App, always after it.
        Assert.That(MindSidecarClient.TurnRequestTimeout, Is.EqualTo(TimeSpan.FromSeconds(30)));
        Assert.That(MindSidecarClient.TurnRequestCeiling, Is.GreaterThan(TimeSpan.FromSeconds(120)));
    }

    // Revisión PCR1 (A2, A3): the mind's ceiling for a turn's request is what its server may have to read (468 s on the
    // RX 7600, LlmServer.ceiling_s), past the App's fixed 126 s: the App gave up on a request the mind still served. It
    // comes with catalog.ready, and the App's ceiling is that with the margin its window has over the mind's 24 s; a mind
    // that does not say it leaves the App's own.
    [TestCase(468.0, 474.0)]
    // int-staging-1: the longest the mind says (LlmServer.REQUEST_MOST_S), and one past what a start may take.
    [TestCase(2694.0, 2700.0)]
    [TestCase(7536.0, 126.0)]
    [TestCase(null, 126.0)]
    public async Task TheTurnsCeilingFollowsTheMindsOwn(double? mindSays, double appWaits)
    {
        using var fake = new FakeMind();
        var ready = new JsonObject { ["type"] = "catalog.ready", ["count"] = 0 };
        if (mindSays is { } seconds)
        {
            ready["ceiling_s"] = seconds;
        }

        fake.Script(new JsonObject { ["reply"] = new JsonObject { ["catalog.configure"] = ready } });
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();

        Assert.That(mind.TurnCeiling, Is.EqualTo(TimeSpan.FromSeconds(appWaits)));
    }

    // Uso-124: the mind says whether its notices are slow with each one (Mind.notices_are_slow).
    [TestCase(true)]
    [TestCase(false)]
    public async Task TheClientKeepsWhetherNoticesAreSlow(bool slow)
    {
        using var fake = new FakeMind();
        fake.Script(new JsonObject
        {
            ["reply"] = new JsonObject
            {
                ["turn.notice"] = new JsonObject { ["type"] = "turn.notice.result", ["notice"] = "Busco.", ["slow"] = slow },
            },
        });
        await using MindSidecarClient mind = await FakeMind.StartClientAsync();

        Assert.That(await mind.NoticeAsync(CancellationToken.None), Is.EqualTo("Busco."));
        Assert.That(mind.NoticesAreSlow, Is.EqualTo(slow));
    }

    private static async Task<MindSidecarClient> ScaledAsync(TimeSpan ceiling)
    {
        var mind = new MindSidecarClient { TurnWindow = TimeSpan.FromSeconds(1), TurnCeiling = ceiling };
        Assert.That(await mind.TryStartAsync(
            Task.FromResult(FakeMind.EmptyCatalog), TimeSpan.FromSeconds(30), CancellationToken.None), Is.True);
        return mind;
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
