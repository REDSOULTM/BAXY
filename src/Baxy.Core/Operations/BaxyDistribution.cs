using System.IO.Compression;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace Baxy.Core.Operations;

/// <summary>
/// Where this BAXY came from (actualizar-ordenes-app, 2026-11-09). The folder BAXY runs from is the one
/// scripts/build_steam.ps1 builds for the three places it is published: Steam's depot as it is, itch.io's upload as it is
/// (documentacion/itchio/EMPAQUETADO.md) and GitHub's installer, which cuts it into zips (scripts/build_github_release.py).
/// Each packager writes <see cref="FileName"/> beside <c>app\</c> with its channel, so every store's own integrity check
/// covers it: the SHA-256 of each part in the installer's manifest, Steam's file validation and itch.io's signature. No
/// file (py main.py, a build of this machine) is a development BAXY, which no store updates.
/// </summary>
internal sealed partial record BaxyDistribution(string Channel, string Root, string? Repository)
{
    internal const string FileName = "distribution.json";
    internal const string Schema = "baxy.distribution.v1";
    internal const string GitHub = "github";
    internal const string Steam = "steam";
    internal const string Itch = "itch";
    internal const string Development = "development";

    /// <summary>The distribution of the product baxy-core.exe running from <paramref name="coreFolder"/> belongs to: it is
    /// published into app\core (scripts/build_product.ps1, CoreProcessClient), so its app folder is the one above (AMD2: read
    /// from its own folder, every installed BAXY said «development»).</summary>
    internal static BaxyDistribution OfCore(string coreFolder) => Read(Path.Combine(coreFolder, ".."));

    /// <summary>The distribution of the product the folder <paramref name="appFolder"/> (where Baxy.exe is) belongs to.</summary>
    internal static BaxyDistribution Read(string appFolder)
    {
        string root = Path.GetFullPath(Path.Combine(appFolder, ".."));
        string marker = Path.Combine(root, FileName);
        try
        {
            using FileStream file = File.OpenRead(marker);
            using JsonDocument document = JsonDocument.Parse(file);
            JsonElement value = document.RootElement;
            string? channel = Text(value, "channel");
            string? repository = Text(value, "repository");
            if (Text(value, "schema") != Schema || channel is not (GitHub or Steam or Itch))
            {
                return new BaxyDistribution(Development, root, null);
            }

            // GitHub's owner/name, the only thing the address of its latest release is built from.
            return new BaxyDistribution(
                channel, root, channel == GitHub && repository is not null && RepositoryName().IsMatch(repository) ? repository : null);
        }
        catch (Exception unreadable) when (unreadable is IOException or UnauthorizedAccessException or JsonException)
        {
            return new BaxyDistribution(Development, root, null);
        }
    }

    /// <summary>
    /// The game's page on itch.io, from the receipt the itch app writes into every folder it installs
    /// (<c>.itch\receipt.json.gz</c>); null without one or with an address that is not itch.io's.
    /// </summary>
    internal Uri? ItchPage()
    {
        try
        {
            using FileStream file = File.OpenRead(Path.Combine(Root, ".itch", "receipt.json.gz"));
            using GZipStream unzipped = new(file, CompressionMode.Decompress);
            using JsonDocument receipt = JsonDocument.Parse(unzipped);
            return receipt.RootElement.ValueKind == JsonValueKind.Object
                && receipt.RootElement.TryGetProperty("game", out JsonElement game)
                && Text(game, "url") is { } url
                && Uri.TryCreate(url, UriKind.Absolute, out Uri? page)
                && page.Scheme == Uri.UriSchemeHttps
                && (page.Host == "itch.io" || page.Host.EndsWith(".itch.io", StringComparison.OrdinalIgnoreCase))
                    ? page
                    : null;
        }
        catch (Exception unreadable) when (unreadable is IOException or UnauthorizedAccessException or JsonException
            or InvalidDataException)
        {
            return null;
        }
    }

    private static string? Text(JsonElement value, string name) =>
        value.ValueKind == JsonValueKind.Object && value.TryGetProperty(name, out JsonElement named)
        && named.ValueKind == JsonValueKind.String
            ? named.GetString()
            : null;

    [GeneratedRegex("^[A-Za-z0-9-]{1,39}/[A-Za-z0-9._-]{1,100}$")]
    private static partial Regex RepositoryName();
}
