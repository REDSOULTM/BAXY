using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using Baxy.Kernel.Operations;
using Microsoft.Win32;

namespace Baxy.Providers.Windows.External;

internal sealed partial class SteamLocalAdapter : IExternalOperationAdapter
{
    // The game catalog this adapter reads (InstalledGameCatalogEntry's provider), and the name its application's acts and
    // title search are declared under in the data (app_places.v1.json «gameCatalog»).
    internal const string GameCatalog = "steam";
    private const int InstallObservationIntervals = 60;
    private const int CancelObservationIntervals = 30;
    private const int LaunchObservationIntervals = 70;
    private const int LaunchDialogObservation = 10;
    private static readonly TimeSpan ObservationInterval = TimeSpan.FromMilliseconds(500);
    private readonly Func<IReadOnlyList<SteamLocalGame>> _snapshot;
    private readonly Func<IReadOnlySet<string>?> _owned;
    private readonly ISteamClientAutomation _automation;
    private readonly Func<TimeSpan, CancellationToken, ValueTask> _delay;
    private readonly Func<IReadOnlyList<SteamProcessObservation>>? _processSnapshot;
    private readonly Func<string, CancellationToken, ValueTask<IReadOnlyList<SteamStoreTitle>>>? _storeTitles;
    // Feria (caso 15): the games this Steam client knows (SteamAppInfo); null when its cache could not be read.
    private readonly Func<IReadOnlyList<SteamStoreTitle>?> _knownGames;
    // Renew al máximo (auditoría de flujos): the processes running now and each one's executable, read with the least
    // access Windows grants (an elevated game, or one its anti-cheat protects, too).
    private readonly Func<IReadOnlyList<int>> _processIds;
    private readonly Func<int, string?> _imagePath;

    // Encargo imp-steam: a title turns into its catalog number by the installed games' manifests and, for one not
    // installed, by the store's public title search the data declare (only the title leaves); 13 titles written here
    // (KnownTitleAppIds, with misheard variants) were retired. The dialog Steam opens for an act's address is confirmed
    // by the mission's own click (input.visible.click on Steam's window, the label from the data), handed in here.
    internal SteamLocalAdapter(IExternalOperationAdapter? clicks = null)
        : this(
            ReadInstalledCatalog,
            ReadOwnedAppIds,
            new WindowsSteamClientAutomation(press: clicks is null ? null : PressBy(clicks)),
            storeTitles: SearchStoreAsync,
            knownGames: ReadKnownGames)
    {
    }

    internal SteamLocalAdapter(Func<IReadOnlyList<SteamLocalGame>> snapshot)
        : this(
            snapshot,
            () => snapshot().Select(game => game.AppId).ToHashSet(StringComparer.Ordinal),
            new WindowsSteamClientAutomation())
    {
    }

    internal SteamLocalAdapter(
        Func<IReadOnlyList<SteamLocalGame>> snapshot,
        Func<IReadOnlySet<string>?> owned,
        ISteamClientAutomation automation,
        Func<TimeSpan, CancellationToken, ValueTask>? delay = null,
        Func<IReadOnlyList<SteamProcessObservation>>? processSnapshot = null,
        Func<string, CancellationToken, ValueTask<IReadOnlyList<SteamStoreTitle>>>? storeTitles = null,
        Func<IReadOnlyList<int>>? processIds = null,
        Func<int, string?>? imagePath = null,
        Func<IReadOnlyList<SteamStoreTitle>?>? knownGames = null)
    {
        _snapshot = snapshot ?? throw new ArgumentNullException(nameof(snapshot));
        _owned = owned ?? throw new ArgumentNullException(nameof(owned));
        _automation = automation ?? throw new ArgumentNullException(nameof(automation));
        _delay = delay ?? DelayAsync;
        _processSnapshot = processSnapshot;
        _storeTitles = storeTitles;
        _processIds = processIds ?? RunningProcessIds;
        _imagePath = imagePath ?? Applications.WindowsInstalledApplicationPlatform.ExecutableImagePath;
        _knownGames = knownGames ?? (static () => null);
    }

    private static IReadOnlyList<int> RunningProcessIds()
    {
        Process[] processes = Process.GetProcesses();
        try
        {
            return [.. processes.Select(static process => process.Id)];
        }
        finally
        {
            foreach (Process process in processes)
                process.Dispose();
        }
    }

