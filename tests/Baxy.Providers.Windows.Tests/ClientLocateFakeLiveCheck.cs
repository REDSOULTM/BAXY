using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

/// <summary>
/// client.channel.locate and the look at a minimized window on the real desktop, against a local fake of the client with a
/// process name of its own (BAXY_FAKE_CHANNEL_CLIENT): the adapter looks only for that name here, so a real client that is open is
/// never reached. The fake's folder says how it behaves: recientes.txt (the rows of the empty switcher), listo.txt (ms until it
/// draws any row), demora.txt (ms until the filter is drawn), abrir.txt (ms until Ctrl+K takes effect), inicio.txt (minimizada,
/// encima), recientes2.txt and segundo.txt (more recent rows, drawn that many ms after the name is typed; with cambia.txt they
/// take the place of the first ones), otro.txt (Ctrl+K opens another dialog instead: sin_campo, con_texto, campo_vacio). It notes
/// what it receives and draws in eventos.txt. Explicit. What it cannot say:
/// whether the real client still draws so.
/// </summary>
[TestFixture]
[Explicit("Opens windows of its own and types into them.")]
[Category("LiveDesktop")]
[NonParallelizable]
public sealed class ClientLocateFakeLiveCheck
{
    private const string Asked = "Taller de ceramica";
    private static readonly string[] Recent = ["Tienda de pruebas", "Club de lectura, Canal de texto, Gremio", "Sala Sur (canal de voz), Gremio"];
    private readonly List<Process> _opened = [];
    private readonly List<string> _folders = [];
    private string[]? _realNames;
    private string _fake = string.Empty;
    private string _process = string.Empty;
    private string _scans = string.Empty;
    private string _lastFolder = string.Empty;

    [SetUp]
    public void Name()
    {
        string? fake = Environment.GetEnvironmentVariable("BAXY_FAKE_CHANNEL_CLIENT");
        if (string.IsNullOrWhiteSpace(fake))
            Assert.Ignore("BAXY_FAKE_CHANNEL_CLIENT is needed to touch the desktop.");
        _fake = fake;
        _process = Path.GetFileNameWithoutExtension(fake);
        if (string.Equals(_process, "Discord", StringComparison.OrdinalIgnoreCase))
            Assert.Ignore("The fake needs a process name of its own: a real client may be open.");
        _realNames = WindowsDesktopMessagingAutomation.DiscordProcesses;
        WindowsDesktopMessagingAutomation.DiscordProcesses = [_process];
        _scans = Path.Combine(Path.GetTempPath(), "baxy-canal-scans-" + Guid.NewGuid().ToString("N"));
        _folders.Add(_scans);
    }

    [TearDown]
    public void CloseOwn()
    {
        foreach (Process process in _opened)
        {
            if (!process.HasExited)
                process.Kill();
            process.WaitForExit(5000);
            process.Dispose();
        }

        _opened.Clear();
        foreach (string folder in _folders)
        {
            if (Directory.Exists(folder))
                Directory.Delete(folder, recursive: true);
        }

        _folders.Clear();
        if (_realNames is not null)
            WindowsDesktopMessagingAutomation.DiscordProcesses = _realNames;
    }

