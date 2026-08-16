using System.IO.Compression;
using System.Security.Cryptography;
using System.Text.Json;

namespace Baxy.Providers.Windows.External;

internal sealed class WindowsKnownBackupAdapter : IExternalOperationAdapter
{
    private readonly string _backupRoot;
    private readonly IReadOnlyDictionary<string, string[]> _configuredRoots;

    internal WindowsKnownBackupAdapter(string dataRoot)
        : this(dataRoot, DefaultRoots())
    {
    }

    internal WindowsKnownBackupAdapter(
        string dataRoot,
        IReadOnlyDictionary<string, string[]> configuredRoots)
    {
        _backupRoot = Path.Combine(Path.GetFullPath(dataRoot), "known-backups");
        _configuredRoots = configuredRoots;
    }

    public bool CanHandle(string operation) => operation is
        "backup.known.create" or "backup.known.list" or "backup.known.restore.latest"
        or "backup.known.verify.latest";

    public ValueTask<ExternalCapabilityReceipt> InvokeAsync(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        var effectBoundary = new ExternalEffectBoundary();
        try
        {
            return ValueTask.FromResult(operation switch
            {
                "backup.known.create" => Create(
                    operation, arguments, effectBoundary, cancellationToken),
                "backup.known.list" => List(operation, arguments, cancellationToken),
                "backup.known.restore.latest" => RestoreLatest(
                    operation, arguments, effectBoundary, cancellationToken),
                "backup.known.verify.latest" => VerifyLatest(operation, arguments, cancellationToken),
                _ => ExternalJson.Failure(operation, "known_backup_operation_invalid"),
            });
        }
        catch (OperationCanceledException) when (
            cancellationToken.IsCancellationRequested && effectBoundary.WasCrossed)
        {
            return ValueTask.FromResult(effectBoundary.Failure(
                operation, "known_backup_filesystem_unavailable"));
        }
        catch (InvalidDataException exception)
        {
            return ValueTask.FromResult(effectBoundary.Failure(operation, exception.Message));
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException or System.Security.SecurityException)
        {
            return ValueTask.FromResult(effectBoundary.Failure(
                operation, "known_backup_filesystem_unavailable"));
        }
    }

