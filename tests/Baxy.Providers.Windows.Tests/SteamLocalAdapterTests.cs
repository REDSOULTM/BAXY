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
        foreach (string appId in new[] { "10", "11", "12" })
        {
            ExternalCapabilityReceipt status = await adapter.InvokeAsync(
                "game.install.status", Json($$"""{"appId":"{{appId}}"}"""), CancellationToken.None);
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
            "game.install.status", Json("""{"appId":"620"}"""), CancellationToken.None);

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
}
