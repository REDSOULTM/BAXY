using System.Text.Json;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Notes;

namespace Baxy.Core.Operations;

internal abstract class NoteHandlerBase(INoteStore store) : IOperationHandler
{
    protected INoteStore Store { get; } = store ?? throw new ArgumentNullException(nameof(store));

    public abstract OperationDefinition Definition { get; }

    public ValueTask<OperationOutcome> ExecuteAsync(
        OperationInvocation invocation,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        try
        {
            return ValueTask.FromResult(Execute(invocation));
        }
        catch (JsonException)
        {
            return ValueTask.FromResult(OperationOutcome.Failure("invalid_arguments"));
        }
        catch (NoteValidationException)
        {
            return ValueTask.FromResult(OperationOutcome.Failure("invalid_note"));
        }
        catch (NoteNotFoundException)
        {
            return ValueTask.FromResult(OperationOutcome.Failure(
                "note_not_found",
                causeCode: "by_id"));
        }
        catch (NoteTitleNotFoundException)
        {
            return ValueTask.FromResult(OperationOutcome.Failure(
                "note_not_found",
                causeCode: "by_title"));
        }
        catch (NoteTitleAmbiguousException exception)
        {
            return ValueTask.FromResult(OperationOutcome.Failure(
                "note_ambiguous",
                SerializeAmbiguity(exception)));
        }
        catch (NoteSelectionStaleException)
        {
            return ValueTask.FromResult(OperationOutcome.Failure("note_selection_stale"));
        }
        catch (NoteConflictException)
        {
            return ValueTask.FromResult(OperationOutcome.Failure("idempotency_conflict"));
        }
        catch (NoteCapacityException)
        {
            return ValueTask.FromResult(OperationOutcome.Failure("note_capacity_reached"));
        }
        catch (NoteCorruptionException) when (Definition.Risk == OperationRisk.ReadOnly)
        {
            return ValueTask.FromResult(OperationOutcome.Failure("note_integrity_failed"));
        }
        catch (UnsafeNoteStorePathException) when (Definition.Risk == OperationRisk.ReadOnly)
        {
            return ValueTask.FromResult(OperationOutcome.Failure("unsafe_storage"));
        }
        catch (IOException) when (Definition.Risk == OperationRisk.ReadOnly)
        {
            return ValueTask.FromResult(OperationOutcome.Failure("storage_failed"));
        }
    }

    protected abstract OperationOutcome Execute(OperationInvocation invocation);

    protected static T Parse<T>(
        JsonElement arguments,
        System.Text.Json.Serialization.Metadata.JsonTypeInfo<T> typeInfo)
        where T : class =>
        JsonSerializer.Deserialize(arguments, typeInfo)
        ?? throw new JsonException("Arguments cannot be null.");

    protected static Guid ParseNoteId(string value)
    {
        if (!Guid.TryParseExact(value, "D", out Guid id) || id == Guid.Empty)
        {
            throw new NoteValidationException("noteId must be a canonical UUID.");
        }

        return id;
    }

    protected static NoteRecord SelectNote(
        NoteSelectorArguments arguments,
        Func<Guid, NoteRecord> selectById,
        Func<string, NoteRecord> selectByTitle,
        Func<NoteSelection, NoteRecord> selectSelected)
    {
        bool hasId = arguments.NoteId is not null;
        bool hasTitle = arguments.Title is not null;
        bool hasExpectedTitle = arguments.ExpectedTitle is not null;
        bool hasExpectedRevision = arguments.ExpectedRevision.HasValue;
        bool hasExpectedState = arguments.ExpectedIsTrashed.HasValue;
        bool hasAnyExpectation = hasExpectedTitle || hasExpectedRevision || hasExpectedState;
        bool hasAllExpectations = hasExpectedTitle && hasExpectedRevision && hasExpectedState;

        if (hasTitle)
        {
            if (hasId || hasAnyExpectation)
            {
                throw new JsonException("A title selector cannot contain an ID or snapshot expectations.");
            }

            return selectByTitle(arguments.Title!);
        }

        if (!hasId)
        {
            throw new JsonException("Exactly one of noteId or title must be provided.");
        }

        Guid id = ParseNoteId(arguments.NoteId!);
        if (!hasAnyExpectation)
        {
            return selectById(id);
        }

        if (!hasAllExpectations || arguments.ExpectedRevision < 1)
        {
            throw new JsonException("A selected note requires a complete valid snapshot.");
        }

        return selectSelected(new NoteSelection(
            id,
            arguments.ExpectedTitle!,
            arguments.ExpectedRevision!.Value,
            arguments.ExpectedIsTrashed!.Value));
    }