    /// <summary>The mission's click on a window by a label (input.visible.click), as the act's confirmation.</summary>
    internal static Func<string, long, CancellationToken, ValueTask<ExternalCapabilityReceipt>> PressBy(
        IExternalOperationAdapter clicks) =>
        (label, window, cancellationToken) => clicks.InvokeAsync(
            "input.visible.click",
            ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteString("label", label);
                writer.WriteNumber("window", window);
                writer.WriteEndObject();
            }),
            cancellationToken);

    public bool CanHandle(string operation) => operation.StartsWith("game.", StringComparison.Ordinal);

    internal InstalledGameCatalogSnapshot GetCatalogSnapshot()
    {
        IReadOnlyList<SteamLocalGame> catalog = _snapshot();
        InstalledGameCatalogEntry[] entries = catalog
            .Where(static game => game.Installed)
            .OrderBy(static game => game.Name, StringComparer.OrdinalIgnoreCase)
            .ThenBy(static game => game.AppId, StringComparer.Ordinal)
            .Select(static game => new InstalledGameCatalogEntry(
                GameCatalog,
                game.AppId,
                game.Name))
            .ToArray();
        // Ronda final 9 (regla 3): a library on a drive not mounted leaves the installed list incomplete.
        return new InstalledGameCatalogSnapshot(
            Verified: true,
            Complete: UnreadLibraries(catalog) == 0,
            entries);
    }

    public async ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        var effectBoundary = new ExternalEffectBoundary();
        try
        {
            return operation switch
            {
                "game.catalog.list" => List(operation, arguments),
                "game.entitlement.named" => EntitlementNamed(operation, arguments),
                "game.install.named" => await InstallNamedAsync(
                    operation, arguments, effectBoundary, cancellationToken)
                    .ConfigureAwait(false),
                "game.uninstall.named" => await UninstallNamedAsync(
                    operation, arguments, effectBoundary, cancellationToken)
                    .ConfigureAwait(false),
                "game.install.status" => Status(operation, arguments),
                "game.install.cancel" => await CancelAsync(
                    operation, arguments, effectBoundary, cancellationToken)
                    .ConfigureAwait(false),
                "game.install.cancel.active" => await CancelActiveAsync(
                    operation, effectBoundary, cancellationToken).ConfigureAwait(false),
                "game.launch" => await LaunchAsync(
                    operation, arguments, effectBoundary, cancellationToken)
                    .ConfigureAwait(false),
                _ => ExternalJson.Failure(operation, "external_operation_not_supported"),
            };
        }
        catch (OperationCanceledException) when (
            cancellationToken.IsCancellationRequested && effectBoundary.WasCrossed)
        {
            return effectBoundary.Failure(operation, "steam_local_adapter_failed");
        }
        catch (InvalidDataException)
        {
            return effectBoundary.Failure(operation, "steam_app_id_invalid");
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException or InvalidOperationException)
        {
            return effectBoundary.Failure(
                operation,
                operation == "game.catalog.list"
                    ? "steam_local_catalog_failed"
                    : "steam_local_adapter_failed");
        }
    }

    private ExternalCapabilityReceipt List(string operation, JsonElement arguments)
    {
        int limit = Math.Clamp(ExternalJson.OptionalInt(arguments, "limit", 50), 1, 100);
        string query = arguments.TryGetProperty("query", out JsonElement queryValue)
            && queryValue.ValueKind == JsonValueKind.String
                ? queryValue.GetString() ?? string.Empty
                : string.Empty;
        IReadOnlyList<SteamLocalGame> catalog = _snapshot();
        int unreadLibraries = UnreadLibraries(catalog);
        SteamLocalGame[] matching = catalog
            .Where(game => query.Length == 0
                || game.AppId.Contains(query, StringComparison.OrdinalIgnoreCase)
                || game.Name.Contains(query, StringComparison.CurrentCultureIgnoreCase))
            .OrderBy(game => game.Name, StringComparer.CurrentCultureIgnoreCase)
            .ToArray();
        SteamLocalGame[] games = matching.Take(limit).ToArray();
        // Uso real 03-11 (G9): a search nothing installed bears was said «not in your library»; what the account's
        // library cache says of that title goes beside it.
        JsonElement? entitlement = matching.Length == 0 && !string.IsNullOrWhiteSpace(query) ? EntitlementOf(query) : null;
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("source", "steam_local_appmanifests");
            writer.WriteString("scope", InstalledScope);
            if (entitlement is { } owned)
            {
                writer.WritePropertyName("entitlement");
                owned.WriteTo(writer);
            }
            writer.WriteNumber("count", games.Length);
            // Ronda final 7 (regla 3): the limit leaves some out: how many there are, and that the list is cut.
            writer.WriteNumber("totalCount", matching.Length);
            if (matching.Length > games.Length) writer.WriteBoolean("truncated", true);
            if (unreadLibraries > 0) writer.WriteNumber("librariesUnread", unreadLibraries);
            // Auditoría de falsedades 2026-11-04 (P2, U34): with a library unread the list is of the libraries read, and
            // «no encontré ningún juego» was told of Steam whole; readInPart is the contract the mind tells a part by.
            if (unreadLibraries > 0) writer.WriteBoolean("readInPart", true);
            // Cosecha 04-11 F34: «¿a qué le di la última vez?» took the first by name (limit 1) and gave up; the
            // manifests say when each was last played (LastPlayed, Unix seconds), whatever the view leaves out.
            if (matching.Where(game => game.LastPlayedUtc is not null).MaxBy(game => game.LastPlayedUtc) is { } latest)
            {
                writer.WriteStartObject("lastPlayed");
                writer.WriteString("appId", latest.AppId);
                writer.WriteString("name", latest.Name);
                writer.WriteString("lastPlayedUtc", latest.LastPlayedUtc!.Value);
                writer.WriteEndObject();
            }
            writer.WriteStartArray("games");
            foreach (SteamLocalGame game in games)
            {
                WriteGame(writer, game);
            }
            writer.WriteEndArray(); writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: false);
    }

    // The manifests are this PC's games, never the account's library (Steam's own GetOwnedGames needs a web key).
    private const string InstalledScope = "games_installed_or_downloading_on_this_pc";

    // What game.entitlement.named says of the title (the account's library cache), or null when it could not be read.
    private JsonElement? EntitlementOf(string title)
    {
        ExternalCapabilityReceipt read = EntitlementNamed("game.entitlement.named", ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteString("title", title); writer.WriteEndObject();
        }));
        return read.Verified ? read.Result : null;
    }

    // INSTALL1617 «Descarga Worms Rumble en Steam»: before any download the
    // turn needs a truthful answer to «is this game mine and is it installed?».
    // Renew al máximo (B-APP-6): the title resolves only on the PC, never by the
    // store's search (nothing of the person's leaves the PC for a local check); an
    // unresolved title is reported as such, never guessed.
    private ExternalCapabilityReceipt EntitlementNamed(string operation, JsonElement arguments)
    {
        string title = ExternalJson.RequiredString(arguments, "title");
        if (string.IsNullOrWhiteSpace(title) || Encoding.UTF8.GetByteCount(title) > 256)
        {
            return ExternalJson.Failure(operation, "steam_title_invalid");
        }
        if (arguments.ValueKind == JsonValueKind.Object
            && arguments.TryGetProperty("store", out JsonElement store)
            && store.ValueKind == JsonValueKind.String
            && string.Equals(store.GetString(), "epic", StringComparison.Ordinal))
        {
            return EpicEntitlementNamed(operation, title, EpicLauncherDataRoot);
        }
        IReadOnlyList<SteamLocalGame> catalog = _snapshot();
        string folded = FoldTitle(title);
        string[] bearing = Bearing(catalog, folded);
        // Feria (caso 15): a game not on this PC answered as a title no game bears. One no manifest bears is looked up
        // among the games this Steam client knows (SteamAppInfo), which are not the whole store.
        IReadOnlyList<SteamStoreTitle>? known = bearing.Length == 0 ? _knownGames() : null;
        SteamStoreTitle[] knownBearing = known is null ? []
            : [.. known.Where(game => FoldTitle(game.Name) == folded).DistinctBy(static game => game.AppId)];
        IReadOnlySet<string>? cache = _owned();
        // Two known games bear the same title (a re-release under the same name): the one in the library cache, when only
        // one of them is.
        SteamStoreTitle[] knownOwned = cache is null ? []
            : [.. knownBearing.Where(candidate => cache.Contains(candidate.AppId))];
        SteamStoreTitle? knownGame = knownBearing.Length == 1 ? knownBearing[0]
            : knownOwned.Length == 1 ? knownOwned[0] : null;
        string? appId = bearing.Length == 1 ? bearing[0] : knownGame?.AppId;
        bool librariesUnread = UnreadLibraries(catalog) > 0;
        SteamLocalGame? game = appId is null
            ? null
            : catalog.SingleOrDefault(candidate => candidate.AppId == appId);
        bool owned = appId is not null && cache is not null && cache.Contains(appId);
        bool installed = game is { Installed: true };
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("query", title);
            writer.WriteBoolean("resolved", appId is not null);
            if (appId is null) writer.WriteNull("appId"); else writer.WriteString("appId", appId);
            writer.WriteString("title", game?.Name ?? knownGame?.Name ?? title);
            // How many manifests bear the title (none, or two that leave it ambiguous); with a library unread, only some.
            if (bearing.Length > 0 || !librariesUnread) writer.WriteNumber("steamManifestsWithThatName", bearing.Length);
            if (known is not null) writer.WriteNumber("steamKnownGamesWithThatName", knownBearing.Length);
            // The games this Steam knows were to be looked up and their cache could not be read: only this PC's were.
            else if (bearing.Length == 0) writer.WriteBoolean("knownGamesUnread", true);
            // Ronda final: the local library cache is incomplete (see InstallNamedAsync), so a game absent from it is
            // absent from the cache, never «not owned».
            // An installed manifest is not the account's ownership (a shared or free game): only the cache says owned.
            if (owned) writer.WriteBoolean("owned", true);
            else if (appId is not null && !installed && cache is not null) writer.WriteBoolean("inLocalLibraryCache", false);
            // Auditoría final (regla 3): installed or not is read by the AppID's manifest; a title not resolved to one says
            // nothing of it.
            // Ronda final 8: with a library unread, a game not found installed may be installed there.
            if (appId is not null && (installed || !librariesUnread)) writer.WriteBoolean("installed", installed);
            if (librariesUnread) writer.WriteBoolean("librariesUnread", true);
            if (librariesUnread) writer.WriteBoolean("readInPart", true);
            // A known game close to the title is offered only when the library cache has it: one merely seen in the store
            // is not the person's.
            if (appId is null)
            {
                IEnumerable<string> knownOwnedNames = known?
                    .Where(candidate => cache?.Contains(candidate.AppId) == true)
                    .Select(static candidate => candidate.Name) ?? [];
                WriteClosest(writer, ClosestTitles(title, catalog.Select(static game => game.Name).Concat(knownOwnedNames)));
            }
            // Feria (caso 15): an unresolved title was read as a game Steam does not have. Where it was looked up is
            // said: an unresolved one says neither that the game does not exist nor that it is not owned.
            writer.WriteString("titleLookedUpAmong", known is null
                ? InstalledScope : "games_on_this_pc_and_games_this_steam_client_knows");
            writer.WriteString("state", appId is null ? "title_not_resolved"
                : installed ? "installed"
                : librariesUnread ? "install_not_read"
                : owned ? "owned_not_installed" : cache is not null ? "not_in_local_library_cache" : "library_cache_unavailable");
            writer.WriteString("authority", installed || appId is null
                ? "steam_local_appmanifest" : "steam_authenticated_library_cache");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: false);
    }

    private async ValueTask<ExternalCapabilityReceipt> InstallNamedAsync(
        string operation,
        JsonElement arguments,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        string title = ExternalJson.RequiredString(arguments, "title");
        // REOPEN1993 grupo S (H0578 «Descarga Fall guys en epic games»): the
        // store named after the title picks the launcher.
        if (arguments.TryGetProperty("store", out JsonElement store)
            && store.ValueKind == JsonValueKind.String && store.GetString() == "epic")
        {
            return await EpicInstallNamedAsync(operation, title, effectBoundary, cancellationToken)
                .ConfigureAwait(false);
        }

        (string? appId, bool searchFailed, string[] closest) =
            await ResolveTitleAsync(title, cancellationToken).ConfigureAwait(false);
        if (searchFailed)
            return NotResolved(operation, "steam_store_search_failed", title, closest);
        if (appId is null)
            return NotResolved(operation, "steam_title_not_resolved", title, closest);
        // Encargo imp-steam: the account's library is not read here as a gate. Its local cache is incomplete (measured
        // 2026-10-11: Super Meat Boy, in the owner's account, is absent from the notebook's userdata librarycache);
        // Steam's own install dialog only installs what the account holds, and the manifest proves it did.
        SteamLocalGame? game = _snapshot().SingleOrDefault(candidate => candidate.AppId == appId);
        if (game is { Installed: true })
        {
            JsonElement installed = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject(); writer.WriteNumber("version", 1);
                writer.WriteString("appId", appId); writer.WriteString("name", game.Name);
                writer.WriteString("state", "already_installed");
                writer.WriteString("authority", "steam_local_appmanifest"); writer.WriteEndObject();
            });
            return ExternalJson.Switched(operation, installed, effectObserved: false);
        }
        return await DispatchInstallAsync(operation, appId, effectBoundary, cancellationToken)
            .ConfigureAwait(false);
    }

    private async ValueTask<ExternalCapabilityReceipt> DispatchInstallAsync(
        string operation,
        string appId,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        SteamLocalGame? before = _snapshot().SingleOrDefault(game => game.AppId == appId);
        // Ronda final: a download already running grows by itself, so it cannot show this request's start. A manifest
        // that reads «downloading» may also be a download cut with Steam closed: only bytes seen growing between two
        // reads, before anything is sent, are the state reached (changed:false); otherwise the second read is the
        // baseline and the request goes on. Renew al máximo (B-APP-4): one that reads «paused» is read twice too: only its
        // growth says whether it runs.
        SteamLocalGame? running = null;
        if (before is { Installed: false } first && InstallState(first) is "downloading" or "paused")
        {
            await _delay(ObservationInterval, cancellationToken).ConfigureAwait(false);
            SteamLocalGame? second = _snapshot().SingleOrDefault(game => game.AppId == appId);
            if (second is { Installed: false } && second.BytesDownloaded > first.BytesDownloaded)
                running = second;
            else
                before = second;
        }

        if (running is not null)
        {
            JsonElement downloading = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject(); writer.WriteNumber("version", 1);
                writer.WriteString("jobId", JobId(appId)); writer.WriteString("appId", appId);
                writer.WriteString("name", running.Name);
                writer.WriteString("state", "downloading");
                writer.WriteNumber("stateFlags", running.StateFlags);
                writer.WriteNumber("bytesDownloaded", running.BytesDownloaded);
                writer.WriteNumber("bytesTotal", running.BytesToDownload);
                writer.WriteString("next", $"{StatusCall(running)} reads its progress later");
                writer.WriteString("authority", "steam_manifest_growth_preread"); writer.WriteEndObject();
            });
            return ExternalJson.Switched(operation, downloading, effectObserved: false);
        }

        if (await ActAsync(operation, "install", appId, effectBoundary, cancellationToken).ConfigureAwait(false)
            is { } failed)
        {
            return failed;
        }

        for (int observation = 0; observation <= InstallObservationIntervals; observation++)
        {
            SteamLocalGame? after = _snapshot().SingleOrDefault(game => game.AppId == appId);
            if (after is not null && (before is null
                || after.BytesDownloaded > before.BytesDownloaded
                || after.StateFlags != before.StateFlags
                || !string.Equals(after.ManifestSha256, before.ManifestSha256, StringComparison.Ordinal)))
            {
                JsonElement result = ExternalJson.Create(writer =>
                {
                    writer.WriteStartObject(); writer.WriteNumber("version", 1);
                    writer.WriteString("jobId", JobId(appId)); writer.WriteString("appId", appId);
                    writer.WriteString("name", after.Name);
                    writer.WriteString("state", InstallState(after));
                    writer.WriteNumber("stateFlags", after.StateFlags);
                    writer.WriteNumber("bytesDownloaded", after.BytesDownloaded);
                    writer.WriteNumber("bytesTotal", after.BytesToDownload);
                    // Encargo 52: the manifest read is the first one Steam wrote for this request; what it brings
                    // later is read by the status call, never assumed (a game was told installed at 18 %).
                    if (!after.Installed) writer.WriteString("next", $"{StatusCall(after)} reads its progress later");
                    writer.WriteString("authority", "steam_manifest_transition"); writer.WriteEndObject();
                });
                return ExternalJson.Success(operation, result, effectObserved: true);
            }

            if (observation < InstallObservationIntervals)
            {
                await _delay(ObservationInterval, cancellationToken).ConfigureAwait(false);
            }
        }
        return ExternalJson.Failure(operation, "steam_install_transition_not_verified", effectObserved: true);
    }

    /// <summary>
    /// Encargo imp-steam: an act of the game (install, uninstall) is its address in the data handed to Steam, and the
    /// dialog Steam opens for it confirmed by the mission's click on its own button (the data's «confirm» names); never a
    /// key or a console command. Null when both happened (or the act has no dialog): the caller proves the effect on the
    /// game's manifest. Otherwise the failure: before any effect when the data declare no such act; the dialog left open
    /// when its button was not pressed.
    /// </summary>
    private async ValueTask<ExternalCapabilityReceipt?> ActAsync(
        string operation,
        string act,
        string appId,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        ApplicationPlaces.GameAct? declared = ApplicationPlaces.GameActOf(GameCatalog, act, appId);
        if (declared is null)
        {
            return ExternalJson.FailureBeforeEffect(operation, "steam_act_not_declared");
        }

        effectBoundary.Cross(cancellationToken);
        SteamDispatchResult dispatch = await _automation.DispatchAsync(declared.Address, cancellationToken)
            .ConfigureAwait(false);
        if (!dispatch.Accepted)
        {
            return effectBoundary.Failure(operation, $"steam_{act}_dispatch_rejected", dispatch.EffectObserved);
        }

        if (declared.Confirm.Count == 0)
        {
            return null;
        }

        SteamDispatchResult confirmed = await _automation.ConfirmAsync(dispatch, declared.Confirm, cancellationToken)
            .ConfigureAwait(false);
        // A press that may have landed is judged by the manifest, never by the press's own post-read.
        return confirmed.Accepted || confirmed.EffectObserved
            ? null
            : effectBoundary.Failure(operation, $"steam_{act}_dialog_not_confirmed", effectObserved: true);
    }

    // H0578 «Descarga Fall guys en epic games»: the Epic Games launcher keeps its
    // installed games as one JSON manifest each (%ProgramData%\Epic\EpicGamesLauncher\
    // Data\Manifests\*.item: DisplayName, AppName, CatalogItemId, InstallLocation) and
    // the authenticated account's catalog as a base64 JSON list (Data\Catalog\
    // catcache.bin: id, title, namespace). Both are read, nothing is written; the
    // first catalog entry with that title (case and accents aside) is taken.
    private static string EpicLauncherDataRoot => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData),
        "Epic", "EpicGamesLauncher", "Data");

    internal static ExternalCapabilityReceipt EpicEntitlementNamed(string operation, string title, string dataRoot)
    {
        string folded = FoldTitle(title);
        string manifests = Path.Combine(dataRoot, "Manifests");
        string catalogCache = Path.Combine(dataRoot, "Catalog", "catcache.bin");
        // Uso real 02-11 («LEGO Batman comprado en Epic»): a title said short of the cache's («LEGO® Batman™ The Videogame»,
        // and two more) was told «not in the cache» twice. As with Steam, a title no entry bears exactly is unresolved, with
        // the closest titles of the cache and the manifests.
        List<string> names = [];
        if (!Directory.Exists(manifests) && !File.Exists(catalogCache))
        {
            return ExternalJson.Failure(operation, "epic_launcher_data_not_found");
        }
        string? installedName = null;
        string? installedCatalogId = null;
        // Auditoría final (regla 3): a manifest that could not be read leaves «not installed» unsaid, and what is read is a
        // manifest with that exact name, said as that.
        bool manifestUnread = false;
        if (Directory.Exists(manifests))
        {
            foreach (string file in Directory.EnumerateFiles(manifests, "*.item"))
            {
                try
                {
                    using JsonDocument document = JsonDocument.Parse(File.ReadAllText(file, Encoding.UTF8));
                    JsonElement root = document.RootElement;
                    if (root.ValueKind != JsonValueKind.Object
                        || !root.TryGetProperty("DisplayName", out JsonElement displayName)
                        || displayName.ValueKind != JsonValueKind.String)
                    {
                        continue;
                    }
                    names.Add(displayName.GetString() ?? string.Empty);
                    if (FoldTitle(displayName.GetString() ?? string.Empty) != folded
                        || (root.TryGetProperty("bIsIncompleteInstall", out JsonElement incomplete)
                            && incomplete.ValueKind == JsonValueKind.True))
                    {
                        continue;
                    }
                    installedName = displayName.GetString();
                    installedCatalogId = root.TryGetProperty("CatalogItemId", out JsonElement catalogId)
                        && catalogId.ValueKind == JsonValueKind.String ? catalogId.GetString() : null;
                    break;
                }
                catch (JsonException)
                {
                    // A manifest the launcher is rewriting is not evidence either way.
                    manifestUnread = true;
                }
                catch (IOException)
                {
                    manifestUnread = true;
                }
            }
        }
        string? ownedName = null;
        string? ownedCatalogId = null;
        int ownedMatches = 0;
        bool cacheRead = false;
        if (File.Exists(catalogCache))
        {
            try
            {
                byte[] decoded = Convert.FromBase64String(File.ReadAllText(catalogCache, Encoding.ASCII).Trim());
                using JsonDocument document = JsonDocument.Parse(decoded);
                if (document.RootElement.ValueKind == JsonValueKind.Array)
                {
                    foreach (JsonElement item in document.RootElement.EnumerateArray())
                    {
                        if (item.ValueKind != JsonValueKind.Object
                            || !item.TryGetProperty("title", out JsonElement itemTitle)
                            || itemTitle.ValueKind != JsonValueKind.String)
                        {
                            continue;
                        }
                        names.Add(itemTitle.GetString() ?? string.Empty);
                        if (FoldTitle(itemTitle.GetString() ?? string.Empty) != folded)
                        {
                            continue;
                        }
                        ownedMatches++;
                        ownedName ??= itemTitle.GetString();
                        ownedCatalogId ??= item.TryGetProperty("id", out JsonElement itemId)
                            && itemId.ValueKind == JsonValueKind.String ? itemId.GetString() : null;
                    }
                    cacheRead = true;
                }
            }
            catch (FormatException)
            {
            }
            catch (JsonException)
            {
            }
            catch (IOException)
            {
            }
        }
        bool installed = installedName is not null;
        // Ronda final: as with Steam, an installed manifest is not the account's ownership: only the catalog cache says owned.
        bool owned = ownedMatches >= 1;
        string? catalogItemId = installedCatalogId ?? ownedCatalogId;
        string[] closest = owned || installed ? [] : ClosestTitles(title, names);
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("query", title);
            writer.WriteString("store", "epic");
            writer.WriteBoolean("resolved", owned || installed);
            if (catalogItemId is null) writer.WriteNull("appId"); else writer.WriteString("appId", catalogItemId);
            writer.WriteString("title", installedName ?? ownedName ?? title);
            // Ronda final: without the catalog cache read, the library was not looked at.
            if (owned) writer.WriteBoolean("owned", true);
            else if (cacheRead && closest.Length == 0) writer.WriteBoolean("inLocalLibraryCache", false);
            if (installed) writer.WriteBoolean("installed", true);
            else if (!manifestUnread) writer.WriteBoolean("epicManifestWithThatName", false);
            WriteClosest(writer, closest);
            writer.WriteString("state", installed ? "installed"
                : owned ? (manifestUnread ? "owned_install_not_read" : "owned_no_epic_manifest_with_that_name")
                : closest.Length > 0 ? "title_not_resolved"
                : cacheRead ? "not_in_local_library_cache" : "library_cache_unavailable");
            writer.WriteString("authority", installed
                ? "epic_launcher_local_manifest" : "epic_launcher_catalog_cache");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: false);
    }

    // Renew al máximo (B-APP-5): a store search that got no answer is SearchFailed, never a title no game bears.
    // Renew al máximo (auditoría de flujos): unresolved, with the closest titles of the store's answer and the manifests
    // (only the manifests when the store did not answer).
    private async ValueTask<(string? AppId, bool SearchFailed, string[] Closest)> ResolveTitleAsync(
        string title, CancellationToken cancellationToken)
    {
        string folded = FoldTitle(title);
        IReadOnlyList<SteamLocalGame> catalog = _snapshot();
        string? installed = Bearing(catalog, folded) is [string one] ? one : null;
        string[] Local() => ClosestTitles(title, catalog.Select(static game => game.Name));
        if (installed is not null || _storeTitles is null)
        {
            return (installed, false, installed is null ? Local() : []);
        }

        IReadOnlyList<SteamStoreTitle> found;
        try
        {
            found = await _storeTitles(title, cancellationToken).ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is HttpRequestException or JsonException or IOException
            || (exception is TaskCanceledException && !cancellationToken.IsCancellationRequested))
        {
            return (null, true, Local());
        }

        // Exactly one game of the store answer bears the title (folded): «Super Meat Boy» is not «Super Meat Boy Forever».
        string[] matches = found
            .Where(item => FoldTitle(item.Name) == folded)
            .Select(item => item.AppId)
            .Distinct(StringComparer.Ordinal)
            .ToArray();
        if (matches.Length == 1)
        {
            return (matches[0], false, []);
        }

        IEnumerable<string> names = found.Select(static item => item.Name).Concat(catalog.Select(static game => game.Name));
        string[] near = TitlesItSoundsLike(title, names);
        return near.Length > 0 && SoundsAlike(folded, FoldTitle(near[0]))
            ? (null, false, near)
            : (null, false, await NearestWithPiecesAsync(title, names, cancellationToken).ConfigureAwait(false));
    }

    // F39: what is said wrong is BAXY's to fix (the owner's rule of 2026-09-19), most often its own ear's mistake: it wrote
    // a game's name as words it knows. The store's title search corrects nothing (0 answers for a word off), but it answers
    // for the title without one of its words, or for one word alone, and those answers hold the game: its closest titles
    // are read there, in parallel, and among the games this Steam client knows; only the title's words leave, as in the
    // search itself. A held-out set of 14 misheard titles: the game offered 1 → 5 of 14, invented names nothing close.
    private async ValueTask<string[]> NearestWithPiecesAsync(
        string title, IEnumerable<string> names, CancellationToken cancellationToken)
    {
        string[] words = title.Split(' ', StringSplitOptions.RemoveEmptyEntries);
        string[] pieces = [.. Enumerable.Range(0, words.Length > 1 ? words.Length : 0)
                .Select(index => string.Join(' ', words.Where((_, at) => at != index)))
            .Concat(words.Where(static word => word.Length >= PieceMinimumLength))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .Take(PiecesAsked)];
        IReadOnlyList<SteamStoreTitle>[] answers = await Task.WhenAll(pieces.Select(async piece =>
        {
            try
            {
                return await _storeTitles!(piece, cancellationToken).ConfigureAwait(false);
            }
            catch (Exception exception) when (exception is HttpRequestException or JsonException or IOException
                || (exception is TaskCanceledException && !cancellationToken.IsCancellationRequested))
            {
                return (IReadOnlyList<SteamStoreTitle>)[];
            }
        })).ConfigureAwait(false);
        IReadOnlyList<SteamStoreTitle> known = _knownGames() ?? [];
        return TitlesItSoundsLike(title, names
            .Concat(answers.SelectMany(static answer => answer.Select(static item => item.Name)))
            .Concat(known.Select(static game => game.Name)));
    }

    private const int PiecesAsked = 6;
    private const int PieceMinimumLength = 4;
    // How alike two titles are written (1 - edit distance / longer, without spaces) to be said as the same one misheard:
    // of 14 misheard titles the five retrieved scored 0.60-1, invented names against what the store answers 0.40 at most.
    private const double SoundsAlikeSimilarity = 0.55;

    private static bool SoundsAlike(string folded, string name) => Similarity(folded, name) >= SoundsAlikeSimilarity;

    private static double Similarity(string folded, string name)
    {
        string ours = folded.Replace(" ", string.Empty, StringComparison.Ordinal);
        string theirs = name.Replace(" ", string.Empty, StringComparison.Ordinal);
        if (ours.Length == 0 || theirs.Length == 0)
            return 0;
        int[] above = [.. Enumerable.Range(0, theirs.Length + 1)];
        for (int i = 1; i <= ours.Length; i++)
        {
            int[] row = new int[theirs.Length + 1];
            row[0] = i;
            for (int j = 1; j <= theirs.Length; j++)
                row[j] = Math.Min(Math.Min(above[j] + 1, row[j - 1] + 1), above[j - 1] + (ours[i - 1] == theirs[j - 1] ? 0 : 1));
            above = row;
        }

        return 1 - (double)above[theirs.Length] / Math.Max(ours.Length, theirs.Length);
    }

    /// <summary>
    /// F39: the titles a heard one may be: those written alike (<see cref="SoundsAlikeSimilarity"/>) or sharing a word with
    /// it (<see cref="ClosestTitles"/>), most alike first. Only said, never resolved.
    /// </summary>
    internal static string[] TitlesItSoundsLike(string title, IEnumerable<string> names)
    {
        string folded = FoldTitle(title);
        string[] asked = [.. folded.Split(' ', StringSplitOptions.RemoveEmptyEntries).Where(static word => word.Length >= 3)];
        return [.. names
            .Where(static name => !string.IsNullOrWhiteSpace(name))
            .DistinctBy(FoldTitle, StringComparer.Ordinal)
            .Select(name => (Name: name, Fold: FoldTitle(name)))
            .Select(item => (item.Name, Alike: Similarity(folded, item.Fold), Shared: Nearness(folded, asked, item.Fold)))
            .Where(static scored => scored.Alike >= SoundsAlikeSimilarity || scored.Shared > 0)
            .OrderByDescending(static scored => scored.Alike)
            .ThenBy(static scored => scored.Name, StringComparer.OrdinalIgnoreCase)
            .Take(ClosestTitleCount)
            .Select(static scored => scored.Name)];
    }

    // Renew al máximo (auditoría de flujos, decision2): how many of the closest titles an unresolved one names.
    private const int ClosestTitleCount = 5;

    /// <summary>
    /// Renew al máximo (auditoría de flujos, decision2: «desinstala el worms» failed with nothing to name): the titles of
    /// <paramref name="names"/> closest to <paramref name="title"/>, folded as titles are: by the words of three letters or
    /// more they share (one said as the start of the other's counts), then by one title starting the other; at most five,
    /// none sharing nothing. Only said, never resolved.
    /// </summary>
    internal static string[] ClosestTitles(string title, IEnumerable<string> names)
    {
        string folded = FoldTitle(title);
        string[] asked = [.. folded.Split(' ', StringSplitOptions.RemoveEmptyEntries).Where(static word => word.Length >= 3)];
        return [.. names
            .Where(static name => !string.IsNullOrWhiteSpace(name))
            .DistinctBy(FoldTitle, StringComparer.Ordinal)
            .Select(name => (Name: name, Score: Nearness(folded, asked, FoldTitle(name))))
            .Where(static scored => scored.Score > 0)
            .OrderByDescending(static scored => scored.Score)
            .ThenBy(static scored => scored.Name, StringComparer.OrdinalIgnoreCase)
            .Take(ClosestTitleCount)
            .Select(static scored => scored.Name)];
    }

    private static int Nearness(string folded, string[] asked, string name)
    {
        string[] words = name.Split(' ', StringSplitOptions.RemoveEmptyEntries);
        int shared = asked.Count(word => words.Any(other => other.StartsWith(word, StringComparison.Ordinal)
            || (other.Length >= 3 && word.StartsWith(other, StringComparison.Ordinal))));
        bool starts = folded.Length >= 3 && name.Length >= 3
            && (name.StartsWith(folded, StringComparison.Ordinal) || folded.StartsWith(name, StringComparison.Ordinal));
        return shared * 2 + (starts ? 1 : 0);
    }

    internal static void WriteClosest(Utf8JsonWriter writer, string[] closest)
    {
        if (closest.Length == 0)
            return;
        writer.WriteStartArray("closestTitles");
        foreach (string name in closest)
            writer.WriteStringValue(name);
        writer.WriteEndArray();
    }

    // A title that resolved to no game, failed before anything is sent, with what was asked and the closest titles.
    private static ExternalCapabilityReceipt NotResolved(string operation, string code, string title, string[] closest) =>
        new(operation, false, false, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("query", title);
            WriteClosest(writer, closest);
            // F39: the title may be how the ear wrote it, so the person is not asked for what they already said. A store
            // that did not answer says nothing of the title.
            if (code != "steam_store_search_failed" && closest.Length > 0)
                writer.WriteString("next", $"no game is called \"{title}\" and it may have been misheard: this call changed nothing. Ask the person whether they meant one of closestTitles, naming it.");
            else if (code == "steam_title_not_resolved")
                writer.WriteString("next", $"no game is called \"{title}\" and it may have been misheard: this call changed nothing. If it sounds like a game you know, call game_install_named with that game's real title; if not, ask the person to say it again.");
            writer.WriteEndObject();
        }), code);

    /// <summary>
    /// BAXY Renew cu (C04): the game whose store page is asked for by its title (app.open, place game). The installed
    /// game bearing the title, else the store's answer: the one game bearing it, else the first, in the store's own
    /// order, whose name holds every word of it («Sid Meier Civilization VI» is «Sid Meier's Civilization VI»). Only a page is
    /// opened with it, and its name goes back with the opening; null when nothing bears the title, and
    /// <see cref="Applications.GameTitleSearchFailedException"/> when the store's search got no answer.
    /// </summary>
    internal static async ValueTask<SteamStoreTitle?> PageTitleAsync(
        string title,
        CancellationToken cancellationToken,
        Func<IReadOnlyList<SteamLocalGame>>? installed = null,
        Func<string, CancellationToken, ValueTask<IReadOnlyList<SteamStoreTitle>>>? storeTitles = null)
    {
        string folded = FoldTitle(title);
        SteamLocalGame[] local = [.. (installed ?? ReadInstalledCatalog)().Where(game => FoldTitle(game.Name) == folded)];
        if (local.Select(game => game.AppId).Distinct(StringComparer.Ordinal).Count() == 1)
        {
            return new SteamStoreTitle(local[0].AppId, local[0].Name);
        }

        IReadOnlyList<SteamStoreTitle> found;
        try
        {
            found = await (storeTitles ?? SearchStoreAsync)(title, cancellationToken).ConfigureAwait(false);
        }
        // Renew al máximo (auditoría de flujos): a search with no answer is not a title nothing bears.
        catch (Exception exception) when (exception is HttpRequestException or JsonException or IOException
            || (exception is TaskCanceledException && !cancellationToken.IsCancellationRequested))
        {
            throw new Applications.GameTitleSearchFailedException(exception);
        }

        SteamStoreTitle[] bearing = [.. found.Where(item => FoldTitle(item.Name) == folded)
            .DistinctBy(item => item.AppId, StringComparer.Ordinal)];
        if (bearing.Length == 1)
        {
            return bearing[0];
        }

        string[] words = folded.Split(' ', StringSplitOptions.RemoveEmptyEntries);
        return words.Length == 0 ? null : found.FirstOrDefault(
            item => FoldTitle(item.Name).Split(' ', StringSplitOptions.RemoveEmptyEntries) is string[] name
                && words.All(word => name.Contains(word, StringComparer.Ordinal)));
    }

    private static readonly HttpClient StoreHttp = new() { Timeout = TimeSpan.FromSeconds(8) };

    /// <summary>The store's public title search the data declare (app_places.v1.json «titles»); only the title leaves.</summary>
    private static async ValueTask<IReadOnlyList<SteamStoreTitle>> SearchStoreAsync(
        string title,
        CancellationToken cancellationToken)
    {
        ApplicationPlaces.TitleSearch? search = ApplicationPlaces.TitleSearchOf(GameCatalog, title);
        if (search is null)
        {
            return [];
        }

        using HttpResponseMessage response = await StoreHttp.GetAsync(search.Address, cancellationToken)
            .ConfigureAwait(false);
        // Renew al máximo (B-APP-5): an error status is a search that failed (HttpRequestException), not an empty answer.
        response.EnsureSuccessStatusCode();

        await using Stream body = await response.Content.ReadAsStreamAsync(cancellationToken).ConfigureAwait(false);
        using JsonDocument document = await JsonDocument.ParseAsync(body, cancellationToken: cancellationToken)
            .ConfigureAwait(false);
        return StoreTitles(document.RootElement, search);
    }

    /// <summary>Each game of a title search's answer, by the fields the data name: its number and its name.</summary>
    internal static IReadOnlyList<SteamStoreTitle> StoreTitles(JsonElement answer, ApplicationPlaces.TitleSearch search)
    {
        if (answer.ValueKind != JsonValueKind.Object
            || !answer.TryGetProperty(search.List, out JsonElement items)
            || items.ValueKind != JsonValueKind.Array)
        {
            return [];
        }

        var titles = new List<SteamStoreTitle>();
        foreach (JsonElement item in items.EnumerateArray())
        {
            if (item.ValueKind != JsonValueKind.Object
                || !item.TryGetProperty(search.Id, out JsonElement id)
                || !item.TryGetProperty(search.Name, out JsonElement name)
                || name.ValueKind != JsonValueKind.String)
            {
                continue;
            }

            string? number = id.ValueKind switch
            {
                JsonValueKind.Number when id.TryGetUInt64(out ulong value) => value.ToString(System.Globalization.CultureInfo.InvariantCulture),
                JsonValueKind.String => id.GetString(),
                _ => null,
            };
            if (number is { Length: > 0 and <= 10 } && number[0] != '0' && number.All(char.IsAsciiDigit))
            {
                titles.Add(new SteamStoreTitle(number, name.GetString()!));
            }
        }

        return titles;
    }

    // The AppIDs of the manifests bearing the title (folded): the title resolves when exactly one does.
    private static string[] Bearing(IReadOnlyList<SteamLocalGame> catalog, string folded) => catalog
        .Where(game => FoldTitle(game.Name) == folded)
        .Select(game => game.AppId)
        .Distinct(StringComparer.Ordinal)
        .ToArray();

    // Renew al máximo (w8): an apostrophe joins its word; as a space it made «assassin s creed», which no spoken title
    // ever matched (launch, entitlement, install and uninstall). And a word's final «s» is left aside on both sides, so
    // the possessive is matched said with it or without it («assassins creed», «Sid Meier Civilization»).
    internal static bool IsApostrophe(char character) => character is '\'' or '’' or '‘' or 'ʼ' or '`' or '´';

    internal static string FoldTitle(string value)
    {
        string decomposed = value.Normalize(NormalizationForm.FormD);
        return string.Join(' ', new string(decomposed
            .Where(character => System.Globalization.CharUnicodeInfo.GetUnicodeCategory(character)
                != System.Globalization.UnicodeCategory.NonSpacingMark && !IsApostrophe(character))
            .Select(char.ToLowerInvariant)
            .Select(character => char.IsLetterOrDigit(character) ? character : ' ')
            .ToArray()).Split(' ', StringSplitOptions.RemoveEmptyEntries)
            .Select(static word => word.Length > 3 && word[^1] == 's' ? word[..^1] : word));
    }

    private ExternalCapabilityReceipt Status(string operation, JsonElement arguments)
    {
        string given = RequireAppId(arguments);
        string? title = arguments.TryGetProperty("title", out JsonElement titleElement)
            && titleElement.ValueKind == JsonValueKind.String
            && !string.IsNullOrWhiteSpace(titleElement.GetString()) ? titleElement.GetString()!.Trim() : null;
        IReadOnlyList<SteamLocalGame> catalog = _snapshot();
        SteamLocalGame? named = catalog.SingleOrDefault(candidate => candidate.AppId == given);
        // Encargo 52 (sesión real 03-11): asked about Crysis Remastered, the model read R.E.P.O.'s appId and its 0 % was
        // told as Crysis's; replayed with the real model, its status calls carried appIds no receipt gave (6 of 6, with
        // the install's appId in the conversation). The title the person asked about goes in the call, as with
        // game.launch, and governs: the one manifest bearing it is the game read, and the receipt says the appId given
        // was another's (appIdGiven), as game.launch drops an appId no game bears (Encargo 10, punto 2). With no manifest
        // bearing the title, an appId of another game reads nothing of it: which game that is and the games in progress.
        SteamLocalGame[] titled = title is null
            ? []
            : [.. catalog.Where(candidate => FoldTitle(candidate.Name) == FoldTitle(title))];
        SteamLocalGame? game = titled is [{ } own] ? own : named;
        if (title is null || (game is not null && FoldTitle(game.Name) != FoldTitle(title)))
        {
            return new ExternalCapabilityReceipt(operation, false, false, ExternalJson.Create(writer =>
            {
                writer.WriteStartObject(); writer.WriteNumber("version", 1);
                writer.WriteString("appId", given);
                if (named is not null) writer.WriteString("name", named.Name);
                if (title is not null) writer.WriteString("title", title);
                writer.WriteStartArray("gamesInProgress");
                foreach (SteamLocalGame pending in catalog
                    .Where(candidate => !candidate.Installed || candidate.BytesToDownload > 0).Take(20))
                {
                    writer.WriteStartObject();
                    writer.WriteString("appId", pending.AppId); writer.WriteString("name", pending.Name);
                    writer.WriteEndObject();
                }
                writer.WriteEndArray();
                writer.WriteString("authority", "steam_local_appmanifest"); writer.WriteEndObject();
            }), title is null ? "game_title_required" : "game_title_mismatch");
        }
        string appId = game?.AppId ?? given;
        // Ronda final 9 (regla 3): with a library unread, a game not found may be installed there.
        bool librariesUnread = UnreadLibraries(catalog) > 0;
        IReadOnlySet<string>? cache = _owned();
        if (game is null && cache is null)
        {
            return ExternalJson.Failure(operation, "steam_library_cache_unavailable");
        }
        if (game is null && !cache!.Contains(appId))
        {
            return ExternalJson.Failure(operation, "steam_app_not_in_local_library_cache");
        }
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("jobId", JobId(appId)); writer.WriteString("appId", appId);
            writer.WriteString("title", title);
            if (game is not null) writer.WriteString("name", game.Name);
            if (appId != given)
            {
                writer.WriteStartObject("appIdGiven");
                writer.WriteString("appId", given);
                if (named is not null) writer.WriteString("name", named.Name);
                writer.WriteEndObject();
            }
            writer.WriteString("state", game is not null ? InstallState(game)
                : librariesUnread ? "install_not_read" : "not_installed");
            if (game is null && librariesUnread) writer.WriteBoolean("librariesUnread", true);
            if (game is not null) writer.WriteNumber("stateFlags", game.StateFlags);
            if (game is { Installed: true })
            {
                // Encargo 52: R.E.P.O. (StateFlags 6, 0 of 619 374 528 bytes) was told «0 % de 590 MB» as an install not
                // done. The bytes of an installed game are its update's, said apart with the update's own state.
                if (game.BytesToDownload > 0)
                {
                    writer.WriteStartObject("update");
                    writer.WriteString("state", DownloadState(game));
                    WriteBytes(writer, game);
                    writer.WriteEndObject();
                }
            }
            else if (game is not null) WriteBytes(writer, game);
            else
            {
                writer.WriteNumber("bytesDownloaded", 0); writer.WriteNumber("bytesTotal", 0);
                writer.WriteNull("progressPercent");
            }
            writer.WriteString("authority", game is null
                ? "steam_authenticated_library_cache" : "steam_local_appmanifest");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: false);
    }

    private async ValueTask<ExternalCapabilityReceipt> CancelAsync(
        string operation,
        JsonElement arguments,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        string appId = RequireAppId(arguments);
        SteamLocalGame? before = _snapshot().SingleOrDefault(candidate => candidate.AppId == appId);
        if (before is null || before.Installed || before.BytesDownloaded <= 0)
        {
            return ExternalJson.Failure(operation, "steam_partial_download_not_active");
        }
        // Encargo imp-steam: Steam's own uninstall dialog removes a partial download too (it replaces the console's
        // typed app_uninstall); its manifest says when it stopped.
        if (await ActAsync(operation, "uninstall", appId, effectBoundary, cancellationToken).ConfigureAwait(false)
            is { } failed)
        {
            return failed;
        }

        long lastBytes = before.BytesDownloaded;
        for (int observation = 0; observation <= CancelObservationIntervals; observation++)
        {
            SteamLocalGame? after = _snapshot().SingleOrDefault(candidate => candidate.AppId == appId);
            bool terminal = after is null
                || (after.BytesDownloaded == lastBytes
                    && InstallState(after) == "paused");
            bool changedFromPreDispatch = after is null
                || after.BytesDownloaded != before.BytesDownloaded
                || !string.Equals(
                    InstallState(after),
                    InstallState(before),
                    StringComparison.Ordinal);
            // Ronda final: a download that was already paused shows nothing by staying paused; only a change is the
            // cancel's.
            if (terminal && (changedFromPreDispatch || (observation > 0 && InstallState(before) != "paused")))
            {
                JsonElement result = ExternalJson.Create(writer =>
                {
                    writer.WriteStartObject(); writer.WriteNumber("version", 1);
                    writer.WriteString("jobId", JobId(appId)); writer.WriteString("appId", appId);
                    writer.WriteString("state", after is null ? "cancelled" : InstallState(after));
                    writer.WriteString("authority", "steam_manifest_postread"); writer.WriteEndObject();
                });
                return ExternalJson.Success(operation, result, effectObserved: true);
            }
            lastBytes = after?.BytesDownloaded ?? lastBytes;

            if (observation < CancelObservationIntervals)
            {
                await _delay(ObservationInterval, cancellationToken).ConfigureAwait(false);
            }
        }
        return ExternalJson.Failure(operation, "steam_cancel_not_verified", effectObserved: true);
    }

    private async ValueTask<ExternalCapabilityReceipt> CancelActiveAsync(
        string operation,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        // Renew al máximo (B-APP-4): every download already started of a game not installed is cancelled, one in pause
        // too; the post-read below says none still runs.
        string[] active = _snapshot()
            .Where(game => !game.Installed && game.BytesDownloaded > 0)
            .Select(game => game.AppId)
            .Distinct(StringComparer.Ordinal)
            .ToArray();
        foreach (string appId in active)
        {
            using JsonDocument arguments = JsonDocument.Parse("{\"appId\":\"" + appId + "\"}");
            ExternalCapabilityReceipt canceled = await CancelAsync(
                operation, arguments.RootElement, effectBoundary, cancellationToken).ConfigureAwait(false);
            if (!canceled.Verified)
                return effectBoundary.Failure(
                    operation,
                    canceled.ErrorCode ?? "steam_cancel_active_failed",
                    canceled.EffectObserved);
        }
        IReadOnlyList<SteamLocalGame> after = _snapshot();
        string[] remaining = after
            .Where(game => !game.Installed && game.BytesDownloaded > 0
                && InstallState(game) is "downloading" or "installing")
            .Select(game => game.AppId).Distinct(StringComparer.Ordinal).ToArray();
        if (remaining.Length != 0)
            return ExternalJson.Failure(operation, "steam_active_downloads_remain", active.Length > 0);
        // Ronda final 32 (regla 3): a download that wrote no bytes yet (a new install queued: UpdateRequired with
        // UpdateStarted, 1026) or an update of an installed game (UpdateStarted 1024, UpdateRunning 256, Downloading
        // 1048576) is not cancelled here: while one is in the manifests, «no active download left» is not said.
        // Renew al máximo (w8): one in pause (UpdatePaused 512) is no active download: Steam keeps UpdateStarted on a
        // paused update of an installed game, and «cancela las descargas» failed steam_downloads_not_covered forever.
        const ulong DownloadFlags = 1024UL | 256UL | 1048576UL;
        if (after.Any(game => (game.StateFlags & DownloadFlags) != 0 && (game.StateFlags & PausedFlag) == 0))
            return ExternalJson.Failure(operation, "steam_downloads_not_covered", active.Length > 0);
        return ExternalJson.Switched(operation, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteNumber("canceledCount", active.Length);
            writer.WriteNumber("remainingActiveCount", 0);
            writer.WriteString("authority", "steam_manifest_all_active_postread");
            writer.WriteEndObject();
        }), active.Length > 0);
    }

    // Banco ciego c3 C3-049 (also C3-142): «abre Luanti», installed outside Steam, went as game.launch with an invented
    // appId, and the reply denied it was installed from the Steam games listed. A title no installed game of the library
    // holds is said as outside that library, not as absent from the PC; null when the library holds it, or with no title.
    private string? OutsideLibrary(string? title) =>
        !IsOutsideLibrary(title) || !Infrastructure.ModelAids.On(Infrastructure.ModelAids.GameLibraryOnly)
            ? null
            // Encargo 34: not with the call first. Measured with the real model, when the person said not to open it
            // outside Steam, the call first opened it there anyway 7 times of 14 (2 of 14 with this text), and where
            // the person did want it opened both texts led to app_open (2 of 2).
            : $"installedGames is only the Steam games installed on this PC and «{title}» is not among them, which does "
                + $"not say it is not installed: app_open with appId «{title}» can open a game installed outside Steam";

    // Uso real 03-11 (G9): a title no installed game bears, with what the account's library cache says of it.
    private void WriteEntitlement(Utf8JsonWriter writer, string? title)
    {
        if (title is null || EntitlementOf(title) is not { } entitlement)
            return;
        writer.WritePropertyName("entitlement");
        entitlement.WriteTo(writer);
    }

    // Ajuste c5: the fact the handler acts on (GameLaunchHandler), aid or not.
    private bool IsOutsideLibrary(string? title) =>
        title is not null
        && !_snapshot().Any(candidate => candidate.Installed && FoldTitle(candidate.Name) == FoldTitle(title));

    private async ValueTask<ExternalCapabilityReceipt> LaunchAsync(
        string operation,
        JsonElement arguments,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        string? title = arguments.TryGetProperty("title", out JsonElement titleElement)
            && titleElement.ValueKind == JsonValueKind.String
            && !string.IsNullOrWhiteSpace(titleElement.GetString()) ? titleElement.GetString()!.Trim() : null;
        // Ajuste c5: a game outside the library has no appId for the model to copy; what it writes there, a name or a
        // number no game has, is no reason to stop looking for the title. A title of the library is that game's, by Steam.
        // Encargo 10 (punto 2): a well-formed appId no game in the library bears is such a number; it is dropped so the
        // title still resolves it, as an ill-formed one already did (ValidAppId only checks shape, never that it exists).
        string? given = ValidAppId(arguments);
        if (given is not null && !_snapshot().Any(candidate => candidate.AppId == given))
        {
            given = null;
        }
        string? appId = given ?? _snapshot().FirstOrDefault(
            candidate => candidate.Installed && title is not null && FoldTitle(candidate.Name) == FoldTitle(title))?.AppId;
        if (appId is null && !IsOutsideLibrary(title))
        {
            throw new InvalidDataException("Steam AppID is invalid.");
        }

        SteamLocalGame? game = appId is null ? null : _snapshot().SingleOrDefault(candidate => candidate.AppId == appId);
        if (game is null || !game.Installed || string.IsNullOrWhiteSpace(game.InstallDirectory))
        {
            // Encargo 10 (punto 1): a title the library holds but has not finished installing (downloading, paused,
            // queued or installing) is not outside the library: its real state is said and game.install.status reads its
            // progress. IsOutsideLibrary only looks at Installed, so without this it would be sent to the Start menu.
            SteamLocalGame? pending = game ?? (title is null
                ? null
                : _snapshot().FirstOrDefault(candidate => FoldTitle(candidate.Name) == FoldTitle(title)));
            if (pending is { Installed: false })
            {
                return new ExternalCapabilityReceipt(operation, false, false, ExternalJson.Create(writer =>
                {
                    writer.WriteStartObject(); writer.WriteNumber("version", 1);
                    writer.WriteString("appId", pending.AppId);
                    writer.WriteString("title", title ?? pending.Name);
                    writer.WriteString("name", pending.Name);
                    writer.WriteString("state", InstallState(pending));
                    if (pending.BytesToDownload > 0)
                    {
                        writer.WriteString("progress", Infrastructure.ReadingUnits.Percent(
                            Math.Clamp(pending.BytesDownloaded * 100d / pending.BytesToDownload, 0d, 100d)));
                    }
                    // Encargo 34: the read of its progress comes first, as the call with its argument written.
                    writer.WriteString("next", $"{StatusCall(pending)} reads its progress; a game is not launched until "
                        + "it finishes installing");
                    writer.WriteString("authority", "steam_manifest_preread"); writer.WriteEndObject();
                }), "steam_game_not_installed");
            }
            return IsOutsideLibrary(title)
                ? new ExternalCapabilityReceipt(operation, false, false, ExternalJson.Create(writer =>
                {
                    writer.WriteStartObject(); writer.WriteNumber("version", 1);
                    if (appId is not null) writer.WriteString("appId", appId);
                    writer.WriteString("title", title);
                    writer.WriteBoolean("outsideLibrary", true);
                    WriteEntitlement(writer, title);
                    if (OutsideLibrary(title) is { } next) writer.WriteString("next", next);
                    writer.WriteString("authority", "steam_manifest_preread"); writer.WriteEndObject();
                }), "steam_installed_game_not_verified")
                : ExternalJson.Failure(operation, "steam_installed_game_not_verified");
        }

        appId = game.AppId;
        // Renew al máximo (falsedades F001/F016): the model launched the one installed game's appId (Rocket League) for
        // «Doom Eternal» and «Fortnite», twice in front of the owner, and said it had launched what was asked. The title
        // asked for goes in the call and must be this manifest's own (folded as an entitlement's title is); another,
        // or none, fails before anything is sent, with the games installed.
        if (title is null || FoldTitle(title) != FoldTitle(game.Name))
        {
            SteamLocalGame[] installedGames = [.. _snapshot().Where(candidate => candidate.Installed).Take(20)];
            return new ExternalCapabilityReceipt(operation, false, false, ExternalJson.Create(writer =>
            {
                writer.WriteStartObject(); writer.WriteNumber("version", 1);
                writer.WriteString("appId", appId); writer.WriteString("name", game.Name);
                if (title is not null) writer.WriteString("title", title);
                writer.WriteStartArray("installedGames");
                foreach (SteamLocalGame candidate in installedGames)
                {
                    writer.WriteStartObject();
                    writer.WriteString("appId", candidate.AppId); writer.WriteString("name", candidate.Name);
                    writer.WriteEndObject();
                }
                writer.WriteEndArray();
                if (IsOutsideLibrary(title))
                {
                    writer.WriteBoolean("outsideLibrary", true);
                    WriteEntitlement(writer, title);
                }
                if (OutsideLibrary(title) is { } next) writer.WriteString("next", next);
                writer.WriteString("authority", "steam_manifest_preread"); writer.WriteEndObject();
            }), title is null ? "game_title_required" : "game_title_mismatch");
        }
        ApplicationPlaces.GameAct? launch = ApplicationPlaces.GameActOf(GameCatalog, "launch", appId);
        if (launch is null)
        {
            return ExternalJson.FailureBeforeEffect(operation, "steam_act_not_declared");
        }

        string installRoot = Path.GetFullPath(game.InstallDirectory);
        (HashSet<int> before, int? running) = ReadProcesses(installRoot);
        // Renew al máximo (B-APP-8): a game already running is the state reached, said before anything is sent: its
        // address would minimize Steam's windows, maybe press «Jugar» and wait 35 s for no new process.
        if (running is not null)
        {
            JsonElement reached = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject(); writer.WriteNumber("version", 1);
                writer.WriteString("appId", appId); writer.WriteString("name", game.Name);
                writer.WriteNumber("processId", running.Value);
                writer.WriteBoolean("alreadyRunning", true);
                writer.WriteString("authority", "steam_manifest_process_preread"); writer.WriteEndObject();
            });
            return ExternalJson.Switched(operation, reached, effectObserved: false);
        }

        effectBoundary.Cross(cancellationToken);
        SteamDispatchResult dispatch = await _automation.DispatchAsync(launch.Address, cancellationToken)
            .ConfigureAwait(false);
        if (!dispatch.Accepted)
        {
            return effectBoundary.Failure(
                operation, "steam_launch_dispatch_rejected", dispatch.EffectObserved);
        }
        // Ronda final 21 (regla 3): the Steam windows the launch minimized (so its dialog opens apart from the library)
        // are shown again, without taking the front, whatever the launch's end; the receipt says how many.
        try
        {
        for (int observation = 0; observation <= LaunchObservationIntervals; observation++)
        {
            int? processId = FindLaunchedProcess(before, installRoot);
            if (processId is not null)
            {
                // Ronda final 22 (regla 3): shown again before the receipt says so, and read back.
                (int shownAgain, int leftMinimized) = _automation.ShowAgain(dispatch);
                JsonElement result = ExternalJson.Create(writer =>
                {
                    writer.WriteStartObject(); writer.WriteNumber("version", 1);
                    writer.WriteString("appId", appId); writer.WriteString("name", game.Name);
                    writer.WriteNumber("processId", processId.Value);
                    if (dispatch.VisibleSteamWindowsBefore is { Count: > 0 })
                    {
                        writer.WriteNumber("steamWindowsShownAgain", shownAgain);
                        if (leftMinimized > 0)
                            writer.WriteNumber("steamWindowsLeftMinimized", leftMinimized);
                    }
                    writer.WriteString("authority", "steam_manifest_process_postread"); writer.WriteEndObject();
                });
                return ExternalJson.Success(operation, result, effectObserved: true);
            }

            // A dialog Steam may show before the game (its launch options) is confirmed as an act's dialog is, by the
            // mission's click on its own button (the data's names); no key is pressed (encargo imp-steam).
            if (observation == LaunchDialogObservation && launch.Confirm.Count > 0)
            {
                await _automation.ConfirmAsync(dispatch, launch.Confirm, cancellationToken).ConfigureAwait(false);
            }

            if (observation < LaunchObservationIntervals)
            {
                await _delay(ObservationInterval, cancellationToken).ConfigureAwait(false);
            }
        }
        return ExternalJson.Failure(operation, "steam_launch_process_not_verified", effectObserved: true);
        }
        finally
        {
            // Every other end shows them again too (a window already shown is left as it is).
            _ = _automation.ShowAgain(dispatch);
        }
    }

    // Every process running now, and one whose executable lies under the game's folder (null: none). The executable is
    // read with the least access Windows grants (an elevated game too).
    private (HashSet<int> Ids, int? Running) ReadProcesses(string installRoot)
    {
        IEnumerable<SteamProcessObservation> processes = _processSnapshot is not null
            ? _processSnapshot()
            : _processIds().Select(id => new SteamProcessObservation(id, _imagePath(id)));
        var ids = new HashSet<int>();
        int? running = null;
        foreach (SteamProcessObservation process in processes)
        {
            ids.Add(process.ProcessId);
            if (running is null && RunsFrom(process.ExecutablePath, installRoot))
                running = process.ProcessId;
        }

        return (ids, running);
    }

    private static bool RunsFrom(string? executable, string installRoot) =>
        executable is not null && Path.GetFullPath(executable).StartsWith(
            Path.TrimEndingDirectorySeparator(installRoot) + Path.DirectorySeparatorChar,
            StringComparison.OrdinalIgnoreCase);

    // Renew al máximo (auditoría de flujos): a process born after the launch is read as one already running is (by its
    // image, with the least access); its main module, read before, is refused for an elevated or protected game.
    private int? FindLaunchedProcess(HashSet<int> before, string installRoot)
    {
        if (_processSnapshot is not null)
        {
            foreach (SteamProcessObservation process in _processSnapshot())
            {
                if (!before.Contains(process.ProcessId) && RunsFrom(process.ExecutablePath, installRoot))
                {
                    return process.ProcessId;
                }
            }

            return null;
        }

        foreach (int processId in _processIds())
        {
            if (!before.Contains(processId) && RunsFrom(_imagePath(processId), installRoot))
            {
                return processId;
            }
        }

        return null;
    }

    private static ValueTask DelayAsync(
        TimeSpan delay,
        CancellationToken cancellationToken) =>
        new(Task.Delay(delay, cancellationToken));

    private static string RequireAppId(JsonElement arguments) =>
        ValidAppId(arguments) ?? throw new InvalidDataException("Steam AppID is invalid.");

    private static string? ValidAppId(JsonElement arguments)
    {
        string appId = ExternalJson.RequiredString(arguments, "appId");
        return appId.Length is < 1 or > 10
            || appId[0] == '0'
            || appId.Any(character => !char.IsAsciiDigit(character))
                ? null
                : appId;
    }

    private static void WriteGame(Utf8JsonWriter writer, SteamLocalGame game)
    {
        writer.WriteStartObject(); writer.WriteString("appId", game.AppId); writer.WriteString("name", game.Name);
        writer.WriteString("state", InstallState(game)); writer.WriteString("manifestSha256", game.ManifestSha256);
        writer.WriteNumber("bytesDownloaded", game.BytesDownloaded); writer.WriteNumber("bytesTotal", game.BytesToDownload);
        if (game.LastPlayedUtc is { } played) writer.WriteString("lastPlayedUtc", played);
        writer.WriteEndObject();
    }

    // Renew al máximo (B-APP-4): Steam's EAppState flags (Open Steamworks AppsCommon.h): UpdateRunning 256, UpdatePaused
    // 512, Downloading 1048576. Only a running flag says «downloading»; a download in pause (1538: UpdateRequired |
    // UpdatePaused | UpdateStarted), or one with bytes and no running flag, is «paused».
    // Encargo 52 (sesión real 03-11): the manifest Steam writes when it takes an install reads UpdateRequired |
    // UpdateStarted 1024 with no bytes counted yet, and it was told «queued» while Steam was already bringing it. A job
    // Steam started is «started»; a running flag is «downloading» before its first bytes reach the manifest; «queued» is
    // left for one with neither.
    private const ulong RunningFlags = 256UL | 1048576UL;
    private const ulong PausedFlag = 512UL;
    private const ulong UpdateStartedFlag = 1024UL;

    private static string InstallState(SteamLocalGame game) => game.Installed ? "installed" : DownloadState(game);

    // The state of the bytes Steam still has to bring: a game's install, or the update of an installed one.
    private static string DownloadState(SteamLocalGame game)
    {
        if (game.BytesToDownload > 0 && game.BytesDownloaded >= game.BytesToDownload) return "installing";
        if ((game.StateFlags & PausedFlag) != 0) return "paused";
        if ((game.StateFlags & RunningFlags) != 0) return "downloading";
        if (game.BytesDownloaded > 0) return "paused";
        return (game.StateFlags & UpdateStartedFlag) != 0 ? "started" : "queued";
    }

    // The bytes a manifest holds, with their readings (Holdout v4: «69 %» for 0.69 %, ReadingUnits) when it knows a total.
    private static void WriteBytes(Utf8JsonWriter writer, SteamLocalGame game)
    {
        writer.WriteNumber("bytesDownloaded", game.BytesDownloaded);
        writer.WriteNumber("bytesTotal", game.BytesToDownload);
        if (game.BytesToDownload > 0)
        {
            double progress = Math.Clamp(game.BytesDownloaded * 100d / game.BytesToDownload, 0d, 100d);
            writer.WriteNumber("progressPercent", progress);
            writer.WriteString("progress", Infrastructure.ReadingUnits.Percent(progress));
            writer.WriteString("downloaded", Infrastructure.ReadingUnits.Size(game.BytesDownloaded));
            writer.WriteString("total", Infrastructure.ReadingUnits.Size(game.BytesToDownload));
        }
        else writer.WriteNull("progressPercent");
    }

    // Encargo 52: the status of a game is read later by its own appId and the title it bears, as the call written.
    private static string StatusCall(SteamLocalGame game) =>
        WireNames.Call("game.install.status", new() { ["appId"] = game.AppId, ["title"] = game.Name });

    private static string JobId(string appId) => "steam_job_"
        + Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(appId)))[..24];

    // Ronda final 8 (regla 3): the installed games read, with how many of Steam's libraries could not be read (a drive
    // not mounted): while one is unread, the list is not all that is installed and «not installed» is not known.
    internal sealed class InstalledCatalog(IList<SteamLocalGame> games, int unreadLibraries)
        : System.Collections.ObjectModel.ReadOnlyCollection<SteamLocalGame>(games)
    {
        public int UnreadLibraries { get; } = unreadLibraries;
    }

    private static int UnreadLibraries(IReadOnlyList<SteamLocalGame> games) =>
        games is InstalledCatalog catalog ? catalog.UnreadLibraries : 0;

    // Renew al máximo (auditoría de flujos, P215): the games installed, as their manifests say them; none when the
    // manifests cannot be read (what reads them is only told a game apart).
    internal static IReadOnlyList<SteamLocalGame> InstalledGames()
    {
        try
        {
            return [.. ReadInstalledCatalog().Where(static game => game.Installed)];
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException
            or System.Security.SecurityException)
        {
            return [];
        }
    }

    private static IReadOnlyList<SteamLocalGame> ReadInstalledCatalog() => ReadInstalledCatalog(SteamRoots().Libraries);

    // Revisión de calidad (nb-q-apps): one manifest that cannot be read no longer fails the whole catalog. Steam deletes
    // a manifest at the end of an uninstall and rewrites it while it downloads, and the catalog is read every 500 ms
    // while BAXY waits on it: a manifest listed and gone by the time it is read is skipped (the game is no longer
    // there); one that is there and refuses its read leaves its library unread, as a library not found does.
    internal static IReadOnlyList<SteamLocalGame> ReadInstalledCatalog(
        IEnumerable<string> libraries,
        Func<string, byte[]>? read = null)
    {
        read ??= File.ReadAllBytes;
        var result = new Dictionary<string, SteamLocalGame>(StringComparer.Ordinal);
        int unread = 0;
        foreach (string library in libraries)
        {
            string steamApps = Path.Combine(library, "steamapps");
            if (!Directory.Exists(steamApps))
            {
                unread++;
                continue;
            }
            string[] manifests;
            try
            {
                manifests = Directory.GetFiles(steamApps, "appmanifest_*.acf");
            }
            catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
            {
                unread++;
                continue;
            }
            bool libraryUnread = false;
            foreach (string manifest in manifests)
            {
                byte[] bytes;
                try
                {
                    bytes = read(manifest);
                }
                catch (Exception exception) when (exception is FileNotFoundException or DirectoryNotFoundException)
                {
                    continue;
                }
                catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
                {
                    libraryUnread = true;
                    continue;
                }
                string text = Encoding.UTF8.GetString(bytes);
                var fields = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
                foreach (Match field in ManifestFieldRegex().Matches(text))
                {
                    fields[field.Groups[1].Value] = field.Groups[2].Value;
                }
                if (!fields.TryGetValue("appid", out string? appId)
                    || !fields.TryGetValue("name", out string? name)
                    || !appId.All(char.IsAsciiDigit) || string.IsNullOrWhiteSpace(name)) continue;
                _ = ulong.TryParse(fields.GetValueOrDefault("StateFlags"), out ulong flags);
                _ = long.TryParse(fields.GetValueOrDefault("BytesDownloaded"), out long downloaded);
                _ = long.TryParse(fields.GetValueOrDefault("BytesToDownload"), out long total);
                // 0 in a manifest of a game never played; a value out of the calendar is no date.
                _ = long.TryParse(fields.GetValueOrDefault("LastPlayed"), out long played);
                string installDirectory = fields.TryGetValue("installdir", out string? installDir)
                    ? Path.Combine(steamApps, "common", installDir) : string.Empty;
                result[appId] = new(appId, name, Convert.ToHexStringLower(SHA256.HashData(bytes)),
                    flags, Math.Max(0, downloaded), Math.Max(0, total), installDirectory,
                    played is > 0 and < 253402300800 ? DateTimeOffset.FromUnixTimeSeconds(played) : null);
            }
            if (libraryUnread)
                unread++;
        }
        return new InstalledCatalog(result.Values.ToArray(), unread);
    }

    private static IReadOnlyList<SteamStoreTitle>? ReadKnownGames() =>
        SteamAppInfo.ReadGames(Path.Combine(SteamRoots().Root, "appcache", "appinfo.vdf"));

    private static IReadOnlySet<string>? ReadOwnedAppIds() =>
        ReadOwnedAppIds(Path.Combine(SteamRoots().Root, "userdata"), SignedInAccount());

    // Auditoría final (regla 3): ownership is the account's library cache alone (an installed manifest may be a shared
    // or free game), and no cache read at all is null, never an empty library. Feria (NB-W5): a PC where two accounts
    // signed in keeps a cache for each, so only the signed-in account's counts; every cache only when there is none.
    internal static IReadOnlySet<string>? ReadOwnedAppIds(string userdata, string? account)
    {
        var result = new HashSet<string>(StringComparer.Ordinal);
        bool cacheRead = false;
        if (!Directory.Exists(userdata)) return null;
        string? signedIn = account is null ? null : Path.Combine(userdata, account);
        IEnumerable<string> users = signedIn is not null && Directory.Exists(Path.Combine(signedIn, "config", "librarycache"))
            ? [signedIn]
            : Directory.EnumerateDirectories(userdata);
        foreach (string user in users)
        {
            string cache = Path.Combine(user, "config", "librarycache");
            if (!Directory.Exists(cache)) continue;
            cacheRead = true;
            foreach (string file in Directory.EnumerateFiles(cache, "*.json"))
            {
                string appId = Path.GetFileNameWithoutExtension(file);
                if (appId.Length is > 0 and <= 10 && appId.All(char.IsAsciiDigit) && appId != "0")
                {
                    result.Add(appId);
                }
            }
        }
        return cacheRead ? result : null;
    }

    private static (string Root, string[] Libraries) SteamRoots()
    {
        using RegistryKey? steamKey = Registry.CurrentUser.OpenSubKey(@"Software\Valve\Steam");
        string root = steamKey?.GetValue("SteamPath") as string
            ?? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86), "Steam");
        var libraries = new HashSet<string>(StringComparer.OrdinalIgnoreCase) { root };
        string libraryFile = Path.Combine(root, "steamapps", "libraryfolders.vdf");
        if (File.Exists(libraryFile))
        {
            foreach (Match match in LibraryPathRegex().Matches(File.ReadAllText(libraryFile, Encoding.UTF8)))
            {
                libraries.Add(match.Groups[1].Value.Replace("\\\\", "\\", StringComparison.Ordinal));
            }
        }
        return (root, libraries.ToArray());
    }

    // The account Steam signs in with (its userdata folder's name), which Steam keeps once it has quit; null when it
    // names none.
    private static string? SignedInAccount()
    {
        using RegistryKey? process = Registry.CurrentUser.OpenSubKey(@"Software\Valve\Steam\ActiveProcess");
        return process?.GetValue("ActiveUser") is int account and not 0
            ? unchecked((uint)account).ToString(System.Globalization.CultureInfo.InvariantCulture)
            : null;
    }

    [GeneratedRegex("\\\"path\\\"\\s+\\\"([^\\\"]+)\\\"", RegexOptions.IgnoreCase)]
    private static partial Regex LibraryPathRegex();
    [GeneratedRegex("^\\s*\\\"([^\\\"]+)\\\"\\s+\\\"([^\\\"]*)\\\"", RegexOptions.Multiline)]
    private static partial Regex ManifestFieldRegex();
}

