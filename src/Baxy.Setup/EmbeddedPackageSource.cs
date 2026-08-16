using System.Reflection;
using System.Text.Json;

namespace Baxy.Setup;

public static class EmbeddedPackageSource
{
    public static Stream OpenPayload(Assembly? assembly = null)
    {
        Assembly sourceAssembly = assembly ?? typeof(EmbeddedPackageSource).Assembly;
        return sourceAssembly.GetManifestResourceStream(PackageContract.EmbeddedPackageResourceName) ??
            throw new ProductPackageException("The embedded BAXY payload resource is missing.");
    }

    public static VerifiedProductPackage Verify(
        ProductPackageVerifier? verifier = null,
        Assembly? assembly = null)
    {
        Assembly sourceAssembly = assembly ?? typeof(EmbeddedPackageSource).Assembly;
        using Stream payload = OpenPayload(sourceAssembly);
        using Stream attestationStream = sourceAssembly.GetManifestResourceStream(
            PackageContract.EmbeddedPackageAttestationResourceName) ??
            throw new ProductPackageException("The embedded BAXY package attestation resource is missing.");
        if (attestationStream.Length is <= 0 or > 4096)
        {
            throw new ProductPackageException("The embedded package attestation has an invalid length.");
        }

        byte[] attestationBytes = new byte[checked((int)attestationStream.Length)];
        attestationStream.ReadExactly(attestationBytes);
        return VerifyStreams(payload, attestationBytes, verifier ?? new ProductPackageVerifier());
    }

    internal static VerifiedProductPackage VerifyStreams(
        Stream payload,
        byte[] attestationBytes,
        ProductPackageVerifier verifier)
    {
        EmbeddedPackageAttestation attestation = ReadAttestation(attestationBytes);
        VerifiedProductPackage package = verifier.Verify(payload);
        if (attestation.DataSchema != package.DataSchema ||
            !string.Equals(attestation.Version, package.Version, StringComparison.Ordinal) ||
            !string.Equals(attestation.PackageSha256, package.PackageSha256, StringComparison.Ordinal) ||
            attestation.PackageBytes != package.PackageLength ||
            !string.Equals(attestation.ManifestSha256, package.ManifestSha256, StringComparison.Ordinal) ||
            !string.Equals(attestation.ContentId, package.ContentId, StringComparison.Ordinal) ||
            attestation.SourceDateEpoch != package.SourceDateEpoch ||
            !string.Equals(attestation.Commit, package.Commit, StringComparison.Ordinal))
        {
            throw new ProductPackageException("The embedded package does not match its canonical attestation.");
        }

        return package;
    }

    internal static byte[] CreateCanonicalAttestation(VerifiedProductPackage package)
    {
        EmbeddedPackageAttestation attestation = new()
        {
            DataSchema = package.DataSchema,
            Version = package.Version,
            PackageSha256 = package.PackageSha256,
            PackageBytes = package.PackageLength,
            ManifestSha256 = package.ManifestSha256,
            ContentId = package.ContentId,
            SourceDateEpoch = package.SourceDateEpoch,
            Commit = package.Commit,
        };
        byte[] json = JsonSerializer.SerializeToUtf8Bytes(
            attestation,
            SetupJsonContext.Default.EmbeddedPackageAttestation);
        byte[] durable = new byte[json.Length + 1];
        json.CopyTo(durable, 0);
        durable[^1] = (byte)'\n';
        return durable;
    }

    public static void WriteVerificationEvidence(string path, VerifiedProductPackage package)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(path);
        ArgumentNullException.ThrowIfNull(package);
        if (!Path.IsPathFullyQualified(path) || File.Exists(path) || Directory.Exists(path))
        {
            throw new InstallationSafetyException("The verification evidence path must be a new absolute file path.");
        }

        string fullPath = Path.GetFullPath(path);
        string? parent = Path.GetDirectoryName(fullPath);
        string leaf = Path.GetFileName(path);
        if (parent is null || !Directory.Exists(parent))
        {
            throw new InstallationSafetyException("The verification evidence parent directory must already exist.");
        }