    protected static NoteResult ToResult(NoteRecord note) => new(
        note.Id.ToString("D"),
        note.Title,
        note.Content,
        note.CreatedAtUtc,
        note.UpdatedAtUtc,
        note.TrashedAtUtc,
        note.Revision,
        note.IsTrashed);

    protected static NoteSummaryResult ToSummary(NoteSummaryRecord note) => new(
        note.Id.ToString("D"),
        note.Title,
        note.CreatedAtUtc,
        note.UpdatedAtUtc,
        note.TrashedAtUtc,
        note.Revision,
        note.IsTrashed);

    protected static JsonElement Serialize(NoteResult result) =>
        JsonSerializer.SerializeToElement(result, CoreJsonContext.Default.NoteResult);

    private static JsonElement SerializeAmbiguity(NoteTitleAmbiguousException exception)
    {
        NoteAmbiguityCandidateResult[] candidates = exception.Candidates
            .Select(static candidate => new NoteAmbiguityCandidateResult(
                candidate.Id.ToString("D"),
                candidate.ContentPreview,
                candidate.CreatedAtUtc,
                candidate.UpdatedAtUtc,
                candidate.Revision,
                candidate.IsTrashed))
            .ToArray();
        var result = new NoteAmbiguityResult(candidates);
        return JsonSerializer.SerializeToElement(result, CoreJsonContext.Default.NoteAmbiguityResult);
    }
}

internal sealed class CreateNoteHandler(INoteStore store) : NoteHandlerBase(store)
{
    public override OperationDefinition Definition { get; } =
        ProductCatalog.CreateDefinition("note.create");

    protected override OperationOutcome Execute(OperationInvocation invocation)
    {
        CreateNoteArguments arguments = Parse(
            invocation.Arguments,
            CoreJsonContext.Default.CreateNoteArguments);
        NoteRecord created = Store.Create(
            arguments.Title,
            arguments.Content,
            invocation.InvocationId);
        NoteRecord observed;
        try
        {
            observed = Store.Read(created.Id);
        }
        catch (NoteNotFoundException)
        {
            return OperationOutcome.Failure(
                "verification_failed",
                effectMayHaveOccurred: true);
        }

        if (observed.Id != created.Id
            || observed.IsTrashed
            || !string.Equals(observed.Title, created.Title, StringComparison.Ordinal)
            || !string.Equals(observed.Content, created.Content, StringComparison.Ordinal))
        {
            return OperationOutcome.Failure(
                "verification_failed",
                effectMayHaveOccurred: true);
        }

        return OperationOutcome.Success(Serialize(ToResult(observed)));
    }
}

internal sealed class ReadNoteHandler(INoteStore store) : NoteHandlerBase(store)
{
    public override OperationDefinition Definition { get; } =
        ProductCatalog.CreateDefinition("note.read");

    protected override OperationOutcome Execute(OperationInvocation invocation)
    {
        NoteSelectorArguments arguments = Parse(
            invocation.Arguments,
            CoreJsonContext.Default.NoteSelectorArguments);
        NoteRecord note = SelectNote(
            arguments,
            id => Store.Read(id),
            Store.ReadExactTitle,
            Store.ReadSelected);
        return OperationOutcome.Success(Serialize(ToResult(note)));
    }
}

internal sealed class ListNotesHandler(INoteStore store) : NoteHandlerBase(store)
{
    private const int DefaultLimit = 50;
    private const int MaximumLimit = 100;

    public override OperationDefinition Definition { get; } =
        ProductCatalog.CreateDefinition("note.list");

    protected override OperationOutcome Execute(OperationInvocation invocation)
    {
        ListNotesArguments arguments = Parse(invocation.Arguments, CoreJsonContext.Default.ListNotesArguments);
        NoteListScope scope = arguments.Scope switch
        {
            null or "active" => NoteListScope.Active,
            "trashed" => NoteListScope.Trashed,
            "all" => NoteListScope.All,
            _ => throw new JsonException("Unknown note list scope."),
        };

        int limit = arguments.Limit ?? DefaultLimit;
        int offset = arguments.Offset ?? 0;
        if (limit is < 1 or > MaximumLimit)
        {
            throw new JsonException($"limit must be between 1 and {MaximumLimit}.");
        }

        if (offset < 0)
        {
            throw new JsonException("offset cannot be negative.");
        }

        NotePage page = Store.ListPage(scope, limit, offset);
        NoteSummaryResult[] notes = page.Notes
            .Select(ToSummary)
            .ToArray();
        string wireScope = scope.ToString().ToLowerInvariant();
        int? nextOffset = offset + notes.Length < page.TotalCount
            ? offset + notes.Length
            : null;
        var result = new NoteListResult(
            notes,
            notes.Length,
            page.TotalCount,
            wireScope,
            limit,
            offset,
            nextOffset);
        JsonElement json = JsonSerializer.SerializeToElement(result, CoreJsonContext.Default.NoteListResult);
        return OperationOutcome.Success(json);
    }
}

