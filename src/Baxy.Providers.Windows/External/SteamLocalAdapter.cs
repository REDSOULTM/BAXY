using System.Collections.Concurrent;
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
    private const string GameCatalog = "steam";
    private const int InstallObservationIntervals = 60;
    private const int CancelObservationIntervals = 30;
    private const int LaunchObservationIntervals = 70;
    private const int LaunchDialogObservation = 10;
    private static readonly TimeSpan ObservationInterval = TimeSpan.FromMilliseconds(500);
    private readonly Func<IReadOnlyList<SteamLocalGame>> _snapshot;
    private readonly Func<IReadOnlySet<string>> _owned;
    private readonly ISteamClientAutomation _automation;
    private readonly Func<TimeSpan, CancellationToken, ValueTask> _delay;
    private readonly Func<IReadOnlyList<SteamProcessObservation>>? _processSnapshot;
    private readonly ConcurrentDictionary<string, SteamInstallPreparation> _preparations = new();
    private readonly Func<string, CancellationToken, ValueTask<IReadOnlyList<SteamStoreTitle>>>? _storeTitles;

    // Encargo imp-steam: a title turns into its catalog number by the installed games' manifests and, for one not
    // installed, by the store's public title search the data declare (only the title leaves); 13 titles written here
    // (KnownTitleAppIds, with misheard variants) were retired. The dialog Steam opens for an act's address is confirmed
    // by the mission's own click (input.visible.click on Steam's window, the label from the data), handed in here.
    internal SteamLocalAdapter(IExternalOperationAdapter? clicks = null)
        : this(
            ReadInstalledCatalog,
            ReadOwnedAppIds,
            new WindowsSteamClientAutomation(press: clicks is null ? null : PressBy(clicks)),
            storeTitles: SearchStoreAsync)
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
        Func<IReadOnlySet<string>> owned,
        ISteamClientAutomation automation,
        Func<TimeSpan, CancellationToken, ValueTask>? delay = null,
        Func<IReadOnlyList<SteamProcessObservation>>? processSnapshot = null,
        Func<string, CancellationToken, ValueTask<IReadOnlyList<SteamStoreTitle>>>? storeTitles = null)
    {
        _snapshot = snapshot ?? throw new ArgumentNullException(nameof(snapshot));
        _owned = owned ?? throw new ArgumentNullException(nameof(owned));
        _automation = automation ?? throw new ArgumentNullException(nameof(automation));
        _delay = delay ?? DelayAsync;
        _processSnapshot = processSnapshot;
        _storeTitles = storeTitles;
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
        InstalledGameCatalogEntry[] entries = _snapshot()
            .Where(static game => game.Installed)
            .OrderBy(static game => game.Name, StringComparer.OrdinalIgnoreCase)
            .ThenBy(static game => game.AppId, StringComparer.Ordinal)
            .Select(static game => new InstalledGameCatalogEntry(
                GameCatalog,
                game.AppId,
                game.Name))
            .ToArray();
        return new InstalledGameCatalogSnapshot(
            Verified: true,
            Complete: true,
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
                "game.entitlement.named" => await EntitlementNamedAsync(operation, arguments, cancellationToken)
                    .ConfigureAwait(false),
                "game.install.prepare" => Prepare(operation, arguments),
                "game.install.commit" => await CommitAsync(
                    operation, arguments, effectBoundary, cancellationToken)
                    .ConfigureAwait(false),
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
                "game.purchase.prepare" => ExternalJson.Failure(operation, "steam_price_authority_required"),
                "game.purchase.commit" => ExternalJson.Failure(operation, "steam_purchase_live_gate_forbidden"),
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
        SteamLocalGame[] games = _snapshot()
            .Where(game => query.Length == 0
                || game.AppId.Contains(query, StringComparison.OrdinalIgnoreCase)
                || game.Name.Contains(query, StringComparison.CurrentCultureIgnoreCase))
            .OrderBy(game => game.Name, StringComparer.CurrentCultureIgnoreCase)
            .Take(limit)
            .ToArray();
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("source", "steam_local_appmanifests");
            writer.WriteNumber("count", games.Length); writer.WriteStartArray("games");
            foreach (SteamLocalGame game in games)
            {
                WriteGame(writer, game);
            }
            writer.WriteEndArray(); writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: false);
    }

    // INSTALL1617 «Descarga Worms Rumble en Steam»: before any download the
    // turn needs a truthful answer to «is this game mine and is it installed?».
    // The title resolves like game.install.named (the local snapshot, then the
    // store's title search); an unresolved title is reported as such, never guessed.
    private async ValueTask<ExternalCapabilityReceipt> EntitlementNamedAsync(
        string operation, JsonElement arguments, CancellationToken cancellationToken)
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
            return EpicEntitlementNamed(operation, title);
        }
        string? appId = await ResolveTitleAsync(title, cancellationToken).ConfigureAwait(false);
        SteamLocalGame? game = appId is null
            ? null
            : _snapshot().SingleOrDefault(candidate => candidate.AppId == appId);
        bool owned = appId is not null && _owned().Contains(appId);
        bool installed = game is { Installed: true };
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("query", title);
            writer.WriteBoolean("resolved", appId is not null);
            if (appId is null) writer.WriteNull("appId"); else writer.WriteString("appId", appId);
            writer.WriteString("title", game?.Name ?? title);
            writer.WriteBoolean("owned", owned);
            writer.WriteBoolean("installed", installed);
            writer.WriteString("state", appId is null ? "title_not_resolved"
                : installed ? "installed"
                : owned ? "owned_not_installed" : "not_in_library");
            writer.WriteString("authority", installed
                ? "steam_local_appmanifest" : "steam_authenticated_library_cache");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: false);
    }

    private ExternalCapabilityReceipt Prepare(string operation, JsonElement arguments)
    {
        string appId = RequireAppId(arguments);
        SteamLocalGame? game = _snapshot().SingleOrDefault(candidate => candidate.AppId == appId);
        if (game is not null && game.Installed)
        {
            JsonElement installed = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject(); writer.WriteNumber("version", 1);
                writer.WriteString("confirmationId", ConfirmationId(appId, game.ManifestSha256));
                writer.WriteString("appId", appId); writer.WriteString("name", game.Name);
                writer.WriteString("state", "already_installed"); writer.WriteBoolean("requiresInstall", false);
                writer.WriteString("authority", "steam_local_appmanifest"); writer.WriteEndObject();
            });
            return ExternalJson.Success(operation, installed, effectObserved: false);
        }
        if (!_owned().Contains(appId))
        {
            return ExternalJson.Failure(operation, "steam_entitlement_not_verified");
        }
        string authority = game?.ManifestSha256 ?? OwnedAuthority(appId);
        string confirmationId = ConfirmationId(appId, authority);
        _preparations[confirmationId] = new(appId, authority, DateTimeOffset.UtcNow.AddMinutes(5));
        JsonElement prepared = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("confirmationId", confirmationId); writer.WriteString("appId", appId);
            writer.WriteString("name", game?.Name ?? "Steam App " + appId);
            writer.WriteString("state", game is null ? "ready_to_install" : InstallState(game));
            writer.WriteBoolean("requiresInstall", true);
            writer.WriteString("authority", "steam_authenticated_library_cache"); writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, prepared, effectObserved: false);
    }

    private async ValueTask<ExternalCapabilityReceipt> CommitAsync(
        string operation,
        JsonElement arguments,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        string confirmationId = ExternalJson.RequiredString(arguments, "confirmationId");
        if (!_preparations.TryRemove(confirmationId, out SteamInstallPreparation? prepared)
            || prepared.ExpiresAtUtc <= DateTimeOffset.UtcNow)
        {
            return ExternalJson.Failure(operation, "steam_install_confirmation_expired");
        }
        if (!_owned().Contains(prepared.AppId)
            || !string.Equals(ConfirmationId(prepared.AppId, prepared.Authority), confirmationId, StringComparison.Ordinal))
        {
            return ExternalJson.Failure(operation, "steam_install_authority_changed");
        }
        return await DispatchInstallAsync(
            operation, prepared.AppId, effectBoundary, cancellationToken)
            .ConfigureAwait(false);
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

        string? appId = await ResolveTitleAsync(title, cancellationToken).ConfigureAwait(false);
        if (appId is null)
            return ExternalJson.Failure(operation, "steam_title_not_resolved");
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
            return ExternalJson.Success(operation, installed, effectObserved: false);
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
                    writer.WriteNumber("bytesDownloaded", after.BytesDownloaded);
                    writer.WriteNumber("bytesTotal", after.BytesToDownload);
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
    // catcache.bin: id, title, namespace). Both are read, nothing is written; a title
    // that matches exactly one catalog entry is resolved, anything else is not.
    private static string EpicLauncherDataRoot => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData),
        "Epic", "EpicGamesLauncher", "Data");

    private static ExternalCapabilityReceipt EpicEntitlementNamed(string operation, string title)
    {
        string folded = FoldTitle(title);
        string manifests = Path.Combine(EpicLauncherDataRoot, "Manifests");
        string catalogCache = Path.Combine(EpicLauncherDataRoot, "Catalog", "catcache.bin");
        if (!Directory.Exists(manifests) && !File.Exists(catalogCache))
        {
            return ExternalJson.Failure(operation, "epic_launcher_data_not_found");
        }
        string? installedName = null;
        string? installedCatalogId = null;
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
                        || displayName.ValueKind != JsonValueKind.String
                        || FoldTitle(displayName.GetString() ?? string.Empty) != folded
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
                }
                catch (IOException)
                {
                }
            }
        }
        string? ownedName = null;
        string? ownedCatalogId = null;
        int ownedMatches = 0;
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
                            || itemTitle.ValueKind != JsonValueKind.String
                            || FoldTitle(itemTitle.GetString() ?? string.Empty) != folded)
                        {
                            continue;
                        }
                        ownedMatches++;
                        ownedName ??= itemTitle.GetString();
                        ownedCatalogId ??= item.TryGetProperty("id", out JsonElement itemId)
                            && itemId.ValueKind == JsonValueKind.String ? itemId.GetString() : null;
                    }
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
        bool owned = installed || ownedMatches >= 1;
        string? catalogItemId = installedCatalogId ?? ownedCatalogId;
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("query", title);
            writer.WriteString("store", "epic");
            writer.WriteBoolean("resolved", owned);
            if (catalogItemId is null) writer.WriteNull("appId"); else writer.WriteString("appId", catalogItemId);
            writer.WriteString("title", installedName ?? ownedName ?? title);
            writer.WriteBoolean("owned", owned);
            writer.WriteBoolean("installed", installed);
            writer.WriteString("state", installed ? "installed"
                : owned ? "owned_not_installed" : "not_in_library");
            writer.WriteString("authority", installed
                ? "epic_launcher_local_manifest" : "epic_launcher_catalog_cache");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: false);
    }

    private async ValueTask<string?> ResolveTitleAsync(string title, CancellationToken cancellationToken)
    {
        string folded = FoldTitle(title);
        string? installed = ResolveSnapshotTitle(folded);
        if (installed is not null || _storeTitles is null)
        {
            return installed;
        }

        IReadOnlyList<SteamStoreTitle> found;
        try
        {
            found = await _storeTitles(title, cancellationToken).ConfigureAwait(false);
        }
        catch (Exception exception) when (exception is HttpRequestException or JsonException or IOException
            || (exception is TaskCanceledException && !cancellationToken.IsCancellationRequested))
        {
            return null;
        }

        // Exactly one game of the store answer bears the title (folded): «Super Meat Boy» is not «Super Meat Boy Forever».
        string[] matches = found
            .Where(item => FoldTitle(item.Name) == folded)
            .Select(item => item.AppId)
            .Distinct(StringComparer.Ordinal)
            .ToArray();
        return matches.Length == 1 ? matches[0] : null;
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
        if (!response.IsSuccessStatusCode)
        {
            return [];
        }

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

    private string? ResolveSnapshotTitle(string folded)
    {
        string[] matches = _snapshot()
            .Where(game => FoldTitle(game.Name) == folded)
            .Select(game => game.AppId)
            .Distinct(StringComparer.Ordinal)
            .ToArray();
        return matches.Length == 1 ? matches[0] : null;
    }

    private static string FoldTitle(string value)
    {
        string decomposed = value.Normalize(NormalizationForm.FormD);
        return string.Join(' ', new string(decomposed
            .Where(character => System.Globalization.CharUnicodeInfo.GetUnicodeCategory(character)
                != System.Globalization.UnicodeCategory.NonSpacingMark)
            .Select(char.ToLowerInvariant)
            .Select(character => char.IsLetterOrDigit(character) ? character : ' ')
            .ToArray()).Split(' ', StringSplitOptions.RemoveEmptyEntries));
    }

    private ExternalCapabilityReceipt Status(string operation, JsonElement arguments)
    {
        string appId = RequireAppId(arguments);
        SteamLocalGame? game = _snapshot().SingleOrDefault(candidate => candidate.AppId == appId);
        bool owned = _owned().Contains(appId);
        if (game is null && !owned)
        {
            return ExternalJson.Failure(operation, "steam_app_not_in_authenticated_library");
        }
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("jobId", JobId(appId)); writer.WriteString("appId", appId);
            writer.WriteString("state", game is null ? "not_installed" : InstallState(game));
            writer.WriteNumber("bytesDownloaded", game?.BytesDownloaded ?? 0);
            writer.WriteNumber("bytesTotal", game?.BytesToDownload ?? 0);
            if (game is not null && game.BytesToDownload > 0)
            {
                writer.WriteNumber("progressPercent", Math.Clamp(
                    game.BytesDownloaded * 100d / game.BytesToDownload, 0d, 100d));
            }
            else writer.WriteNull("progressPercent");
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
                    && InstallState(after) is "paused" or "not_installed");
            bool changedFromPreDispatch = after is null
                || after.BytesDownloaded != before.BytesDownloaded
                || !string.Equals(
                    InstallState(after),
                    InstallState(before),
                    StringComparison.Ordinal);
            if (terminal && (observation > 0 || changedFromPreDispatch))
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
        string[] active = _snapshot()
            .Where(game => !game.Installed && game.BytesDownloaded > 0
                && InstallState(game) is "downloading" or "installing")
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
        string[] remaining = _snapshot()
            .Where(game => !game.Installed && game.BytesDownloaded > 0
                && InstallState(game) is "downloading" or "installing")
            .Select(game => game.AppId).Distinct(StringComparer.Ordinal).ToArray();
        if (remaining.Length != 0)
            return ExternalJson.Failure(operation, "steam_active_downloads_remain", active.Length > 0);
        return ExternalJson.Success(operation, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteNumber("canceledCount", active.Length);
            writer.WriteNumber("remainingActiveCount", 0);
            writer.WriteString("authority", "steam_manifest_all_active_postread");
            writer.WriteEndObject();
        }), active.Length > 0);
    }

    private async ValueTask<ExternalCapabilityReceipt> LaunchAsync(
        string operation,
        JsonElement arguments,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        string appId = RequireAppId(arguments);
        SteamLocalGame? game = _snapshot().SingleOrDefault(candidate => candidate.AppId == appId);
        if (game is null || !game.Installed || string.IsNullOrWhiteSpace(game.InstallDirectory))
        {
            return ExternalJson.Failure(operation, "steam_installed_game_not_verified");
        }
        ApplicationPlaces.GameAct? launch = ApplicationPlaces.GameActOf(GameCatalog, "launch", appId);
        if (launch is null)
        {
            return ExternalJson.FailureBeforeEffect(operation, "steam_act_not_declared");
        }

        HashSet<int> before = ReadProcessIds();
        effectBoundary.Cross(cancellationToken);
        SteamDispatchResult dispatch = await _automation.DispatchAsync(launch.Address, cancellationToken)
            .ConfigureAwait(false);
        if (!dispatch.Accepted)
        {
            return effectBoundary.Failure(
                operation, "steam_launch_dispatch_rejected", dispatch.EffectObserved);
        }
        string installRoot = Path.GetFullPath(game.InstallDirectory);
        for (int observation = 0; observation <= LaunchObservationIntervals; observation++)
        {
            int? processId = FindLaunchedProcess(before, installRoot);
            if (processId is not null)
            {
                JsonElement result = ExternalJson.Create(writer =>
                {
                    writer.WriteStartObject(); writer.WriteNumber("version", 1);
                    writer.WriteString("appId", appId); writer.WriteString("name", game.Name);
                    writer.WriteNumber("processId", processId.Value);
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

    private HashSet<int> ReadProcessIds()
    {
        if (_processSnapshot is not null)
        {
            return _processSnapshot()
                .Select(static process => process.ProcessId)
                .ToHashSet();
        }

        return Process.GetProcesses().Select(process =>
        {
            using (process) return process.Id;
        }).ToHashSet();
    }

    private int? FindLaunchedProcess(HashSet<int> before, string installRoot)
    {
        string installPrefix =
            Path.TrimEndingDirectorySeparator(installRoot) + Path.DirectorySeparatorChar;
        if (_processSnapshot is not null)
        {
            foreach (SteamProcessObservation process in _processSnapshot())
            {
                if (!before.Contains(process.ProcessId)
                    && process.ExecutablePath is not null
                    && Path.GetFullPath(process.ExecutablePath).StartsWith(
                        installPrefix,
                        StringComparison.OrdinalIgnoreCase))
                {
                    return process.ProcessId;
                }
            }

            return null;
        }

        foreach (Process process in Process.GetProcesses())
        {
            using (process)
            {
                if (before.Contains(process.Id)) continue;
                try
                {
                    string? executable = process.MainModule?.FileName;
                    if (executable is not null && Path.GetFullPath(executable).StartsWith(
                        installPrefix,
                        StringComparison.OrdinalIgnoreCase))
                    {
                        return process.Id;
                    }
                }
                catch (Exception exception) when (exception is InvalidOperationException
                    or System.ComponentModel.Win32Exception)
                {
                }
            }
        }

        return null;
    }

    private static ValueTask DelayAsync(
        TimeSpan delay,
        CancellationToken cancellationToken) =>
        new(Task.Delay(delay, cancellationToken));

    private static string RequireAppId(JsonElement arguments)
    {
        string appId = ExternalJson.RequiredString(arguments, "appId");
        if (appId.Length is < 1 or > 10
            || appId[0] == '0'
            || appId.Any(character => !char.IsAsciiDigit(character)))
        {
            throw new InvalidDataException("Steam AppID is invalid.");
        }
        return appId;
    }

    private static void WriteGame(Utf8JsonWriter writer, SteamLocalGame game)
    {
        writer.WriteStartObject(); writer.WriteString("appId", game.AppId); writer.WriteString("name", game.Name);
        writer.WriteString("state", InstallState(game)); writer.WriteString("manifestSha256", game.ManifestSha256);
        writer.WriteNumber("bytesDownloaded", game.BytesDownloaded); writer.WriteNumber("bytesTotal", game.BytesToDownload);
        writer.WriteEndObject();
    }

    private static string InstallState(SteamLocalGame game)
    {
        if (game.Installed) return "installed";
        if (game.BytesToDownload > 0 && game.BytesDownloaded >= game.BytesToDownload) return "installing";
        if (game.BytesDownloaded > 0) return game.StateFlags == 2 ? "paused" : "downloading";
        return "queued";
    }

    private static string ConfirmationId(string appId, string authority) => "steam_install_"
        + Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(appId + "\n" + authority)))[..24];
    private static string JobId(string appId) => "steam_job_"
        + Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(appId)))[..24];
    private static string OwnedAuthority(string appId) => Convert.ToHexStringLower(
        SHA256.HashData(Encoding.UTF8.GetBytes("steam-library-cache\n" + appId)));

    private static IReadOnlyList<SteamLocalGame> ReadInstalledCatalog()
    {
        (string root, string[] libraries) = SteamRoots();
        var result = new Dictionary<string, SteamLocalGame>(StringComparer.Ordinal);
        foreach (string library in libraries)
        {
            string steamApps = Path.Combine(library, "steamapps");
            if (!Directory.Exists(steamApps)) continue;
            foreach (string manifest in Directory.EnumerateFiles(steamApps, "appmanifest_*.acf"))
            {
                byte[] bytes = File.ReadAllBytes(manifest);
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
                string installDirectory = fields.TryGetValue("installdir", out string? installDir)
                    ? Path.Combine(steamApps, "common", installDir) : string.Empty;
                result[appId] = new(appId, name, Convert.ToHexStringLower(SHA256.HashData(bytes)),
                    flags, Math.Max(0, downloaded), Math.Max(0, total), installDirectory, manifest);
            }
        }
        _ = root;
        return result.Values.ToArray();
    }

    private static IReadOnlySet<string> ReadOwnedAppIds()
    {
        (string root, _) = SteamRoots();
        var result = new HashSet<string>(StringComparer.Ordinal);
        string userdata = Path.Combine(root, "userdata");
        if (!Directory.Exists(userdata)) return result;
        foreach (string user in Directory.EnumerateDirectories(userdata))
        {
            string cache = Path.Combine(user, "config", "librarycache");
            if (!Directory.Exists(cache)) continue;
            foreach (string file in Directory.EnumerateFiles(cache, "*.json"))
            {
                string appId = Path.GetFileNameWithoutExtension(file);
                if (appId.Length is > 0 and <= 10 && appId.All(char.IsAsciiDigit) && appId != "0")
                {
                    result.Add(appId);
                }
            }
        }
        foreach (SteamLocalGame installed in ReadInstalledCatalog()) result.Add(installed.AppId);
        return result;
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

    [GeneratedRegex("\\\"path\\\"\\s+\\\"([^\\\"]+)\\\"", RegexOptions.IgnoreCase)]
    private static partial Regex LibraryPathRegex();
    [GeneratedRegex("^\\s*\\\"([^\\\"]+)\\\"\\s+\\\"([^\\\"]*)\\\"", RegexOptions.Multiline)]
    private static partial Regex ManifestFieldRegex();
}

internal sealed record SteamInstallPreparation(string AppId, string Authority, DateTimeOffset ExpiresAtUtc);

internal sealed record SteamLocalGame(
    string AppId,
    string Name,
    string ManifestSha256,
    ulong StateFlags = 4,
    long BytesDownloaded = 0,
    long BytesToDownload = 0,
    string InstallDirectory = "",
    string ManifestPath = "")
{
    internal bool Installed => (StateFlags & 4UL) != 0;
}

internal sealed record SteamDispatchResult(
    bool Accepted,
    bool EffectObserved,
    IReadOnlySet<nint>? VisibleSteamWindowsBefore = null,
    string? ErrorCode = null);

internal sealed record SteamProcessObservation(int ProcessId, string? ExecutablePath);

/// <summary>A game of the store's title search: its catalog number and its name.</summary>
internal sealed record SteamStoreTitle(string AppId, string Name);

internal interface ISteamClientAutomation
{
    ValueTask<SteamDispatchResult> DispatchAsync(string uri, CancellationToken cancellationToken);
    /// <summary>Presses, on the dialog Steam opened for <paramref name="dispatch"/>, its control named by one of <paramref name="labels"/>.</summary>
    ValueTask<SteamDispatchResult> ConfirmAsync(
        SteamDispatchResult dispatch,
        IReadOnlyList<string> labels,
        CancellationToken cancellationToken);
}

internal sealed partial class WindowsSteamClientAutomation : ISteamClientAutomation
{
    // How long the dialog an act's address opens is waited for, and from which look a Steam window in front counts as
    // the one it is drawn on (measured 2026-10-11 on redpc: the dialog was up within a second; Steam on screen draws it
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
                return new(false, true, ErrorCode: pressed.ErrorCode);
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
