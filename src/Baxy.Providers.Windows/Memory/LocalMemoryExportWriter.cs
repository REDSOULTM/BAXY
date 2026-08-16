using System.Buffers;
using System.Collections.Concurrent;
using System.Diagnostics.CodeAnalysis;
using System.Globalization;
using System.Security;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Baxy.Security.Windows;

namespace Baxy.Providers.Windows.Memory;

public sealed class LocalMemoryExportWriter : IMemoryExportWriter
{
    public const int MaximumExportBytes = 4 * 1024 * 1024;
    public const string ExportDirectoryName = "BAXY";
    public const string RedactedValue = "[REDACTED]";

    private const string ExportSchema = "baxy.memory.export";
    private static readonly UTF8Encoding StrictUtf8 = new(false, true);
    private static readonly ConcurrentDictionary<string, object> DirectoryLocks =
        new(StringComparer.OrdinalIgnoreCase);
    private readonly string? _documentsDirectory;
    private readonly Action<MemoryExportWriteStage>? _writeHook;

    public LocalMemoryExportWriter(string? documentsDirectory = null)
        : this(documentsDirectory, writeHook: null)
    {
    }

    internal LocalMemoryExportWriter(
        string? documentsDirectory,
        Action<MemoryExportWriteStage>? writeHook)
    {
        _documentsDirectory = documentsDirectory;
        _writeHook = writeHook;
    }

    public MemoryExportResult Export(MemoryExportRequest request)
    {
        ArgumentNullException.ThrowIfNull(request);
        byte[]? utf8 = null;
        try
        {
            ValidateCanonicalIdentifier(request.InvocationId, nameof(request.InvocationId));
            ArgumentNullException.ThrowIfNull(request.Records);
            if (request.Records.Count > LocalMemoryStore.MaximumRecords)
            {
                throw new MemoryExportUnavailableException();
            }

            foreach (MemoryRecord? record in request.Records)
            {
                if (record is null)
                {
                    throw new MemoryExportUnavailableException();
                }
            }

            MemoryRecord[] records = request.Records
                .OrderBy(static record => record.Id)
                .ToArray();
            ValidateRecords(records);
            utf8 = Serialize(request.InvocationId, records);
            if (utf8.Length is < 1 or > MaximumExportBytes)
            {
                throw new MemoryExportUnavailableException();
            }

            string root = ResolveAndValidateRoot();
            object directoryLock = DirectoryLocks.GetOrAdd(root, static _ => new object());
            lock (directoryLock)
            {
                return WriteUnderLock(root, request.InvocationId, records.Length, utf8);
            }
        }
        catch (MemoryExportException)
        {
            throw;
        }
        catch (Exception exception) when (exception is ArgumentException
            or IOException
            or UnauthorizedAccessException
            or NotSupportedException
            or PathTooLongException
            or SecurityException
            or EncoderFallbackException)
        {
            throw new MemoryExportUnavailableException();
        }
        finally
        {
            if (utf8 is not null)
            {
                CryptographicOperations.ZeroMemory(utf8);
            }
        }
    }

    public bool Verify(MemoryExportVerificationRequest request)
    {
        ArgumentNullException.ThrowIfNull(request);
        try
        {
            ValidateCanonicalIdentifier(request.InvocationId, nameof(request.InvocationId));
            if (request.RecordCount is < 0 or > LocalMemoryStore.MaximumRecords
                || string.IsNullOrEmpty(request.Sha256)
                || request.Sha256.Length != 64
                || request.Sha256.Any(static character => character is not (
                    >= '0' and <= '9' or >= 'a' and <= 'f')))
            {
                return false;
            }

            string root = ResolveRootPath();
            string invocationHash = HashUtf8(StrictUtf8.GetBytes(request.InvocationId));
            string expectedPath = GetManagedPath(
                root,
                $"memory-export-{invocationHash}.json");
            if (!string.Equals(request.Path, expectedPath, StringComparison.OrdinalIgnoreCase)
                || !TryOpenRegularFile(expectedPath, out WindowsPrivateFileLease? file))
            {
                return false;
            }

            using (file)
            {
                FileStream stream = file.Stream;
                if (stream.Length is < 1 or > MaximumExportBytes)
                {
                    return false;
                }

                byte[] actualHash = SHA256.HashData(stream);
                byte[] expectedHash = Convert.FromHexString(request.Sha256);
                try
                {
                    if (stream.ReadByte() != -1
                        || !CryptographicOperations.FixedTimeEquals(actualHash, expectedHash))
                    {
                        return false;
                    }
                }
                finally
                {
                    CryptographicOperations.ZeroMemory(actualHash);
                    CryptographicOperations.ZeroMemory(expectedHash);
                }

                stream.Position = 0;
                using JsonDocument document = JsonDocument.Parse(
                    stream,
                    new JsonDocumentOptions
                    {
                        AllowTrailingCommas = false,
                        CommentHandling = JsonCommentHandling.Disallow,
                        MaxDepth = 32,
                    });
                return IsExpectedDocument(document.RootElement, request);
            }
        }
        catch (Exception exception) when (exception is MemoryExportException
            or ArgumentException
            or IOException
            or UnauthorizedAccessException
            or NotSupportedException
            or PathTooLongException
            or SecurityException
            or CryptographicException
            or EncoderFallbackException)
        {
            return false;
        }
    }