internal sealed record SteamLocalGame(
    string AppId,
    string Name,
    string ManifestSha256,
    ulong StateFlags = 4,
    long BytesDownloaded = 0,
    long BytesToDownload = 0,
    string InstallDirectory = "",
    DateTimeOffset? LastPlayedUtc = null)
{
    internal bool Installed => (StateFlags & 4UL) != 0;
}

internal sealed record SteamDispatchResult(
    bool Accepted,
    bool EffectObserved,
    IReadOnlySet<nint>? VisibleSteamWindowsBefore = null);

internal sealed record SteamProcessObservation(int ProcessId, string? ExecutablePath);

/// <summary>A game of the store's title search, or of the ones this Steam client knows (<see cref="SteamAppInfo"/>): its
/// catalog number and its name.</summary>
internal sealed record SteamStoreTitle(string AppId, string Name);

internal interface ISteamClientAutomation
{
    ValueTask<SteamDispatchResult> DispatchAsync(string uri, CancellationToken cancellationToken);
    /// <summary>Presses, on the dialog Steam opened for <paramref name="dispatch"/>, its control named by one of <paramref name="labels"/>.</summary>
    ValueTask<SteamDispatchResult> ConfirmAsync(
        SteamDispatchResult dispatch,
        IReadOnlyList<string> labels,
        CancellationToken cancellationToken);

