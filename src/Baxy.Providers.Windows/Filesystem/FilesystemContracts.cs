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
    int Count);

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
    bool ReachedState);

public sealed record FilesystemTrashPreparation(
    string TrashId,
    string ReviewLabel,
    string Kind,
    long Size);

public sealed record FilesystemTrashReceipt(
    string RestoreId,
    string ReviewLabel,
    bool Trashed);

public sealed record BackupReceipt(
    string BackupId,
    long Size,
    string Sha256,
    bool Verified);

public sealed record BackupListResult(
    IReadOnlyList<BackupReceipt> Backups,
    int Count);

public interface IFilesystemProvider
{
    FilesystemListResult List(string relativeDirectory, int limit);
    FilesystemListResult Search(string query, int limit);
    FilesystemTextResult ReadText(string resourceId, int maximumBytes);
    FilesystemEntry Hash(string resourceId);
    FilesystemMutationResult CreateDirectory(string relativePath);
    FilesystemMutationResult WriteText(
        string relativePath,
        string text,
        string? expectedSha256);
    FilesystemMutationResult Transfer(
        string resourceId,
        string destinationRelativePath,
        string expectedSha256,
        bool move);
    FilesystemTrashPreparation PrepareTrash(string resourceId);
    FilesystemTrashReceipt CommitTrash(string trashId, string reviewLabel);
    FilesystemMutationResult Restore(string restoreId);
    BackupReceipt CreateBackup(string resourceId, string expectedSha256);
    BackupListResult ListBackups(int limit);
    BackupReceipt VerifyBackup(string backupId);
    FilesystemMutationResult RestoreBackup(string backupId, string destinationRelativePath);
}

public class FilesystemProviderException(string code) : Exception(code)
{
    public string Code { get; } = code;
}
