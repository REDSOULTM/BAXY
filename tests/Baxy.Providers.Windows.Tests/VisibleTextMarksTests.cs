using System.Runtime.InteropServices.WindowsRuntime;
using Baxy.Providers.Windows.External;
using NUnit.Framework;
using Windows.Graphics.Imaging;
using Windows.Storage.Streams;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// v3 punto 5 (live 2026-10-07 v2-s12, v2-c17): a game launcher drawn without an accessible tree, already on its
/// library, was told «Parece que ya estabas…». Its row of navigation labels marks the page it is on by the colour of
/// the label's ink. The fixtures are the navigation row cropped from the bench's own captures (after.png of v2-c17 and
/// v2-g1 on the library, v2-x10 on the store), with the words' boxes measured on those pixels. The last label, the
/// account's name, is replaced by «.MODO_DEMO.™» assembled from white glyphs of the same row (no account is published).
/// </summary>
[TestFixture]
public sealed class VisibleTextMarksTests
{
    // Measured on the crops (rows 18–42 of the 768×432 after.png): the glyphs of the row span rows 7–15.
    private static readonly (string Text, int X, int W)[] LibraryRow =
        [("TIENDA", 49, 40), ("BIBLIOTECA", 102, 64), ("COMUNIDAD", 179, 69), (".MODO_DEMO.™", 261, 90)];

    private static readonly (string Text, int X, int W)[] StoreRow =
        [("TIENDA", 48, 41), ("BIBLIOTECA", 102, 64), ("COMUNIDAD", 179, 69), (".MODO_DEMO.™", 261, 90)];

    [TestCase("steam-library-c17.png")]
    [TestCase("steam-library-g1.png")]
    public async Task OnTheLibraryOnlyItsLabelIsWrittenInAnotherInk(string fixture)
    {
        Dictionary<string, VisibleTextMarks.Mark> marks = await MarksAsync(fixture, LibraryRow);

        Assert.Multiple(() =>
        {
            Assert.That(marks["BIBLIOTECA"].Ink, Is.EqualTo("blue"));
            foreach (string other in new[] { "TIENDA", "COMUNIDAD", ".MODO_DEMO.™" })
            {
                // The others are written in one colourless ink, as bright as each other.
                Assert.That(marks[other].Ink, Is.AnyOf("white", "gray"), other);
                Assert.That(marks[other].InkValue, Is.EqualTo(marks["TIENDA"].InkValue).Within(24), other);
            }

            // The launcher writes light labels on a dark bar: the background is measured apart from the ink.
            foreach (VisibleTextMarks.Mark mark in marks.Values)
            {
                Assert.That(mark.InkValue - mark.BackgroundValue, Is.GreaterThan(64), mark.Text);
            }
        });
    }

    [Test]
    public async Task OnTheStoreTheLibraryLabelIsWrittenLikeItsNeighbours()
    {
        // Contracase: the same row on the store marks «TIENDA», never «BIBLIOTECA».
        Dictionary<string, VisibleTextMarks.Mark> marks = await MarksAsync("steam-store-x10.png", StoreRow);

        Assert.Multiple(() =>
        {
            Assert.That(marks["TIENDA"].Ink, Is.EqualTo("blue"));
            foreach (string other in new[] { "BIBLIOTECA", "COMUNIDAD", ".MODO_DEMO.™" })
            {
                Assert.That(marks[other].Ink, Is.AnyOf("white", "gray"), other);
                Assert.That(marks[other].InkValue, Is.EqualTo(marks["BIBLIOTECA"].InkValue).Within(24), other);
            }
        });
    }

    [Test]
    public async Task ARowReadAsOneLineIsSplitIntoItsLabelsAndTheSecondPassIsNotCountedTwice()
    {
        (byte[] bmp, _, _) = await BitmapAsync("steam-library-c17.png");
        WindowsVisibleOcrLocator.LayoutWord[] words = [.. LibraryRow.Select(word => Word(word.Text, word.X, word.W))];
        // The first pass reads the whole row as one line; the darker pass reads «BIBLIOTECA COMUNIDAD» apart.
        WindowsVisibleOcrLocator.LayoutLine[] lines =
        [
            Line(words),
            Line([words[1], words[2]]),
        ];

        List<VisibleTextMarks.Mark> marks = VisibleTextMarks.Read(bmp, 100, 200, lines);

        Assert.Multiple(() =>
        {
            Assert.That(marks.Select(mark => mark.Text), Is.EqualTo(LibraryRow.Select(word => word.Text)));
            // In the window's coordinates: the capture's own pixels moved by its origin.
            Assert.That(marks[1].X, Is.EqualTo(102 + 100));
            Assert.That(marks[1].Y, Is.EqualTo(7 + 200));
            // The zone is the capture's (§1.4): on this 24-row strip the row is its middle third, left column.
            Assert.That(marks[1].Zone, Is.EqualTo("L"));
        });
    }

