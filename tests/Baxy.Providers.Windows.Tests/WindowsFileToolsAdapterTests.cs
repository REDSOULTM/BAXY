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

    // Revisión de calidad (archivos): a folder that holds BAXY's own state (home's AppData) is not zipped: its journal and
    // memory store went whole into a zip beside the person's files.
    [Test]
    public async Task AFolderThatHoldsBaxysOwnStateIsNotZipped()
    {
        string privateArea = Path.Combine(_root, "AppData", "Local", "BAXY");
        Directory.CreateDirectory(privateArea);
        File.WriteAllText(Path.Combine(privateArea, "confirmation-mode"), "normal");
        var adapter = new WindowsFileToolsAdapter(folder => folder == "home" ? _root : null, null)
        {
            PrivateRoots = [privateArea],
        };

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "file.compress", JsonSerializer.SerializeToElement(new { folder = "home", name = "AppData" }), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("path_reserved"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(File.Exists(Path.Combine(_root, "AppData.zip")), Is.False);
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

    // Renew al máximo (auditoría de flujos, archivos): a folder with a file another program holds open (an Excel book in
    // use) is not zipped, and nothing is left behind: a half-written zip stayed beside the folder, the failure said
    // zip_create_failed, and asking again answered zip_already_exists.
    [Test]
    public async Task AFolderWithAFileInUseLeavesNoHalfZipAndSaysTheFileIsInUse()
    {
        string folder = Path.Combine(_root, "Informe");
        Directory.CreateDirectory(folder);
        File.WriteAllText(Path.Combine(folder, "a.txt"), "uno");
        string held = Path.Combine(folder, "ventas.xlsx");
        File.WriteAllText(held, "dos");

        ExternalCapabilityReceipt first;
        ExternalCapabilityReceipt again;
        using (new FileStream(held, FileMode.Open, FileAccess.ReadWrite, FileShare.None))
        {
            first = await Adapter().InvokeAsync(
                "file.compress", JsonSerializer.SerializeToElement(new { folder = "desktop", name = "Informe" }),
                CancellationToken.None);
            again = await Adapter().InvokeAsync(
                "file.compress", JsonSerializer.SerializeToElement(new { folder = "desktop", name = "Informe" }),
                CancellationToken.None);
        }

        Assert.Multiple(() =>
        {
            Assert.That(first.ErrorCode, Is.EqualTo("file_in_use"));
            Assert.That(first.EffectMayHaveOccurred, Is.False);
            Assert.That(again.ErrorCode, Is.EqualTo("file_in_use"));
            Assert.That(File.Exists(Path.Combine(_root, "Informe.zip")), Is.False);
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

        WindowsFileToolsAdapter.OpenTarget target = TwoFolders(documents, pictures)
            .LocateOpenTarget("documents", "baxy-prueba-v3\\paisaje.jpg");

        Assert.Multiple(() =>
        {
            Assert.That(target.Error, Is.Null);
            Assert.That(target.Path, Is.EqualTo(Path.Combine(sub, "paisaje.jpg")));
        });
    }

    // Auditoría final 2: a file of that name in another folder is not opened in its place; where it was seen is said.
    [Test]
    public void AFileNotInTheFolderSaidIsNotOpenedAndWhereItWasSeenIsSaid()
    {
        string documents = Directory.CreateDirectory(Path.Combine(_root, "Documentos")).FullName;
        string pictures = Directory.CreateDirectory(Path.Combine(_root, "Imagenes")).FullName;
        string sub = Directory.CreateDirectory(Path.Combine(documents, "baxy-prueba-v3")).FullName;
        File.WriteAllText(Path.Combine(sub, "paisaje.jpg"), "x");

        WindowsFileToolsAdapter.OpenTarget target = TwoFolders(documents, pictures)
            .LocateOpenTarget("pictures", "paisaje.jpg");

        Assert.Multiple(() =>
        {
            Assert.That(target.Path, Is.Null);
            Assert.That(target.Error, Is.EqualTo("file_not_found"));
            Assert.That(target.SeenElsewhere, Is.EqualTo(new[] { ("documents", Path.Combine("baxy-prueba-v3", "paisaje.jpg")) }));
            Assert.That(target.SearchComplete, Is.True);
        });
    }

    // Holdout v6 (V6F010): «lista invitados» said, lista_invitados.txt there. A name is its words whatever separates them
    // (space, -, _, .): the one file of those words where it was asked is opened; two there are not, and are said with
    // any seen elsewhere.
    [Test]
    public void ANameSaidWithOtherSeparatorsOpensThatFileAndTwoSuchAreSaid()
    {
        string documents = Directory.CreateDirectory(Path.Combine(_root, "Documentos")).FullName;
        string pictures = Directory.CreateDirectory(Path.Combine(_root, "Imagenes")).FullName;
        File.WriteAllText(Path.Combine(documents, "lista_invitados.txt"), "x");
        File.WriteAllText(Path.Combine(documents, "notas_reunion.txt"), "x");
        File.WriteAllText(Path.Combine(documents, "notas-reunion.txt"), "x");
        File.WriteAllText(Path.Combine(Directory.CreateDirectory(Path.Combine(pictures, "viaje")).FullName, "foto-playa.jpg"), "x");
        WindowsFileToolsAdapter adapter = TwoFolders(documents, pictures);

        WindowsFileToolsAdapter.OpenTarget one = adapter.LocateOpenTarget("documents", "lista invitados.txt");
        WindowsFileToolsAdapter.OpenTarget two = adapter.LocateOpenTarget("documents", "notas reunion.txt");
        WindowsFileToolsAdapter.OpenTarget elsewhere = adapter.LocateOpenTarget("documents", "foto playa.jpg");

        Assert.Multiple(() =>
        {
            Assert.That(one.Path, Is.EqualTo(Path.Combine(documents, "lista_invitados.txt")));
            Assert.That(two.Path, Is.Null);
            Assert.That(two.SeenElsewhere.Select(seen => seen.RelativePath).Order(StringComparer.Ordinal),
                Is.EqualTo(new[] { "notas-reunion.txt", "notas_reunion.txt" }));
            Assert.That(elsewhere.Path, Is.Null);
            Assert.That(elsewhere.SeenElsewhere, Is.EqualTo(new[] { ("pictures", Path.Combine("viaje", "foto-playa.jpg")) }));
        });
    }

    [Test]
    public void TwoFilesWithTheNameAreBothSaidAndNoneIsAnHonestAbsence()
    {
        string documents = Directory.CreateDirectory(Path.Combine(_root, "Documentos")).FullName;
        string pictures = Directory.CreateDirectory(Path.Combine(_root, "Imagenes")).FullName;
        File.WriteAllText(Path.Combine(Directory.CreateDirectory(Path.Combine(documents, "a")).FullName, "foto.png"), "x");
        File.WriteAllText(Path.Combine(Directory.CreateDirectory(Path.Combine(pictures, "b")).FullName, "foto.png"), "x");
        WindowsFileToolsAdapter adapter = TwoFolders(documents, pictures);

        Assert.Multiple(() =>
        {
            Assert.That(adapter.LocateOpenTarget("documents", "foto.png").SeenElsewhere, Has.Count.EqualTo(2));
            Assert.That(adapter.LocateOpenTarget("documents", "foto.png").Path, Is.Null);
            Assert.That(adapter.LocateOpenTarget("documents", "nada.png").SeenElsewhere, Is.Empty);
            Assert.That(adapter.LocateOpenTarget("documents", "nada.png").Error, Is.EqualTo("file_not_found"));
        });
    }

    // Holdout v6 V6E062: «ábreme horario.txt que está ahí» (BAXY-bench in the home folder, just opened) was asked in the
    // home folder by its bare name, and the search never looked into the home folder's own folders: «no está en ningún
    // otro lugar». Its folders are looked into one level down; a known folder inside it is said once.
    [Test]
    public void ABareNameAskedInTheHomeFolderIsSeenInItsOwnFolders()
    {
        string home = Directory.CreateDirectory(Path.Combine(_root, "home")).FullName;
        string desktop = Directory.CreateDirectory(Path.Combine(home, "Desktop")).FullName;
        File.WriteAllText(Path.Combine(Directory.CreateDirectory(Path.Combine(home, "BAXY-bench")).FullName, "horario.txt"), "x");
        File.WriteAllText(Path.Combine(Directory.CreateDirectory(Path.Combine(home, "a", "b")).FullName, "hondo.txt"), "x");
        File.WriteAllText(Path.Combine(desktop, "foto.png"), "x");
        var adapter = new WindowsFileToolsAdapter(
            folder => folder switch { "home" => home, "desktop" => desktop, _ => null }, null);

        WindowsFileToolsAdapter.OpenTarget seen = adapter.LocateOpenTarget("home", "horario.txt");

        Assert.Multiple(() =>
        {
            Assert.That(seen.Path, Is.Null, "a file in another folder is never opened in its place");
            Assert.That(seen.Error, Is.EqualTo("file_not_found"));
            Assert.That(seen.SeenElsewhere, Is.EqualTo(new[] { ("home", Path.Combine("BAXY-bench", "horario.txt")) }));
            Assert.That(adapter.LocateOpenTarget("home", "hondo.txt").SeenElsewhere, Is.Empty, "one level down only");
            Assert.That(adapter.LocateOpenTarget("home", "foto.png").SeenElsewhere, Has.Count.EqualTo(1));
            // Asked in a known folder, the home folder is not looked into.
            Assert.That(adapter.LocateOpenTarget("desktop", "horario.txt").SeenElsewhere, Is.Empty);
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
            TwoFolders(documents, pictures).LocateOpenTarget("documents", "proyectoA\\informe.docx").SeenElsewhere,
            Is.Empty);
    }

    // Una búsqueda cortada (tiempo o cancelación) lo dice: lo visto no es todo.
    [Test]
    public void ASearchCutShortSaysItWasNotComplete()
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
                adapter.LocateOpenTarget("pictures", "foto.png", budget: TimeSpan.Zero).SearchComplete, Is.False);
            Assert.That(
                adapter.LocateOpenTarget("pictures", "foto.png", cancellationToken: cancelled.Token).SearchComplete,
                Is.False);
            // With time to look, both are seen and none is opened.
            Assert.That(adapter.LocateOpenTarget("pictures", "foto.png").SeenElsewhere, Has.Count.EqualTo(2));
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

    [TestCase("#ff0000", 255, 0, 0)]
    [TestCase("00ff00", 0, 255, 0)]
    [TestCase("#004E98", 0, 78, 152)]
    public void ColoursAreHex(string color, int r, int g, int b) =>
        Assert.That(WindowsFileToolsAdapter.ParseColor(color), Is.EqualTo(((byte)r, (byte)g, (byte)b)));

    [TestCase("azul")]
    [TestCase("blue")]
    public void AColourNameIsNotParsedHere(string color) =>
        Assert.That(WindowsFileToolsAdapter.ParseColor(color), Is.Null);

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

    // Renew al máximo (w8): a connection cut in the middle of the body escaped the adapter (told as a provider failure
    // that may have had an effect), and a 404 was the same code as an unreachable server; each says what it was.
    [Test]
    public async Task ADownloadCutOrRefusedByTheServerSaysWhichAndSavesNothing()
    {
        var cut = Adapter((_, _) => Task.FromException<(byte[], string)>(new IOException("connection reset")));
        var missing = Adapter((_, _) => Task.FromException<(byte[], string)>(
            new HttpRequestException("not found", null, System.Net.HttpStatusCode.NotFound)));
        JsonElement asked = JsonSerializer.SerializeToElement(new { url = "https://example.org/a.pdf", folder = "desktop" });

        ExternalCapabilityReceipt interrupted = await cut.InvokeAsync("web.download", asked, CancellationToken.None);
        ExternalCapabilityReceipt notFound = await missing.InvokeAsync("web.download", asked, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(interrupted.ErrorCode, Is.EqualTo("download_source_unavailable"));
            Assert.That(interrupted.EffectMayHaveOccurred, Is.False);
            Assert.That(interrupted.Result!.Value.GetProperty("next").GetString(), Does.Contain("nothing was saved"));
            Assert.That(notFound.ErrorCode, Is.EqualTo("download_http_status"));
            Assert.That(notFound.Result!.Value.GetProperty("statusCode").GetInt32(), Is.EqualTo(404));
            Assert.That(Directory.GetFiles(_root), Is.Empty);
        });
    }

    // Only an address is downloaded: a query used to scrape an image search engine's results page (BAXY Renew audit
    // 2026-10-15, O1); without an address nothing is asked of the network.
    [Test]
    public async Task WithoutAnAddressNothingIsFetched()
    {
        var asked = new List<string>();
        var adapter = Adapter((url, _) =>
        {
            asked.Add(url);
            return Task.FromResult((Array.Empty<byte>(), "text/html"));
        });

        ExternalCapabilityReceipt none = await adapter.InvokeAsync(
            "web.download",
            JsonSerializer.SerializeToElement(new { query = "meme de gatos", folder = "desktop" }),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(none.ErrorCode, Is.EqualTo("download_source_missing"));
            Assert.That(asked, Is.Empty);
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
            Assert.That(receipt.Result!.Value.GetProperty("pageUrl").GetString(), Is.EqualTo("https://wikipedia.org/"));
            Assert.That(receipt.Result!.Value.GetProperty("imageAnnouncedByPage").GetBoolean(), Is.True);
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

    // Auditoría final: a download reads only public web addresses, as web.fetch does; this PC and the local network
    // are never asked, neither as the address given nor as the image a public page announces.
    [Test]
    public async Task AnAddressOfThisPcOrTheLocalNetworkIsNeverAsked()
    {
        var asked = new List<string>();
        var adapter = Adapter((url, _) =>
        {
            asked.Add(url);
            return Task.FromResult(url.StartsWith("https://example.org/", StringComparison.Ordinal)
                ? (Encoding.UTF8.GetBytes("<meta property=\"og:image\" content=\"http://192.168.1.10/cam.jpg\">"), "text/html")
                : ([1, 2, 3], "image/jpeg"));
        });

        var receipts = new List<ExternalCapabilityReceipt>();
        foreach (string url in new[] { "http://192.168.1.10/cam.jpg", "http://localhost:8080/x.png", "http://router.lan/x.png", "https://example.org/" })
        {
            receipts.Add(await adapter.InvokeAsync(
                "web.download", JsonSerializer.SerializeToElement(new { url, folder = "desktop" }), CancellationToken.None));
        }

        Assert.Multiple(() =>
        {
            Assert.That(receipts.Select(receipt => receipt.ErrorCode), Is.All.EqualTo("download_url_not_public"));
            Assert.That(asked, Is.EqualTo(new[] { "https://example.org/" }));
            Assert.That(Directory.EnumerateFiles(_root), Is.Empty);
        });
    }

    // Renew al máximo (auditoría de flujos, web): a file over 50 MiB whose size the server does not announce (sent in
    // chunks) stops being read past the bound; it was read whole into memory (up to 2 GB) and only then refused.
    [Test]
    public async Task AnUnannouncedFileOverTheBoundIsNotReadWhole()
    {
        var body = new EndlessStream();
        var adapter = new WindowsFileToolsAdapter(folder => folder == "desktop" ? _root : null, null, null,
            new AnsweringHandler(() =>
            {
                var content = new StreamContent(body);
                content.Headers.ContentType = new System.Net.Http.Headers.MediaTypeHeaderValue("application/zip");
                return new System.Net.Http.HttpResponseMessage(System.Net.HttpStatusCode.OK) { Content = content };
            }));
        using var turn = new CancellationTokenSource(TimeSpan.FromSeconds(60));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "web.download",
            JsonSerializer.SerializeToElement(new { url = "https://example.org/grande.zip", folder = "desktop" }),
            turn.Token);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("download_too_large"));
            Assert.That(body.Served, Is.LessThanOrEqualTo(50L * 1024 * 1024 + 1024 * 1024));
            Assert.That(Directory.EnumerateFiles(_root), Is.Empty);
        });
    }

    private sealed class AnsweringHandler(Func<System.Net.Http.HttpResponseMessage> answer)
        : System.Net.Http.HttpMessageHandler
    {
        protected override Task<System.Net.Http.HttpResponseMessage> SendAsync(
            System.Net.Http.HttpRequestMessage request, CancellationToken cancellationToken) =>
            Task.FromResult(answer());
    }

    // A body that never ends (a server streaming chunks with no announced length), counting what was read of it.
    private sealed class EndlessStream : Stream
    {
        private const long Ceiling = 300L * 1024 * 1024;
        internal long Served { get; private set; }
        public override bool CanRead => true;
        public override bool CanSeek => false;
        public override bool CanWrite => false;
        public override long Length => throw new NotSupportedException();
        public override long Position { get => Served; set => throw new NotSupportedException(); }
        public override void Flush() { }
        public override int Read(byte[] buffer, int offset, int count)
        {
            // Past the ceiling it ends, so a reader without a bound stops too instead of filling the test's memory.
            int served = (int)Math.Min(count, Ceiling - Served);
            Array.Clear(buffer, offset, served);
            Served += served;
            return served;
        }
        public override long Seek(long offset, SeekOrigin origin) => throw new NotSupportedException();
        public override void SetLength(long value) => throw new NotSupportedException();
        public override void Write(byte[] buffer, int offset, int count) => throw new NotSupportedException();
    }

    [TestCase("portada", "image/png", "portada.png")]
    [TestCase("", "image/jpeg", "descarga.jpg")]
    [TestCase("a:b*c.txt", "text/plain", "abc.txt")]
    public void DownloadedNamesAreSafeAndCarryAnExtension(string candidate, string contentType, string expected) =>
        Assert.That(WindowsFileToolsAdapter.SafeFileName(candidate, contentType), Is.EqualTo(expected));
}