    /// <summary>Ronda final 21-22: shows again, without activating them, the Steam windows <paramref name="dispatch"/>
    /// minimized that are still minimized, and reads them back: how many were shown again, and how many stay minimized.</summary>
    (int ShownAgain, int LeftMinimized) ShowAgain(SteamDispatchResult dispatch) => (0, 0);
}

internal sealed partial class WindowsSteamClientAutomation : ISteamClientAutomation
{
    public (int ShownAgain, int LeftMinimized) ShowAgain(SteamDispatchResult dispatch)
    {
        int shown = 0;
        int left = 0;
        foreach (nint window in dispatch.VisibleSteamWindowsBefore ?? new HashSet<nint>())
        {
            if (!IsIconic(window))
                continue;
            _ = ShowWindow(window, 4);
            if (IsIconic(window))
                left++;
            else
                shown++;
        }

        return (shown, left);
    }

    // How long the dialog an act's address opens is waited for, and from which look a Steam window in front counts as
    // the one it is drawn on (measured 2026-10-11 on the development PC: the dialog was up within a second; Steam on screen draws it
    // over its main window and takes the front, Steam minimized opens it as a window of its own).
    private const int DialogLooks = 24;
    private const int FrontLook = 4;
    private static readonly TimeSpan DialogLookInterval = TimeSpan.FromMilliseconds(250);
    private readonly Func<string, long, CancellationToken, ValueTask<ExternalCapabilityReceipt>>? _press;

