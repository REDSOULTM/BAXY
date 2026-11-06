using System.Buffers.Binary;
using System.Security.Cryptography;
using System.Text.Json;
using Baxy.Providers.Windows.Capture;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Uso-108, what the agent-desktop study found in BAXY's receipts: a plain key told by its window's image (B2), vision of the
/// bytes it already described (F31), the view after an act paired by more than an id, and a killed Core's temporary.
/// </summary>
[TestFixture]
public sealed class RecibosUso108Tests
{
    private const nint Front = 0x1234;

    private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();

    private sealed class NoProcessRunner : IExternalProcessRunner
    {
        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout, CancellationToken cancellationToken) =>
            throw new InvalidOperationException("no process in this test");
    }

    // A white window of 4 by 4 cells, with one cell black for each cell named (MotionCell pixels square).
    private static VisibleControlSurface.CapturedWindow Image(nint window, params int[] blackCells)
    {
        const int cell = VisibleControlSurface.MotionCell;
        const int side = cell * 4;
        const int header = 54;
        byte[] bmp = new byte[header + (side * side * 4)];
        bmp[0] = (byte)'B';
        bmp[1] = (byte)'M';
        BinaryPrimitives.WriteInt32LittleEndian(bmp.AsSpan(10), header);
        BinaryPrimitives.WriteInt32LittleEndian(bmp.AsSpan(14), 40);
        BinaryPrimitives.WriteInt32LittleEndian(bmp.AsSpan(18), side);
        BinaryPrimitives.WriteInt32LittleEndian(bmp.AsSpan(22), -side);
        BinaryPrimitives.WriteInt16LittleEndian(bmp.AsSpan(26), 1);
        BinaryPrimitives.WriteInt16LittleEndian(bmp.AsSpan(28), 32);
        bmp.AsSpan(header).Fill(255);
        foreach (int black in blackCells)
        {
            for (int y = 0; y < cell; y++)
            {
                int row = header + ((((black / 4 * cell) + y) * side) + (black % 4 * cell)) * 4;
                bmp.AsSpan(row, cell * 4).Clear();
            }
        }

        return new VisibleControlSurface.CapturedWindow(window, bmp, 0, 0, side, side, Convert.ToHexString(SHA256.HashData(bmp)));
    }

    // The images a window shows, in the order they are read; the last one stays.
    private static KeySurfaceWitness Shows(
        out List<nint> reads, Func<nint, long, bool>? touched, params VisibleControlSurface.CapturedWindow[] images)
    {
        var read = new List<nint>();
        reads = read;
        return new KeySurfaceWitness(
            (window, _, _) =>
            {
                read.Add(window);
                return ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(images[Math.Min(read.Count - 1, images.Length - 1)]);
            },
            touched ?? ((_, _) => false));
    }

    private static WindowsDesktopInteractionAdapter Adapter(KeySurfaceWitness surface, IViewedFields? fields = null, FakeDesktopKeyboard? keyboard = null)
    {
        keyboard ??= new FakeDesktopKeyboard();
        keyboard.Holding.Add(Front);
        keyboard.Holding.Add(4660);
        return new WindowsDesktopInteractionAdapter(
            new NoProcessRunner(), "folder.ps1", "file.ps1", "select.ps1", "keys.ps1", keyboard, fields, new FakeFieldMessages())
        {
            KeySurface = surface,
        };
    }

    private static bool Says(ExternalCapabilityReceipt receipt) =>
        receipt.Result!.Value.TryGetProperty("surfaceChanged", out JsonElement changed) && changed.GetBoolean();

    [Test]
    public async Task APlainKeyThatChangedTheWindowSaysSo()
    {
        WindowsDesktopInteractionAdapter adapter = Adapter(Shows(out _, null, Image(Front), Image(Front, 5)));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.key.press", Json("""{"key":"page_down"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(Says(receipt), Is.True, "the slide moved: one receipt proves it, with no other look");
        });
    }

    [Test]
    public async Task CounterCaseAKeyThatChangedNothingSaysNothing()
    {
        WindowsDesktopInteractionAdapter adapter = Adapter(Shows(out List<nint> reads, null, Image(Front)));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.key.press", Json("""{"key":"page_down"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(Says(receipt), Is.False, "absence: never surfaceChanged false");
            Assert.That(receipt.Result!.Value.TryGetProperty("surfaceChanged", out _), Is.False);
            Assert.That(reads, Has.Count.EqualTo(1 + KeySurfaceWitness.Looks), "no motion probes on a key that changed nothing");
        });
    }

    // What moves by itself is no proof: cell 5 is a video, and differs again in the probes after the key.
    [Test]
    public async Task CounterCaseOnlyACellThatMovesByItselfSaysNothing()
    {
        WindowsDesktopInteractionAdapter adapter = Adapter(Shows(
            out _, null, Image(Front), Image(Front, 5), Image(Front), Image(Front, 5)));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.key.press", Json("""{"key":"page_down"}"""), CancellationToken.None);

        Assert.That(Says(receipt), Is.False);
    }

    // A video in cell 5 and the slide in cell 10. Measured live: told by cells, a bar crossing into new ones read as the
    // key's. A window that keeps moving claims nothing: the key stays unverified.
    [Test]
    public async Task CounterCaseAWindowThatKeepsMovingClaimsNothingEvenBesideARealChange()
    {
        WindowsDesktopInteractionAdapter adapter = Adapter(Shows(
            out _, null, Image(Front), Image(Front, 5, 10), Image(Front, 10), Image(Front, 5, 10)));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.key.press", Json("""{"key":"page_down"}"""), CancellationToken.None);

        Assert.That(Says(receipt), Is.False);
    }

    // Live with real keys: an arrow taken by a window that animates, drawn and so unseen by the tree, read «same».
    [Test]
    public async Task AKeyInANamedWindowThatKeepsMovingIsNotToldTheWindowIsTheSame()
    {
        WindowsDesktopInteractionAdapter adapter = Adapter(Shows(
            out _, null, [Image(4660), Image(4660, 5), Image(4660, 6), Image(4660, 7)]), new SameView());

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.key.press", Json("""{"key":"page_down","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(Says(receipt), Is.False);
            Assert.That(receipt.Result!.Value.GetProperty("after").GetProperty("sameListed").GetBoolean(), Is.True);
        });
    }

    // A slide that fades in: it differs at the first look, keeps changing, and settles in time: the key's.
    [Test]
    public async Task AnAnswerThatAnimatesAndSettlesCounts()
    {
        List<VisibleControlSurface.CapturedWindow> images = [Image(Front), Image(Front, 5)];
        WindowsDesktopInteractionAdapter adapter = Adapter(Shows(out _, null, [.. images, Image(Front, 5, 10)]));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.key.press", Json("""{"key":"page_down"}"""), CancellationToken.None);

        Assert.That(Says(receipt), Is.True);
    }

    [Test]
    public async Task CounterCaseThePersonsOwnInputEndsTheProof()
    {
        WindowsDesktopInteractionAdapter adapter = Adapter(Shows(out _, (_, _) => true, Image(Front), Image(Front, 5)));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.key.press", Json("""{"key":"page_down"}"""), CancellationToken.None);

        Assert.That(Says(receipt), Is.False);
    }

    // A screen copy of a window that lost the front shows what covers it.
    [Test]
    public async Task CounterCaseAWindowThatLostTheFrontProvesNothing()
    {
        var keyboard = new FakeDesktopKeyboard();
        WindowsDesktopInteractionAdapter adapter = Adapter(Shows(out _, null, Image(Front), Image(Front, 5)), keyboard: keyboard);
        keyboard.Holding.Clear();

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.key.press", Json("""{"key":"page_down"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(Says(receipt), Is.False);
        });
    }

    // Review of batch 2 (B1): a window behind becomes active for the key and inactive again after it: caption, focus ring and
    // selection colour differ and stay still, so a key that did nothing read as changed. Nothing is claimed there, and the
    // tree alone cannot say «the window did not change» of it either: only what it lists.
    [Test]
    public async Task AKeyToAWindowBehindClaimsNothingFromItsImage()
    {
        var keyboard = new FakeDesktopKeyboard();
        WindowsDesktopInteractionAdapter adapter = new(
            new NoProcessRunner(), "folder.ps1", "file.ps1", "select.ps1", "keys.ps1", keyboard, new SameView(), new FakeFieldMessages())
        {
            KeySurface = Shows(out List<nint> reads, null, Image(4660), Image(4660, 5)),
        };

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.key.press", Json("""{"key":"page_down","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(keyboard.Fronted, Is.EqualTo(new nint[] { 4660 }), "it was behind");
            Assert.That(Says(receipt), Is.False);
            Assert.That(reads, Is.Empty, "no image of it is compared");
            JsonElement after = receipt.Result!.Value.GetProperty("after");
            Assert.That(after.TryGetProperty("same", out _), Is.False, after.GetRawText());
            Assert.That(after.GetProperty("sameListed").GetBoolean(), Is.True);
        });
    }

    // Review of batch 2 (I1): a seconds counter ticks once inside the looks; the next tick comes up to 1 s later, past the
    // 600 ms of the click's probes, so its cell was never marked as moving and a key that did nothing read as changed.
    [Test]
    public async Task CounterCaseACellThatTicksOnceASecondIsNoProof()
    {
        WindowsDesktopInteractionAdapter adapter = Adapter(Shows(
            out _, null, Image(Front), Image(Front, 5), Image(Front, 5), Image(Front, 5), Image(Front)));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.key.press", Json("""{"key":"page_down"}"""), CancellationToken.None);

        Assert.That(Says(receipt), Is.False);
    }

    // A shortcut has its own witness, a copy its clipboard, a text its read-back: only plain keys are looked at.
    [TestCase("ctrl_s")]
    [TestCase("ctrl_c")]
    public async Task CounterCaseAShortcutOrACopyIsNotLookedAt(string key)
    {
        WindowsDesktopInteractionAdapter adapter = Adapter(Shows(out List<nint> reads, null, Image(Front), Image(Front, 5)));

        _ = await adapter.InvokeAsync("input.key.press", Json($$"""{"key":"{{key}}"}"""), CancellationToken.None);

        Assert.That(reads, Is.Empty);
    }

    // hondo 15, note 5: «la ventana no cambió» told of a slide that advanced with the same tree. As the click (C67): the
    // tree says only that what it lists is the same.
    [Test]
    public async Task AKeyInANamedWindowWhoseImageChangedIsNotToldTheWindowIsTheSame()
    {
        var fields = new SameView();
        WindowsDesktopInteractionAdapter adapter = Adapter(Shows(out _, null, Image(4660), Image(4660, 5)), fields);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.key.press", Json("""{"key":"page_down","window":4660}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(Says(receipt), Is.True);
            JsonElement after = receipt.Result!.Value.GetProperty("after");
            Assert.That(after.TryGetProperty("same", out _), Is.False, after.GetRawText());
            Assert.That(after.GetProperty("sameListed").GetBoolean(), Is.True);
        });
    }

    [Test]
    public async Task CounterCaseAKeyInANamedWindowThatChangedNothingKeepsTheSame()
    {
        WindowsDesktopInteractionAdapter adapter = Adapter(Shows(out _, null, Image(4660)), new SameView());

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.key.press", Json("""{"key":"page_down","window":4660}"""), CancellationToken.None);

        Assert.That(receipt.Result!.Value.GetProperty("after").GetProperty("same").GetBoolean(), Is.True);
    }

    // hondo 11 finding 4: the worker saw the focus go to the field written; the receipt says it, only then.
    [TestCase(true)]
    [TestCase(false)]
    public async Task AFieldWrittenThatTookTheFocusSaysSo(bool moved)
    {
        string answer = "{\"ok\":true,\"error\":\"\",\"kind\":\"Edit\",\"className\":\"\",\"nativeHwnd\":0,\"method\":\"setvalue\",\"delivered\":true"
            + (moved ? ",\"focusMoved\":true}" : "}");
        var adapter = new WindowsDesktopInteractionAdapter(
            new NoProcessRunner(), "folder.ps1", "file.ps1", "select.ps1", "keys.ps1", new FakeDesktopKeyboard(), new SameView(answer),
            new FakeFieldMessages());

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.text.type", Json("""{"text":"mouse","window":4660,"index":3}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result!.Value.TryGetProperty("focusMoved", out _), Is.EqualTo(moved));
        });
    }

    private sealed class SameView(string? field = null) : IViewedFields
    {
        public bool TryViewedField(int index, out nint window, out string controlId)
        {
            window = 4660;
            controlId = "4.2." + index;
            return true;
        }

        public ValueTask<JsonDocument?> FieldAsync(
            nint window, string controlId, string? text, bool replace, CancellationToken cancellationToken) =>
            ValueTask.FromResult<JsonDocument?>(field is null ? null : JsonDocument.Parse(field));

        public ValueTask<JsonDocument?> EntryAsync(nint window, string controlId, string text, CancellationToken cancellationToken) =>
            ValueTask.FromResult<JsonDocument?>(null);

        public ValueTask<JsonElement?> AfterActAsync(nint window, CancellationToken cancellationToken) =>
            ValueTask.FromResult<JsonElement?>(Json("""{"same":true}"""));
    }

    // ---------------------------------------------------------------- a click where the pointer is

    private sealed class ClickRunner : IExternalProcessRunner
    {
        public ValueTask<ExternalProcessResult> RunAsync(
            string executable, IReadOnlyList<string> arguments, TimeSpan timeout, CancellationToken cancellationToken) =>
            ValueTask.FromResult(new ExternalProcessResult(0,
                """{"version":1,"ok":true,"effectObserved":true,"error":"","pointerAction":"click"}""", string.Empty));
    }

    private static WindowsDesktopInteractionAdapter PointerAdapter(Func<string?> under) =>
        new(new ClickRunner(), "folder.ps1", "file.ps1", "select.ps1", Path.Combine(AppContext.BaseDirectory, "DesktopKeyPress.ps1"), new FakeDesktopKeyboard())
        {
            PointerUnder = under,
        };

    [Test]
    public async Task AClickWhereThePointerIsSaysWhatWasUnderIt()
    {
        ExternalCapabilityReceipt receipt = await PointerAdapter(static () => "Informe.docx (WINWORD)").InvokeAsync(
            "input.pointer.control", Json("""{"action":"click"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result!.Value.GetProperty("under").GetString(), Is.EqualTo("Informe.docx (WINWORD)"));
        });
    }

    [Test]
    public async Task CounterCaseAnUnreadWindowOrAMoveSaysNothingOfIt()
    {
        ExternalCapabilityReceipt unread = await PointerAdapter(static () => null).InvokeAsync(
            "input.pointer.control", Json("""{"action":"click"}"""), CancellationToken.None);
        bool asked = false;
        ExternalCapabilityReceipt moved = await PointerAdapter(() =>
        {
            asked = true;
            return "x";
        }).InvokeAsync("input.pointer.control", Json("""{"action":"move_center"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(unread.Result!.Value.TryGetProperty("under", out _), Is.False);
            Assert.That(asked, Is.False, "only a click");
            Assert.That(moved.Result!.Value.TryGetProperty("under", out _), Is.False);
        });
    }

    // ---------------------------------------------------------------- bare names

    // CreateProcess looks in the parent's current directory before the system's: a planted powershell.exe (here a copy of
    // whoami.exe, which answers an unknown argument with an error) must not be what starts.
    [Test]
    [NonParallelizable]
    public async Task ABareNameNeverRunsAFilePlantedInTheCurrentDirectory()
    {
        string folder = TemporaryFolder();
        string current = Environment.CurrentDirectory;
        // A session's shell may set this one, which hides the current directory from the search; a product never has it.
        string? hidden = Environment.GetEnvironmentVariable("NoDefaultCurrentDirectoryInExePath");
        try
        {
            File.Copy(Path.Combine(Environment.SystemDirectory, "whoami.exe"), Path.Combine(folder, "powershell.exe"));
            Environment.SetEnvironmentVariable("NoDefaultCurrentDirectoryInExePath", null);
            Environment.CurrentDirectory = folder;

            ExternalProcessResult run = await new ExternalProcessRunner().RunAsync(
                "powershell.exe", ["-NoProfile", "-NonInteractive", "-Command", "'la-de-verdad'"],
                TimeSpan.FromSeconds(60), CancellationToken.None);

            Assert.That(run.Output.Trim(), Is.EqualTo("la-de-verdad"));
        }
        finally
        {
            Environment.CurrentDirectory = current;
            Environment.SetEnvironmentVariable("NoDefaultCurrentDirectoryInExePath", hidden);
            Directory.Delete(folder, recursive: true);
        }
    }

    [Test]
    public void ABareNameResolvesToTheSystemThenToAbsoluteFoldersOfPath()
    {
        string folder = TemporaryFolder();
        try
        {
            string alias = Path.Combine(folder, "herramienta.exe");
            File.WriteAllText(alias, "x");
            string system = Path.Combine(Environment.SystemDirectory, "herramienta.exe");
            Assert.Multiple(() =>
            {
                Assert.That(SystemExecutable.Resolve("powershell.exe", null), Is.EqualTo(SystemExecutable.PowerShell));
                Assert.That(File.Exists(SystemExecutable.PowerShell), Is.True, "the path the worker starts by");
                Assert.That(SystemExecutable.Resolve("netsh.exe", null), Is.EqualTo(Path.Combine(Environment.SystemDirectory, "netsh.exe")));
                Assert.That(SystemExecutable.Resolve("herramienta.exe", @"relativa;.;" + folder), Is.EqualTo(alias), "winget's alias");
                Assert.That(SystemExecutable.Resolve("herramienta.exe", @"relativa;."), Is.EqualTo(system), "found nowhere: a missing file");
                Assert.That(SystemExecutable.Resolve(alias, null), Is.EqualTo(alias), "a full path stays");
            });
        }
        finally
        {
            Directory.Delete(folder, recursive: true);
        }
    }

    // D4 (hondo 14 finding 8): forty tests of the worker's text Assume its script is next to them, and a skip passes: a
    // build that stopped copying it would be green with none of them run.
    [TestCase("DesktopUiaWorker.ps1")]
    [TestCase("DesktopKeyPress.ps1")]
    public void TheScriptsTheWorkerTestsAssumeAreCopiedNextToThem(string script) =>
        Assert.That(File.Exists(Path.Combine(AppContext.BaseDirectory, script)), Is.True);

    // ---------------------------------------------------------------- the view after an act

    private static List<WindowsVisibleControlAdapter.ViewControl> Rows(params (string Id, string Name)[] rows) =>
        [.. rows.Select((row, index) => new WindowsVisibleControlAdapter.ViewControl
        {
            Index = index, Kind = "ListItem", Name = row.Name, Id = row.Id,
        })];

    private static string[] Listed(JsonElement difference, string name) =>
        difference.TryGetProperty(name, out JsonElement list)
            ? [.. list.EnumerateArray().Select(static item => item.GetString()!)]
            : [];

    // agent-desktop identity-mutation.json: rows of a list keep their place's id and name another file.
    [Test]
    public void DeletingARowOfAListKeyedByPlaceTellsTheRightRowGone()
    {
        JsonElement difference = WindowsVisibleControlAdapter.ViewDifference(
            Rows(("1", "a"), ("2", "b"), ("3", "c"), ("4", "d"), ("5", "e")), "Carpeta",
            Rows(("1", "a"), ("2", "c"), ("3", "d"), ("4", "e")), [], "Carpeta");

        Assert.Multiple(() =>
        {
            Assert.That(Listed(difference, "gone"), Is.EqualTo(new[] { "ListItem «b»" }), difference.GetRawText());
            Assert.That(Listed(difference, "changed"), Is.Empty);
            Assert.That(Listed(difference, "moved"), Has.Length.EqualTo(3));
        });
    }

    [Test]
    public void CounterCaseARenamedControlKeepingItsIdIsStillChanged()
    {
        JsonElement difference = WindowsVisibleControlAdapter.ViewDifference(
            Rows(("1", "a"), ("2", "b")), "Carpeta", Rows(("1", "a"), ("2", "otro")), [], "Carpeta");

        Assert.Multiple(() =>
        {
            Assert.That(Listed(difference, "changed"), Is.EqualTo(new[] { "[1] ListItem «otro»" }), difference.GetRawText());
            Assert.That(Listed(difference, "gone"), Is.Empty);
            Assert.That(Listed(difference, "appeared"), Is.Empty);
        });
    }

    // Twins: one row of two with the same name goes; the one with the id that stayed is the one kept.
    [Test]
    public void CounterCaseOfTwoTwinsTheIdDecides()
    {
        JsonElement difference = WindowsVisibleControlAdapter.ViewDifference(
            Rows(("1", "x"), ("2", "x"), ("3", "y")), "Carpeta", Rows(("2", "x"), ("3", "y")), [], "Carpeta");

        Assert.Multiple(() =>
        {
            Assert.That(Listed(difference, "gone"), Is.EqualTo(new[] { "ListItem «x»" }));
            Assert.That(Listed(difference, "moved"), Is.EqualTo(new[] { "[0] ListItem «x» was [1]", "[1] ListItem «y» was [2]" }));
        });
    }

    // ---------------------------------------------------------------- captures

    private sealed class Frames(params ScreenshotFrame[] frames) : IScreenshotPlatform
    {
        private int _taken;

        private ScreenshotFrame Next() => frames[Math.Min(_taken++, frames.Length - 1)];

        public ScreenshotFrame CaptureVirtualScreen() => Next();

        public ScreenshotFrame CaptureActiveWindow() => Next();
    }

    private static ScreenshotFrame Frame(byte shade) => new(2, 1, [shade, shade, shade, 255, shade, shade, shade, 255]);

    private static string TemporaryFolder()
    {
        string path = Path.Combine(Path.GetTempPath(), "baxy-recibos-tests", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(path);
        return path;
    }

    // hondo 14 finding 5: a Core killed between the write and the move leaves a whole screen under a temporary name.
    [Test]
    public async Task AnOrphanedTemporaryOfAKilledCoreIsSweptAndOneInFlightStays()
    {
        string folder = TemporaryFolder();
        try
        {
            string orphan = Path.Combine(folder, ".capture_" + Guid.NewGuid().ToString("N") + ".tmp");
            string inFlight = Path.Combine(folder, ".capture_" + Guid.NewGuid().ToString("N") + ".tmp");
            string foreign = Path.Combine(folder, "other.tmp");
            foreach (string file in new[] { orphan, inFlight, foreign })
                File.WriteAllText(file, "x");
            File.SetLastWriteTimeUtc(orphan, DateTime.UtcNow - WindowsScreenshotProvider.OrphanedTemporaryAge - TimeSpan.FromSeconds(5));
            File.SetLastWriteTimeUtc(foreign, DateTime.UtcNow.AddDays(-3));
            var provider = new WindowsScreenshotProvider(folder, new Frames(Frame(40)), TimeProvider.System);

            _ = await provider.CaptureAsync(CancellationToken.None);

            Assert.Multiple(() =>
            {
                Assert.That(File.Exists(orphan), Is.False, "private data outside the retention limit");
                Assert.That(File.Exists(inFlight), Is.True, "a write under 60 s old may be another call's");
                Assert.That(File.Exists(foreign), Is.True, "only the capture's own temporary name");
            });
        }
        finally
        {
            Directory.Delete(folder, recursive: true);
        }
    }

    // ---------------------------------------------------------------- vision

    private sealed class CountingVision(params string[] descriptions) : HttpMessageHandler
    {
        internal int Asked { get; private set; }

        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            string description = descriptions[Math.Min(Asked++, descriptions.Length - 1)];
            string body = JsonSerializer.Serialize(new { choices = new[] { new { message = new { content = description } } } });
            return Task.FromResult(new HttpResponseMessage(System.Net.HttpStatusCode.OK) { Content = new StringContent(body) });
        }
    }

    [Test]
    [NonParallelizable]
    public async Task VisionOfASecondCaptureWithTheSameBytesSparesTheServer()
    {
        string folder = TemporaryFolder();
        string? endpoint = Environment.GetEnvironmentVariable("BAXY_VISION_ENDPOINT");
        string? model = Environment.GetEnvironmentVariable("BAXY_VISION_MODEL");
        try
        {
            Environment.SetEnvironmentVariable("BAXY_VISION_ENDPOINT", "http://127.0.0.1:9/v1/chat/completions");
            Environment.SetEnvironmentVariable("BAXY_VISION_MODEL", "vision-test");
            string a = "capture_" + new string('a', 32), b = "capture_" + new string('b', 32), c = "capture_" + new string('c', 32);
            byte[] picture = PngBmp(40), another = PngBmp(90);
            File.WriteAllBytes(Path.Combine(folder, a + ".bmp"), picture);
            File.WriteAllBytes(Path.Combine(folder, b + ".bmp"), picture);
            File.WriteAllBytes(Path.Combine(folder, c + ".bmp"), another);
            var vision = new CountingVision("una ventana con un botón", "otra forma de decirlo", "una ventana distinta");
            using var http = new HttpClient(vision);
            using var adapter = new CaptureVisionAdapter(folder, http);
            Task<ExternalCapabilityReceipt> Ask(string id) => adapter.InvokeAsync(
                "vision.describe", Json($$"""{"captureId":"{{id}}"}"""), CancellationToken.None).AsTask();

            ExternalCapabilityReceipt first = await Ask(a);
            ExternalCapabilityReceipt same = await Ask(b);
            ExternalCapabilityReceipt other = await Ask(c);
            ExternalCapabilityReceipt sameId = await Ask(a);

            Assert.Multiple(() =>
            {
                Assert.That(same.Result!.Value.GetProperty("description").GetString(), Is.EqualTo("una ventana con un botón"));
                Assert.That(same.Result!.Value.GetProperty("captureId").GetString(), Is.EqualTo(b));
                Assert.That(other.Result!.Value.GetProperty("description").GetString(), Is.EqualTo("otra forma de decirlo"));
                Assert.That(first.Result!.Value.GetProperty("description").GetString(), Is.EqualTo("una ventana con un botón"));
                Assert.That(sameId.Result!.Value.GetProperty("description").GetString(), Is.EqualTo("una ventana con un botón"));
                Assert.That(vision.Asked, Is.EqualTo(2), "only the two images");
            });
        }
        finally
        {
            Environment.SetEnvironmentVariable("BAXY_VISION_ENDPOINT", endpoint);
            Environment.SetEnvironmentVariable("BAXY_VISION_MODEL", model);
            Directory.Delete(folder, recursive: true);
        }
    }

    private static byte[] PngBmp(byte shade)
    {
        byte[] bmp = new byte[54 + 4];
        bmp[0] = (byte)'B';
        bmp[1] = (byte)'M';
        BinaryPrimitives.WriteInt32LittleEndian(bmp.AsSpan(2), bmp.Length);
        BinaryPrimitives.WriteInt32LittleEndian(bmp.AsSpan(10), 54);
        BinaryPrimitives.WriteInt32LittleEndian(bmp.AsSpan(14), 40);
        BinaryPrimitives.WriteInt32LittleEndian(bmp.AsSpan(18), 1);
        BinaryPrimitives.WriteInt32LittleEndian(bmp.AsSpan(22), 1);
        BinaryPrimitives.WriteInt16LittleEndian(bmp.AsSpan(26), 1);
        BinaryPrimitives.WriteInt16LittleEndian(bmp.AsSpan(28), 32);
        BinaryPrimitives.WriteInt32LittleEndian(bmp.AsSpan(34), 4);
        bmp[54] = bmp[55] = bmp[56] = shade;
        bmp[57] = 255;
        return bmp;
    }
}
