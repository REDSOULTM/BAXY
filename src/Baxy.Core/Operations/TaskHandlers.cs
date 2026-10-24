using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Infrastructure;
using Baxy.Providers.Windows.Notes;
using Baxy.Providers.Windows.Tasks;

namespace Baxy.Core.Operations;

internal static class TaskHandlers
{
    public static IOperationHandler[] Create(ILocalTaskStore store) =>
    [
        new CompleteTaskHandler(store),
        new CreateTaskHandler(store),
        new DeleteTaskHandler(store),
        new ListTasksHandler(store),
        new ReopenTaskHandler(store),
        new RestoreTaskHandler(store),
        new SearchTasksHandler(store),
        new UpdateTaskHandler(store),
    ];
}

internal abstract class TaskHandlerBase(ILocalTaskStore store) : IOperationHandler
{
    protected ILocalTaskStore Store { get; } = store ?? throw new ArgumentNullException(nameof(store));

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
            return ValueTask.FromResult(OperationOutcome.InvalidArguments(Definition, invocation.Arguments));
        }
        // Renew al máximo (w8): «invalid_task» came bare; it says which field and why (the store's own words, which
        // name a field and never carry its value), and that nothing was written.
        catch (LocalTaskValidationException exception)
        {
            return ValueTask.FromResult(OperationOutcome.Failure("invalid_task", Problem(exception.Message)));
        }
        catch (Exception exception) when (exception is LocalTaskNotFoundException or NoteNotFoundException)
        {
            return ValueTask.FromResult(OperationOutcome.Failure(
                "task_not_found", StateFacts(invocation.Arguments, conflict: false)));
        }
        catch (Exception exception)
            when (exception is LocalTaskVersionConflictException or NoteSelectionStaleException)
        {
            return ValueTask.FromResult(OperationOutcome.Failure(
                "task_version_conflict", StateFacts(invocation.Arguments, conflict: true)));
        }
        // Auditoría del Core (w8): the invocation's key already made another task (note.create says the same).
        catch (NoteConflictException)
        {
            return ValueTask.FromResult(OperationOutcome.Failure("idempotency_conflict"));
        }
        catch (NoteValidationException)
        {
            return ValueTask.FromResult(OperationOutcome.Failure("invalid_task"));
        }
        // Revisión 2026-10-22 (C-1): a full store threw past this handler and ended the core (exit 70); it refuses
        // before writing anything.
        catch (NoteCapacityException)
        {
            return ValueTask.FromResult(OperationOutcome.Failure("task_capacity_reached"));
        }
        // Auditoría del Core (w8): a task whose stored payload does not read back (LocalTaskStoreException), a corrupt
        // document or a store whose path became unsafe, met by task.complete, task.update or any other change, threw
        // past this handler and ended the core (exit 70); the unsafe store did so even for a read. It is this
        // operation's failure, named; a change may have begun only for an operation that changes something.
        catch (Exception exception) when (exception is LocalTaskStoreException or NoteCorruptionException)
        {
            return ValueTask.FromResult(OperationOutcome.Failure(
                "task_integrity_failed", effectMayHaveOccurred: Definition.Risk != OperationRisk.ReadOnly));
        }
        catch (UnsafeNoteStorePathException)
        {
            return ValueTask.FromResult(OperationOutcome.Failure(
                "unsafe_storage", effectMayHaveOccurred: Definition.Risk != OperationRisk.ReadOnly));
        }
        // Revisión 2026-10-22 (C-1): a disk or a guarded folder that fails a write ended the core too; it is this
        // operation's failure, named, and a change may have begun only for an operation that changes something
        // (FilesystemHandlers does the same).
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            return ValueTask.FromResult(OperationOutcome.Failure(
                "storage_failed", effectMayHaveOccurred: Definition.Risk != OperationRisk.ReadOnly));
        }
    }

    protected abstract OperationOutcome Execute(OperationInvocation invocation);

    private static JsonElement Problem(string problem)
    {
        var facts = new JsonObject { ["problem"] = problem };
        if (ModelAids.On(ModelAids.TaskStateNext))
        {
            facts["next"] = "nothing was written: " + problem;
        }

        using JsonDocument document = JsonDocument.Parse(facts.ToJsonString());
        return document.RootElement.Clone();
    }

    // Renew al máximo (w5): «task_not_found» and «task_version_conflict» came bare, and a task.complete retried after it
    // was done (its version moved) read as a failure. Both say what the store holds under that taskId now, deleted
    // ones included, and nothing was changed (both refuse before any write); aid task_state_next says it as a sentence.
    protected JsonElement? StateFacts(JsonElement arguments, bool conflict)
    {
        if (arguments.ValueKind != JsonValueKind.Object
            || !arguments.TryGetProperty("taskId", out JsonElement given)
            || given.ValueKind != JsonValueKind.String
            || !Guid.TryParseExact(given.GetString(), "D", out Guid id)
            || id == Guid.Empty)
        {
            return null;
        }

        LocalTaskRecord? current;
        try
        {
            current = Store.Read(id, includeDeleted: true);
        }
        catch (LocalTaskNotFoundException)
        {
            current = null;
        }
        catch (Exception exception) when (exception is LocalTaskStoreException or NoteStoreException or IOException
            or UnauthorizedAccessException)
        {
            return null;
        }

        var facts = new JsonObject { ["taskId"] = id.ToString("D") };
        string next;
        if (current is null)
        {
            facts["searched"] = "active and deleted tasks";
            next = "nothing was changed: no task has this taskId, deleted ones included; task.search or task.list gives the ids";
        }
        else
        {
            facts["current"] = JsonSerializer.SerializeToNode(ToSummary(current), CoreJsonContext.Default.TaskSummaryResult);
            string label = arguments.TryGetProperty("reviewLabel", out JsonElement review)
                && review.ValueKind == JsonValueKind.String
                    ? review.GetString()!.Normalize(System.Text.NormalizationForm.FormC).Trim()
                    : current.Title;
            string state = (current.Completed ? "completed" : "open") + (current.Deleted ? ", deleted" : string.Empty);
            next = !conflict
                ? $"nothing was changed: the task is deleted; task.restore with version {current.Version} brings it back first"
                : !string.Equals(label, current.Title, StringComparison.Ordinal)
                    ? $"nothing was changed: reviewLabel must be the task's exact title, \"{current.Title}\""
                    : $"nothing was changed: the task is {state} at version {current.Version} now";
        }

        if (ModelAids.On(ModelAids.TaskStateNext))
        {
            facts["next"] = next;
        }

        using JsonDocument document = JsonDocument.Parse(facts.ToJsonString());
        return document.RootElement.Clone();
    }

    protected static T Parse<T>(
        JsonElement arguments,
        System.Text.Json.Serialization.Metadata.JsonTypeInfo<T> typeInfo)
        where T : class =>
        JsonSerializer.Deserialize(arguments, typeInfo)
        ?? throw new JsonException("Arguments cannot be null.");

    protected static Guid ParseId(string value)
    {
        if (!Guid.TryParseExact(value, "D", out Guid id) || id == Guid.Empty)
        {
            throw new LocalTaskValidationException("taskId must be a canonical UUID.");
        }

        return id;
    }

    protected static TaskListStatus ParseStatus(string? status, TaskListStatus fallback) => status switch
    {
        null => fallback,
        "open" => TaskListStatus.Open,
        "completed" => TaskListStatus.Completed,
        "all" => TaskListStatus.All,
        _ => throw new JsonException("Unknown task status."),
    };

    protected OperationOutcome VerifiedMutation(LocalTaskRecord changed, long? expectedVersion = null)
    {
        LocalTaskRecord verified;
        try
        {
            verified = Store.Read(changed.Id, includeDeleted: true);
        }
        catch (LocalTaskNotFoundException)
        {
            return OperationOutcome.Failure(
                "verification_failed",
                effectMayHaveOccurred: true);
        }

        if (verified != changed)
        {
            return OperationOutcome.Failure(
                "verification_failed",
                effectMayHaveOccurred: true);
        }

        JsonElement result = Serialize(ToResult(verified));
        // Ronda final: a task already in the state asked (completed, open, deleted, restored) keeps its version: the
        // state reached, changed:false, never a change this call made.
        if (expectedVersion is { } version && verified.Version == version)
        {
            var unchanged = (System.Text.Json.Nodes.JsonObject)System.Text.Json.Nodes.JsonNode.Parse(result.GetRawText())!;
            unchanged["changed"] = false;
            using JsonDocument document = JsonDocument.Parse(unchanged.ToJsonString());
            result = document.RootElement.Clone();
        }

        return OperationOutcome.Success(result);
    }

    protected static TaskResult ToResult(LocalTaskRecord task) => new(
        task.Id.ToString("D"),
        task.Title,
        task.Details,
        task.DueUtc,
        task.Completed,
        task.CompletedAtUtc,
        task.Deleted,
        task.CreatedAtUtc,
        task.UpdatedAtUtc,
        task.Version);

    protected static TaskSummaryResult ToSummary(LocalTaskRecord task) => new(
        task.Id.ToString("D"),
        task.Title,
        task.DueUtc,
        task.Completed,
        task.Deleted,
        task.UpdatedAtUtc,
        task.Version);

    protected static JsonElement Serialize(TaskResult result) =>
        JsonSerializer.SerializeToElement(result, CoreJsonContext.Default.TaskResult);
}

