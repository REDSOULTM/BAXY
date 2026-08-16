using System.Security.Cryptography;
using System.Text.Json;
using Baxy.Security.Windows;

namespace Baxy.Core;

internal sealed record LegacyJournalMigrationResult(
    bool Migrated,
    string? ArchivePath,
    string? Sha256,
    long Length);

internal static class LegacyJournalMigration
{
    private const long MaximumJournalBytes = 64L * 1024 * 1024;
    private const int MaximumRecordBytes = 2 * 1024 * 1024;

    internal static LegacyJournalMigrationResult PreserveUnkeyedV1(
        string journalPath,
        string anchorPath,
        string authenticationKeyPath)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(journalPath);
        ArgumentException.ThrowIfNullOrWhiteSpace(anchorPath);
        ArgumentException.ThrowIfNullOrWhiteSpace(authenticationKeyPath);

        string fullJournalPath = Path.GetFullPath(journalPath);
        string fullAnchorPath = Path.GetFullPath(anchorPath);
        string fullKeyPath = Path.GetFullPath(authenticationKeyPath);
        if (File.Exists(fullAnchorPath) || File.Exists(fullKeyPath))
        {
            return new LegacyJournalMigrationResult(false, null, null, 0);
        }

        if (!WindowsPrivateStorage.TryOpenFile(
                fullJournalPath,
                FileAccess.Read,
                FileShare.Read,
                deleteAccess: true,
                out WindowsPrivateFileLease? journal))
        {
            return new LegacyJournalMigrationResult(false, null, null, 0);
        }

        using (journal)
        {
            FileStream stream = journal.Stream;
            if (stream.Length == 0)
            {
                return new LegacyJournalMigrationResult(false, null, null, 0);
            }

            if (stream.Length > MaximumJournalBytes)
            {
                return new LegacyJournalMigrationResult(false, null, null, stream.Length);
            }

            byte[] bytes = GC.AllocateUninitializedArray<byte>(checked((int)stream.Length));
            try
            {
                stream.ReadExactly(bytes);
                if (stream.ReadByte() != -1 || !IsV1Journal(bytes))
                {
                    return new LegacyJournalMigrationResult(false, null, null, stream.Length);
                }

                string digest = Convert.ToHexStringLower(SHA256.HashData(bytes));
                string archiveName = string.Concat(
                    Path.GetFileNameWithoutExtension(fullJournalPath),
                    ".legacy-v1-untrusted.",
                    digest,
                    ".",
                    Guid.NewGuid().ToString("N"),
                    Path.GetExtension(fullJournalPath));
                if (!WindowsPrivateStorage.Rename(journal, archiveName, replace: false))
                {
                    throw new IOException("The legacy journal archive name already exists.");
                }

                return new LegacyJournalMigrationResult(
                    true,
                    journal.Path,
                    digest,
                    bytes.LongLength);
            }
            finally
            {
                CryptographicOperations.ZeroMemory(bytes);
            }
        }
    }

    private static bool IsV1Journal(ReadOnlyMemory<byte> bytes)
    {
        ReadOnlySpan<byte> span = bytes.Span;
        int start = 0;
        int records = 0;
        for (int index = 0; index <= span.Length; index++)
        {
            if (index < span.Length && span[index] != (byte)'\n')
            {
                continue;
            }

            int length = index - start;
            if (length == 0)
            {
                if (index == span.Length && records > 0)
                {
                    break;
                }

                return false;
            }

            if (length > MaximumRecordBytes
                || !IsV1Record(bytes.Slice(start, length)))
            {
                return false;
            }

            records++;
            start = index + 1;
        }

        return records > 0;
    }

    private static bool IsV1Record(ReadOnlyMemory<byte> utf8)
    {
        try
        {
            using JsonDocument document = JsonDocument.Parse(utf8);
            JsonElement root = document.RootElement;
            if (root.ValueKind != JsonValueKind.Object
                || root.EnumerateObject().Count() != 3
                || !root.TryGetProperty("payload", out JsonElement payload)
                || payload.ValueKind != JsonValueKind.Object
                || !root.TryGetProperty("previousHash", out JsonElement previousHash)
                || !root.TryGetProperty("hash", out JsonElement hash))
            {
                return false;
            }

            return IsLowerHexSha256(previousHash) && IsLowerHexSha256(hash);
        }
        catch (JsonException)
        {
            return false;
        }
    }

    private static bool IsLowerHexSha256(JsonElement element)
    {
        if (element.ValueKind != JsonValueKind.String
            || element.GetString() is not { Length: 64 } value)
        {
            return false;
        }

        return value.All(static character =>
            character is (>= '0' and <= '9') or (>= 'a' and <= 'f'));
    }
}
