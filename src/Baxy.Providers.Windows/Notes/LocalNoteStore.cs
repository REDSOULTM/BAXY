using System.Buffers.Binary;
using System.Collections.Concurrent;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace Baxy.Providers.Windows.Notes;

/// <summary>
/// Stores one UTF-8 JSON document per note beneath an injected private directory.
/// Mutations use same-directory atomic replacement and retain the last valid document
/// as a recovery copy.
/// </summary>
public sealed class LocalNoteStore : INoteStore
{
    public const int MaximumTitleUtf8Bytes = 512;
    public const int MaximumContentUtf8Bytes = 65_536;
    public const int MaximumContentPreviewUtf8Bytes = 128;
    public const int MaximumIdempotencyKeyUtf8Bytes = 256;
    public const int MaximumStoredNotes = 512;
    public const int MaximumListPageSize = 100;

    private const int CurrentSchemaVersion = 1;
    private const long MaximumDocumentBytes = 96 * 1024;
    private const string NotesDirectoryName = "notes";
    private const string BackupSuffix = ".bak";
    private const string TemporaryPrefix = ".baxy-note-";
    private const string TemporarySuffix = ".tmp";
    private static readonly UTF8Encoding StrictUtf8 = new(false, true);
    private static readonly ConcurrentDictionary<string, object> RootLocks =
        new(StringComparer.OrdinalIgnoreCase);

    private readonly string _rootDirectory;
    private readonly string _notesDirectory;
    private readonly object _rootLock;
    private readonly TimeProvider _timeProvider;
    private readonly Action<string>? _afterNewDocumentCommitted;
    private readonly int _maximumStoredNotes;

    public LocalNoteStore(string rootDirectory, TimeProvider? timeProvider = null)
        : this(
            rootDirectory,
            timeProvider,
            afterNewDocumentCommitted: null,
            maximumStoredNotes: MaximumStoredNotes)
    {
    }

    internal LocalNoteStore(
        string rootDirectory,
        TimeProvider? timeProvider,
        Action<string>? afterNewDocumentCommitted,
        int maximumStoredNotes = MaximumStoredNotes)
    {
        if (maximumStoredNotes is < 1 or > MaximumStoredNotes)
        {
            throw new ArgumentOutOfRangeException(nameof(maximumStoredNotes));
        }

        _rootDirectory = ValidateAndNormalizeRootPath(rootDirectory);
        _notesDirectory = GetContainedPath(_rootDirectory, NotesDirectoryName);
        _rootLock = RootLocks.GetOrAdd(_rootDirectory, static _ => new object());
        _timeProvider = timeProvider ?? TimeProvider.System;
        _afterNewDocumentCommitted = afterNewDocumentCommitted;
        _maximumStoredNotes = maximumStoredNotes;

        lock (_rootLock)
        {
            InitializeStorageUnsafe();
        }
    }

    public string RootDirectory => _rootDirectory;

    public NoteRecord Create(string title, string content, string? idempotencyKey = null)
    {
        string normalizedTitle = ValidateAndNormalizeText(
            title,
            nameof(title),
            MaximumTitleUtf8Bytes,
            allowLineBreaks: false,
            allowEmpty: false,
            trim: true);
        string normalizedContent = ValidateAndNormalizeText(
            content,
            nameof(content),
            MaximumContentUtf8Bytes,
            allowLineBreaks: true,
            allowEmpty: true,
            trim: false);
        string? normalizedKey = idempotencyKey is null
            ? null
            : ValidateAndNormalizeText(
                idempotencyKey,
                nameof(idempotencyKey),
                MaximumIdempotencyKeyUtf8Bytes,
                allowLineBreaks: false,
                allowEmpty: false,
                trim: true);

        lock (_rootLock)
        {
            EnsureSafeStorageTreeUnsafe();
            DeleteAbandonedTemporaryFilesUnsafe();
            Guid[] storedIds = EnumerateStoredIdsUnsafe();

            if (normalizedKey is not null)
            {
                NoteDocument? replay = FindByIdempotencyKeyUnsafe(normalizedKey, storedIds);
                if (replay is not null)
                {
                    if (!string.Equals(replay.Title, normalizedTitle, StringComparison.Ordinal)
                        || !string.Equals(replay.Content, normalizedContent, StringComparison.Ordinal))
                    {
                        throw new NoteConflictException(
                            "The idempotency key was already used with different note content.");
                    }

                    return ToRecord(replay);
                }
            }

            if (storedIds.Length >= _maximumStoredNotes)
            {
                throw new NoteCapacityException(_maximumStoredNotes);
            }

            DateTimeOffset now = GetUtcNow();
            NoteDocument document;
            string path;
            do
            {
                Guid id = Guid.NewGuid();
                document = WithIntegrity(new NoteDocument
                {
                    SchemaVersion = CurrentSchemaVersion,
                    Id = id,
                    Title = normalizedTitle,
                    Content = normalizedContent,
                    CreatedAtUtc = now,
                    UpdatedAtUtc = now,
                    Revision = 1,
                    IdempotencyKey = normalizedKey,
                });
                path = GetPrimaryPath(id);
            }
            while (File.Exists(path) || File.Exists(GetBackupPath(path)));

            WriteNewDocumentUnsafe(path, document);
            return ToRecord(document);
        }
    }

    public NoteRecord Read(Guid id, bool includeTrashed = false)
    {
        ValidateId(id);

        lock (_rootLock)
        {
            EnsureSafeStorageTreeUnsafe();
            NoteDocument document = ReadDocumentWithRecoveryUnsafe(id);
            if (document.TrashedAtUtc.HasValue && !includeTrashed)
            {
                throw new NoteNotFoundException(id);
            }

            return ToRecord(document);
        }
    }