    [Test]
    public void TheWordsOfOneLabelStayTogether()
    {
        // «Ver Amigos» is one label: its words are closer than the line is tall.
        WindowsVisibleOcrLocator.LayoutLine line = Line([Word("Formas", 316, 30), Word("de", 349, 10), Word("jugar", 362, 22)]);

        Assert.That(VisibleTextMarks.Labels(line).Select(label => label.Text), Is.EqualTo(new[] { "Formas de jugar" }));
    }

    [Test]
    public void ABoxWithoutInkTellsNoColour()
    {
        byte[] bmp = Bmp(16, 16, (_, _) => (30, 30, 30));
        Assert.That(VisibleControlColors.TryParse(bmp, out int offset, out int width, out int height), Is.True);

        // The background is still measured (30): only the ink is missing.
        Assert.That(VisibleTextMarks.Ink(bmp, offset, width, height, 4, 4, 8, 8), Is.EqualTo((string.Empty, 0, 30)));
    }

    private static async Task<Dictionary<string, VisibleTextMarks.Mark>> MarksAsync(
        string fixture, (string Text, int X, int W)[] row)
    {
        (byte[] bmp, _, _) = await BitmapAsync(fixture);
        List<VisibleTextMarks.Mark> marks = VisibleTextMarks.Read(
            bmp, 0, 0, [Line([.. row.Select(word => Word(word.Text, word.X, word.W))])]);
        TestContext.Out.WriteLine(string.Join("; ", marks.Select(mark => $"{mark.Text}={mark.Ink}/{mark.InkValue}/{mark.BackgroundValue}")));
        return marks.ToDictionary(mark => mark.Text);
    }

    private static WindowsVisibleOcrLocator.LayoutWord Word(string text, int x, int width) => new(text, x, 7, width, 9);

    private static WindowsVisibleOcrLocator.LayoutLine Line(IReadOnlyList<WindowsVisibleOcrLocator.LayoutWord> words)
    {
        double x0 = words.Min(word => word.X);
        double x1 = words.Max(word => word.X + word.Width);
        return new WindowsVisibleOcrLocator.LayoutLine(
            string.Join(' ', words.Select(word => word.Text)), x0, 7, x1 - x0, 9, words);
    }

    private static async Task<(byte[] Bmp, int Width, int Height)> BitmapAsync(string fixture)
    {
        byte[] png = await File.ReadAllBytesAsync(Path.Combine(
            AppContext.BaseDirectory, "Fixtures", "TextMarks", fixture));
        using var stream = new InMemoryRandomAccessStream();
        await stream.WriteAsync(png.AsBuffer());
        stream.Seek(0);
        BitmapDecoder decoder = await BitmapDecoder.CreateAsync(stream);
        PixelDataProvider pixels = await decoder.GetPixelDataAsync(
            BitmapPixelFormat.Bgra8, BitmapAlphaMode.Ignore, new BitmapTransform(),
            ExifOrientationMode.IgnoreExifOrientation, ColorManagementMode.DoNotColorManage);
        byte[] bgra = pixels.DetachPixelData();
        int width = (int)decoder.PixelWidth;
        int height = (int)decoder.PixelHeight;
        return (Bmp(width, height, (x, y) =>
        {
            int index = (y * width + x) * 4;
            return (bgra[index + 2], bgra[index + 1], bgra[index]);
        }), width, height);
    }

    // A bottom-up 32-bit BMP, the shape of the window capture.
    private static byte[] Bmp(int width, int height, Func<int, int, (byte R, byte G, byte B)> pixel)
    {
        const int Offset = 54;
        byte[] bmp = new byte[Offset + width * height * 4];
        bmp[0] = (byte)'B';
        bmp[1] = (byte)'M';
        BitConverter.GetBytes(bmp.Length).CopyTo(bmp, 2);
        BitConverter.GetBytes(Offset).CopyTo(bmp, 10);
        BitConverter.GetBytes(40).CopyTo(bmp, 14);
        BitConverter.GetBytes(width).CopyTo(bmp, 18);
        BitConverter.GetBytes(height).CopyTo(bmp, 22);
        BitConverter.GetBytes((short)1).CopyTo(bmp, 26);
        BitConverter.GetBytes((short)32).CopyTo(bmp, 28);
        for (int y = 0; y < height; y++)
        {
            for (int x = 0; x < width; x++)
            {
                (byte r, byte g, byte b) = pixel(x, y);
                int index = Offset + ((height - 1 - y) * width + x) * 4;
                bmp[index] = b;
                bmp[index + 1] = g;
                bmp[index + 2] = r;
                bmp[index + 3] = 255;
            }
        }

        return bmp;
    }
}
