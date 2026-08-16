using System.Text.Json.Serialization;

namespace Baxy.Setup;

internal sealed class BuildManifest
{
    [JsonPropertyName("schema")]
    public string Schema { get; init; } = string.Empty;

    [JsonPropertyName("product")]
    public string Product { get; init; } = string.Empty;

    [JsonPropertyName("version")]
    public string Version { get; init; } = string.Empty;

    [JsonPropertyName("data_schema")]
    public int DataSchema { get; init; } = PackageContract.DataSchema;

    [JsonPropertyName("configuration")]
    public string Configuration { get; init; } = string.Empty;

    [JsonPropertyName("runtime")]
    public string Runtime { get; init; } = string.Empty;

    [JsonPropertyName("target_framework")]
    public string TargetFramework { get; init; } = string.Empty;

    [JsonPropertyName("authenticity")]
    public string Authenticity { get; init; } = string.Empty;

    [JsonPropertyName("source")]
    public BuildSource Source { get; init; } = new();

    [JsonPropertyName("toolchain")]
    public BuildToolchain Toolchain { get; init; } = new();

    [JsonPropertyName("deployment")]
    public BuildDeployment Deployment { get; init; } = new();

    [JsonPropertyName("file_count")]
    public int FileCount { get; init; }

    [JsonPropertyName("total_bytes")]
    public long TotalBytes { get; init; }

    [JsonPropertyName("files")]
    public BuildFileRecord[] Files { get; init; } = [];
}

internal sealed class BuildSource
{
    [JsonPropertyName("commit")]
    public string Commit { get; init; } = string.Empty;

    [JsonPropertyName("dirty")]
    public bool Dirty { get; init; }

    [JsonPropertyName("provenance")]
    public string Provenance { get; init; } = string.Empty;

    [JsonPropertyName("source_date_epoch")]
    public long SourceDateEpoch { get; init; }
}

internal sealed class BuildToolchain
{
    [JsonPropertyName("dotnet_sdk")]
    public string DotnetSdk { get; init; } = string.Empty;

    [JsonPropertyName("powershell")]
    public string PowerShell { get; init; } = string.Empty;
}

internal sealed class BuildDeployment
{
    [JsonPropertyName("app")]
    public string App { get; init; } = string.Empty;

    [JsonPropertyName("native_libraries")]
    public string NativeLibraries { get; init; } = string.Empty;

    [JsonPropertyName("core")]
    public string Core { get; init; } = string.Empty;

    [JsonPropertyName("symbols")]
    public string Symbols { get; init; } = string.Empty;
}

internal sealed class BuildFileRecord
{
    [JsonPropertyName("path")]
    public string Path { get; init; } = string.Empty;

    [JsonPropertyName("bytes")]
    public long Bytes { get; init; }

    [JsonPropertyName("sha256")]
    public string Sha256 { get; init; } = string.Empty;
}

internal sealed class InstalledVersionAttestation
{
    [JsonPropertyName("schema")]
    public string Schema { get; init; } = PackageContract.VersionAttestationSchema;

    [JsonPropertyName("version")]
    public string Version { get; init; } = string.Empty;

    [JsonPropertyName("data_schema")]
    public int DataSchema { get; init; } = PackageContract.DataSchema;

    [JsonPropertyName("package_sha256")]
    public string PackageSha256 { get; init; } = string.Empty;

    [JsonPropertyName("manifest_sha256")]
    public string ManifestSha256 { get; init; } = string.Empty;

    [JsonPropertyName("content_id")]
    public string ContentId { get; init; } = string.Empty;
}

internal sealed class InstallationPointer
{
    [JsonPropertyName("schema")]
    public string Schema { get; init; } = PackageContract.PointerSchema;

    [JsonPropertyName("version")]
    public string Version { get; init; } = string.Empty;

    [JsonPropertyName("data_schema")]
    public int DataSchema { get; init; } = PackageContract.DataSchema;

    [JsonPropertyName("package_sha256")]
    public string PackageSha256 { get; init; } = string.Empty;

    [JsonPropertyName("manifest_sha256")]
    public string ManifestSha256 { get; init; } = string.Empty;

