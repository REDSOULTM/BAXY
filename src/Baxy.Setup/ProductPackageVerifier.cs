using System.Buffers;
using System.Globalization;
using System.Diagnostics.CodeAnalysis;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Baxy.Setup;

public sealed class ProductPackageVerifier
{
    private static readonly UTF8Encoding StrictUtf8 = new(false, true);

    [SuppressMessage("Performance", "CA1822:Mark members as static", Justification = "Verifier instances are injectable installation services.")]
    public VerifiedProductPackage Verify(Stream packageStream)
    {
        ArgumentNullException.ThrowIfNull(packageStream);
        try
        {
            IReadOnlyList<StoredZipEntry> storedEntries = StoredZipReader.Read(packageStream);
            AssertExactZipPaths(storedEntries);

            Dictionary<string, byte[]> metadata = new(StringComparer.Ordinal);
            List<VerifiedEntry> verifiedEntries = new(storedEntries.Count);
            foreach (StoredZipEntry storedEntry in storedEntries)
            {
                bool capture = storedEntry.Path is "build-manifest.json" or "SHA256SUMS";
                int captureLimit = storedEntry.Path == "build-manifest.json"
                    ? PackageContract.MaximumManifestBytes
                    : PackageContract.MaximumChecksumBytes;
                if (capture && storedEntry.Length > captureLimit)
                {
                    throw new ProductPackageException($"Package metadata exceeds its reviewed limit: {storedEntry.Path}");
                }

                EntryDigest digest = DigestEntry(packageStream, storedEntry, capture);
                if (digest.Crc32 != storedEntry.Crc32)
                {
                    throw new ProductPackageException($"ZIP CRC32 does not match entry bytes: {storedEntry.Path}");
                }

                if (digest.Bytes is not null)
                {
                    metadata.Add(storedEntry.Path, digest.Bytes);
                }

                verifiedEntries.Add(new VerifiedEntry(
                    storedEntry.Path,
                    storedEntry.Length,
                    digest.Sha256,
                    digest.Crc32,
                    storedEntry.DataOffset,
                    storedEntry.DosTime,
                    storedEntry.DosDate));
            }

            byte[] manifestBytes = metadata["build-manifest.json"];
            byte[] checksumBytes = metadata["SHA256SUMS"];
            BuildManifest manifest = ValidateManifest(manifestBytes);
            AssertPackageTimestamp(verifiedEntries, manifest.Source.SourceDateEpoch);
            ValidateManifestAgainstEntries(manifest, verifiedEntries);
            ValidateChecksums(checksumBytes, verifiedEntries);

            string packageSha256 = DigestWholeStream(packageStream);
            string manifestSha256 = verifiedEntries.Single(
                static entry => entry.Path == "build-manifest.json").Sha256;
            string contentId = ComputeContentId(verifiedEntries);
            return new VerifiedProductPackage(
                manifest.DataSchema,
                manifest.Version,
                packageSha256,
                manifestSha256,
                contentId,
                manifest.Source.Commit,
                packageStream.Length,
                manifest.Source.SourceDateEpoch,
                verifiedEntries);
        }
        catch (ProductPackageException)
        {
            throw;
        }
        catch (Exception exception) when (
            exception is EndOfStreamException or InvalidDataException or IOException or
            OverflowException or JsonException or DecoderFallbackException or CryptographicException)
        {
            throw new ProductPackageException("The product package is truncated, malformed, or unreadable.", exception);
        }
        finally
        {
            if (packageStream.CanSeek)
            {
                packageStream.Position = 0;
            }
        }
    }