    private static bool IsExpectedDocument(
        JsonElement root,
        MemoryExportVerificationRequest request)
    {
        if (root.ValueKind != JsonValueKind.Object)
        {
            return false;
        }

        var properties = new HashSet<string>(StringComparer.Ordinal);
        foreach (JsonProperty property in root.EnumerateObject())
        {
            if (!properties.Add(property.Name))
            {
                return false;
            }
        }

        return properties.SetEquals([
                "schema",
                "version",
                "invocationId",
                "includeSecretValues",
                "recordCount",
                "records",
            ])
            && root.GetProperty("schema").ValueKind == JsonValueKind.String
            && string.Equals(
                root.GetProperty("schema").GetString(),
                ExportSchema,
                StringComparison.Ordinal)
            && root.GetProperty("version").ValueKind == JsonValueKind.Number
            && root.GetProperty("version").TryGetInt32(out int version)
            && version == 1
            && root.GetProperty("invocationId").ValueKind == JsonValueKind.String
            && string.Equals(
                root.GetProperty("invocationId").GetString(),
                request.InvocationId,
                StringComparison.Ordinal)
            && root.GetProperty("includeSecretValues").ValueKind == JsonValueKind.False
            && root.GetProperty("recordCount").ValueKind == JsonValueKind.Number
            && root.GetProperty("recordCount").TryGetInt32(out int recordCount)
            && recordCount == request.RecordCount
            && root.GetProperty("records").ValueKind == JsonValueKind.Array
            && root.GetProperty("records").GetArrayLength() == request.RecordCount;
    }

    private MemoryExportResult WriteUnderLock(
        string root,
        string invocationId,
        int recordCount,
        byte[] utf8)
    {
        EnsureSafeRoot(root);
        string invocationHash = HashUtf8(StrictUtf8.GetBytes(invocationId));
        string targetPath = GetManagedPath(
            root,
            $"memory-export-{invocationHash}.json");
        string contentHash = HashUtf8(utf8);
        if (RegularFileExists(targetPath))
        {
            EnsureExistingMatches(root, targetPath, utf8);
            return new MemoryExportResult(targetPath, recordCount, contentHash, Replayed: true);
        }

        string temporaryPath = GetManagedPath(
            root,
            $".memory-export-{invocationHash}-{Guid.NewGuid():N}.tmp");
        WindowsPrivateFileLease? candidate = null;
        bool published = false;
        try
        {
            EnsureSafeRoot(root);
            candidate = CreateRegularFile(temporaryPath);
            candidate.Stream.Write(utf8);
            candidate.Stream.Flush(flushToDisk: true);
            _writeHook?.Invoke(MemoryExportWriteStage.CandidateFlushed);

            if (!RenameRegularFile(candidate, Path.GetFileName(targetPath), replace: false))
            {
                EnsureExistingMatches(root, targetPath, utf8);
                return new MemoryExportResult(
                    targetPath,
                    recordCount,
                    contentHash,
                    Replayed: true);
            }

            published = true;
            candidate.Dispose();
            candidate = null;
            EnsureExistingMatches(root, targetPath, utf8);
            return new MemoryExportResult(targetPath, recordCount, contentHash, Replayed: false);
        }
        finally
        {
            try
            {
                if (!published && candidate is not null)
                {
                    DestroyCandidate(candidate);
                }
            }
            finally
            {
                candidate?.Dispose();
            }
        }
    }

