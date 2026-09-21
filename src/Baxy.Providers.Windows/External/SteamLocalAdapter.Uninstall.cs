using System.Text;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

/// <summary>
/// Auditoría semántica 2026-09-20 (REOPEN1993 grupo S, D11): «Desinstala Worms
/// Rumble en Steam» (H0039, H0612, H0620) es una desinstalación real: el
/// título se resuelve a su AppID instalado, la consola de Steam recibe
/// <c>app_uninstall</c> y el manifiesto local deja de decir «instalado».
/// Nada se compra ni se descarga; lo que no está instalado se dice.
/// </summary>
internal sealed partial class SteamLocalAdapter
{
    private const int UninstallObservationIntervals = 90;

    private async ValueTask<ExternalCapabilityReceipt> UninstallNamedAsync(
        string operation,
        JsonElement arguments,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        string title = ExternalJson.RequiredString(arguments, "title");
        string store = arguments.TryGetProperty("store", out JsonElement named)
            && named.ValueKind == JsonValueKind.String ? named.GetString() ?? "steam" : "steam";
        if (store == "epic")
            return ExternalJson.FailureBeforeEffect(operation, "epic_uninstall_not_supported");
        string folded = FoldTitle(title);
        string? appId = KnownTitleAppIds.TryGetValue(folded, out string? known)
            ? known
            : ResolveSnapshotTitle(folded);
        if (appId is null)
            return ExternalJson.FailureBeforeEffect(operation, "steam_title_not_resolved");
        SteamLocalGame? before = _snapshot().SingleOrDefault(candidate => candidate.AppId == appId);
        if (before is null || !before.Installed)
            return ExternalJson.FailureBeforeEffect(operation, "steam_game_not_installed");

        effectBoundary.Cross(cancellationToken);
        // La consola de Steam ya desinstala descargas parciales (game.install.cancel);
        // la misma orden quita un juego instalado.
        SteamDispatchResult dispatch = await _automation.CancelPartialAsync(appId, cancellationToken)
            .ConfigureAwait(false);
        if (!dispatch.Accepted)
            return effectBoundary.Failure(operation, "steam_uninstall_dispatch_rejected", dispatch.EffectObserved);

        for (int observation = 0; observation <= UninstallObservationIntervals; observation++)
        {
            SteamLocalGame? after = _snapshot().SingleOrDefault(candidate => candidate.AppId == appId);
            if (after is null || !after.Installed)
            {
                JsonElement result = ExternalJson.Create(writer =>
                {
                    writer.WriteStartObject(); writer.WriteNumber("version", 1);
                    writer.WriteString("appId", appId); writer.WriteString("name", before.Name);
                    writer.WriteBoolean("removed", true);
                    writer.WriteString("state", after is null ? "manifest_removed" : "manifest_not_installed");
                    writer.WriteString("authority", "steam_local_appmanifest_absence_postread"); writer.WriteEndObject();
                });
                return ExternalJson.Success(operation, result, effectObserved: true);
            }

            if (observation < UninstallObservationIntervals)
                await _delay(ObservationInterval, cancellationToken).ConfigureAwait(false);
        }

        return effectBoundary.Failure(operation, "steam_uninstall_not_verified", effectObserved: true);
    }