    [SuppressMessage("Performance", "CA1822:Mark members as static", Justification = "Verifier instances are injectable installation services.")]
    internal void ExtractVerified(
        Stream packageStream,
        VerifiedProductPackage verifiedPackage,
        string installationRoot,
        string destinationRoot)
    {
        ArgumentNullException.ThrowIfNull(packageStream);
        ArgumentNullException.ThrowIfNull(verifiedPackage);
        if (!packageStream.CanRead || !packageStream.CanSeek || packageStream.Length != verifiedPackage.PackageLength ||
            !string.Equals(DigestWholeStream(packageStream), verifiedPackage.PackageSha256, StringComparison.Ordinal))
        {
            throw new ProductPackageException("The extraction stream is not the previously verified package.");
        }

        string rootFull = Path.GetFullPath(installationRoot).TrimEnd(Path.DirectorySeparatorChar);
        string destinationFull = Path.GetFullPath(destinationRoot).TrimEnd(Path.DirectorySeparatorChar);
        if (!destinationFull.StartsWith(rootFull + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase) ||
            Directory.Exists(destinationFull) || File.Exists(destinationFull))
        {
            throw new InstallationSafetyException("The extraction destination must be a new strict descendant of the installation root.");
        }

        bool destinationCreated = false;
        try
        {
            PathSafety.EnsureOwnedDirectory(rootFull, destinationFull);
            destinationCreated = true;
            foreach (VerifiedEntry entry in verifiedPackage.Entries)
            {
                string destination = PathSafety.GetStrictDescendantPath(destinationFull, entry.Path);
                string? parent = Path.GetDirectoryName(destination);
                if (parent is null)
                {
                    throw new InstallationSafetyException("An extracted file has no owned parent directory.");
                }

                PathSafety.EnsureOwnedDirectory(rootFull, parent);
                CopyVerifiedEntry(packageStream, entry, destination);
            }

            VerifyExtractedPackageDirectory(destinationFull, verifiedPackage);
        }
        catch
        {
            if (destinationCreated && Directory.Exists(destinationFull))
            {
                PathSafety.DeleteTreeFailClosed(rootFull, destinationFull);
            }

            throw;
        }
        finally
        {
            packageStream.Position = 0;
        }
    }

    [SuppressMessage("Performance", "CA1822:Mark members as static", Justification = "Verifier instances are injectable installation services.")]
    internal void WriteVersionAttestation(string versionRoot, VerifiedProductPackage package)
    {
        InstalledVersionAttestation attestation = new()
        {
            DataSchema = package.DataSchema,
            Version = package.Version,
            PackageSha256 = package.PackageSha256,
            ManifestSha256 = package.ManifestSha256,
            ContentId = package.ContentId,
        };
        byte[] bytes = SerializeDurable(attestation, SetupJsonContext.Default.InstalledVersionAttestation);
        string path = Path.Combine(versionRoot, ".baxy-version.json");
        WriteNewDurableFile(path, bytes);
        PathSafety.AssertRegularFile(path);
    }

    [SuppressMessage("Performance", "CA1822:Mark members as static", Justification = "Verifier instances are injectable installation services.")]
    internal VerifiedInstalledVersion VerifyInstalledVersion(string versionRoot)
    {
        SafeFileTree tree = PathSafety.InspectTree(versionRoot);
        if (!tree.Directories.SequenceEqual(PackageContract.DirectoryPaths, StringComparer.Ordinal))
        {
            throw new InstallationSafetyException("An installed version has an unexpected directory set.");
        }

        string[] expectedFiles = [.. PackageContract.ZipPaths, ".baxy-version.json"];
        Array.Sort(expectedFiles, StringComparer.Ordinal);
        if (!tree.Files.SequenceEqual(expectedFiles, StringComparer.Ordinal))
        {
            throw new InstallationSafetyException("An installed version contains missing or unexpected files.");
        }

        List<VerifiedEntry> entries = new(PackageContract.ZipPaths.Length);
        Dictionary<string, byte[]> metadata = new(StringComparer.Ordinal);
        long installedBytes = 0;
        foreach (string relativePath in PackageContract.ZipPaths)
        {
            string path = PathSafety.GetStrictDescendantPath(versionRoot, relativePath);
            FileInfo info = new(path);
            if (info.Length > PackageContract.MaximumPayloadFileBytes)
            {
                throw new InstallationSafetyException($"An installed file exceeds its reviewed size limit: {relativePath}");
            }

            installedBytes = checked(installedBytes + info.Length);
            if (installedBytes > PackageContract.MaximumPackageBytes)
            {
                throw new InstallationSafetyException("The installed version exceeds the reviewed aggregate byte limit.");
            }

            byte[]? captured = relativePath switch
            {
                "build-manifest.json" when info.Length <= PackageContract.MaximumManifestBytes => File.ReadAllBytes(path),
                "SHA256SUMS" when info.Length <= PackageContract.MaximumChecksumBytes => File.ReadAllBytes(path),
                "build-manifest.json" or "SHA256SUMS" => throw new InstallationSafetyException(
                    $"Installed metadata exceeds its reviewed limit: {relativePath}"),
                _ => null,
            };
            string sha256 = DigestFile(path);
            entries.Add(new VerifiedEntry(relativePath, info.Length, sha256, 0, 0, 0, 0));
            if (captured is not null)
            {
                metadata.Add(relativePath, captured);
            }
        }

        BuildManifest manifest = ValidateManifest(metadata["build-manifest.json"]);
        ValidateManifestAgainstEntries(manifest, entries);
        ValidateChecksums(metadata["SHA256SUMS"], entries);
        string contentId = ComputeContentId(entries);
        string manifestSha256 = entries.Single(static entry => entry.Path == "build-manifest.json").Sha256;

        string attestationPath = Path.Combine(versionRoot, ".baxy-version.json");
        InstalledVersionAttestation attestation = ReadVersionAttestation(attestationPath);
        if (attestation.DataSchema != manifest.DataSchema ||
            !string.Equals(attestation.Version, manifest.Version, StringComparison.Ordinal) ||
            !string.Equals(attestation.ManifestSha256, manifestSha256, StringComparison.Ordinal) ||
            !string.Equals(attestation.ContentId, contentId, StringComparison.Ordinal))
        {
            throw new InstallationSafetyException("The installed-version attestation does not match installed bytes.");
        }

        return new VerifiedInstalledVersion(
            attestation.DataSchema,
            attestation.Version,
            attestation.PackageSha256,
            attestation.ManifestSha256,
            attestation.ContentId);
    }

