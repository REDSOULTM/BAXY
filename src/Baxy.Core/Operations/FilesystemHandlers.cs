using System.Buffers;
using System.Text.Json;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Filesystem;

namespace Baxy.Core.Operations;

internal static class FilesystemHandlers
{
    public static IOperationHandler[] Create(IFilesystemProvider provider) =>
    [
        new FilesystemHandler("backup.create", provider),
        new FilesystemHandler("backup.list", provider),
        new FilesystemHandler("backup.restore", provider),
        new FilesystemHandler("backup.verify", provider),
        new FilesystemHandler("filesystem.copy", provider),
        new FilesystemHandler("filesystem.create.directory", provider),
        new FilesystemHandler("filesystem.hash", provider),
        new FilesystemHandler("filesystem.list", provider),
        new FilesystemHandler("filesystem.move", provider),
        new FilesystemHandler("filesystem.read.text", provider),
        new FilesystemHandler("filesystem.search", provider),
        new FilesystemHandler("filesystem.trash.commit", provider),
        new FilesystemHandler("filesystem.trash.prepare", provider),
        new FilesystemHandler("filesystem.trash.restore", provider),
        new FilesystemHandler("filesystem.write.text", provider),
    ];
}

internal sealed class FilesystemHandler(string operation, IFilesystemProvider provider)
    : IOperationHandler
{
    private readonly IFilesystemProvider _provider =
        provider ?? throw new ArgumentNullException(nameof(provider));

    public OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition(operation);

    public ValueTask<OperationOutcome> ExecuteAsync(
        OperationInvocation invocation,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        try
        {
            JsonElement arguments = invocation.Arguments;
            JsonElement result = operation switch
            {
                "backup.create" => VerifiedBackup(_provider.CreateBackup(
                    RequiredString(arguments, "resourceId"), RequiredString(arguments, "expectedSha256"))),
                "backup.list" => FilesystemResultJson.BackupList(_provider.ListBackups(
                    OptionalInt(arguments, "limit") ?? 20)),
                "backup.verify" => FilesystemResultJson.Backup(_provider.VerifyBackup(
                    RequiredString(arguments, "backupId"))),
                "backup.restore" => VerifiedMutation(_provider.RestoreBackup(
                    RequiredString(arguments, "backupId"),
                    RequiredString(arguments, "destinationRelativePath"))),
                "filesystem.list" => FilesystemResultJson.List(_provider.List(
                    OptionalString(arguments, "relativeDirectory") ?? string.Empty,
                    OptionalInt(arguments, "limit") ?? 50)),
                "filesystem.search" => FilesystemResultJson.List(_provider.Search(
                    arguments.GetProperty("query").GetString()!,
                    OptionalInt(arguments, "limit") ?? 50)),
                "filesystem.read.text" => FilesystemResultJson.Text(_provider.ReadText(
                    RequiredString(arguments, "resourceId"),
                    OptionalInt(arguments, "maximumBytes") ?? 1_048_576)),
                "filesystem.hash" => FilesystemResultJson.Entry(_provider.Hash(
                    RequiredString(arguments, "resourceId"))),
                "filesystem.create.directory" => VerifiedMutation(
                    _provider.CreateDirectory(
                        RequiredString(arguments, "relativePath"),
                        OptionalString(arguments, "folder"))),
                "filesystem.write.text" => VerifiedMutation(_provider.WriteText(
                    RequiredString(arguments, "relativePath"),
                    arguments.GetProperty("text").GetString()!,
                    OptionalString(arguments, "expectedSha256"),
                    OptionalString(arguments, "folder"))),
                "filesystem.copy" => VerifiedMutation(TransferResult(arguments, move: false)),
                "filesystem.move" => VerifiedMutation(TransferResult(arguments, move: true)),
                "filesystem.trash.prepare" => FilesystemResultJson.TrashPreparation(
                    _provider.PrepareTrash(RequiredString(arguments, "resourceId"))),
                "filesystem.trash.commit" => FilesystemResultJson.TrashReceipt(
                    _provider.CommitTrash(
                        RequiredString(arguments, "trashId"),
                        RequiredString(arguments, "reviewLabel"))),
                "filesystem.trash.restore" => VerifiedMutation(
                    _provider.Restore(RequiredString(arguments, "restoreId"))),
                _ => throw new InvalidOperationException("Unknown filesystem operation."),
            };
            return ValueTask.FromResult(OperationOutcome.Success(result));
        }
        catch (FilesystemProviderException exception)
        {
            return ValueTask.FromResult(OperationOutcome.Failure(exception.Code));
        }
    }

    private FilesystemMutationResult TransferResult(JsonElement arguments, bool move) =>
        _provider.Transfer(
            RequiredString(arguments, "resourceId"),
            RequiredString(arguments, "destinationRelativePath"),
            RequiredString(arguments, "expectedSha256"),
            move);

    private JsonElement VerifiedMutation(FilesystemMutationResult result)
    {
        if (result.Sha256 is not null)
        {
            FilesystemEntry hashed = _provider.Hash(result.ResourceId);
            if (!string.Equals(hashed.Sha256, result.Sha256, StringComparison.Ordinal))
            {
                throw new FilesystemProviderException("verification_failed");
            }
        }

        return FilesystemResultJson.Mutation(result);
    }

    private JsonElement VerifiedBackup(BackupReceipt result)
    {
        BackupReceipt verified = _provider.VerifyBackup(result.BackupId);
        if (!verified.Verified
            || !string.Equals(verified.Sha256, result.Sha256, StringComparison.Ordinal))
        {
            throw new FilesystemProviderException("verification_failed");
        }

        return FilesystemResultJson.Backup(result);
    }

    private static string RequiredString(JsonElement arguments, string name) =>
        arguments.GetProperty(name).GetString()!;

    private static string? OptionalString(JsonElement arguments, string name) =>
        arguments.TryGetProperty(name, out JsonElement value) && value.ValueKind != JsonValueKind.Null
            ? value.GetString() : null;

    private static int? OptionalInt(JsonElement arguments, string name) =>
        arguments.TryGetProperty(name, out JsonElement value) ? value.GetInt32() : null;
}

