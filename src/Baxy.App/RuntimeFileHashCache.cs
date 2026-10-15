using System.IO;
using System.Text.Json;

namespace Baxy.App;

/// <summary>
/// Remembers the SHA-256 of large runtime files (model, speech, interpreter)
/// by (path, size, creation and last-write time), so a start whose files did
/// not change since the last verified start does not read gigabytes again.
/// The store lives beside the runtime registration, which already names the
/// expected hashes: it is trusted exactly as much as that registration, and
/// it only says what a file hashed to, never whether it is accepted. A file
/// written within <see cref="RacyWindow"/> of its hashing is never remembered,
/// so a rewrite that keeps size and timestamp tick cannot reuse an old hash.
/// </summary>
internal sealed class RuntimeFileHashCache
{
    internal const string Schema = "baxy-runtime-hash-cache-v1";
    internal const string FileName = "mind-runtime-v1.hash-cache.json";
    internal static readonly TimeSpan RacyWindow = TimeSpan.FromSeconds(2);
    private const int MaximumEntries = 64;
    private const int MaximumStoreBytes = 64 * 1024;

    private readonly string? _storePath;
    private readonly Func<string, string> _hasher;
    private readonly Func<DateTime> _utcNow;
    private readonly Dictionary<string, Entry> _entries = new(StringComparer.OrdinalIgnoreCase);
    private bool _dirty;

    internal RuntimeFileHashCache(
        string? storePath,
        Func<string, string> hasher,
        Func<DateTime>? utcNow = null)
    {
        _storePath = storePath;
        _hasher = hasher;
        _utcNow = utcNow ?? (static () => DateTime.UtcNow);
        Load();
    }

    internal static RuntimeFileHashCache ForRegistration(
        string registrationPath,
        Func<string, string> hasher)
    {
        string? directory = Path.GetDirectoryName(registrationPath);
        return new RuntimeFileHashCache(
            string.IsNullOrEmpty(directory) ? null : Path.Combine(directory, FileName),
            hasher);
    }

    /// <summary>The file's SHA-256 (lower-case hex), read only when its identity changed.</summary>
    internal string Sha256(string path)
    {
        var before = new FileInfo(path);
        Entry? identity = Identify(before);
        if (identity is not null
            && _entries.TryGetValue(before.FullName, out Entry? known)
            && known.SameIdentity(identity))
        {
            return known.Sha256;
        }

        DateTime hashedAt = _utcNow();
        string digest = _hasher(path);
        Entry? after = Identify(new FileInfo(path));
        if (identity is not null
            && after is not null
            && identity.SameIdentity(after)
            && hashedAt - identity.LastWriteUtc >= RacyWindow)
        {
            _entries[before.FullName] = identity with { Sha256 = digest };
            _dirty = true;
        }
        else if (_entries.Remove(before.FullName))
        {
            _dirty = true;
        }

        return digest;
    }

    internal void Save()
    {
        if (!_dirty || _storePath is null)
        {
            return;
        }

        try
        {
            var document = new StoreDocument(
                Schema,
                _entries
                    .OrderBy(static pair => pair.Key, StringComparer.Ordinal)
                    .Take(MaximumEntries)
                    .Select(static pair => new StoreEntry(
                        pair.Key,
                        pair.Value.Length,
                        pair.Value.CreationUtc.Ticks,
                        pair.Value.LastWriteUtc.Ticks,
                        pair.Value.Sha256))
                    .ToArray());
            string temporary = _storePath + "." + Guid.NewGuid().ToString("N") + ".tmp";
            File.WriteAllBytes(temporary, JsonSerializer.SerializeToUtf8Bytes(document));
            File.Move(temporary, _storePath, overwrite: true);
            _dirty = false;
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException
            or ArgumentException
            or NotSupportedException)
        {
            // A store that cannot be written only costs the next start a re-read.
        }
    }

    private void Load()
    {
        if (_storePath is null)
        {
            return;
        }

        try
        {
            var info = new FileInfo(_storePath);
            if (!info.Exists || info.Length is <= 0 or > MaximumStoreBytes)
            {
                return;
            }

            StoreDocument? document = JsonSerializer.Deserialize<StoreDocument>(
                File.ReadAllBytes(_storePath));
            if (document is not { Schema: Schema, Entries: { Length: <= MaximumEntries } entries })
            {
                return;
            }

            foreach (StoreEntry entry in entries)
            {
                if (entry is { Path: { Length: > 0 } path, Sha256: { Length: 64 } sha256 }
                    && entry.Length >= 0
                    && sha256.All(static character => character is >= '0' and <= '9' or >= 'a' and <= 'f')
                    && entry.CreationTicks is >= 0 and <= 3155378975999999999
                    && entry.LastWriteTicks is >= 0 and <= 3155378975999999999)
                {
                    _entries[path] = new Entry(
                        entry.Length,
                        new DateTime(entry.CreationTicks, DateTimeKind.Utc),
                        new DateTime(entry.LastWriteTicks, DateTimeKind.Utc),
                        sha256);
                }
            }
        }
        catch (Exception exception) when (exception is IOException
            or UnauthorizedAccessException
            or JsonException
            or ArgumentException
            or NotSupportedException)
        {
            _entries.Clear();
        }
    }

    private static Entry? Identify(FileInfo info)
    {
        info.Refresh();
        return info.Exists
            ? new Entry(info.Length, info.CreationTimeUtc, info.LastWriteTimeUtc, string.Empty)
            : null;
    }

    private sealed record Entry(long Length, DateTime CreationUtc, DateTime LastWriteUtc, string Sha256)
    {
        internal bool SameIdentity(Entry other) =>
            Length == other.Length
            && CreationUtc == other.CreationUtc
            && LastWriteUtc == other.LastWriteUtc;
    }

    private sealed record StoreDocument(string Schema, StoreEntry[] Entries);

    private sealed record StoreEntry(
        string Path,
        long Length,
        long CreationTicks,
        long LastWriteTicks,
        string Sha256);
}
