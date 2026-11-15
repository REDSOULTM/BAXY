using System.Globalization;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Text.RegularExpressions;

namespace Baxy.Installer;

/// <summary>
/// A zip cut into release assets (GitHub takes less than 2 GiB per file). With <see cref="GpuVendor"/> (a PCI vendor id, as
/// <see cref="MachineGpu"/> reads it) it goes only to a machine with that maker's GPU, and adds its
/// <see cref="InstalledBytes"/> to the manifest's.
/// </summary>
internal sealed record ReleaseArchive(string Name, IReadOnlyList<ReleasePart> Parts, string? GpuVendor = null, long InstalledBytes = 0)
{
    internal long Bytes => Parts.Sum(part => part.Bytes);
}

/// <summary>
/// AUT2: the license agreement a release brings, by the fingerprint the installer keeps of an accepted one
/// (<see cref="AcceptedAgreement.Of"/>). Its two texts are published beside the parts for a BAXY that asks for it by voice.
/// </summary>
internal sealed record ReleaseAgreement(string Sha256);

/// <summary>What the installer may download, embedded in it at build time: its hashes are the only ones it trusts.
/// AUT2: or a newer release's, signed, that an older installer applies (<see cref="SignedRelease.ReadAsync"/>).</summary>
internal sealed partial record ReleaseManifest(
    string Version,
    string BaseUrl,
    long InstalledBytes,
    IReadOnlyList<ReleaseArchive> Archives,
    ReleaseFiles? Files = null,
    string? InstallerMin = null,
    ReleaseAgreement? Agreement = null)
{
    internal static ReleaseManifest Parse(Stream json)
    {
        ReleaseManifest manifest = JsonSerializer.Deserialize(json, ReleaseManifestJson.Default.ReleaseManifest)
            ?? throw new InvalidDataException("release manifest is empty");
        manifest.Validate();
        return manifest;
    }

    /// <summary>What this machine downloads and installs, given its adapters. Call it once, on the manifest as parsed.</summary>
    internal ReleaseManifest ForMachine(IReadOnlyList<GpuAdapter> adapters)
    {
        ReleaseArchive[] kept = [.. Archives.Where(archive =>
            archive.GpuVendor is null || adapters.Any(adapter => MachineGpu.Vendor(adapter.DeviceId) == archive.GpuVendor))];
        return this with { InstalledBytes = InstalledBytes + kept.Sum(archive => archive.InstalledBytes), Archives = kept };
    }

    private void Validate()
    {
        // A plain address only for this machine itself: the end-to-end test of a build. The hashes rule either way.
        // UNI1 (REV8 F1): decided on the host the address goes to (RFC 3986: authority = [ userinfo "@" ] host
        // [ ":" port ]), so «http://127.0.0.1:80@example.test/», which goes to example.test, is not this machine.
        bool trusted = Uri.TryCreate(BaseUrl, UriKind.Absolute, out Uri? address) && address.UserInfo.Length == 0 &&
            (address.Scheme == Uri.UriSchemeHttps ||
             (address.Scheme == Uri.UriSchemeHttp && address.Host == "127.0.0.1" &&
              BaseUrl.StartsWith("http://127.0.0.1:", StringComparison.Ordinal)));
        if (string.IsNullOrWhiteSpace(Version) || !trusted || !BaseUrl.EndsWith('/') || InstalledBytes <= 0 ||
            Archives is null || Archives.Count == 0)
        {
            throw new InvalidDataException("release manifest: version, base address or size is not valid");
        }

        // AUT1: files.json, when the release names one (FileManifest).
        if (Files is not null && (Files.File is null || !AssetName().IsMatch(Files.File) || Files.Bytes <= 0
            || Files.Sha256 is null || !Hash().IsMatch(Files.Sha256)))
        {
            throw new InvalidDataException("release manifest: its file manifest is not valid");
        }

        // AUT2: the oldest installer that applies this release, and the agreement's fingerprint, when it names them.
        if ((InstallerMin is not null && Numbers(InstallerMin) is null)
            || (Agreement is not null && (Agreement.Sha256 is null || !Hash().IsMatch(Agreement.Sha256))))
        {
            throw new InvalidDataException("release manifest: its installer minimum or its agreement is not valid");
        }

        foreach (ReleaseArchive archive in Archives)
        {
            if (archive.Parts is null || archive.Parts.Count == 0 || archive.InstalledBytes < 0 ||
                (archive.GpuVendor is not null && !GpuVendorId().IsMatch(archive.GpuVendor)))
            {
                throw new InvalidDataException($"release manifest: archive {archive.Name} is not valid");
            }

            foreach (ReleasePart part in archive.Parts)
            {
                if (!AssetName().IsMatch(part.File) || part.Bytes <= 0 || !Hash().IsMatch(part.Sha256))
                {
                    throw new InvalidDataException($"release manifest: part {part.File} is not valid");
                }
            }
        }
    }

    /// <summary>A version as release.json writes it (1.5.3); null when it is not one.</summary>
    internal static Version? Numbers(string? text)
    {
        string[] numbers = (text ?? string.Empty).Split('+', '-')[0].Split('.');
        return numbers.Length == 3 && numbers.All(static number => number.Length is > 0 and < 6 && number.All(char.IsAsciiDigit))
            ? new Version(int.Parse(numbers[0], CultureInfo.InvariantCulture), int.Parse(numbers[1], CultureInfo.InvariantCulture),
                int.Parse(numbers[2], CultureInfo.InvariantCulture))
            : null;
    }

    [GeneratedRegex(@"^[A-Za-z0-9][A-Za-z0-9._-]*$")]
    private static partial Regex AssetName();

    [GeneratedRegex("^[0-9a-f]{64}$")]
    private static partial Regex Hash();

    [GeneratedRegex("^[0-9a-f]{4}$")]
    private static partial Regex GpuVendorId();
}

[JsonSourceGenerationOptions(PropertyNamingPolicy = JsonKnownNamingPolicy.CamelCase)]
[JsonSerializable(typeof(ReleaseManifest))]
[JsonSerializable(typeof(FileManifest))]
internal sealed partial class ReleaseManifestJson : JsonSerializerContext;
