using System.Collections.Concurrent;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using Microsoft.Win32;

namespace Baxy.Providers.Windows.External;

internal sealed partial class SteamLocalAdapter : IExternalOperationAdapter
{
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
    private static readonly Dictionary<string, string> KnownTitleAppIds =
        new Dictionary<string, string>(StringComparer.Ordinal)
        {
            ["batman arkham knight"] = "208650",
            ["batman arkham knights"] = "208650",
            ["batman arkham nike"] = "208650",
            ["diin eternal"] = "782330",
            ["doom"] = "782330",
            ["doom eternal"] = "782330",
            ["fall guys"] = "1097150",
            ["hades"] = "1145360",
            ["marvel rivals"] = "2767030",
            ["mortal kombat 11"] = "976310",
            ["stardew valley"] = "413150",
            ["terraria"] = "105600",
            ["worms rumble"] = "1186040",
        };

    internal SteamLocalAdapter()
        : this(ReadInstalledCatalog, ReadOwnedAppIds, new WindowsSteamClientAutomation())
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
        Func<IReadOnlyList<SteamProcessObservation>>? processSnapshot = null)
    {
        _snapshot = snapshot ?? throw new ArgumentNullException(nameof(snapshot));
        _owned = owned ?? throw new ArgumentNullException(nameof(owned));
        _automation = automation ?? throw new ArgumentNullException(nameof(automation));
        _delay = delay ?? DelayAsync;
        _processSnapshot = processSnapshot;
    }

    public bool CanHandle(string operation) => operation.StartsWith("game.", StringComparison.Ordinal);

    internal InstalledGameCatalogSnapshot GetCatalogSnapshot()
    {
        InstalledGameCatalogEntry[] entries = _snapshot()
            .Where(static game => game.Installed)
            .OrderBy(static game => game.Name, StringComparer.OrdinalIgnoreCase)
            .ThenBy(static game => game.AppId, StringComparer.Ordinal)
            .Select(static game => new InstalledGameCatalogEntry(
                "steam",
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
                "game.entitlement.named" => EntitlementNamed(operation, arguments),
                "game.install.prepare" => Prepare(operation, arguments),
                "game.install.commit" => await CommitAsync(
                    operation, arguments, effectBoundary, cancellationToken)
                    .ConfigureAwait(false),
                "game.install.named" => await InstallNamedAsync(
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
    // The title resolves like game.install.named (closed titles, then the local
    // snapshot); an unresolved title is reported as such, never guessed.
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
            return EpicEntitlementNamed(operation, title);
        }
        string folded = FoldTitle(title);
        string? appId = KnownTitleAppIds.TryGetValue(folded, out string? known)
            ? known
            : ResolveSnapshotTitle(folded);
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
        string folded = FoldTitle(title);
        string? appId = KnownTitleAppIds.TryGetValue(folded, out string? known)
            ? known
            : ResolveSnapshotTitle(folded);
        if (appId is null)
            return ExternalJson.Failure(operation, "steam_title_not_resolved");
        if (!_owned().Contains(appId))
            return ExternalJson.Failure(operation, "steam_entitlement_not_verified");
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
        effectBoundary.Cross(cancellationToken);
        SteamDispatchResult dispatch = await _automation.DispatchAsync(
            "steam://install/" + appId,
            cancellationToken).ConfigureAwait(false);
        if (!dispatch.Accepted)
        {
            return effectBoundary.Failure(
                operation, "steam_install_dispatch_rejected", dispatch.EffectObserved);
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
        effectBoundary.Cross(cancellationToken);
        SteamDispatchResult dispatch = await _automation.CancelPartialAsync(appId, cancellationToken)
            .ConfigureAwait(false);
        if (!dispatch.Accepted)
        {
            return effectBoundary.Failure(
                operation, "steam_cancel_dispatch_rejected", dispatch.EffectObserved);
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
        HashSet<int> before = ReadProcessIds();
        effectBoundary.Cross(cancellationToken);
        SteamDispatchResult dispatch = await _automation.DispatchAsync(
            "steam://rungameid/" + appId,
            cancellationToken).ConfigureAwait(false);
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

            if (observation == LaunchDialogObservation)
            {
                await _automation.ContinueLaunchDialogAsync(
                    dispatch,
                    cancellationToken).ConfigureAwait(false);
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
    IReadOnlySet<nint>? VisibleSteamWindowsBefore = null);

internal sealed record SteamProcessObservation(int ProcessId, string? ExecutablePath);

internal interface ISteamClientAutomation
{
    ValueTask<SteamDispatchResult> DispatchAsync(string uri, CancellationToken cancellationToken);
    ValueTask<SteamDispatchResult> ContinueLaunchDialogAsync(
        SteamDispatchResult dispatch,
        CancellationToken cancellationToken);
    ValueTask<SteamDispatchResult> CancelPartialAsync(string appId, CancellationToken cancellationToken);
}

internal sealed partial class WindowsSteamClientAutomation : ISteamClientAutomation
{
    public ValueTask<SteamDispatchResult> DispatchAsync(string uri, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        if (!Uri.TryCreate(uri, UriKind.Absolute, out Uri? parsed) || parsed.Scheme != "steam")
        {
            return ValueTask.FromResult(new SteamDispatchResult(false, false));
        }
        IReadOnlySet<nint>? visibleBefore = null;
        if (uri.StartsWith("steam://rungameid/", StringComparison.Ordinal))
        {
            HashSet<nint> steamWindows = SteamWindows();
            foreach (nint window in steamWindows)
            {
                _ = ShowWindow(window, 6);
            }
            visibleBefore = steamWindows;
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

    public async ValueTask<SteamDispatchResult> ContinueLaunchDialogAsync(
        SteamDispatchResult dispatch,
        CancellationToken cancellationToken)
    {
        if (!dispatch.Accepted || dispatch.VisibleSteamWindowsBefore is null)
        {
            return new(false, dispatch.EffectObserved);
        }

        nint handle = SteamWindows().FirstOrDefault(
            static candidate => IsWindowVisible(candidate) && !IsIconic(candidate));
        if (handle == 0 || !Focus(handle))
        {
            return new(false, dispatch.EffectObserved);
        }
        await Task.Delay(150, cancellationToken).ConfigureAwait(false);
        SendVirtualKey(0x0D, false);
        SendVirtualKey(0x0D, true);
        return new(true, true);
    }

    public async ValueTask<SteamDispatchResult> CancelPartialAsync(
        string appId,
        CancellationToken cancellationToken)
    {
        SteamDispatchResult opened = await DispatchAsync("steam://open/console", cancellationToken)
            .ConfigureAwait(false);
        if (!opened.Accepted) return opened;
        await Task.Delay(1200, cancellationToken).ConfigureAwait(false);
        Process[] processes = Process.GetProcessesByName("steamwebhelper");
        nint handle = processes.Select(process => process.MainWindowHandle).FirstOrDefault(value => value != 0);
        foreach (Process process in processes) process.Dispose();
        if (handle == 0 || !SetForegroundWindow(handle))
        {
            return new(false, true);
        }
        await Task.Delay(150, cancellationToken).ConfigureAwait(false);
        if (GetForegroundWindow() != handle) return new(false, true);
        SendText("app_uninstall " + appId);
        SendVirtualKey(0x0D, false); SendVirtualKey(0x0D, true);
        return new(true, true);
    }

    private static HashSet<nint> SteamWindows()
    {
        Process[] processes = Process.GetProcessesByName("steamwebhelper");
        try
        {
            return processes
                .Select(static process => process.MainWindowHandle)
                .Where(static handle => handle != 0)
                .ToHashSet();
        }
        finally
        {
            foreach (Process process in processes)
            {
                process.Dispose();
            }
        }
    }

    private static bool Focus(nint handle)
    {
        nint foreground = GetForegroundWindow();
        uint foregroundThread = foreground == 0
            ? 0
            : GetWindowThreadProcessId(foreground, out _);
        uint currentThread = GetCurrentThreadId();
        bool attached = foregroundThread != 0
            && currentThread != foregroundThread
            && AttachThreadInput(currentThread, foregroundThread, true);
        try
        {
            _ = ShowWindow(handle, 9);
            _ = BringWindowToTop(handle);
            _ = SetForegroundWindow(handle);
            return GetForegroundWindow() == handle;
        }
        finally
        {
            if (attached)
            {
                _ = AttachThreadInput(currentThread, foregroundThread, false);
            }
        }
    }

    private static void SendText(string text)
    {
        foreach (char character in text)
        {
            SendUnicode(character, false); SendUnicode(character, true);
        }
    }

    private static void SendVirtualKey(ushort key, bool up)
    {
        Input[] input = [new() { Type = 1, Union = new InputUnion
        { Keyboard = new KeyboardInput { VirtualKey = key, Flags = up ? 2U : 0U } } }];
        if (SendInput(1, input, Marshal.SizeOf<Input>()) != 1) throw new IOException("Steam input failed.");
    }

    private static void SendUnicode(char character, bool up)
    {
        Input[] input = [new() { Type = 1, Union = new InputUnion
        { Keyboard = new KeyboardInput { ScanCode = character, Flags = 4U | (up ? 2U : 0U) } } }];
        if (SendInput(1, input, Marshal.SizeOf<Input>()) != 1) throw new IOException("Steam input failed.");
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct Input
    {
        internal uint Type;
        internal InputUnion Union;
    }

    [StructLayout(LayoutKind.Explicit)]
    private struct InputUnion
    {
        [FieldOffset(0)]
        internal KeyboardInput Keyboard;

        [FieldOffset(0)]
        internal MouseInput Mouse;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct KeyboardInput
    {
        internal ushort VirtualKey;
        internal ushort ScanCode;
        internal uint Flags;
        internal uint Time;
        internal nint ExtraInfo;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct MouseInput
    {
        internal int X;
        internal int Y;
        internal uint Data;
        internal uint Flags;
        internal uint Time;
        internal nint ExtraInfo;
    }

    [LibraryImport("user32.dll")]
    private static partial uint SendInput(uint count, Input[] inputs, int size);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool SetForegroundWindow(nint window);

    [LibraryImport("user32.dll")]
    private static partial nint GetForegroundWindow();

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
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool BringWindowToTop(nint window);
    [LibraryImport("user32.dll")]
    private static partial uint GetWindowThreadProcessId(
        nint window,
        out uint processId);
    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool AttachThreadInput(
        uint attachThread,
        uint attachToThread,
        [MarshalAs(UnmanagedType.Bool)] bool attach);

    [LibraryImport("kernel32.dll")]
    private static partial uint GetCurrentThreadId();
}