    internal WindowsSteamClientAutomation(
        Func<string, long, CancellationToken, ValueTask<ExternalCapabilityReceipt>>? press = null)
    {
        _press = press;
    }

    public ValueTask<SteamDispatchResult> DispatchAsync(string uri, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        // REOPEN1993 grupo S: the Epic launcher takes its own install links.
        if (!Uri.TryCreate(uri, UriKind.Absolute, out Uri? parsed)
            || parsed.Scheme is not ("steam" or "com.epicgames.launcher"))
        {
            return ValueTask.FromResult(new SteamDispatchResult(false, false));
        }
        // The windows Steam shows before the address, so the dialog it opens is told apart (ConfirmAsync). A launch
        // minimizes them first: a launch dialog then opens as a window of its own, never one drawn over the library.
        IReadOnlySet<nint>? visibleBefore = parsed.Scheme == "steam" ? SteamTopWindows() : null;
        if (visibleBefore is not null && uri.StartsWith("steam://rungameid/", StringComparison.Ordinal))
        {
            foreach (nint window in visibleBefore)
            {
                _ = ShowWindow(window, 6);
            }
        }
        var start = new ProcessStartInfo(uri) { UseShellExecute = true };
        try
        {
            using Process? process = Process.Start(start);
            return ValueTask.FromResult(new SteamDispatchResult(
                true,
                true,
                visibleBefore));
        }
        catch (System.ComponentModel.Win32Exception)
        {
            return ValueTask.FromResult(new SteamDispatchResult(false, false));
        }
    }