    private static void AssertExactZipPaths(IReadOnlyList<StoredZipEntry> entries)
    {
        if (entries.Count != PackageContract.ZipPaths.Length)
        {
            throw new ProductPackageException(
                $"The product ZIP must contain exactly {PackageContract.ZipPaths.Length} reviewed files.");
        }

        for (int index = 0; index < PackageContract.ZipPaths.Length; index++)
        {
            if (!string.Equals(entries[index].Path, PackageContract.ZipPaths[index], StringComparison.Ordinal))
            {
                throw new ProductPackageException($"Unexpected product ZIP path: {entries[index].Path}");
            }
        }
    }

    private static BuildManifest ValidateManifest(byte[] bytes)
    {
        AssertUtf8WithoutBom(bytes, "build-manifest.json");
        using JsonDocument document = JsonDocument.Parse(bytes, new JsonDocumentOptions
        {
            AllowTrailingCommas = false,
            CommentHandling = JsonCommentHandling.Disallow,
            MaxDepth = 12,
        });
        AssertPropertySequence(document.RootElement,
        [
            "schema", "product", "version", "data_schema", "configuration", "runtime", "target_framework",
            "authenticity", "source", "toolchain", "deployment", "file_count", "total_bytes", "files",
        ], "build manifest");

        AssertPropertySequence(document.RootElement.GetProperty("source"),
            ["commit", "dirty", "provenance", "source_date_epoch"], "build manifest source");
        AssertPropertySequence(document.RootElement.GetProperty("toolchain"),
            ["dotnet_sdk", "powershell"], "build manifest toolchain");
        AssertPropertySequence(document.RootElement.GetProperty("deployment"),
            ["app", "native_libraries", "core", "symbols"], "build manifest deployment");

        JsonElement filesElement = document.RootElement.GetProperty("files");
        if (filesElement.ValueKind != JsonValueKind.Array || filesElement.GetArrayLength() != PackageContract.PayloadPaths.Length)
        {
            throw new ProductPackageException("The build manifest file array has an unexpected shape.");
        }

        foreach (JsonElement record in filesElement.EnumerateArray())
        {
            AssertPropertySequence(record, ["path", "bytes", "sha256"], "build manifest file record");
        }

        BuildManifest? manifest = JsonSerializer.Deserialize(bytes, SetupJsonContext.Default.BuildManifest);
        if (manifest is null)
        {
            throw new ProductPackageException("The build manifest JSON is null.");
        }

        ValidateManifestValues(manifest);
        byte[] canonical = JsonSerializer.SerializeToUtf8Bytes(manifest, SetupJsonContext.Default.BuildManifest);
        if (!bytes.AsSpan().SequenceEqual(canonical))
        {
            throw new ProductPackageException("build-manifest.json is not canonical v4 JSON.");
        }

        return manifest;
    }

