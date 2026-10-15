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

    [Test]
    public async Task InstallPrepareDoesNotClaimEntitlementForUnknownAppId()
    {
        var adapter = new SteamLocalAdapter(() => Catalog);
        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "game.install.prepare",
            Json("""{"appId":"999"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("steam_entitlement_not_verified"));
        });
    }

    [TestCase("game.install.prepare")]
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
    public async Task InstalledAppPrepareIsReadOnlyAndReportsAlreadyInstalled()
    {
        var adapter = new SteamLocalAdapter(() => Catalog);
        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "game.install.prepare",
            Json("""{"appId":"620"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.True);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(
                receipt.Result?.GetProperty("state").GetString(),
                Is.EqualTo("already_installed"));
            Assert.That(receipt.Result?.GetProperty("requiresInstall").GetBoolean(), Is.False);
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
            Assert.That(receipt.Result?.GetProperty("appId").GetString(), Is.EqualTo("620"));
            Assert.That(receipt.Result?.GetProperty("state").GetString(),
                Is.EqualTo("already_installed"));
        });
    }

    [Test]
    public async Task MonetaryCommitIsNeverDispatchedByLocalCatalogAdapter()
    {
        var adapter = new SteamLocalAdapter(() => Catalog);
        ExternalCapabilityReceipt receipt = await adapter.InvokeAsync(
            "game.purchase.commit",
            Json("""{"confirmationId":"x","expectedPriceCents":999}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Verified, Is.False);
            Assert.That(receipt.EffectObserved, Is.False);
            Assert.That(receipt.ErrorCode, Is.EqualTo("steam_purchase_live_gate_forbidden"));
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
            new("620", "Portal 2", new string('a', 64), StateFlags: 1,
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
    public async Task InstallCommitRequiresPreparationAndVerifiesManifestTransition()
    {
        SteamLocalGame? observed = null;
        var delays = new RecordingDelay();
        var automation = new FakeSteamAutomation(
            uri => Assert.That(uri, Is.EqualTo("steam://install/777")),
            onConfirm: () => observed = new SteamLocalGame("777", "Owned Game", new string('c', 64),
                StateFlags: 1, BytesDownloaded: 10, BytesToDownload: 100));
        var adapter = new SteamLocalAdapter(
            () => observed is null ? [] : [observed],
            () => new HashSet<string>(["777"], StringComparer.Ordinal),
            automation,
            delays.DelayAsync);

        ExternalCapabilityReceipt prepared = await adapter.InvokeAsync(
            "game.install.prepare", Json("""{"appId":"777"}"""), CancellationToken.None);
        string confirmationId = prepared.Result!.Value.GetProperty("confirmationId").GetString()!;
        ExternalCapabilityReceipt committed = await adapter.InvokeAsync(
            "game.install.commit",
            Json($$"""{"confirmationId":"{{confirmationId}}"}"""),
            CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(committed.Verified, Is.True);
            Assert.That(committed.EffectObserved, Is.True);
            Assert.That(committed.Result?.GetProperty("state").GetString(), Is.EqualTo("downloading"));
            Assert.That(automation.DispatchCount, Is.EqualTo(1));
            Assert.That(automation.Confirmed, Is.EqualTo(new[] { "Instalar", "Install" }));
            Assert.That(delays.Calls, Is.Zero);
        });
    }

    [Test]
    public async Task CancelRequiresPartialDownloadAndVerifiesPausedManifest()
    {
        SteamLocalGame observed = new("888", "Partial Game", new string('d', 64),
            StateFlags: 1, BytesDownloaded: 50, BytesToDownload: 100);
        var delays = new RecordingDelay();
        var automation = new FakeSteamAutomation(
            onDispatch: uri => Assert.That(uri, Is.EqualTo("steam://uninstall/888")),
            onCancel: appId =>
            {
                Assert.That(appId, Is.EqualTo("888"));
                observed = observed with { StateFlags = 2 };
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
            Json("""{"appId":"620"}"""),
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
            Json("""{"appId":"620"}"""),
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
            ["888"] = new("888", "Partial One", new string('d', 64), 1, 50, 100),
            ["999"] = new("999", "Partial Two", new string('e', 64), 1, 25, 100),
        };
        var automation = new FakeSteamAutomation(
            onDispatch: null,
            onCancel: appId => observed[appId] = observed[appId] with { StateFlags = 2 });
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
            Assert.That(automation.CancelCount, Is.EqualTo(2));
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

    // Counter-cases: an installed title never asks the store; a store answer with no game of exactly that title, two of
    // them, or no answer at all resolves nothing and nothing is opened.
    [TestCase("Portal 2", true)]
    [TestCase("Super Meat", false)]
    [TestCase("Doubled", false)]
    [TestCase("Offline", false)]
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
                return said == "Offline"
                    ? throw new HttpRequestException("simulated offline store")
                    : ValueTask.FromResult<IReadOnlyList<SteamStoreTitle>>(
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
}
