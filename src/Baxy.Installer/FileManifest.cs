using System.Security.Cryptography;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace Baxy.Installer;

/// <summary>
/// One file of the release: what it must be (size and SHA-256) and where its bytes are in the archive's parts, taken as
/// one zip: <see cref="Packed"/> bytes from <see cref="Offset"/>, stored (0) or deflated (8). The data of a zip entry
/// follows its local header (PKWARE APPNOTE.TXT 4.3.7 and 4.3.8), so one file can be read alone.
/// </summary>
internal sealed record ReleaseFile(string Path, long Bytes, string Sha256, string Archive, long Offset, long Packed, int Method)
{
    internal const int Stored = 0;
    internal const int Deflated = 8;
}

/// <summary>files.json as release.json names it: signed with it, by size and SHA-256.</summary>
internal sealed record ReleaseFiles(string File, long Bytes, string Sha256);

/// <summary>
/// AUT1 (orden del dueño, 13-11-2026: «Debe instalar solamente lo necesario […] No debe volver a descargar nada que ya
/// exista»). files.json (scripts/build_github_release.py): every file of the release by size and SHA-256, the way the
/// update frameworks list their targets (TUF, «TARGETS»: a path with its length and hashes, under a signature,
/// theupdateframework.github.io/specification/latest, read 2026-11-13). The installer carries it, and it counts only when
/// it is the one its release.json names by SHA-256, which is what the owner's key signs (<see cref="SignedRelease"/>).
/// </summary>
internal sealed partial record FileManifest(string Version, IReadOnlyList<ReleaseFile> Files)
{
    internal static FileManifest Parse(Stream json)
    {
        FileManifest manifest = JsonSerializer.Deserialize(json, ReleaseManifestJson.Default.FileManifest)
            ?? throw new InvalidDataException("file manifest is empty");
        manifest.Validate();
        return manifest;
    }

    /// <summary>
    /// The file manifest in <paramref name="carried"/> when it is the one <paramref name="release"/> names, for that
    /// version; else null, and the installer takes the parts whole as it always did.
    /// </summary>
    internal static FileManifest? Named(byte[]? carried, ReleaseManifest release)
    {
        if (carried is null || release.Files is not { } named || carried.LongLength != named.Bytes
            || Convert.ToHexStringLower(SHA256.HashData(carried)) != named.Sha256)
        {
            return null;
        }

        try
        {
            using MemoryStream json = new(carried);
            FileManifest manifest = Parse(json);
            return manifest.Version == release.Version ? manifest : null;
        }
        catch (Exception unreadable) when (unreadable is InvalidDataException or JsonException)
        {
            Program.Log("files.json is not valid: " + unreadable.Message);
            return null;
        }
    }

    private void Validate()
    {
        if (string.IsNullOrWhiteSpace(Version) || Files is null)
        {
            throw new InvalidDataException("file manifest: no version or no files");
        }

        foreach (ReleaseFile file in Files)
        {
            // A path of the installation, never outside it: plain segments with «/», as the zip names its entries.
            bool inside = !string.IsNullOrEmpty(file.Path) && !file.Path.Contains('\\', StringComparison.Ordinal)
                && !file.Path.Contains(':', StringComparison.Ordinal)
                && file.Path.Split('/').All(static segment => segment.Length > 0 && segment is not ("." or ".."));
            bool placed = file.Method == ReleaseFile.Stored ? file.Packed == file.Bytes : file.Method == ReleaseFile.Deflated;
            if (!inside || !placed || file.Bytes < 0 || file.Packed < 0 || file.Offset <= 0
                || file.Sha256 is null || !Hash().IsMatch(file.Sha256) || file.Archive is null || !AssetName().IsMatch(file.Archive))
            {
                throw new InvalidDataException($"file manifest: {file.Path} is not valid");
            }
        }
    }

    [GeneratedRegex(@"^[A-Za-z0-9][A-Za-z0-9._-]*$")]
    private static partial Regex AssetName();

    [GeneratedRegex("^[0-9a-f]{64}$")]
    private static partial Regex Hash();
}