    private static void ValidateManifestValues(BuildManifest manifest)
    {
        if (manifest.Source is null || manifest.Toolchain is null || manifest.Deployment is null || manifest.Files is null ||
            manifest.Files.Any(static record => record is null))
        {
            throw new ProductPackageException("The build manifest contains a null object or file record.");
        }

        if (!string.Equals(manifest.Schema, PackageContract.ManifestSchema, StringComparison.Ordinal) ||
            manifest.DataSchema != PackageContract.DataSchema ||
            !string.Equals(manifest.Product, PackageContract.Product, StringComparison.Ordinal) ||
            !string.Equals(manifest.Configuration, PackageContract.Configuration, StringComparison.Ordinal) ||
            !string.Equals(manifest.Runtime, PackageContract.Runtime, StringComparison.Ordinal) ||
            !string.Equals(manifest.TargetFramework, PackageContract.TargetFramework, StringComparison.Ordinal) ||
            !string.Equals(manifest.Authenticity, PackageContract.Authenticity, StringComparison.Ordinal))
        {
            throw new ProductPackageException("The build manifest is not the reviewed BAXY Release win-x64 contract.");
        }

        if (!SemanticVersionComparer.IsValid(manifest.Version))
        {
            throw new ProductPackageException("The build manifest semantic version is invalid.");
        }

        if (!IsLowerHex(manifest.Source.Commit, 40) || manifest.Source.Dirty ||
            !string.Equals(manifest.Source.Provenance, PackageContract.SourceProvenance, StringComparison.Ordinal) ||
            manifest.Source.SourceDateEpoch < 0)
        {
            throw new ProductPackageException("The build manifest source is not a clean Git HEAD snapshot.");
        }

        if (string.IsNullOrWhiteSpace(manifest.Toolchain.DotnetSdk) ||
            string.IsNullOrWhiteSpace(manifest.Toolchain.PowerShell))
        {
            throw new ProductPackageException("The build manifest toolchain is incomplete.");
        }

        if (!string.Equals(manifest.Deployment.App, "self_contained_single_file", StringComparison.Ordinal) ||
            !string.Equals(manifest.Deployment.NativeLibraries, "adjacent_no_self_extraction", StringComparison.Ordinal) ||
            !string.Equals(manifest.Deployment.Core, "native_aot_self_contained", StringComparison.Ordinal) ||
            !string.Equals(manifest.Deployment.Symbols, "excluded_from_user_payload", StringComparison.Ordinal))
        {
            throw new ProductPackageException("The build manifest deployment contract is invalid.");
        }

        if (manifest.FileCount != PackageContract.PayloadPaths.Length ||
            manifest.Files.Length != PackageContract.PayloadPaths.Length)
        {
            throw new ProductPackageException(
                $"The build manifest must contain exactly {PackageContract.PayloadPaths.Length} payload records.");
        }

        long totalBytes = 0;
        HashSet<string> windowsPaths = new(StringComparer.OrdinalIgnoreCase);
        string? previousPath = null;
        for (int index = 0; index < manifest.Files.Length; index++)
        {
            BuildFileRecord record = manifest.Files[index];
            if (record.Path is null || record.Sha256 is null)
            {
                throw new ProductPackageException("A build manifest payload record contains null text.");
            }
            PathSafety.ValidateRelativePath(record.Path);
            if (!windowsPaths.Add(record.Path) ||
                (previousPath is not null && StringComparer.Ordinal.Compare(previousPath, record.Path) >= 0) ||
                !string.Equals(record.Path, PackageContract.PayloadPaths[index], StringComparison.Ordinal) ||
                record.Bytes < 0 || record.Bytes > PackageContract.MaximumPayloadFileBytes ||
                !IsLowerHex(record.Sha256, 64))
            {
                throw new ProductPackageException("A build manifest payload record is invalid or out of order.");
            }

            totalBytes = checked(totalBytes + record.Bytes);
            previousPath = record.Path;
        }

        if (manifest.TotalBytes != totalBytes)
        {
            throw new ProductPackageException("The build manifest total_bytes value is invalid.");
        }
    }

