using System.Text.Json;
using Baxy.Providers.Windows.Capture;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Perception and click of the computer-use engine over the persistent UIA
/// worker seam (documentacion/computer-use/CONTRATO_VISTA_ACCION.md §1, §2):
/// the adapter's rules are exercised with scripted worker answers, never with a
/// real window.
/// </summary>
[TestFixture]
public sealed class ComputerUsePerceptionTests
{
    private static JsonElement Json(string value) => JsonDocument.Parse(value).RootElement.Clone();

    // The control that has the keyboard reaches the view as the worker read it (the model reads it as «Foco:»).
    [Test]
    public async Task TheViewCarriesTheFocusedControlTheWorkerRead()
    {
        // A handle no window has: nothing on the desktop is read or moved.
        const long front = 0x7FFF_0F3A;
        var worker = new ScriptedUiaWorker(
            "{\"ok\":true,\"error\":\"\",\"hwnd\":" + front + ",\"window\":\"Trabajo\",\"controls\":[" +
            "{\"kind\":\"Button\",\"name\":\"Ajustes\",\"id\":\"4.1\",\"state\":\"\",\"value\":null,\"rect\":null," +
            "\"repeated\":0},{\"kind\":\"Edit\",\"name\":\"main Input\",\"id\":\"4.2\",\"state\":\"\"," +
            "\"value\":\"hola\",\"rect\":null,\"repeated\":0}],\"controlCount\":2," +
            "\"focused\":{\"kind\":\"Edit\",\"name\":\"main Input\",\"value\":\"hola\",\"i\":1}}");
        var adapter = new WindowsVisibleControlAdapter(worker, null, null,
            requestedWindow: (_, _) => ValueTask.FromResult((nint)front));

        ExternalCapabilityReceipt view = await adapter.InvokeAsync(
            "input.visible.controls", Json("""{"application":"el navegador"}"""), CancellationToken.None);

        JsonElement focused = view.Result!.Value.GetProperty("window").GetProperty("focused");
        Assert.Multiple(() =>
        {
            Assert.That(view.Verified, Is.True);
            Assert.That(focused.GetProperty("name").GetString(), Is.EqualTo("main Input"));
            Assert.That(focused.GetProperty("value").GetString(), Is.EqualTo("hola"));
            Assert.That(focused.GetProperty("i").GetInt32(), Is.EqualTo(1), "the index it clicks by in this view");
        });
    }

