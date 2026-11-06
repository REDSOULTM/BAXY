using System.Runtime.InteropServices;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;
using Windows.Media.Ocr;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// Encargo 119 (F10): the real engine over text drawn here, never a receipt written by hand. Text of 10 px came back as
/// nonsense, a paragraph's long lines were left out of a look, and the darkened pass gave one line twice.
/// </summary>
[TestFixture]
public sealed class OcrReadsWhatIsDrawnTests
{
    private const string SmallLine = "El código del portón es 4471 y la llave está bajo la maceta azul";
    private const string LongLine =
        "Quienes tengan estanque deben cerrar la válvula amarilla antes de esa hora y avisar en la portería del edificio";

    [DllImport("gdi32.dll")] private static extern nint CreateCompatibleDC(nint dc);
    [DllImport("gdi32.dll")] private static extern nint CreateDIBSection(nint dc, in BitmapInfoHeader info, uint usage, out nint bits, nint section, uint offset);
    [DllImport("gdi32.dll")] private static extern nint SelectObject(nint dc, nint item);
    [DllImport("gdi32.dll", CharSet = CharSet.Unicode)]
    private static extern nint CreateFontW(int height, int width, int escapement, int orientation, int weight, uint italic, uint underline, uint strike,
        uint charset, uint precision, uint clip, uint quality, uint pitch, string face);
    [DllImport("gdi32.dll", CharSet = CharSet.Unicode)] private static extern bool TextOutW(nint dc, int x, int y, string text, int length);
    [DllImport("gdi32.dll")] private static extern bool DeleteObject(nint item);
    [DllImport("gdi32.dll")] private static extern bool DeleteDC(nint dc);

    [StructLayout(LayoutKind.Sequential)]
    private struct BitmapInfoHeader
    {
        public uint Size;
        public int Width, Height;
        public ushort Planes, BitCount;
        public uint Compression, SizeImage;
        public int XPelsPerMeter, YPelsPerMeter;
        public uint ClrUsed, ClrImportant;
    }

    // Text drawn by GDI with the font height asked, as a window without accessibility paints it, into a 24-bit BMP.
    private static byte[] Drawn(int pixels, params string[] lines)
    {
        const int width = 1400;
        int height = 40 + lines.Length * pixels * 2;
        int stride = (width * 3 + 3) / 4 * 4;
        var info = new BitmapInfoHeader
        {
            Size = (uint)Marshal.SizeOf<BitmapInfoHeader>(), Width = width, Height = height, Planes = 1, BitCount = 24,
        };
        nint dc = CreateCompatibleDC(0);
        nint section = CreateDIBSection(dc, info, 0, out nint bits, 0, 0);
        // 5: CLEARTYPE_QUALITY, what a window's text is drawn with.
        nint font = CreateFontW(-pixels, 0, 0, 0, 400, 0, 0, 0, 1, 0, 0, 5, 0, "Segoe UI");
        SelectObject(dc, section);
        SelectObject(dc, font);
        var pixelsOut = new byte[stride * height];
        Array.Fill(pixelsOut, (byte)255);
        Marshal.Copy(pixelsOut, 0, bits, pixelsOut.Length);
        for (int line = 0; line < lines.Length; line++)
            TextOutW(dc, 20, 20 + line * pixels * 2, lines[line], lines[line].Length);
        Marshal.Copy(bits, pixelsOut, 0, pixelsOut.Length);
        DeleteDC(dc);
        DeleteObject(section);
        DeleteObject(font);

        using var bmp = new MemoryStream();
        using var writer = new BinaryWriter(bmp);
        writer.Write((ushort)0x4D42);
        writer.Write(54 + pixelsOut.Length);
        writer.Write(0);
        writer.Write(54);
        writer.Write(40);
        writer.Write(width);
        writer.Write(height);
        writer.Write((ushort)1);
        writer.Write((ushort)24);
        writer.Write(new byte[24]);
        writer.Write(pixelsOut);
        writer.Flush();
        return bmp.ToArray();
    }

    private static void NeedsTheEngine()
    {
        if (OcrEngine.TryCreateFromUserProfileLanguages() is null)
            Assert.Ignore("Windows has no OCR for this profile's languages.");
    }

