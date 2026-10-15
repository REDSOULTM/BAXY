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

    private static JsonElement Result(
        IReadOnlyList<CaptureOcrLine> lines, string text = "original", double? angle = null, string? digest = null) =>
        CaptureOcrLayout.CreateResult("capture_test", "es-ES", text, digest ?? ImageDigest,
            100, 50, RecognizedAt, angle, lines);
}
