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

public interface ILocalTaskStore
{
    LocalTaskRecord Create(string title, string details, string? due);

    LocalTaskRecord Read(Guid id, bool includeDeleted = false);

    LocalTaskRecord ResolveExact(string title, bool includeDeleted);

    IReadOnlyList<LocalTaskRecord> List(TaskListStatus status, bool includeDeleted, int limit);

    IReadOnlyList<LocalTaskRecord> Search(string query, TaskListStatus status, int limit);

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

public sealed class LocalTaskAmbiguousException(string message) : LocalTaskStoreException(message);

public sealed class LocalTaskVersionConflictException(Guid id)
    : LocalTaskStoreException($"Task '{id:D}' changed before the requested mutation.");