    public NoteRecord ReadExactTitle(string title)
    {
        string normalizedTitle = NormalizeTitleSelector(title);

        lock (_rootLock)
        {
            EnsureSafeStorageTreeUnsafe();
            DeleteAbandonedTemporaryFilesUnsafe();
            return ToRecord(FindUniqueByTitleUnsafe(normalizedTitle, NoteListScope.Active));
        }
    }

    public NoteRecord ReadSelected(NoteSelection selection)
    {
        NoteSelection normalized = NormalizeSelection(selection);
        if (normalized.ExpectedIsTrashed)
        {
            throw new NoteSelectionStaleException(normalized.Id);
        }

        lock (_rootLock)
        {
            EnsureSafeStorageTreeUnsafe();
            DeleteAbandonedTemporaryFilesUnsafe();
            NoteDocument current = ReadDocumentWithRecoveryUnsafe(normalized.Id);
            if (!MatchesSelection(current, normalized))
            {
                throw new NoteSelectionStaleException(normalized.Id);
            }

            return ToRecord(current);
        }
    }

    public NoteRecord UpdateSelected(NoteSelection selection, string title, string content)
    {
        NoteSelection normalized = NormalizeSelection(selection);
        if (normalized.ExpectedIsTrashed) throw new NoteSelectionStaleException(normalized.Id);
        string normalizedTitle = ValidateAndNormalizeText(
            title, nameof(title), MaximumTitleUtf8Bytes,
            allowLineBreaks: false, allowEmpty: false, trim: true);
        string normalizedContent = ValidateAndNormalizeText(
            content, nameof(content), MaximumContentUtf8Bytes,
            allowLineBreaks: true, allowEmpty: true, trim: false);

        lock (_rootLock)
        {
            EnsureSafeStorageTreeUnsafe();
            DeleteAbandonedTemporaryFilesUnsafe();
            NoteDocument current = ReadDocumentWithRecoveryUnsafe(normalized.Id);
            if (!MatchesSelection(current, normalized))
            {
                bool replay = normalized.ExpectedRevision < long.MaxValue
                    && current.Id == normalized.Id
                    && current.Revision == normalized.ExpectedRevision + 1
                    && !current.TrashedAtUtc.HasValue
                    && string.Equals(current.Title, normalizedTitle, StringComparison.Ordinal)
                    && string.Equals(current.Content, normalizedContent, StringComparison.Ordinal);
                if (replay) return ToRecord(current);
                throw new NoteSelectionStaleException(normalized.Id);
            }

            if (string.Equals(current.Title, normalizedTitle, StringComparison.Ordinal)
                && string.Equals(current.Content, normalizedContent, StringComparison.Ordinal))
            {
                return ToRecord(current);
            }

            DateTimeOffset now = GetUtcNowAfter(current.UpdatedAtUtc);
            NoteDocument updated = WithIntegrity(new NoteDocument
            {
                SchemaVersion = CurrentSchemaVersion,
                Id = current.Id,
                Title = normalizedTitle,
                Content = normalizedContent,
                CreatedAtUtc = current.CreatedAtUtc,
                UpdatedAtUtc = now,
                Revision = checked(current.Revision + 1),
                IdempotencyKey = current.IdempotencyKey,
            });
            ReplaceDocumentUnsafe(GetPrimaryPath(current.Id), updated);
            return ToRecord(updated);
        }
    }

    public IReadOnlyList<NoteRecord> List(NoteListScope scope = NoteListScope.Active)
    {
        if (!Enum.IsDefined(scope))
        {
            throw new ArgumentOutOfRangeException(nameof(scope));
        }

        lock (_rootLock)
        {
            EnsureSafeStorageTreeUnsafe();
            DeleteAbandonedTemporaryFilesUnsafe();

            List<NoteRecord> results = [];
            foreach (Guid id in EnumerateStoredIdsUnsafe())
            {
                NoteDocument document = ReadDocumentWithRecoveryUnsafe(id);
                bool include = scope switch
                {
                    NoteListScope.Active => !document.TrashedAtUtc.HasValue,
                    NoteListScope.Trashed => document.TrashedAtUtc.HasValue,
                    NoteListScope.All => true,
                    _ => false,
                };

                if (include)
                {
                    results.Add(ToRecord(document));
                }
            }

            return results
                .OrderByDescending(static note => note.UpdatedAtUtc)
                .ThenBy(static note => note.Id)
                .ToArray();
        }
    }

    public NotePage ListPage(NoteListScope scope, int limit, int offset)
    {
        if (!Enum.IsDefined(scope))
        {
            throw new ArgumentOutOfRangeException(nameof(scope));
        }

        if (limit is < 1 or > MaximumListPageSize)
        {
            throw new ArgumentOutOfRangeException(nameof(limit));
        }

        ArgumentOutOfRangeException.ThrowIfNegative(offset);

        lock (_rootLock)
        {
            EnsureSafeStorageTreeUnsafe();
            DeleteAbandonedTemporaryFilesUnsafe();

            List<NoteSummaryRecord> summaries = new(_maximumStoredNotes);
            foreach (Guid id in EnumerateStoredIdsUnsafe())
            {
                NoteDocument document = ReadDocumentWithRecoveryUnsafe(id);
                if (ShouldInclude(document, scope))
                {
                    summaries.Add(ToSummary(document));
                }
            }

            NoteSummaryRecord[] page = summaries
                .OrderByDescending(static note => note.UpdatedAtUtc)
                .ThenBy(static note => note.Id)
                .Skip(offset)
                .Take(limit)
                .ToArray();
            return new NotePage(page, summaries.Count, limit, offset);
        }
    }

