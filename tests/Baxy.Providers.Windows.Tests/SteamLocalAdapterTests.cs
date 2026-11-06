using System.Text.Json;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.External;
using NUnit.Framework;

namespace Baxy.Providers.Windows.Tests;

[TestFixture]
public sealed class SteamLocalAdapterTests
{
    private static readonly SteamLocalGame[] Catalog =
    [
        new("620", "Portal 2", new string('a', 64)),
        new("123", "Another Game", new string('b', 64)),
    ];

    // Renew al máximo (B-APP-4): Steam's EAppState flags as its manifests write them: a download running
    // (UpdateRequired 2 | UpdateStarted 1024 | Downloading 1048576), one in pause (UpdateRequired 2 | UpdatePaused 512 |
    // UpdateStarted 1024), and one left with no running flag (a download cut with Steam closed).
    private const ulong Downloading = 2 | 1024 | 1048576;
    private const ulong Paused = 2 | 512 | 1024;
    private const ulong Stopped = 2 | 1024;

    // Renew al máximo (w8): a title with an apostrophe is matched as it is said («assassins creed origins», «Sid Meier
    // Civilization VI»), the typographic one and the ™/® marks included; a title of other words still is not.
    [TestCase("Assassin's Creed Origins", "assassins creed origins", true)]
    [TestCase("Tom Clancy’s Rainbow Six® Siege", "tom clancys rainbow six siege", true)]
    [TestCase("Sid Meier's Civilization® VI", "Sid Meier's Civilization VI", true)]
    [TestCase("Sid Meier's Civilization VI", "Sid Meier Civilization VI", true)]
    [TestCase("Assassin's Creed Origins", "assassins creed odyssey", false)]
    public void ATitleWithAnApostropheFoldsAsItIsSaid(string title, string said, bool same) =>
        Assert.That(SteamLocalAdapter.FoldTitle(title) == SteamLocalAdapter.FoldTitle(said), Is.EqualTo(same));

    // Renew al máximo (B-APP-4): only a running flag says «downloading»; a download in pause, or one with bytes and no
    // running flag, is «paused», in its status and in the catalog.
    [Test]
    public async Task APausedDownloadIsNotSaidDownloading()
    {
        SteamLocalGame[] observed =
        [
            new("10", "Paused Game", new string('a', 64), Paused, 250, 1000),
            new("11", "Running Game", new string('b', 64), Downloading, 250, 1000),
            new("12", "Stopped Game", new string('c', 64), Stopped, 250, 1000),
        ];
        var adapter = new SteamLocalAdapter(() => observed);
        var said = new Dictionary<string, string?>(StringComparer.Ordinal);
        foreach (SteamLocalGame game in observed)
        {
            string appId = game.AppId;
            ExternalCapabilityReceipt status = await adapter.InvokeAsync(
                "game.install.status", Json($$"""{"appId":"{{appId}}","title":"{{game.Name}}"}"""), CancellationToken.None);
            said[appId] = status.Result?.GetProperty("state").GetString();
        }

        ExternalCapabilityReceipt list = await adapter.InvokeAsync("game.catalog.list", Json("{}"), CancellationToken.None);
        Dictionary<string, string?> listed = list.Result!.Value.GetProperty("games").EnumerateArray().ToDictionary(
            game => game.GetProperty("appId").GetString()!, game => game.GetProperty("state").GetString());

        var expected = new Dictionary<string, string?> { ["10"] = "paused", ["11"] = "downloading", ["12"] = "paused" };
        Assert.Multiple(() =>
        {
            Assert.That(said, Is.EquivalentTo(expected));
            Assert.That(listed, Is.EquivalentTo(expected));
        });
    }

    [Test]
    public void AuthenticatedSnapshotContainsOnlyInstalledGamesInStableOrder()
    {
        SteamLocalGame[] observed =
        [
            new("999", "Zulu", new string('c', 64), StateFlags: 1),
            new("730", "Counter-Strike 2", new string('d', 64)),
            new("620", "Portal 2", new string('a', 64)),
        ];
        var adapter = new SteamLocalAdapter(() => observed);

        InstalledGameCatalogSnapshot snapshot = adapter.GetCatalogSnapshot();

        Assert.Multiple(() =>
        {
            Assert.That(snapshot.Verified, Is.True);
            Assert.That(snapshot.Complete, Is.True);
            Assert.That(
                snapshot.Entries,
                Is.EqualTo(new[]
                {
                    new InstalledGameCatalogEntry("steam", "730", "Counter-Strike 2"),
                    new InstalledGameCatalogEntry("steam", "620", "Portal 2"),
                }));
        });
    }

    [Test]
    public async Task CatalogListsOnlyObservedLocalManifestsAndHonorsQuery()
    {
        var adapter = new SteamLocalAdapter(() => Catalog);
        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "game.catalog.list",
            Json("""{"query":"Portal","limit":10}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.Result?.GetProperty("count").GetInt32(), Is.EqualTo(1));
            Assert.That(
                receipt.Result?.GetProperty("games")[0].GetProperty("appId").GetString(),
                Is.EqualTo("620"));
        });
    }

    // Auditoría de falsedades 2026-11-04 (P2, U34 18 de 18): «¿Tengo algún juego de carreras instalado?» → a list with
    // count 0 and librariesUnread 1 (Steam's library could not be read) → «No encontré ningún juego de carreras en tu
    // lista de Steam». The mind says a «no está» covers only what was read when the result says readInPart; a list or
    // a title looked up with a library unread is read in part, and one with every library read is not.
    [Test]
    public async Task AReadWithALibraryUnreadSaysItWasReadInPart()
    {
        var unread = new SteamLocalAdapter(() => new SteamLocalAdapter.InstalledCatalog([], 1));
        var whole = new SteamLocalAdapter(() => new SteamLocalAdapter.InstalledCatalog([.. Catalog], 0));

        ExternalCapabilityReceipt list = await unread.InvokeAsync(
            "game.catalog.list", Json("""{"query":"carreras"}"""), CancellationToken.None);
        ExternalCapabilityReceipt named = await unread.InvokeAsync(
            "game.entitlement.named", Json("""{"title":"carreras"}"""), CancellationToken.None);
        ExternalCapabilityReceipt listed = await whole.InvokeAsync(
            "game.catalog.list", Json("""{"query":"carreras"}"""), CancellationToken.None);
        ExternalCapabilityReceipt known = await whole.InvokeAsync(
            "game.entitlement.named", Json("""{"title":"Portal 2"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(list.Result!.Value.GetProperty("count").GetInt32(), Is.Zero);
            Assert.That(list.Result!.Value.GetProperty("librariesUnread").GetInt32(), Is.EqualTo(1));
            Assert.That(list.Result!.Value.GetProperty("readInPart").GetBoolean(), Is.True);
            Assert.That(named.Result!.Value.GetProperty("readInPart").GetBoolean(), Is.True);
            Assert.That(listed.Result!.Value.TryGetProperty("readInPart", out _), Is.False);
            Assert.That(known.Result!.Value.TryGetProperty("readInPart", out _), Is.False);
        });
    }

    // Uso real 03-11 (G9): a game searched among the installed ones, none bearing it, was said «not in your library».
    // The list says what it covers and, for a search nothing installed bears, what the account's library cache says.
    [Test]
    public async Task ASearchNothingInstalledBearsSaysItsScopeAndWhatTheLibraryCacheSays()
    {
        SteamLocalAdapter adapter = OwnedElsewhereAdapter();

        ExternalCapabilityReceipt found = await adapter.InvokeAsync(
            "game.catalog.list", Json("""{"query":"Portal"}"""), CancellationToken.None);
        ExternalCapabilityReceipt none = await adapter.InvokeAsync(
            "game.catalog.list", Json("""{"query":"Owned Elsewhere"}"""), CancellationToken.None);

        JsonElement entitlement = none.Result!.Value.GetProperty("entitlement");
        Assert.Multiple(() =>
        {
            Assert.That(none.Verified, Is.True);
            Assert.That(none.Result!.Value.GetProperty("count").GetInt32(), Is.Zero);
            Assert.That(none.Result!.Value.GetProperty("scope").GetString(),
                Is.EqualTo("games_installed_or_downloading_on_this_pc"));
            Assert.That(entitlement.GetProperty("state").GetString(), Is.EqualTo("owned_not_installed"));
            Assert.That(entitlement.GetProperty("appId").GetString(), Is.EqualTo("700"));
            Assert.That(found.Result!.Value.GetProperty("scope").GetString(),
                Is.EqualTo("games_installed_or_downloading_on_this_pc"));
            Assert.That(found.Result!.Value.TryGetProperty("entitlement", out _), Is.False);
        });
    }

