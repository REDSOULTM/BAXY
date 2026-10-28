using System.Collections.Concurrent;
using System.Diagnostics;
using System.IO.Enumeration;
using System.Security.Cryptography;
using System.Text;
using System.Text.Encodings.Web;
using System.Text.Json;
using Baxy.Providers.Windows.External;
using Baxy.Providers.Windows.Infrastructure;

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
    private readonly IRecycleBin _recycleBin;

    public LocalFilesystemProvider(string rootDirectory)
        : this(rootDirectory, WindowsRecycleBin.Instance)
    {
    }

    internal LocalFilesystemProvider(string rootDirectory, IRecycleBin recycleBin)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(rootDirectory);
        _recycleBin = recycleBin ?? throw new ArgumentNullException(nameof(recycleBin));
        _root = Path.GetFullPath(rootDirectory);
        _backups = Path.Combine(_root, ".backups");
        Directory.CreateDirectory(_root);
        Directory.CreateDirectory(_backups);
        _gate = RootLocks.GetOrAdd(_root, static _ => new object());
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
            // Holdout v6 (V6F010): a part of a name is also its words whatever separates them (SpokenFileNames).
            string[] matching = Directory.EnumerateFileSystemEntries(_root, "*", options)
                .Where(path => !IsReserved(path)
                    && (Path.GetFileName(path).Contains(normalized, StringComparison.OrdinalIgnoreCase)
                        || SpokenFileNames.Contains(Path.GetFileName(path), normalized)))
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
        (string root, relativePath) = RootFor(folder, relativePath);
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
        string calledPath = relativePath;
        (string root, relativePath) = RootFor(folder, relativePath);
        string normalizedText = NormalizeText(text, MaximumTextBytes, allowEmpty: true);
        lock (_gate)
        {
            string path = ResolveIn(root, relativePath, allowMissingLeaf: true, takesFolder: true);
            if (Directory.Exists(path)) throw Error("destination_is_directory");
            bool exists = File.Exists(path);
            // Renew al máximo (w5, E024): «añade a notas.txt, en la carpeta BAXY-bench» came with the subfolder
            // left out, and the append made a new home\notas.txt beside the person's. An append presupposes the file:
            // missing here and found below the same folder, nothing is written and the places are told.
            if (append && !exists && SameNameBelow(root, path) is { Length: > 0 } elsewhere)
                throw AppendTargetElsewhere(path, elsewhere, root, folder);
            byte[] previous = [];
            if (exists && append)
            {
                if (new FileInfo(path).Length > MaximumAppendTargetBytes) throw Error("file_too_large");
                previous = File.ReadAllBytes(path);
                // FT/proveedores goal (review of receipts): a file with no byte order mark that is not UTF-8 (ANSI) took
                // the new line in UTF-8, its accents garbled next to the old ones, and was told verified; file.edit
                // refuses such a file, and so does an append.
                if (TextFileEncoding.DecodeExactly(previous) is null) throw Error("known_text_encoding_unsupported");
            }
            byte[] bytes = append
                ? [.. previous, .. TextFileEncoding.EncodeAppended(previous, normalizedText)]
                : StrictUtf8.GetBytes(normalizedText);
            string desiredHash = Hex(SHA256.HashData(bytes));
            string? current = !exists ? null : append ? Hex(SHA256.HashData(previous)) : HashFile(path);
            if (current is not null && string.Equals(current, desiredHash, StringComparison.Ordinal))
                return WhereWritten(Mutation(path, root, reachedState: true, previousVersionRecycled: false), root, path);
            bool conflict = current is null
                ? expectedSha256 is not null
                : append
                    ? expectedSha256 is not null && !string.Equals(current, expectedSha256, StringComparison.Ordinal)
                    : !IsHash(expectedSha256) || !string.Equals(current, expectedSha256, StringComparison.Ordinal);
            // Holdout v6 V6E041 (aid overwrite_guard): what a refused replacement of a file there would lose; one under
            // the file's own hash asks the person first in normal mode (FilesystemHandler's preflight, ReplacementAsksFirst).
            TextLoss? loss = conflict && current is not null && !append && ModelAids.On(ModelAids.OverwriteGuard)
                ? LossOf(path, normalizedText)
                : null;
            // BAXY Renew (notebook): a hash expected of a file that is not there is no other version of it.
            if (conflict)
            {
                throw WriteRefused(
                    current is null ? "expected_hash_for_missing_file" : "version_conflict", path, exists, append,
                    current, current is null ? 0 : append ? previous.Length : new FileInfo(path).Length,
                    replaceOrAppend: current is not null && !append && !IsHash(expectedSha256),
                    loss: loss is null ? null : new LossTold(loss, calledPath, folder, text));
            }

            // A refused write leaves nothing behind: the folder of a new file is made only now.
            EnsureHandleRoom();
            string? folderCreated = FirstMissingFolder(root, Path.GetDirectoryName(path)!);
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            EnsureSafePathIn(root, Path.GetDirectoryName(path)!, allowMissingLeaf: false);
            string temporary = Path.Combine(
                Path.GetDirectoryName(path)!, ".baxy-write-" + Guid.NewGuid().ToString("N") + ".tmp");
            bool recycled = false, keepNewText = false;
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
                    try
                    {
                        File.Move(temporary, path);
                    }
                    catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
                    {
                        // Renew al máximo (w8): the previous version was in the bin and the new text, deleted with
                        // the temporary file, was lost with a bare filesystem_io_failed. The new text stays, named.
                        keepNewText = true;
                        throw NewTextKept(temporary, root);
                    }
                }
                else
                {
                    File.Move(temporary, path);
                }
            }
            finally
            {
                if (!keepNewText && File.Exists(temporary)) File.Delete(temporary);
            }
            if (!string.Equals(HashFile(path), desiredHash, StringComparison.Ordinal))
                throw AfterEffect("verification_failed");
            return WhereWritten(
                Mutation(path, root, reachedState: false, previousVersionRecycled: recycled) with
                {
                    Created = !exists,
                    FolderCreated = folderCreated,
                },
                root, path);
        }
    }

    // E024 (pc-ayudas): a write into the working folder says so, and a folder in the person's home named as the path's
    // first part is told beside it (only read: nothing is moved, nothing refused, the model chooses what to do).
    private FilesystemMutationResult WhereWritten(FilesystemMutationResult result, string root, string path)
    {
        if (!ModelAids.On(ModelAids.WorkFolder) || !string.Equals(root, _root, StringComparison.OrdinalIgnoreCase))
            return result;
        string[] parts = Path.GetRelativePath(_root, path)
            .Split(Path.DirectorySeparatorChar, StringSplitOptions.RemoveEmptyEntries);
        string? sameName = null;
        if (parts.Length > 1)
        {
            try
            {
                // Al máximo, flujos: a known folder by the name a person gives it is where Windows keeps it («Imágenes»
                // is Pictures, or OneDrive's), never a «home\Imágenes» that does not exist.
                string candidate = KnownFolderNames.TryGetValue(Fold(parts[0]), out string? known)
                    ? KnownFolderPath(known)
                    : Path.Combine(RootFor("home"), parts[0]);
                if (Directory.Exists(candidate) && !Inside(_root, candidate)
                    && !string.Equals(candidate, _root, StringComparison.OrdinalIgnoreCase))
                    sameName = candidate;
            }
            catch (FilesystemProviderException) { }
        }

        return result with { InWorkFolder = true, SameNameInHome = sameName };
    }

    /// <summary>
    /// The sandbox root, or one of the person's known folders when the
    /// catalog argument names it. Known folders never use the sandbox's
    /// backups; the same reparse-point and traversal checks apply.
    /// </summary>
    // FT/proveedores goal (e2e E019): a full path with no folder is the place the person said, so it is read inside the
    // known folder it lies in, the working folder first. Refused as outside the working folder, the model retried
    // with folder home and the path cut to its last part («proyecto»), and the folder was made in the wrong place.
    // Al máximo, flujos (P263, 26 of 27 runs: «Documentos/Proyectos» with no folder was made in the working folder): a
    // relative path whose first part names a known folder the catalog's folder takes is that folder, as folder would
    // name it, with the rest of the path inside it.
    private (string Root, string RelativePath) RootFor(string? folder, string relativePath)
    {
        if (folder is null && !Path.IsPathFullyQualified(relativePath ?? string.Empty)
            && (relativePath ?? string.Empty).Split(['/', '\\'], 2) is [var first, var rest]
            && !string.IsNullOrWhiteSpace(rest)
            && KnownFolderNames.TryGetValue(Fold(first), out string? named)
            && named is "desktop" or "documents" or "downloads")
            return (RootFor(named), rest);
        if (folder is not null || !Path.IsPathFullyQualified(relativePath ?? string.Empty))
            return (RootFor(folder), relativePath!);
        // ResolveIn refuses it the same way; here it must not reach GetFullPath, which throws on it.
        if (relativePath!.Contains('\0')) throw Error("invalid_path");
        string full = Path.GetFullPath(relativePath);
        if (Inside(full, _root)) return (_root, relativePath);
        foreach (string known in (string[])["desktop", "documents", "downloads", "home"])
        {
            string root;
            try { root = RootFor(known); }
            catch (FilesystemProviderException) { continue; }
            if (Inside(full, root)) return (root, relativePath);
        }

        return (_root, relativePath);
    }

    // The person's known folders by the names a person gives them (PersonFolders.Names). The catalog's folder takes
    // desktop, documents and downloads; pictures, music and videos are only told.
    private static IReadOnlyDictionary<string, string> KnownFolderNames => PersonFolders.Names;

    private static string Fold(string value) => PersonFolders.Fold(value);

    private static bool Inside(string full, string root) =>
        full.StartsWith(root.TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar,
            StringComparison.OrdinalIgnoreCase);

    /// <summary>Where each known folder of the person's is (tests point them away from the real profile).</summary>
    internal Func<string, string> KnownFolderPath { get; init; } = static folder =>
        PersonFolders.Path(folder) ?? PersonFolders.Path("home")!;

    /// <summary>BAXY's own state (<see cref="BaxyPrivateArea"/>); tests point it at a temporary folder.</summary>
    internal IReadOnlyList<string> PrivateRoots { get; init; } = BaxyPrivateArea.DefaultRoots();

    /// <summary>The folders Windows runs at sign-in (<see cref="AutostartArea"/>); tests point it at a temporary folder.</summary>
    internal IReadOnlyList<string> AutostartRoots { get; init; } = AutostartArea.DefaultRoots();

    private string RootFor(string? folder)
    {
        if (folder is null) return _root;
        if (folder is not ("desktop" or "documents" or "downloads" or "home")) throw Error("invalid_folder");
        string path = KnownFolderPath(folder);
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
            // FT/proveedores goal (review of receipts): «notas.txt» renamed «Notas.txt» is the same file under another
            // spelling (the file system ignores case), not a destination that exists.
            bool caseOnly = move
                && string.Equals(Path.GetFullPath(source), Path.GetFullPath(destination), StringComparison.OrdinalIgnoreCase)
                && !string.Equals(Path.GetFullPath(source), Path.GetFullPath(destination), StringComparison.Ordinal);
            if (!caseOnly && (File.Exists(destination) || Directory.Exists(destination))) throw Error("destination_exists");
            EnsureHandleRoom();
            Directory.CreateDirectory(Path.GetDirectoryName(destination)!);
            EnsureSafePath(Path.GetDirectoryName(destination)!, allowMissingLeaf: false);
            if (move) File.Move(source, destination);
            else File.Copy(source, destination);
            string shownName = Path.GetFileName(destination);
            bool renamed = !caseOnly || Directory.EnumerateFiles(Path.GetDirectoryName(destination)!, shownName)
                .Any(file => string.Equals(Path.GetFileName(file), shownName, StringComparison.Ordinal));
            if (!File.Exists(destination)
                || !string.Equals(HashFile(destination), sourceHash, StringComparison.Ordinal)
                || (move && !caseOnly && File.Exists(source))
                || !renamed)
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
            DateTimeOffset.UtcNow);
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
        // Revisión de calidad (archivos): a «:» past the folder names a stream of a file («descarga.exe:Zone.Identifier»,
        // the mark SmartScreen reads), never a file of the person's; it reached the Recycle Bin as one.
        if (full.AsSpan(root.Length).Contains(':')) throw Error("invalid_path");
        // Revisión de calidad (archivos): the backups are reserved whichever folder names them (through home too).
        if (IsReserved(full)) throw Error("path_reserved");
        // Renew al máximo (B-SYS-1): BAXY's own state is not one of the person's files, whichever folder names it; the
        // working folder, inside it, is this provider's own.
        bool inWorkingFolder = string.Equals(full, _root, StringComparison.OrdinalIgnoreCase)
            || full.StartsWith(_root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase);
        if (!inWorkingFolder && BaxyPrivateArea.Holds(PrivateRoots, full)) throw Error("path_reserved");
        // Revisión de fase 3: a known folder resolved here is written (file.write, filesystem.create.directory), never
        // where Windows runs it at sign-in.
        if (!inWorkingFolder && AutostartArea.Holds(AutostartRoots, full)) throw Error("path_autostart");
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
        DateTimeOffset now = DateTimeOffset.UtcNow;
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

    // The outermost folder of directory (inside root) that is not there yet, relative to root; null when all are.
    internal static string? FirstMissingFolder(string root, string directory)
    {
        string? missing = null;
        for (string? current = Path.GetFullPath(directory);
             current is not null && IsStrictlyInside(root, current) && !Directory.Exists(current);
             current = Path.GetDirectoryName(current))
            missing = current;
        return missing is null ? null : Path.GetRelativePath(root, missing);
    }

    private static bool IsStrictlyInside(string root, string path)
    {
        string relative = Path.GetRelativePath(Path.GetFullPath(root), path);
        return relative != "." && !relative.StartsWith("..", StringComparison.Ordinal) && !Path.IsPathRooted(relative);
    }

    // The previous version went to the Recycle Bin and the new one could not take its place: both are kept and named.
    private static FilesystemProviderException NewTextKept(string temporary, string root) =>
        new("write_not_completed_previous_recycled")
        {
            EffectMayHaveOccurred = true,
            Result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", 1);
                writer.WriteBoolean("previousVersionRecycled", true);
                writer.WriteString("newTextFile", Path.GetRelativePath(root, temporary));
                writer.WriteString("next", "the previous version is in the Recycle Bin and the new text is in newTextFile "
                    + "beside it; another program may hold the name now; tell the person both places");
                writer.WriteEndObject();
            }),
        };

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

    // What a refused write saw: whether the file is there, where, and whether the call appended. Al máximo, flujos: and
    // the version of it the refusal was decided on (its SHA-256 and size), so a replace that came without the hash goes
    // straight in a second call instead of a file.read first; its previous version still goes to the Recycle Bin. Hallazgo
    // E030 (w9-sha): that second call asks the person first, since a hash only a refusal told is no sighting (ToldVersions).
    // Holdout v6 V6E041: a write that came without append and without the hash says both ways on.
    // Holdout v6 V6E041 (overwrite_guard): a write that would replace text it keeps little of says how much the file has
    // (lines and characters, or its bytes when it is no text), how many of its lines the text keeps, and both ways on.
    private static FilesystemProviderException WriteRefused(
        string code, string path, bool exists, bool append, string? currentSha256 = null, long size = 0,
        bool replaceOrAppend = false, LossTold? loss = null) =>
        new(code)
        {
            Result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteBoolean("exists", exists);
                writer.WriteString("fullPath", Path.GetFullPath(path));
                writer.WriteBoolean("append", append);
                if (currentSha256 is not null)
                {
                    writer.WriteString("currentSha256", currentSha256);
                    writer.WriteNumber("size", size);
                }
                if (loss is not null)
                {
                    if (loss.Loss.Lines is int lines)
                    {
                        writer.WriteNumber("lines", lines);
                        writer.WriteNumber("characters", loss.Loss.Characters);
                        writer.WriteNumber("linesKept", loss.Loss.LinesKept);
                    }
                    writer.WriteString("next", LossNext(Path.GetFileName(path), size, loss));
                }
                else if (replaceOrAppend && ModelAids.On(ModelAids.ReplaceOrAppend))
                {
                    writer.WriteString("next", $"nothing was written: {Path.GetFileName(path)} is already there; "
                        + "file_write with append true adds the text as a new line at its end and keeps what it has, and "
                        + "with expectedSha256 (currentSha256) it replaces all the file has with the text, its previous "
                        + "version to the Recycle Bin");
                }
                writer.WriteEndObject();
            }),
        };

    /// <summary>
    /// Holdout v6 V6E041/V6E048 (overwrite_guard): whether this replacement, under the file's current hash, would lose
    /// the file's text (TextLoss), so in normal mode the person is asked first, bound to the call (FilesystemHandler's
    /// preflight); in bypass it goes straight. Read only.
    /// </summary>
    public bool ReplacementAsksFirst(string relativePath, string text, string? expectedSha256, string? folder)
    {
        if (!ModelAids.On(ModelAids.OverwriteGuard) || !IsHash(expectedSha256)) return false;
        try
        {
            (string root, string inner) = RootFor(folder, relativePath);
            string normalizedText = NormalizeText(text, MaximumTextBytes, allowEmpty: true);
            lock (_gate)
            {
                string path = ResolveIn(root, inner, allowMissingLeaf: true, takesFolder: true);
                if (!File.Exists(path)) return false;
                string current = HashFile(path);
                string desired = Hex(SHA256.HashData(StrictUtf8.GetBytes(normalizedText)));
                return string.Equals(current, expectedSha256, StringComparison.Ordinal)
                    && !string.Equals(current, desired, StringComparison.Ordinal)
                    && LossOf(path, normalizedText) is not null;
            }
        }
        catch (Exception exception) when (exception is FilesystemProviderException or IOException
            or UnauthorizedAccessException or ArgumentException or NotSupportedException)
        {
            return false;
        }
    }

    // What a file has that a replacement by text would lose (TextLoss), or no lines for a file that is no text (bytes
    // that are no text in a known encoding, or past the size an append reads).
    private static TextLoss? LossOf(string path, string text)
    {
        long size = new FileInfo(path).Length;
        if (size == 0) return null;
        if (size > MaximumAppendTargetBytes) return new TextLoss(null, 0, 0);
        string? before = TextFileEncoding.DecodeExactly(File.ReadAllBytes(path));
        return before is null || before.Contains(' ') ? new TextLoss(null, 0, 0) : TextLoss.Of(before, text);
    }

    // The receipt's sentence: what the file has, that this call replaces all of it, the call that appends (a file that
    // is text), how a replacement the person asked for goes on, and that the person's words pick the way: the yes to a
    // replacement is BAXY's to ask (holdout v6 V6E041/V6E048, practice E030: after «in normal mode it asks the person's
    // yes first» the model asked «¿reemplazo o agrego?» itself in 7 of 7 runs, «agrégale la línea» and «sobrescribe»
    // alike, and never made either call).
    private static string LossNext(string name, long size, LossTold told)
    {
        TextLoss loss = told.Loss;
        string what = loss.Lines is int lines
            ? $"{lines} {(lines == 1 ? "line" : "lines")} ({loss.Characters} {(loss.Characters == 1 ? "character" : "characters")})"
            : $"{size} {(size == 1 ? "byte" : "bytes")} that are not text";
        string keeps = loss.Lines is null ? string.Empty
            : loss.LinesKept == 0 ? ", which keeps none of its lines"
            : $", which keeps {loss.LinesKept} of its {loss.Lines} lines";
        var next = new StringBuilder(
            $"nothing was written: {name} is already there with {what}, and this call would replace all of it with "
            + $"the text{keeps}.");
        if (loss.Lines is not null)
        {
            next.Append(" If the person asked to add the text: ")
                .Append(AppendCall(told))
                .Append(", a new line at its end that keeps what it has.");
        }
        next.Append(" If the person asked to replace all it has: ")
            .Append("the same call with expectedSha256 (currentSha256)")
            .Append(". Their words pick the call, so ask them nothing: in normal mode BAXY itself asks their yes "
                + "before a replacement");
        return next.ToString();
    }

    // The exact file_write that appends, with this call's own arguments; a long text is named, not repeated.
    private const int MaximumTextRepeated = 300;
    private static readonly JsonWriterOptions CallWriting = new() { Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping };

    private static string AppendCall(LossTold told)
    {
        if (told.Text.Length > MaximumTextRepeated)
        {
            return told.Folder is null
                ? "file_write with the same relativePath and text, and append true"
                : "file_write with the same relativePath, folder and text, and append true";
        }

        using var buffer = new MemoryStream();
        using (var writer = new Utf8JsonWriter(buffer, CallWriting))
        {
            writer.WriteStartObject();
            writer.WriteString("relativePath", told.RelativePath);
            if (told.Folder is not null) writer.WriteString("folder", told.Folder);
            writer.WriteString("text", told.Text);
            writer.WriteBoolean("append", true);
            writer.WriteEndObject();
        }
        return "file_write " + Encoding.UTF8.GetString(buffer.ToArray());
    }

    // A loss as a version_conflict tells it: the call's own path, folder and text (the call still needs the hash).
    private sealed record LossTold(TextLoss Loss, string RelativePath, string? Folder, string Text);

    // Renew al máximo (w5, E024): how far an append to a missing file looks for one of that name below its folder.
    private const int SameNameDepth = 6;
    private const int SameNameShown = 5;
    private static readonly TimeSpan SameNameBudget = TimeSpan.FromSeconds(1);

    // Files named like the leaf of path below root (hidden, system and linked folders left out, BAXY's backups too),
    // the shallowest first; a walk past its budget gives what it found so far, and none found claims nothing. A name of
    // the same words otherwise separated is one of that name (holdout v6 V6F010, SpokenFileNames).
    private string[] SameNameBelow(string root, string path)
    {
        string name = Path.GetFileName(path);
        if (name.Length == 0 || name.IndexOfAny(['*', '?']) >= 0) return [];
        long started = Stopwatch.GetTimestamp();
        var options = new EnumerationOptions
        {
            RecurseSubdirectories = true,
            MaxRecursionDepth = SameNameDepth,
            AttributesToSkip = FileAttributes.Hidden | FileAttributes.System | FileAttributes.ReparsePoint,
            IgnoreInaccessible = true,
        };
        var found = new List<string>();
        try
        {
            var walk = new FileSystemEnumerable<string>(root,
                (ref FileSystemEntry entry) => entry.ToFullPath(), options)
            {
                ShouldIncludePredicate = (ref FileSystemEntry entry) =>
                    !entry.IsDirectory && (entry.FileName.Equals(name, StringComparison.OrdinalIgnoreCase)
                        || SpokenFileNames.Same(entry.FileName.ToString(), name)),
                ShouldRecursePredicate = (ref FileSystemEntry _) => Stopwatch.GetElapsedTime(started) < SameNameBudget,
            };
            foreach (string file in walk)
            {
                if (IsReserved(file) || string.Equals(file, path, StringComparison.OrdinalIgnoreCase)) continue;
                found.Add(Path.GetRelativePath(root, file).Replace(Path.DirectorySeparatorChar, '/'));
                if (found.Count == SameNameShown) break;
            }
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException) { }

        return [.. found.OrderBy(static item => item.Count(character => character == '/'))
            .ThenBy(static item => item, StringComparer.OrdinalIgnoreCase)];
    }

    // Holdout v6 V6E044 (cien s1 and s2): told that «a file of that name is in BAXY-bench/gastos.txt, and file_write
    // with that relativePath and the same folder appends to it», the model answered «gastos.txt está en mi carpeta de
    // trabajo» and wrote nothing. With aid «append_elsewhere_call» the file is said by its full path and whose it is (the
    // person's, or BAXY's own working folder's), and the append as the call that makes it; a call whose folder came from
    // the path's first part (no folder given, a known folder's name) keeps the sentence of before.
    private FilesystemProviderException AppendTargetElsewhere(string path, string[] elsewhere, string root, string? folder) =>
        new("append_target_missing")
        {
            Result = ExternalJson.Create(writer =>
            {
                writer.WriteStartObject();
                writer.WriteBoolean("exists", false);
                writer.WriteString("fullPath", Path.GetFullPath(path));
                writer.WriteBoolean("append", true);
                writer.WriteStartArray("sameNameIn");
                foreach (string item in elsewhere) writer.WriteStringValue(item);
                writer.WriteEndArray();
                bool work = string.Equals(root, _root, StringComparison.OrdinalIgnoreCase);
                if (ModelAids.On(ModelAids.AppendElsewhereCall) && (folder is not null || work))
                {
                    string name = Path.GetFileName(path);
                    bool one = elsewhere.Length == 1;
                    IEnumerable<string> full = elsewhere.Select(item =>
                        Path.Combine(root, item.Replace('/', Path.DirectorySeparatorChar)));
                    string whose = work ? "in BAXY's own working folder"
                        : $"{(one ? "a file" : "files")} of the person's, not of BAXY's own working folder";
                    writer.WriteString("next", $"nothing was written: {name} is not in "
                        + $"{Path.GetDirectoryName(Path.GetFullPath(path))}; "
                        + $"{(one ? "the file of that name is" : "the files of that name are")} {string.Join(" and ", full)}, "
                        + $"{whose}: to add the text at {(one ? "its end" : "the end of one")}, call file_write again with "
                        + "relativePath " + string.Join(" or ", elsewhere.Select(item => $"\"{item}\""))
                        + (folder is null ? " and no folder" : $" and folder \"{folder}\"")
                        + $" and append true; without append, a new {name} is made here");
                }
                else if (ModelAids.On(ModelAids.AppendElsewhere))
                {
                    string name = Path.GetFileName(path);
                    writer.WriteString("next", $"nothing was written: {name} is not in {Path.GetDirectoryName(Path.GetFullPath(path))}; "
                        + $"a file of that name is in {string.Join(" and ", elsewhere)}, and file_write with that "
                        + $"relativePath and the same folder appends to it; without append, a new {name} is made here");
                }
                writer.WriteEndObject();
            }),
        };

    private sealed record Handle(string Path, string Root, DateTime LastWriteUtc, long Size, DateTimeOffset IssuedAt);
}
