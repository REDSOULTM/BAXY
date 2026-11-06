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
            Assert.That(saved.Subdirectory, Is.Empty);
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

        // P2.44 causa 11 (V11D169): the copy says the subfolder it went into, so where it is can be told and found.
        Assert.Multiple(() =>
        {
            Assert.That(File.Exists(Path.Combine(pictures, "Screenshots", saved.FileName)), Is.True);
            Assert.That(saved.Subdirectory, Is.EqualTo("Screenshots"));
        });
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

    // Banco de uso 03-11 (U23, «hazme un pantallazo y déjalo guardado en la carpeta …»): a capture was kept only in the
    // known folders, and the folder the person named was refused. A copy also goes to a folder of theirs given by its
    // path, read as a file tool's (PersonFolders.Place): a name alone is in their home.
    [Test]
    public async Task ACopyGoesToAFolderOfThePersonsGivenByItsPath()
    {
        using Folder root = new();
        string home = Directory.CreateDirectory(Path.Combine(root.Path, "home")).FullName;
        string named = Directory.CreateDirectory(Path.Combine(home, "carpeta-prueba")).FullName;
        WindowsScreenshotProvider provider = Provider(root, folder => folder == "home" ? home : null);

        CaptureResult capture = await provider.CaptureAsync(CancellationToken.None);
        SavedCaptureCopy saved = await provider.SaveCopyAtAsync(
            capture.CaptureId, "carpeta-prueba", Filesystem.PersonFolders.PathLabels("capture.screenshot"),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(File.Exists(Path.Combine(named, saved.FileName)), Is.True);
            Assert.That(saved.Folder, Is.EqualTo("home"));
            Assert.That(saved.Subdirectory, Is.EqualTo("carpeta-prueba"));
            Assert.That(Directory.GetFiles(home), Is.Empty);
        });
    }

    // The capture's call takes that path («path», as a file tool's) and its result says where the copy went.
    [Test]
    public async Task ACaptureWithAPathIsSavedThereAndSaysWhere()
    {
        using Folder root = new();
        string home = Directory.CreateDirectory(Path.Combine(root.Path, "home")).FullName;
        string named = Directory.CreateDirectory(Path.Combine(home, "carpeta-prueba")).FullName;
        var handler = new Baxy.Core.Operations.ScreenshotCaptureHandler(
            Provider(root, folder => folder == "home" ? home : null));

        Baxy.Kernel.Operations.OperationOutcome outcome = await handler.ExecuteAsync(
            new Baxy.Kernel.Operations.OperationInvocation("request", "mission", "invocation",
                System.Text.Json.JsonDocument.Parse("""{"path":"carpeta-prueba"}""").RootElement.Clone()),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(outcome.Succeeded, Is.True, outcome.ErrorCode);
            Assert.That(outcome.Result!.Value.GetProperty("savedFolder").GetString(), Is.EqualTo("home"));
            Assert.That(outcome.Result!.Value.GetProperty("savedSubdirectory").GetString(), Is.EqualTo("carpeta-prueba"));
            Assert.That(Directory.GetFiles(named, "*.png"), Has.Length.EqualTo(1));
        });
    }

    // A path outside the person's folders, or a folder that is not there, writes nothing.
    [TestCase("C:\\Windows", "known_path_outside_folder")]
    [TestCase("carpeta-que-no-hay", "capture_folder_unavailable")]
    [TestCase("..\\fuera", "known_path_outside_folder")]
    public async Task APathOutsideThePersonsFoldersOrNotThereWritesNothing(string path, string code)
    {
        using Folder root = new();
        string home = Directory.CreateDirectory(Path.Combine(root.Path, "home")).FullName;
        WindowsScreenshotProvider provider = Provider(root, folder => folder == "home" ? home : null);
        CaptureResult capture = await provider.CaptureAsync(CancellationToken.None);

        ScreenshotUnavailableException? failure = Assert.ThrowsAsync<ScreenshotUnavailableException>(
            async () => await provider.SaveCopyAtAsync(
                capture.CaptureId, path, Filesystem.PersonFolders.PathLabels("capture.screenshot"), CancellationToken.None));

        Assert.Multiple(() =>
        {
            Assert.That(failure!.Code, Is.EqualTo(code));
            Assert.That(Directory.GetFileSystemEntries(home), Is.Empty);
            Assert.That(Directory.GetFiles(root.Path, "*.png", SearchOption.AllDirectories), Is.Empty);
        });
    }

    // Encargo 17 (banco uso-cf8d, U23: «{folder:"pictures", path:"<carpeta>/pantallazo.png"}» failed as
    // capture_folder_unavailable alone). The failure says the facts: the known folder the path was read in, the part of
    // it that is there and the first part that is not (and whether a file holds that name), that the path is a folder, and
    // the person's folders of that name under their known folders (searched as a file's name is, bounded), each as a path
    // the call takes. Nothing is written.
    [Test]
    public async Task AFolderThatIsNotThereSaysWhatPartIsMissingAndWhereFoldersOfThatNameAre()
    {
        using Folder root = new();
        string home = Directory.CreateDirectory(Path.Combine(root.Path, "home")).FullName;
        string pictures = Directory.CreateDirectory(Path.Combine(home, "Pictures")).FullName;
        Directory.CreateDirectory(Path.Combine(home, "carpeta-prueba"));
        File.WriteAllText(Path.Combine(home, "carpeta-prueba", "nota.txt"), "x");
        var handler = new Baxy.Core.Operations.ScreenshotCaptureHandler(Provider(root,
            folder => folder switch { "home" => home, "pictures" => pictures, _ => null }));

        async Task<Baxy.Kernel.Operations.OperationOutcome> Capture(string arguments) => await handler.ExecuteAsync(
            new Baxy.Kernel.Operations.OperationInvocation("request", "mission", "invocation",
                System.Text.Json.JsonDocument.Parse(arguments).RootElement.Clone()),
            CancellationToken.None);

        Baxy.Kernel.Operations.OperationOutcome withName = await Capture(
            """{"folder":"pictures","path":"carpeta-prueba/captura.png"}""");
        Baxy.Kernel.Operations.OperationOutcome elsewhere = await Capture("""{"path":"imagenes/carpeta-prueba"}""");
        Baxy.Kernel.Operations.OperationOutcome aFile = await Capture("""{"path":"carpeta-prueba/nota.txt"}""");

        Assert.Multiple(() =>
        {
            Assert.That(withName.ErrorCode, Is.EqualTo("capture_folder_unavailable"));
            System.Text.Json.JsonElement said = withName.Result!.Value;
            Assert.That(said.GetProperty("folder").GetString(), Is.EqualTo("home"));
            Assert.That(said.GetProperty("existingPath").GetString(), Is.EqualTo(@"home\carpeta-prueba"));
            Assert.That(said.GetProperty("missingPart").GetString(), Is.EqualTo("captura.png"));
            Assert.That(said.GetProperty("pathIsAFolder").GetBoolean(), Is.True);
            Assert.That(said.GetProperty("foldersNamedLikeIt").GetArrayLength(), Is.Zero);
            Assert.That(said.GetProperty("searchComplete").GetBoolean(), Is.True);

            Assert.That(elsewhere.ErrorCode, Is.EqualTo("capture_folder_unavailable"));
            System.Text.Json.JsonElement other = elsewhere.Result!.Value;
            Assert.That(other.GetProperty("folder").GetString(), Is.EqualTo("pictures"));
            Assert.That(other.GetProperty("existingPath").GetString(), Is.EqualTo("pictures"));
            Assert.That(other.GetProperty("missingPart").GetString(), Is.EqualTo("carpeta-prueba"));
            Assert.That(other.GetProperty("foldersNamedLikeIt").EnumerateArray().Select(item => item.GetString()),
                Is.EqualTo(new[] { @"home\carpeta-prueba" }));

            Assert.That(aFile.Result!.Value.GetProperty("missingPartIsAFile").GetBoolean(), Is.True);
            Assert.That(Directory.GetFiles(root.Path, "*.png", SearchOption.AllDirectories), Is.Empty);
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