    public IReadOnlyList<NoteSummaryRecord> Search(string query, bool includeTrashed, int limit)
    {
        string normalized = ValidateAndNormalizeText(
            query, nameof(query), MaximumTitleUtf8Bytes,
            allowLineBreaks: false, allowEmpty: false, trim: true);
        if (limit is < 1 or > MaximumListPageSize) throw new ArgumentOutOfRangeException(nameof(limit));

        lock (_rootLock)
        {
            EnsureSafeStorageTreeUnsafe();
            DeleteAbandonedTemporaryFilesUnsafe();
            return EnumerateStoredIdsUnsafe()
                .Select(ReadDocumentWithRecoveryUnsafe)
                .Where(document => (includeTrashed || !document.TrashedAtUtc.HasValue)
                    && (document.Title.Contains(normalized, StringComparison.OrdinalIgnoreCase)
                        || document.Content.Contains(normalized, StringComparison.OrdinalIgnoreCase)))
                .OrderByDescending(static document => document.UpdatedAtUtc)
                .ThenBy(static document => document.Id)
                .Take(limit)
                .Select(ToSummary)
                .ToArray();
        }
    }

    public NoteRecord Trash(Guid id)
    {
        ValidateId(id);

        lock (_rootLock)
        {
            EnsureSafeStorageTreeUnsafe();
            NoteDocument current = ReadDocumentWithRecoveryUnsafe(id);
            if (current.TrashedAtUtc.HasValue)
            {
                return ToRecord(current);
            }

            DateTimeOffset now = GetUtcNowAfter(current.UpdatedAtUtc);
            NoteDocument trashed = WithIntegrity(new NoteDocument
            {
                SchemaVersion = CurrentSchemaVersion,
                Id = current.Id,
                Title = current.Title,
                Content = current.Content,
                CreatedAtUtc = current.CreatedAtUtc,
                UpdatedAtUtc = now,
                TrashedAtUtc = now,
                Revision = checked(current.Revision + 1),
                IdempotencyKey = current.IdempotencyKey,
            });
            ReplaceDocumentUnsafe(GetPrimaryPath(id), trashed);
            return ToRecord(trashed);
        }
    }

    public NoteRecord TrashExactTitle(string title)
    {
        string normalizedTitle = NormalizeTitleSelector(title);

        lock (_rootLock)
        {
            EnsureSafeStorageTreeUnsafe();
            DeleteAbandonedTemporaryFilesUnsafe();
            NoteDocument selected = FindUniqueByTitleUnsafe(normalizedTitle, NoteListScope.All);
            return Trash(selected.Id);
        }
    }

    public NoteRecord TrashSelected(NoteSelection selection)
    {
        NoteSelection normalized = NormalizeSelection(selection);

        lock (_rootLock)
        {
            EnsureSafeStorageTreeUnsafe();
            DeleteAbandonedTemporaryFilesUnsafe();
            NoteDocument current = ReadDocumentWithRecoveryUnsafe(normalized.Id);
            if (MatchesSelection(current, normalized))
            {
                return Trash(current.Id);
            }

            if (IsReachedReplay(current, normalized, targetIsTrashed: true))
            {
                return ToRecord(current);
            }

            throw new NoteSelectionStaleException(normalized.Id);
        }
    }

    public NoteRecord Restore(Guid id)
    {
        ValidateId(id);

        lock (_rootLock)
        {
            EnsureSafeStorageTreeUnsafe();
            NoteDocument current = ReadDocumentWithRecoveryUnsafe(id);
            if (!current.TrashedAtUtc.HasValue)
            {
                return ToRecord(current);
            }

            DateTimeOffset now = GetUtcNowAfter(current.UpdatedAtUtc);
            NoteDocument restored = WithIntegrity(new NoteDocument
            {
                SchemaVersion = CurrentSchemaVersion,
                Id = current.Id,
                Title = current.Title,
                Content = current.Content,
                CreatedAtUtc = current.CreatedAtUtc,
                UpdatedAtUtc = now,
                Revision = checked(current.Revision + 1),
                IdempotencyKey = current.IdempotencyKey,
            });
            ReplaceDocumentUnsafe(GetPrimaryPath(id), restored);
            return ToRecord(restored);
        }
    }

    public NoteRecord RestoreExactTitle(string title)
    {
        string normalizedTitle = NormalizeTitleSelector(title);

        lock (_rootLock)
        {
            EnsureSafeStorageTreeUnsafe();
            DeleteAbandonedTemporaryFilesUnsafe();
            NoteDocument selected = FindUniqueByTitleUnsafe(normalizedTitle, NoteListScope.All);
            return Restore(selected.Id);
        }
    }

    public NoteRecord RestoreSelected(NoteSelection selection)
    {
        NoteSelection normalized = NormalizeSelection(selection);

        lock (_rootLock)
        {
            EnsureSafeStorageTreeUnsafe();
            DeleteAbandonedTemporaryFilesUnsafe();
            NoteDocument current = ReadDocumentWithRecoveryUnsafe(normalized.Id);
            if (MatchesSelection(current, normalized))
            {
                return Restore(current.Id);
            }

            if (IsReachedReplay(current, normalized, targetIsTrashed: false))
            {
                return ToRecord(current);
            }

            throw new NoteSelectionStaleException(normalized.Id);
        }
    }

