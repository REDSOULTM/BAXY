using System.Net;
using System.Text;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

// Ajuste c3, séptima vuelta (en vivo en el NB, «Guardar como»): a click by a label the window does not have («Editar» on
// the dialog, a file name asked for as a button) went down the cascade to vision, which answered a point; nothing written
// there was the label and no accessible control there had its name, the pointer pressed it anyway and the receipt said
// completed. A point vision answers is pressed only when it is the label: the control there has its name (the worker's
// press by its way), or the words read there hold it. Otherwise nothing is pressed and the label is not found.
[NonParallelizable]
public sealed class VisionPointLabelTests
{
    private const int Width = 128;
    private const int Height = 64;

    private static readonly string[] Names = ["BAXY_VISION_ENDPOINT", "BAXY_VISION_MODEL", "BAXY_VISION_SLOT_DIR"];

    // The answered box [100, 200, 300, 300] in thousandths is the point (26, 16) of a 128×64 window.
    private const int PointX = 26;
    private const int PointY = 16;

    private static WindowsVisibleOcrLocator.LayoutLine Line(string text, double x, double y, double w, double h) =>
        new(text, x, y, w, h, [new WindowsVisibleOcrLocator.LayoutWord(text, x, y, w, h)]);

    [Test]
    public async Task APointWhereNeitherTheWordsNorTheControlAreTheLabelPressesNothing()
    {
        var press = new FakePress(PointPressed.NothingThere);
        ExternalCapabilityReceipt? receipt = await ClickAsync("Editar", [Line("Guardar", 80, 40, 40, 12)], press);

        Assert.Multiple(() =>
        {
            Assert.That(receipt, Is.Null, "the label is not found, never completed");
            Assert.That(press.PointAsked, Is.EqualTo(1), "the control at the point may still be the label's");
            Assert.That(press.PointerPressed, Is.Zero, "the pointer never presses a point that is not the label");
        });
    }

    // Encargo 16 (suite de Providers en el PC, 2 de 3839 en rojo; en el NB, con otra ventana al frente, 4 de 22): the
    // window's own motion was read from the desktop's front window, not through the locator's capture; a front window that
    // could not be captured failed the click as vision_provider_request_failed before anything was pressed. Every look at
    // the window goes through the locator's capture: the one read, the one before the press and the motion probes.
    [Test]
    public async Task TheWindowsOwnMotionIsReadThroughTheLocatorsCapture()
    {
        var press = new FakePress(PointPressed.NothingThere);
        using var http = new HttpClient(new Answering());
        VisibleControlSurface.CapturedWindow shown = Frame();
        int looks = 0;
        var locator = new WindowsVisibleVisionLocator(
            http,
            _ =>
            {
                looks++;
                return ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(shown);
            },
            (_, _) => ValueTask.FromResult<IReadOnlyList<WindowsVisibleOcrLocator.LayoutLine>?>(
                [Line("Guardar", 80, 40, 40, 12)]));
        string?[] saved = SetEnvironment();
        try
        {
            ExternalCapabilityReceipt? receipt = await locator.TryClickAsync("input.visible.click", "Editar", press, CancellationToken.None);
            Assert.Multiple(() =>
            {
                Assert.That(receipt, Is.Null);
                Assert.That(looks, Is.EqualTo(2 + VisibleControlSurface.AnimationProbes.Length));
            });
        }
        finally
        {
            RestoreEnvironment(saved);
        }
    }

    // The same answer twice on the same drawing: the second asks no one and presses nothing (VisionAnswerMemory).
    [Test]
    public async Task ThePointNotTheLabelIsRememberedForTheSameDrawing()
    {
        var press = new FakePress(PointPressed.NothingThere);
        var handler = new Answering();
        using var http = new HttpClient(handler);
        var locator = Locator(http, [Line("Guardar", 80, 40, 40, 12)]);
        string?[] saved = SetEnvironment();
        try
        {
            ExternalCapabilityReceipt? first = await locator.TryClickAsync("input.visible.click", "Editar", press, CancellationToken.None);
            ExternalCapabilityReceipt? again = await locator.TryClickAsync("input.visible.click", "Editar", press, CancellationToken.None);
            Assert.Multiple(() =>
            {
                Assert.That(first, Is.Null);
                Assert.That(again, Is.Null);
                Assert.That(handler.Asked, Is.EqualTo(1));
                Assert.That(press.PointerPressed, Is.Zero);
            });
        }
        finally
        {
            RestoreEnvironment(saved);
        }
    }