internal static class FilesystemResultJson
{
    public static JsonElement List(FilesystemListResult result) => Write(writer =>
    {
        writer.WritePropertyName("entries");
        writer.WriteStartArray();
        foreach (FilesystemEntry entry in result.Entries) WriteEntry(writer, entry);
        writer.WriteEndArray();
        writer.WriteNumber("count", result.Count);
    });

    public static JsonElement Entry(FilesystemEntry entry) =>
        Write(writer => WriteEntryProperties(writer, entry));

    public static JsonElement Text(FilesystemTextResult result) => Write(writer =>
    {
        writer.WriteString("resourceId", result.ResourceId);
        writer.WriteString("text", result.Text);
        writer.WriteNumber("utf8Bytes", result.Utf8Bytes);
        writer.WriteString("sha256", result.Sha256);
    });

    public static JsonElement Mutation(FilesystemMutationResult result) => Write(writer =>
    {
        writer.WriteString("resourceId", result.ResourceId);
        writer.WriteString("name", result.Name);
        writer.WriteString("kind", result.Kind);
        writer.WriteNumber("size", result.Size);
        if (result.Sha256 is null) writer.WriteNull("sha256"); else writer.WriteString("sha256", result.Sha256);
        writer.WriteBoolean("reachedState", result.ReachedState);
    });

    public static JsonElement TrashPreparation(FilesystemTrashPreparation result) => Write(writer =>
    {
        writer.WriteString("trashId", result.TrashId);
        writer.WriteString("reviewLabel", result.ReviewLabel);
        writer.WriteString("kind", result.Kind);
        writer.WriteNumber("size", result.Size);
    });

    public static JsonElement TrashReceipt(FilesystemTrashReceipt result) => Write(writer =>
    {
        writer.WriteString("restoreId", result.RestoreId);
        writer.WriteString("reviewLabel", result.ReviewLabel);
        writer.WriteBoolean("trashed", result.Trashed);
    });

    public static JsonElement Backup(BackupReceipt result) => Write(writer =>
    {
        writer.WriteString("backupId", result.BackupId);
        writer.WriteNumber("size", result.Size);
        writer.WriteString("sha256", result.Sha256);
        writer.WriteBoolean("verified", result.Verified);
    });

    public static JsonElement BackupList(BackupListResult result) => Write(writer =>
    {
        writer.WriteStartArray("backups");
        foreach (BackupReceipt backup in result.Backups)
        {
            writer.WriteStartObject();
            writer.WriteString("backupId", backup.BackupId);
            writer.WriteNumber("size", backup.Size);
            writer.WriteString("sha256", backup.Sha256);
            writer.WriteBoolean("verified", backup.Verified);
            writer.WriteEndObject();
        }
        writer.WriteEndArray();
        writer.WriteNumber("count", result.Count);
    });

    private static void WriteEntry(Utf8JsonWriter writer, FilesystemEntry entry)
    {
        writer.WriteStartObject();
        WriteEntryProperties(writer, entry);
        writer.WriteEndObject();
    }

    private static void WriteEntryProperties(Utf8JsonWriter writer, FilesystemEntry entry)
    {
        writer.WriteString("resourceId", entry.ResourceId);
        writer.WriteString("name", entry.Name);
        writer.WriteString("kind", entry.Kind);
        writer.WriteNumber("size", entry.Size);
        writer.WriteString("lastWriteUtc", entry.LastWriteUtc);
        if (entry.Sha256 is null) writer.WriteNull("sha256"); else writer.WriteString("sha256", entry.Sha256);
    }

    private static JsonElement Write(Action<Utf8JsonWriter> body)
    {
        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteNumber("version", 1);
            body(writer);
            writer.WriteEndObject();
        }
        using JsonDocument document = JsonDocument.Parse(buffer.WrittenMemory);
        return document.RootElement.Clone();
    }
}