internal sealed class TrashNoteHandler(INoteStore store) : NoteHandlerBase(store)
{
    public override OperationDefinition Definition { get; } =
        ProductCatalog.CreateDefinition("note.trash");

    protected override OperationOutcome Execute(OperationInvocation invocation)
    {
        NoteSelectorArguments arguments = Parse(
            invocation.Arguments,
            CoreJsonContext.Default.NoteSelectorArguments);
        NoteRecord trashed = SelectNote(
            arguments,
            Store.Trash,
            Store.TrashExactTitle,
            Store.TrashSelected);
        NoteRecord verified = Store.Read(trashed.Id, includeTrashed: true);
        if (!verified.IsTrashed)
        {
            return OperationOutcome.Failure(
                "verification_failed",
                effectMayHaveOccurred: true);
        }

        return OperationOutcome.Success(Serialize(ToResult(verified)));
    }
}

internal sealed class SearchNotesHandler(INoteStore store) : NoteHandlerBase(store)
{
    public override OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition("note.search");

    protected override OperationOutcome Execute(OperationInvocation invocation)
    {
        NoteSearchArguments arguments = Parse(invocation.Arguments, CoreJsonContext.Default.NoteSearchArguments);
        int limit = arguments.Limit ?? 20;
        NoteSummaryRecord[] found = Store.Search(arguments.Query, arguments.IncludeTrashed ?? false, limit).ToArray();
        foreach (NoteSummaryRecord summary in found)
        {
            NoteRecord verified = Store.Read(summary.Id, includeTrashed: true);
            if (verified.Revision != summary.Revision
                || !string.Equals(verified.Title, summary.Title, StringComparison.Ordinal)
                || verified.IsTrashed != summary.IsTrashed)
            {
                return OperationOutcome.Failure(
                    "verification_failed",
                    effectMayHaveOccurred: false);
            }
        }

        NoteSummaryResult[] notes = found.Select(ToSummary).ToArray();
        var result = new NoteListResult(notes, notes.Length, notes.Length, "search", limit, 0, null);
        return OperationOutcome.Success(
            JsonSerializer.SerializeToElement(result, CoreJsonContext.Default.NoteListResult));
    }
}

internal sealed record NoteSearchArguments(string Query, bool? IncludeTrashed, int? Limit);

internal sealed class RestoreNoteHandler(INoteStore store) : NoteHandlerBase(store)
{
    public override OperationDefinition Definition { get; } =
        ProductCatalog.CreateDefinition("note.restore");

    protected override OperationOutcome Execute(OperationInvocation invocation)
    {
        NoteSelectorArguments arguments = Parse(
            invocation.Arguments,
            CoreJsonContext.Default.NoteSelectorArguments);
        NoteRecord restored = SelectNote(
            arguments,
            Store.Restore,
            Store.RestoreExactTitle,
            Store.RestoreSelected);
        NoteRecord verified = Store.Read(restored.Id);
        if (verified.IsTrashed)
        {
            return OperationOutcome.Failure(
                "verification_failed",
                effectMayHaveOccurred: true);
        }

        return OperationOutcome.Success(Serialize(ToResult(verified)));
    }
}

internal sealed class UpdateNoteHandler(INoteStore store) : NoteHandlerBase(store)
{
    public override OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition("note.update");

    protected override OperationOutcome Execute(OperationInvocation invocation)
    {
        NoteUpdateArguments arguments = Parse(invocation.Arguments, CoreJsonContext.Default.NoteUpdateArguments);
        if (!Guid.TryParseExact(arguments.NoteId, "D", out Guid id)
            || arguments.ExpectedRevision < 1
            || string.IsNullOrWhiteSpace(arguments.ExpectedTitle))
        {
            return OperationOutcome.Failure("invalid_note_selection");
        }

        NoteRecord updated = Store.UpdateSelected(
            new NoteSelection(id, arguments.ExpectedTitle, arguments.ExpectedRevision, false),
            arguments.Title,
            arguments.Content);
        NoteRecord verified = Store.Read(updated.Id);
        if (verified.Revision != updated.Revision
            || !string.Equals(verified.Title, updated.Title, StringComparison.Ordinal)
            || !string.Equals(verified.Content, updated.Content, StringComparison.Ordinal))
        {
            return OperationOutcome.Failure(
                "verification_failed",
                effectMayHaveOccurred: true);
        }
        return OperationOutcome.Success(Serialize(ToResult(verified)));
    }
}

internal sealed record NoteUpdateArguments(
    string NoteId,
    string ExpectedTitle,
    long ExpectedRevision,
    string Title,
    string Content);
