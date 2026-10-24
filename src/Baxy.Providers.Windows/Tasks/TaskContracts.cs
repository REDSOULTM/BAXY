namespace Baxy.Providers.Windows.Tasks;

public enum TaskListStatus
{
    Open,
    Completed,
    All,
}

public sealed record LocalTaskRecord(
    Guid Id,
    string Title,
    string Details,
    DateTimeOffset? DueUtc,
    bool Completed,
    DateTimeOffset? CompletedAtUtc,
    bool Deleted,
    DateTimeOffset CreatedAtUtc,
    DateTimeOffset UpdatedAtUtc,
    long Version);

// Ronda final 7: the tasks listed (at most the limit) and how many match.
public sealed record LocalTaskQuery(IReadOnlyList<LocalTaskRecord> Tasks, int MatchCount);

public interface ILocalTaskStore
{
    /// <param name="idempotencyKey">The invocation that creates it (as note.create): the same key with the same task
    /// gives back the task it already created, never a second one; with another task it is a conflict.</param>
    LocalTaskRecord Create(string title, string details, string? due, string? idempotencyKey = null);

    LocalTaskRecord Read(Guid id, bool includeDeleted = false);

    LocalTaskQuery List(TaskListStatus status, bool includeDeleted, int limit);

    LocalTaskQuery Search(string query, TaskListStatus status, int limit);

    LocalTaskRecord Update(Guid id, long expectedVersion, string title, string details, string? due);

    LocalTaskRecord SetCompleted(Guid id, long expectedVersion, bool completed);

    LocalTaskRecord Delete(Guid id, long expectedVersion, string reviewLabel);

    LocalTaskRecord Restore(Guid id, long expectedVersion);
}

public class LocalTaskStoreException : Exception
{
    public LocalTaskStoreException(string message)
        : base(message)
    {
    }

    public LocalTaskStoreException(string message, Exception innerException)
        : base(message, innerException)
    {
    }
}

public sealed class LocalTaskValidationException(string message) : LocalTaskStoreException(message);

public sealed class LocalTaskNotFoundException(string message) : LocalTaskStoreException(message);

public sealed class LocalTaskVersionConflictException(Guid id)
    : LocalTaskStoreException($"Task '{id:D}' changed before the requested mutation.");
