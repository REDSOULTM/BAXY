using System.Collections.Concurrent;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;

namespace Baxy.Providers.Windows.Filesystem;

/// <summary>
/// Confines file authority to one injected root. Public contracts exchange only
/// normalized relative destinations and short-lived opaque resource handles.
/// </summary>
public sealed class LocalFilesystemProvider : IFilesystemProvider
{
    private const int MaximumHandles = 512;
    private const int MaximumTextBytes = 1_048_576;
    private static readonly TimeSpan HandleLifetime = TimeSpan.FromMinutes(5);
    private static readonly UTF8Encoding StrictUtf8 = new(false, true);
    private static readonly ConcurrentDictionary<string, object> RootLocks =
        new(StringComparer.OrdinalIgnoreCase);
    private readonly string _root;
    private readonly string _trash;
    private readonly string _backups;
    private readonly object _gate;
    private readonly Dictionary<string, Handle> _handles = new(StringComparer.Ordinal);
    private readonly Dictionary<string, TrashHandle> _trashHandles = new(StringComparer.Ordinal);
    private readonly TimeProvider _time;

    public LocalFilesystemProvider(string rootDirectory, TimeProvider? timeProvider = null)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(rootDirectory);
        _root = Path.GetFullPath(rootDirectory);
        _trash = Path.Combine(_root, ".trash");
        _backups = Path.Combine(_root, ".backups");
        Directory.CreateDirectory(_root);
        Directory.CreateDirectory(_trash);
        Directory.CreateDirectory(_backups);
        _gate = RootLocks.GetOrAdd(_root, static _ => new object());
        _time = timeProvider ?? TimeProvider.System;
        EnsureSafePath(_root, allowMissingLeaf: false);
        EnsureSafePath(_trash, allowMissingLeaf: false);
        EnsureSafePath(_backups, allowMissingLeaf: false);
    }

    public FilesystemListResult List(string relativeDirectory, int limit)
    {
        ValidateLimit(limit);
        lock (_gate)
        {
            string directory = Resolve(relativeDirectory, allowMissingLeaf: false);
            if (!Directory.Exists(directory)) throw Error("directory_not_found");
            FilesystemEntry[] entries = Directory.EnumerateFileSystemEntries(directory)
                .Where(path => !IsReserved(path))
                .OrderBy(Path.GetFileName, StringComparer.OrdinalIgnoreCase)
                .Take(limit)
                .Select(IssueEntry)
                .ToArray();
            return new FilesystemListResult(entries, entries.Length);
        }
    }

    public FilesystemListResult Search(string query, int limit)
    {
        ValidateLimit(limit);
        string normalized = NormalizeText(query, 512, allowEmpty: false);
        lock (_gate)
        {
            var options = new EnumerationOptions
            {
                RecurseSubdirectories = true,
                AttributesToSkip = FileAttributes.ReparsePoint,
                IgnoreInaccessible = false,
            };
            FilesystemEntry[] entries = Directory.EnumerateFileSystemEntries(_root, "*", options)
                .Where(path => !IsReserved(path)
                    && Path.GetFileName(path).Contains(normalized, StringComparison.OrdinalIgnoreCase))
                .OrderBy(path => Path.GetRelativePath(_root, path), StringComparer.OrdinalIgnoreCase)
                .Take(limit)
                .Select(IssueEntry)
                .ToArray();
            return new FilesystemListResult(entries, entries.Length);
        }
    }

    public FilesystemTextResult ReadText(string resourceId, int maximumBytes)
    {
        if (maximumBytes is < 1 or > MaximumTextBytes) throw Error("invalid_limit");
        lock (_gate)
        {
            string path = ResolveHandle(resourceId, requireFile: true);
            byte[] bytes = File.ReadAllBytes(path);
            if (bytes.Length > maximumBytes) throw Error("file_too_large");
            string text;
            try { text = StrictUtf8.GetString(bytes); }
            catch (DecoderFallbackException) { throw Error("invalid_utf8"); }
            string hash = Hex(SHA256.HashData(bytes));
            return new FilesystemTextResult(resourceId, text, bytes.Length, hash);
        }
    }

    public FilesystemEntry Hash(string resourceId)
    {
        lock (_gate)
        {
            string path = ResolveHandle(resourceId, requireFile: true);
            return Entry(resourceId, path, includeHash: true);
        }
    }

    public FilesystemMutationResult CreateDirectory(string relativePath)
    {
        lock (_gate)
        {
            string path = Resolve(relativePath, allowMissingLeaf: true);
            if (File.Exists(path)) throw Error("destination_exists");
            bool reached = Directory.Exists(path);
            if (!reached) Directory.CreateDirectory(path);
            EnsureSafePath(path, allowMissingLeaf: false);
            return Mutation(Issue(path), path, reached);
        }
    }

    public FilesystemMutationResult WriteText(
        string relativePath,
        string text,
        string? expectedSha256)
    {
        string normalizedText = NormalizeText(text, MaximumTextBytes, allowEmpty: true);
        byte[] bytes = StrictUtf8.GetBytes(normalizedText);
        string desiredHash = Hex(SHA256.HashData(bytes));
        lock (_gate)
        {
            string path = Resolve(relativePath, allowMissingLeaf: true);
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            EnsureSafePath(Path.GetDirectoryName(path)!, allowMissingLeaf: false);
            bool exists = File.Exists(path);
            if (exists)
            {
                string current = HashFile(path);
                if (string.Equals(current, desiredHash, StringComparison.Ordinal))
                    return Mutation(Issue(path), path, reachedState: true);
                if (!IsHash(expectedSha256) || !string.Equals(current, expectedSha256, StringComparison.Ordinal))
                    throw Error("version_conflict");
            }
            else if (expectedSha256 is not null)
            {
                throw Error("version_conflict");
            }

            string temporary = Path.Combine(
                Path.GetDirectoryName(path)!, ".baxy-write-" + Guid.NewGuid().ToString("N") + ".tmp");
            try
            {
                using (var stream = new FileStream(
                    temporary, FileMode.CreateNew, FileAccess.Write, FileShare.None,
                    4096, FileOptions.WriteThrough))
                {
                    stream.Write(bytes);
                    stream.Flush(flushToDisk: true);
                }
                if (exists) File.Move(temporary, path, overwrite: true);
                else File.Move(temporary, path);
            }
            finally
            {
                if (File.Exists(temporary)) File.Delete(temporary);
            }
            if (!string.Equals(HashFile(path), desiredHash, StringComparison.Ordinal))
                throw Error("verification_failed");
            return Mutation(Issue(path), path, reachedState: false);
        }
    }

    public FilesystemMutationResult Transfer(
        string resourceId,
        string destinationRelativePath,
        string expectedSha256,
        bool move)
    {
        if (!IsHash(expectedSha256)) throw Error("invalid_hash");
        lock (_gate)
        {
            string source = ResolveHandle(resourceId, requireFile: true);
            string sourceHash = HashFile(source);
            if (!string.Equals(sourceHash, expectedSha256, StringComparison.Ordinal))
                throw Error("version_conflict");
            string destination = Resolve(destinationRelativePath, allowMissingLeaf: true);
            if (File.Exists(destination) || Directory.Exists(destination)) throw Error("destination_exists");
            Directory.CreateDirectory(Path.GetDirectoryName(destination)!);
            EnsureSafePath(Path.GetDirectoryName(destination)!, allowMissingLeaf: false);
            if (move) File.Move(source, destination);
            else File.Copy(source, destination);
            if (!File.Exists(destination)
                || !string.Equals(HashFile(destination), sourceHash, StringComparison.Ordinal)
                || (move && File.Exists(source)))
                throw Error("verification_failed");
            return Mutation(Issue(destination), destination, reachedState: false);
        }
    }

    public FilesystemTrashPreparation PrepareTrash(string resourceId)
    {
        lock (_gate)
        {
            string path = ResolveHandle(resourceId, requireFile: false);
            string id = "trash_" + Guid.NewGuid().ToString("N");
            string label = Path.GetFileName(path);
            _trashHandles[id] = new TrashHandle(path, label, _time.GetUtcNow());
            long size = File.Exists(path) ? new FileInfo(path).Length : 0;
            return new FilesystemTrashPreparation(id, label,
                Directory.Exists(path) ? "directory" : "file", size);
        }
    }

    public FilesystemTrashReceipt CommitTrash(string trashId, string reviewLabel)
    {
        lock (_gate)
        {
            TrashHandle handle = ConsumeTrash(trashId);
            if (!string.Equals(handle.ReviewLabel, reviewLabel, StringComparison.Ordinal)
                || (!File.Exists(handle.Path) && !Directory.Exists(handle.Path)))
                throw Error("trash_selection_changed");
            string restoreId = "restore_" + Guid.NewGuid().ToString("N");
            string destination = Path.Combine(_trash, restoreId + "_" + handle.ReviewLabel);
            if (File.Exists(handle.Path)) File.Move(handle.Path, destination);
            else Directory.Move(handle.Path, destination);
            _trashHandles[restoreId] = new TrashHandle(
                destination, Path.GetRelativePath(_root, handle.Path), _time.GetUtcNow());
            return new FilesystemTrashReceipt(restoreId, reviewLabel, true);
        }
    }

    public FilesystemMutationResult Restore(string restoreId)
    {
        lock (_gate)
        {
            TrashHandle handle = ConsumeTrash(restoreId);
            string destination = Resolve(handle.ReviewLabel, allowMissingLeaf: true);
            if (File.Exists(destination) || Directory.Exists(destination)) throw Error("destination_exists");
            if (File.Exists(handle.Path)) File.Move(handle.Path, destination);
            else if (Directory.Exists(handle.Path)) Directory.Move(handle.Path, destination);
            else throw Error("restore_not_found");
            return Mutation(Issue(destination), destination, reachedState: false);
        }
    }

    public BackupReceipt CreateBackup(string resourceId, string expectedSha256)
    {
        if (!IsHash(expectedSha256)) throw Error("invalid_hash");
        lock (_gate)
        {
            string source = ResolveHandle(resourceId, requireFile: true);
            string hash = HashFile(source);
            if (!string.Equals(hash, expectedSha256, StringComparison.Ordinal))
                throw Error("version_conflict");
            string id = "backup_" + Guid.NewGuid().ToString("N");
            string destination = Path.Combine(_backups, id + ".bin");
            File.Copy(source, destination);
            BackupReceipt receipt = VerifyBackupUnsafe(id);
            if (!string.Equals(receipt.Sha256, hash, StringComparison.Ordinal))
                throw Error("verification_failed");
            return receipt;
        }
    }

    public BackupListResult ListBackups(int limit)
    {
        if (limit is < 1 or > 50) throw Error("invalid_limit");
        lock (_gate)
        {
            BackupReceipt[] backups = Directory.EnumerateFiles(
                    _backups, "backup_????????????????????????????????.bin", SearchOption.TopDirectoryOnly)
                .Select(path => new FileInfo(path))
                .OrderByDescending(static info => info.LastWriteTimeUtc)
                .ThenBy(static info => info.Name, StringComparer.Ordinal)
                .Take(limit)
                .Select(info => VerifyBackupUnsafe(Path.GetFileNameWithoutExtension(info.Name)))
                .ToArray();
            return new BackupListResult(backups, backups.Length);
        }
    }

    public BackupReceipt VerifyBackup(string backupId)
    {
        lock (_gate) return VerifyBackupUnsafe(backupId);
    }

    public FilesystemMutationResult RestoreBackup(string backupId, string destinationRelativePath)
    {
        lock (_gate)
        {
            BackupReceipt receipt = VerifyBackupUnsafe(backupId);
            string source = Path.Combine(_backups, backupId + ".bin");
            string destination = Resolve(destinationRelativePath, allowMissingLeaf: true);
            if (File.Exists(destination) || Directory.Exists(destination)) throw Error("destination_exists");
            Directory.CreateDirectory(Path.GetDirectoryName(destination)!);
            File.Copy(source, destination);
            if (!string.Equals(HashFile(destination), receipt.Sha256, StringComparison.Ordinal))
                throw Error("verification_failed");
            return Mutation(Issue(destination), destination, reachedState: false);
        }
    }

    private BackupReceipt VerifyBackupUnsafe(string backupId)
    {
        if (backupId is not { Length: 39 } || !backupId.StartsWith("backup_", StringComparison.Ordinal)
            || !backupId[7..].All(static c => c is >= '0' and <= '9' or >= 'a' and <= 'f'))
            throw Error("invalid_backup_id");
        string path = Path.Combine(_backups, backupId + ".bin");
        EnsureSafePath(path, allowMissingLeaf: false);
        if (!File.Exists(path)) throw Error("backup_not_found");
        var info = new FileInfo(path);
        return new BackupReceipt(backupId, info.Length, HashFile(path), true);
    }

    private FilesystemEntry IssueEntry(string path) => Entry(Issue(path), path, includeHash: false);

    private static FilesystemEntry Entry(string id, string path, bool includeHash)
    {
        bool directory = Directory.Exists(path);
        var info = directory ? (FileSystemInfo)new DirectoryInfo(path) : new FileInfo(path);
        return new FilesystemEntry(id, info.Name, directory ? "directory" : "file",
            directory ? 0 : ((FileInfo)info).Length, info.LastWriteTimeUtc,
            includeHash && !directory ? HashFile(path) : null);
    }

    private static FilesystemMutationResult Mutation(string id, string path, bool reachedState)
    {
        FilesystemEntry entry = Entry(id, path, includeHash: File.Exists(path));
        return new FilesystemMutationResult(
            entry.ResourceId, entry.Name, entry.Kind, entry.Size, entry.Sha256, reachedState);
    }

    private string Issue(string path)
    {
        EnsureSafePath(path, allowMissingLeaf: false);
        Prune();
        if (_handles.Count >= MaximumHandles) throw Error("handle_capacity_reached");
        string id = "fs_" + Guid.NewGuid().ToString("N");
        FileSystemInfo info = File.Exists(path) ? new FileInfo(path) : new DirectoryInfo(path);
        _handles[id] = new Handle(path, info.LastWriteTimeUtc, File.Exists(path) ? ((FileInfo)info).Length : 0,
            _time.GetUtcNow());
        return id;
    }

    private string ResolveHandle(string id, bool requireFile)
    {
        Prune();
        if (!_handles.TryGetValue(id, out Handle? handle)) throw Error("invalid_resource_id");
        EnsureSafePath(handle.Path, allowMissingLeaf: false);
        FileSystemInfo info = File.Exists(handle.Path)
            ? new FileInfo(handle.Path)
            : Directory.Exists(handle.Path) ? new DirectoryInfo(handle.Path) : throw Error("resource_changed");
        long size = info is FileInfo file ? file.Length : 0;
        if (info.LastWriteTimeUtc != handle.LastWriteUtc || size != handle.Size
            || (requireFile && info is not FileInfo)) throw Error("resource_changed");
        return handle.Path;
    }

    private string Resolve(string relative, bool allowMissingLeaf)
    {
        relative ??= string.Empty;
        if (Path.IsPathRooted(relative) || relative.Contains('\0')) throw Error("invalid_path");
        string full = Path.GetFullPath(Path.Combine(_root, relative.Replace('/', Path.DirectorySeparatorChar)));
        if (!full.StartsWith(_root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase)
            && !string.Equals(full, _root, StringComparison.OrdinalIgnoreCase)) throw Error("path_outside_sandbox");
        if (IsReserved(full)) throw Error("path_reserved");
        EnsureSafePath(full, allowMissingLeaf);
        return full;
    }

    private void EnsureSafePath(string path, bool allowMissingLeaf)
    {
        string current = _root;
        string relative = Path.GetRelativePath(_root, path);
        if (relative == ".") return;
        string[] parts = relative.Split(Path.DirectorySeparatorChar, StringSplitOptions.RemoveEmptyEntries);
        for (int index = 0; index < parts.Length; index++)
        {
            current = Path.Combine(current, parts[index]);
            if (!File.Exists(current) && !Directory.Exists(current))
            {
                if (allowMissingLeaf) return;
                throw Error("path_not_found");
            }
            FileSystemInfo info = Directory.Exists(current)
                ? new DirectoryInfo(current) : new FileInfo(current);
            if (info.LinkTarget is not null) throw Error("unsafe_reparse_point");
        }
    }

    private TrashHandle ConsumeTrash(string id)
    {
        Prune();
        if (!_trashHandles.Remove(id, out TrashHandle? handle)) throw Error("invalid_trash_id");
        return handle;
    }

    private void Prune()
    {
        DateTimeOffset now = _time.GetUtcNow();
        foreach (string key in _handles.Where(pair => now - pair.Value.IssuedAt > HandleLifetime)
            .Select(static pair => pair.Key).ToArray()) _handles.Remove(key);
        foreach (string key in _trashHandles.Where(pair => now - pair.Value.IssuedAt > HandleLifetime)
            .Select(static pair => pair.Key).ToArray()) _trashHandles.Remove(key);
    }

    private bool IsUnderTrash(string path) => path.StartsWith(
        _trash + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase)
        || string.Equals(path, _trash, StringComparison.OrdinalIgnoreCase);

    private bool IsReserved(string path) => IsUnderTrash(path)
        || path.StartsWith(_backups + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase)
        || string.Equals(path, _backups, StringComparison.OrdinalIgnoreCase);

    private static void ValidateLimit(int limit)
    {
        if (limit is < 1 or > 100) throw Error("invalid_limit");
    }

    private static string NormalizeText(string value, int maximumBytes, bool allowEmpty)
    {
        if (value is null || (!allowEmpty && string.IsNullOrWhiteSpace(value))) throw Error("invalid_text");
        try
        {
            if (StrictUtf8.GetByteCount(value) > maximumBytes || value.Contains('\0')) throw Error("invalid_text");
        }
        catch (EncoderFallbackException) { throw Error("invalid_text"); }
        return value;
    }

    private static string HashFile(string path)
    {
        using FileStream stream = File.Open(path, FileMode.Open, FileAccess.Read, FileShare.Read);
        return Hex(SHA256.HashData(stream));
    }

    private static bool IsHash(string? value) => value is { Length: 64 }
        && value.All(static character => character is >= '0' and <= '9' or >= 'a' and <= 'f');
    private static string Hex(byte[] value) => Convert.ToHexStringLower(value);
    private static FilesystemProviderException Error(string code) => new(code);

    private sealed record Handle(string Path, DateTime LastWriteUtc, long Size, DateTimeOffset IssuedAt);
    private sealed record TrashHandle(string Path, string ReviewLabel, DateTimeOffset IssuedAt);
}
