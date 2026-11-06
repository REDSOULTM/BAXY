using System.Buffers.Binary;
using System.Runtime.InteropServices.WindowsRuntime;
using Baxy.Providers.Windows.External;
using NUnit.Framework;
using Windows.Graphics.Imaging;

namespace Baxy.Providers.Windows.Tests;

// Uso real 2026-11-03 (G3): message.draft and message.send failed with recipient_identity_not_verified on a WhatsApp chat
// whose one row was clicked: the header must name the recipient exactly, and a contact saved with an emoji after its name
// is read by Tesseract with that picture as letters for some emoji. The fixtures are WhatsApp-like header rows rendered by
// Chromium (Edge headless, the engine of WhatsApp Desktop's WebView2), with invented names.
[TestFixture]
public sealed class G3CabeceraConEmojiDetrasTests
{
    // An emoji the OCR reads as letters («Rey wr», «Luna J», «Profe My» in today's six passes) is set aside: it is drawn
    // in colour after the name.
    [TestCase("cabecera-rey-corona-oscuro.png", "Rey")]
    [TestCase("cabecera-luna-oscuro.png", "Luna")]
    [TestCase("cabecera-profe-libros-claro.png", "Profe")]
    [TestCase("cabecera-hermano-cara-oscuro.png", "Hermano")]
    // Held-out, written by a subagent that did not see the change (names and emoji its own).
    [TestCase("heldout-fena-oscuro.png", "Feña")]
    [TestCase("heldout-fena-claro.png", "Feña")]
    [TestCase("heldout-don-hernan-oscuro.png", "Don Hernán")]
    [TestCase("heldout-don-hernan-claro.png", "Don Hernán")]
    [TestCase("heldout-primo-nacho-oscuro.png", "Primo Nacho")]
    [TestCase("heldout-primo-nacho-claro.png", "Primo Nacho")]
    public async Task AnEmojiAfterTheNameStillLetsTheHeaderNameTheRecipient(string fixture, string recipient)
    {
        byte[] header = await HeaderAsync(fixture);
        string? named = await WindowsDesktopMessagingAutomation.ReadHeaderNameAsync(header, recipient, CancellationToken.None);
        Assert.That(named is not null && WindowsDesktopMessagingAutomation.NamesRecipient(named, recipient), Is.True,
            $"the header read named «{named}»");
    }

    // Encargo 33: «Feña» passed on the notebook and failed on the PC. Same Tesseract (5.4.0) and the same English model
    // (SHA-256 7d4322bd…) on both; only the notebook's runtime has the Spanish one (BAXYRuntime\ocr	essdata-fast), and
    // the English model, which has no «ñ», reads «Fenia». Read as on a machine without it, an accented name still names
    // the recipient, so the result no longer depends on which models a machine has.
    [TestCase("heldout-fena-oscuro.png", "Feña")]
    [TestCase("heldout-fena-claro.png", "Feña")]
    [TestCase("heldout-don-hernan-oscuro.png", "Don Hernán")]
    [TestCase("heldout-don-hernan-claro.png", "Don Hernán")]
    public async Task AnAccentedNameIsReadWithoutTesseractsSpanishModel(string fixture, string recipient)
    {
        byte[] header = await HeaderAsync(fixture);
        string? named = await WindowsDesktopMessagingAutomation.ReadHeaderNameAsync(
            header, recipient, CancellationToken.None, spanishModel: false);
        Assert.That(named is not null && WindowsDesktopMessagingAutomation.NamesRecipient(named, recipient), Is.True,
            $"the header read named «{named}»");
    }

    // Without the Spanish model either, «Ana B» never passes for «Ana».
    [TestCase("cabecera-ana-b-oscuro.png")]
    [TestCase("cabecera-ana-b-claro.png")]
    public async Task WithoutTesseractsSpanishModelALetterAfterTheNameIsStillAnotherName(string fixture)
    {
        byte[] header = await HeaderAsync(fixture);
        Assert.That(await WindowsDesktopMessagingAutomation.ReadHeaderNameAsync(
            header, "Ana", CancellationToken.None, spanishModel: false), Is.Null);
    }

