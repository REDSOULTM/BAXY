using System.Reflection;
using System.Security.Cryptography;
using System.Text;

namespace Baxy.Core.Operations;

/// <summary>
/// FIR1 (decisión A1 del líder, 10-11-2026): the owner's signature on a release.json. GitHub's own SHA-256 of an asset only
/// says the bytes are the ones uploaded: whoever holds the account or a token uploads the file and its digest together
/// (INFORME_PRV1 §6). A release.json names every file of a version by size and SHA-256 and is signed apart, in
/// release.json.sig, with a key that never goes to GitHub (scripts/ReleaseSigning.cs), as TUF's «targets» role or a
/// minisign-signed checksum list do (theupdateframework.github.io/specification/latest, read 2026-11-10). ECDSA P-256 over
/// SHA-256 is .NET's own (learn.microsoft.com/dotnet/api/system.security.cryptography.ecdsa.verifydata, read 2026-11-10):
/// the .sig is the base64 of r||s (IEEE P1363). The keys BAXY trusts are built in (Directory.Build.props,
/// BaxyUpdateKeys): more than one only while a key is being replaced (documentacion/FIRMA_ACTUALIZACIONES.md).
/// The installer links this file (Baxy.Installer.csproj).
/// </summary>
internal static class ReleaseSignature
{
    internal const string ManifestName = "release.json";
    internal const string SignatureName = "release.json.sig";

    /// <summary>Never more than this is read of either file: a release.json of BAXY is about one kilobyte.</summary>
    internal const int ManifestLimit = 64 * 1024;

    internal const int SignatureLimit = 1024;

    private const string KeysResource = "Baxy.UpdateKeys.pem";
    private const string Begin = "-----BEGIN PUBLIC KEY-----";
    private const string End = "-----END PUBLIC KEY-----";

    /// <summary>The public keys built into this assembly; none when a build left them out (then nothing verifies).</summary>
    internal static IReadOnlyList<string> BuiltInKeys(Assembly assembly)
    {
        using Stream? resource = assembly.GetManifestResourceStream(KeysResource);
        if (resource is null)
        {
            return [];
        }

        using StreamReader reader = new(resource, Encoding.ASCII);
        return Blocks(reader.ReadToEnd());
    }

    /// <summary>Each PEM «PUBLIC KEY» block of a text, in order.</summary>
    internal static IReadOnlyList<string> Blocks(string text)
    {
        List<string> blocks = [];
        int start = 0;
        while (text.IndexOf(Begin, start, StringComparison.Ordinal) is var begin and >= 0
            && text.IndexOf(End, begin, StringComparison.Ordinal) is var end and >= 0)
        {
            blocks.Add(text[begin..(end + End.Length)]);
            start = end + End.Length;
        }

        return blocks;
    }

    /// <summary>Whether <paramref name="signature"/> (a .sig file's bytes) is one of <paramref name="keys"/> over exactly these bytes.</summary>
    internal static bool Verifies(ReadOnlySpan<byte> manifest, ReadOnlySpan<byte> signature, IReadOnlyList<string> keys)
    {
        byte[] raw;
        try
        {
            raw = Convert.FromBase64String(Encoding.ASCII.GetString(signature).Trim());
        }
        catch (FormatException)
        {
            return false;
        }

        foreach (string pem in keys)
        {
            using ECDsa key = ECDsa.Create();
            try
            {
                key.ImportFromPem(pem);
            }
            catch (Exception unreadable) when (unreadable is ArgumentException or CryptographicException)
            {
                continue;
            }

            if (key.KeySize == 256 && key.VerifyData(manifest, raw, HashAlgorithmName.SHA256))
            {
                return true;
            }
        }

        return false;
    }
}
