using System.Globalization;
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
            if (provider is "any" or "steam")
                matches.AddRange(ReadSteamGames(foldedTitle));
            if (provider is "any" or "epic")
                matches.AddRange(ReadEpicGames(foldedTitle));

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
                writer.WriteBoolean("installed", distinct.Length > 0);
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

    private IEnumerable<InstalledGame> ReadSteamGames(string foldedTitle)
    {
        foreach (string steamAppsRoot in _steamAppsRoots.Where(Directory.Exists))
        {
            foreach (string manifest in Directory.EnumerateFiles(
                steamAppsRoot, "appmanifest_*.acf", SearchOption.TopDirectoryOnly))
            {
                string content = File.ReadAllText(manifest);
                string name = AcfValue(content, "name");
                string installDirectory = AcfValue(content, "installdir");
                string appId = AcfValue(content, "appid");
                if (string.IsNullOrWhiteSpace(name)
                    || !TitleMatches(Fold(name), foldedTitle)
                    || string.IsNullOrWhiteSpace(installDirectory)
                    || !Directory.Exists(Path.Combine(
                        steamAppsRoot, "common", installDirectory)))
                {
                    continue;
                }
                yield return new InstalledGame(
                    "steam", name, appId.Length > 0 ? appId : manifest,
                    Sha256File(manifest));
            }
        }
    }

    private IEnumerable<InstalledGame> ReadEpicGames(string foldedTitle)
    {
        foreach (string manifestRoot in _epicManifestRoots.Where(Directory.Exists))
        {
            foreach (string manifest in Directory.EnumerateFiles(
                manifestRoot, "*.item", SearchOption.TopDirectoryOnly))
            {
                using JsonDocument document = JsonDocument.Parse(File.ReadAllText(manifest));
                JsonElement root = document.RootElement;
                string name = JsonString(root, "DisplayName");
                string installLocation = JsonString(root, "InstallLocation");
                string identity = JsonString(root, "CatalogItemId");
                if (identity.Length == 0) identity = JsonString(root, "AppName");
                if (string.IsNullOrWhiteSpace(name)
                    || !TitleMatches(Fold(name), foldedTitle)
                    || string.IsNullOrWhiteSpace(installLocation)
                    || !Directory.Exists(installLocation))
                {
                    continue;
                }
                yield return new InstalledGame(
                    "epic", name, identity.Length > 0 ? identity : manifest,
                    Sha256File(manifest));
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

    private static bool TitleMatches(string candidate, string requested) =>
        candidate == requested
        || candidate.Contains(requested, StringComparison.Ordinal)
        || requested.Contains(candidate, StringComparison.Ordinal);

    private static string Fold(string value)
    {
        string normalized = value.Normalize(NormalizationForm.FormD);
        var builder = new StringBuilder(normalized.Length);
        foreach (char character in normalized)
        {
            if (CharUnicodeInfo.GetUnicodeCategory(character) == UnicodeCategory.NonSpacingMark)
                continue;
            builder.Append(char.IsLetterOrDigit(character)
                ? char.ToLowerInvariant(character)
                : ' ');
        }
        return string.Join(' ', builder.ToString().Split(
            ' ', StringSplitOptions.RemoveEmptyEntries));
    }

    private static string OpaqueId(string provider, string identity) => provider + "_"
        + Convert.ToHexStringLower(SHA256.HashData(
            Encoding.UTF8.GetBytes(identity)))[..24];

    private static string Sha256File(string path) => Convert.ToHexStringLower(
        SHA256.HashData(File.ReadAllBytes(path)));

    private sealed record InstalledGame(
        string Provider,
        string Title,
        string Identity,
        string ManifestSha256);
}
