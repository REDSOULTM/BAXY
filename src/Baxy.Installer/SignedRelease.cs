using System.Diagnostics;
using System.Globalization;
using System.Net;
using System.Reflection;
using System.Text.Json;
using Baxy.Core.Operations;

namespace Baxy.Installer;

/// <summary>Where the parts come from, release.json is missing, not signed with a key this installer trusts, or not its own.</summary>
internal sealed class UnsignedReleaseException(string message) : Exception(message);

/// <summary>The folder holds a newer BAXY than the one this installer brings: it is not replaced by an older one.</summary>
internal sealed class OlderReleaseException(string installed, string offered)
    : Exception($"the folder holds BAXY {installed}, newer than {offered}")
{
    internal string Installed { get; } = installed;

    internal string Offered { get; } = offered;
}

/// <summary>
/// FIR1 (decisión A1 del líder, 10-11-2026). Before anything is downloaded or installed (Windows' prerequisites included),
/// the release.json published where the parts are, with its signature (<see cref="ReleaseSignature"/>), must be signed with
/// a key built into this installer and be exactly the manifest it carries: the same version, address and parts, by size and
/// SHA-256. A release whose files were swapped on GitHub, or an old release.json signed for real, installs nothing; and a
/// folder holding a newer BAXY is not replaced by an older one, with --update or without (TUF calls it a rollback attack:
/// theupdateframework.github.io/specification/latest, «Detailed client workflow», «Check for a rollback attack», read
/// 2026-11-10). Only memory is used until then: nothing is left behind.
/// </summary>
internal static class SignedRelease
{
    internal static IReadOnlyList<string> BuiltInKeys => ReleaseSignature.BuiltInKeys(Assembly.GetExecutingAssembly());

    internal static async Task ConfirmAsync(
        HttpClient http, ReleaseManifest carried, InstallPaths paths, IReadOnlyList<string> keys, CancellationToken cancellation)
    {
        if (InstalledVersion(paths.App) is { } installed && Numbers(carried.Version) is { } offered && installed > offered)
        {
            throw new OlderReleaseException(installed.ToString(3), offered.ToString(3));
        }

        Uri from = new(carried.BaseUrl);
        byte[]? manifest = await SmallAsync(http, new Uri(from, ReleaseSignature.ManifestName), ReleaseSignature.ManifestLimit, cancellation)
            .ConfigureAwait(false);
        byte[]? signature = await SmallAsync(http, new Uri(from, ReleaseSignature.SignatureName), ReleaseSignature.SignatureLimit, cancellation)
            .ConfigureAwait(false);
        if (manifest is null || signature is null)
        {
            throw new UnsignedReleaseException($"{from}{ReleaseSignature.SignatureName} is not published");
        }

        if (!ReleaseSignature.Verifies(manifest, signature, keys))
        {
            throw new UnsignedReleaseException("release.json is not signed with BAXY's key");
        }

        ReleaseManifest signed;
        try
        {
            using MemoryStream json = new(manifest);
            signed = ReleaseManifest.Parse(json);
        }
        catch (Exception unreadable) when (unreadable is InvalidDataException or JsonException)
        {
            throw new UnsignedReleaseException($"the signed release.json is not valid: {unreadable.Message}");
        }

        if (!Same(carried, signed))
        {
            throw new UnsignedReleaseException($"the signed release.json is {signed.Version}'s, not the one of this installer ({carried.Version})");
        }
    }

    // The version of the BAXY in that folder, from its exe (1.3.2+<commit>); null when there is none.
    internal static Version? InstalledVersion(string app) =>
        File.Exists(app) ? Numbers(FileVersionInfo.GetVersionInfo(app).ProductVersion) : null;

    private static Version? Numbers(string? text)
    {
        string[] numbers = (text ?? string.Empty).Split('+', '-')[0].Split('.');
        return numbers.Length >= 3
            && int.TryParse(numbers[0], NumberStyles.None, CultureInfo.InvariantCulture, out int major)
            && int.TryParse(numbers[1], NumberStyles.None, CultureInfo.InvariantCulture, out int minor)
            && int.TryParse(numbers[2], NumberStyles.None, CultureInfo.InvariantCulture, out int patch)
            ? new Version(major, minor, patch)
            : null;
    }

    private static bool Same(ReleaseManifest carried, ReleaseManifest signed) =>
        carried.Version == signed.Version && carried.BaseUrl == signed.BaseUrl && carried.InstalledBytes == signed.InstalledBytes
        && carried.Archives.Count == signed.Archives.Count
        && carried.Archives.Zip(signed.Archives).All(pair =>
            pair.First.Name == pair.Second.Name && pair.First.GpuVendor == pair.Second.GpuVendor
            && pair.First.InstalledBytes == pair.Second.InstalledBytes && pair.First.Parts.SequenceEqual(pair.Second.Parts));

    // A small file, whole and never longer than its limit; null when the server says it is not there or it is too long.
    private static async Task<byte[]?> SmallAsync(HttpClient http, Uri address, int limit, CancellationToken cancellation)
    {
        using CancellationTokenSource within = CancellationTokenSource.CreateLinkedTokenSource(cancellation);
        within.CancelAfter(PartFetcher.StallLimit);
        using HttpResponseMessage response = await http.GetAsync(address, HttpCompletionOption.ResponseHeadersRead, within.Token)
            .ConfigureAwait(false);
        if (response.StatusCode == HttpStatusCode.NotFound)
        {
            return null;
        }

        response.EnsureSuccessStatusCode();
        await using Stream body = await response.Content.ReadAsStreamAsync(within.Token).ConfigureAwait(false);
        using MemoryStream kept = new();
        byte[] buffer = new byte[4096];
        for (int read; (read = await body.ReadAsync(buffer, within.Token).ConfigureAwait(false)) > 0;)
        {
            if (kept.Length + read > limit)
            {
                return null;
            }

            kept.Write(buffer, 0, read);
        }

        return kept.ToArray();
    }
}