internal sealed class CreateTaskHandler(ILocalTaskStore store) : TaskHandlerBase(store)
{
    public override OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition("task.create");

    protected override OperationOutcome Execute(OperationInvocation invocation)
    {
        TaskCreateArguments arguments = Parse(invocation.Arguments, CoreJsonContext.Default.TaskCreateArguments);
        return VerifiedMutation(Store.Create(
            arguments.Title, arguments.Details ?? string.Empty, arguments.Due, invocation.InvocationId));
    }
}

internal sealed class CompleteTaskHandler(ILocalTaskStore store) : TaskHandlerBase(store)
{
    public override OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition("task.complete");

    protected override OperationOutcome Execute(OperationInvocation invocation)
    {
        TaskCasArguments arguments = Parse(invocation.Arguments, CoreJsonContext.Default.TaskCasArguments);
        return VerifiedMutation(Store.SetCompleted(ParseId(arguments.TaskId), arguments.ExpectedVersion, true),
            arguments.ExpectedVersion);
    }
}

internal sealed class ReopenTaskHandler(ILocalTaskStore store) : TaskHandlerBase(store)
{
    public override OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition("task.reopen");

    protected override OperationOutcome Execute(OperationInvocation invocation)
    {
        TaskCasArguments arguments = Parse(invocation.Arguments, CoreJsonContext.Default.TaskCasArguments);
        return VerifiedMutation(Store.SetCompleted(ParseId(arguments.TaskId), arguments.ExpectedVersion, false),
            arguments.ExpectedVersion);
    }
}

