namespace Baxy.Providers.Windows.Notes;

/// <summary>
/// Selects which notes are returned by <see cref="INoteStore.List"/>.
/// </summary>
public enum NoteListScope
{
    Active,
    Trashed,
    All,
}

/// <summary>
/// An immutable snapshot of a note stored on the local machine.
/// </summary>
public sealed record NoteRecord(
    Guid Id,
    string Title,
    string Content,
    DateTimeOffset CreatedAtUtc,
    DateTimeOffset UpdatedAtUtc,
    DateTimeOffset? TrashedAtUtc,
    long Revision)
{
    public bool IsTrashed => TrashedAtUtc.HasValue;
}

/// <summary>
/// A bounded list projection that intentionally omits note content.
/// </summary>
public sealed record NoteSummaryRecord(
    Guid Id,
    string Title,
    DateTimeOffset CreatedAtUtc,
    DateTimeOffset UpdatedAtUtc,
    DateTimeOffset? TrashedAtUtc,
    long Revision)
{
    public bool IsTrashed => TrashedAtUtc.HasValue;
}

/// <summary>
/// One provider-level page of note summaries.
/// </summary>
public sealed record NotePage(
    IReadOnlyList<NoteSummaryRecord> Notes,
    int TotalCount,
    int Limit,
    int Offset);

/// <summary>
/// A bounded, content-safe candidate used to disambiguate notes with the same title.
/// </summary>
public sealed record NoteAmbiguityCandidate(
    Guid Id,
    string Title,
    string ContentPreview,
    DateTimeOffset CreatedAtUtc,
    DateTimeOffset UpdatedAtUtc,
    long Revision,
    bool IsTrashed);

/// <summary>
/// Binds a later operation to the exact note snapshot shown to the user.
/// </summary>
public sealed record NoteSelection(
    Guid Id,
    string ExpectedTitle,
    long ExpectedRevision,
    bool ExpectedIsTrashed);

/// <summary>
/// Durable local note operations exposed to the BAXY core.
/// </summary>
public interface INoteStore
{
    NoteRecord Create(string title, string content, string? idempotencyKey = null);

    NoteRecord Read(Guid id, bool includeTrashed = false);

    /// <summary>
    /// Reads the sole active note whose normalized title matches exactly, ignoring case.
    /// </summary>
    NoteRecord ReadExactTitle(string title);

    NoteRecord ReadSelected(NoteSelection selection);

    NoteRecord UpdateSelected(NoteSelection selection, string title, string content);

    IReadOnlyList<NoteRecord> List(NoteListScope scope = NoteListScope.Active);

    NotePage ListPage(NoteListScope scope, int limit, int offset);

    IReadOnlyList<NoteSummaryRecord> Search(string query, bool includeTrashed, int limit);

    NoteRecord Trash(Guid id);

    /// <summary>
    /// Trashes the sole note with the exact normalized title across every lifecycle state.
    /// A unique note already in the trash is returned unchanged for safe retries.
    /// </summary>
    NoteRecord TrashExactTitle(string title);

    NoteRecord TrashSelected(NoteSelection selection);

    NoteRecord Restore(Guid id);

    /// <summary>
    /// Restores the sole note with the exact normalized title across every lifecycle state.
    /// A unique active note is returned unchanged for safe retries.
    /// </summary>
    NoteRecord RestoreExactTitle(string title);

    NoteRecord RestoreSelected(NoteSelection selection);
}

public class NoteStoreException : Exception
{
    public NoteStoreException()
    {
    }

    public NoteStoreException(string message)
        : base(message)
    {
    }

    public NoteStoreException(string message, Exception innerException)
        : base(message, innerException)
    {
    }
}

public sealed class NoteValidationException : NoteStoreException
{
    public NoteValidationException(string message)
        : base(message)
    {
    }

    public NoteValidationException(string message, Exception innerException)
        : base(message, innerException)
    {
    }
}

public sealed class NoteNotFoundException : NoteStoreException
{
    public NoteNotFoundException(Guid id)
        : base($"Note '{id:D}' was not found.")
    {
        NoteId = id;
    }

    public Guid NoteId { get; }
}

public sealed class NoteTitleNotFoundException : NoteStoreException
{
    public NoteTitleNotFoundException(NoteListScope scope)
        : base("No note with that exact title was found in the requested scope.")
    {
        Scope = scope;
    }

    public NoteListScope Scope { get; }
}

public sealed class NoteTitleAmbiguousException : NoteStoreException
{
    public NoteTitleAmbiguousException(
        NoteListScope scope,
        IReadOnlyList<NoteAmbiguityCandidate> candidates)
        : base("More than one note has that exact title in the requested scope.")
    {
        ArgumentNullException.ThrowIfNull(candidates);
        if (candidates.Count < 2)
        {
            throw new ArgumentOutOfRangeException(
                nameof(candidates),
                "At least two ambiguity candidates are required.");
        }

        Scope = scope;
        Candidates = candidates.ToArray();
    }

    public NoteListScope Scope { get; }

    public int MatchCount => Candidates.Count;

    public IReadOnlyList<NoteAmbiguityCandidate> Candidates { get; }
}

public sealed class NoteSelectionStaleException : NoteStoreException
{
    public NoteSelectionStaleException(Guid id)
        : base($"The selected snapshot for note '{id:D}' is stale.")
    {
        NoteId = id;
    }

    public Guid NoteId { get; }
}

public sealed class NoteConflictException : NoteStoreException
{
    public NoteConflictException(string message)
        : base(message)
    {
    }
}

public sealed class NoteCapacityException : NoteStoreException
{
    public NoteCapacityException(int maximumStoredNotes)
        : base($"The note store has reached its {maximumStoredNotes}-note capacity.")
    {
        MaximumStoredNotes = maximumStoredNotes;
    }

    public int MaximumStoredNotes { get; }
}

public sealed class NoteCorruptionException : NoteStoreException
{
    public NoteCorruptionException(string message)
        : base(message)
    {
    }

    public NoteCorruptionException(string message, Exception innerException)
        : base(message, innerException)
    {
    }
}

public sealed class UnsafeNoteStorePathException : NoteStoreException
{
    public UnsafeNoteStorePathException(string message)
        : base(message)
    {
    }

    public UnsafeNoteStorePathException(string message, Exception innerException)
        : base(message, innerException)
    {
    }
}