    /// <summary>
    /// Encargo imp-steam: the dialog an act's address opened is confirmed as a step of a mission confirms one, by the
    /// mission's click on that window by a label (input.visible.click: the accessible tree, else OCR and the pointer in a
    /// burst of the foreground lease); the labels come from the data. Steam's own window only: one it opened for the
    /// address, or the one of its windows that took the front with the dialog drawn over it. Nothing is pressed when no
    /// such window shows; a press that may have landed is never followed by another label.
    /// </summary>
    public async ValueTask<SteamDispatchResult> ConfirmAsync(
        SteamDispatchResult dispatch,
        IReadOnlyList<string> labels,
        CancellationToken cancellationToken)
    {
        if (!dispatch.Accepted || _press is null || labels.Count == 0)
        {
            return new(false, false);
        }

        nint window = await DialogWindowAsync(dispatch.VisibleSteamWindowsBefore, cancellationToken).ConfigureAwait(false);
        if (window == 0)
        {
            return new(false, false);
        }

        foreach (string label in labels)
        {
            ExternalCapabilityReceipt pressed = await _press(label, window, cancellationToken).ConfigureAwait(false);
            if (pressed.Verified)
            {
                return new(true, true);
            }

            if (pressed.EffectObserved || pressed.EffectMayHaveOccurred)
            {
                return new(false, true);
            }
        }

        return new(false, false);
    }