    private static void ValidateManifestAgainstEntries(BuildManifest manifest, IReadOnlyList<VerifiedEntry> entries)
    {
        Dictionary<string, VerifiedEntry> entriesByPath = entries.ToDictionary(static entry => entry.Path, StringComparer.Ordinal);
        foreach (BuildFileRecord record in manifest.Files)
        {
            if (!entriesByPath.TryGetValue(record.Path, out VerifiedEntry? actual) ||
                record.Bytes != actual.Length || !string.Equals(record.Sha256, actual.Sha256, StringComparison.Ordinal))
            {
                throw new ProductPackageException($"The manifest record does not match payload bytes: {record.Path}");
            }
        }
    }

    private static void ValidateChecksums(byte[] checksumBytes, IReadOnlyList<VerifiedEntry> entries)
    {
        AssertUtf8WithoutBom(checksumBytes, "SHA256SUMS");
        Dictionary<string, VerifiedEntry> entriesByPath = entries.ToDictionary(static entry => entry.Path, StringComparer.Ordinal);
        StringBuilder canonical = new();
        foreach (string path in PackageContract.ChecksumPaths)
        {
            VerifiedEntry entry = entriesByPath[path];
            _ = canonical.Append(entry.Sha256).Append("  ").Append(path).Append('\n');
        }

        byte[] expected = StrictUtf8.GetBytes(canonical.ToString());
        if (!checksumBytes.AsSpan().SequenceEqual(expected))
        {
            throw new ProductPackageException("SHA256SUMS is not the exact canonical checksum set.");
        }
    }

    private static void AssertPackageTimestamp(IReadOnlyList<VerifiedEntry> entries, long sourceDateEpoch)
    {
        DateTimeOffset timestamp;
        try
        {
            timestamp = DateTimeOffset.FromUnixTimeSeconds(sourceDateEpoch).ToUniversalTime();
        }
        catch (ArgumentOutOfRangeException exception)
        {
            throw new ProductPackageException("source_date_epoch cannot be represented.", exception);
        }

        DateTimeOffset minimum = new(1980, 1, 1, 0, 0, 0, TimeSpan.Zero);
        DateTimeOffset maximum = new(2107, 12, 31, 23, 59, 58, TimeSpan.Zero);
        if (timestamp < minimum)
        {
            timestamp = minimum;
        }
        else if (timestamp > maximum)
        {
            timestamp = maximum;
        }

        timestamp = timestamp.AddTicks(-(timestamp.Ticks % TimeSpan.TicksPerSecond));
        if ((timestamp.Second & 1) != 0)
        {
            timestamp = timestamp.AddSeconds(-1);
        }

        ushort expectedTime = checked((ushort)((timestamp.Hour << 11) | (timestamp.Minute << 5) | (timestamp.Second / 2)));
        ushort expectedDate = checked((ushort)(((timestamp.Year - 1980) << 9) | (timestamp.Month << 5) | timestamp.Day));
        foreach (VerifiedEntry entry in entries)
        {
            if (entry.DosTime != expectedTime || entry.DosDate != expectedDate)
            {
                throw new ProductPackageException($"A ZIP entry timestamp does not match source_date_epoch: {entry.Path}");
            }
        }
    }

    private static void VerifyExtractedPackageDirectory(string directory, VerifiedProductPackage package)
    {
        SafeFileTree tree = PathSafety.InspectTree(directory);
        if (!tree.Directories.SequenceEqual(PackageContract.DirectoryPaths, StringComparer.Ordinal) ||
            !tree.Files.SequenceEqual(PackageContract.ZipPaths.Order(StringComparer.Ordinal), StringComparer.Ordinal))
        {
            throw new InstallationSafetyException("The extracted staging tree has an unexpected layout.");
        }

        foreach (VerifiedEntry entry in package.Entries)
        {
            string path = PathSafety.GetStrictDescendantPath(directory, entry.Path);
            FileInfo info = new(path);
            if (info.Length != entry.Length || !string.Equals(DigestFile(path), entry.Sha256, StringComparison.Ordinal))
            {
                throw new InstallationSafetyException($"Extracted bytes failed verification: {entry.Path}");
            }
        }
    }