    private string ResolveAndValidateRoot()
    {
        string root = ResolveRootPath();
        try
        {
            MemoryPathPolicy.CreateAndValidateRoot(root);
            return root;
        }
        catch (UnsafeMemoryStorePathException)
        {
            throw new UnsafeMemoryExportPathException();
        }
    }

    private string ResolveRootPath()
    {
        string documents = _documentsDirectory
            ?? Environment.GetFolderPath(
                Environment.SpecialFolder.MyDocuments,
                Environment.SpecialFolderOption.DoNotVerify);
        if (string.IsNullOrWhiteSpace(documents))
        {
            throw new UnsafeMemoryExportPathException();
        }

        try
        {
            string normalizedDocuments = MemoryPathPolicy.NormalizeRoot(documents);
            string root = MemoryPathPolicy.NormalizeRoot(
                Path.Combine(normalizedDocuments, ExportDirectoryName));
            string? volumeRoot = Path.GetPathRoot(root);
            if (string.IsNullOrEmpty(volumeRoot)
                || new DriveInfo(volumeRoot).DriveType != DriveType.Fixed)
            {
                throw new UnsafeMemoryExportPathException();
            }

            return root;
        }
        catch (UnsafeMemoryStorePathException)
        {
            throw new UnsafeMemoryExportPathException();
        }
    }

    private static void EnsureSafeRoot(string root)
    {
        try
        {
            MemoryPathPolicy.EnsureDirectory(root);
        }
        catch (UnsafeMemoryStorePathException)
        {
            throw new UnsafeMemoryExportPathException();
        }
    }

    private static string GetManagedPath(string root, string fileName)
    {
        try
        {
            return MemoryPathPolicy.GetManagedPath(root, fileName);
        }
        catch (UnsafeMemoryStorePathException)
        {
            throw new UnsafeMemoryExportPathException();
        }
    }

    private static bool RegularFileExists(string path)
    {
        try
        {
            return MemoryPathPolicy.RegularFileExists(path);
        }
        catch (UnsafeMemoryStorePathException)
        {
            throw new UnsafeMemoryExportPathException();
        }
    }

    private static WindowsPrivateFileLease CreateRegularFile(string path)
    {
        try
        {
            return MemoryPathPolicy.CreateRegularFile(path);
        }
        catch (UnsafeMemoryStorePathException)
        {
            throw new UnsafeMemoryExportPathException();
        }
    }

    private static bool RenameRegularFile(
        WindowsPrivateFileLease file,
        string destinationFileName,
        bool replace)
    {
        try
        {
            return MemoryPathPolicy.RenameRegularFile(file, destinationFileName, replace);
        }
        catch (UnsafeMemoryStorePathException)
        {
            throw new UnsafeMemoryExportPathException();
        }
    }

    private static void EnsureExistingMatches(
        string root,
        string targetPath,
        ReadOnlySpan<byte> expected)
    {
        EnsureSafeRoot(root);
        if (!TryOpenRegularFile(targetPath, out WindowsPrivateFileLease? file))
        {
            throw new MemoryExportConflictException();
        }

        using (file)
        {
            FileStream stream = file.Stream;
            if (stream.Length is < 1 or > MaximumExportBytes
                || stream.Length != expected.Length)
            {
                throw new MemoryExportConflictException();
            }

            byte[] actual = GC.AllocateUninitializedArray<byte>(checked((int)stream.Length));
            try
            {
                stream.ReadExactly(actual);
                if (stream.ReadByte() != -1 || !actual.AsSpan().SequenceEqual(expected))
                {
                    throw new MemoryExportConflictException();
                }
            }
            finally
            {
                CryptographicOperations.ZeroMemory(actual);
            }
        }
    }

    private static bool TryOpenRegularFile(
        string path,
        [NotNullWhen(true)] out WindowsPrivateFileLease? file)
    {
        try
        {
            return MemoryPathPolicy.TryOpenRegularFile(
                path,
                FileAccess.Read,
                FileShare.Read,
                deleteAccess: false,
                out file);
        }
        catch (UnsafeMemoryStorePathException)
        {
            file = null;
            throw new UnsafeMemoryExportPathException();
        }
    }

