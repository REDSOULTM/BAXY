using System.Collections.Concurrent;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using Baxy.Providers.Windows.External;

namespace Baxy.Providers.Windows.Filesystem;

/// <summary>
/// Confines file authority to one injected root. Public contracts exchange only
/// normalized relative destinations and short-lived opaque resource handles.
/// </summary>
public sealed class LocalFilesystemProvider : IFilesystemProvider
{
    private const int MaximumHandles = 512;
    private const int MaximumTextBytes = 1_048_576;
    private const long MaximumAppendTargetBytes = 10L * 1024 * 1024;
    private const string RecordedHashExtension = ".sha256";
    private static readonly TimeSpan HandleLifetime = TimeSpan.FromMinutes(5);
    private static readonly UTF8Encoding StrictUtf8 = new(false, true);
    private static readonly ConcurrentDictionary<string, object> RootLocks =
        new(StringComparer.OrdinalIgnoreCase);
    private readonly string _root;
    private readonly string _backups;
    private readonly object _gate;
    private readonly Dictionary<string, Handle> _handles = new(StringComparer.Ordinal);
    private readonly TimeProvider _time;
    private readonly IRecycleBin _recycleBin;

    public LocalFilesystemProvider(string rootDirectory, TimeProvider? timeProvider = null)
        : this(rootDirectory, WindowsRecycleBin.Instance, timeProvider)
    {
    }

