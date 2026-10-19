using System.Text.Json;

namespace Baxy.Providers.Windows.Filesystem;

public sealed record FilesystemEntry(
    string ResourceId,
    string Name,
    string Kind,
    long Size,
    DateTimeOffset LastWriteUtc,
    string? Sha256);

public sealed record FilesystemListResult(
    IReadOnlyList<FilesystemEntry> Entries,
    int Count,
    // BAXY Renew (notebook): the folder a list read and how many entries it holds, so the receipt says where and
    // whether the limit left some out.
    string? FullPath = null,
    int? TotalCount = null);

public sealed record FilesystemTextResult(
    string ResourceId,
    string Text,
    int Utf8Bytes,
    string Sha256);

public sealed record FilesystemMutationResult(
    string ResourceId,
    string Name,
    string Kind,
    long Size,
    string? Sha256,
    bool ReachedState,
    bool? PreviousVersionRecycled = null,
    // Where it is now, as the provider resolved it: what the result can say of the place (falsedades p4 F013: without
    // it the model told the folder it had been asked for, not the one written).
    string? FullPath = null,
    // FT/proveedores goal (review of receipts): the file was not there and this write made it (an append included):
    // «añadí a tu lista» cannot be said of a list that did not exist here.
    bool Created = false,
    // E024 (pc-ayudas): a file.write that went to BAXY's own working folder (no folder, a relative path) says so, and
    // a folder of the person's home with the same first part of the path is a fact beside it, never a redirection.
    bool InWorkFolder = false,
    string? SameNameInHome = null);

public sealed record BackupReceipt(
    string BackupId,
    long Size,
    string Sha256,
    bool Verified);

public sealed record BackupListResult(
    IReadOnlyList<BackupReceipt> Backups,
    int Count,
    // Ronda final 7: how many backups there are, the newest «Count» of them listed.
    int TotalCount);

public interface IFilesystemProvider
{
    FilesystemListResult List(string relativeDirectory, int limit);
    FilesystemListResult Search(string query, int limit);
    FilesystemTextResult ReadText(string resourceId, int maximumBytes);
    FilesystemEntry Hash(string resourceId);

    /// <summary>
    /// Creates a directory in the sandbox, or rooted at a known folder ("desktop", "documents", "downloads"); null
    /// keeps the sandbox root.
    /// </summary>
    FilesystemMutationResult CreateDirectory(string relativePath, string? folder);

    /// <summary>
    /// Writes a text file in the sandbox or in a known folder: replacing an existing one takes its current SHA-256 and
    /// sends its previous version to the Recycle Bin first; appending keeps what is there.
    /// </summary>
    FilesystemMutationResult WriteText(
        string relativePath,
        string text,
        string? expectedSha256,
        string? folder = null,
        bool append = false);
    FilesystemMutationResult Transfer(
        string resourceId,
        string destinationRelativePath,
        string expectedSha256,
        bool move);
    BackupReceipt CreateBackup(string resourceId, string expectedSha256);
    BackupListResult ListBackups(int limit);
    BackupReceipt VerifyBackup(string backupId);
    FilesystemMutationResult RestoreBackup(string backupId, string destinationRelativePath);
}

public class FilesystemProviderException(string code) : Exception(code)
{
    public string Code { get; } = code;

    /// <summary>
    /// What the refused call had observed, or what it can do instead, when that helps the model act (where, whether
    /// it exists, its next step).
    /// </summary>
    public JsonElement? Result { get; init; }

    /// <summary>
    /// Round A: the call already wrote, moved or copied when it failed (a read-back that did not match; ronda B: or the
    /// handle of what it changed that could not be issued or resolved), so the change may be on disk; a refusal before
    /// any change leaves it false.
    /// </summary>
    public bool EffectMayHaveOccurred { get; init; }
}