    private ExternalCapabilityReceipt RestoreLatest(
        string operation,
        JsonElement arguments,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        string folder = ExternalJson.RequiredString(arguments, "folder");
        BackupManifest? latest = Manifests(50, cancellationToken)
            .FirstOrDefault(item => folder == "all_known" || item.Folder == folder);
        if (latest is null) return ExternalJson.Failure(operation, "known_backup_not_found");
        if (!VerifyManifest(latest))
            return ExternalJson.Failure(operation, "known_backup_hash_mismatch");
        string archivePath = Path.Combine(_backupRoot, latest.BackupId + ".zip");
        string restoreId = "known_restore_" + Guid.NewGuid().ToString("N");
        string restoreRoot = Path.Combine(_backupRoot, "restored", restoreId);
        effectBoundary.Cross(cancellationToken);
        Directory.CreateDirectory(restoreRoot);
        int fileCount = 0;
        long restoredBytes = 0;
        var hashes = new Dictionary<string, string>(StringComparer.Ordinal);
        try
        {
            using ZipArchive archive = ZipFile.OpenRead(archivePath);
            foreach (ZipArchiveEntry entry in archive.Entries)
            {
                cancellationToken.ThrowIfCancellationRequested();
                if (string.IsNullOrEmpty(entry.Name)) continue;
                string relative = entry.FullName.Replace('/', Path.DirectorySeparatorChar);
                if (Path.IsPathRooted(relative) || relative.Contains(':'))
                    throw new InvalidDataException("known_backup_entry_invalid");
                string destination = Path.GetFullPath(Path.Combine(restoreRoot, relative));
                string root = Path.GetFullPath(restoreRoot).TrimEnd(Path.DirectorySeparatorChar);
                if (!destination.StartsWith(root + Path.DirectorySeparatorChar,
                        StringComparison.OrdinalIgnoreCase))
                    throw new InvalidDataException("known_backup_entry_invalid");
                Directory.CreateDirectory(Path.GetDirectoryName(destination)!);
                using Stream input = entry.Open();
                using (FileStream output = new(
                    destination, FileMode.CreateNew, FileAccess.Write, FileShare.None,
                    64 * 1024, FileOptions.WriteThrough))
                {
                    input.CopyTo(output); output.Flush(flushToDisk: true);
                }
                var info = new FileInfo(destination);
                if (info.Length != entry.Length)
                    return ExternalJson.Failure(operation, "known_backup_restore_length_failed", true);
                hashes[relative] = HashFile(destination);
                restoredBytes += info.Length;
                fileCount++;
            }
            if (fileCount != latest.FileCount || restoredBytes != latest.SourceBytes)
                return ExternalJson.Failure(operation, "known_backup_restore_manifest_failed", true);
            foreach ((string relative, string expectedHash) in hashes)
            {
                string destination = Path.Combine(restoreRoot, relative);
                if (!File.Exists(destination)
                    || !string.Equals(HashFile(destination), expectedHash, StringComparison.Ordinal))
                    return ExternalJson.Failure(operation, "known_backup_restore_hash_failed", true);
            }
        }
        catch
        {
            try { Directory.Delete(restoreRoot, recursive: true); } catch { }
            throw;
        }
        return ExternalJson.Success(operation, ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteString("backupId", latest.BackupId); writer.WriteString("restoreId", restoreId);
            writer.WriteString("folder", latest.Folder); writer.WriteNumber("fileCount", fileCount);
            writer.WriteNumber("restoredBytes", restoredBytes); writer.WriteBoolean("verified", true);
            writer.WriteString("authority", "windows_known_backup_private_restore_hash_postread");
            writer.WriteEndObject();
        }), true);
    }

    private ExternalCapabilityReceipt Create(
        string operation,
        JsonElement arguments,
        ExternalEffectBoundary effectBoundary,
        CancellationToken cancellationToken)
    {
        string folder = ExternalJson.RequiredString(arguments, "folder");
        string[] roots = Roots(folder);
        effectBoundary.Cross(cancellationToken);
        Directory.CreateDirectory(_backupRoot);
        string backupId = "known_backup_" + Guid.NewGuid().ToString("N");
        string archivePath = Path.Combine(_backupRoot, backupId + ".zip");
        string partialPath = archivePath + ".partial";
        int fileCount = 0;
        long sourceBytes = 0;
        try
        {
            using (FileStream output = new(
                partialPath, FileMode.CreateNew, FileAccess.ReadWrite, FileShare.None))
            using (var archive = new ZipArchive(output, ZipArchiveMode.Create, leaveOpen: false))
            {
                foreach ((string root, string file) in Enumerate(roots))
                {
                    cancellationToken.ThrowIfCancellationRequested();
                    string rootLabel = roots.Length == 1
                        ? folder
                        : Path.GetFileName(root.TrimEnd(
                            Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar));
                    string relative = Path.GetRelativePath(root, file);
                    string entryName = (rootLabel + "/" + relative)
                        .Replace(Path.DirectorySeparatorChar, '/');
                    ZipArchiveEntry entry = archive.CreateEntry(
                        entryName, CompressionLevel.SmallestSize);
                    using Stream destination = entry.Open();
                    using FileStream source = new(
                        file, FileMode.Open, FileAccess.Read,
                        FileShare.ReadWrite | FileShare.Delete);
                    sourceBytes += source.Length;
                    source.CopyTo(destination);
                    fileCount++;
                }
            }
            if (fileCount == 0)
                throw new InvalidDataException("known_backup_source_empty");
            File.Move(partialPath, archivePath);
        }
        finally
        {
            if (File.Exists(partialPath)) File.Delete(partialPath);
        }

        string sha256 = HashFile(archivePath);
        var manifest = new BackupManifest(
            1, backupId, folder, DateTimeOffset.UtcNow, fileCount,
            sourceBytes, new FileInfo(archivePath).Length, sha256);
        string manifestPath = Path.Combine(_backupRoot, backupId + ".json");
        File.WriteAllText(manifestPath, SerializeManifest(manifest));
        BackupManifest postread = ReadManifest(manifestPath);
        if (postread.BackupId != backupId || !File.Exists(archivePath)
            || !string.Equals(HashFile(archivePath), sha256, StringComparison.Ordinal))
            return ExternalJson.Failure(operation, "known_backup_postread_failed", true);
        return ExternalJson.Success(operation, ManifestResult(postread, verified: true), true);
    }

    private ExternalCapabilityReceipt List(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        int limit = Math.Clamp(ExternalJson.OptionalInt(arguments, "limit", 20), 1, 50);
        BackupManifest[] manifests = Manifests(limit, cancellationToken).ToArray();
        JsonElement result = ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            writer.WriteNumber("count", manifests.Length); writer.WriteStartArray("backups");
            foreach (BackupManifest manifest in manifests)
            {
                writer.WriteStartObject(); WriteManifest(writer, manifest);
                writer.WriteBoolean("verified", VerifyManifest(manifest)); writer.WriteEndObject();
            }
            writer.WriteEndArray();
            writer.WriteString("authority", "windows_known_backup_manifest_hash_snapshot");
            writer.WriteEndObject();
        });
        return ExternalJson.Success(operation, result, effectObserved: false);
    }

    private ExternalCapabilityReceipt VerifyLatest(
        string operation,
        JsonElement arguments,
        CancellationToken cancellationToken)
    {
        string folder = ExternalJson.RequiredString(arguments, "folder");
        BackupManifest? latest = Manifests(50, cancellationToken)
            .FirstOrDefault(item => folder == "all_known" || item.Folder == folder);
        if (latest is null) return ExternalJson.Failure(operation, "known_backup_not_found");
        bool verified = VerifyManifest(latest);
        if (!verified) return ExternalJson.Failure(operation, "known_backup_hash_mismatch");
        return ExternalJson.Success(operation, ManifestResult(latest, verified), false);
    }

    private IEnumerable<BackupManifest> Manifests(int limit, CancellationToken token)
    {
        if (!Directory.Exists(_backupRoot)) yield break;
        foreach (string path in Directory.EnumerateFiles(_backupRoot, "known_backup_*.json")
            .OrderByDescending(File.GetLastWriteTimeUtc).Take(limit))
        {
            token.ThrowIfCancellationRequested();
            BackupManifest manifest;
            try { manifest = ReadManifest(path); }
            catch (Exception exception) when (exception is IOException or JsonException)
            {
                continue;
            }
            yield return manifest;
        }
    }

    private bool VerifyManifest(BackupManifest manifest)
    {
        string archive = Path.Combine(_backupRoot, manifest.BackupId + ".zip");
        return File.Exists(archive)
            && string.Equals(HashFile(archive), manifest.Sha256, StringComparison.Ordinal);
    }

    private string[] Roots(string folder)
    {
        if (!_configuredRoots.TryGetValue(folder, out string[]? roots))
            throw new InvalidDataException("known_backup_folder_invalid");
        string[] existing = roots.Select(Path.GetFullPath)
            .Where(Directory.Exists).Distinct(StringComparer.OrdinalIgnoreCase).ToArray();
        if (existing.Length == 0)
            throw new InvalidDataException("known_backup_source_not_found");
        return existing;
    }

    private static IEnumerable<(string Root, string File)> Enumerate(string[] roots)
    {
        var options = new EnumerationOptions
        {
            RecurseSubdirectories = true,
            IgnoreInaccessible = true,
            AttributesToSkip = FileAttributes.ReparsePoint,
            MaxRecursionDepth = 32,
        };
        foreach (string root in roots)
        {
            foreach (string file in Directory.EnumerateFiles(root, "*", options)
                .Order(StringComparer.OrdinalIgnoreCase))
            {
                yield return (root, file);
            }
        }
    }

    private static JsonElement ManifestResult(BackupManifest manifest, bool verified) =>
        ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1);
            WriteManifest(writer, manifest); writer.WriteBoolean("verified", verified);
            writer.WriteString("authority", "windows_known_backup_zip_hash_postread");
            writer.WriteEndObject();
        });

    private static void WriteManifest(Utf8JsonWriter writer, BackupManifest manifest)
    {
        writer.WriteString("backupId", manifest.BackupId);
        writer.WriteString("folder", manifest.Folder);
        writer.WriteString("createdUtc", manifest.CreatedUtc);
        writer.WriteNumber("fileCount", manifest.FileCount);
        writer.WriteNumber("sourceBytes", manifest.SourceBytes);
        writer.WriteNumber("archiveBytes", manifest.ArchiveBytes);
        writer.WriteString("sha256", manifest.Sha256);
    }

    private static string SerializeManifest(BackupManifest manifest) =>
        ExternalJson.Create(writer =>
        {
            writer.WriteStartObject(); writer.WriteNumber("version", manifest.Version);
            WriteManifest(writer, manifest); writer.WriteEndObject();
        }).GetRawText();

    private static BackupManifest ReadManifest(string path)
    {
        using JsonDocument document = JsonDocument.Parse(File.ReadAllText(path));
        JsonElement root = document.RootElement;
        return new BackupManifest(
            root.GetProperty("version").GetInt32(),
            root.GetProperty("backupId").GetString()
                ?? throw new InvalidDataException("known_backup_manifest_invalid"),
            root.GetProperty("folder").GetString()
                ?? throw new InvalidDataException("known_backup_manifest_invalid"),
            root.GetProperty("createdUtc").GetDateTimeOffset(),
            root.GetProperty("fileCount").GetInt32(),
            root.GetProperty("sourceBytes").GetInt64(),
            root.GetProperty("archiveBytes").GetInt64(),
            root.GetProperty("sha256").GetString()
                ?? throw new InvalidDataException("known_backup_manifest_invalid"));
    }

    private static string HashFile(string path)
    {
        using FileStream stream = File.OpenRead(path);
        return Convert.ToHexStringLower(SHA256.HashData(stream));
    }

    private static Dictionary<string, string[]> DefaultRoots()
    {
        string profile = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
        string documents = Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments);
        string pictures = Environment.GetFolderPath(Environment.SpecialFolder.MyPictures);
        string desktop = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
        return new Dictionary<string, string[]>(StringComparer.Ordinal)
        {
            ["documents"] = [documents],
            ["pictures"] = [pictures],
            ["desktop"] = [desktop],
            ["projects"] = [Path.Combine(documents, "Projects"), Path.Combine(profile, "Projects")],
            ["all_known"] = [documents, pictures, desktop],
        };
    }

    private sealed record BackupManifest(
        int Version,
        string BackupId,
        string Folder,
        DateTimeOffset CreatedUtc,
        int FileCount,
        long SourceBytes,
        long ArchiveBytes,
        string Sha256);
}