    private static InstalledVersionAttestation ReadVersionAttestation(string path)
    {
        PathSafety.AssertRegularFile(path);
        FileInfo info = new(path);
        if (info.Length is <= 0 or > 2048)
        {
            throw new InstallationSafetyException("The installed-version attestation has an invalid length.");
        }

        try
        {
            byte[] bytes = File.ReadAllBytes(path);
            AssertUtf8WithoutBom(bytes, ".baxy-version.json");
            InstalledVersionAttestation? attestation = JsonSerializer.Deserialize(
                bytes,
                SetupJsonContext.Default.InstalledVersionAttestation);
            if (attestation is null ||
                !string.Equals(attestation.Schema, PackageContract.VersionAttestationSchema, StringComparison.Ordinal) ||
                attestation.DataSchema != PackageContract.DataSchema ||
                !SemanticVersionComparer.IsValid(attestation.Version) ||
                !IsLowerHex(attestation.PackageSha256, 64) || !IsLowerHex(attestation.ManifestSha256, 64) ||
                !IsLowerHex(attestation.ContentId, 64))
            {
                throw new InstallationSafetyException("The installed-version attestation is invalid.");
            }

            byte[] canonical = SerializeDurable(attestation, SetupJsonContext.Default.InstalledVersionAttestation);
            if (!bytes.AsSpan().SequenceEqual(canonical))
            {
                throw new InstallationSafetyException("The installed-version attestation is not canonical.");
            }

            return attestation;
        }
        catch (InstallationSafetyException)
        {
            throw;
        }
        catch (Exception exception) when (exception is ProductPackageException or JsonException or IOException)
        {
            throw new InstallationSafetyException("The installed-version attestation is malformed.", exception);
        }
    }

    private static EntryDigest DigestEntry(Stream stream, StoredZipEntry entry, bool capture)
    {
        stream.Position = entry.DataOffset;
        byte[]? captured = capture ? new byte[checked((int)entry.Length)] : null;
        int capturedOffset = 0;
        byte[] buffer = ArrayPool<byte>.Shared.Rent(1024 * 1024);
        try
        {
            using IncrementalHash hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
            Crc32Accumulator crc = new();
            long remaining = entry.Length;
            while (remaining > 0)
            {
                int requested = (int)Math.Min(buffer.Length, remaining);
                int read = stream.Read(buffer, 0, requested);
                if (read <= 0)
                {
                    throw new EndOfStreamException($"ZIP entry is truncated: {entry.Path}");
                }

                ReadOnlySpan<byte> bytes = buffer.AsSpan(0, read);
                hash.AppendData(bytes);
                crc.Append(bytes);
                if (captured is not null)
                {
                    bytes.CopyTo(captured.AsSpan(capturedOffset));
                    capturedOffset += read;
                }

                remaining -= read;
            }

            return new EntryDigest(Convert.ToHexString(hash.GetHashAndReset()).ToLowerInvariant(), crc.GetCurrent(), captured);
        }
        finally
        {
            ArrayPool<byte>.Shared.Return(buffer, clearArray: true);
        }
    }

    private static void CopyVerifiedEntry(Stream source, VerifiedEntry entry, string destination)
    {
        source.Position = entry.DataOffset;
        byte[] buffer = ArrayPool<byte>.Shared.Rent(1024 * 1024);
        try
        {
            using FileStream output = new(destination, new FileStreamOptions
            {
                Mode = FileMode.CreateNew,
                Access = FileAccess.Write,
                Share = FileShare.None,
                BufferSize = 1024 * 1024,
                Options = FileOptions.SequentialScan | FileOptions.WriteThrough,
            });
            using IncrementalHash hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
            Crc32Accumulator crc = new();
            long remaining = entry.Length;
            while (remaining > 0)
            {
                int requested = (int)Math.Min(buffer.Length, remaining);
                int read = source.Read(buffer, 0, requested);
                if (read <= 0)
                {
                    throw new EndOfStreamException($"ZIP entry is truncated during extraction: {entry.Path}");
                }

                output.Write(buffer, 0, read);
                ReadOnlySpan<byte> bytes = buffer.AsSpan(0, read);
                hash.AppendData(bytes);
                crc.Append(bytes);
                remaining -= read;
            }

            output.Flush(flushToDisk: true);
            string sha256 = Convert.ToHexString(hash.GetHashAndReset()).ToLowerInvariant();
            if (!string.Equals(sha256, entry.Sha256, StringComparison.Ordinal) || crc.GetCurrent() != entry.Crc32)
            {
                throw new ProductPackageException($"Extracted entry does not match its verified digest: {entry.Path}");
            }
        }
        finally
        {
            ArrayPool<byte>.Shared.Return(buffer, clearArray: true);
        }

        PathSafety.AssertRegularFile(destination);
    }