    // Ajuste c4 (banco ciego c3: C3-051, 053, 054, 067 y 072, «Opciones», «Guardar» o «Awake» on a window without them,
    // two questions each, 18.8 to 40.6 s): the first point fell on another label and nothing read or last seen is like
    // the label. A second question could give no point to press (no words there hold the label, and the worker presses
    // only a control of that name, which the tree did not find): vision is asked once, the receipt and the memory as
    // with two.
    [Test]
    public async Task APointOnAnotherLabelWithNothingLikeTheLabelShownAsksVisionOnce()
    {
        var press = new FakePress(PointPressed.NothingThere);
        var handler = new Answering();
        using var http = new HttpClient(handler);
        var locator = Locator(http, [Line("Archivo", 14, 10, 30, 12)]);
        string?[] saved = SetEnvironment();
        try
        {
            ExternalCapabilityReceipt? first = await locator.TryClickAsync("input.visible.click", "Opciones", press, CancellationToken.None);
            int asked = handler.Asked;
            ExternalCapabilityReceipt? again = await locator.TryClickAsync("input.visible.click", "Opciones", press, CancellationToken.None);
            Assert.Multiple(() =>
            {
                Assert.That(asked, Is.EqualTo(1), "one question, not two");
                Assert.That(first?.ErrorCode, Is.EqualTo("vision_point_on_other_label"));
                Assert.That(first?.EffectMayHaveOccurred, Is.False);
                Assert.That(again?.ErrorCode, Is.EqualTo("vision_point_on_other_label"), "remembered for the same drawing");
                Assert.That(handler.Asked, Is.EqualTo(1), "the retry asks nothing");
                Assert.That(press.PointAsked + press.PointerPressed, Is.Zero);
            });
        }
        finally
        {
            RestoreEnvironment(saved);
        }
    }

    // Contracases: the label may be on this drawing, so the second question (told which label the point is not) is still
    // asked: written in a line read, a short one too; a line read like it; a name the last look of the window showed like it.
    [TestCase("Opciones", "Opciones", null, TestName = "AsksAgainWhenTheLabelIsWrittenElsewhere")]
    [TestCase("Opciones avanzadas", "Opciones", null, TestName = "AsksAgainWhenALineReadIsLikeTheLabel")]
    [TestCase("OK", "OK", null, TestName = "AsksAgainForAShortLabelWrittenElsewhere")]
    [TestCase("Opciones", null, "Opciones de impresión", TestName = "AsksAgainWhenTheLastLookNamedSomethingLikeIt")]
    [TestCase("OK", null, "OK", TestName = "AsksAgainWhenTheLastLookNamedAShortLabel")]
    public async Task APointOnAnotherLabelAsksAgainWhenTheLabelMayBeShown(string label, string? written, string? seen)
    {
        var press = new FakePress(PointPressed.NothingThere, seen is null ? [] : [seen]);
        var handler = new Answering();
        using var http = new HttpClient(handler);
        WindowsVisibleOcrLocator.LayoutLine[] layout = written is null
            ? [Line("Archivo", 14, 10, 30, 12)]
            : [Line("Archivo", 14, 10, 30, 12), Line(written, 80, 40, 40, 12)];
        string?[] saved = SetEnvironment();
        try
        {
            ExternalCapabilityReceipt? receipt = await Locator(http, layout)
                .TryClickAsync("input.visible.click", label, press, CancellationToken.None);
            Assert.Multiple(() =>
            {
                Assert.That(handler.Asked, Is.EqualTo(2));
                Assert.That(receipt?.ErrorCode, Is.EqualTo("vision_point_on_other_label"));
                Assert.That(receipt?.EffectMayHaveOccurred, Is.False);
            });
        }
        finally
        {
            RestoreEnvironment(saved);
        }
    }