    private static string NormalizeTitleSelector(string title) =>
        ValidateAndNormalizeText(
            title,
            nameof(title),
            MaximumTitleUtf8Bytes,
            allowLineBreaks: false,
            allowEmpty: false,
            trim: true);

    private static NoteSelection NormalizeSelection(NoteSelection selection)
    {
        ArgumentNullException.ThrowIfNull(selection);
        ValidateId(selection.Id);
        if (selection.ExpectedRevision < 1)
        {
            throw new NoteValidationException("expectedRevision must be positive.");
        }

        string expectedTitle = NormalizeTitleSelector(selection.ExpectedTitle);
        return selection with { ExpectedTitle = expectedTitle };
    }

    private static bool MatchesSelection(NoteDocument document, NoteSelection selection) =>
        document.Id == selection.Id
        && string.Equals(document.Title, selection.ExpectedTitle, StringComparison.OrdinalIgnoreCase)
        && document.Revision == selection.ExpectedRevision
        && document.TrashedAtUtc.HasValue == selection.ExpectedIsTrashed;

    private static bool IsReachedReplay(
        NoteDocument document,
        NoteSelection selection,
        bool targetIsTrashed) =>
        selection.ExpectedIsTrashed != targetIsTrashed
        && selection.ExpectedRevision < long.MaxValue
        && document.Id == selection.Id
        && string.Equals(document.Title, selection.ExpectedTitle, StringComparison.OrdinalIgnoreCase)
        && document.Revision == selection.ExpectedRevision + 1
        && document.TrashedAtUtc.HasValue == targetIsTrashed;

    private NoteDocument FindUniqueByTitleUnsafe(string normalizedTitle, NoteListScope scope)
    {
        List<NoteDocument> matches = [];
        foreach (Guid id in EnumerateStoredIdsUnsafe())
        {
            NoteDocument document = ReadDocumentWithRecoveryUnsafe(id);
            if (ShouldInclude(document, scope)
                && string.Equals(document.Title, normalizedTitle, StringComparison.OrdinalIgnoreCase))
            {
                matches.Add(document);
            }
        }

        if (matches.Count == 0)
        {
            throw new NoteTitleNotFoundException(scope);
        }

        if (matches.Count == 1)
        {
            return matches[0];
        }

        NoteAmbiguityCandidate[] candidates = matches
            .OrderByDescending(static document => document.UpdatedAtUtc)
            .ThenBy(static document => document.Id)
            .Select(static document => new NoteAmbiguityCandidate(
                document.Id,
                document.Title,
                CreateContentPreview(document.Content),
                document.CreatedAtUtc,
                document.UpdatedAtUtc,
                document.Revision,
                document.TrashedAtUtc.HasValue))
            .ToArray();
        throw new NoteTitleAmbiguousException(scope, candidates);
    }

    private static string CreateContentPreview(string content)
    {
        var preview = new StringBuilder(Math.Min(content.Length, MaximumContentPreviewUtf8Bytes));
        int utf8Bytes = 0;
        bool pendingSpace = false;
        foreach (Rune rune in content.EnumerateRunes())
        {
            if (Rune.IsWhiteSpace(rune))
            {
                pendingSpace = preview.Length > 0;
                continue;
            }

            int requiredBytes = rune.Utf8SequenceLength + (pendingSpace ? 1 : 0);
            if (utf8Bytes + requiredBytes > MaximumContentPreviewUtf8Bytes)
            {
                break;
            }

            if (pendingSpace)
            {
                preview.Append(' ');
                utf8Bytes++;
                pendingSpace = false;
            }

            preview.Append(rune);
            utf8Bytes += rune.Utf8SequenceLength;
        }

        return preview.ToString();
    }

    private static string ValidateAndNormalizeRootPath(string rootDirectory)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(rootDirectory);
        if (!Path.IsPathFullyQualified(rootDirectory))
        {
            throw new UnsafeNoteStorePathException("The note store root must be an absolute path.");
        }

        if (rootDirectory.StartsWith("\\\\", StringComparison.Ordinal))
        {
            throw new UnsafeNoteStorePathException(
                "The note store root must be on a local drive; UNC and device paths are forbidden.");
        }

        string rootPart = Path.GetPathRoot(rootDirectory) ?? string.Empty;
        string remainder = rootDirectory[rootPart.Length..];
        string[] segments = remainder.Split(
            [Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar],
            StringSplitOptions.RemoveEmptyEntries);
        if (segments.Any(static segment => segment is "." or ".."))
        {
            throw new UnsafeNoteStorePathException("The note store root cannot contain traversal segments.");
        }

        if (remainder.Contains(':', StringComparison.Ordinal))
        {
            throw new UnsafeNoteStorePathException("Alternate data stream syntax is not allowed in the note store root.");
        }

        string normalized;
        try
        {
            normalized = Path.TrimEndingDirectorySeparator(Path.GetFullPath(rootDirectory));
        }
        catch (Exception exception) when (exception is ArgumentException or NotSupportedException or PathTooLongException)
        {
            throw new UnsafeNoteStorePathException("The note store root is not a valid path.", exception);
        }

        string? normalizedRoot = Path.GetPathRoot(normalized);
        if (normalizedRoot is not null
            && string.Equals(
                Path.TrimEndingDirectorySeparator(normalizedRoot),
                normalized,
                StringComparison.OrdinalIgnoreCase))
        {
            throw new UnsafeNoteStorePathException("A volume root cannot be used as the note store root.");
        }

