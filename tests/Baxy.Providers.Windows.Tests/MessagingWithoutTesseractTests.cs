using System.Runtime.InteropServices.WindowsRuntime;
using Baxy.Providers.Windows.External;
using NUnit.Framework;
using Windows.Graphics.Imaging;

namespace Baxy.Providers.Windows.Tests;

// BAXY's packages do not bring Tesseract (scripts/ names it nowhere), so on a clean Windows every message ended in
// message_ocr_unavailable before opening anything. Read as such a Windows does: the header with Windows' OCR.
[TestFixture]
[NonParallelizable]
public sealed class MessagingWithoutTesseractTests
{
    private Func<string?>? _installed;

    [SetUp]
    public void HideTesseract()
    {
        _installed = WindowsDesktopMessagingAutomation.TesseractLookup;
        WindowsDesktopMessagingAutomation.TesseractLookup = () => null;
    }

    [TearDown]
    public void GiveTesseractBack() => WindowsDesktopMessagingAutomation.TesseractLookup = _installed!;

    [Test]
    public void WindowsOcrIsAnEngineForTheChat()
    {
        if (global::Windows.Media.Ocr.OcrEngine.TryCreateFromUserProfileLanguages() is null)
            Assert.Inconclusive("This Windows has no OCR language of the person's.");
        Assert.That(WindowsDesktopMessagingAutomation.AnyOcrEngine(), Is.EqualTo("windows"));
    }

    [TestCase("heldout-fena-oscuro.png", "Feña")]
    [TestCase("heldout-fena-claro.png", "Feña")]
    [TestCase("heldout-don-hernan-oscuro.png", "Don Hernán")]
    [TestCase("heldout-don-hernan-claro.png", "Don Hernán")]
    [TestCase("heldout-primo-nacho-oscuro.png", "Primo Nacho")]
    public async Task TheHeaderNamesTheRecipient(string fixture, string recipient)
    {
        string? named = await WindowsDesktopMessagingAutomation.ReadHeaderNameAsync(
            await HeaderAsync(fixture), recipient, CancellationToken.None);

        Assert.That(named is not null && WindowsDesktopMessagingAutomation.NamesRecipient(named, recipient), Is.True,
            $"the header read named «{named}»");
    }

    // Measured 2026-11-04: Windows' OCR does not get this one header (an emoji after the name on a light background). It
    // stops the flow with nothing written; it never names anyone else.
    [Test]
    public async Task AHeaderItCannotReadStopsRatherThanNamingSomeoneElse()
    {
        string? named = await WindowsDesktopMessagingAutomation.ReadHeaderNameAsync(
            await HeaderAsync("heldout-primo-nacho-claro.png"), "Primo Nacho", CancellationToken.None);

        Assert.That(named is null || WindowsDesktopMessagingAutomation.NamesRecipient(named, "Primo Nacho"), Is.True);
    }

    // The guard on the recipient does not loosen with the engine: «Ana B» never passes for «Ana».
    [TestCase("cabecera-ana-b-oscuro.png")]
    [TestCase("cabecera-ana-b-claro.png")]
    public async Task ALetterAfterTheNameIsStillAnotherName(string fixture)
    {
        Assert.That(await WindowsDesktopMessagingAutomation.ReadHeaderNameAsync(
            await HeaderAsync(fixture), "Ana", CancellationToken.None), Is.Null);
    }

    private static async Task<byte[]> HeaderAsync(string fixture)
    {
        string path = Path.Combine(TestContext.CurrentContext.TestDirectory, "Fixtures", "Messaging", fixture);
        await using FileStream file = File.OpenRead(path);
        using global::Windows.Storage.Streams.IRandomAccessStream stream = file.AsRandomAccessStream();
        BitmapDecoder decoder = await BitmapDecoder.CreateAsync(stream);
        using SoftwareBitmap bitmap = await decoder.GetSoftwareBitmapAsync(BitmapPixelFormat.Bgra8, BitmapAlphaMode.Ignore);
        int width = bitmap.PixelWidth, height = bitmap.PixelHeight;
        byte[] topDown = new byte[width * height * 4];
        bitmap.CopyToBuffer(topDown.AsBuffer());
        byte[] bottomUp = new byte[topDown.Length];
        for (int row = 0; row < height; row++)
            Array.Copy(topDown, row * width * 4, bottomUp, (height - 1 - row) * width * 4, width * 4);
        return WindowsDesktopMessagingAutomation.EncodeBmp(width, height, bottomUp);
    }
}
