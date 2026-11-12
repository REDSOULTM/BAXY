using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;
using Windows.Graphics.Imaging;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
public sealed class CaptureOcrLayoutTests
{
    private static readonly DateTimeOffset RecognizedAt =
        new(2026, 9, 11, 12, 30, 0, TimeSpan.FromHours(2));
    private static readonly string ImageDigest = new('a', 64);

    [Test]
    public void EmptyRecognitionIsAvailableLayoutWithNoInventedWordsOrAngle()
    {
        JsonElement result = Result([], text: string.Empty);
        JsonElement layout = result.GetProperty("layout");

        Assert.Multiple(() =>
        {
            Assert.That(result.GetProperty("text").GetString(), Is.Empty);
            Assert.That(result.GetProperty("lineCount").GetInt32(), Is.Zero);
            Assert.That(result.GetProperty("textSha256").GetString(),
                Is.EqualTo(Convert.ToHexStringLower(SHA256.HashData([]))));
            Assert.That(layout.GetProperty("available").GetBoolean(), Is.True);
            Assert.That(layout.GetProperty("lines").GetArrayLength(), Is.Zero);
            Assert.That(layout.GetProperty("textAngleDegrees").ValueKind, Is.EqualTo(JsonValueKind.Null));
        });
    }

    // Encargo 119 (F10): the engine has no confidence, so the read says what it cannot read: a foreign alphabet came back as
    // nonsense told as text, and a capture with faint text as a capture with none.
    [Test]
    public void AReadSaysItsLanguagesAndThatNothingRecognizedIsNotNoText()
    {
        JsonElement empty = CaptureOcrLayout.CreateResult("capture_test", "es-MX", string.Empty, ImageDigest,
            100, 50, RecognizedAt, null, [], ["es-MX"]);
        JsonElement read = CaptureOcrLayout.CreateResult("capture_test", "es-MX", "uno", ImageDigest,
            100, 50, RecognizedAt, null, [new("uno", [new("uno", 0, 0, 10, 5)])], ["es-MX", "en-US"]);

        Assert.Multiple(() =>
        {
            Assert.That(empty.GetProperty("recognizerLanguages")[0].GetString(), Is.EqualTo("es-MX"));
            Assert.That(empty.GetProperty("nothingRead").GetString(), Does.Contain("not that it has no text"));
            Assert.That(read.GetProperty("recognizerLanguages").GetArrayLength(), Is.EqualTo(2));
            Assert.That(read.GetProperty("limits").GetString(), Does.Contain("another alphabet").And.Contain("Windows Settings"));
            Assert.That(read.TryGetProperty("nothingRead", out _), Is.False);
        });
    }