    // A grey letter after the name is part of another contact's name: «Ana B» never passes for «Ana».
    [TestCase("cabecera-ana-b-oscuro.png")]
    [TestCase("cabecera-ana-b-claro.png")]
    public async Task ALetterAfterTheNameIsAnotherName(string fixture)
    {
        byte[] header = await HeaderAsync(fixture);
        Assert.Multiple(async () =>
        {
            Assert.That(await WindowsDesktopMessagingAutomation.ReadHeaderNameAsync(header, "Ana", CancellationToken.None),
                Is.Null);
            Assert.That(await WindowsDesktopMessagingAutomation.ReadHeaderNameAsync(header, "Ana B", CancellationToken.None),
                Is.EqualTo("Ana B"));
        });
    }

    [Test]
    public void OnlyAColouredLastWordAfterTheNameIsSetAside()
    {
        // 40 x 10: grey on the left half, a filled colour on the right half.
        byte[] picture = Bitmap(40, 10, x => x < 20 ? ((byte)200, (byte)200, (byte)200) : ((byte)240, (byte)180, (byte)20));
        WindowsDesktopMessagingAutomation.TsvWord Word(string text, int left) => new(text, 1, 1, 1, left, 0, 18, 10);
        Assert.Multiple(() =>
        {
            Assert.That(WindowsDesktopMessagingAutomation.ColourShare(picture, 0, 0, 18, 10), Is.Zero);
            Assert.That(WindowsDesktopMessagingAutomation.ColourShare(picture, 22, 0, 18, 10), Is.GreaterThan(0.8));
            Assert.That(WindowsDesktopMessagingAutomation.PictureTailName([Word("Rey", 0), Word("wr", 22)], picture, 1, "Rey"),
                Is.EqualTo("Rey"));
            Assert.That(WindowsDesktopMessagingAutomation.PictureTailName([Word("Rey", 22), Word("wr", 0)], picture, 1, "Rey"),
                Is.Null, "a grey last word is a letter of the name");
            Assert.That(WindowsDesktopMessagingAutomation.PictureTailName([Word("Reyes", 0), Word("wr", 22)], picture, 1, "Rey"),
                Is.Null, "the words before it must be the recipient");
            Assert.That(WindowsDesktopMessagingAutomation.OneWordAfterName("Rey wr", "Rey"), Is.True);
            Assert.That(WindowsDesktopMessagingAutomation.OneWordAfterName("Rey wr x", "Rey"), Is.False);
            Assert.That(WindowsDesktopMessagingAutomation.TsvWords(
                    "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\r\n"
                    + "4\t1\t1\t1\t1\t0\t5\t6\t70\t20\t-1\t\r\n5\t1\t1\t1\t1\t1\t5\t6\t40\t20\t93.1\tRey\r\n"),
                Is.EqualTo(new[] { new WindowsDesktopMessagingAutomation.TsvWord("Rey", 1, 1, 1, 5, 6, 40, 20) }));
        });
    }