    [TestCase("Opciones", new[] { "Archivo" }, new string[0], ExpectedResult = false)]
    [TestCase("Opciones", new[] { "Archivo", "Más opciones" }, new string[0], ExpectedResult = true)]
    [TestCase("opciones", new[] { "OPCIONES" }, new string[0], ExpectedResult = true)]
    [TestCase("OK", new[] { "Archivo", "OK" }, new string[0], ExpectedResult = true)]
    [TestCase("OK", new[] { "Archivo", "Okupas" }, new string[0], ExpectedResult = true)]
    [TestCase("OK", new[] { "Archivo" }, new string[0], ExpectedResult = false)]
    [TestCase("OK", new[] { "Archivo" }, new[] { "OK" }, ExpectedResult = true)]
    [TestCase("Opciones avanzadas", new[] { "Opciones" }, new string[0], ExpectedResult = true)]
    [TestCase("Opciones", new[] { "Archivo" }, new[] { "Opciones de impresión" }, ExpectedResult = true)]
    [TestCase("Configuración", new[] { "Combinar el archivo entero con." }, new string[0], ExpectedResult = true)]
    public bool TheLabelMayBeShownWhenWrittenOrLikeALineOrANameSeen(string label, string[] lines, string[] seen) =>
        WindowsVisibleVisionLocator.LabelMayBeShown([.. lines.Select(static text => Line(text, 0, 0, 40, 12))], label, seen);

    [Test]
    public void NothingReadSaysNothingAgainstTheLabel() =>
        Assert.That(WindowsVisibleVisionLocator.LabelMayBeShown(null, "Opciones", []), Is.True);

    // Contracase: the words read at the point are the label (a control the tree does not name): the pointer may press it.
    [Test]
    public async Task APointOnTheLabelsWordsMayStillBePressedByThePointer()
    {
        var press = new FakePress(PointPressed.NothingThere);
        await ClickAsync("Editar", [Line("Editar", 14, 10, 30, 12)], press);

        Assert.That(press.PointerPressed, Is.EqualTo(1));
    }

    // Contracase: the control at the point bears the label (the worker presses it by its way, no pointer).
    [Test]
    public async Task AControlAtThePointThatBearsTheLabelIsPressedByItsWay()
    {
        var press = new FakePress(new PointPressed(PointPressOutcome.Pressed, "invoke", "Editar", "Button"));
        await ClickAsync("Editar", [], press);

        Assert.Multiple(() =>
        {
            Assert.That(press.PointAsked, Is.EqualTo(1));
            Assert.That(press.PointerPressed, Is.Zero);
        });
    }

    [Test]
    public void TheLabelIsAtThePointOnlyWhereItsWordsAre()
    {
        WindowsVisibleOcrLocator.LayoutLine row = new("Archivo Editar Ver", 10, 10, 120, 12,
        [
            new WindowsVisibleOcrLocator.LayoutWord("Archivo", 10, 10, 40, 12),
            new WindowsVisibleOcrLocator.LayoutWord("Editar", 56, 10, 34, 12),
            new WindowsVisibleOcrLocator.LayoutWord("Ver", 96, 10, 20, 12),
        ]);
        WindowsVisibleOcrLocator.LayoutLine file = new("prueba c3 guardado.txt", 10, 40, 130, 12,
        [
            new WindowsVisibleOcrLocator.LayoutWord("prueba", 10, 40, 40, 12),
            new WindowsVisibleOcrLocator.LayoutWord("c3", 54, 40, 14, 12),
            new WindowsVisibleOcrLocator.LayoutWord("guardado.txt", 72, 40, 68, 12),
        ]);
        WindowsVisibleOcrLocator.LayoutLine[] layout = [row, file];
        Assert.Multiple(() =>
        {
            Assert.That(WindowsVisibleVisionLocator.LabelWrittenAt(layout, "Editar", 70, 16), Is.True, "on its word");
            Assert.That(WindowsVisibleVisionLocator.LabelWrittenAt(layout, "editar", 92, 16), Is.True, "beside it, folded");
            Assert.That(WindowsVisibleVisionLocator.LabelWrittenAt(layout, "Editar", 25, 16), Is.False,
                "another word of the same line");
            Assert.That(WindowsVisibleVisionLocator.LabelWrittenAt(layout, "Prueba c3 guardado.txt", 60, 46), Is.True,
                "a label of several words, on any of them");
            Assert.That(WindowsVisibleVisionLocator.LabelWrittenAt(layout, "Editar", 70, 60), Is.False, "blank room");
            Assert.That(WindowsVisibleVisionLocator.LabelWrittenAt(layout, "Guardar", 70, 16), Is.False, "not written");
            Assert.That(WindowsVisibleVisionLocator.LabelWrittenAt(null, "Editar", 70, 16), Is.False, "nothing read");
        });
    }