    [JsonPropertyName("content_id")]
    public string ContentId { get; init; } = string.Empty;
}

internal sealed class EmbeddedPackageAttestation
{
    [JsonPropertyName("schema")]
    public string Schema { get; init; } = PackageContract.EmbeddedPackageAttestationSchema;

    [JsonPropertyName("version")]
    public string Version { get; init; } = string.Empty;

    [JsonPropertyName("data_schema")]
    public int DataSchema { get; init; } = PackageContract.DataSchema;

    [JsonPropertyName("package_sha256")]
    public string PackageSha256 { get; init; } = string.Empty;

    [JsonPropertyName("package_bytes")]
    public long PackageBytes { get; init; }

    [JsonPropertyName("manifest_sha256")]
    public string ManifestSha256 { get; init; } = string.Empty;

    [JsonPropertyName("content_id")]
    public string ContentId { get; init; } = string.Empty;

    [JsonPropertyName("source_date_epoch")]
    public long SourceDateEpoch { get; init; }

    [JsonPropertyName("commit")]
    public string Commit { get; init; } = string.Empty;
}

internal sealed class InstallTransaction
{
    [JsonPropertyName("schema")]
    public string Schema { get; init; } = PackageContract.TransactionSchema;

    [JsonPropertyName("transaction_id")]
    public string TransactionId { get; init; } = string.Empty;

    [JsonPropertyName("staging_id")]
    public string? StagingId { get; init; }

    [JsonPropertyName("operation")]
    public string Operation { get; init; } = string.Empty;

    [JsonPropertyName("phase")]
    public string Phase { get; init; } = string.Empty;

    [JsonPropertyName("target")]
    public InstallationPointer? Target { get; init; }

    [JsonPropertyName("before_current")]
    public InstallationPointer? BeforeCurrent { get; init; }
}

internal sealed class EmbeddedVerificationEvidence
{
    [JsonPropertyName("schema")]
    public string Schema { get; init; } = PackageContract.EmbeddedVerificationEvidenceSchema;

    [JsonPropertyName("status")]
    public string Status { get; init; } = "passed";

    [JsonPropertyName("version")]
    public string Version { get; init; } = string.Empty;

    [JsonPropertyName("data_schema")]
    public int DataSchema { get; init; } = PackageContract.DataSchema;

    [JsonPropertyName("package_sha256")]
    public string PackageSha256 { get; init; } = string.Empty;

    [JsonPropertyName("package_bytes")]
    public long PackageBytes { get; init; }

    [JsonPropertyName("manifest_sha256")]
    public string ManifestSha256 { get; init; } = string.Empty;

    [JsonPropertyName("content_id")]
    public string ContentId { get; init; } = string.Empty;

    [JsonPropertyName("source_date_epoch")]
    public long SourceDateEpoch { get; init; }

    [JsonPropertyName("commit")]
    public string Commit { get; init; } = string.Empty;
}

internal sealed record VerifiedEntry(
    string Path,
    long Length,
    string Sha256,
    uint Crc32,
    long DataOffset,
    ushort DosTime,
    ushort DosDate);

public sealed class VerifiedProductPackage
{
    internal VerifiedProductPackage(
        int dataSchema,
        string version,
        string packageSha256,
        string manifestSha256,
        string contentId,
        string commit,
        long packageLength,
        long sourceDateEpoch,
        IReadOnlyList<VerifiedEntry> entries)
    {
        DataSchema = dataSchema;
        Version = version;
        PackageSha256 = packageSha256;
        ManifestSha256 = manifestSha256;
        ContentId = contentId;
        Commit = commit;
        PackageLength = packageLength;
        SourceDateEpoch = sourceDateEpoch;
        Entries = entries;
    }

    public int DataSchema { get; }

    public string Version { get; }

    public string PackageSha256 { get; }

    public string ManifestSha256 { get; }

    public string ContentId { get; }

    public string Commit { get; }

    public long PackageLength { get; }

    public long SourceDateEpoch { get; }

    internal IReadOnlyList<VerifiedEntry> Entries { get; }
}

internal sealed record VerifiedInstalledVersion(
    int DataSchema,
    string Version,
    string PackageSha256,
    string ManifestSha256,
    string ContentId);