    [Test]
    public async Task VisibleButtonClickRequiresUiaPostreadThatTheControlChanged()
    {
        var worker = new ScriptedUiaWorker(
            "{\"version\":2,\"ok\":true,\"effectObserved\":true," +
            "\"error\":\"\",\"name\":\"Aceptar\",\"controlIdentity\":\"1.2.3\"," +
            "\"absentOrDisabled\":true,\"authority\":\"windows_uia_or_win32_button_postread\"}");
        var adapter = new WindowsVisibleControlAdapter(worker, null, null);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"aceptar"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.Result?.GetProperty("absentOrDisabled").GetBoolean(), Is.True);
            Assert.That(worker.Commands[^1], Does.Contain("\"cmd\":\"click\""));
            Assert.That(worker.Commands[^1], Does.Contain("\"aliases\":[\"aceptar\"]"), "auditoría P3: the label as written");
        });
    }

    [Test]
    public async Task VisibleClickAcceptsASelectedOrToggledControlPostread()
    {
        var selected = new ScriptedUiaWorker(
            "{\"version\":2,\"ok\":true,\"effectObserved\":true,\"error\":\"\",\"name\":\"Library\"," +
            "\"controlIdentity\":\"1.2.3\",\"absentOrDisabled\":false,\"selected\":true,\"toggled\":false," +
            "\"surfaceChanged\":false,\"cascadeStage\":\"uia\"}");
        var toggled = new ScriptedUiaWorker(
            "{\"version\":2,\"ok\":true,\"effectObserved\":true,\"error\":\"\",\"name\":\"Modo avión\"," +
            "\"controlIdentity\":\"1.2.4\",\"absentOrDisabled\":false,\"selected\":false,\"toggled\":true," +
            "\"surfaceChanged\":false,\"cascadeStage\":\"uia\"}");

        ExternalCapabilityReceipt first = await new WindowsVisibleControlAdapter(selected, null, null).InvokeAsync(
            "input.visible.click", Json("""{"label":"Library"}"""), CancellationToken.None);
        ExternalCapabilityReceipt second = await new WindowsVisibleControlAdapter(toggled, null, null).InvokeAsync(
            "input.visible.click", Json("""{"label":"Modo avión"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(first.Verified, Is.True);
            Assert.That(first.Result?.GetProperty("selected").GetBoolean(), Is.True);
            Assert.That(second.Verified, Is.True);
            Assert.That(second.Result?.GetProperty("toggled").GetBoolean(), Is.True);
        });
    }

    [Test]
    public async Task VisibleClickCascadeSkipsOcrAndVisionWhenUiaFindsTheControl()
    {
        var worker = new ScriptedUiaWorker(
            "{\"version\":2,\"ok\":true,\"effectObserved\":true,\"error\":\"\",\"name\":\"Aceptar\"," +
            "\"controlIdentity\":\"1.2.3\",\"absentOrDisabled\":true,\"selected\":false,\"surfaceChanged\":false}");
        var ocr = new CountingLocator("ocr", hit: true);
        var vision = new CountingLocator("vision", hit: true);
        var adapter = new WindowsVisibleControlAdapter(worker, ocr, vision);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"aceptar"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(ocr.Calls, Is.Zero);
            Assert.That(vision.Calls, Is.Zero);
        });
    }

    [Test]
    public async Task VisibleClickCascadeUsesOcrWhenUiaExposesNothing()
    {
        var worker = new ScriptedUiaWorker(
            "{\"version\":2,\"ok\":false,\"effectObserved\":false,\"error\":\"visible_button_not_found\"," +
            "\"name\":\"\",\"controlIdentity\":\"\",\"absentOrDisabled\":false}");
        var ocr = new CountingLocator("ocr", hit: true);
        var vision = new CountingLocator("vision", hit: true);
        var adapter = new WindowsVisibleControlAdapter(worker, ocr, vision);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"Library"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("cascadeStage").GetString(), Is.EqualTo("ocr"));
            Assert.That(ocr.Calls, Is.EqualTo(1));
            Assert.That(vision.Calls, Is.Zero);
        });
    }

    [Test]
    public async Task VisibleClickCascadeUsesVisionOnlyAfterUiaAndOcrMiss()
    {
        var worker = new ScriptedUiaWorker(
            "{\"version\":2,\"ok\":false,\"effectObserved\":false,\"error\":\"visible_button_not_found\"," +
            "\"name\":\"\",\"controlIdentity\":\"\",\"absentOrDisabled\":false}");
        var ocr = new CountingLocator("ocr", hit: false);
        var vision = new CountingLocator("vision", hit: true);
        var adapter = new WindowsVisibleControlAdapter(worker, ocr, vision);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"Library"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("cascadeStage").GetString(), Is.EqualTo("vision"));
            Assert.That(ocr.Calls, Is.EqualTo(1));
            Assert.That(vision.Calls, Is.EqualTo(1));
        });
    }

    [Test]
    public async Task VisibleClickByIndexWithoutAViewIsRefusedBeforeAnyEffect()
    {
        var worker = new ScriptedUiaWorker("{\"ok\":true}");
        var adapter = new WindowsVisibleControlAdapter(worker, null, null);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"Biblioteca","index":3}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("visible_control_identity_stale"));
            Assert.That(worker.Commands, Is.Empty);
        });
    }

    [Test]
    public async Task AWorkerThatDoesNotAnswerLeavesAnHonestClickReceipt()
    {
        var worker = new ScriptedUiaWorker(answers: []);
        var adapter = new WindowsVisibleControlAdapter(worker, null, null);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "input.visible.click", Json("""{"label":"Aceptar"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.AnyOf("visible_click_no_receipt", "active_window_not_found"));
        });
    }

    // Auditoría final V3: an application named that no window is (exactly) is never read in another window's place,
    // the person's in front: nothing is looked at, and the visible windows go back for the model to name one.
    [Test]
    public async Task ANamedApplicationThatNoWindowIsReadsNothingInItsPlace()
    {
        var worker = new ScriptedUiaWorker("{\"ok\":true,\"controls\":[]}");
        var adapter = new WindowsVisibleControlAdapter(
            worker, null, null, requestedWindow: (_, _) => ValueTask.FromResult((nint)0));

        ExternalCapabilityReceipt view = await adapter.InvokeAsync(
            "input.visible.controls", Json("""{"application":"el navegador"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(view.Verified, Is.False);
            Assert.That(view.EffectObserved, Is.False);
            Assert.That(view.ErrorCode, Is.EqualTo("application_window_not_found"));
            Assert.That(worker.Commands, Is.Empty, "no window is read in the named one's place");
            Assert.That(view.Result?.GetProperty("candidates").ValueKind, Is.EqualTo(JsonValueKind.Array));
        });
    }

    [Test]
    public void TheCandidatesAreTheVisibleWindowsByTitleAndProcess()
    {
        VisibleControlSurface.DestinationWindow[] desktop =
        [
            new("chrome", "Nueva pestaña - Google Chrome"),
            new("notepad++", "notas.txt - Notepad++"),
        ];
        // Ronda final 19 (regla 3): a desktop of more windows than are listed says how many there are.
        VisibleControlSurface.DestinationWindow[] crowded =
            [.. Enumerable.Range(0, WindowsVisibleControlAdapter.NamedWindowCandidateLimit + 2)
                .Select(index => new VisibleControlSurface.DestinationWindow("notepad", "nota " + index))];

        ExternalCapabilityReceipt receipt = WindowsVisibleControlAdapter.NamedWindowNotFound("input.visible.controls", desktop);
        JsonElement cut = WindowsVisibleControlAdapter.NamedWindowNotFound("input.visible.controls", crowded).Result!.Value;

        JsonElement candidates = receipt.Result!.Value.GetProperty("candidates");
        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("application_window_not_found"));
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(candidates.GetArrayLength(), Is.EqualTo(2));
            Assert.That(receipt.Result!.Value.GetProperty("candidateCount").GetInt32(), Is.EqualTo(2));
            Assert.That(receipt.Result!.Value.TryGetProperty("truncated", out _), Is.False);
            Assert.That(candidates[0].GetProperty("title").GetString(), Is.EqualTo("Nueva pestaña - Google Chrome"));
            Assert.That(candidates[0].GetProperty("process").GetString(), Is.EqualTo("chrome"));
            Assert.That(candidates[1].GetProperty("process").GetString(), Is.EqualTo("notepad++"));
            Assert.That(cut.GetProperty("candidates").GetArrayLength(), Is.EqualTo(WindowsVisibleControlAdapter.NamedWindowCandidateLimit));
            Assert.That(cut.GetProperty("candidateCount").GetInt32(), Is.EqualTo(WindowsVisibleControlAdapter.NamedWindowCandidateLimit + 2));
            Assert.That(cut.GetProperty("truncated").GetBoolean(), Is.True);
        });
    }

    // Auditoría P3: only the name itself, folded (case, accents, spaces); no alias, no containment, no typo.
    [TestCase("aceptar", "Aceptar", true)]
    [TestCase("biblioteca", "BIBLIOTECA", true)]
    [TestCase("Modo avión", "Modo  avion", true)]
    [TestCase("Cotele", "Cotele (canal de voz)", false)]
    [TestCase("bibloteca", "Biblioteca", false)]
    [TestCase("library", "Biblioteca", false)]
    [TestCase("5", "Cinco", false)]
    [TestCase("Tienda", "Biblioteca", false)]
    [TestCase("", "Biblioteca", false)]
    public void ALabelNamesOnlyTheControlOfThatFoldedName(string label, string name, bool expected)
    {
        Assert.That(WindowsVisibleControlAdapter.SameLabel(label, name), Is.EqualTo(expected));
    }

    [Test]
    public void ALabelNamingNothingExactlyPressesNothingAndSaysTheNamesSeen()
    {
        ExternalCapabilityReceipt missing = WindowsVisibleControlAdapter.NotNamed(
            "input.visible.click", "visible_button_not_found", ["Cotele (canal de voz)", "Cotele, texto"]);
        ExternalCapabilityReceipt bare = WindowsVisibleControlAdapter.NotNamed("input.visible.click", "visible_button_not_found", []);

        Assert.Multiple(() =>
        {
            Assert.That(missing.ErrorCode, Is.EqualTo("visible_button_not_found"));
            Assert.That(missing.EffectObserved || missing.EffectMayHaveOccurred || missing.Verified, Is.False);
            Assert.That(missing.Result?.GetProperty("candidates").EnumerateArray().Select(name => name.GetString()),
                Is.EqualTo(new[] { "Cotele (canal de voz)", "Cotele, texto" }));
            Assert.That(bare.Result, Is.Null);
            Assert.That(bare.EffectMayHaveOccurred, Is.False);
        });
    }

    [TestCase(10, 10, "TL")]
    [TestCase(150, 10, "T")]
    [TestCase(290, 10, "TR")]
    [TestCase(10, 100, "L")]
    [TestCase(150, 100, "C")]
    [TestCase(290, 190, "BR")]
    [TestCase(150, 190, "B")]
    public void ZonesFollowTheThreeByThreeGridOfTheWindow(int x, int y, string expected)
    {
        var window = new WindowsVisibleControlAdapter.Rect(0, 0, 300, 200);
        Assert.That(WindowsVisibleControlAdapter.Zone(x, y, window), Is.EqualTo(expected));
    }

    [Test]
    public async Task TheOcrReadsAWindowImageHeldInMemory()
    {
        // A red pixel beside a green one, as a window capture encodes it (BGRA, bottom-up): decoded from memory,
        // with no capture file, for the OCR engine.
        WindowImage image = WindowsScreenshotProvider.Image(new ScreenshotFrame(2, 1, [0, 0, 255, 255, 0, 255, 0, 255]));

        using global::Windows.Graphics.Imaging.SoftwareBitmap bitmap = await WindowsVisibleOcrLocator.DecodeAsync(image.Bmp);
        byte[] pixels = new byte[8];
        bitmap.CopyToBuffer(System.Runtime.InteropServices.WindowsRuntime.WindowsRuntimeBufferExtensions.AsBuffer(pixels));

        Assert.Multiple(() =>
        {
            Assert.That((bitmap.PixelWidth, bitmap.PixelHeight), Is.EqualTo((2, 1)));
            Assert.That(pixels[..3], Is.EqualTo(new byte[] { 0, 0, 255 }));
            Assert.That(pixels[4..7], Is.EqualTo(new byte[] { 0, 255, 0 }));
        });
    }

    internal sealed class ScriptedUiaWorker : IUiaWorker
    {
        private readonly Queue<string> _answers;

        internal ScriptedUiaWorker(params string[] answers)
        {
            _answers = new Queue<string>(answers);
        }

        internal List<string> Commands { get; } = [];

        internal int Prewarmed { get; private set; }

        // After this many commands the worker answers nothing more.
        internal int? FallSilentAfter { get; set; }

        public ValueTask PrewarmAsync(CancellationToken cancellationToken)
        {
            Prewarmed++;
            return ValueTask.CompletedTask;
        }

        public ValueTask<JsonDocument?> SendAsync(string commandJson, TimeSpan timeout, CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            Commands.Add(commandJson);
            if (_answers.Count == 0 || Commands.Count > FallSilentAfter)
                return ValueTask.FromResult<JsonDocument?>(null);
            string answer = _answers.Count == 1 ? _answers.Peek() : _answers.Dequeue();
            return ValueTask.FromResult<JsonDocument?>(JsonDocument.Parse(answer));
        }
    }

    private sealed class CountingLocator : IVisibleControlLocator
    {
        private readonly bool _hit;

        internal CountingLocator(string stage, bool hit)
        {
            Stage = stage;
            _hit = hit;
        }

        internal int Calls { get; private set; }

        public string Stage { get; }

        public ValueTask<ExternalCapabilityReceipt?> TryClickAsync(
            string operation, string label, CancellationToken cancellationToken)
        {
            Calls++;
            if (!_hit)
                return ValueTask.FromResult<ExternalCapabilityReceipt?>(null);
            JsonElement result = Json(
                "{\"version\":1,\"ok\":true,\"effectObserved\":true,\"error\":\"\",\"name\":\"" + label + "\"," +
                "\"controlIdentity\":\"" + Stage + ".1\",\"absentOrDisabled\":false,\"selected\":false," +
                "\"surfaceChanged\":true,\"cascadeStage\":\"" + Stage + "\",\"authority\":\"" + Stage + "_locate_click_postread\"}");
            return ValueTask.FromResult<ExternalCapabilityReceipt?>(
                new ExternalCapabilityReceipt(operation, true, true, result, null));
        }
    }
}
