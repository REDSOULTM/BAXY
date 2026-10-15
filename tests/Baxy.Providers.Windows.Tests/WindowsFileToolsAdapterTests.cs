using System.IO.Compression;
using System.Text;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// REOPEN1957 H0542/H0459/H0077 (D11): comprimir, abrir, fondo de escritorio y
/// descarga con postlectura propia, sobre una carpeta «conocida» temporal.
/// </summary>
[TestFixture]
public sealed class WindowsFileToolsAdapterTests
{
    private string _root = string.Empty;

    [SetUp]
    public void SetUp()
    {
        _root = Path.Combine(Path.GetTempPath(), "baxy-filetools-tests", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(_root);
    }

    [TearDown]
    public void TearDown()
    {
        try { Directory.Delete(_root, recursive: true); } catch (IOException) { }
    }

    private WindowsFileToolsAdapter Adapter(Func<string, CancellationToken, Task<(byte[], string)>>? fetch = null) =>
        new(folder => folder == "desktop" ? _root : null, fetch);

    [Test]
    public async Task AFolderIsZippedNextToItselfAndTheZipIsReadBack()
    {
        string folder = Path.Combine(_root, "Nueva carpeta");
        Directory.CreateDirectory(folder);
        File.WriteAllText(Path.Combine(folder, "Nuevo documento de texto.txt"), string.Empty);

        ExternalCapabilityReceipt receipt = await Adapter().InvokeAsync(
            "file.compress",
            JsonSerializer.SerializeToElement(new { folder = "desktop", name = "Nueva carpeta" }),
            CancellationToken.None);

        Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
        string zip = Path.Combine(_root, "Nueva carpeta.zip");
        using ZipArchive archive = ZipFile.OpenRead(zip);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.Result!.Value.GetProperty("zipName").GetString(), Is.EqualTo("Nueva carpeta.zip"));
            Assert.That(receipt.Result!.Value.GetProperty("entryCount").GetInt32(), Is.EqualTo(1));
            Assert.That(archive.Entries.Select(entry => entry.FullName), Does.Contain("Nueva carpeta/Nuevo documento de texto.txt"));
        });
    }

    [Test]
    public async Task ZippingWhatDoesNotExistOrTwiceIsAnHonestAbsence()
    {
        ExternalCapabilityReceipt missing = await Adapter().InvokeAsync(
            "file.compress", JsonSerializer.SerializeToElement(new { folder = "desktop", name = "nada" }), CancellationToken.None);
        File.WriteAllText(Path.Combine(_root, "a.txt"), "x");
        File.WriteAllText(Path.Combine(_root, "a.txt.zip"), "y");
        ExternalCapabilityReceipt twice = await Adapter().InvokeAsync(
            "file.compress", JsonSerializer.SerializeToElement(new { folder = "desktop", name = "a.txt" }), CancellationToken.None);
        ExternalCapabilityReceipt escape = await Adapter().InvokeAsync(
            "file.compress", JsonSerializer.SerializeToElement(new { folder = "desktop", name = "..\\secret" }), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(missing.ErrorCode, Is.EqualTo("file_not_found"));
            Assert.That(twice.ErrorCode, Is.EqualTo("zip_already_exists"));
            Assert.That(escape.ErrorCode, Is.EqualTo("file_name_invalid"));
            Assert.That(missing.EffectMayHaveOccurred | twice.EffectMayHaveOccurred | escape.EffectMayHaveOccurred, Is.False);
        });
    }

    [Test]
    public async Task OpeningAFileThatIsNotThereOrNotSafeTouchesNothing()
    {
        File.WriteAllText(Path.Combine(_root, "run.exe"), "x");
        ExternalCapabilityReceipt missing = await Adapter().InvokeAsync(
            "file.open", JsonSerializer.SerializeToElement(new { folder = "desktop", name = "nada.zip" }), CancellationToken.None);
        ExternalCapabilityReceipt unsafeFile = await Adapter().InvokeAsync(
            "file.open", JsonSerializer.SerializeToElement(new { folder = "desktop", name = "run.exe" }), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(missing.ErrorCode, Is.EqualTo("file_not_found"));
            Assert.That(unsafeFile.ErrorCode, Is.EqualTo("file_extension_not_openable"));
        });
    }

    // v3 ronda 3 (lugar M6): v3-15 «paisaje.jpg que está en Documentos\baxy-prueba-v3» terminó en file_not_found y
    // v3-18 lo buscó sólo en Imágenes. Se resuelve sin abrir nada: la ubicación es una lectura del disco.
    private static WindowsFileToolsAdapter TwoFolders(string documents, string pictures) =>
        new(folder => folder switch { "documents" => documents, "pictures" => pictures, _ => null }, null);

    [Test]
    public void AFileInASubfolderOfTheKnownFolderIsFoundByItsRelativePath()
    {
        string documents = Directory.CreateDirectory(Path.Combine(_root, "Documentos")).FullName;
        string pictures = Directory.CreateDirectory(Path.Combine(_root, "Imagenes")).FullName;
        string sub = Directory.CreateDirectory(Path.Combine(documents, "baxy-prueba-v3")).FullName;
        File.WriteAllText(Path.Combine(sub, "paisaje.jpg"), "x");

        (string? path, string folder, string? error) = TwoFolders(documents, pictures)
            .LocateOpenTarget("documents", "baxy-prueba-v3\\paisaje.jpg");

        Assert.Multiple(() =>
        {
            Assert.That(error, Is.Null);
            Assert.That(folder, Is.EqualTo("documents"));
            Assert.That(path, Is.EqualTo(Path.Combine(sub, "paisaje.jpg")));
        });
    }

    [Test]
    public void AFileNotInTheFolderSaidIsFoundWhenOnlyOneKnownFolderHasIt()
    {
        string documents = Directory.CreateDirectory(Path.Combine(_root, "Documentos")).FullName;
        string pictures = Directory.CreateDirectory(Path.Combine(_root, "Imagenes")).FullName;
        string sub = Directory.CreateDirectory(Path.Combine(documents, "baxy-prueba-v3")).FullName;
        File.WriteAllText(Path.Combine(sub, "paisaje.jpg"), "x");

        (string? path, string folder, string? error) = TwoFolders(documents, pictures)
            .LocateOpenTarget("pictures", "paisaje.jpg");

        Assert.Multiple(() =>
        {
            Assert.That(error, Is.Null);
            Assert.That(folder, Is.EqualTo("documents"));
            Assert.That(path, Is.EqualTo(Path.Combine(sub, "paisaje.jpg")));
        });
    }

    [Test]
    public void TwoFilesWithTheNameAreNotGuessedAndNoneIsAnHonestAbsence()
    {
        string documents = Directory.CreateDirectory(Path.Combine(_root, "Documentos")).FullName;
        string pictures = Directory.CreateDirectory(Path.Combine(_root, "Imagenes")).FullName;
        File.WriteAllText(Path.Combine(Directory.CreateDirectory(Path.Combine(documents, "a")).FullName, "foto.png"), "x");
        File.WriteAllText(Path.Combine(Directory.CreateDirectory(Path.Combine(pictures, "b")).FullName, "foto.png"), "x");
        WindowsFileToolsAdapter adapter = TwoFolders(documents, pictures);

        Assert.Multiple(() =>
        {
            Assert.That(adapter.LocateOpenTarget("documents", "foto.png"), Is.EqualTo(((string?)null, "documents", (string?)"file_ambiguous")));
            Assert.That(adapter.LocateOpenTarget("documents", "nada.png"), Is.EqualTo(((string?)null, "documents", (string?)"file_not_found")));
        });
    }

    // Revisión de la rama ruta: con subcarpetas en el nombre la persona dijo dónde
    // está; si no está ahí, otro archivo con el mismo nombre no lo reemplaza.
    [Test]
    public void ANameWithSubfoldersIsNotSearchedElsewhere()
    {
        string documents = Directory.CreateDirectory(Path.Combine(_root, "Documentos")).FullName;
        string pictures = Directory.CreateDirectory(Path.Combine(_root, "Imagenes")).FullName;
        File.WriteAllText(Path.Combine(Directory.CreateDirectory(Path.Combine(pictures, "otra")).FullName, "informe.docx"), "x");

        Assert.That(
            TwoFolders(documents, pictures).LocateOpenTarget("documents", "proyectoA\\informe.docx"),
            Is.EqualTo(((string?)null, "documents", (string?)"file_not_found")));
    }

    // Revisión de la rama ruta: una búsqueda cortada (tiempo o cancelación) no
    // prueba que el archivo hallado primero sea el único; el duplicado de una
    // carpeta posterior nunca se vio, así que no se abre ninguno.
    [Test]
    public void ASearchCutShortOpensNothingEvenWithOneMatchSeen()
    {
        string documents = Directory.CreateDirectory(Path.Combine(_root, "Documentos")).FullName;
        string pictures = Directory.CreateDirectory(Path.Combine(_root, "Imagenes")).FullName;
        File.WriteAllText(Path.Combine(Directory.CreateDirectory(Path.Combine(documents, "a")).FullName, "foto.png"), "x");
        File.WriteAllText(Path.Combine(Directory.CreateDirectory(Path.Combine(pictures, "b")).FullName, "foto.png"), "x");
        WindowsFileToolsAdapter adapter = TwoFolders(documents, pictures);
        using var cancelled = new CancellationTokenSource();
        cancelled.Cancel();

        Assert.Multiple(() =>
        {
            Assert.That(
                adapter.LocateOpenTarget("pictures", "foto.png", budget: TimeSpan.Zero),
                Is.EqualTo(((string?)null, "pictures", (string?)"file_search_incomplete")));
            Assert.That(
                adapter.LocateOpenTarget("pictures", "foto.png", cancellationToken: cancelled.Token),
                Is.EqualTo(((string?)null, "pictures", (string?)"file_search_incomplete")));
            // With time to look, both are seen and none is guessed.
            Assert.That(
                adapter.LocateOpenTarget("pictures", "foto.png").Error, Is.EqualTo("file_ambiguous"));
        });
    }

    [TestCase("..\\secreto.txt")]
    [TestCase("baxy\\..\\..\\secreto.txt")]
    [TestCase("C:\\Windows\\win.ini")]
    [TestCase("\\Windows\\win.ini")]
    [TestCase("a:b.txt")]
    public void ARelativePathNeverLeavesTheKnownFolder(string name)
    {
        string documents = Directory.CreateDirectory(Path.Combine(_root, "Documentos")).FullName;
        Assert.That(TwoFolders(documents, documents).LocateOpenTarget("documents", name).Error, Is.EqualTo("file_name_invalid"));
    }

    [TestCase("azul", 0, 78, 152)]
    [TestCase("Azul", 0, 78, 152)]
    [TestCase("#ff0000", 255, 0, 0)]
    [TestCase("00ff00", 0, 255, 0)]
    public void ColoursAreNamedOrHex(string color, int r, int g, int b) =>
        Assert.That(WindowsFileToolsAdapter.ParseColor(color), Is.EqualTo(((byte)r, (byte)g, (byte)b)));

    [Test]
    public async Task AnUnknownColourAndANonImageAreRefusedBeforeAnyChange()
    {
        File.WriteAllText(Path.Combine(_root, "notas.txt"), "x");
        ExternalCapabilityReceipt colour = await Adapter().InvokeAsync(
            "desktop.wallpaper.set", JsonSerializer.SerializeToElement(new { color = "turquesa brillante" }), CancellationToken.None);
        ExternalCapabilityReceipt text = await Adapter().InvokeAsync(
            "desktop.wallpaper.set", JsonSerializer.SerializeToElement(new { folder = "desktop", name = "notas.txt" }), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(colour.ErrorCode, Is.EqualTo("wallpaper_color_unknown"));
            Assert.That(text.ErrorCode, Is.EqualTo("wallpaper_file_not_an_image"));
            Assert.That(colour.EffectMayHaveOccurred | text.EffectMayHaveOccurred, Is.False);
        });
    }

    [Test]
    public async Task AFileIsDownloadedIntoTheKnownFolderAndItsSizeIsTheProof()
    {
        byte[] body = Encoding.UTF8.GetBytes("%PDF-1.4 fake");
        var adapter = Adapter((_, _) => Task.FromResult((body, "application/pdf")));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.download",
            JsonSerializer.SerializeToElement(new { url = "https://example.org/docs/informe.pdf", folder = "desktop" }),
            CancellationToken.None);

        Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Result!.Value.GetProperty("name").GetString(), Is.EqualTo("informe.pdf"));
            Assert.That(receipt.Result!.Value.GetProperty("bytes").GetInt64(), Is.EqualTo(body.Length));
            Assert.That(File.ReadAllBytes(Path.Combine(_root, "informe.pdf")), Is.EqualTo(body));
        });
    }

    [Test]
    public async Task AQueryDownloadsTheFirstImageTheSearchEngineLists()
    {
        const string page = "<div class=\"iusc\" m=\"{&quot;murl&quot;:&quot;https://i.kym-cdn.com/photos/a5d.png&quot;,&quot;turl&quot;:&quot;x&quot;}\"></div>";
        byte[] png = [0x89, 0x50, 0x4E, 0x47, 9, 9];
        var asked = new List<string>();
        var adapter = Adapter((url, _) =>
        {
            asked.Add(url);
            return Task.FromResult(url.EndsWith(".png", StringComparison.Ordinal)
                ? (png, "image/png")
                : (Encoding.UTF8.GetBytes(page), "text/html"));
        });

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.download",
            JsonSerializer.SerializeToElement(new { query = "meme de gatos", folder = "desktop", name = "meme" }),
            CancellationToken.None);
        ExternalCapabilityReceipt none = await adapter.InvokeAsync(
            "web.download",
            JsonSerializer.SerializeToElement(new { folder = "desktop" }),
            CancellationToken.None);

        Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
        Assert.Multiple(() =>
        {
            Assert.That(asked[0], Does.StartWith("https://www.bing.com/images/search?q=meme%20de%20gatos"));
            Assert.That(asked[1], Is.EqualTo("https://i.kym-cdn.com/photos/a5d.png"));
            Assert.That(receipt.Result!.Value.GetProperty("name").GetString(), Is.EqualTo("meme.png"));
            Assert.That(receipt.Result!.Value.GetProperty("query").GetString(), Is.EqualTo("meme de gatos"));
            Assert.That(File.Exists(Path.Combine(_root, "meme.png")), Is.True);
            Assert.That(none.ErrorCode, Is.EqualTo("download_source_missing"));
        });
    }

    [Test]
    public async Task APageGivesItsAnnouncedCoverImageNotItsHtml()
    {
        const string html = "<html><head><meta property=\"og:image\" content=\"https://upload.wikimedia.org/portada.png\"></head></html>";
        byte[] png = [0x89, 0x50, 0x4E, 0x47, 1, 2, 3];
        var asked = new List<string>();
        var adapter = Adapter((url, _) =>
        {
            asked.Add(url);
            return Task.FromResult(url.EndsWith(".png", StringComparison.Ordinal)
                ? (png, "image/png")
                : (Encoding.UTF8.GetBytes(html), "text/html"));
        });

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.download",
            JsonSerializer.SerializeToElement(new { url = "wikipedia.org", folder = "desktop" }),
            CancellationToken.None);

        Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
        Assert.Multiple(() =>
        {
            Assert.That(asked, Is.EqualTo(new[] { "https://wikipedia.org/", "https://upload.wikimedia.org/portada.png" }));
            Assert.That(receipt.Result!.Value.GetProperty("name").GetString(), Is.EqualTo("portada.png"));
            Assert.That(receipt.Result!.Value.GetProperty("sourceUrl").GetString(), Is.EqualTo("https://upload.wikimedia.org/portada.png"));
            Assert.That(File.Exists(Path.Combine(_root, "portada.png")), Is.True);
        });
    }

    [Test]
    public async Task APageWithoutACoverAndAnUnreachableAddressAreNamed()
    {
        var noCover = Adapter((_, _) => Task.FromResult((Encoding.UTF8.GetBytes("<html></html>"), "text/html")));
        var offline = Adapter((_, _) => throw new System.Net.Http.HttpRequestException("offline"));

        ExternalCapabilityReceipt cover = await noCover.InvokeAsync(
            "web.download", JsonSerializer.SerializeToElement(new { url = "https://example.org/", folder = "desktop" }), CancellationToken.None);
        ExternalCapabilityReceipt down = await offline.InvokeAsync(
            "web.download", JsonSerializer.SerializeToElement(new { url = "https://example.org/x.png", folder = "desktop" }), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(cover.ErrorCode, Is.EqualTo("download_page_without_image"));
            Assert.That(down.ErrorCode, Is.EqualTo("download_source_unavailable"));
            Assert.That(Directory.EnumerateFiles(_root), Is.Empty);
        });
    }

    [TestCase("portada", "image/png", "portada.png")]
    [TestCase("", "image/jpeg", "descarga.jpg")]
    [TestCase("a:b*c.txt", "text/plain", "abc.txt")]
    public void DownloadedNamesAreSafeAndCarryAnExtension(string candidate, string contentType, string expected) =>
        Assert.That(WindowsFileToolsAdapter.SafeFileName(candidate, contentType), Is.EqualTo(expected));
}
