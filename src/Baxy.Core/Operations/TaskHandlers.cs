using System.Text.Json;
using Baxy.Kernel.Operations;
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
        new ResolveExactTaskHandler(store),
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
            return ValueTask.FromResult(OperationOutcome.Failure("invalid_arguments"));
        }
        catch (LocalTaskValidationException)
        {
            return ValueTask.FromResult(OperationOutcome.Failure("invalid_task"));
        }
        catch (Exception exception) when (exception is LocalTaskNotFoundException or NoteNotFoundException)
        {
            return ValueTask.FromResult(OperationOutcome.Failure("task_not_found"));
        }
        catch (LocalTaskAmbiguousException)
        {
            return ValueTask.FromResult(OperationOutcome.Failure("task_ambiguous"));
        }
        catch (Exception exception)
            when (exception is LocalTaskVersionConflictException or NoteSelectionStaleException)
        {
            return ValueTask.FromResult(OperationOutcome.Failure("task_version_conflict"));
        }
        catch (NoteValidationException)
        {
            return ValueTask.FromResult(OperationOutcome.Failure("invalid_task"));
        }
        catch (Exception exception)
            when (Definition.Risk == OperationRisk.ReadOnly
                && (exception is LocalTaskStoreException or NoteCorruptionException))
        {
            return ValueTask.FromResult(OperationOutcome.Failure("task_integrity_failed"));
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

    protected OperationOutcome VerifiedMutation(LocalTaskRecord changed)
    {
        LocalTaskRecord verified = Store.Read(changed.Id, includeDeleted: true);
        if (verified != changed) return OperationOutcome.Failure("verification_failed");
        return OperationOutcome.Success(Serialize(ToResult(verified)));
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
        return VerifiedMutation(Store.Create(arguments.Title, arguments.Details ?? string.Empty, arguments.Due));
    }
}

internal sealed class CompleteTaskHandler(ILocalTaskStore store) : TaskHandlerBase(store)
{
    public override OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition("task.complete");

    protected override OperationOutcome Execute(OperationInvocation invocation)
    {
        TaskCasArguments arguments = Parse(invocation.Arguments, CoreJsonContext.Default.TaskCasArguments);
        return VerifiedMutation(Store.SetCompleted(ParseId(arguments.TaskId), arguments.ExpectedVersion, true));
    }
}

internal sealed class ReopenTaskHandler(ILocalTaskStore store) : TaskHandlerBase(store)
{
    public override OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition("task.reopen");

    protected override OperationOutcome Execute(OperationInvocation invocation)
    {
        TaskCasArguments arguments = Parse(invocation.Arguments, CoreJsonContext.Default.TaskCasArguments);
        return VerifiedMutation(Store.SetCompleted(ParseId(arguments.TaskId), arguments.ExpectedVersion, false));
    }
}

internal sealed class DeleteTaskHandler(ILocalTaskStore store) : TaskHandlerBase(store)
{
    public override OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition("task.delete");

    protected override OperationOutcome Execute(OperationInvocation invocation)
    {
        TaskDeleteArguments arguments = Parse(invocation.Arguments, CoreJsonContext.Default.TaskDeleteArguments);
        return VerifiedMutation(Store.Delete(
            ParseId(arguments.TaskId),
            arguments.ExpectedVersion,
            arguments.ReviewLabel));
    }
}

internal sealed class RestoreTaskHandler(ILocalTaskStore store) : TaskHandlerBase(store)
{
    public override OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition("task.restore");

    protected override OperationOutcome Execute(OperationInvocation invocation)
    {
        TaskCasArguments arguments = Parse(invocation.Arguments, CoreJsonContext.Default.TaskCasArguments);
        return VerifiedMutation(Store.Restore(ParseId(arguments.TaskId), arguments.ExpectedVersion));
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
            arguments.Due));
    }
}

internal sealed class ResolveExactTaskHandler(ILocalTaskStore store) : TaskHandlerBase(store)
{
    public override OperationDefinition Definition { get; } =
        ProductCatalog.CreateDefinition("task.resolve.exact");

    protected override OperationOutcome Execute(OperationInvocation invocation)
    {
        TaskResolveExactArguments arguments = Parse(
            invocation.Arguments,
            CoreJsonContext.Default.TaskResolveExactArguments);
        LocalTaskRecord found = Store.ResolveExact(arguments.Title, arguments.IncludeDeleted ?? false);
        LocalTaskRecord verified = Store.Read(found.Id, includeDeleted: true);
        if (verified != found) return OperationOutcome.Failure("verification_failed");
        var result = new TaskSelectionResult(
            found.Id.ToString("D"),
            found.Version,
            found.Title,
            found.Deleted,
            found.Completed ? "completed" : "open");
        return OperationOutcome.Success(JsonSerializer.SerializeToElement(
            result,
            CoreJsonContext.Default.TaskSelectionResult));
    }
}

internal sealed class ListTasksHandler(ILocalTaskStore store) : TaskHandlerBase(store)
{
    public override OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition("task.list");

    protected override OperationOutcome Execute(OperationInvocation invocation)
    {
        TaskListArguments arguments = Parse(invocation.Arguments, CoreJsonContext.Default.TaskListArguments);
        int limit = arguments.Limit ?? 20;
        IReadOnlyList<LocalTaskRecord> found = Store.List(
            ParseStatus(arguments.Status, TaskListStatus.Open),
            arguments.IncludeDeleted ?? false,
            limit);
        return VerifiedList(found, "tasks", limit);
    }

    private OperationOutcome VerifiedList(IReadOnlyList<LocalTaskRecord> found, string mode, int limit)
    {
        foreach (LocalTaskRecord task in found)
        {
            if (Store.Read(task.Id, includeDeleted: true) != task)
            {
                return OperationOutcome.Failure("verification_failed");
            }
        }

        var result = new TaskListResult(found.Select(ToSummary).ToArray(), found.Count, mode, limit);
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
        IReadOnlyList<LocalTaskRecord> found = Store.Search(
            arguments.Query,
            ParseStatus(arguments.Status, TaskListStatus.All),
            limit);
        foreach (LocalTaskRecord task in found)
        {
            if (Store.Read(task.Id) != task) return OperationOutcome.Failure("verification_failed");
        }

        var result = new TaskListResult(found.Select(ToSummary).ToArray(), found.Count, "search", limit);
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

internal sealed record TaskResolveExactArguments(string Title, bool? IncludeDeleted);

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

internal sealed record TaskSelectionResult(
    string TaskId,
    long ExpectedVersion,
    string ReviewLabel,
    bool Deleted,
    string Status);

internal sealed record TaskListResult(
    TaskSummaryResult[] Tasks,
    int Count,
    string Mode,
    int Limit);