    [Test]
    public void RecognitionPreservesEngineOrderOriginalTextAndFractionalImageCoordinates()
    {
        CaptureOcrLine[] lines =
        [
            new("Memoria Ω", [new("Memoria", 60.25, 40.5, 20.25, 9.5), new("Ω", 90, 40, 10, 10)]),
            new("α 12,5 MB", [new("α", 0, 0, 10, 5), new("12,5", 15, 0, 20, 5), new("MB", 40, 0, 10, 5)]),
            new("", []),
        ];
        const string text = "Memoria Ω\r\nα 12,5 MB";
        JsonElement result = Result(lines, text);
        JsonElement layout = result.GetProperty("layout");
        JsonElement observed = layout.GetProperty("lines");
        JsonElement rectangle = observed[0].GetProperty("words")[0].GetProperty("boundingRect");

        Assert.Multiple(() =>
        {
            Assert.That(result.GetProperty("text").GetString(), Is.EqualTo(text));
            Assert.That(result.GetProperty("textSha256").GetString(),
                Is.EqualTo(Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(text)))));
            Assert.That(result.GetProperty("lineCount").GetInt32(), Is.EqualTo(3));
            Assert.That(result.GetProperty("captureId").GetString(), Is.EqualTo("capture_test"));
            Assert.That(result.GetProperty("language").GetString(), Is.EqualTo("es-ES"));
            Assert.That(result.GetProperty("authority").GetString(), Is.EqualTo("windows_media_ocr"));
            Assert.That(result.GetProperty("imageSha256").GetString(), Is.EqualTo(ImageDigest));
            Assert.That(result.GetProperty("imageWidth").GetInt32(), Is.EqualTo(100));
            Assert.That(result.GetProperty("imageHeight").GetInt32(), Is.EqualTo(50));
            Assert.That(result.GetProperty("recognizedAtUtc").GetDateTimeOffset(),
                Is.EqualTo(RecognizedAt.ToUniversalTime()));
            Assert.That(result.GetProperty("recognizedAtUtc").GetDateTimeOffset().Offset, Is.EqualTo(TimeSpan.Zero));
            Assert.That(layout.GetProperty("coordinateSystem").GetString(), Is.EqualTo("image_pixels"));
            Assert.That(observed[0].GetProperty("text").GetString(), Is.EqualTo("Memoria Ω"));
            Assert.That(observed[1].GetProperty("words")[1].GetProperty("text").GetString(), Is.EqualTo("12,5"));
            Assert.That(observed[2].GetProperty("words").GetArrayLength(), Is.Zero);
            Assert.That(rectangle.GetProperty("x").GetDouble(), Is.EqualTo(60.25));
            Assert.That(rectangle.GetProperty("y").GetDouble(), Is.EqualTo(40.5));
            Assert.That(rectangle.GetProperty("width").GetDouble(), Is.EqualTo(20.25));
            Assert.That(rectangle.GetProperty("height").GetDouble(), Is.EqualTo(9.5));
            Assert.That(layout.TryGetProperty("rows", out _), Is.False);
            Assert.That(layout.TryGetProperty("columns", out _), Is.False);
        });
    }

    [TestCase(-12.75)]
    [TestCase(0)]
    [TestCase(20.5)]
    public void RotationIsPreservedWithoutChangingTheObservedRectangle(double angle)
    {
        JsonElement layout = Result([new("word", [new("word", 1, 2, 3, 4)])], angle: angle)
            .GetProperty("layout");

        Assert.Multiple(() =>
        {
            Assert.That(layout.GetProperty("textAngleDegrees").GetDouble(), Is.EqualTo(angle));
            Assert.That(layout.GetProperty("rotationApplied").GetBoolean(), Is.False);
            Assert.That(layout.GetProperty("boundingRectFrame").GetString(), Is.EqualTo("windows_media_ocr_text_angle"));
            Assert.That(layout.GetProperty("lines")[0].GetProperty("words")[0]
                .GetProperty("boundingRect").GetProperty("x").GetDouble(), Is.EqualTo(1));
        });
    }

    [TestCase(double.NaN, 0, 1, 1)]
    [TestCase(0, double.PositiveInfinity, 1, 1)]
    [TestCase(0, 0, double.PositiveInfinity, 1)]
    [TestCase(0, 0, 1, double.NaN)]
    [TestCase(-0.1, 0, 1, 1)]
    [TestCase(0, -1, 1, 1)]
    [TestCase(0, 0, 0, 1)]
    [TestCase(0, 0, 1, -1)]
    [TestCase(99, 0, 1.01, 1)]
    [TestCase(0, 49, 1, 1.01)]
    [TestCase(double.MaxValue, 0, double.MaxValue, 1)]
    public void InvalidWordBoundsRejectTheWholeObservation(double x, double y, double width, double height)
    {
        Assert.Throws<InvalidDataException>(() => Result(
            [new("valid", [new("valid", 1, 1, 1, 1)]), new("bad", [new("bad", x, y, width, height)])]));
    }

    [TestCase(double.NaN)]
    [TestCase(double.PositiveInfinity)]
    [TestCase(double.NegativeInfinity)]
    public void NonfiniteAnglesCannotProduceVerifiedGeometry(double angle) =>
        Assert.Throws<InvalidDataException>(() => Result([], angle: angle));

    [TestCase(0, 50)]
    [TestCase(100, -1)]
    public void InvalidImageDimensionsAreRejected(int width, int height) =>
        Assert.Throws<InvalidDataException>(() => CaptureOcrLayout.CreateResult(
            "capture_test", "es-ES", "", ImageDigest, width, height, RecognizedAt, null, []));

    [TestCase("")]
    [TestCase("not-a-sha256")]
    public void MissingImageDigestCannotClaimImageProvenance(string digest) =>
        Assert.Throws<InvalidDataException>(() => Result([], digest: digest));

    [Test]
    public void FlatBackendExplicitlyWithholdsGeometry()
    {
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject();
            CaptureOcrLayout.WriteUnavailable(writer);
            writer.WriteEndObject();
        });
        JsonElement layout = result.GetProperty("layout");
        Assert.Multiple(() =>
        {
            Assert.That(layout.GetProperty("available").GetBoolean(), Is.False);
            Assert.That(layout.GetProperty("reason").GetString(), Is.EqualTo("backend_returns_flat_text"));
            Assert.That(layout.TryGetProperty("lines", out _), Is.False);
            Assert.That(layout.TryGetProperty("textAngleDegrees", out _), Is.False);
            Assert.That(layout.TryGetProperty("coordinateSystem", out _), Is.False);
        });
    }

    [Test]
    public async Task ImageHashAndDecoderShareAHandleThatDeniesMutationAndReplacement()
    {
        string path = Path.Combine(Path.GetTempPath(), "BaxyOcr_" + Guid.NewGuid().ToString("N") + ".bmp");
        byte[] bytes = Convert.FromHexString(
            "424D3E0000000000000036000000280000000200000001000000010018000000000008000000000000000000000000000000000000000000FF00FF000000");
        await File.WriteAllBytesAsync(path, bytes);
        await File.WriteAllBytesAsync(path + ".replacement", bytes);
        try
        {
            using FileStream image = CaptureVisionAdapter.OpenOcrImage(path);
            string digest = await CaptureVisionAdapter.HashOcrImageAsync(image, CancellationToken.None);
            Assert.Throws<IOException>(() => File.WriteAllBytes(path, bytes));
            Assert.Throws<IOException>(() => File.Delete(path));
            Assert.That(() => File.Move(path + ".replacement", path, overwrite: true),
                Throws.TypeOf<IOException>().Or.TypeOf<UnauthorizedAccessException>());
            Assert.That(await File.ReadAllBytesAsync(path), Is.EqualTo(bytes));
            Assert.That(image.Position, Is.Zero, "Decoder must start on the exact bytes hashed.");
            using global::Windows.Storage.Streams.IRandomAccessStream stream = image.AsRandomAccessStream();
            BitmapDecoder decoder = await BitmapDecoder.CreateAsync(stream);
            using SoftwareBitmap bitmap = await decoder.GetSoftwareBitmapAsync(
                BitmapPixelFormat.Bgra8, BitmapAlphaMode.Ignore);
            Assert.Multiple(() =>
            {
                Assert.That(digest, Is.EqualTo(Convert.ToHexStringLower(SHA256.HashData(bytes))));
                Assert.That(bitmap.PixelWidth, Is.EqualTo(2));
                Assert.That(bitmap.PixelHeight, Is.EqualTo(1));
            });
            JsonElement first = Result([], "same text", digest: digest);
            bytes[^1] ^= 1;
            JsonElement second = Result([], "same text", digest: Convert.ToHexStringLower(SHA256.HashData(bytes)));
            Assert.Multiple(() =>
            {
                Assert.That(first.GetProperty("textSha256").GetString(), Is.EqualTo(second.GetProperty("textSha256").GetString()));
                Assert.That(first.GetProperty("imageSha256").GetString(), Is.Not.EqualTo(second.GetProperty("imageSha256").GetString()));
            });
        }
        finally
        {
            File.Delete(path);
            File.Delete(path + ".replacement");
        }
    }

    // PAN1 (VIVO10B, VIVO11: «Mira mi pantalla» on BAXY's own window said «88 capacidades»): the grid icon before
    // «Capacidades 191» is read by OCR as «88». The window gives that row's text exactly («Capacidades 191»), so a word
    // the OCR read inside the row and the row's text does not hold is not given, and the row's text goes as it is.
    [Test]
    public void AnOcrWordInsideAnAccessibleTextThatDoesNotHoldItIsNotGiven()
    {
        CaptureOcrLine row = Line(("88", 2, 30), ("Capacidades", 14, 30), ("191", 80, 30));
        CaptureOcrLine outside = Line(("Oferta", 2, 2), ("2x1", 30, 2));
        ScreenTextReading sifted = CaptureOcrLayout.Sift(
            [outside, row], [new AccessibleTextBox("Capacidades 191", 0, 26, 100, 14)]);
        JsonElement result = CaptureOcrLayout.CreateResult("capture_test", "es-ES", "Oferta 2x1 88 Capacidades 191",
            ImageDigest, 100, 50, RecognizedAt, null, [outside, row], sifted: sifted);

        Assert.Multiple(() =>
        {
            Assert.That(result.GetProperty("text").GetString(), Is.EqualTo("Oferta 2x1 Capacidades 191"));
            Assert.That(result.GetProperty("text").GetString(), Does.Not.Contain("88"));
            Assert.That(sifted.Withheld, Is.EqualTo(1));
            Assert.That(sifted.WindowText, Is.EqualTo(new[] { "Capacidades 191" }));
            Assert.That(result.GetProperty("layout").GetProperty("lines")[1].GetProperty("text").GetString(),
                Is.EqualTo("Capacidades 191"));
            // Measured (PAN1 lot 4): the window's texts beside the OCR made the model stop reading a picture's text.
            Assert.That(result.TryGetProperty("windowText", out _), Is.False);
        });
    }

    // PAN1 held-out: an icon beside a one-word label is half of the words inside the box, and a number the OCR read
    // without its comma («48» for «4,8») is the other word of a two-word label.
    [Test]
    public void AnIconBesideAOneWordLabelIsNotGiven()
    {
        ScreenTextReading sifted = CaptureOcrLayout.Sift(
            [Line(("®", 2, 2), ("Ajustes", 14, 2)), Line(("Calificación", 2, 30), ("48", 70, 30))],
            [new AccessibleTextBox("Ajustes", 0, 0, 100, 14), new AccessibleTextBox("Calificación 4,8", 0, 26, 100, 14)]);

        Assert.Multiple(() =>
        {
            Assert.That(sifted.Lines.Select(static line => line.Text), Is.EqualTo(new[] { "Ajustes", "Calificación" }));
            Assert.That(sifted.WindowText, Is.EqualTo(new[] { "Ajustes", "Calificación 4,8" }));
            Assert.That(sifted.Withheld, Is.EqualTo(2));
        });
    }

    // PAN1 (VIVO11 f1e): the OCR put the grid icon («88») on a line with a word outside the panel, apart from its label.
    [Test]
    public void AnIconTheOcrPutOnAnotherLineThanItsLabelIsNotGiven()
    {
        CaptureOcrLine across = Line(("memoria", 120, 30), ("88", 2, 31));
        CaptureOcrLine label = Line(("Capacidades", 14, 31), ("191", 80, 31));
        ScreenTextReading sifted = CaptureOcrLayout.Sift(
            [across, label], [new AccessibleTextBox("Capacidades 191", 0, 26, 100, 14)]);

        Assert.Multiple(() =>
        {
            Assert.That(sifted.Lines.Select(static line => line.Text), Is.EqualTo(new[] { "memoria", "Capacidades 191" }));
            Assert.That(sifted.Withheld, Is.EqualTo(1));
        });
    }

    // PAN1 held-out (lot 2): a picture's text inside a link named otherwise shares a word with the name («se»), but most of
    // its line is not the name's words: it is read as the OCR read it, beside the name's own line.
    [Test]
    public void APictureTextInsideALinkNamedOtherwiseIsStillRead()
    {
        CaptureOcrLine picture = Line(("SE", 2, 2), ("ALQUILA", 30, 2));
        CaptureOcrLine title = Line(("Los", 2, 30), ("locales", 20, 30), ("se", 50, 30), ("duplican", 70, 30));
        ScreenTextReading sifted = CaptureOcrLayout.Sift(
            [picture, title], [new AccessibleTextBox("Los locales se duplican", 0, 0, 100, 44)]);

        Assert.Multiple(() =>
        {
            Assert.That(sifted.Withheld, Is.Zero);
            Assert.That(sifted.Lines.Select(static line => line.Text),
                Is.EqualTo(new[] { "SE ALQUILA", "Los locales se duplican" }));
        });
    }

    // What has no accessible text (an image's, a video's, an app without accessibility) is read by OCR as before, and a
    // box whose words the capture mostly does not show (a picture under a link, a window that changed) is not used.
    [Test]
    public void TextWithoutAnAccessibleBoxOrUnderABoxItDoesNotMatchIsStillRead()
    {
        CaptureOcrLine picture = Line(("HOY", 2, 2), ("2x1", 20, 2), ("PIZZA", 40, 2));
        ScreenTextReading sifted = CaptureOcrLayout.Sift(
            [picture], [new AccessibleTextBox("Vídeo de cocina casera", 0, 0, 100, 14)]);

        Assert.Multiple(() =>
        {
            Assert.That(sifted.Withheld, Is.Zero);
            Assert.That(sifted.WindowText, Is.Empty);
            Assert.That(sifted.Lines.Single().Text, Is.EqualTo("HOY 2x1 PIZZA"));
        });
    }

    private static CaptureOcrLine Line(params (string Text, double X, double Y)[] words) => new(
        string.Join(' ', words.Select(static word => word.Text)),
        [.. words.Select(static word => new CaptureOcrWord(word.Text, word.X, word.Y, 10, 8))]);

    private static JsonElement Result(
        IReadOnlyList<CaptureOcrLine> lines, string text = "original", double? angle = null, string? digest = null) =>
        CaptureOcrLayout.CreateResult("capture_test", "es-ES", text, digest ?? ImageDigest,
            100, 50, RecognizedAt, angle, lines);
}