    private static async ValueTask<nint> DialogWindowAsync(IReadOnlySet<nint>? before, CancellationToken cancellationToken)
    {
        for (int look = 0; look < DialogLooks; look++)
        {
            HashSet<nint> now = SteamTopWindows();
            nint front = GetForegroundWindow();
            nint[] born = [.. now.Where(window => before is null || !before.Contains(window))];
            if (born.Length > 0)
            {
                // The dialog takes the front (measured); a main window shown again beside it does not.
                return born.Contains(front) ? front : born[0];
            }

            if (look >= FrontLook && now.Contains(front))
            {
                return front;
            }

            await Task.Delay(DialogLookInterval, cancellationToken).ConfigureAwait(false);
        }

        return 0;
    }

    // Every visible, not minimized top-level window of Steam's interface process (its dialogs are windows of their own,
    // which a process's main window handle does not list).
    private static HashSet<nint> SteamTopWindows()
    {
        Process[] processes = Process.GetProcessesByName("steamwebhelper");
        HashSet<uint> owners;
        try
        {
            owners = [.. processes.Select(static process => unchecked((uint)process.Id))];
        }
        finally
        {
            foreach (Process process in processes)
            {
                process.Dispose();
            }
        }

        var windows = new HashSet<nint>();
        if (owners.Count == 0)
        {
            return windows;
        }

        EnumWindowsProc callback = (window, _) =>
        {
            if (IsWindowVisible(window) && !IsIconic(window)
                && GetWindowThreadProcessId(window, out uint owner) != 0 && owners.Contains(owner))
            {
                windows.Add(window);
            }

            return true;
        };
        _ = EnumWindows(callback, 0);
        GC.KeepAlive(callback);
        return windows;
    }

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool ShowWindow(nint window, int command);
    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsWindowVisible(nint window);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool IsIconic(nint window);

    [LibraryImport("user32.dll")]
    private static partial nint GetForegroundWindow();

    [LibraryImport("user32.dll")]
    private static partial uint GetWindowThreadProcessId(nint window, out uint processId);

    [UnmanagedFunctionPointer(CallingConvention.Winapi)]
    private delegate bool EnumWindowsProc(nint window, nint lParam);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool EnumWindows(EnumWindowsProc callback, nint lParam);
}
