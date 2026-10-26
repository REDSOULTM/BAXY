using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using Microsoft.Win32;

namespace Baxy.Providers.Windows.External;

internal sealed class WindowsGameInstallationAdapter : IExternalOperationAdapter
{
    private readonly string[] _steamAppsRoots;
    private readonly string[] _epicManifestRoots;

    internal WindowsGameInstallationAdapter()
        : this(DiscoverSteamAppsRoots(), DiscoverEpicManifestRoots())
    {
    }

    internal WindowsGameInstallationAdapter(
        IEnumerable<string> steamAppsRoots,
        IEnumerable<string> epicManifestRoots)
    {
        _steamAppsRoots = CanonicalRoots(steamAppsRoots);
        _epicManifestRoots = CanonicalRoots(epicManifestRoots);
    }

    public bool CanHandle(string operation) => operation == "game.installed.named";

    public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        try
        {
            string title = ExternalJson.RequiredString(arguments, "title");
            string provider = arguments.TryGetProperty("provider", out JsonElement value)
                && value.ValueKind == JsonValueKind.String
                    ? value.GetString() ?? "any"
                    : "any";
            if (provider is not ("any" or "epic" or "steam")
                || Encoding.UTF8.GetByteCount(title) > 256)
            {
                return ValueTask.FromResult(ExternalJson.Failure(
                    operation, "game_installation_query_invalid"));
            }

            string foldedTitle = Fold(title);
            var matches = new List<InstalledGame>();
            // Renew al máximo (auditoría de flujos, decision2): every name read, for the closest ones when none matches.
            var read = new List<string>();
            // Renew al máximo (w8): one manifest that could not be read (locked while its store rewrites it, a corrupt
            // .item) failed game_installation_inventory_failed for every title, both stores; it is left aside and counted.
            var unread = new List<string>();
            if (provider is "any" or "steam")
                matches.AddRange(ReadSteamGames(foldedTitle, read, unread));
            if (provider is "any" or "epic")
                matches.AddRange(ReadEpicGames(foldedTitle, read, unread));

            InstalledGame[] distinct = matches
                .GroupBy(game => game.Provider + "\n" + game.Identity, StringComparer.Ordinal)
                .Select(group => group.First())
                .OrderBy(game => game.Provider, StringComparer.Ordinal)
                .ThenBy(game => game.Title, StringComparer.OrdinalIgnoreCase)
                .ToArray();
            JsonElement result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteString("query", title);
                writer.WriteString("provider", provider);
                // Ronda final: what is read is the Steam and Epic manifests by the exact name; none named so is not «not
                // installed» (another name, another store), so only a match says installed.
                // Ronda final 32 (regla 3): only a finished install says installed; one still downloading says so.
                if (distinct.Any(game => game.Complete == true))
                    writer.WriteBoolean("installed", true);
                else if (distinct.Any(game => game.Complete is null))
                    writer.WriteString("state", "install_state_not_read");
                else if (distinct.Length > 0)
                    writer.WriteString("state", "install_not_finished");
                // A manifest not read may be the game's: with one, no name found is not said.
                else if (unread.Count > 0)
                    writer.WriteString("state", "install_state_not_read");
                else
                {
                    writer.WriteString("state", "no_steam_or_epic_manifest_with_that_name");
                    SteamLocalAdapter.WriteClosest(writer, SteamLocalAdapter.ClosestTitles(title, read));
                }
                if (unread.Count > 0)
                    writer.WriteNumber("manifestsUnread", unread.Count);
                writer.WriteNumber("matchCount", distinct.Length);
                writer.WriteStartArray("games");
                foreach (InstalledGame game in distinct)
                {
                    writer.WriteStartObject();
                    writer.WriteString("provider", game.Provider);
                    writer.WriteString("title", game.Title);
                    writer.WriteString("gameId", OpaqueId(game.Provider, game.Identity));
                    writer.WriteString("manifestSha256", game.ManifestSha256);
                    writer.WriteBoolean("installDirectoryPresent", true);
                    if (game.Complete is { } finished)
                        writer.WriteBoolean("installFinished", finished);
                    writer.WriteEndObject();
                }
                writer.WriteEndArray();
                writer.WriteString(
                    "authority", "steam_epic_manifests_install_directory_postread");
                writer.WriteEndObject();
            });
            return ValueTask.FromResult(ExternalJson.Success(
                operation, result, effectObserved: false));
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException or JsonException or InvalidOperationException)
        {
            return ValueTask.FromResult(ExternalJson.Failure(
                operation, "game_installation_inventory_failed"));
        }
    }

    // One manifest's text, or null (counted in «unread») when it cannot be read now.
    private static string? ReadManifest(string manifest, List<string> unread)
    {
        try
        {
            return File.ReadAllText(manifest);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            unread.Add(manifest);
            return null;
        }
    }

    private IEnumerable<InstalledGame> ReadSteamGames(string foldedTitle, List<string> read, List<string> unread)
    {
        foreach (string steamAppsRoot in _steamAppsRoots.Where(Directory.Exists))
        {
            foreach (string manifest in Directory.EnumerateFiles(
                steamAppsRoot, "appmanifest_*.acf", SearchOption.TopDirectoryOnly))
            {
                if (ReadManifest(manifest, unread) is not { } content)
                    continue;
                string name = AcfValue(content, "name");
                string installDirectory = AcfValue(content, "installdir");
                string appId = AcfValue(content, "appid");
                if (string.IsNullOrWhiteSpace(name)
                    || string.IsNullOrWhiteSpace(installDirectory)
                    || !Directory.Exists(Path.Combine(
                        steamAppsRoot, "common", installDirectory)))
                {
                    continue;
                }
                read.Add(name);
                if (!TitleMatches(Fold(name), foldedTitle))
                {
                    continue;
                }
                // Ronda final 32 (regla 3): a manifest without Steam's FullyInstalled flag (4) is an install still
                // queued or downloading, whose folder already exists: never «installed».
                // Ronda final 33: StateFlags missing or unreadable is the state not read, never «not finished».
                bool? complete = ulong.TryParse(AcfValue(content, "StateFlags"), out ulong flags)
                    ? (flags & 4UL) != 0
                    : null;
                yield return new InstalledGame(
                    "steam", name, appId.Length > 0 ? appId : manifest,
                    Sha256File(manifest), complete);
            }
        }
    }

    private IEnumerable<InstalledGame> ReadEpicGames(string foldedTitle, List<string> read, List<string> unread)
    {
        foreach (string manifestRoot in _epicManifestRoots.Where(Directory.Exists))
        {
            foreach (string manifest in Directory.EnumerateFiles(
                manifestRoot, "*.item", SearchOption.TopDirectoryOnly))
            {
                JsonDocument document;
                try
                {
                    if (ReadManifest(manifest, unread) is not { } text)
                        continue;
                    document = JsonDocument.Parse(text);
                }
                catch (JsonException)
                {
                    unread.Add(manifest);
                    continue;
                }

                using JsonDocument parsed = document;
                JsonElement root = parsed.RootElement;
                if (root.ValueKind != JsonValueKind.Object)
                {
                    unread.Add(manifest);
                    continue;
                }
                string name = JsonString(root, "DisplayName");
                string installLocation = JsonString(root, "InstallLocation");
                string identity = JsonString(root, "CatalogItemId");
                if (identity.Length == 0) identity = JsonString(root, "AppName");
                if (string.IsNullOrWhiteSpace(name)
                    || string.IsNullOrWhiteSpace(installLocation)
                    || !Directory.Exists(installLocation))
                {
                    continue;
                }
                read.Add(name);
                if (!TitleMatches(Fold(name), foldedTitle))
                {
                    continue;
                }
                // Ronda final 32 (regla 3): Epic marks an install not finished yet (bIsIncompleteInstall), as
                // SteamLocalAdapter already reads it for its own Epic checks.
                bool incomplete = root.TryGetProperty("bIsIncompleteInstall", out JsonElement unfinished)
                    && unfinished.ValueKind == JsonValueKind.True;
                yield return new InstalledGame(
                    "epic", name, identity.Length > 0 ? identity : manifest,
                    Sha256File(manifest), !incomplete);
            }
        }
    }

    private static string[] DiscoverSteamAppsRoots()
    {
        var steamRoots = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        AddRegistrySteamRoot(steamRoots, Registry.CurrentUser, @"Software\Valve\Steam");
        AddRegistrySteamRoot(steamRoots, Registry.LocalMachine, @"SOFTWARE\WOW6432Node\Valve\Steam");
        string programFiles = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86);
        if (programFiles.Length > 0) steamRoots.Add(Path.Combine(programFiles, "Steam"));

        var libraryRoots = new HashSet<string>(steamRoots, StringComparer.OrdinalIgnoreCase);
        foreach (string steamRoot in steamRoots.ToArray())
        {
            string libraryFile = Path.Combine(steamRoot, "steamapps", "libraryfolders.vdf");
            if (!File.Exists(libraryFile)) continue;
            string content = File.ReadAllText(libraryFile);
            foreach (Match match in Regex.Matches(
                content, "\\\"path\\\"\\s+\\\"([^\\\"]+)\\\"",
                RegexOptions.CultureInvariant))
            {
                libraryRoots.Add(match.Groups[1].Value.Replace("\\\\", "\\"));
            }
        }
        return libraryRoots.Select(root => Path.Combine(root, "steamapps")).ToArray();
    }

    private static string[] DiscoverEpicManifestRoots()
    {
        string common = Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData);
        return common.Length == 0
            ? []
            : [Path.Combine(common, "Epic", "EpicGamesLauncher", "Data", "Manifests")];
    }

    private static void AddRegistrySteamRoot(
        HashSet<string> roots,
        RegistryKey hive,
        string keyName)
    {
        using RegistryKey? key = hive.OpenSubKey(keyName);
        string? value = key?.GetValue("SteamPath") as string
            ?? key?.GetValue("InstallPath") as string;
        if (!string.IsNullOrWhiteSpace(value)) roots.Add(value);
    }

    private static string[] CanonicalRoots(IEnumerable<string> roots) => roots
        .Where(root => !string.IsNullOrWhiteSpace(root))
        .Select(Path.GetFullPath)
        .Distinct(StringComparer.OrdinalIgnoreCase)
        .ToArray();

    private static string AcfValue(string content, string key)
    {
        Match match = Regex.Match(
            content, "\\\"" + Regex.Escape(key) + "\\\"\\s+\\\"([^\\\"]*)\\\"",
            RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
        return match.Success ? match.Groups[1].Value : string.Empty;
    }

    private static string JsonString(JsonElement element, string property) =>
        element.TryGetProperty(property, out JsonElement value)
        && value.ValueKind == JsonValueKind.String
            ? value.GetString() ?? string.Empty
            : string.Empty;

    // The game the model named, folded for case, accents and punctuation, and nothing else: «Portal» is not
    // «Portal 2» (BAXY Renew audit 2026-10-15).
    private static bool TitleMatches(string candidate, string requested) => candidate == requested;

    // Renew al máximo (w8): the same fold as Steam's own titles (SteamLocalAdapter.FoldTitle: an apostrophe joins its
    // word, a word's final «s» is left aside), so both stores match a title as it is said.
    private static string Fold(string value) => SteamLocalAdapter.FoldTitle(value);

    private static string OpaqueId(string provider, string identity) => provider + "_"
        + Convert.ToHexStringLower(SHA256.HashData(
            Encoding.UTF8.GetBytes(identity)))[..24];

    private static string Sha256File(string path) => Convert.ToHexStringLower(
        SHA256.HashData(File.ReadAllBytes(path)));

    private sealed record InstalledGame(
        string Provider,
        string Title,
        string Identity,
        string ManifestSha256,
        bool? Complete);
}