internal sealed class DeleteTaskHandler(ILocalTaskStore store) : TaskHandlerBase(store), IInvocationPreflight
{
    public override OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition("task.delete");

    // Renew al máximo (w5): a task.delete asks the person's yes, and one whose task is not there, or not at that version
    // and title, failed only after the yes. It is read first (no effect) and that failure answers without asking.
    public ValueTask<InvocationPreflightResult> PreflightAsync(JsonElement arguments, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        try
        {
            TaskDeleteArguments parsed = Parse(arguments, CoreJsonContext.Default.TaskDeleteArguments);
            Guid id = ParseId(parsed.TaskId);
            LocalTaskRecord current;
            try
            {
                current = Store.Read(id, includeDeleted: true);
            }
            catch (LocalTaskNotFoundException)
            {
                return ValueTask.FromResult(InvocationPreflightResult.Fails(
                    OperationOutcome.Failure("task_not_found", StateFacts(arguments, conflict: false))));
            }

            string label = parsed.ReviewLabel.Normalize(System.Text.NormalizationForm.FormC).Trim();
            return ValueTask.FromResult(current.Version != parsed.ExpectedVersion
                || !string.Equals(current.Title, label, StringComparison.Ordinal)
                    ? InvocationPreflightResult.Fails(
                        OperationOutcome.Failure("task_version_conflict", StateFacts(arguments, conflict: true)))
                    : InvocationPreflightResult.Proceed);
        }
        catch (Exception exception) when (exception is JsonException or LocalTaskStoreException or NoteStoreException
            or IOException or UnauthorizedAccessException)
        {
            return ValueTask.FromResult(InvocationPreflightResult.Proceed);
        }
    }

    protected override OperationOutcome Execute(OperationInvocation invocation)
    {
        TaskDeleteArguments arguments = Parse(invocation.Arguments, CoreJsonContext.Default.TaskDeleteArguments);
        return VerifiedMutation(Store.Delete(
            ParseId(arguments.TaskId),
            arguments.ExpectedVersion,
            arguments.ReviewLabel), arguments.ExpectedVersion);
    }
}

internal sealed class RestoreTaskHandler(ILocalTaskStore store) : TaskHandlerBase(store)
{
    public override OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition("task.restore");