        try
        {
            PathSafety.ValidateRelativePath(leaf);
        }
        catch (ProductPackageException exception)
        {
            throw new InstallationSafetyException("The verification evidence filename is unsafe on Windows.", exception);
        }

        PathSafety.AssertExistingChainHasNoReparsePoint(parent);
        EmbeddedVerificationEvidence evidence = new()
        {
            DataSchema = package.DataSchema,
            Version = package.Version,
            PackageSha256 = package.PackageSha256,
            PackageBytes = package.PackageLength,
            ManifestSha256 = package.ManifestSha256,
            ContentId = package.ContentId,
            SourceDateEpoch = package.SourceDateEpoch,
            Commit = package.Commit,
        };
        byte[] json = JsonSerializer.SerializeToUtf8Bytes(
            evidence,
            SetupJsonContext.Default.EmbeddedVerificationEvidence);
        using FileStream stream = new(fullPath, new FileStreamOptions
        {
            Mode = FileMode.CreateNew,
            Access = FileAccess.Write,
            Share = FileShare.None,
            BufferSize = 4096,
            Options = FileOptions.WriteThrough,
        });
        stream.Write(json);
        stream.WriteByte((byte)'\n');
        stream.Flush(flushToDisk: true);
        stream.Dispose();
        PathSafety.AssertRegularFile(fullPath);
    }

    private static EmbeddedPackageAttestation ReadAttestation(byte[] bytes)
    {
        if (bytes.Length >= 3 && bytes[0] == 0xef && bytes[1] == 0xbb && bytes[2] == 0xbf)
        {
            throw new ProductPackageException("UTF-8 BOM is forbidden in the embedded package attestation.");
        }

        try
        {
            using JsonDocument document = JsonDocument.Parse(bytes);
            string[] expected =
            [
                "schema", "version", "data_schema", "package_sha256", "package_bytes", "manifest_sha256", "content_id",
                "source_date_epoch", "commit",
            ];
            int index = 0;
            foreach (JsonProperty property in document.RootElement.EnumerateObject())
            {
                if (index >= expected.Length || !string.Equals(property.Name, expected[index], StringComparison.Ordinal))
                {
                    throw new ProductPackageException("The embedded package attestation property set is non-canonical.");
                }

                index++;
            }

            if (index != expected.Length)
            {
                throw new ProductPackageException("The embedded package attestation property set is incomplete.");
            }

            EmbeddedPackageAttestation? attestation = JsonSerializer.Deserialize(
                bytes,
                SetupJsonContext.Default.EmbeddedPackageAttestation);
            if (attestation is null ||
                !string.Equals(attestation.Schema, PackageContract.EmbeddedPackageAttestationSchema, StringComparison.Ordinal) ||
                attestation.DataSchema != PackageContract.DataSchema ||
                string.IsNullOrWhiteSpace(attestation.Version) ||
                !IsLowerHex(attestation.PackageSha256) || attestation.PackageBytes is <= 0 or > PackageContract.MaximumPackageBytes ||
                !IsLowerHex(attestation.ManifestSha256) || !IsLowerHex(attestation.ContentId) ||
                attestation.SourceDateEpoch < 0 || !IsLowerHex(attestation.Commit, 40))
            {
                throw new ProductPackageException("The embedded package attestation contains an invalid or null value.");
            }

            byte[] canonical = JsonSerializer.SerializeToUtf8Bytes(
                attestation,
                SetupJsonContext.Default.EmbeddedPackageAttestation);
            if (bytes.Length != canonical.Length + 1 || bytes[^1] != (byte)'\n' ||
                !bytes.AsSpan(0, canonical.Length).SequenceEqual(canonical))
            {
                throw new ProductPackageException("The embedded package attestation is not canonical JSON.");
            }

            return attestation;
        }
        catch (ProductPackageException)
        {
            throw;
        }
        catch (Exception exception) when (exception is JsonException or InvalidOperationException or IOException)
        {
            throw new ProductPackageException("The embedded package attestation is malformed.", exception);
        }
    }

    private static bool IsLowerHex(string? value, int length = 64)
    {
        if (value is null || value.Length != length)
        {
            return false;
        }

        return value.All(static character => character is >= '0' and <= '9' or >= 'a' and <= 'f');
    }
}
