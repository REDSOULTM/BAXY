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
            Assert.That(worker.Commands[^1], Does.Contain("Aceptar"));
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

    [Test]
    public async Task TheBrowserWithoutANameIsTheFrontWindowOfThePersonsBrowser()
    {
        // A handle no window has: nothing on the desktop is read or moved.
        const long front = 0x7FFF_0F1E;
        var worker = new ScriptedUiaWorker(
            "{\"ok\":true,\"error\":\"\",\"hwnd\":" + front + ",\"window\":\"Inicio\",\"controls\":[" +
            "{\"i\":0,\"kind\":\"TabItem\",\"name\":\"Never Gonna Give You Up - YouTube\",\"id\":\"4.2\"," +
            "\"state\":\"\",\"value\":null,\"rect\":null,\"repeated\":0}],\"controlCount\":1,\"focused\":null}");
        var browser = new FixedBrowserWindow(front);
        var adapter = new WindowsVisibleControlAdapter(worker, null, null, browserWindow: browser);

        ExternalCapabilityReceipt view = await adapter.InvokeAsync(
            "input.visible.controls", Json("""{"application":"el navegador","processId":4242}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(view.Verified, Is.True);
            Assert.That(browser.Calls, Is.EqualTo(1));
            Assert.That(worker.Commands[0], Does.Contain("\"hwnd\":" + front),
                "the person's browser window wins over a process the mission had adopted");
            Assert.That(view.Result?.GetProperty("window").GetProperty("hwnd").GetInt64(), Is.EqualTo(front));
            Assert.That(view.Result?.GetProperty("window").GetProperty("requested").GetBoolean(), Is.True);
            Assert.That(view.Result?.GetProperty("controls")[0].GetProperty("kind").GetString(), Is.EqualTo("TabItem"));
        });
    }

    [TestCase("navegador", true)]
    [TestCase("el navegador", true)]
    [TestCase("Mi Navegador", true)]
    [TestCase("browser", true)]
    [TestCase("my browser", true)]
    [TestCase("web browser", true)]
    [TestCase("navegador web", true)]
    [TestCase("Opera GX", false)]
    [TestCase("navegador de archivos", false)]
    [TestCase("", false)]
    [TestCase(null, false)]
    public void TheBrowserCategoryIsTheWordNotAProduct(string? application, bool expected) =>
        Assert.That(IUserBrowserWindowLocator.NamesTheCategory(application), Is.EqualTo(expected));

    [TestCase("aceptar", "Aceptar", true)]
    [TestCase("biblioteca", "BIBLIOTECA", true)]
    [TestCase("Modo avión", "Modo avion", true)]
    [TestCase("Cotele", "Cotele (canal de voz)", true)]
    [TestCase("bibloteca", "Biblioteca", true)]
    [TestCase("Tienda", "Biblioteca", false)]
    [TestCase("", "Biblioteca", false)]
    public void LabelsNameControlsFoldedAndWithABoundedTypo(string label, string name, bool expected)
    {
        Assert.That(WindowsVisibleControlAdapter.LabelNames(label, name), Is.EqualTo(expected));
    }

    [TestCase("5", new[] { "5", "Cinco", "Five" })]
    [TestCase("cinco", new[] { "5", "Cinco", "Five" })]
    [TestCase("library", new[] { "Biblioteca", "Library", "library" })]
    [TestCase("Cotele", new[] { "Cotele" })]
    public void AliasesCoverDigitsAndBilingualCatalogLabels(string label, string[] expected)
    {
        Assert.That(WindowsVisibleControlAdapter.Aliases(label), Is.EqualTo(expected));
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

    [TestCase(220, 30, 30, "red")]
    [TestCase(240, 140, 20, "orange")]
    [TestCase(30, 180, 60, "green")]
    [TestCase(30, 60, 220, "blue")]
    [TestCase(250, 250, 250, "white")]
    [TestCase(10, 10, 10, "black")]
    [TestCase(128, 128, 128, "gray")]
    [TestCase(160, 40, 200, "purple")]
    public void DominantColourClassesFollowTheHsvCuts(int red, int green, int blue, string expected)
    {
        int index = VisibleControlColors.Classify((byte)red, (byte)green, (byte)blue);
        Assert.That(VisibleControlColors.Names[index], Is.EqualTo(expected));
    }

    [Test]
    public void DominantColourIsReadFromTheControlRectangleOfABottomUpBitmap()
    {
        const int width = 8;
        const int height = 8;
        const int offset = 54;
        byte[] bmp = new byte[offset + width * height * 4];
        bmp[0] = (byte)'B';
        bmp[1] = (byte)'M';
        BitConverter.GetBytes(offset).CopyTo(bmp, 10);
        BitConverter.GetBytes(width).CopyTo(bmp, 18);
        BitConverter.GetBytes(height).CopyTo(bmp, 22);
        BitConverter.GetBytes((short)32).CopyTo(bmp, 28);
        // Top half red, bottom half blue, stored bottom-up.
        for (int y = 0; y < height; y++)
        {
            int row = height - 1 - y;
            for (int x = 0; x < width; x++)
            {
                int index = offset + row * width * 4 + x * 4;
                bmp[index] = (byte)(y < 4 ? 20 : 220);      // B
                bmp[index + 1] = 20;                          // G
                bmp[index + 2] = (byte)(y < 4 ? 220 : 20);   // R
                bmp[index + 3] = 255;
            }
        }

        Assert.Multiple(() =>
        {
            Assert.That(VisibleControlColors.TryParse(bmp, out int parsedOffset, out int parsedWidth, out int parsedHeight), Is.True);
            Assert.That((parsedOffset, parsedWidth, parsedHeight), Is.EqualTo((offset, width, height)));
            Assert.That(VisibleControlColors.Dominant(bmp, offset, width, height, 0, 0, 8, 4), Is.EqualTo("red"));
            Assert.That(VisibleControlColors.Dominant(bmp, offset, width, height, 0, 4, 8, 4), Is.EqualTo("blue"));
        });
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

    private sealed class FixedBrowserWindow(long handle) : IUserBrowserWindowLocator
    {
        internal int Calls { get; private set; }

        public nint FrontWindow()
        {
            Calls++;
            return (nint)handle;
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
