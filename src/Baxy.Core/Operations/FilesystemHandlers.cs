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
        new FilesystemHandler("file.write", provider),
        new FilesystemHandler("filesystem.copy", provider),
        new FilesystemHandler("filesystem.create.directory", provider),
        new FilesystemHandler("filesystem.list", provider),
        new FilesystemHandler("filesystem.move", provider),
        new FilesystemHandler("filesystem.read.text", provider),
        new FilesystemHandler("filesystem.search", provider),
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
                "filesystem.create.directory" => VerifiedMutation(
                    _provider.CreateDirectory(
                        RequiredString(arguments, "relativePath"),
                        OptionalString(arguments, "folder")),
                    OptionalString(arguments, "folder")),
                "file.write" => VerifiedMutation(_provider.WriteText(
                    RequiredString(arguments, "relativePath"),
                    arguments.GetProperty("text").GetString()!,
                    OptionalString(arguments, "expectedSha256"),
                    OptionalString(arguments, "folder"),
                    OptionalBoolean(arguments, "append")),
                    OptionalString(arguments, "folder")),
                "filesystem.copy" => VerifiedMutation(TransferResult(arguments, move: false)),
                "filesystem.move" => VerifiedMutation(TransferResult(arguments, move: true)),
                _ => throw new InvalidOperationException("Unknown filesystem operation."),
            };
            return ValueTask.FromResult(OperationOutcome.Success(result));
        }
        catch (FilesystemProviderException exception)
        {
            return ValueTask.FromResult(OperationOutcome.Failure(
                exception.Code, exception.Result, effectMayHaveOccurred: exception.EffectMayHaveOccurred));
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            // FT/proveedores goal (review of receipts): a file another program holds open (Excel with ventas.csv), or a
            // folder Windows guards (Controlled Folder Access), threw past this handler and ended the core (exit 70),
            // which the turn told as «pudo o no ocurrir». It is this operation's failure, named; a change may have
            // begun only for an operation that changes something.
            bool changes = operation is not ("backup.list" or "backup.verify" or "filesystem.list"
                or "filesystem.search" or "filesystem.read.text");
            bool inUse = exception is IOException && (exception.HResult & 0xFFFF) is 32 or 33;
            return ValueTask.FromResult(OperationOutcome.Failure(
                inUse ? "file_in_use" : exception is UnauthorizedAccessException ? "filesystem_access_denied"
                    : "filesystem_io_failed",
                effectMayHaveOccurred: changes));
        }
    }

    private FilesystemMutationResult TransferResult(JsonElement arguments, bool move) =>
        _provider.Transfer(
            RequiredString(arguments, "resourceId"),
            RequiredString(arguments, "destinationRelativePath"),
            RequiredString(arguments, "expectedSha256"),
            move);

    // Ronda 22 (r18 t4-c07, t1-c13): the receipt says which known folder it was made in, beside reachedState
    // (true when the folder or the same content was already there), so the reply can say where without guessing.
    private JsonElement VerifiedMutation(FilesystemMutationResult result, string? folder = null)
    {
        if (result.Sha256 is not null)
        {
            FilesystemEntry hashed;
            try
            {
                hashed = _provider.Hash(result.ResourceId);
            }
            catch (FilesystemProviderException exception) when (!result.ReachedState)
            {
                // The handle of what was just changed no longer resolves (resource_changed, path_not_found): the change
                // was made, and may be on disk.
                throw new FilesystemProviderException(exception.Code)
                {
                    Result = exception.Result,
                    EffectMayHaveOccurred = true,
                };
            }
            if (!string.Equals(hashed.Sha256, result.Sha256, StringComparison.Ordinal))
            {
                // The change was made unless the state was already there (round A: it was a clean failure).
                throw new FilesystemProviderException("verification_failed")
                {
                    EffectMayHaveOccurred = !result.ReachedState,
                };
            }
        }

        return FilesystemResultJson.Mutation(result, folder);
    }

    private JsonElement VerifiedBackup(BackupReceipt result)
    {
        BackupReceipt verified = _provider.VerifyBackup(result.BackupId);
        if (!verified.Verified
            || !string.Equals(verified.Sha256, result.Sha256, StringComparison.Ordinal))
        {
            // The backup was already copied into the backups folder.
            throw new FilesystemProviderException("verification_failed") { EffectMayHaveOccurred = true };
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

    private static bool OptionalBoolean(JsonElement arguments, string name) =>
        arguments.TryGetProperty(name, out JsonElement value) && value.ValueKind == JsonValueKind.True;
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
        if (result.FullPath is not null) writer.WriteString("fullPath", result.FullPath);
        if (result.TotalCount is int total)
        {
            writer.WriteNumber("totalCount", total);
            writer.WriteBoolean("hasMore", total > result.Count);
        }
    });

    public static JsonElement Text(FilesystemTextResult result) => Write(writer =>
    {
        writer.WriteString("resourceId", result.ResourceId);
        writer.WriteString("text", result.Text);
        writer.WriteNumber("utf8Bytes", result.Utf8Bytes);
        writer.WriteString("sha256", result.Sha256);
    });

    public static JsonElement Mutation(FilesystemMutationResult result, string? folder = null) => Write(writer =>
    {
        writer.WriteString("resourceId", result.ResourceId);
        writer.WriteString("name", result.Name);
        writer.WriteString("kind", result.Kind);
        writer.WriteNumber("size", result.Size);
        if (result.Sha256 is null) writer.WriteNull("sha256"); else writer.WriteString("sha256", result.Sha256);
        writer.WriteBoolean("reachedState", result.ReachedState);
        // BAXY Renew (file.write): whether the version it replaced went to the Recycle Bin, as observed.
        if (result.PreviousVersionRecycled is bool recycled) writer.WriteBoolean("previousVersionRecycled", recycled);
        if (!string.IsNullOrEmpty(folder)) writer.WriteString("folder", folder);
        // E024 (pc-ayudas): a write with no folder went to BAXY's own working folder, not to one of the person's.
        else if (result.InWorkFolder) writer.WriteString("folder", "baxy_work");
        if (result.FullPath is not null) writer.WriteString("fullPath", result.FullPath);
        if (result.SameNameInHome is not null) writer.WriteString("sameNameInHome", result.SameNameInHome);
        if (result.Created) writer.WriteBoolean("created", true);
        // E006/E024 (pc-ayudas, lever 3b): with a folder of that name in the person's home, the fact and the option, as
        // calculator_next: without it the model said «lo guardé en BAXY-bench» of the working folder (continuation probe,
        // 2 of 3 per seed; 0 with it). Only with the home folder seen: a generic hint made it name a folder that is not.
        if (result.SameNameInHome is not null)
        {
            writer.WriteString("next", $"this file is in BAXY's own working folder, not in {result.SameNameInHome}, "
                + "which also exists; file_write with folder home and the same relativePath writes it there");
        }
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
        writer.WriteNumber("totalCount", result.TotalCount);
        writer.WriteBoolean("hasMore", result.TotalCount > result.Count);
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