    // Epic: el lanzador acepta un enlace de instalación con el espacio de nombres,
    // el id de catálogo y el nombre de app del título; la descarga se ve nacer
    // como un manifiesto incompleto en su carpeta de manifiestos.
    private async ValueTask<ExternalCapabilityReceipt> EpicInstallNamedAsync(
        string operation,
        string title,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        string folded = FoldTitle(title);
        string catalogCache = Path.Combine(EpicLauncherDataRoot, "Catalog", "catcache.bin");
        string manifests = Path.Combine(EpicLauncherDataRoot, "Manifests");
        if (!File.Exists(catalogCache))
            return ExternalJson.FailureBeforeEffect(operation, "epic_launcher_data_not_found");
        string? catalogItemId = null;
        string? ns = null;
        string? appName = null;
        string? displayTitle = null;
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

                    displayTitle = itemTitle.GetString();
                    catalogItemId = item.TryGetProperty("id", out JsonElement id) && id.ValueKind == JsonValueKind.String ? id.GetString() : null;
                    ns = item.TryGetProperty("namespace", out JsonElement space) && space.ValueKind == JsonValueKind.String ? space.GetString() : null;
                    if (item.TryGetProperty("releaseInfo", out JsonElement releases) && releases.ValueKind == JsonValueKind.Array)
                    {
                        foreach (JsonElement release in releases.EnumerateArray())
                        {
                            if (release.ValueKind == JsonValueKind.Object
                                && release.TryGetProperty("appId", out JsonElement releaseApp)
                                && releaseApp.ValueKind == JsonValueKind.String)
                            {
                                appName = releaseApp.GetString();
                                break;
                            }
                        }
                    }

                    break;
                }
            }
        }
        catch (Exception exception) when (exception is FormatException or JsonException or IOException)
        {
            return ExternalJson.FailureBeforeEffect(operation, "epic_launcher_data_not_found");
        }

        if (catalogItemId is null)
            return ExternalJson.FailureBeforeEffect(operation, "epic_entitlement_not_verified");
        if (IsEpicInstalled(manifests, catalogItemId))
        {
            JsonElement installed = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject(); writer.WriteNumber("version", 1);
                writer.WriteString("appId", catalogItemId); writer.WriteString("name", displayTitle ?? title);
                writer.WriteString("store", "epic"); writer.WriteString("state", "already_installed");
                writer.WriteString("authority", "epic_launcher_local_manifest"); writer.WriteEndObject();
            });
            return ExternalJson.Success(operation, installed, effectObserved: false);
        }

        if (ns is null || appName is null)
            return ExternalJson.FailureBeforeEffect(operation, "epic_install_link_not_resolved");
        string link = "com.epicgames.launcher://apps/" + Uri.EscapeDataString(ns + ":" + catalogItemId + ":" + appName) + "?action=install&silent=true";
        effectBoundary.Cross(cancellationToken);
        SteamDispatchResult dispatch = await _automation.DispatchAsync(link, cancellationToken).ConfigureAwait(false);
        if (!dispatch.Accepted)
            return effectBoundary.Failure(operation, "epic_install_dispatch_rejected", dispatch.EffectObserved);
        for (int observation = 0; observation <= InstallObservationIntervals; observation++)
        {
            if (Directory.Exists(manifests) && EpicManifestExists(manifests, catalogItemId))
            {
                JsonElement result = ExternalJson.Create(writer =>
                {
                    writer.WriteStartObject(); writer.WriteNumber("version", 1);
                    writer.WriteString("appId", catalogItemId); writer.WriteString("name", displayTitle ?? title);
                    writer.WriteString("store", "epic"); writer.WriteString("state", "downloading");
                    writer.WriteString("authority", "epic_launcher_manifest_transition"); writer.WriteEndObject();
                });
                return ExternalJson.Success(operation, result, effectObserved: true);
            }

            if (observation < InstallObservationIntervals)
                await _delay(ObservationInterval, cancellationToken).ConfigureAwait(false);
        }

        return effectBoundary.Failure(operation, "epic_install_not_verified", effectObserved: true);
    }

    private static bool IsEpicInstalled(string manifests, string catalogItemId) =>
        Directory.Exists(manifests) && Directory.EnumerateFiles(manifests, "*.item").Any(file =>
        {
            try
            {
                using JsonDocument document = JsonDocument.Parse(File.ReadAllText(file, Encoding.UTF8));
                JsonElement root = document.RootElement;
                return root.ValueKind == JsonValueKind.Object
                    && root.TryGetProperty("CatalogItemId", out JsonElement id)
                    && id.ValueKind == JsonValueKind.String
                    && string.Equals(id.GetString(), catalogItemId, StringComparison.OrdinalIgnoreCase)
                    && !(root.TryGetProperty("bIsIncompleteInstall", out JsonElement incomplete)
                        && incomplete.ValueKind == JsonValueKind.True);
            }
            catch (Exception exception) when (exception is JsonException or IOException)
            {
                return false;
            }
        });

    private static bool EpicManifestExists(string manifests, string catalogItemId) =>
        Directory.EnumerateFiles(manifests, "*.item").Any(file =>
        {
            try
            {
                using JsonDocument document = JsonDocument.Parse(File.ReadAllText(file, Encoding.UTF8));
                JsonElement root = document.RootElement;
                return root.ValueKind == JsonValueKind.Object
                    && root.TryGetProperty("CatalogItemId", out JsonElement id)
                    && id.ValueKind == JsonValueKind.String
                    && string.Equals(id.GetString(), catalogItemId, StringComparison.OrdinalIgnoreCase);
            }
            catch (Exception exception) when (exception is JsonException or IOException)
            {
                return false;
            }
        });
}
