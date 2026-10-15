using System.Buffers.Binary;
using System.Globalization;
using System.IO.Compression;
using System.Security.Cryptography;
using Baxy.Providers.Windows.Capture;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

// Ronda 22 (uso real r18 t2-c16 «toma una captura de pantalla y guárdala en mis imágenes», t3-c11 «…y guárdala en el
// escritorio», t4-c09 «saca una captura de pantalla y guárdala»): the capture asked to be kept is saved as a PNG in the
// known folder named, verified on disk, and never overwrites. Every folder here is a temporary one.
[TestFixture]
public sealed class CaptureCopiesTests
{
    [Test]
    public async Task ACopyIsAVerifiedPngOfTheCaptureInTheKnownFolderNamed()
    {
        using Folder root = new();
        string desktop = Directory.CreateDirectory(Path.Combine(root.Path, "Desktop")).FullName;
        WindowsScreenshotProvider provider = Provider(root, folder => folder == "desktop" ? desktop : null);

        CaptureResult capture = await provider.CaptureAsync(CancellationToken.None);
        SavedCaptureCopy saved = await provider.SaveCopyAsync(capture.CaptureId, "desktop", CancellationToken.None);

        string file = Path.Combine(desktop, saved.FileName);
        byte[] png = File.ReadAllBytes(file);
        Assert.Multiple(() =>
        {
            Assert.That(saved.Folder, Is.EqualTo("desktop"));
            Assert.That(saved.FileName, Does.EndWith(".png"));
            Assert.That(Directory.GetFiles(desktop), Has.Length.EqualTo(1));
            Assert.That(Convert.ToHexStringLower(SHA256.HashData(png)), Is.EqualTo(saved.Sha256));
            Assert.That(png.AsSpan(0, 8).ToArray(), Is.EqualTo(new byte[] { 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A }));
            Assert.That(Pixels(png), Is.EqualTo((2, 1, new byte[] { 0, 255, 0, 0, 0, 255, 0 })));
            Assert.That(Path.GetFileName(Path.GetDirectoryName(file)), Is.EqualTo("Desktop"));
        });
    }

    [Test]
    public async Task PicturesGoesToItsScreenshotsSubfolder()
    {
        using Folder root = new();
        string pictures = Directory.CreateDirectory(Path.Combine(root.Path, "Pictures")).FullName;
        WindowsScreenshotProvider provider = Provider(root, folder => folder == "pictures" ? pictures : null);

        CaptureResult capture = await provider.CaptureAsync(CancellationToken.None);
        SavedCaptureCopy saved = await provider.SaveCopyAsync(capture.CaptureId, "pictures", CancellationToken.None);

        Assert.That(File.Exists(Path.Combine(pictures, "Screenshots", saved.FileName)), Is.True);
    }

    // Contracaso: two captures in the same second never overwrite each other, nor a file the person already has.
    [Test]
    public async Task TwoCopiesInARowNeverOverwriteEachOtherOrTheFolder()
    {
        using Folder root = new();
        string documents = Directory.CreateDirectory(Path.Combine(root.Path, "Documents")).FullName;
        WindowsScreenshotProvider provider = Provider(root, folder => folder == "documents" ? documents : null);
        CaptureResult first = await provider.CaptureAsync(CancellationToken.None);
        CaptureResult second = await provider.CaptureAsync(CancellationToken.None);

        SavedCaptureCopy one = await provider.SaveCopyAsync(first.CaptureId, "documents", CancellationToken.None);
        string persons = Path.Combine(documents, one.FileName.Replace(".png", " (2).png", StringComparison.Ordinal));
        File.WriteAllText(persons, "the person's own file");
        SavedCaptureCopy two = await provider.SaveCopyAsync(second.CaptureId, "documents", CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(two.FileName, Is.Not.EqualTo(one.FileName));
            Assert.That(two.FileName, Is.Not.EqualTo(Path.GetFileName(persons)));
            Assert.That(File.ReadAllText(persons), Is.EqualTo("the person's own file"));
            Assert.That(Directory.GetFiles(documents), Has.Length.EqualTo(3));
        });
    }

    [Test]
    public async Task AFolderThatIsNotThereIsAnHonestFailureAndWritesNothing()
    {
        using Folder root = new();
        WindowsScreenshotProvider provider = Provider(root, _ => Path.Combine(root.Path, "missing"));
        CaptureResult capture = await provider.CaptureAsync(CancellationToken.None);

        ScreenshotUnavailableException? failure = Assert.ThrowsAsync<ScreenshotUnavailableException>(
            async () => await provider.SaveCopyAsync(capture.CaptureId, "downloads", CancellationToken.None));

        Assert.Multiple(() =>
        {
            Assert.That(failure!.Code, Is.EqualTo("capture_folder_unavailable"));
            Assert.That(Directory.Exists(Path.Combine(root.Path, "missing")), Is.False);
        });
    }

    [Test]
    public void AnIdentityThatIsNotACaptureIsRefused()
    {
        using Folder root = new();
        WindowsScreenshotProvider provider = Provider(root, _ => root.Path);

        Assert.ThrowsAsync<IOException>(
            async () => await provider.SaveCopyAsync("..\\secret", "desktop", CancellationToken.None));
    }

    private static WindowsScreenshotProvider Provider(Folder root, Func<string, string?> knownFolder) =>
        new(Path.Combine(root.Path, "private"), new Platform(), new Clock()) { KnownFolder = knownFolder };

    private static (int Width, int Height, byte[] Rows) Pixels(byte[] png)
    {
        int width = 0, height = 0;
        using var data = new MemoryStream();
        for (int offset = 8; offset < png.Length;)
        {
            int length = BinaryPrimitives.ReadInt32BigEndian(png.AsSpan(offset));
            string type = System.Text.Encoding.ASCII.GetString(png, offset + 4, 4);
            byte[] body = png.AsSpan(offset + 8, length).ToArray();
            uint crc = BinaryPrimitives.ReadUInt32BigEndian(png.AsSpan(offset + 8 + length));
            Assert.That(crc, Is.EqualTo(CaptureCopies.Crc32(png.AsSpan(offset + 4, 4 + length))), type);
            if (type == "IHDR")
            {
                width = BinaryPrimitives.ReadInt32BigEndian(body);
                height = BinaryPrimitives.ReadInt32BigEndian(body.AsSpan(4));
            }
            else if (type == "IDAT")
            {
                data.Write(body);
            }

            offset += 12 + length;
        }

        data.Position = 0;
        using var inflated = new MemoryStream();
        using (var zlib = new ZLibStream(data, CompressionMode.Decompress))
            zlib.CopyTo(inflated);
        return (width, height, inflated.ToArray());
    }

    private sealed class Platform : IScreenshotPlatform
    {
        // BGRA bottom-up: a red pixel and a green one.
        public ScreenshotFrame CaptureVirtualScreen() => new(2, 1, [0, 0, 255, 255, 0, 255, 0, 255]);
        public ScreenshotFrame CaptureActiveWindow() => new(1, 1, [0, 0, 255, 255]);
    }

    private sealed class Clock : TimeProvider
    {
        public override DateTimeOffset GetUtcNow() => DateTimeOffset.UnixEpoch;
    }

    private sealed class Folder : IDisposable
    {
        public Folder()
        {
            Path = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "baxy-capture-copy-tests",
                Guid.NewGuid().ToString("N", CultureInfo.InvariantCulture));
            Directory.CreateDirectory(Path);
        }

        public string Path { get; }

        public void Dispose()
        {
            if (Directory.Exists(Path))
                Directory.Delete(Path, recursive: true);
        }
    }
}