    protected override OperationOutcome Execute(OperationInvocation invocation)
    {
        TaskCasArguments arguments = Parse(invocation.Arguments, CoreJsonContext.Default.TaskCasArguments);
        return VerifiedMutation(Store.Restore(ParseId(arguments.TaskId), arguments.ExpectedVersion), arguments.ExpectedVersion);
    }
}

internal sealed class UpdateTaskHandler(ILocalTaskStore store) : TaskHandlerBase(store)
{
    public override OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition("task.update");

    protected override OperationOutcome Execute(OperationInvocation invocation)
    {
        TaskUpdateArguments arguments = Parse(invocation.Arguments, CoreJsonContext.Default.TaskUpdateArguments);
        return VerifiedMutation(Store.Update(
            ParseId(arguments.TaskId),
            arguments.ExpectedVersion,
            arguments.Title,
            arguments.Details,
            arguments.Due), arguments.ExpectedVersion);
    }
}

internal sealed class ListTasksHandler(ILocalTaskStore store) : TaskHandlerBase(store)
{
    public override OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition("task.list");

    protected override OperationOutcome Execute(OperationInvocation invocation)
    {
        TaskListArguments arguments = Parse(invocation.Arguments, CoreJsonContext.Default.TaskListArguments);
        int limit = arguments.Limit ?? 20;
        LocalTaskQuery found = Store.List(
            ParseStatus(arguments.Status, TaskListStatus.Open),
            arguments.IncludeDeleted ?? false,
            limit);
        return VerifiedList(found, "tasks", limit);
    }

    private OperationOutcome VerifiedList(LocalTaskQuery found, string mode, int limit)
    {
        foreach (LocalTaskRecord task in found.Tasks)
        {
            if (Store.Read(task.Id, includeDeleted: true) != task)
            {
                return OperationOutcome.Failure("verification_failed");
            }
        }

        var result = new TaskListResult(
            found.Tasks.Select(ToSummary).ToArray(), found.Tasks.Count, found.MatchCount, mode, limit);
        return OperationOutcome.Success(JsonSerializer.SerializeToElement(
            result,
            CoreJsonContext.Default.TaskListResult));
    }
}

internal sealed class SearchTasksHandler(ILocalTaskStore store) : TaskHandlerBase(store)
{
    public override OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition("task.search");

    protected override OperationOutcome Execute(OperationInvocation invocation)
    {
        TaskSearchArguments arguments = Parse(invocation.Arguments, CoreJsonContext.Default.TaskSearchArguments);
        int limit = arguments.Limit ?? 20;
        LocalTaskQuery found = Store.Search(
            arguments.Query,
            ParseStatus(arguments.Status, TaskListStatus.All),
            limit);
        foreach (LocalTaskRecord task in found.Tasks)
        {
            if (Store.Read(task.Id) != task) return OperationOutcome.Failure("verification_failed");
        }

        var result = new TaskListResult(
            found.Tasks.Select(ToSummary).ToArray(), found.Tasks.Count, found.MatchCount, "search", limit);
        return OperationOutcome.Success(JsonSerializer.SerializeToElement(
            result,
            CoreJsonContext.Default.TaskListResult));
    }
}

internal sealed record TaskCreateArguments(string Title, string? Details, string? Due);

internal sealed record TaskCasArguments(string TaskId, long ExpectedVersion);

internal sealed record TaskDeleteArguments(string TaskId, long ExpectedVersion, string ReviewLabel);

internal sealed record TaskUpdateArguments(
    string TaskId,
    long ExpectedVersion,
    string Title,
    string Details,
    string? Due);

internal sealed record TaskListArguments(string? Status, bool? IncludeDeleted, int? Limit);

internal sealed record TaskSearchArguments(string Query, string? Status, int? Limit);

internal sealed record TaskResult(
    string TaskId,
    string Title,
    string Details,
    DateTimeOffset? DueUtc,
    bool Completed,
    DateTimeOffset? CompletedAtUtc,
    bool Deleted,
    DateTimeOffset CreatedAtUtc,
    DateTimeOffset UpdatedAtUtc,
    long Version);

internal sealed record TaskSummaryResult(
    string TaskId,
    string Title,
    DateTimeOffset? DueUtc,
    bool Completed,
    bool Deleted,
    DateTimeOffset UpdatedAtUtc,
    long Version);

internal sealed record TaskListResult(
    TaskSummaryResult[] Tasks,
    int Count,
    // Ronda final 7 (regla 3): how many match; more than Count means the limit cut the list.
    int TotalCount,
    string Mode,
    int Limit);