    [Test]
    public async Task TheCaptureReadReadsSmallTextAndKeepsTheImagesPixels()
    {
        NeedsTheEngine();
        string folder = Path.Combine(Path.GetTempPath(), "BaxyOcr119_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(folder);
        try
        {
            string id = "capture_" + new string('b', 32);
            byte[] bmp = Drawn(10, SmallLine);
            await File.WriteAllBytesAsync(Path.Combine(folder, id + ".bmp"), bmp);
            using var adapter = new CaptureVisionAdapter(folder);
            using JsonDocument arguments = JsonDocument.Parse($$"""{"captureId":"{{id}}"}""");

            ExternalCapabilityReceipt read = await adapter.InvokeAsync("ocr.read", arguments.RootElement, CancellationToken.None);

            JsonElement result = read.Result!.Value;
            JsonElement word = result.GetProperty("layout").GetProperty("lines")[0].GetProperty("words")[0].GetProperty("boundingRect");
            Assert.Multiple(() =>
            {
                Assert.That(read.Verified, Is.True);
                Assert.That(result.GetProperty("text").GetString(), Does.Contain("4471").And.Contain("maceta"));
                Assert.That(result.GetProperty("imageWidth").GetInt32(), Is.EqualTo(1400));
                Assert.That(word.GetProperty("x").GetDouble(), Is.LessThan(40), "The first word is drawn at x=20 of the image.");
            });
        }
        finally
        {
            Directory.Delete(folder, recursive: true);
        }
    }

    [Test]
    public async Task AReadingLookReadsSmallTextInCapturePixels()
    {
        NeedsTheEngine();
        IReadOnlyList<WindowsVisibleOcrLocator.LayoutLine>? lines = await WindowsVisibleOcrLocator.ReadLayoutAsync(
            Drawn(10, SmallLine), 40, CancellationToken.None, reading: true);

        Assert.That(lines, Is.Not.Null.And.Not.Empty);
        Assert.Multiple(() =>
        {
            Assert.That(string.Join(' ', lines!.Select(line => line.Text)), Does.Contain("4471").And.Contain("maceta"));
            Assert.That(lines![0].X, Is.LessThan(40), "The line is drawn at x=20 of the capture.");
            Assert.That(lines![0].Y, Is.LessThan(40), "The line is drawn at y=20 of the capture.");
        });
    }

    [Test]
    public async Task AReadingLookKeepsALongLineAndALabelLookStillLeavesItOut()
    {
        NeedsTheEngine();
        var omitted = new System.Runtime.CompilerServices.StrongBox<int>();
        IReadOnlyList<WindowsVisibleOcrLocator.LayoutLine>? reading = await WindowsVisibleOcrLocator.ReadLayoutAsync(
            Drawn(18, LongLine), 40, CancellationToken.None, reading: true);
        IReadOnlyList<WindowsVisibleOcrLocator.LayoutLine>? labels = await WindowsVisibleOcrLocator.ReadLayoutAsync(
            Drawn(18, LongLine), 40, CancellationToken.None, omitted: omitted);

        Assert.Multiple(() =>
        {
            Assert.That(string.Join(' ', reading!.Select(line => line.Text)), Does.Contain("válvula amarilla").And.Contain("portería"));
            Assert.That(labels, Is.Empty, "A look for a label's place has no use for a sentence.");
            Assert.That(omitted.Value, Is.GreaterThan(0), "What a label look leaves out is still counted.");
        });
    }

    [Test]
    public void TwoSpellingsOfOneLineAreOnePlaceAndTwoLinesAreNot()
    {
        var first = new WindowsVisibleOcrLocator.LayoutLine("a las 19:40", 20, 100, 300, 20);
        var again = new WindowsVisibleOcrLocator.LayoutLine("a las 1940", 22, 101, 290, 19);
        var below = new WindowsVisibleOcrLocator.LayoutLine("a las 19:40", 20, 130, 300, 20);
        var beside = new WindowsVisibleOcrLocator.LayoutLine("otra", 330, 100, 80, 20);

        Assert.Multiple(() =>
        {
            Assert.That(WindowsVisibleOcrLocator.SamePlace(first, again), Is.True);
            Assert.That(WindowsVisibleOcrLocator.SamePlace(first, below), Is.False);
            Assert.That(WindowsVisibleOcrLocator.SamePlace(first, beside), Is.False);
        });
    }

    // Live: the model named the window as its title starts, and pressed the title when nothing was found.
    [Test]
    public void ANameReadOffATitleIsThatWindowsProcessWhenOneWindowHoldsIt()
    {
        VisibleControlSurface.DestinationWindow[] desktop =
        [
            new("VisorPrueba", "Visor de Prueba - aviso.png"),
            new("OtraCosa", "Otra cosa"),
        ];

        Assert.Multiple(() =>
        {
            Assert.That(WindowsVisibleControlAdapter.OnlyWindowTitled("Visor de Prueba", desktop), Is.EqualTo("VisorPrueba"));
            Assert.That(WindowsVisibleControlAdapter.OnlyWindowTitled("Prueba de Visor", desktop), Is.Null);
            Assert.That(WindowsVisibleControlAdapter.OnlyWindowTitled(
                "Visor", [new("VisorPrueba", "Visor uno"), new("OtroVisor", "Visor dos")]), Is.Null, "Two windows hold it.");
            Assert.That(WindowsVisibleControlAdapter.OnlyWindowTitled("Visor", [new("cmd", "Visor de Prueba - consola")]),
                Is.Null, "A protected window is never named here.");
        });
    }

    private static WindowsVisibleOcrLocator.LayoutLine At(string text, double x, double y) => new(text, x, y, 100, 20);

    // Live: a price table told as «Tornillo M4 con 120 unidades a 75».
    [Test]
    public void ShortLinesOnOneRowAreOneLineAndEachRowItsOwn()
    {
        WindowsVisibleOcrLocator.LayoutLine[] read =
        [
            At("Tornillo M4", 30, 100), At("120", 330, 101), At("3,40", 630, 100),
            At("Arandela", 30, 150), At("75", 330, 150), At("0,95", 630, 151),
        ];

        IReadOnlyList<WindowsVisibleOcrLocator.LayoutLine> rows = WindowsVisibleOcrLocator.CellsAsRows(read, static _ => false);

        Assert.Multiple(() =>
        {
            Assert.That(rows.Select(static row => row.Text), Is.EqualTo(new[] { "Tornillo M4 · 120 · 3,40", "Arandela · 75 · 0,95" }));
            Assert.That(rows[0].X + rows[0].Width, Is.EqualTo(730));
        });
    }

    [Test]
    public void SentencesInColumnsAndControlNamesStayAlone()
    {
        string sentence = new('a', 60);
        WindowsVisibleOcrLocator.LayoutLine[] columns = [At(sentence, 30, 100), At(sentence + "b", 600, 100)];
        WindowsVisibleOcrLocator.LayoutLine[] menu = [At("Archivo", 30, 10), At("Editar", 140, 10), At("Total 12", 250, 10)];

        Assert.Multiple(() =>
        {
            Assert.That(WindowsVisibleOcrLocator.CellsAsRows(columns, static _ => false), Has.Count.EqualTo(2));
            Assert.That(WindowsVisibleOcrLocator.CellsAsRows(menu, static text => text is "Archivo" or "Editar").Select(static row => row.Text),
                Is.EqualTo(new[] { "Archivo", "Editar", "Total 12" }));
        });
    }

    [Test]
    public void AWholeLargeScreenIsReadAtItsSize()
    {
        Assert.Multiple(() =>
        {
            Assert.That(WindowsVisibleOcrLocator.ReadingScaleOf(1920, 1080), Is.EqualTo(2));
            Assert.That(WindowsVisibleOcrLocator.ReadingScaleOf(2560, 1440), Is.EqualTo(2));
            Assert.That(WindowsVisibleOcrLocator.ReadingScaleOf(3840, 2160), Is.EqualTo(1));
            Assert.That(WindowsVisibleOcrLocator.ReadingScaleOf(1200, OcrEngine.MaxImageDimension), Is.EqualTo(1));
        });
    }
}