    internal LocalFilesystemProvider(string rootDirectory, IRecycleBin recycleBin, TimeProvider? timeProvider = null)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(rootDirectory);
        _recycleBin = recycleBin ?? throw new ArgumentNullException(nameof(recycleBin));
        _root = Path.GetFullPath(rootDirectory);
        _backups = Path.Combine(_root, ".backups");
        Directory.CreateDirectory(_root);
        Directory.CreateDirectory(_backups);
        _gate = RootLocks.GetOrAdd(_root, static _ => new object());
        _time = timeProvider ?? TimeProvider.System;
        EnsureSafePath(_root, allowMissingLeaf: false);
        EnsureSafePath(_backups, allowMissingLeaf: false);
    }

    public FilesystemListResult List(string relativeDirectory, int limit)
    {
        ValidateLimit(limit);
        lock (_gate)
        {
            string directory = Resolve(relativeDirectory, allowMissingLeaf: false);
            if (!Directory.Exists(directory)) throw Error("directory_not_found");
            string[] paths = Directory.EnumerateFileSystemEntries(directory)
                .Where(path => !IsReserved(path))
                .OrderBy(Path.GetFileName, StringComparer.OrdinalIgnoreCase)
                .ToArray();
            FilesystemEntry[] entries = paths.Take(limit).Select(IssueEntry).ToArray();
            return new FilesystemListResult(entries, entries.Length, Path.GetFullPath(directory), paths.Length);
        }
    }

    public FilesystemListResult Search(string query, int limit)
    {
        ValidateLimit(limit);
        string normalized = NormalizeText(query, 512, allowEmpty: false);
        if (Path.IsPathFullyQualified(normalized)) throw Error("absolute_path_search_unsupported");
        lock (_gate)
        {
            var options = new EnumerationOptions
            {
                RecurseSubdirectories = true,
                AttributesToSkip = FileAttributes.ReparsePoint,
                IgnoreInaccessible = false,
            };
            string[] matching = Directory.EnumerateFileSystemEntries(_root, "*", options)
                .Where(path => !IsReserved(path)
                    && Path.GetFileName(path).Contains(normalized, StringComparison.OrdinalIgnoreCase))
                .OrderBy(path => Path.GetRelativePath(_root, path), StringComparer.OrdinalIgnoreCase)
                .ToArray();
            FilesystemEntry[] entries = matching.Take(limit).Select(IssueEntry).ToArray();
            // Ronda final 7 (regla 3): the receipt says how many match, so a cut list is never read as all of them.
            return new FilesystemListResult(entries, entries.Length, TotalCount: matching.Length);
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

    public FilesystemMutationResult CreateDirectory(string relativePath, string? folder)
    {
        string root = RootFor(folder);
        lock (_gate)
        {
            string path = ResolveIn(root, relativePath, allowMissingLeaf: true, takesFolder: true);
            if (File.Exists(path)) throw Error("destination_exists");
            bool reached = Directory.Exists(path);
            EnsureHandleRoom();
            if (!reached) Directory.CreateDirectory(path);
            EnsureSafePathIn(root, path, allowMissingLeaf: false);
            return Mutation(path, root, reached);
        }
    }

    /// <summary>
    /// Writes UTF-8 text atomically (a temporary file beside it, then a move). Replacing an existing file takes its
    /// exact current SHA-256, and its previous version goes to the Recycle Bin first, so the change stays recoverable
    /// by the person; appending keeps every byte already there and adds the text as a line of its own (in the file's own
    /// encoding and line breaks), and takes
    /// the hash only when it is given. The same content already there is the state reached, with nothing written.
    /// </summary>
    public FilesystemMutationResult WriteText(
        string relativePath,
        string text,
        string? expectedSha256,
        string? folder = null,
        bool append = false)
    {
        string root = RootFor(folder);
        string normalizedText = NormalizeText(text, MaximumTextBytes, allowEmpty: true);
        lock (_gate)
        {
            string path = ResolveIn(root, relativePath, allowMissingLeaf: true, takesFolder: true);
            if (Directory.Exists(path)) throw Error("destination_is_directory");
            bool exists = File.Exists(path);
            byte[] previous = [];
            if (exists && append)
            {
                if (new FileInfo(path).Length > MaximumAppendTargetBytes) throw Error("file_too_large");
                previous = File.ReadAllBytes(path);
            }
            byte[] bytes = append
                ? [.. previous, .. TextFileEncoding.EncodeAppended(previous, normalizedText)]
                : StrictUtf8.GetBytes(normalizedText);
            string desiredHash = Hex(SHA256.HashData(bytes));
            string? current = !exists ? null : append ? Hex(SHA256.HashData(previous)) : HashFile(path);
            if (current is not null && string.Equals(current, desiredHash, StringComparison.Ordinal))
                return Mutation(path, root, reachedState: true, previousVersionRecycled: false);
            bool conflict = current is null
                ? expectedSha256 is not null
                : append
                    ? expectedSha256 is not null && !string.Equals(current, expectedSha256, StringComparison.Ordinal)
                    : !IsHash(expectedSha256) || !string.Equals(current, expectedSha256, StringComparison.Ordinal);
            // BAXY Renew (notebook): a hash expected of a file that is not there is no other version of it.
            if (conflict)
                throw WriteRefused(
                    current is null ? "expected_hash_for_missing_file" : "version_conflict", path, exists, append);

            // A refused write leaves nothing behind: the folder of a new file is made only now.
            EnsureHandleRoom();
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            EnsureSafePathIn(root, Path.GetDirectoryName(path)!, allowMissingLeaf: false);
            string temporary = Path.Combine(
                Path.GetDirectoryName(path)!, ".baxy-write-" + Guid.NewGuid().ToString("N") + ".tmp");
            bool recycled = false;
            try
            {
                using (var stream = new FileStream(
                    temporary, FileMode.CreateNew, FileAccess.Write, FileShare.None,
                    4096, FileOptions.WriteThrough))
                {
                    stream.Write(bytes);
                    stream.Flush(flushToDisk: true);
                }
                if (exists && append)
                {
                    if (!string.Equals(HashFile(path), current, StringComparison.Ordinal))
                        throw WriteRefused("version_conflict", path, exists, append);
                    File.Move(temporary, path, overwrite: true);
                }
                else if (exists)
                {
                    // The previous version is the person's: it goes to the Recycle Bin before the new one takes its
                    // place, and when the bin cannot take it nothing is replaced.
                    if (!_recycleBin.Recycle(path)) throw Error("previous_version_not_recycled");
                    recycled = true;
                    File.Move(temporary, path);
                }
                else
                {
                    File.Move(temporary, path);
                }
            }
            finally
            {
                if (File.Exists(temporary)) File.Delete(temporary);
            }
            if (!string.Equals(HashFile(path), desiredHash, StringComparison.Ordinal))
                throw AfterEffect("verification_failed");
            return Mutation(path, root, reachedState: false, previousVersionRecycled: recycled);
        }
    }

    /// <summary>
    /// The sandbox root, or one of the person's known folders when the
    /// catalog argument names it. Known folders never use the sandbox's
    /// backups; the same reparse-point and traversal checks apply.
    /// </summary>
    private string RootFor(string? folder)
    {
        if (folder is null) return _root;
        string path = folder switch
        {
            "desktop" => Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory),
            "documents" => Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
            "downloads" => Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "Downloads"),
            "home" => Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),
            _ => throw Error("invalid_folder"),
        };
        if (string.IsNullOrWhiteSpace(path) || !Path.IsPathFullyQualified(path) || !Directory.Exists(path))
            throw Error("known_folder_unavailable");
        return Path.GetFullPath(path);
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
            EnsureHandleRoom();
            Directory.CreateDirectory(Path.GetDirectoryName(destination)!);
            EnsureSafePath(Path.GetDirectoryName(destination)!, allowMissingLeaf: false);
            if (move) File.Move(source, destination);
            else File.Copy(source, destination);
            if (!File.Exists(destination)
                || !string.Equals(HashFile(destination), sourceHash, StringComparison.Ordinal)
                || (move && File.Exists(source)))
                throw AfterEffect("verification_failed");
            return Mutation(destination, _root, reachedState: false);
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
            if (!string.Equals(HashFile(destination), hash, StringComparison.Ordinal))
                throw AfterEffect("verification_failed");
            File.WriteAllText(Path.Combine(_backups, id + RecordedHashExtension), hash);
            BackupReceipt receipt = VerifyBackupUnsafe(id);
            if (!receipt.Verified) throw AfterEffect("verification_failed");
            return receipt;
        }
    }

    public BackupListResult ListBackups(int limit)
    {
        if (limit is < 1 or > 50) throw Error("invalid_limit");
        lock (_gate)
        {
            FileInfo[] all = Directory.EnumerateFiles(
                    _backups, "backup_????????????????????????????????.bin", SearchOption.TopDirectoryOnly)
                .Select(path => new FileInfo(path))
                // Ronda final 9 (regla 3): newest backup first by when the copy was made; File.Copy keeps the original's
                // last write time, so that would order by the original's last edit.
                .OrderByDescending(static info => info.CreationTimeUtc)
                .ThenBy(static info => info.Name, StringComparer.Ordinal)
                .ToArray();
            BackupReceipt[] backups = all
                .Take(limit)
                .Select(info => VerifyBackupUnsafe(Path.GetFileNameWithoutExtension(info.Name)))
                .ToArray();
            return new BackupListResult(backups, backups.Length, all.Length);
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
            if (!receipt.Verified) throw Error("backup_not_verified");
            string source = Path.Combine(_backups, backupId + ".bin");
            string destination = Resolve(destinationRelativePath, allowMissingLeaf: true);
            if (File.Exists(destination) || Directory.Exists(destination)) throw Error("destination_exists");
            EnsureHandleRoom();
            Directory.CreateDirectory(Path.GetDirectoryName(destination)!);
            EnsureSafePath(Path.GetDirectoryName(destination)!, allowMissingLeaf: false);
            File.Copy(source, destination);
            if (!string.Equals(HashFile(destination), receipt.Sha256, StringComparison.Ordinal))
                throw AfterEffect("verification_failed");
            return Mutation(destination, _root, reachedState: false);
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
        string hash = HashFile(path);
        return new BackupReceipt(backupId, info.Length, hash, string.Equals(RecordedHash(backupId), hash, StringComparison.Ordinal));
    }

    // The SHA-256 a backup had when it was made (a file beside it), or null for one made before it was recorded: only a
    // backup whose bytes still hash to it is verified.
    private string? RecordedHash(string backupId)
    {
        string path = Path.Combine(_backups, backupId + RecordedHashExtension);
        EnsureSafePath(path, allowMissingLeaf: true);
        if (!File.Exists(path) || new FileInfo(path).Length != 64) return null;
        string recorded = File.ReadAllText(path);
        return IsHash(recorded) ? recorded : null;
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

    // The handle of what a mutation left, issued after its change: room for it was made sure before the change
    // (EnsureHandleRoom), and a path gone or changed meanwhile fails with the change possibly on disk, unless the state
    // was already there.
    private FilesystemMutationResult Mutation(
        string path, string root, bool reachedState, bool? previousVersionRecycled = null)
    {
        string id;
        try
        {
            id = Issue(path, root);
        }
        catch (FilesystemProviderException exception)
        {
            throw new FilesystemProviderException(exception.Code)
            {
                Result = exception.Result,
                EffectMayHaveOccurred = !reachedState,
            };
        }
        FilesystemEntry entry = Entry(id, path, includeHash: File.Exists(path));
        return new FilesystemMutationResult(
            entry.ResourceId, entry.Name, entry.Kind, entry.Size, entry.Sha256, reachedState, previousVersionRecycled,
            Path.GetFullPath(path));
    }

    private string Issue(string path) => Issue(path, _root);

    private string Issue(string path, string root)
    {
        EnsureSafePathIn(root, path, allowMissingLeaf: false);
        EnsureHandleRoom();
        string id = "fs_" + Guid.NewGuid().ToString("N");
        FileSystemInfo info = File.Exists(path) ? new FileInfo(path) : new DirectoryInfo(path);
        _handles[id] = new Handle(path, root, info.LastWriteTimeUtc, File.Exists(path) ? ((FileInfo)info).Length : 0,
            _time.GetUtcNow());
        return id;
    }

    // A full table of handles refuses; checked before a mutation's change too, so a change is never made whose handle
    // cannot be issued (under the gate the count only shrinks until Issue).
    private void EnsureHandleRoom()
    {
        Prune();
        if (_handles.Count >= MaximumHandles) throw Error("handle_capacity_reached");
    }

    private string ResolveHandle(string id, bool requireFile)
    {
        Prune();
        if (!_handles.TryGetValue(id, out Handle? handle)) throw Error("invalid_resource_id");
        EnsureSafePathIn(handle.Root, handle.Path, allowMissingLeaf: false);
        FileSystemInfo info = File.Exists(handle.Path)
            ? new FileInfo(handle.Path)
            : Directory.Exists(handle.Path) ? new DirectoryInfo(handle.Path) : throw Error("resource_changed");
        long size = info is FileInfo file ? file.Length : 0;
        if (info.LastWriteTimeUtc != handle.LastWriteUtc || size != handle.Size
            || (requireFile && info is not FileInfo)) throw Error("resource_changed");
        return handle.Path;
    }

    private string Resolve(string relative, bool allowMissingLeaf) =>
        ResolveIn(_root, relative, allowMissingLeaf);

    // takesFolder: the operation has a folder argument, so a path outside the working folder can name the person's.
    private string ResolveIn(string root, string relative, bool allowMissingLeaf, bool takesFolder = false)
    {
        relative ??= string.Empty;
        // A full path inside the folder is the same place as its relative path: the model copies the path the person
        // said (BAXY Renew 2026-10-15, e2e p3 F013); one outside the folder is refused before any effect.
        if ((Path.IsPathRooted(relative) && !Path.IsPathFullyQualified(relative)) || relative.Contains('\0'))
            throw Error("invalid_path");
        string full = Path.GetFullPath(Path.Combine(root, relative.Replace('/', Path.DirectorySeparatorChar)));
        if (!full.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase)
            && !string.Equals(full, root, StringComparison.OrdinalIgnoreCase))
            throw string.Equals(root, _root, StringComparison.OrdinalIgnoreCase)
                ? OutsideTheSandbox(takesFolder)
                : Error("path_outside_folder");
        if (string.Equals(root, _root, StringComparison.OrdinalIgnoreCase) && IsReserved(full)) throw Error("path_reserved");
        EnsureSafePathIn(root, full, allowMissingLeaf);
        return full;
    }

    private void EnsureSafePath(string path, bool allowMissingLeaf) =>
        EnsureSafePathIn(_root, path, allowMissingLeaf);

    private static void EnsureSafePathIn(string root, string path, bool allowMissingLeaf)
    {
        string current = root;
        string relative = Path.GetRelativePath(root, path);
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

    private void Prune()
    {
        DateTimeOffset now = _time.GetUtcNow();
        foreach (string key in _handles.Where(pair => now - pair.Value.IssuedAt > HandleLifetime)
            .Select(static pair => pair.Key).ToArray()) _handles.Remove(key);
    }

    private bool IsReserved(string path) =>
        path.StartsWith(_backups + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase)
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

    // A failure once the file was already written, moved or copied: the change may be on disk.
    private static FilesystemProviderException AfterEffect(string code) => new(code) { EffectMayHaveOccurred = true };

    // A path outside the working folder: where the operation takes a folder, the refusal says how to name the person's.
    private static FilesystemProviderException OutsideTheSandbox(bool takesFolder) =>
        new("path_outside_sandbox")
        {
            Result = takesFolder
                ? ExternalJson.Create(writer =>
                {
                    writer.WriteStartObject();
                    writer.WriteString("next", "without folder, relativePath is read inside your working folder; a "
                        + "folder of the person's needs folder (desktop, documents, downloads, or home for "
                        + "C:\\Users\\<name>\\...) with the rest of the path in relativePath");
                    writer.WriteEndObject();
                })
                : null,
        };

    // What a refused write saw: whether the file is there, where, and whether the call appended.
    private static FilesystemProviderException WriteRefused(string code, string path, bool exists, bool append) =>
        new(code)
        {
            Result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteBoolean("exists", exists);
                writer.WriteString("fullPath", Path.GetFullPath(path));
                writer.WriteBoolean("append", append);
                writer.WriteEndObject();
            }),
        };

    private sealed record Handle(string Path, string Root, DateTime LastWriteUtc, long Size, DateTimeOffset IssuedAt);
}