    private static async Task<ExternalCapabilityReceipt?> ClickAsync(
        string label, WindowsVisibleOcrLocator.LayoutLine[] layout, FakePress press)
    {
        string?[] saved = SetEnvironment();
        try
        {
            using var http = new HttpClient(new Answering());
            return await Locator(http, layout).TryClickAsync("input.visible.click", label, press, CancellationToken.None);
        }
        finally
        {
            RestoreEnvironment(saved);
        }
    }

    private static WindowsVisibleVisionLocator Locator(HttpClient http, WindowsVisibleOcrLocator.LayoutLine[] layout)
    {
        VisibleControlSurface.CapturedWindow shown = Frame();
        return new WindowsVisibleVisionLocator(
            http,
            _ => ValueTask.FromResult<VisibleControlSurface.CapturedWindow?>(shown),
            (_, _) => ValueTask.FromResult<IReadOnlyList<WindowsVisibleOcrLocator.LayoutLine>?>(layout));
    }

    private static string?[] SetEnvironment()
    {
        string?[] saved = [.. Names.Select(Environment.GetEnvironmentVariable)];
        Environment.SetEnvironmentVariable("BAXY_VISION_ENDPOINT", "http://127.0.0.1:8090/v1/chat/completions");
        Environment.SetEnvironmentVariable("BAXY_VISION_MODEL", "vision-test");
        Environment.SetEnvironmentVariable("BAXY_VISION_SLOT_DIR", null);
        return saved;
    }

    private static void RestoreEnvironment(string?[] saved)
    {
        for (int index = 0; index < Names.Length; index++)
            Environment.SetEnvironmentVariable(Names[index], saved[index]);
    }

    // A 32-bit bottom-up BMP of the window, all grey.
    private static VisibleControlSurface.CapturedWindow Frame()
    {
        int stride = Width * 4;
        var bmp = new byte[54 + (stride * Height)];
        bmp[0] = (byte)'B';
        bmp[1] = (byte)'M';
        BitConverter.GetBytes(bmp.Length).CopyTo(bmp, 2);
        BitConverter.GetBytes(54).CopyTo(bmp, 10);
        BitConverter.GetBytes(40).CopyTo(bmp, 14);
        BitConverter.GetBytes(Width).CopyTo(bmp, 18);
        BitConverter.GetBytes(Height).CopyTo(bmp, 22);
        BitConverter.GetBytes((short)1).CopyTo(bmp, 26);
        BitConverter.GetBytes((short)32).CopyTo(bmp, 28);
        bmp.AsSpan(54).Fill(0x80);
        return new VisibleControlSurface.CapturedWindow(7, bmp, 0, 0, Width, Height, "dialog");
    }

    // The server: every question answered with the box [100, 200, 300, 300], the point (26, 16).
    private sealed class Answering : HttpMessageHandler
    {
        internal int Asked { get; private set; }

        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            Asked++;
            return Task.FromResult(new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new StringContent(
                    """{"choices":[{"message":{"content":"{\"bbox_2d\": [100, 200, 300, 300]}"}}]}""",
                    Encoding.UTF8,
                    "application/json"),
            });
        }
    }

    // The press at the point: the worker's answer is given; the pointer is only counted, and reports a press with no burst.
    // The last look of the window showed the names «seen».
    private sealed class FakePress(PointPressed atPoint, string[]? seen = null) : IPointPress
    {
        public IReadOnlyList<string> NamesSeen(nint window) => seen ?? [];

        internal int PointAsked { get; private set; }

        internal int PointerPressed { get; private set; }

        public ValueTask<PointPressed> PressAtAsync(
            nint window, int screenX, int screenY, string label, CancellationToken cancellationToken)
        {
            PointAsked++;
            Assert.That((screenX, screenY), Is.EqualTo((PointX, PointY)));
            return ValueTask.FromResult(atPoint);
        }

        public ValueTask<PointerPressed> PointerAtAsync(
            nint window,
            int screenX,
            int screenY,
            VisibleControlSurface.CapturedWindow? located,
            PointRelocator? relocate,
            CancellationToken cancellationToken)
        {
            PointerPressed++;
            return ValueTask.FromResult(new PointerPressed(true, located));
        }
    }
}