    private static void DestroyCandidate(WindowsPrivateFileLease candidate)
    {
        try
        {
            MemoryPathPolicy.DeleteRegularFile(candidate);
        }
        catch (UnsafeMemoryStorePathException)
        {
            try
            {
                candidate.Stream.SetLength(0);
                candidate.Stream.Flush(flushToDisk: true);
            }
            catch (Exception exception) when (exception is IOException
                or UnauthorizedAccessException)
            {
                throw new MemoryExportUnavailableException();
            }
        }
    }

    private static byte[] Serialize(string invocationId, MemoryRecord[] records)
    {
        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer, new JsonWriterOptions
        {
            Indented = true,
            SkipValidation = false,
        }))
        {
            writer.WriteStartObject();
            writer.WriteString("schema", ExportSchema);
            writer.WriteNumber("version", 1);
            writer.WriteString("invocationId", invocationId);
            writer.WriteBoolean("includeSecretValues", false);
            writer.WriteNumber("recordCount", records.Length);
            writer.WriteStartArray("records");
            foreach (MemoryRecord record in records)
            {
                WriteRecord(writer, record);
            }

            writer.WriteEndArray();
            writer.WriteEndObject();
            writer.Flush();
        }

        byte[] result = new byte[checked(buffer.WrittenCount + 1)];
        buffer.WrittenSpan.CopyTo(result);
        result[^1] = (byte)'\n';
        return result;
    }

    private static void WriteRecord(Utf8JsonWriter writer, MemoryRecord record)
    {
        bool redact = record.Sensitivity is MemorySensitivity.Sensitive
            or MemorySensitivity.Secret;
        writer.WriteStartObject();
        writer.WriteString("recordId", record.Id.ToString("D"));
        writer.WriteNumber("revision", record.Revision);
        writer.WriteString("selector", redact ? RedactedValue : record.Selector);
        writer.WriteString("label", redact ? RedactedValue : record.Label);
        writer.WriteString("value", redact ? RedactedValue : record.Value);
        writer.WriteBoolean("valueRedacted", redact);
        writer.WriteString("kind", ToWire(record.Kind));
        writer.WriteString("origin", "explicit");
        writer.WriteString("sensitivity", ToWire(record.Sensitivity));
        writer.WriteString("retention", ToWire(record.Retention));
        writer.WriteStartArray("tags");
        if (!redact)
        {
            foreach (string tag in record.Tags)
            {
                writer.WriteStringValue(tag);
            }
        }

        writer.WriteEndArray();
        writer.WriteString("createdAtUtc", CanonicalTimestamp(record.CreatedAtUtc));
        writer.WriteString("updatedAtUtc", CanonicalTimestamp(record.UpdatedAtUtc));
        WriteOptionalString(
            writer,
            "expiresAtUtc",
            record.ExpiresAtUtc is { } expires ? CanonicalTimestamp(expires) : null);
        WriteOptionalString(writer, "sourceMissionId", redact ? null : record.SourceMissionId);
        writer.WriteString("capturedAtUtc", CanonicalTimestamp(record.CapturedAtUtc));
        WriteOptionalString(writer, "sessionId", record.SessionId);
        writer.WriteEndObject();
    }

    private static void WriteOptionalString(Utf8JsonWriter writer, string name, string? value)
    {
        if (value is null)
        {
            writer.WriteNull(name);
        }
        else
        {
            writer.WriteString(name, value);
        }
    }

    private static void ValidateRecords(MemoryRecord[] records)
    {
        var ids = new HashSet<Guid>();
        foreach (MemoryRecord record in records)
        {
            ArgumentNullException.ThrowIfNull(record);
            if (record.Id == Guid.Empty
                || !ids.Add(record.Id)
                || record.Revision < 1
                || record.Origin != MemoryOrigin.Explicit)
            {
                throw new MemoryExportUnavailableException();
            }

            ValidateBoundedText(
                record.Selector,
                LocalMemoryStore.MaximumSelectorUtf8Bytes,
                allowEmpty: false);
            ValidateBoundedText(
                record.Label,
                LocalMemoryStore.MaximumLabelUtf8Bytes,
                allowEmpty: false);
            ValidateBoundedText(
                record.Value,
                LocalMemoryStore.MaximumValueUtf8Bytes,
                allowEmpty: true);
            if (record.Tags is null || record.Tags.Count > LocalMemoryStore.MaximumTags)
            {
                throw new MemoryExportUnavailableException();
            }

            var uniqueTags = new HashSet<string>(StringComparer.Ordinal);
            foreach (string tag in record.Tags)
            {
                ValidateBoundedText(
                    tag,
                    LocalMemoryStore.MaximumTagUtf8Bytes,
                    allowEmpty: false);
                if (!uniqueTags.Add(tag))
                {
                    throw new MemoryExportUnavailableException();
                }
            }

            ValidateTimestamp(record.CreatedAtUtc);
            ValidateTimestamp(record.UpdatedAtUtc);
            ValidateTimestamp(record.CapturedAtUtc);
            if (record.UpdatedAtUtc < record.CreatedAtUtc)
            {
                throw new MemoryExportUnavailableException();
            }
            if (record.ExpiresAtUtc is { } expires)
            {
                ValidateTimestamp(expires);
            }

            if (record.SourceMissionId is not null)
            {
                ValidateCanonicalIdentifier(record.SourceMissionId, nameof(record.SourceMissionId));
            }

            if (record.SessionId is not null)
            {
                ValidateCanonicalIdentifier(record.SessionId, nameof(record.SessionId));
            }

            bool retentionValid = record.Retention switch
            {
                MemoryRetention.Persistent => record.SessionId is null
                    && record.ExpiresAtUtc is null,
                MemoryRetention.Session => record.SessionId is not null
                    && record.ExpiresAtUtc is null,
                MemoryRetention.Temporary => record.SessionId is null
                    && record.ExpiresAtUtc is not null,
                _ => false,
            };
            if (!retentionValid)
            {
                throw new MemoryExportUnavailableException();
            }
        }
    }

    private static void ValidateBoundedText(string value, int maximumUtf8Bytes, bool allowEmpty)
    {
        if (value is null
            || (!allowEmpty && string.IsNullOrWhiteSpace(value))
            || !value.IsNormalized(NormalizationForm.FormC)
            || value.Any(static character => char.IsControl(character))
            || StrictUtf8.GetByteCount(value) > maximumUtf8Bytes)
        {
            throw new MemoryExportUnavailableException();
        }
    }

    private static void ValidateCanonicalIdentifier(string value, string parameterName)
    {
        if (!Guid.TryParseExact(value, "D", out Guid parsed)
            || !string.Equals(parsed.ToString("D"), value, StringComparison.Ordinal))
        {
            throw new ArgumentException("A canonical identifier was required.", parameterName);
        }
    }

    private static void ValidateTimestamp(DateTimeOffset value)
    {
        if (value.Offset != TimeSpan.Zero)
        {
            throw new MemoryExportUnavailableException();
        }
    }

    private static string CanonicalTimestamp(DateTimeOffset value) =>
        value.ToUniversalTime().ToString("O", CultureInfo.InvariantCulture);

    private static string HashUtf8(ReadOnlySpan<byte> utf8) =>
        Convert.ToHexStringLower(SHA256.HashData(utf8));

    private static string ToWire(MemoryKind value) => value switch
    {
        MemoryKind.Fact => "fact",
        MemoryKind.Preference => "preference",
        MemoryKind.Context => "context",
        MemoryKind.Rule => "rule",
        _ => throw new MemoryExportUnavailableException(),
    };

    private static string ToWire(MemorySensitivity value) => value switch
    {
        MemorySensitivity.Normal => "normal",
        MemorySensitivity.Personal => "personal",
        MemorySensitivity.Sensitive => "sensitive",
        MemorySensitivity.Secret => "secret",
        _ => throw new MemoryExportUnavailableException(),
    };

    private static string ToWire(MemoryRetention value) => value switch
    {
        MemoryRetention.Persistent => "persistent",
        MemoryRetention.Session => "session",
        MemoryRetention.Temporary => "temporary",
        _ => throw new MemoryExportUnavailableException(),
    };
}

internal enum MemoryExportWriteStage
{
    CandidateFlushed,
}