    private Process Open(string? fake = null, string? start = null, int ready = 0, int filter = 0, string[]? recent = null, string[]? chats = null, int late = 0, string[]? second = null, int secondMs = 0, bool replaces = false, string? other = null)
    {
        string folder = Path.Combine(Path.GetTempPath(), "baxy-canal-falso-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(folder);
        _folders.Add(folder);
        _lastFolder = folder;
        File.WriteAllText(Path.Combine(folder, "abrir.txt"), late.ToString(System.Globalization.CultureInfo.InvariantCulture));
        File.WriteAllLines(Path.Combine(folder, "chats.txt"), chats ?? [Asked, "Taller de ceramica fina", "Ronaldo Perez"], Encoding.UTF8);
        File.WriteAllLines(Path.Combine(folder, "recientes.txt"), recent ?? Recent, Encoding.UTF8);
        File.WriteAllText(Path.Combine(folder, "listo.txt"), ready.ToString(System.Globalization.CultureInfo.InvariantCulture));
        File.WriteAllText(Path.Combine(folder, "demora.txt"), filter.ToString(System.Globalization.CultureInfo.InvariantCulture));
        if (start is not null)
            File.WriteAllText(Path.Combine(folder, "inicio.txt"), start);
        if (second is not null)
        {
            File.WriteAllLines(Path.Combine(folder, "recientes2.txt"), second, Encoding.UTF8);
            File.WriteAllText(Path.Combine(folder, "segundo.txt"), secondMs.ToString(System.Globalization.CultureInfo.InvariantCulture));
        }

        if (replaces)
            File.WriteAllText(Path.Combine(folder, "cambia.txt"), "1");
        if (other is not null)
            File.WriteAllText(Path.Combine(folder, "otro.txt"), other);
        Process client = Process.Start(new ProcessStartInfo(fake ?? _fake, '"' + folder + '"') { UseShellExecute = false })!;
        _opened.Add(client);
        for (int attempt = 0; attempt < 80 && client.MainWindowHandle == 0; attempt++)
        {
            Thread.Sleep(50);
            client.Refresh();
        }

        Assert.That(client.MainWindowHandle, Is.Not.EqualTo(0), "the fake shows its window");
        return client;
    }

    private async Task<(ExternalCapabilityReceipt Receipt, JsonElement Result, long Ms)> LocateAsync(string name = Asked)
    {
        var adapter = new WindowsDeviceControlAdapter(_scans, _scans, new ExternalProcessRunner()) { KeysLease = ForegroundLease.Shared };
        using JsonDocument arguments = JsonDocument.Parse(JsonSerializer.Serialize(new { client = "discord", name }));
        var watch = Stopwatch.StartNew();
        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync("client.channel.locate", arguments.RootElement, CancellationToken.None);
        long took = watch.ElapsedMilliseconds;
        TestContext.Out.WriteLine($"PASO {took} ms {receipt.ErrorCode} {receipt.Result}");
        return (receipt, receipt.Result ?? default, took);
    }

    private static string Rows(JsonElement result) =>
        string.Join('\n', result.GetProperty("switcherRows").EnumerateArray().Select(static row => row.GetString()));

    private string Events()
    {
        string events = Path.Combine(_lastFolder, "eventos.txt");
        return File.Exists(events) ? File.ReadAllText(events, Encoding.UTF8) : string.Empty;
    }

    // F47: a look puts back what it restored; nobody asked for the client.
    [Test]
    public async Task ALookLeavesAMinimizedClientMinimized()
    {
        Process client = Open(start: "minimizada");
        (ExternalCapabilityReceipt receipt, JsonElement result, _) = await LocateAsync();
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(result.GetProperty("restoredFromMinimized").GetBoolean(), Is.True);
            Assert.That(result.GetProperty("leftShown").GetBoolean(), Is.False);
            Assert.That(IsIconic(client.MainWindowHandle), Is.True);
        });
    }

    // F47: «abre … y ve a …»: this very turn's opening asked for the client, which came up minimized by its own memory of how
    // it was left. It stays where the person can see it, and the receipt says so.
    [Test]
    public async Task AClientThisTurnOpenedStaysInSight()
    {
        Process client = Open(start: "minimizada");
        VisibleControlSurface.NoteOpened(client.Id, launched: true, client.MainWindowHandle);
        (ExternalCapabilityReceipt receipt, JsonElement result, _) = await LocateAsync();
        _ = VisibleControlSurface.TakeOpened(TimeSpan.FromHours(1));
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(result.GetProperty("restoredFromMinimized").GetBoolean(), Is.True);
            Assert.That(result.GetProperty("leftShown").GetBoolean(), Is.True);
            Assert.That(IsIconic(client.MainWindowHandle), Is.False);
        });
    }

    // F47: the noted opening counts only for the client's own process, and for one that is still there.
    [Test]
    public void OnlyTheClientsOwnOpeningCounts()
    {
        Process client = Open();
        DateTime now = DateTime.UtcNow;
        Assert.Multiple(() =>
        {
            Assert.That(WindowsDeviceControlAdapter.OpenedThisTurn(new VisibleControlSurface.OpenedApplication(client.Id, now, now, true, 0)), Is.True);
            Assert.That(WindowsDeviceControlAdapter.OpenedThisTurn(new VisibleControlSurface.OpenedApplication(Environment.ProcessId, now, now, true, 0)), Is.False);
            Assert.That(WindowsDeviceControlAdapter.OpenedThisTurn(new VisibleControlSurface.OpenedApplication(int.MaxValue - 1, now, now, true, 0)), Is.False);
            Assert.That(WindowsDeviceControlAdapter.OpenedThisTurn(null), Is.False);
        });
    }

    // F47: another application's opening says nothing of this client.
    [Test]
    public async Task AnotherApplicationsOpeningDoesNotKeepTheClient()
    {
        Process client = Open(start: "minimizada");
        VisibleControlSurface.NoteOpened(Environment.ProcessId, launched: true);
        (ExternalCapabilityReceipt receipt, JsonElement result, _) = await LocateAsync();
        _ = VisibleControlSurface.TakeOpened(TimeSpan.FromHours(1));
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(result.GetProperty("leftShown").GetBoolean(), Is.False);
            Assert.That(IsIconic(client.MainWindowHandle), Is.True);
        });
    }

    // F48: a client that has just opened draws its recent rows only after the name was typed. Those rows are no result:
    // the receipt says the filter's, never «not found» out of the recent ones.
    [Test]
    public async Task TheRecentRowsOfAClientStillLoadingAreNoResult()
    {
        Process client = Open(ready: 3200, filter: 1500);
        _ = ForegroundRight.Give(client.MainWindowHandle);
        (ExternalCapabilityReceipt receipt, JsonElement result, _) = await LocateAsync();
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(result.GetProperty("found").GetBoolean(), Is.True);
            Assert.That(Rows(result), Does.Contain(Asked));
            Assert.That(Rows(result), Does.Not.Contain("Tienda de pruebas"));
        });
    }

    // F48: the filter never came: no «not found», the switcher was not read.
    [Test]
    public async Task AFilterNeverSeenSaysTheSwitcherWasNotRead()
    {
        Process client = Open(ready: 3200, filter: 120_000);
        _ = ForegroundRight.Give(client.MainWindowHandle);
        (ExternalCapabilityReceipt receipt, _, _) = await LocateAsync();
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("client_quick_switcher_not_read"));
        });
    }

    // Review R1 (A3): more recent rows drawn after the name was typed, with the filter still to come: the list only grew, so it is
    // no result. The channel is there and the receipt says so.
    [TestCase(100, 2600)]
    [TestCase(700, 2500)]
    [TestCase(1200, 2500)]
    public async Task RecentRowsThatGrowAfterTypingAreNoResult(int secondMs, int filter)
    {
        Process client = Open(filter: filter, second: ["Tienda de Orbs", "Perfil de juego"], secondMs: secondMs);
        await Task.Delay(1500);
        _ = ForegroundRight.Give(client.MainWindowHandle);
        (ExternalCapabilityReceipt receipt, JsonElement result, _) = await LocateAsync();
        Assert.Multiple(() =>
        {
            Assert.That(Events(), Does.Contain("segunda tanda"), "the rows arrived late");
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(result.GetProperty("found").GetBoolean(), Is.True);
            Assert.That(Rows(result), Does.Not.Contain("Tienda de pruebas"));
        });
    }

    // Review R1 (A3), the same with a recent row whose text changed (a new message): as many rows, most of them still there.
    [Test]
    public async Task ARecentRowThatChangesAfterTypingIsNoResult()
    {
        Process client = Open(filter: 2500, recent: ["Tienda de pruebas", "Club de lectura", "Perfil de juego"], second: ["Tienda de pruebas, 1 sin leer"], secondMs: 300, replaces: true);
        await Task.Delay(1500);
        _ = ForegroundRight.Give(client.MainWindowHandle);
        (ExternalCapabilityReceipt receipt, JsonElement result, _) = await LocateAsync();
        Assert.Multiple(() =>
        {
            Assert.That(Events(), Does.Contain("segunda tanda"), "the row changed late");
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(result.GetProperty("found").GetBoolean(), Is.True);
        });
    }

    // A3, control: the same rows arriving late, and a channel that is not there: never «there», and a filter seen empty says «not found».
    [Test]
    public async Task RecentRowsThatGrowAndNoSuchChannelAreNeverAFind()
    {
        Process client = Open(filter: 2500, second: ["Tienda de Orbs", "Perfil de juego"], secondMs: 300);
        await Task.Delay(1500);
        _ = ForegroundRight.Give(client.MainWindowHandle);
        (ExternalCapabilityReceipt receipt, JsonElement result, _) = await LocateAsync("Zzz sin coincidencia");
        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.Not.EqualTo("client_not_foreground"), "the script never reached the client");
            Assert.That(receipt.Verified && result.GetProperty("found").GetBoolean(), Is.False, receipt.ErrorCode);
        });
    }

    // A review of A3's own rule: a filter sharing half of the recent rows, as many as they were, is still a filter: it says its rows.
    [Test]
    public async Task AFilterSharingHalfOfTheRecentRowsIsStillAResult()
    {
        Process client = Open(filter: 800, recent: ["Taller uno", "Club de lectura"], chats: ["Taller uno", "Taller dos"]);
        await Task.Delay(1500);
        _ = ForegroundRight.Give(client.MainWindowHandle);
        (ExternalCapabilityReceipt receipt, JsonElement result, _) = await LocateAsync("Taller");
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(result.GetProperty("found").GetBoolean(), Is.False);
            Assert.That(Rows(result), Does.Contain("Taller dos"));
        });
    }

    // A3, control: a filter never drawn while the list grew: the switcher was not read, and only the exact name would count.
    [TestCase(Asked, true)]
    [TestCase("Taller", false)]
    public async Task RecentRowsThatGrowAndNoFilterSayOnlyTheExactName(string name, bool found)
    {
        Process client = Open(filter: 120_000, recent: ["Tienda de pruebas", Asked], second: ["Perfil de juego"], secondMs: 300);
        await Task.Delay(1500);
        _ = ForegroundRight.Give(client.MainWindowHandle);
        (ExternalCapabilityReceipt receipt, JsonElement result, _) = await LocateAsync(name);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.EqualTo(found), receipt.ErrorCode);
            if (found)
                Assert.That(result.GetProperty("found").GetBoolean(), Is.True);
            else
                Assert.That(receipt.ErrorCode, Is.EqualTo("client_quick_switcher_not_read"));
        });
    }

    // Review R1 (H1): Ctrl+K brought another dialog of the client's (a call, a confirmation) and not the switcher: it holds no empty
    // field, or holds the focus on a button, so the name is not typed into it and nothing in it is pressed.
    [TestCase("sin_campo")]
    [TestCase("con_texto")]
    [TestCase("campo_vacio")]
    public async Task TheNameIsNeverTypedIntoAnotherDialog(string other)
    {
        Process client = Open(other: other);
        await Task.Delay(1500);
        _ = ForegroundRight.Give(client.MainWindowHandle);
        (ExternalCapabilityReceipt receipt, _, _) = await LocateAsync();
        string events = Events();
        TestContext.Out.WriteLine($"OTRO {other}: {receipt.ErrorCode ?? "leido"} eventos=[{events.ReplaceLineEndings("|")}]");
        Assert.Multiple(() =>
        {
            Assert.That(events, Does.Contain("otro dialogo abierto"), "the key reached the client");
            Assert.That(events, Does.Not.Contain("letra en otro dialogo"));
            Assert.That(events, Does.Not.Contain("boton pulsado"));
            Assert.That(receipt.Verified, Is.False);
        });
    }

    // Review of F51 (the one thing that must never happen): a Ctrl+K that takes effect late, around every wait of the script. A
    // Ctrl+K sent while it is about to open closes it, and the name must not reach the person's message box.
    [TestCase(300)]
    [TestCase(1300)]
    [TestCase(1500)]
    [TestCase(1700)]
    [TestCase(2000)]
    [TestCase(2300)]
    [TestCase(3000)]
    public async Task ASwitcherThatOpensLateNeverGetsTheNameOutsideIt(int late)
    {
        Process client = Open(filter: 200, late: late);
        await Task.Delay(1500);
        _ = ForegroundRight.Give(client.MainWindowHandle);
        (ExternalCapabilityReceipt receipt, _, _) = await LocateAsync();
        string draft = Path.Combine(_lastFolder, "borrador.txt");
        string typed = File.Exists(draft) ? File.ReadAllText(draft, Encoding.UTF8) : string.Empty;
        string sent = Path.Combine(_lastFolder, "enviados.txt");
        string events = Events();
        TestContext.Out.WriteLine($"TARDE {late} ms: {receipt.ErrorCode ?? "leido"} borrador=[{typed.Trim()}]");
        Assert.Multiple(() =>
        {
            // Review R1 (B7): with the front held by another window no key is sent and nothing here would be tested.
            Assert.That(receipt.ErrorCode, Is.Not.EqualTo("client_not_foreground"), "the script never reached the client");
            Assert.That(events, Does.Contain("cambiador abierto"), "the client got its Ctrl+K");
            Assert.That(typed, Does.Not.Contain("Taller"));
            Assert.That(File.Exists(sent), Is.False);
        });
    }

    // F51: no row matches: the rows seen before are gone with the name in the field. Said once, not after five rounds.
    [Test]
    public async Task NoRowForTheNameIsSaidOnce()
    {
        Process client = Open(filter: 600);
        await Task.Delay(61_000); // no longer a client just started
        _ = ForegroundRight.Give(client.MainWindowHandle);
        (ExternalCapabilityReceipt receipt, JsonElement result, long took) = await LocateAsync("Zzz sin coincidencia");
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(result.GetProperty("found").GetBoolean(), Is.False);
            Assert.That(Rows(result), Is.Empty);
            Assert.That(took, Is.LessThan(15_000));
        });
    }

    // A client just started may still be loading what it filters: no row is «not found» after a second look, not after five.
    [Test]
    public async Task NoRowOnAClientJustStartedIsSaidAfterASecondLook()
    {
        Process client = Open(filter: 600);
        await Task.Delay(1500);
        _ = ForegroundRight.Give(client.MainWindowHandle);
        (ExternalCapabilityReceipt receipt, JsonElement result, long took) = await LocateAsync("Zzz sin coincidencia");
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(result.GetProperty("found").GetBoolean(), Is.False);
            Assert.That(took, Is.LessThan(25_000));
        });
    }

    // A client with no recent rows at all: the exact name is said; without it, the switcher was not read.
    [TestCase(Asked, true)]
    [TestCase("Taller", false)]
    public async Task AClientWithNoRecentRowsSaysOnlyTheExactName(string name, bool found)
    {
        Process client = Open(filter: 300, recent: []);
        await Task.Delay(1500);
        _ = ForegroundRight.Give(client.MainWindowHandle);
        (ExternalCapabilityReceipt receipt, JsonElement result, _) = await LocateAsync(name);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.EqualTo(found), receipt.ErrorCode);
            if (found)
                Assert.That(result.GetProperty("found").GetBoolean(), Is.True);
            else
                Assert.That(receipt.ErrorCode, Is.EqualTo("client_quick_switcher_not_read"));
        });
    }

    // A loaded client: the filter's rows, with and without the exact name.
    [TestCase(Asked, true)]
    [TestCase("Taller", false)]
    public async Task ALoadedClientSaysWhatTheFilterShows(string name, bool found)
    {
        Process client = Open(filter: 800);
        await Task.Delay(1500);
        _ = ForegroundRight.Give(client.MainWindowHandle);
        (ExternalCapabilityReceipt receipt, JsonElement result, _) = await LocateAsync(name);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(result.GetProperty("found").GetBoolean(), Is.EqualTo(found));
            Assert.That(Rows(result), Does.Not.Contain("Tienda de pruebas"));
        });
    }

    // F51: what a step costs on a client already loaded, drawing its filter as the real one does at its best and at its worst.
    [TestCase(100)]
    [TestCase(600)]
    [TestCase(2600)]
    public async Task WhatAStepCosts(int filter)
    {
        Process client = Open(filter: filter);
        await Task.Delay(1500);
        _ = ForegroundRight.Give(client.MainWindowHandle);
        var taken = new List<long>();
        for (int run = 0; run < 3; run++)
        {
            (ExternalCapabilityReceipt receipt, _, long took) = await LocateAsync();
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            taken.Add(took);
        }

        TestContext.Out.WriteLine($"COSTE filtro {filter} ms: {string.Join(", ", taken)} ms");
    }

    // F46: a minimized window under one of the product's own: its look reads its own drawing, never the product on the screen.
    // The product's stand-in is the fake, copied under a process name of the product's (BAXY_FAKE_PRODUCT_WINDOW).
    [TestCase(null, null)]
    [TestCase("encima", null)]
    [TestCase(null, "restaura_lento")]
    public async Task AMinimizedWindowUnderTheProductIsNotReadAsTheProduct(string? start, string? clientStart)
    {
        string? fake = Environment.GetEnvironmentVariable("BAXY_FAKE_PRODUCT_WINDOW");
        if (string.IsNullOrWhiteSpace(fake))
            Assert.Ignore("BAXY_FAKE_PRODUCT_WINDOW is needed.");
        Process client = Open(start: clientStart, chats: ["CONVERSACION DEL CLIENTE"]);
        await Task.Delay(800);
        _ = ShowWindow(client.MainWindowHandle, 6);
        await Task.Delay(500);
        Process product = Open(fake, start, chats: ["PANEL PROPIO DEL PRODUCTO", "SESIONES DEL PRODUCTO"]);
        await Task.Delay(1500);
        _ = ForegroundRight.Give(product.MainWindowHandle);
        await Task.Delay(300);
        using var worker = new UiaWorkerHost(Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1"));
        await worker.PrewarmAsync(CancellationToken.None);
        using var visible = new WindowsVisibleControlAdapter(worker);
        using JsonDocument arguments = JsonDocument.Parse(JsonSerializer.Serialize(new { application = _process, includeText = true }));
        ExternalCapabilityReceipt look = await visible.InvokeAsync("input.visible.controls", arguments.RootElement, CancellationToken.None);
        string read = look.Result?.ToString() ?? string.Empty;
        string text = look.Result is { } result && result.TryGetProperty("text", out JsonElement lines) ? lines.ToString() : string.Empty;
        TestContext.Out.WriteLine("LEIDO " + text);
        Assert.Multiple(() =>
        {
            Assert.That(look.Verified, Is.True, look.ErrorCode);
            Assert.That(read, Does.Contain("shownFromMinimized"));
            Assert.That(read, Does.Not.Contain("PRODUCTO"));
            Assert.That(text, Does.Contain("CONVERSACION"), "the window's own drawing");
            Assert.That(read, Does.Contain("Enviar mensaje"), "the window's own tree");
        });
    }

    // F46 on a real Chromium window of a profile of its own (BAXY_CHROMIUM_EXE): every first look at it, just shown from minimized
    // under the product's window, reads the page. The copy of the screen read the product there, and its own drawing taken at once
    // an empty frame.
    [Test]
    public async Task EveryFirstLookAtAChromiumWindowReadsItsPage()
    {
        string? browserPath = Environment.GetEnvironmentVariable("BAXY_CHROMIUM_EXE");
        string? fake = Environment.GetEnvironmentVariable("BAXY_FAKE_PRODUCT_WINDOW");
        if (string.IsNullOrWhiteSpace(browserPath) || string.IsNullOrWhiteSpace(fake))
            Assert.Ignore("BAXY_CHROMIUM_EXE and BAXY_FAKE_PRODUCT_WINDOW are needed.");
        string folder = Path.Combine(Path.GetTempPath(), "baxy-canal-pagina-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(folder);
        _folders.Add(folder);
        string page = Path.Combine(folder, "p.html");
        File.WriteAllText(page, "<title>Sala Falsa</title><body style='font-size:40px'><h1>CONVERSACION DEL CLIENTE</h1><p>Linea propia</p></body>", Encoding.UTF8);
        Process browser = Process.Start(new ProcessStartInfo(
            browserPath,
            $"--user-data-dir=\"{folder}/perfil\" --no-first-run --no-default-browser-check --window-position=40,20 --window-size=1200,800 --app=\"file:///{page.Replace('\\', '/')}\"")
        { UseShellExecute = false })!;
        nint window = 0;
        try
        {
            for (int attempt = 0; attempt < 60 && window == 0; attempt++)
            {
                await Task.Delay(250);
                window = FindWindowW(null, "Sala Falsa");
            }

            Assert.That(window, Is.Not.EqualTo(0));
            await Task.Delay(2500);
            Process product = Open(fake, null, chats: ["PANEL PROPIO DEL PRODUCTO", "SESIONES DEL PRODUCTO"]);
            await Task.Delay(1200);
            using var worker = new UiaWorkerHost(Path.Combine(AppContext.BaseDirectory, "DesktopUiaWorker.ps1"));
            await worker.PrewarmAsync(CancellationToken.None);
            using var visible = new WindowsVisibleControlAdapter(worker);
            using JsonDocument arguments = JsonDocument.Parse(JsonSerializer.Serialize(new { application = "Sala Falsa", includeText = true }));
            int read = 0, productRead = 0;
            const int Looks = 12;
            for (int look = 0; look < Looks; look++)
            {
                _ = ShowWindow(window, 6);
                await Task.Delay(1000);
                _ = ForegroundRight.Give(product.MainWindowHandle);
                await Task.Delay(300);
                ExternalCapabilityReceipt seen = await visible.InvokeAsync("input.visible.controls", arguments.RootElement, CancellationToken.None);
                string text = seen.Result is { } result && result.TryGetProperty("text", out JsonElement lines) ? lines.ToString() : string.Empty;
                TestContext.Out.WriteLine($"LEIDO {look} {text}");
                read += text.Contains("CONVERSACION", StringComparison.Ordinal) ? 1 : 0;
                productRead += text.Contains("PRODUCTO", StringComparison.Ordinal) ? 1 : 0;
            }

            TestContext.Out.WriteLine($"COSTE miradas con la pagina {read}/{Looks}, con el producto {productRead}/{Looks}");
            Assert.Multiple(() =>
            {
                Assert.That(read, Is.EqualTo(Looks));
                Assert.That(productRead, Is.Zero);
            });
        }
        finally
        {
            browser.Kill(entireProcessTree: true);
            browser.WaitForExit(5000);
            browser.Dispose();
        }
    }

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern nint FindWindowW(string? windowClass, string title);

    [DllImport("user32.dll")]
    private static extern bool ShowWindow(nint window, int command);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool IsIconic(nint window);
}
