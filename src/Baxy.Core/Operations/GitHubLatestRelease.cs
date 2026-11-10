using System.Globalization;
using System.Net.Http.Headers;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace Baxy.Core.Operations;

/// <summary>The installer of a release as GitHub lists it: where it downloads, its size and the SHA-256 GitHub computed.</summary>
internal sealed record ReleaseInstaller(Uri Download, long Bytes, string Sha256);

/// <summary>A GitHub release: its version (from its tag), its page and its installer, when it has one with a digest.</summary>
internal sealed record LatestRelease(Version Version, string Tag, Uri? Page, ReleaseInstaller? Installer);

/// <summary>
/// GitHub's latest release of a repository: «the most recent non-prerelease, non-draft release» (REST API, Get the latest
/// release, https://docs.github.com/en/rest/releases/releases, read 2026-11-09), so a prerelease is never offered. Each
/// asset carries «digest»: «sha256:…», the SHA-256 GitHub computes for every uploaded asset since 2025-06-03
/// (https://github.blog/changelog/2025-06-03-releases-now-expose-digests-for-release-assets/); v1.3.1 of BAXY has it.
/// Only this request goes out: the repository's name and BAXY's version in the user agent, nothing of the person.
/// </summary>
internal static partial class GitHubLatestRelease
{
    internal const string InstallerName = "BAXY-Instalador.exe";

    internal static async Task<LatestRelease?> ReadAsync(
        HttpClient http, string repository, string userAgent, CancellationToken cancellationToken)
    {
        using HttpRequestMessage request = new(HttpMethod.Get, $"https://api.github.com/repos/{repository}/releases/latest");
        request.Headers.Accept.Add(new MediaTypeWithQualityHeaderValue("application/vnd.github+json"));
        request.Headers.Add("X-GitHub-Api-Version", "2022-11-28");
        request.Headers.UserAgent.ParseAdd(userAgent);
        using HttpResponseMessage response = await http.SendAsync(request, cancellationToken).ConfigureAwait(false);
        if (!response.IsSuccessStatusCode)
        {
            return null;
        }

        await using Stream body = await response.Content.ReadAsStreamAsync(cancellationToken).ConfigureAwait(false);
        using JsonDocument document = await JsonDocument.ParseAsync(body, cancellationToken: cancellationToken)
            .ConfigureAwait(false);
        return Parse(document.RootElement);
    }

    /// <summary>The release as BAXY trusts it; null for a draft, a prerelease or a tag that is not a version.</summary>
    internal static LatestRelease? Parse(JsonElement release)
    {
        if (release.ValueKind != JsonValueKind.Object
            || Flag(release, "draft") || Flag(release, "prerelease")
            || Text(release, "tag_name") is not { } tag
            || ParseVersion(tag) is not { } version)
        {
            return null;
        }

        Uri? page = Https(Text(release, "html_url"));
        ReleaseInstaller? installer = null;
        if (release.TryGetProperty("assets", out JsonElement assets) && assets.ValueKind == JsonValueKind.Array)
        {
            foreach (JsonElement asset in assets.EnumerateArray())
            {
                if (Text(asset, "name") == InstallerName
                    && Https(Text(asset, "browser_download_url")) is { } download
                    && asset.TryGetProperty("size", out JsonElement size) && size.TryGetInt64(out long bytes) && bytes > 0
                    && Text(asset, "digest") is { } digest && Digest().Match(digest) is { Success: true } sha)
                {
                    installer = new ReleaseInstaller(download, bytes, sha.Groups[1].Value.ToLowerInvariant());
                }
            }
        }

        return new LatestRelease(version, tag, page, installer);
    }

    /// <summary>The first three numbers of a version as BAXY writes it: «v1.3.2», «1.3.2», «1.3.2+abc1234.dirty».</summary>
    internal static Version? ParseVersion(string? text)
    {
        Match match = text is null ? Match.Empty : SemVer().Match(text);
        return match.Success
            ? new Version(
                int.Parse(match.Groups[1].Value, CultureInfo.InvariantCulture),
                int.Parse(match.Groups[2].Value, CultureInfo.InvariantCulture),
                int.Parse(match.Groups[3].Value, CultureInfo.InvariantCulture))
            : null;
    }

    private static Uri? Https(string? address) =>
        Uri.TryCreate(address, UriKind.Absolute, out Uri? uri) && uri.Scheme == Uri.UriSchemeHttps
        && (uri.Host == "github.com" || uri.Host.EndsWith(".github.com", StringComparison.OrdinalIgnoreCase))
            ? uri
            : null;

    private static bool Flag(JsonElement value, string name) =>
        value.TryGetProperty(name, out JsonElement flag) && flag.ValueKind == JsonValueKind.True;

    private static string? Text(JsonElement value, string name) =>
        value.TryGetProperty(name, out JsonElement named) && named.ValueKind == JsonValueKind.String ? named.GetString() : null;

    [GeneratedRegex(@"^v?(\d{1,5})\.(\d{1,5})\.(\d{1,5})(?:[-+].*)?$")]
    private static partial Regex SemVer();

    [GeneratedRegex("^sha256:([0-9a-fA-F]{64})$")]
    private static partial Regex Digest();
}