    [Test]
    public async Task ALaunchOfAnOwnedGameNotInstalledSaysWhatTheLibraryCacheSays()
    {
        ExternalCapabilityReceipt receipt = await OwnedElsewhereAdapter().InvokeAsync(
            "game.launch", Json("""{"appId":"12345","title":"Owned Elsewhere"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.Result!.Value.GetProperty("outsideLibrary").GetBoolean(), Is.True);
            Assert.That(receipt.Result!.Value.GetProperty("entitlement").GetProperty("state").GetString(),
                Is.EqualTo("owned_not_installed"));
        });
    }

    private static SteamLocalAdapter OwnedElsewhereAdapter() => new(
        () => [Catalog[0] with { InstallDirectory = Path.Combine(Path.GetTempPath(), "baxy-steam-launch-fixture") }],
        () => new HashSet<string>(["620", "700"], StringComparer.Ordinal),
        new FakeSteamAutomation(onDispatch: _ => Assert.Fail("nothing is sent to Steam")),
        (_, _) => ValueTask.CompletedTask,
        () => [],
        knownGames: () => [new("700", "Owned Elsewhere"), new("620", "Portal 2")]);

    [TestCase("game.install.status")]
    public async Task SchemaAcceptedInvalidAppIdFailsClosedWithoutEscapingTheAdapter(
        string operation)
    {
        var adapter = new SteamLocalAdapter(() => Catalog);

        ExternalCapabilityReceipt? receipt = null;
        Assert.DoesNotThrowAsync(async () =>
        {
            receipt = await adapter.InvokeAsync(
                operation,
                Json("""{"appId":"audit-missing-id"}"""),
                CancellationToken.None);
        });

        Assert.Multiple(() =>
        {
            Assert.That(receipt, Is.Not.Null);
            Assert.That(receipt!.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("steam_app_id_invalid"));
        });
    }

    [Test]
    public async Task NamedInstallResolvesExactObservedTitleAndReportsInstalledState()
    {
        var adapter = new SteamLocalAdapter(() => Catalog);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "game.install.named",
            Json("""{"title":"Portal 2"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.StateAlreadyReached, Is.True);
            Assert.That(receipt.Result?.GetProperty("appId").GetString(), Is.EqualTo("620"));
            Assert.That(receipt.Result?.GetProperty("state").GetString(),
                Is.EqualTo("already_installed"));
        });
    }