    private static string DigestWholeStream(Stream stream)
    {
        stream.Position = 0;
        using IncrementalHash hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
        byte[] buffer = ArrayPool<byte>.Shared.Rent(1024 * 1024);
        try
        {
            long remaining = stream.Length;
            while (remaining > 0)
            {
                int read = stream.Read(buffer, 0, (int)Math.Min(buffer.Length, remaining));
                if (read <= 0)
                {
                    throw new EndOfStreamException("The package stream changed or was truncated while hashing.");
                }

                hash.AppendData(buffer.AsSpan(0, read));
                remaining -= read;
            }

            return Convert.ToHexString(hash.GetHashAndReset()).ToLowerInvariant();
        }
        finally
        {
            ArrayPool<byte>.Shared.Return(buffer, clearArray: true);
        }
    }

    private static string DigestFile(string path)
    {
        PathSafety.AssertRegularFile(path);
        using FileStream stream = new(path, FileMode.Open, FileAccess.Read, FileShare.Read);
        return Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
    }

    private static string ComputeContentId(IEnumerable<VerifiedEntry> entries)
    {
        StringBuilder canonical = new();
        foreach (VerifiedEntry entry in entries.OrderBy(static entry => entry.Path, StringComparer.Ordinal))
        {
            _ = canonical.Append(entry.Path).Append('\0')
                .Append(entry.Length.ToString(CultureInfo.InvariantCulture)).Append('\0')
                .Append(entry.Sha256).Append('\n');
        }

        return Convert.ToHexString(SHA256.HashData(StrictUtf8.GetBytes(canonical.ToString()))).ToLowerInvariant();
    }

    private static void AssertUtf8WithoutBom(ReadOnlySpan<byte> bytes, string context)
    {
        if (bytes.Length >= 3 && bytes[0] == 0xef && bytes[1] == 0xbb && bytes[2] == 0xbf)
        {
            throw new ProductPackageException($"UTF-8 BOM is forbidden in {context}.");
        }

        try
        {
            _ = StrictUtf8.GetString(bytes);
        }
        catch (DecoderFallbackException exception)
        {
            throw new ProductPackageException($"{context} is not strict UTF-8.", exception);
        }
    }

    private static void AssertPropertySequence(JsonElement element, string[] expected, string context)
    {
        if (element.ValueKind != JsonValueKind.Object)
        {
            throw new ProductPackageException($"The {context} must be a JSON object.");
        }

        int index = 0;
        foreach (JsonProperty property in element.EnumerateObject())
        {
            if (index >= expected.Length || !string.Equals(property.Name, expected[index], StringComparison.Ordinal))
            {
                throw new ProductPackageException($"The {context} property set or order is non-canonical.");
            }

            index++;
        }

        if (index != expected.Length)
        {
            throw new ProductPackageException($"The {context} property set is incomplete.");
        }
    }

    private static bool IsLowerHex(string? value, int length)
    {
        if (value is null || value.Length != length)
        {
            return false;
        }

        foreach (char character in value)
        {
            if (character is not (>= '0' and <= '9') and not (>= 'a' and <= 'f'))
            {
                return false;
            }
        }

        return true;
    }

    private static byte[] SerializeDurable<T>(T value, System.Text.Json.Serialization.Metadata.JsonTypeInfo<T> typeInfo)
    {
        byte[] json = JsonSerializer.SerializeToUtf8Bytes(value, typeInfo);
        byte[] durable = new byte[json.Length + 1];
        json.CopyTo(durable, 0);
        durable[^1] = (byte)'\n';
        return durable;
    }

    private static void WriteNewDurableFile(string path, byte[] bytes)
    {
        using FileStream stream = new(path, new FileStreamOptions
        {
            Mode = FileMode.CreateNew,
            Access = FileAccess.Write,
            Share = FileShare.None,
            BufferSize = 4096,
            Options = FileOptions.WriteThrough,
        });
        stream.Write(bytes);
        stream.Flush(flushToDisk: true);
    }

    private sealed record EntryDigest(string Sha256, uint Crc32, byte[]? Bytes);
}