        return normalized;
    }

    private static string ValidateAndNormalizeText(
        string value,
        string parameterName,
        int maximumUtf8Bytes,
        bool allowLineBreaks,
        bool allowEmpty,
        bool trim)
    {
        ArgumentNullException.ThrowIfNull(value, parameterName);

        string normalized;
        try
        {
            normalized = value.Normalize(NormalizationForm.FormC);
            _ = StrictUtf8.GetByteCount(normalized);
        }
        catch (Exception exception) when (exception is ArgumentException or EncoderFallbackException)
        {
            throw new NoteValidationException($"{parameterName} is not valid Unicode text.", exception);
        }

        if (trim)
        {
            normalized = normalized.Trim();
        }

        if (!allowEmpty && normalized.Length == 0)
        {
            throw new NoteValidationException($"{parameterName} cannot be empty.");
        }

        foreach (char character in normalized)
        {
            if (character == '\0'
                || (char.IsControl(character)
                    && !(allowLineBreaks && character is '\r' or '\n' or '\t')))
            {
                throw new NoteValidationException($"{parameterName} contains a disallowed control character.");
            }
        }

        if (StrictUtf8.GetByteCount(normalized) > maximumUtf8Bytes)
        {
            throw new NoteValidationException(
                string.Create(
                    CultureInfo.InvariantCulture,
                    $"{parameterName} exceeds the {maximumUtf8Bytes}-byte UTF-8 limit."));
        }

        return normalized;
    }

    private static void ValidateId(Guid id)
    {
        if (id == Guid.Empty)
        {
            throw new NoteValidationException("A note ID cannot be empty.");
        }
    }

    private static NoteRecord ToRecord(NoteDocument document) =>
        new(
            document.Id,
            document.Title,
            document.Content,
            document.CreatedAtUtc,
            document.UpdatedAtUtc,
            document.TrashedAtUtc,
            document.Revision);

    private static NoteSummaryRecord ToSummary(NoteDocument document) =>
        new(
            document.Id,
            document.Title,
            document.CreatedAtUtc,
            document.UpdatedAtUtc,
            document.TrashedAtUtc,
            document.Revision);

    private static bool ShouldInclude(NoteDocument document, NoteListScope scope) =>
        scope switch
        {
            NoteListScope.Active => !document.TrashedAtUtc.HasValue,
            NoteListScope.Trashed => document.TrashedAtUtc.HasValue,
            NoteListScope.All => true,
            _ => false,
        };

    private static NoteDocument WithIntegrity(NoteDocument document)
    {
        string integrity = ComputeIntegrity(document);
        return new NoteDocument
        {
            SchemaVersion = document.SchemaVersion,
            Id = document.Id,
            Title = document.Title,
            Content = document.Content,
            CreatedAtUtc = document.CreatedAtUtc,
            UpdatedAtUtc = document.UpdatedAtUtc,
            TrashedAtUtc = document.TrashedAtUtc,
            Revision = document.Revision,
            IdempotencyKey = document.IdempotencyKey,
            IntegritySha256 = integrity,
        };
    }

    private static string ComputeIntegrity(NoteDocument document)
    {
        using IncrementalHash hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
        AppendInt32(hash, document.SchemaVersion);
        Span<byte> idBytes = stackalloc byte[16];
        _ = document.Id.TryWriteBytes(idBytes);
        hash.AppendData(idBytes);
        AppendString(hash, document.Title);
        AppendString(hash, document.Content);
        AppendInt64(hash, document.CreatedAtUtc.UtcTicks);
        AppendInt64(hash, document.UpdatedAtUtc.UtcTicks);
        AppendInt64(hash, document.TrashedAtUtc?.UtcTicks ?? long.MinValue);
        AppendInt64(hash, document.Revision);
        AppendString(hash, document.IdempotencyKey);
        return Convert.ToHexString(hash.GetHashAndReset());
    }

    private static void AppendString(IncrementalHash hash, string? value)
    {
        if (value is null)
        {
            AppendInt32(hash, -1);
            return;
        }

        byte[] bytes = StrictUtf8.GetBytes(value);
        AppendInt32(hash, bytes.Length);
        hash.AppendData(bytes);
    }

    private static void AppendInt32(IncrementalHash hash, int value)
    {
        Span<byte> bytes = stackalloc byte[sizeof(int)];
        BinaryPrimitives.WriteInt32LittleEndian(bytes, value);
        hash.AppendData(bytes);
    }

    private static void AppendInt64(IncrementalHash hash, long value)
    {
        Span<byte> bytes = stackalloc byte[sizeof(long)];
        BinaryPrimitives.WriteInt64LittleEndian(bytes, value);
        hash.AppendData(bytes);
    }

    private void InitializeStorageUnsafe()
    {
        ValidateExistingPathChainDoesNotReparse(_rootDirectory);
        Directory.CreateDirectory(_rootDirectory);
        ValidateExistingPathChainDoesNotReparse(_rootDirectory);
        Directory.CreateDirectory(_notesDirectory);
        EnsureSafeStorageTreeUnsafe();
        DeleteAbandonedTemporaryFilesUnsafe();
    }

    private void EnsureSafeStorageTreeUnsafe()
    {
        ValidateExistingPathChainDoesNotReparse(_rootDirectory);
        ValidateDirectory(_rootDirectory);
        ValidateDirectory(_notesDirectory);

        foreach (string entry in Directory.EnumerateFileSystemEntries(_notesDirectory, "*", SearchOption.TopDirectoryOnly))
        {
            FileAttributes attributes = GetAttributesOrThrow(entry);
            if ((attributes & FileAttributes.ReparsePoint) != 0)
            {
                throw new UnsafeNoteStorePathException($"Reparse points are forbidden in the note store: '{entry}'.");
            }

            if ((attributes & FileAttributes.Directory) != 0)
            {
                throw new UnsafeNoteStorePathException($"Subdirectories are forbidden in the note store: '{entry}'.");
            }

            ValidateStorageFileName(Path.GetFileName(entry));
        }
    }

    private static void ValidateStorageFileName(string fileName)
    {
        if (fileName.StartsWith(TemporaryPrefix, StringComparison.Ordinal)
            && fileName.EndsWith(TemporarySuffix, StringComparison.Ordinal))
        {
            return;
        }

        string idText;
        if (fileName.EndsWith(".json" + BackupSuffix, StringComparison.OrdinalIgnoreCase))
        {
            idText = fileName[..^(".json" + BackupSuffix).Length];
        }
        else if (fileName.EndsWith(".json", StringComparison.OrdinalIgnoreCase))
        {
            idText = fileName[..^".json".Length];
        }
        else
        {
            throw new NoteCorruptionException($"Unexpected file in the note store: '{fileName}'.");
        }

        if (!Guid.TryParseExact(idText, "D", out Guid id) || id == Guid.Empty)
        {
            throw new NoteCorruptionException($"Invalid note file name: '{fileName}'.");
        }
    }

    private static void ValidateExistingPathChainDoesNotReparse(string path)
    {
        string? current = path;
        while (!string.IsNullOrEmpty(current))
        {
            if (Directory.Exists(current) || File.Exists(current))
            {
                FileAttributes attributes = GetAttributesOrThrow(current);
                if ((attributes & FileAttributes.ReparsePoint) != 0)
                {
                    throw new UnsafeNoteStorePathException(
                        $"The note store path crosses a reparse point: '{current}'.");
                }
            }

            DirectoryInfo? parent = Directory.GetParent(current);
            current = parent?.FullName;
        }
    }

    private static void ValidateDirectory(string path)
    {
        FileAttributes attributes = GetAttributesOrThrow(path);
        if ((attributes & FileAttributes.Directory) == 0
            || (attributes & FileAttributes.ReparsePoint) != 0)
        {
            throw new UnsafeNoteStorePathException($"A real directory was expected at '{path}'.");
        }
    }

    private static FileAttributes GetAttributesOrThrow(string path)
    {
        try
        {
            return File.GetAttributes(path);
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            throw new UnsafeNoteStorePathException($"The note store path cannot be safely inspected: '{path}'.", exception);
        }
    }

    private NoteDocument? FindByIdempotencyKeyUnsafe(
        string idempotencyKey,
        IReadOnlyList<Guid> storedIds)
    {
        NoteDocument? match = null;
        foreach (Guid id in storedIds)
        {
            NoteDocument document = ReadDocumentWithRecoveryUnsafe(id);
            if (string.Equals(document.IdempotencyKey, idempotencyKey, StringComparison.Ordinal))
            {
                if (match is not null)
                {
                    throw new NoteCorruptionException(
                        "The note store contains a duplicated idempotency key.");
                }

                match = document;
            }
        }

        return match;
    }

    private Guid[] EnumerateStoredIdsUnsafe()
    {
        HashSet<Guid> ids = [];
        foreach (string path in Directory.EnumerateFiles(_notesDirectory, "*", SearchOption.TopDirectoryOnly))
        {
            string fileName = Path.GetFileName(path);
            if (fileName.StartsWith(TemporaryPrefix, StringComparison.Ordinal)
                && fileName.EndsWith(TemporarySuffix, StringComparison.Ordinal))
            {
                continue;
            }

            ValidateStorageFileName(fileName);
            string idText = fileName.EndsWith(".json" + BackupSuffix, StringComparison.OrdinalIgnoreCase)
                ? fileName[..^(".json" + BackupSuffix).Length]
                : fileName[..^".json".Length];
            Guid id = Guid.ParseExact(idText, "D");

            _ = ids.Add(id);
            if (ids.Count > _maximumStoredNotes)
            {
                throw new NoteCapacityException(_maximumStoredNotes);
            }
        }

        return ids.Order().ToArray();
    }

    private NoteDocument ReadDocumentWithRecoveryUnsafe(Guid id)
    {
        string primaryPath = GetPrimaryPath(id);
        string backupPath = GetBackupPath(primaryPath);
        bool primaryExists = File.Exists(primaryPath);
        bool backupExists = File.Exists(backupPath);

        if (!primaryExists && !backupExists)
        {
            throw new NoteNotFoundException(id);
        }

        Exception? primaryFailure = null;
        if (primaryExists)
        {
            try
            {
                return ReadAndValidateDocumentUnsafe(primaryPath, id);
            }
            catch (NoteCorruptionException exception)
            {
                primaryFailure = exception;
            }
        }

        if (!backupExists)
        {
            throw primaryFailure ?? new NoteNotFoundException(id);
        }

        try
        {
            NoteDocument recovered = ReadAndValidateDocumentUnsafe(backupPath, id);
            RecoverBackupUnsafe(primaryPath, backupPath);
            NoteDocument verified = ReadAndValidateDocumentUnsafe(primaryPath, id);
            if (!DocumentsEqual(recovered, verified))
            {
                throw new NoteCorruptionException($"Recovery verification failed for note '{id:D}'.");
            }

            return verified;
        }
        catch (NoteCorruptionException backupFailure)
        {
            throw new NoteCorruptionException(
                $"Neither the active nor recovery document is valid for note '{id:D}'.",
                new AggregateException(primaryFailure ?? new IOException("The active document is missing."), backupFailure));
        }
    }

    private static NoteDocument ReadAndValidateDocumentUnsafe(string path, Guid expectedId)
    {
        ValidateRegularFile(path);
        byte[] bytes;
        try
        {
            using FileStream stream = new(
                path,
                FileMode.Open,
                FileAccess.Read,
                FileShare.Read,
                bufferSize: 4096,
                FileOptions.SequentialScan);
            if (stream.Length <= 0 || stream.Length > MaximumDocumentBytes)
            {
                throw new NoteCorruptionException($"The note document has an invalid length: '{path}'.");
            }

            bytes = new byte[stream.Length];
            stream.ReadExactly(bytes);
        }
        catch (NoteCorruptionException)
        {
            throw;
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            throw new NoteCorruptionException($"The note document could not be read: '{path}'.", exception);
        }

        NoteDocument document;
        try
        {
            document = JsonSerializer.Deserialize(bytes, NotesJsonContext.Default.NoteDocument)
                ?? throw new NoteCorruptionException($"The note document is empty: '{path}'.");
        }
        catch (NoteCorruptionException)
        {
            throw;
        }
        catch (JsonException exception)
        {
            throw new NoteCorruptionException($"The note document is not valid JSON: '{path}'.", exception);
        }

        ValidateDocument(document, expectedId, path);
        ValidateRegularFile(path);
        return document;
    }

    private static void ValidateDocument(NoteDocument document, Guid expectedId, string path)
    {
        if (document.SchemaVersion != CurrentSchemaVersion
            || document.Id != expectedId
            || document.Id == Guid.Empty
            || document.Revision <= 0
            || document.CreatedAtUtc.Offset != TimeSpan.Zero
            || document.UpdatedAtUtc.Offset != TimeSpan.Zero
            || document.UpdatedAtUtc < document.CreatedAtUtc
            || (document.TrashedAtUtc.HasValue
                && (document.TrashedAtUtc.Value.Offset != TimeSpan.Zero
                    || document.TrashedAtUtc.Value < document.CreatedAtUtc
                    || document.TrashedAtUtc.Value > document.UpdatedAtUtc)))
        {
            throw new NoteCorruptionException($"The note document contains invalid metadata: '{path}'.");
        }

        if (document.Title is null || document.Content is null || document.IntegritySha256 is null)
        {
            throw new NoteCorruptionException($"The note document contains null required fields: '{path}'.");
        }

        try
        {
            string normalizedTitle = ValidateAndNormalizeText(
                document.Title,
                nameof(document.Title),
                MaximumTitleUtf8Bytes,
                allowLineBreaks: false,
                allowEmpty: false,
                trim: true);
            string normalizedContent = ValidateAndNormalizeText(
                document.Content,
                nameof(document.Content),
                MaximumContentUtf8Bytes,
                allowLineBreaks: true,
                allowEmpty: true,
                trim: false);
            if (document.IdempotencyKey is not null)
            {
                string normalizedKey = ValidateAndNormalizeText(
                    document.IdempotencyKey,
                    nameof(document.IdempotencyKey),
                    MaximumIdempotencyKeyUtf8Bytes,
                    allowLineBreaks: false,
                    allowEmpty: false,
                    trim: true);
                if (!string.Equals(document.IdempotencyKey, normalizedKey, StringComparison.Ordinal))
                {
                    throw new NoteValidationException("The stored idempotency key is not normalized.");
                }
            }

            if (!string.Equals(document.Title, normalizedTitle, StringComparison.Ordinal)
                || !string.Equals(document.Content, normalizedContent, StringComparison.Ordinal))
            {
                throw new NoteValidationException("The stored note text is not normalized.");
            }
        }
        catch (NoteValidationException exception)
        {
            throw new NoteCorruptionException($"The note document contains invalid text: '{path}'.", exception);
        }

        string expectedIntegrity = ComputeIntegrity(document);
        if (!CryptographicOperations.FixedTimeEquals(
                StrictUtf8.GetBytes(expectedIntegrity),
                StrictUtf8.GetBytes(document.IntegritySha256)))
        {
            throw new NoteCorruptionException($"The note document failed its integrity check: '{path}'.");
        }
    }

    private static void ValidateRegularFile(string path)
    {
        FileAttributes attributes = GetAttributesOrThrow(path);
        if ((attributes & (FileAttributes.Directory | FileAttributes.ReparsePoint)) != 0)
        {
            throw new UnsafeNoteStorePathException($"A regular non-reparse file was expected at '{path}'.");
        }
    }

    private void WriteNewDocumentUnsafe(string primaryPath, NoteDocument document)
    {
        string temporaryPath = WriteTemporaryDocumentUnsafe(document);
        try
        {
            VerifyPersistedDocumentUnsafe(temporaryPath, document);
            File.Move(temporaryPath, primaryPath, overwrite: false);
            try
            {
                _afterNewDocumentCommitted?.Invoke(primaryPath);
                VerifyPersistedDocumentUnsafe(primaryPath, document);
            }
            catch (Exception exception) when (IsTransientPostCommitReadFailure(exception))
            {
                // The exact bytes were flushed and verified before the atomic move.
                // Once Move succeeds the create is committed; an inability to reread
                // it must not be reported as a terminal failure that invites a duplicate.
            }
        }
        catch
        {
            DeleteRegularFileIfPresentUnsafe(temporaryPath);
            throw;
        }
    }

    private static bool IsTransientPostCommitReadFailure(Exception exception) =>
        exception is IOException or UnauthorizedAccessException
        || exception is NoteCorruptionException
        {
            InnerException: IOException or UnauthorizedAccessException,
        };

    private void ReplaceDocumentUnsafe(string primaryPath, NoteDocument document)
    {
        ValidateRegularFile(primaryPath);
        string backupPath = GetBackupPath(primaryPath);
        DeleteRegularFileIfPresentUnsafe(backupPath);
        string temporaryPath = WriteTemporaryDocumentUnsafe(document);
        try
        {
            global::Baxy.Providers.Windows.AtomicFileReplacement.Replace(
                temporaryPath,
                primaryPath,
                backupPath,
                ignoreMetadataErrors: true);
            VerifyPersistedDocumentUnsafe(primaryPath, document);
            _ = ReadAndValidateDocumentUnsafe(backupPath, document.Id);
        }
        catch
        {
            DeleteRegularFileIfPresentUnsafe(temporaryPath);
            throw;
        }
    }

    private string WriteTemporaryDocumentUnsafe(NoteDocument document)
    {
        byte[] payload = JsonSerializer.SerializeToUtf8Bytes(document, NotesJsonContext.Default.NoteDocument);
        if (payload.LongLength > MaximumDocumentBytes)
        {
            throw new NoteValidationException("The serialized note exceeds the storage limit.");
        }

        string temporaryPath = GetContainedPath(
            _notesDirectory,
            TemporaryPrefix + Guid.NewGuid().ToString("N", CultureInfo.InvariantCulture) + TemporarySuffix);
        try
        {
            using FileStream stream = new(
                temporaryPath,
                FileMode.CreateNew,
                FileAccess.Write,
                FileShare.None,
                bufferSize: 4096,
                FileOptions.WriteThrough);
            stream.Write(payload);
            stream.Flush(flushToDisk: true);
            return temporaryPath;
        }
        catch
        {
            DeleteRegularFileIfPresentUnsafe(temporaryPath);
            throw;
        }
    }

    private static void VerifyPersistedDocumentUnsafe(string path, NoteDocument expected)
    {
        NoteDocument actual = ReadAndValidateDocumentUnsafe(path, expected.Id);
        if (!DocumentsEqual(expected, actual))
        {
            throw new NoteCorruptionException($"The persisted note did not match the requested state: '{path}'.");
        }
    }

    private static bool DocumentsEqual(NoteDocument left, NoteDocument right) =>
        left.SchemaVersion == right.SchemaVersion
        && left.Id == right.Id
        && string.Equals(left.Title, right.Title, StringComparison.Ordinal)
        && string.Equals(left.Content, right.Content, StringComparison.Ordinal)
        && left.CreatedAtUtc == right.CreatedAtUtc
        && left.UpdatedAtUtc == right.UpdatedAtUtc
        && left.TrashedAtUtc == right.TrashedAtUtc
        && left.Revision == right.Revision
        && string.Equals(left.IdempotencyKey, right.IdempotencyKey, StringComparison.Ordinal)
        && string.Equals(left.IntegritySha256, right.IntegritySha256, StringComparison.Ordinal);

    private static void RecoverBackupUnsafe(string primaryPath, string backupPath)
    {
        if (File.Exists(primaryPath))
        {
            string directory = Path.GetDirectoryName(primaryPath)
                ?? throw new UnsafeNoteStorePathException("The note recovery path has no parent directory.");
            string discardedPath = Path.Combine(
                directory,
                TemporaryPrefix + Guid.NewGuid().ToString("N", CultureInfo.InvariantCulture) + TemporarySuffix);
            try
            {
                global::Baxy.Providers.Windows.AtomicFileReplacement.Replace(
                    backupPath,
                    primaryPath,
                    discardedPath,
                    ignoreMetadataErrors: true);
            }
            finally
            {
                DeleteRegularFileIfPresentUnsafe(discardedPath);
            }
        }
        else
        {
            File.Move(backupPath, primaryPath, overwrite: false);
        }
    }

    private void DeleteAbandonedTemporaryFilesUnsafe()
    {
        foreach (string path in Directory.EnumerateFiles(
                     _notesDirectory,
                     TemporaryPrefix + "*" + TemporarySuffix,
                     SearchOption.TopDirectoryOnly))
        {
            DeleteRegularFileIfPresentUnsafe(path);
        }
    }

    private static void DeleteRegularFileIfPresentUnsafe(string path)
    {
        if (!File.Exists(path))
        {
            return;
        }

        ValidateRegularFile(path);
        File.Delete(path);
    }

    private string GetPrimaryPath(Guid id) =>
        GetContainedPath(_notesDirectory, id.ToString("D", CultureInfo.InvariantCulture) + ".json");

    private static string GetBackupPath(string primaryPath) => primaryPath + BackupSuffix;

    private static string GetContainedPath(string root, string childName)
    {
        string candidate = Path.GetFullPath(Path.Combine(root, childName));
        string relative = Path.GetRelativePath(root, candidate);
        if (Path.IsPathFullyQualified(relative)
            || relative.Equals("..", StringComparison.Ordinal)
            || relative.StartsWith(".." + Path.DirectorySeparatorChar, StringComparison.Ordinal)
            || relative.StartsWith(".." + Path.AltDirectorySeparatorChar, StringComparison.Ordinal))
        {
            throw new UnsafeNoteStorePathException("A note store path escaped its configured root.");
        }

        return candidate;
    }

    private DateTimeOffset GetUtcNow() => _timeProvider.GetUtcNow().ToUniversalTime();

    private DateTimeOffset GetUtcNowAfter(DateTimeOffset previous)
    {
        DateTimeOffset now = GetUtcNow();
        return now > previous ? now : previous.AddTicks(1);
    }
}