    // The failure said only recipient_identity_not_verified: it now says what the header read (the most read line first)
    // and the row that was clicked, for the model to ask or to name the chat as shown; nothing was written.
    [Test]
    public async Task AHeaderThatDidNotNameTheRecipientComesBackWithWhatItReadAndTheRowClicked()
    {
        DesktopRecipientObservation observation = WindowsDesktopMessagingAutomation.NotNamedInHeader(
            (nint)42, 7, new OcrText("", ["Rey wr\nen línea\n", "Rey wr\nen linea", "Rey vi\n®\n"]), "Rey 10:15");
        using var adapter = new DesktopMessagingAdapter(new Resolving(observation));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "message.draft", Json("""{"channel":"whatsapp","recipient":"Rey","text":"hola"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("recipient_identity_not_verified"));
            Assert.That(receipt.EffectObserved, Is.True, "the row was clicked and that chat is open");
            Assert.That(receipt.Result?.GetProperty("messageWritten").GetBoolean(), Is.False);
            Assert.That(receipt.Result?.GetProperty("headerRead").EnumerateArray().Select(line => line.GetString()),
                Is.EqualTo(new[] { "Rey wr", "en línea", "en linea", "Rey vi" }));
            Assert.That(receipt.Result?.GetProperty("openedRow").GetString(), Is.EqualTo("Rey 10:15"));
        });
    }

    private static System.Text.Json.JsonElement Json(string value) =>
        System.Text.Json.JsonDocument.Parse(value).RootElement.Clone();

    private sealed class Resolving(DesktopRecipientObservation resolve) : IDesktopMessagingAutomation
    {
        public ValueTask<DesktopClientReadiness> EnsureClientOpenAsync(string channel, CancellationToken cancellationToken) =>
            ValueTask.FromResult(DesktopClientReadiness.AlreadyOpen);

        public ValueTask<DesktopRecipientObservation> ResolveAsync(
            string channel, string recipient, CancellationToken cancellationToken) => ValueTask.FromResult(resolve);

        public ValueTask<DesktopRecipientObservation> OpenConversationAsync(
            string channel, string name, string? server, CancellationToken cancellationToken) => ValueTask.FromResult(resolve);

        public ValueTask<DesktopMessageObservation> SendAsync(
            ResolvedRecipient recipient, string text, CancellationToken cancellationToken) =>
            throw new AssertionException("nothing is sent to a chat not verified");

        public ValueTask<DesktopMessageObservation> DraftAsync(
            ResolvedRecipient recipient, string text, CancellationToken cancellationToken) =>
            throw new AssertionException("nothing is written in a chat not verified");
    }

    private static async Task<byte[]> HeaderAsync(string fixture)
    {
        if (WindowsDesktopMessagingAutomation.FindTesseract() is null)
            Assert.Inconclusive("Tesseract is not installed on this machine.");
        string path = Path.Combine(TestContext.CurrentContext.TestDirectory, "Fixtures", "Messaging", fixture);
        await using FileStream file = File.OpenRead(path);
        using global::Windows.Storage.Streams.IRandomAccessStream stream = file.AsRandomAccessStream();
        BitmapDecoder decoder = await BitmapDecoder.CreateAsync(stream);
        using SoftwareBitmap bitmap = await decoder.GetSoftwareBitmapAsync(BitmapPixelFormat.Bgra8, BitmapAlphaMode.Ignore);
        int width = bitmap.PixelWidth, height = bitmap.PixelHeight;
        byte[] topDown = new byte[width * height * 4];
        bitmap.CopyToBuffer(topDown.AsBuffer());
        // The flow's captures are bottom-up (EncodeBmp, positive height).
        byte[] bottomUp = new byte[topDown.Length];
        for (int row = 0; row < height; row++)
            Array.Copy(topDown, row * width * 4, bottomUp, (height - 1 - row) * width * 4, width * 4);
        return WindowsDesktopMessagingAutomation.EncodeBmp(width, height, bottomUp);
    }

    private static byte[] Bitmap(int width, int height, Func<int, (byte R, byte G, byte B)> colour)
    {
        byte[] pixels = new byte[width * height * 4];
        for (int y = 0; y < height; y++)
        {
            for (int x = 0; x < width; x++)
            {
                (byte r, byte g, byte b) = colour(x);
                int offset = ((y * width) + x) * 4;
                pixels[offset] = b;
                pixels[offset + 1] = g;
                pixels[offset + 2] = r;
                pixels[offset + 3] = 255;
            }
        }

        byte[] bitmap = WindowsDesktopMessagingAutomation.EncodeBmp(width, height, pixels);
        Assert.That(BinaryPrimitives.ReadInt32LittleEndian(bitmap.AsSpan(18)), Is.EqualTo(width));
        return bitmap;
    }
}