    [Test]
    public async Task BrokenLocalSnapshotFailsClosedWithoutCrashingCore()
    {
        var adapter = new SteamLocalAdapter(
            () => throw new IOException("simulated catalog race"));
        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "game.catalog.list",
            Json("{}"),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("steam_local_catalog_failed"));
        });
    }

    [Test]
    public async Task InstallStatusReportsManifestProgressWithoutDispatch()
    {
        SteamLocalGame[] downloading =
        [
            new("620", "Portal 2", new string('a', 64), StateFlags: Downloading,
                BytesDownloaded: 250, BytesToDownload: 1000),
        ];
        var adapter = new SteamLocalAdapter(() => downloading);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "game.install.status", Json("""{"appId":"620","title":"Portal 2"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.Result?.GetProperty("state").GetString(), Is.EqualTo("downloading"));
            Assert.That(receipt.Result?.GetProperty("progressPercent").GetDouble(), Is.EqualTo(25d));
        });
    }

    [Test]
    public async Task CancelRequiresPartialDownloadAndVerifiesPausedManifest()
    {
        SteamLocalGame observed = new("888", "Partial Game", new string('d', 64),
            StateFlags: Downloading, BytesDownloaded: 50, BytesToDownload: 100);
        var delays = new RecordingDelay();
        var automation = new FakeSteamAutomation(
            onDispatch: uri => Assert.That(uri, Is.EqualTo("steam://uninstall/888")),
            onCancel: appId =>
            {
                Assert.That(appId, Is.EqualTo("888"));
                observed = observed with { StateFlags = Paused };
            });
        var adapter = new SteamLocalAdapter(
            () => [observed],
            () => new HashSet<string>(["888"], StringComparer.Ordinal),
            automation,
            delays.DelayAsync);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "game.install.cancel", Json("""{"appId":"888"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.Result?.GetProperty("state").GetString(), Is.EqualTo("paused"));
            Assert.That(automation.CancelCount, Is.EqualTo(1));
            Assert.That(automation.Confirmed, Is.EqualTo(new[] { "Desinstalar", "Uninstall" }));
            Assert.That(delays.Calls, Is.Zero);
        });
    }

    [Test]
    public async Task LaunchVerifiesImmediateProcessPostreadWithoutDelay()
    {
        string installDirectory = Path.Combine(
            Path.GetTempPath(),
            "baxy-steam-launch-fixture");
        bool launched = false;
        int processReads = 0;
        var delays = new RecordingDelay();
        var automation = new FakeSteamAutomation(
            onDispatch: uri =>
            {
                Assert.That(uri, Is.EqualTo("steam://rungameid/620"));
                launched = true;
            });
        IReadOnlyList<SteamProcessObservation> ProcessSnapshot()
        {
            processReads++;
            return launched
                ? [new SteamProcessObservation(
                    4242,
                    Path.Combine(installDirectory, "portal2.exe"))]
                : [];
        }

        SteamLocalGame installed = Catalog[0] with
        {
            InstallDirectory = installDirectory,
        };
        var adapter = new SteamLocalAdapter(
            () => [installed],
            () => new HashSet<string>(["620"], StringComparer.Ordinal),
            automation,
            delays.DelayAsync,
            ProcessSnapshot);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "game.launch",
            Json("""{"appId":"620","title":"Portal 2"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.Result?.GetProperty("processId").GetInt32(), Is.EqualTo(4242));
            Assert.That(receipt.Result?.GetProperty("authority").GetString(),
                Is.EqualTo("steam_manifest_process_postread"));
            Assert.That(processReads, Is.EqualTo(2));
            Assert.That(delays.Calls, Is.Zero);
        });
    }

    // Renew al máximo (auditoría de flujos): the launched game's process was looked for by its main module, which Windows
    // refuses for an elevated game or one its anti-cheat protects: launched, it was said not verified after 35 s. It is
    // read as the game already running is, by the executable's image with the least access.
    // Ajuste c5: el título de un juego de la biblioteca sigue yendo por Steam aunque el appId no sirva.
    [TestCase("""{"appId":"620","title":"Portal 2"}""")]
    [TestCase("""{"appId":"0","title":"portal 2"}""")]
    [TestCase("""{"appId":"portal2","title":"Portal 2"}""")]
    // Encargo 10 (punto 2): a well-formed appId no game bears is dropped as an ill-formed one already was, so a library
    // title still launches its own game.
    [TestCase("""{"appId":"999","title":"Portal 2"}""")]
    public async Task ALaunchedGameIsFoundByItsImageEvenWhenItsModulesCannotBeRead(string arguments)
    {
        string installDirectory = Path.Combine(Path.GetTempPath(), "baxy-steam-launch-fixture");
        bool launched = false;
        var automation = new FakeSteamAutomation(onDispatch: _ => launched = true);
        SteamLocalGame installed = Catalog[0] with { InstallDirectory = installDirectory };
        var adapter = new SteamLocalAdapter(
            () => [installed],
            () => new HashSet<string>(["620"], StringComparer.Ordinal),
            automation,
            new RecordingDelay().DelayAsync,
            processIds: () => launched ? [7, 2_000_000_001] : [7],
            imagePath: id => id == 2_000_000_001 ? Path.Combine(installDirectory, "portal2.exe") : null);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "game.launch", Json(arguments), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True, receipt.ErrorCode);
            Assert.That(receipt.Result?.GetProperty("processId").GetInt32(), Is.EqualTo(2_000_000_001));
        });
    }

    // Renew al máximo (falsedades F001/F016): the model launched Rocket League's appId, the one game installed, for
    // «Doom Eternal» and for «Fortnite», twice in front of the owner. The title asked for goes in the call and is the
    // manifest's own (folded as an entitlement's title is): another, or none, fails before anything is sent, with the
    // games installed.
    [TestCase("""{"appId":"620","title":"Doom Eternal"}""", "game_title_mismatch")]
    [TestCase("""{"appId":"620"}""", "game_title_required")]
    public async Task ALaunchOfAnotherGamesAppIdIsNeverSent(string arguments, string code)
    {
        var automation = new FakeSteamAutomation(onDispatch: _ => Assert.Fail("nothing is sent to Steam"));
        SteamLocalGame installed = Catalog[0] with { InstallDirectory = Path.Combine(Path.GetTempPath(), "baxy-steam-launch-fixture") };
        var adapter = new SteamLocalAdapter(
            () => [installed],
            () => new HashSet<string>(["620"], StringComparer.Ordinal),
            automation,
            new RecordingDelay().DelayAsync,
            () => []);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync("game.launch", Json(arguments), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(code));
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.Result?.GetProperty("installedGames")[0].GetProperty("name").GetString(), Is.EqualTo("Portal 2"));
        });
    }

    // Banco ciego c3 C3-049 (las tres semillas; también C3-142): «abre Luanti», a game installed outside Steam, went as
    // game.launch with an invented appId; the receipt listed Steam's games and the reply said «no hay Luanti instalado:
    // sí tienes Cuphead». A title the Steam library does not hold says that list is only that library and that app_open
    // with the name said opens a game installed outside it; one the library holds under another appId says nothing more.
    [TestCase("""{"appId":"620","title":"Luanti"}""", "game_title_mismatch", true)]
    [TestCase("""{"appId":"458830","title":"Luanti"}""", "steam_installed_game_not_verified", true)]
    // Ajuste c5: un juego fuera de la biblioteca no tiene appId que copiar; lo que el modelo escriba ahí no para la búsqueda.
    [TestCase("""{"appId":"zarvok","title":"Luanti"}""", "steam_installed_game_not_verified", true)]
    [TestCase("""{"appId":"0","title":"Luanti"}""", "steam_installed_game_not_verified", true)]
    [TestCase("""{"appId":"620","title":"Another Game"}""", "game_title_mismatch", false)]
    // Encargo 10 (punto 2): «999» for an installed library title no longer fails; it launches (ALaunchedGame… covers it).
    public async Task ATitleOutsideTheSteamLibraryIsNotToldAsNotInstalled(string arguments, string code, bool outside)
    {
        var automation = new FakeSteamAutomation(onDispatch: _ => Assert.Fail("nothing is sent to Steam"));
        SteamLocalGame installed = Catalog[0] with { InstallDirectory = Path.Combine(Path.GetTempPath(), "baxy-steam-launch-fixture") };
        var adapter = new SteamLocalAdapter(
            () => [installed, Catalog[1] with { InstallDirectory = Path.Combine(Path.GetTempPath(), "baxy-steam-other") }],
            () => new HashSet<string>(["620", "123"], StringComparer.Ordinal),
            automation,
            new RecordingDelay().DelayAsync,
            () => []);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync("game.launch", Json(arguments), CancellationToken.None);

        string? next = receipt.Result is { } result && result.TryGetProperty("next", out JsonElement said)
            ? said.GetString()
            : null;
        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo(code));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            if (outside)
            {
                Assert.That(next, Does.Contain("only the Steam games installed on this PC"));
                Assert.That(next, Does.Contain("app_open with appId «Luanti»"));
                // Encargo 34: measured, the call first opened the game outside Steam when the person had said not to.
                Assert.That(next, Does.Not.StartWith("app_open {"));
                Assert.That(receipt.Result!.Value.GetProperty("outsideLibrary").GetBoolean(), Is.True);
            }
            else
            {
                Assert.That(next, Is.Null);
            }
        });
    }

    // Encargo 10 (punto 1): a title the library holds but is still downloading (Installed=false) is not said as outside
    // the library and sent to the Start menu; its real state is said and game.install.status reads its progress.
    // Its own appId, or an invented one the title still resolves (punto 2); both say the downloading state, not outside.
    [TestCase("""{"appId":"77","title":"Downloading Game"}""")]
    [TestCase("""{"appId":"999","title":"Downloading Game"}""")]
    public async Task ADownloadingLibraryTitleIsSaidWithItsStateNotAsOutsideTheLibrary(string arguments)
    {
        var automation = new FakeSteamAutomation(onDispatch: _ => Assert.Fail("nothing is sent to Steam"));
        SteamLocalGame[] snapshot =
        [
            Catalog[0] with { InstallDirectory = Path.Combine(Path.GetTempPath(), "baxy-steam-launch-fixture") },
            new("77", "Downloading Game", new string('d', 64), Downloading, 250, 1000),
        ];
        var adapter = new SteamLocalAdapter(
            () => snapshot,
            () => new HashSet<string>(["620", "77"], StringComparer.Ordinal),
            automation,
            new RecordingDelay().DelayAsync,
            () => []);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync("game.launch", Json(arguments), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("steam_game_not_installed"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.Result?.GetProperty("state").GetString(), Is.EqualTo("downloading"));
            // Encargo 34: the read of its progress comes first, as the call with its argument written.
            Assert.That(receipt.Result?.GetProperty("next").GetString(), Is.EqualTo(
                "game_install_status {\"appId\":\"77\",\"title\":\"Downloading Game\"} reads its progress; a game is not "
                + "launched until it finishes installing"));
            Assert.That(receipt.Result!.Value.TryGetProperty("outsideLibrary", out _), Is.False);
        });
    }

    // Renew al máximo (B-APP-8): a game already running is the state reached: nothing is sent to Steam (no window of it
    // minimized, no «Jugar» pressed) and nothing is waited for; the receipt names the process that runs.
    [Test]
    public async Task AGameAlreadyRunningIsTheStateReached()
    {
        string installDirectory = Path.Combine(Path.GetTempPath(), "baxy-steam-launch-fixture");
        var delays = new RecordingDelay();
        var automation = new FakeSteamAutomation(onDispatch: null);
        SteamLocalGame installed = Catalog[0] with { InstallDirectory = installDirectory };
        var adapter = new SteamLocalAdapter(
            () => [installed],
            () => new HashSet<string>(["620"], StringComparer.Ordinal),
            automation,
            delays.DelayAsync,
            () =>
            [
                new SteamProcessObservation(7, null),
                new SteamProcessObservation(4242, Path.Combine(installDirectory, "bin", "portal2.exe")),
            ]);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "game.launch", Json("""{"appId":"620","title":"portal 2"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.StateAlreadyReached, Is.True);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.Result?.GetProperty("alreadyRunning").GetBoolean(), Is.True);
            Assert.That(receipt.Result?.GetProperty("processId").GetInt32(), Is.EqualTo(4242));
            Assert.That(automation.DispatchCount, Is.Zero);
            Assert.That(automation.ContinueCount, Is.Zero);
            Assert.That(delays.Calls, Is.Zero);
        });
    }

    [Test]
    public async Task InstallFailureRetainsThirtySecondRetryHorizon()
    {
        int snapshots = 0;
        var delays = new RecordingDelay();
        var game = new SteamLocalGame(
            "777",
            "Owned Game",
            new string('c', 64),
            StateFlags: 0,
            BytesDownloaded: 0,
            BytesToDownload: 100);
        var adapter = new SteamLocalAdapter(
            () =>
            {
                snapshots++;
                return [game];
            },
            () => new HashSet<string>(["777"], StringComparer.Ordinal),
            new FakeSteamAutomation(onDispatch: null),
            delays.DelayAsync);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "game.install.named",
            Json("""{"title":"Owned Game"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("steam_install_transition_not_verified"));
            Assert.That(snapshots, Is.EqualTo(64));
            AssertRetryHorizon(delays, expectedIntervals: 60, intervalMilliseconds: 500);
        });
    }

    [Test]
    public async Task CancelFailureRetainsFifteenSecondRetryHorizon()
    {
        int snapshots = 0;
        var delays = new RecordingDelay();
        var game = new SteamLocalGame(
            "888",
            "Partial Game",
            new string('d', 64),
            StateFlags: 1,
            BytesDownloaded: 50,
            BytesToDownload: 100);
        var adapter = new SteamLocalAdapter(
            () =>
            {
                snapshots++;
                return [game];
            },
            () => new HashSet<string>(["888"], StringComparer.Ordinal),
            new FakeSteamAutomation(onDispatch: null),
            delays.DelayAsync);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "game.install.cancel",
            Json("""{"appId":"888"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("steam_cancel_not_verified"));
            Assert.That(snapshots, Is.EqualTo(32));
            AssertRetryHorizon(delays, expectedIntervals: 30, intervalMilliseconds: 500);
        });
    }

    [Test]
    public async Task LaunchFailureRetainsThirtyFiveSecondRetryHorizonAndDialogTiming()
    {
        string installDirectory = Path.Combine(
            Path.GetTempPath(),
            "baxy-steam-launch-fixture");
        int processReads = 0;
        var delays = new RecordingDelay();
        TimeSpan? dialogAt = null;
        var automation = new FakeSteamAutomation(
            onDispatch: null,
            onContinue: () => dialogAt = delays.Elapsed);
        SteamLocalGame installed = Catalog[0] with
        {
            InstallDirectory = installDirectory,
        };
        var adapter = new SteamLocalAdapter(
            () => [installed],
            () => new HashSet<string>(["620"], StringComparer.Ordinal),
            automation,
            delays.DelayAsync,
            () =>
            {
                processReads++;
                return [];
            });

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "game.launch",
            Json("""{"appId":"620","title":"Portal 2"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("steam_launch_process_not_verified"));
            Assert.That(processReads, Is.EqualTo(72));
            Assert.That(automation.ContinueCount, Is.EqualTo(1));
            Assert.That(automation.Confirmed, Is.EqualTo(new[] { "Jugar", "Play" }));
            Assert.That(dialogAt, Is.EqualTo(TimeSpan.FromSeconds(5)));
            AssertRetryHorizon(delays, expectedIntervals: 70, intervalMilliseconds: 500);
        });
    }

    [Test]
    public async Task CancelActivePausesEveryObservedSteamDownloadAndPostreadsZeroRemaining()
    {
        var observed = new Dictionary<string, SteamLocalGame>(StringComparer.Ordinal)
        {
            ["888"] = new("888", "Partial One", new string('d', 64), Downloading, 50, 100),
            // Renew al máximo (B-APP-4): a download in pause was started too, and is cancelled as well.
            ["999"] = new("999", "Partial Two", new string('e', 64), Paused, 25, 100),
        };
        var automation = new FakeSteamAutomation(
            onDispatch: null,
            onCancel: appId => observed.Remove(appId));
        var adapter = new SteamLocalAdapter(
            () => observed.Values.ToArray(),
            () => observed.Keys.ToHashSet(StringComparer.Ordinal),
            automation);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "game.install.cancel.active", Json("{}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("canceledCount").GetInt32(), Is.EqualTo(2));
            Assert.That(receipt.Result?.GetProperty("remainingActiveCount").GetInt32(), Is.Zero);
            Assert.That(receipt.StateAlreadyReached, Is.False);
            Assert.That(automation.CancelCount, Is.EqualTo(2));
        });
    }

    // Ronda B: with no download active there is nothing to cancel: the request already reached (changed:false), never
    // an unobserved effect.
    [Test]
    public async Task CancelActiveWithNoActiveDownloadIsAlreadyReached()
    {
        var automation = new FakeSteamAutomation(onDispatch: null, onCancel: null);
        var adapter = new SteamLocalAdapter(
            () => Catalog,
            () => new HashSet<string>(StringComparer.Ordinal),
            automation);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "game.install.cancel.active", Json("{}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(receipt.StateAlreadyReached, Is.True);
            Assert.That(receipt.Result?.GetProperty("canceledCount").GetInt32(), Is.Zero);
            Assert.That(automation.CancelCount, Is.Zero);
        });
    }

    // Ronda final 32 (regla 3): a new install queued with no bytes yet (1026) is not cancelled by this operation, so it
    // never says no download is left.
    [Test]
    public async Task CancelActiveNeverSaysNoneLeftWithAQueuedInstall()
    {
        var automation = new FakeSteamAutomation(onDispatch: null, onCancel: null);
        var adapter = new SteamLocalAdapter(
            () => [.. Catalog, new SteamLocalGame("367520", "Hollow Knight", "hk-sha", StateFlags: 1026)],
            () => new HashSet<string>(StringComparer.Ordinal),
            automation);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "game.install.cancel.active", Json("{}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("steam_downloads_not_covered"));
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(automation.CancelCount, Is.Zero);
        });
    }

    // Renew al máximo (w8): an installed game's update in pause (Installed | UpdateStarted | UpdatePaused, 1540) is no
    // active download: with nothing else, cancelling every download is already so, never steam_downloads_not_covered.
    [Test]
    public async Task CancelActiveTakesAPausedUpdateForNoActiveDownload()
    {
        var automation = new FakeSteamAutomation(onDispatch: null, onCancel: null);
        var adapter = new SteamLocalAdapter(
            () => [.. Catalog, new SteamLocalGame("367520", "Hollow Knight", "hk-sha", StateFlags: 4 | 1024 | 512)],
            () => new HashSet<string>(StringComparer.Ordinal),
            automation);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "game.install.cancel.active", Json("{}"), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.Null);
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.StateAlreadyReached, Is.True);
            Assert.That(automation.CancelCount, Is.Zero);
        });
    }

    [Test]
    public async Task SnapshotFailureAfterAcceptedDispatchPreservesAmbiguousEffect()
    {
        int snapshots = 0;
        var game = new SteamLocalGame(
            "1145360",
            "Hades",
            new string('f', 64),
            StateFlags: 0,
            BytesDownloaded: 0,
            BytesToDownload: 100);
        IReadOnlyList<SteamLocalGame> Snapshot()
        {
            snapshots++;
            // Encargo imp-steam: the title resolves on the manifests (no title is written in code any more), the
            // install reads them, the dispatch takes its baseline: the first read after the accepted dispatch fails.
            if (snapshots >= 4)
            {
                throw new IOException("simulated post-dispatch manifest read failure");
            }

            return [game];
        }

        var automation = new FakeSteamAutomation(onDispatch: null);
        var adapter = new SteamLocalAdapter(
            Snapshot,
            () => new HashSet<string>(["1145360"], StringComparer.Ordinal),
            automation);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "game.install.named",
            Json("""{"title":"Hades"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(automation.DispatchCount, Is.EqualTo(1));
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.True);
            Assert.That(receipt.ErrorCode, Is.EqualTo("steam_local_adapter_failed"));
        });
    }

    // Encargo imp-steam: a game that is not installed (the owner's test game, Super Meat Boy) turns into its catalog
    // number by the store's title search, whose exact title wins over its namesakes; the account's local cache is no
    // gate (measured: it does not list that game although the account holds it). The address is the data's, the dialog
    // is confirmed by its labels, and the manifest born for it is the proof.
    [Test]
    public async Task ATitleNotInstalledResolvesByTheStoreSearchAndItsDialogIsConfirmed()
    {
        SteamLocalGame? observed = null;
        string? searched = null;
        var automation = new FakeSteamAutomation(
            uri => Assert.That(uri, Is.EqualTo("steam://install/40800")),
            onConfirm: () => observed = new SteamLocalGame("40800", "Super Meat Boy", new string('a', 64), StateFlags: 1026));
        var adapter = new SteamLocalAdapter(
            () => observed is null ? Catalog : [.. Catalog, observed],
            () => new HashSet<string>(StringComparer.Ordinal),
            automation,
            (_, _) => ValueTask.CompletedTask,
            storeTitles: (title, _) =>
            {
                searched = title;
                return ValueTask.FromResult<IReadOnlyList<SteamStoreTitle>>(
                [
                    new("40800", "Super Meat Boy"),
                    new("581660", "Super Meat Boy Forever"),
                    new("3288210", "Super Meat Boy 3D"),
                ]);
            });

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "game.install.named", Json("""{"title":"super meat boy","store":"steam"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(searched, Is.EqualTo("super meat boy"));
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.True);
            Assert.That(receipt.Result?.GetProperty("appId").GetString(), Is.EqualTo("40800"));
            Assert.That(receipt.Result?.GetProperty("name").GetString(), Is.EqualTo("Super Meat Boy"));
            Assert.That(receipt.Result?.GetProperty("authority").GetString(), Is.EqualTo("steam_manifest_transition"));
            Assert.That(automation.Confirmed, Is.EqualTo(new[] { "Instalar", "Install" }));
        });
    }

    // Counter-cases: an installed title never asks the store; a store answer with no game of exactly that title, or two
    // of them, resolves nothing and nothing is opened.
    [TestCase("Portal 2", true)]
    [TestCase("Super Meat", false)]
    [TestCase("Doubled", false)]
    public async Task OnlyOneExactTitleResolvesAndNothingElseIsOpened(string title, bool installed)
    {
        bool asked = false;
        var automation = new FakeSteamAutomation(onDispatch: null);
        var adapter = new SteamLocalAdapter(
            () => Catalog,
            () => new HashSet<string>(StringComparer.Ordinal),
            automation,
            (_, _) => ValueTask.CompletedTask,
            storeTitles: (said, _) =>
            {
                asked = true;
                return ValueTask.FromResult<IReadOnlyList<SteamStoreTitle>>(
                [
                    new("40800", "Super Meat Boy"),
                    new("11", "Doubled"),
                    new("12", "DOUBLED"),
                ]);
            });

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "game.install.named", Json($$"""{"title":"{{title}}"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(asked, Is.EqualTo(!installed));
            Assert.That(receipt.ErrorCode, Is.EqualTo(installed ? null : "steam_title_not_resolved"));
            Assert.That(automation.DispatchCount, Is.Zero);
        });
    }

    // Renew al máximo (B-APP-6): whether a game is in the library is read on this PC alone: the title resolves only by
    // the installed games' manifests and never goes to the store; one no manifest bears is said as such, unresolved.
    [TestCase("Portal 2", true, 1)]
    [TestCase("Super Meat Boy", false, 0)]
    [TestCase("Doubled", false, 2)]
    public async Task EntitlementNeverSearchesTheStore(string title, bool resolved, int bearing)
    {
        bool asked = false;
        var adapter = new SteamLocalAdapter(
            () => [.. Catalog, new("11", "Doubled", "d1"), new("12", "DOUBLED", "d2")],
            () => new HashSet<string>(["620"], StringComparer.Ordinal),
            new FakeSteamAutomation(onDispatch: null),
            (_, _) => ValueTask.CompletedTask,
            storeTitles: (_, _) =>
            {
                asked = true;
                return ValueTask.FromResult<IReadOnlyList<SteamStoreTitle>>([new("40800", "Super Meat Boy")]);
            });

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "game.entitlement.named", Json($$"""{"title":"{{title}}"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(asked, Is.False);
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("resolved").GetBoolean(), Is.EqualTo(resolved));
            Assert.That(receipt.Result?.GetProperty("state").GetString(),
                Is.EqualTo(resolved ? "installed" : "title_not_resolved"));
            Assert.That(receipt.Result?.GetProperty("steamManifestsWithThatName").GetInt32(), Is.EqualTo(bearing));
            Assert.That(receipt.Result?.GetProperty("authority").GetString(), Is.EqualTo("steam_local_appmanifest"));
        });
    }

    // Feria (caso 15): a game not on this PC left the same title_not_resolved as a title no game bears, and nothing
    // said the title was looked up only among this PC's manifests: the answer was that Steam has no such game. The
    // receipt says where the title was looked up, so an unresolved title is neither «it does not exist» nor «not owned».
    [Test]
    public async Task AnUnresolvedTitleSaysItWasLookedUpOnlyAmongThisPcsGames()
    {
        var adapter = new SteamLocalAdapter(
            () => Catalog,
            () => new HashSet<string>(["620"], StringComparer.Ordinal),
            new FakeSteamAutomation(onDispatch: null),
            (_, _) => ValueTask.CompletedTask);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "game.entitlement.named", Json("""{"title":"A Game Not On This PC"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Result?.GetProperty("state").GetString(), Is.EqualTo("title_not_resolved"));
            Assert.That(receipt.Result?.GetProperty("titleLookedUpAmong").GetString(),
                Is.EqualTo("games_installed_or_downloading_on_this_pc"));
        });
    }

    // Feria (caso 15): a game not on this PC resolves by the games this Steam client knows (its local app cache), and
    // the library cache then says whether it is the person's; a title this Steam does not know stays unresolved, said as
    // looked up among those games, which are not the whole store. Nothing goes to the store.
    [TestCase("Owned Elsewhere", true, "owned_not_installed")]
    [TestCase("Known Not Owned", true, "not_in_local_library_cache")]
    [TestCase("Unknown Here", false, "title_not_resolved")]
    public async Task ATitleNotOnThisPcResolvesByTheGamesThisSteamKnows(string title, bool resolved, string state)
    {
        bool asked = false;
        var adapter = new SteamLocalAdapter(
            () => Catalog,
            () => new HashSet<string>(["620", "700"], StringComparer.Ordinal),
            new FakeSteamAutomation(onDispatch: _ => Assert.Fail("nothing is sent to Steam")),
            (_, _) => ValueTask.CompletedTask,
            storeTitles: (_, _) =>
            {
                asked = true;
                return ValueTask.FromResult<IReadOnlyList<SteamStoreTitle>>([]);
            },
            knownGames: () => [new("700", "Owned Elsewhere"), new("701", "Known Not Owned"), new("620", "Portal 2")]);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "game.entitlement.named", Json($$"""{"title":"{{title}}"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(asked, Is.False);
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("resolved").GetBoolean(), Is.EqualTo(resolved));
            Assert.That(receipt.Result?.GetProperty("state").GetString(), Is.EqualTo(state));
            Assert.That(receipt.Result?.GetProperty("titleLookedUpAmong").GetString(),
                Is.EqualTo("games_on_this_pc_and_games_this_steam_client_knows"));
            Assert.That(receipt.Result?.GetProperty("steamKnownGamesWithThatName").GetInt32(), Is.EqualTo(resolved ? 1 : 0));
            if (resolved) Assert.That(receipt.Result?.GetProperty("installed").GetBoolean(), Is.False);
        });
    }

    // Revisión: two known games bearing one title resolve to the one in the library cache; a known game near the title
    // is offered only when the cache has it; a cache of known games that could not be read is said.
    [Test]
    public async Task KnownGamesSharingATitleResolveByTheLibraryCacheAndOnlyOwnedOnesAreOffered()
    {
        static SteamLocalAdapter Adapter(Func<IReadOnlyList<SteamStoreTitle>?> knownGames) => new(
            () => Catalog,
            () => new HashSet<string>(["700"], StringComparer.Ordinal),
            new FakeSteamAutomation(onDispatch: _ => Assert.Fail("nothing is sent to Steam")),
            (_, _) => ValueTask.CompletedTask,
            knownGames: knownGames);
        IReadOnlyList<SteamStoreTitle> known =
            [new("700", "Shared Name"), new("701", "Shared Name"), new("702", "Store Only Game")];

        ExternalCapabilityReceipt shared = await Adapter(() => known).InvokeAsync(
            "game.entitlement.named", Json("""{"title":"Shared Name"}"""), CancellationToken.None);
        ExternalCapabilityReceipt near = await Adapter(() => known).InvokeAsync(
            "game.entitlement.named", Json("""{"title":"Store Only Gam"}"""), CancellationToken.None);
        ExternalCapabilityReceipt unread = await Adapter(() => null).InvokeAsync(
            "game.entitlement.named", Json("""{"title":"Shared Name"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(shared.Result?.GetProperty("appId").GetString(), Is.EqualTo("700"));
            Assert.That(shared.Result?.GetProperty("state").GetString(), Is.EqualTo("owned_not_installed"));
            Assert.That(shared.Result?.GetProperty("steamKnownGamesWithThatName").GetInt32(), Is.EqualTo(2));
            Assert.That(near.Result?.GetProperty("state").GetString(), Is.EqualTo("title_not_resolved"));
            Assert.That(near.Result?.ToString(), Does.Not.Contain("Store Only Game"));
            Assert.That(unread.Result?.GetProperty("state").GetString(), Is.EqualTo("title_not_resolved"));
            Assert.That(unread.Result?.GetProperty("knownGamesUnread").GetBoolean(), Is.True);
            Assert.That(unread.Result?.GetProperty("titleLookedUpAmong").GetString(),
                Is.EqualTo("games_installed_or_downloading_on_this_pc"));
        });
    }

    // Renew al máximo (B-APP-5): a store search that got no answer (offline, a timeout, an error status, a body not
    // read) is said as such before any effect, never as a title no game bears.
    [TestCase(0)]
    [TestCase(1)]
    [TestCase(2)]
    public async Task AStoreSearchThatFailedIsNotAnUnresolvedTitle(int failure)
    {
        var automation = new FakeSteamAutomation(onDispatch: null);
        var adapter = new SteamLocalAdapter(
            () => Catalog,
            () => new HashSet<string>(StringComparer.Ordinal),
            automation,
            (_, _) => ValueTask.CompletedTask,
            storeTitles: (_, _) => failure switch
            {
                0 => throw new HttpRequestException("simulated offline store"),
                1 => throw new TaskCanceledException("simulated store timeout"),
                _ => throw new JsonException("simulated cut answer"),
            });

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "game.install.named", Json("""{"title":"Super Meat Boy"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("steam_store_search_failed"));
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.EffectMayHaveOccurred, Is.False);
            Assert.That(automation.DispatchCount, Is.Zero);
        });
    }

    // Renew al máximo (auditoría de flujos, decision2): a title that is not exactly one game failed with nothing to name
    // next. The closest titles go back as a fact (words in common, a prefix): the store's and the installed games' for an
    // install, only the installed ones when the store did not answer, for an uninstall and for a library check.
    [Test]
    public async Task ATitleNotResolvedNamesTheClosestTitles()
    {
        SteamLocalGame[] catalog = [.. Catalog, new("327030", "Worms W.M.D", new string('c', 64))];
        var automation = new FakeSteamAutomation(onDispatch: _ => Assert.Fail("nothing is sent to Steam"));
        SteamLocalAdapter Adapter(bool online) => new(
            () => catalog,
            () => new HashSet<string>(StringComparer.Ordinal),
            automation,
            (_, _) => ValueTask.CompletedTask,
            storeTitles: (_, _) => online
                ? ValueTask.FromResult<IReadOnlyList<SteamStoreTitle>>(
                    [new("40800", "Super Meat Boy"), new("581660", "Super Meat Boy Forever"), new("9", "Unrelated")])
                : throw new HttpRequestException("simulated offline store"));

        ExternalCapabilityReceipt install = await Adapter(online: true).InvokeAsync(
            "game.install.named", Json("""{"title":"super meat"}"""), CancellationToken.None);
        ExternalCapabilityReceipt offline = await Adapter(online: false).InvokeAsync(
            "game.install.named", Json("""{"title":"worms"}"""), CancellationToken.None);
        ExternalCapabilityReceipt uninstall = await Adapter(online: true).InvokeAsync(
            "game.uninstall.named", Json("""{"title":"el worms"}"""), CancellationToken.None);
        ExternalCapabilityReceipt owned = await Adapter(online: true).InvokeAsync(
            "game.entitlement.named", Json("""{"title":"worms"}"""), CancellationToken.None);

        static string?[] Near(ExternalCapabilityReceipt receipt) =>
            [.. receipt.Result!.Value.GetProperty("closestTitles").EnumerateArray().Select(name => name.GetString())];
        Assert.Multiple(() =>
        {
            Assert.That(install.ErrorCode, Is.EqualTo("steam_title_not_resolved"));
            Assert.That(Near(install), Is.EqualTo(new[] { "Super Meat Boy", "Super Meat Boy Forever" }));
            Assert.That(offline.ErrorCode, Is.EqualTo("steam_store_search_failed"));
            Assert.That(Near(offline), Is.EqualTo(new[] { "Worms W.M.D" }));
            Assert.That(uninstall.ErrorCode, Is.EqualTo("no_steam_manifest_with_that_name"));
            Assert.That(Near(uninstall), Is.EqualTo(new[] { "Worms W.M.D" }));
            Assert.That(owned.Result?.GetProperty("state").GetString(), Is.EqualTo("title_not_resolved"));
            Assert.That(Near(owned), Is.EqualTo(new[] { "Worms W.M.D" }));
            Assert.That(automation.DispatchCount, Is.Zero);
        });
    }

    // F39: the ear writes a game's name as words it knows. The store's search answers nothing for the whole of it, and
    // something for its pieces: what sounds like it is said, with what to do next, and nothing is sent to Steam.
    [Test]
    public async Task AMisheardTitleNamesTheGamesItSoundsLike()
    {
        List<string> asked = [];
        var automation = new FakeSteamAutomation(onDispatch: _ => Assert.Fail("nothing is sent to Steam"));
        SteamLocalAdapter Adapter(IReadOnlyList<SteamStoreTitle>? known = null) => new(
            () => Catalog,
            () => new HashSet<string>(StringComparer.Ordinal),
            automation,
            (_, _) => ValueTask.CompletedTask,
            storeTitles: (term, _) =>
            {
                lock (asked)
                    asked.Add(term);
                return ValueTask.FromResult<IReadOnlyList<SteamStoreTitle>>(term == "hollo"
                    ? [new("1", "Hollow Fields"), new("367520", "Hollow Knight"), new("2", "Hollo Clicker Deluxe Edition Pack")]
                    : []);
            },
            knownGames: () => known);

        ExternalCapabilityReceipt heard = await Adapter().InvokeAsync(
            "game.install.named", Json("""{"title":"hollo nite"}"""), CancellationToken.None);
        string[] Near(ExternalCapabilityReceipt receipt) =>
            [.. receipt.Result!.Value.GetProperty("closestTitles").EnumerateArray().Select(name => name.GetString()!)];
        Assert.Multiple(() =>
        {
            Assert.That(heard.ErrorCode, Is.EqualTo("steam_title_not_resolved"));
            Assert.That(Near(heard), Does.Contain("Hollow Knight"));
            Assert.That(asked, Does.Contain("hollo nite").And.Contain("hollo").And.Contain("nite"));
            Assert.That(heard.Result!.Value.GetProperty("next").GetString(),
                Does.Contain("may have been misheard").And.Contain("closestTitles"));
            Assert.That(automation.DispatchCount, Is.Zero);
        });

        // A game only this Steam client knows, written close to what was heard.
        ExternalCapabilityReceipt knownOnly = await Adapter([new("9", "Stardew Valley")]).InvokeAsync(
            "game.install.named", Json("""{"title":"stardu valey"}"""), CancellationToken.None);
        Assert.That(Near(knownOnly), Is.EqualTo(new[] { "Stardew Valley" }));
    }

    // The control: a name like no game offers none, and the model is told so.
    [Test]
    public async Task AnInventedTitleOffersNothingAndAStorePieceThatFailsChangesNothing()
    {
        var automation = new FakeSteamAutomation(onDispatch: _ => Assert.Fail("nothing is sent to Steam"));
        var adapter = new SteamLocalAdapter(
            () => Catalog,
            () => new HashSet<string>(StringComparer.Ordinal),
            automation,
            (_, _) => ValueTask.CompletedTask,
            storeTitles: (term, _) => term == "qwrtz plomb"
                ? ValueTask.FromResult<IReadOnlyList<SteamStoreTitle>>([])
                : term == "plomb"
                    ? throw new HttpRequestException("simulated offline store")
                    : ValueTask.FromResult<IReadOnlyList<SteamStoreTitle>>([new("3", "Zebra Fortress")]));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "game.install.named", Json("""{"title":"qwrtz plomb"}"""), CancellationToken.None);
        Assert.Multiple(() =>
        {
            Assert.That(receipt.ErrorCode, Is.EqualTo("steam_title_not_resolved"));
            Assert.That(receipt.Result!.Value.TryGetProperty("closestTitles", out _), Is.False);
            Assert.That(receipt.Result!.Value.GetProperty("next").GetString(), Does.Contain("game_install_named"));
        });
    }

    // The dialog left unconfirmed (its button not found, nothing pressed) is said as such and the manifest is not
    // waited on; a press that may have landed is judged by the manifest, which here never comes.
    [TestCase(false, "steam_install_dialog_not_confirmed", 3)]
    [TestCase(true, "steam_install_transition_not_verified", 64)]
    public async Task AnUnconfirmedDialogClaimsNothing(bool pressed, string code, int reads)
    {
        int snapshots = 0;
        var automation = new FakeSteamAutomation(
            onDispatch: null, confirmation: new SteamDispatchResult(false, pressed));
        var adapter = new SteamLocalAdapter(
            () =>
            {
                snapshots++;
                return Catalog;
            },
            () => new HashSet<string>(StringComparer.Ordinal),
            automation,
            (_, _) => ValueTask.CompletedTask,
            storeTitles: (_, _) => ValueTask.FromResult<IReadOnlyList<SteamStoreTitle>>([new("40800", "Super Meat Boy")]));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "game.install.named", Json("""{"title":"Super Meat Boy"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(code));
            Assert.That(snapshots, Is.EqualTo(reads));
        });
    }

    // The store's answer is read by the fields the data name; an item without a number or a name is skipped.
    [Test]
    public void TheStoreAnswerIsReadByTheDataFields()
    {
        ApplicationPlaces.TitleSearch search = ApplicationPlaces.TitleSearchOf("steam", "Super Meat Boy")!;
        using JsonDocument answer = JsonDocument.Parse("""
            {"total":4,"items":[{"type":"app","name":"Super Meat Boy","id":40800},{"name":"Super Meat Boy Forever","id":"581660"},
            {"name":"no number"},{"name":"zero","id":"0123"},{"id":7}]}
            """);

        IReadOnlyList<SteamStoreTitle> titles = SteamLocalAdapter.StoreTitles(answer.RootElement, search);

        Assert.That(titles, Is.EqualTo(new[] { new SteamStoreTitle("40800", "Super Meat Boy"), new SteamStoreTitle("581660", "Super Meat Boy Forever") }));
    }

    // Encargo 52 (sesión real del dueño, 03-11): the two appmanifests as the owner's Steam wrote them. Crysis Remastered
    // downloading in pause (StateFlags 514: UpdateRequired | UpdatePaused, 13 943 467 264 of 19 167 361 040 bytes) and
    // R.E.P.O. installed with an update Steam has not started (StateFlags 6: UpdateRequired | FullyInstalled, 0 of
    // 619 374 528 bytes). Flags per Open Steamworks AppsCommon.h (EAppState).
    private static readonly SteamLocalGame CrysisPaused =
        new("1715130", "Crysis Remastered", new string('c', 64), 514, 13_943_467_264, 19_167_361_040);
    private static readonly SteamLocalGame RepoUpdatePending =
        new("3241660", "R.E.P.O.", new string('r', 64), 6, 0, 619_374_528);

    // Turn 3: the manifest Steam writes when it takes the install (UpdateRequired | UpdateStarted, no bytes counted yet)
    // is a job Steam started, not one waiting in its queue; the receipt says the flags it read and the status call that
    // reads the game later, with the game's own appId and title.
    [Test]
    public async Task AnInstallSteamJustStartedIsSaidStartedWithItsFlagsAndItsStatusCall()
    {
        SteamLocalGame? observed = null;
        var automation = new FakeSteamAutomation(
            uri => Assert.That(uri, Is.EqualTo("steam://install/1715130")),
            onConfirm: () => observed = new SteamLocalGame("1715130", "Crysis Remastered", new string('c', 64), StateFlags: 1026));
        var adapter = new SteamLocalAdapter(
            () => observed is null ? [RepoUpdatePending] : [RepoUpdatePending, observed],
            () => new HashSet<string>(StringComparer.Ordinal),
            automation,
            (_, _) => ValueTask.CompletedTask,
            storeTitles: (_, _) => ValueTask.FromResult<IReadOnlyList<SteamStoreTitle>>([new("1715130", "Crysis Remastered")]));

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "game.install.named", Json("""{"title":"crysis remastered","store":"steam"}"""), CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.Result?.GetProperty("appId").GetString(), Is.EqualTo("1715130"));
            Assert.That(receipt.Result?.GetProperty("state").GetString(), Is.EqualTo("started"));
            Assert.That(receipt.Result?.GetProperty("stateFlags").GetUInt64(), Is.EqualTo(1026UL));
            Assert.That(receipt.Result?.GetProperty("next").GetString(), Does.StartWith(
                "game_install_status {\"appId\":\"1715130\",\"title\":\"Crysis Remastered\"}"));
        });
    }

    // Turn 5: the status of an installed game whose update Steam has not started says it is installed, with the update
    // apart (its bytes are the update's, not an install at 0 %), and names the game whose manifest was read.
    [Test]
    public async Task AnInstalledGameWithAPendingUpdateIsInstalledAndItsUpdateIsSaidApart()
    {
        var adapter = new SteamLocalAdapter(() => [CrysisPaused, RepoUpdatePending]);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "game.install.status", Json("""{"appId":"3241660","title":"R.E.P.O."}"""), CancellationToken.None);

        JsonElement result = receipt.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(result.GetProperty("name").GetString(), Is.EqualTo("R.E.P.O."));
            Assert.That(result.GetProperty("state").GetString(), Is.EqualTo("installed"));
            Assert.That(result.GetProperty("stateFlags").GetUInt64(), Is.EqualTo(6UL));
            Assert.That(result.TryGetProperty("progress", out _), Is.False);
            Assert.That(result.GetProperty("update").GetProperty("state").GetString(), Is.EqualTo("queued"));
            Assert.That(result.GetProperty("update").GetProperty("bytesTotal").GetInt64(), Is.EqualTo(619_374_528L));
            Assert.That(result.GetProperty("update").GetProperty("progress").GetString(), Is.EqualTo("0 %"));
        });
    }

    // Turn 5: the model asked the status of R.E.P.O.'s appId about Crysis Remastered. The title said goes in the call
    // and governs: the one manifest bearing it is the game read, and the appId given is said to be another game's.
    [TestCase("""{"appId":"3241660","title":"Crysis Remastered"}""", "R.E.P.O.")]
    [TestCase("""{"appId":"1068900","title":"crysis remastered"}""", null)]
    public async Task AStatusIsTheTitlesGameWhateverAppIdCameWithIt(string arguments, string? givenName)
    {
        var adapter = new SteamLocalAdapter(() => [CrysisPaused, RepoUpdatePending]);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "game.install.status", Json(arguments), CancellationToken.None);

        JsonElement result = receipt.Result!.Value;
        JsonElement given = result.GetProperty("appIdGiven");
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(result.GetProperty("appId").GetString(), Is.EqualTo("1715130"));
            Assert.That(result.GetProperty("name").GetString(), Is.EqualTo("Crysis Remastered"));
            Assert.That(result.GetProperty("state").GetString(), Is.EqualTo("paused"));
            Assert.That(given.GetProperty("appId").GetString(), Is.EqualTo(JsonDocument.Parse(arguments).RootElement
                .GetProperty("appId").GetString()));
            Assert.That(given.TryGetProperty("name", out JsonElement name) ? name.GetString() : null, Is.EqualTo(givenName));
        });
    }

    // With no manifest bearing the title, an appId of another game reads nothing of that game: the failure says which
    // game that appId is and the games in progress, so nothing of another game is told as this one's.
    [TestCase("""{"appId":"3241660","title":"crysis remasterd"}""", "game_title_mismatch")]
    [TestCase("""{"appId":"3241660"}""", "game_title_required")]
    public async Task AStatusOfAnotherGamesAppIdTellsNothingOfIt(string arguments, string code)
    {
        var adapter = new SteamLocalAdapter(() => [CrysisPaused, RepoUpdatePending]);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "game.install.status", Json(arguments), CancellationToken.None);

        JsonElement result = receipt.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo(code));
            Assert.That(result.GetProperty("name").GetString(), Is.EqualTo("R.E.P.O."));
            Assert.That(result.TryGetProperty("state", out _), Is.False);
            Assert.That(result.GetProperty("gamesInProgress").EnumerateArray()
                .Select(game => game.GetProperty("appId").GetString()), Is.EqualTo(new[] { "1715130", "3241660" }));
        });
    }

    // The status of the game asked for, by its own appId and title: the bytes the manifest holds and its flags.
    [Test]
    public async Task TheStatusOfTheGameAskedForSaysItsManifestBytesAndFlags()
    {
        var adapter = new SteamLocalAdapter(() => [CrysisPaused, RepoUpdatePending]);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "game.install.status", Json("""{"appId":"1715130","title":"crysis remastered"}"""), CancellationToken.None);

        JsonElement result = receipt.Result!.Value;
        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(result.GetProperty("name").GetString(), Is.EqualTo("Crysis Remastered"));
            Assert.That(result.GetProperty("state").GetString(), Is.EqualTo("paused"));
            Assert.That(result.GetProperty("stateFlags").GetUInt64(), Is.EqualTo(514UL));
            Assert.That(result.GetProperty("bytesDownloaded").GetInt64(), Is.EqualTo(13_943_467_264L));
            Assert.That(result.GetProperty("progress").GetString(), Is.EqualTo("72,75 %"));
        });
    }

    // A running flag (UpdateRunning 256 or Downloading 1048576) is a download running even before its first bytes are
    // written to the manifest; UpdateStarted with no running flag is started; neither is queued.
    [TestCase(2UL | 1024UL | 1048576UL, "downloading")]
    [TestCase(2UL | 256UL, "downloading")]
    [TestCase(2UL | 1024UL, "started")]
    [TestCase(2UL, "queued")]
    public async Task ADownloadWithNoBytesYetIsSaidByItsFlags(ulong flags, string state)
    {
        var adapter = new SteamLocalAdapter(() => [new SteamLocalGame("1715130", "Crysis Remastered", new string('c', 64), flags)]);

        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "game.install.status", Json("""{"appId":"1715130","title":"Crysis Remastered"}"""), CancellationToken.None);

        Assert.That(receipt.Result?.GetProperty("state").GetString(), Is.EqualTo(state));
    }

    private static JsonElement Json(string value) =>
        JsonDocument.Parse(value).RootElement.Clone();

    private static void AssertRetryHorizon(
        RecordingDelay delay,
        int expectedIntervals,
        int intervalMilliseconds)
    {
        Assert.That(delay.Calls, Is.EqualTo(expectedIntervals));
        Assert.That(
            delay.Delays,
            Is.All.EqualTo(TimeSpan.FromMilliseconds(intervalMilliseconds)));
        Assert.That(
            delay.Elapsed,
            Is.EqualTo(TimeSpan.FromMilliseconds(
                expectedIntervals * intervalMilliseconds)));
    }

    internal sealed class FakeSteamAutomation(
        Action<string>? onDispatch,
        Action<string>? onCancel = null,
        Action? onContinue = null,
        Action? onConfirm = null,
        SteamDispatchResult? confirmation = null) : ISteamClientAutomation
    {
        private string _lastUri = string.Empty;

        internal int DispatchCount { get; private set; }
        internal int CancelCount { get; private set; }
        internal int ContinueCount { get; private set; }
        internal IReadOnlyList<string> Confirmed { get; private set; } = [];

        public ValueTask<SteamDispatchResult> DispatchAsync(
            string uri, CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            DispatchCount++;
            _lastUri = uri;
            onDispatch?.Invoke(uri);
            return ValueTask.FromResult(new SteamDispatchResult(true, true));
        }

        // Steam's own dialog for the last address, confirmed by its labels: an uninstall's removes the game.
        public ValueTask<SteamDispatchResult> ConfirmAsync(
            SteamDispatchResult dispatch,
            IReadOnlyList<string> labels,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            Confirmed = labels;
            if (_lastUri.StartsWith("steam://rungameid/", StringComparison.Ordinal))
            {
                // The launch's dialog, when no process came by itself: nothing found to press.
                ContinueCount++;
                onContinue?.Invoke();
                return ValueTask.FromResult(new SteamDispatchResult(false, false));
            }

            SteamDispatchResult result = confirmation ?? new SteamDispatchResult(true, true);
            if (result.Accepted || result.EffectObserved)
            {
                const string Uninstall = "steam://uninstall/";
                if (_lastUri.StartsWith(Uninstall, StringComparison.Ordinal))
                {
                    CancelCount++;
                    onCancel?.Invoke(_lastUri[Uninstall.Length..]);
                }

                onConfirm?.Invoke();
            }

            return ValueTask.FromResult(result);
        }


    }

    private sealed class RecordingDelay
    {
        private readonly List<TimeSpan> _delays = [];

        internal int Calls => _delays.Count;

        internal IReadOnlyList<TimeSpan> Delays => _delays;

        internal TimeSpan Elapsed { get; private set; }

        internal ValueTask DelayAsync(
            TimeSpan delay,
            CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            _delays.Add(delay);
            Elapsed += delay;
            return ValueTask.CompletedTask;
        }
    }

    // BAXY Renew cu (C04): a game's page by its title. The installed game bearing it first; else the store's one game
    // bearing it; else the first, in the store's order, whose name holds every word of it; else none.
    // Renew al máximo (auditoría de flujos): with no network, a game page asked for by its title was «game_title_not_found»;
    // a search that got no answer is said as such.
    [Test]
    public void AGamePageSearchThatGotNoAnswerIsNotATitleNothingBears()
    {
        static ValueTask<IReadOnlyList<SteamStoreTitle>> Offline(string title, CancellationToken token) =>
            throw new HttpRequestException("simulated offline store");

        Assert.ThrowsAsync<Baxy.Providers.Windows.Applications.GameTitleSearchFailedException>(async () =>
            await SteamLocalAdapter.PageTitleAsync("Hades", default, () => [], Offline));
    }

    [Test]
    public async Task AGamePageTitleIsTheInstalledOneThenTheStoreOneBearingItThenTheFirstHoldingItsWords()
    {
        SteamLocalGame[] installed = [new SteamLocalGame("367520", "Hollow Knight", "hk-sha", StateFlags: 4)];
        SteamStoreTitle[] store =
        [
            new("1030300", "Hollow Knight: Silksong"),
            new("289070", "Sid Meier's Civilization VI"),
            new("8930", "Sid Meier's Civilization V"),
            new("40800", "Super Meat Boy"),
            new("581300", "Super Meat Boy Forever"),
        ];
        ValueTask<IReadOnlyList<SteamStoreTitle>> Search(string title, CancellationToken token) =>
            ValueTask.FromResult<IReadOnlyList<SteamStoreTitle>>(store);

        SteamStoreTitle? hollow = await SteamLocalAdapter.PageTitleAsync("hollow knight", default, () => installed, Search);
        SteamStoreTitle? civ = await SteamLocalAdapter.PageTitleAsync("Sid Meier Civilization VI", default, () => [], Search);
        SteamStoreTitle? meat = await SteamLocalAdapter.PageTitleAsync("Super Meat Boy", default, () => [], Search);
        SteamStoreTitle? none = await SteamLocalAdapter.PageTitleAsync("Batman Arkham", default, () => [], Search);

        Assert.Multiple(() =>
        {
            Assert.That(hollow, Is.EqualTo(new SteamStoreTitle("367520", "Hollow Knight")));
            Assert.That(civ, Is.EqualTo(new SteamStoreTitle("289070", "Sid Meier's Civilization VI")));
            Assert.That(meat, Is.EqualTo(new SteamStoreTitle("40800", "Super Meat Boy")));
            Assert.That(none, Is.Null);
        });
    }

    // Cosecha 04-11 F34: «¿a qué le di la última vez?» took the first by name with limit 1; a manifest's LastPlayed
    // says it, whatever the view leaves out, and each game says its own.
    [Test]
    public async Task TheListSaysWhichGameWasLastPlayedWhateverTheViewLeavesOut()
    {
        string library = Path.Combine(Path.GetTempPath(), "baxy-steam-" + Guid.NewGuid().ToString("N"));
        string steamApps = Path.Combine(library, "steamapps");
        Directory.CreateDirectory(steamApps);
        try
        {
            static string Manifest(string id, string name, long played) =>
                $"\"AppState\"\n{{\n\t\"appid\"\t\t\"{id}\"\n\t\"name\"\t\t\"{name}\"\n\t\"StateFlags\"\t\t\"4\"\n"
                + $"\t\"LastPlayed\"\t\t\"{played}\"\n}}\n";
            File.WriteAllText(Path.Combine(steamApps, "appmanifest_10.acf"), Manifest("10", "Alfa", 1_700_000_000));
            File.WriteAllText(Path.Combine(steamApps, "appmanifest_20.acf"), Manifest("20", "Beta", 1_750_000_000));
            File.WriteAllText(Path.Combine(steamApps, "appmanifest_30.acf"), Manifest("30", "Cero", 0));
            IReadOnlyList<SteamLocalGame> games = SteamLocalAdapter.ReadInstalledCatalog([library], File.ReadAllBytes);
            var adapter = new SteamLocalAdapter(() => games);

            JsonElement one = (await adapter.InvokeAsync(
                "game.catalog.list", Json("""{"limit":1}"""), CancellationToken.None)).Result!.Value;
            JsonElement filtered = (await adapter.InvokeAsync(
                "game.catalog.list", Json("""{"query":"Cero"}"""), CancellationToken.None)).Result!.Value;

            Assert.Multiple(() =>
            {
                Assert.That(one.GetProperty("games")[0].GetProperty("name").GetString(), Is.EqualTo("Alfa"));
                Assert.That(one.GetProperty("lastPlayed").GetProperty("name").GetString(), Is.EqualTo("Beta"));
                Assert.That(one.GetProperty("lastPlayed").GetProperty("lastPlayedUtc").GetDateTimeOffset(),
                    Is.EqualTo(DateTimeOffset.FromUnixTimeSeconds(1_750_000_000)));
                Assert.That(one.GetProperty("games")[0].GetProperty("lastPlayedUtc").GetDateTimeOffset(),
                    Is.EqualTo(DateTimeOffset.FromUnixTimeSeconds(1_700_000_000)));
                Assert.That(filtered.TryGetProperty("lastPlayed", out _), Is.False);
                Assert.That(filtered.GetProperty("games")[0].TryGetProperty("lastPlayedUtc", out _), Is.False);
            });
        }
        finally
        {
            Directory.Delete(library, recursive: true);
        }
    }

    // Revisión de calidad (nb-q-apps): Steam deletes a manifest at the end of an uninstall and rewrites it while it
    // downloads; one manifest gone or locked between the listing and its read failed the whole catalog (an IOException
    // out of every poll), and InstalledGames() said «no games», so winget's guard against uninstalling a Steam game was
    // skipped. The other games are still read; a gone manifest is skipped, a locked one leaves its library unread.
    [Test]
    public void OneManifestThatCannotBeReadDoesNotFailTheCatalog()
    {
        string library = Path.Combine(Path.GetTempPath(), "baxy-steam-" + Guid.NewGuid().ToString("N"));
        string steamApps = Path.Combine(library, "steamapps");
        Directory.CreateDirectory(steamApps);
        try
        {
            File.WriteAllText(Path.Combine(steamApps, "appmanifest_10.acf"),
                "\"AppState\"\n{\n\t\"appid\"\t\t\"10\"\n\t\"name\"\t\t\"Portal\"\n\t\"StateFlags\"\t\t\"4\"\n\t\"installdir\"\t\t\"Portal\"\n}\n");
            File.WriteAllText(Path.Combine(steamApps, "appmanifest_20.acf"), "gone");
            File.WriteAllText(Path.Combine(steamApps, "appmanifest_30.acf"), "locked");
            byte[] Read(string path) => Path.GetFileName(path) switch
            {
                "appmanifest_20.acf" => throw new FileNotFoundException("deleted by Steam", path),
                "appmanifest_30.acf" => throw new IOException("sharing violation"),
                _ => File.ReadAllBytes(path),
            };

            IReadOnlyList<SteamLocalGame> games = SteamLocalAdapter.ReadInstalledCatalog([library], Read);

            Assert.Multiple(() =>
            {
                Assert.That(games.Select(game => game.AppId), Is.EqualTo(new[] { "10" }));
                Assert.That(((SteamLocalAdapter.InstalledCatalog)games).UnreadLibraries, Is.EqualTo(1));
            });

            IReadOnlyList<SteamLocalGame> withoutTheLocked = SteamLocalAdapter.ReadInstalledCatalog(
                [library], path => Path.GetFileName(path) == "appmanifest_30.acf"
                    ? throw new FileNotFoundException("deleted by Steam", path)
                    : Read(path));
            Assert.That(((SteamLocalAdapter.InstalledCatalog)withoutTheLocked).UnreadLibraries, Is.EqualTo(0));
        }
        finally
        {
            Directory.Delete(library, recursive: true);
        }
    }

    // Feria (NB-W5): a PC where two accounts signed in to Steam keeps a library cache for each; a game only the other
    // account holds was told owned. Ownership is the signed-in account's cache alone, and every cache only when Steam
    // names no account or that account has none.
    [Test]
    public void OwnershipIsTheSignedInAccountsLibraryCacheAlone()
    {
        string userdata = Path.Combine(Path.GetTempPath(), "baxy-steam-" + Guid.NewGuid().ToString("N"));
        void Cache(string account, params string[] appIds)
        {
            string cache = Path.Combine(userdata, account, "config", "librarycache");
            Directory.CreateDirectory(cache);
            foreach (string appId in appIds)
                File.WriteAllText(Path.Combine(cache, appId + ".json"), "{}");
        }
        try
        {
            Cache("111", "10", "20");
            Cache("222", "30");
            Directory.CreateDirectory(Path.Combine(userdata, "333"));

            Assert.Multiple(() =>
            {
                Assert.That(SteamLocalAdapter.ReadOwnedAppIds(userdata, "111"), Is.EquivalentTo(new[] { "10", "20" }));
                Assert.That(SteamLocalAdapter.ReadOwnedAppIds(userdata, "222"), Is.EquivalentTo(new[] { "30" }));
                Assert.That(SteamLocalAdapter.ReadOwnedAppIds(userdata, null), Is.EquivalentTo(new[] { "10", "20", "30" }));
                Assert.That(SteamLocalAdapter.ReadOwnedAppIds(userdata, "333"), Is.EquivalentTo(new[] { "10", "20", "30" }));
                Assert.That(SteamLocalAdapter.ReadOwnedAppIds(Path.Combine(userdata, "absent"), "111"), Is.Null);
            });
        }
        finally
        {
            Directory.Delete(userdata, recursive: true);
        }
    }

    // Uso real 02-11: a title said short of the Epic cache's, which bears several close to it, is unresolved with the
    // closest titles, never «not in the cache»; one exactly borne is owned; one nothing shares is still not in the cache.
    [TestCase("Brick Knight", "title_not_resolved", false)]
    [TestCase("brick knight™ the saga", "owned_no_epic_manifest_with_that_name", true)]
    [TestCase("Moonlit Harbor", "not_in_local_library_cache", false)]
    public void AnEpicTitleSaidShortIsUnresolvedWithTheClosest(string title, string state, bool owned)
    {
        string root = Path.Combine(Path.GetTempPath(), "baxy-epic-cache-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(Path.Combine(root, "Catalog"));
        File.WriteAllText(Path.Combine(root, "Catalog", "catcache.bin"), Convert.ToBase64String(JsonSerializer.SerializeToUtf8Bytes(
            new[] { "Brick® Knight™ The Saga", "Brick® Knight™ 2 Night Riders", "Knight Arena", "Puzzle Garden" }
                .Select((name, index) => new { id = "item" + index, title = name }))));
        try
        {
            JsonElement result = SteamLocalAdapter.EpicEntitlementNamed("game.entitlement.named", title, root).Result
                ?? throw new AssertionException("the check returned no result");
            Assert.Multiple(() =>
            {
                Assert.That(result.GetProperty("state").GetString(), Is.EqualTo(state));
                Assert.That(result.TryGetProperty("owned", out _), Is.EqualTo(owned));
                Assert.That(result.TryGetProperty("inLocalLibraryCache", out _), Is.EqualTo(state == "not_in_local_library_cache"));
                Assert.That(result.TryGetProperty("closestTitles", out JsonElement closest)
                    ? closest.EnumerateArray().Select(static name => name.GetString()).Take(2) : [],
                    Is.EqualTo(state == "title_not_resolved"
                        ? new[] { "Brick® Knight™ 2 Night Riders", "Brick® Knight™ The Saga" } : Array.Empty<string>()));
            });
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }
}
