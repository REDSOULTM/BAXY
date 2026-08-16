using System.Globalization;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Baxy.Providers.Windows.Notes;

namespace Baxy.Providers.Windows.Tasks;

/// <summary>
/// Adapts the recovered v2 task lifecycle to the current atomic, integrity-checked
/// local document store. Tasks use a separate root and are never Windows Scheduled Tasks.
/// </summary>
public sealed class LocalTaskStore : ILocalTaskStore
{
    private const int MaximumTitleUtf8Bytes = 1_024;
    private const int MaximumDetailsUtf8Bytes = 65_536;
    private const int MaximumQueryUtf8Bytes = 2_000;
    private const int MaximumResultItems = 50;
    private readonly INoteStore _documents;
    private readonly TimeProvider _timeProvider;

    public LocalTaskStore(string rootDirectory, TimeProvider? timeProvider = null)
        : this(new LocalNoteStore(rootDirectory, timeProvider), timeProvider)
    {
    }

    internal LocalTaskStore(INoteStore documents, TimeProvider? timeProvider = null)
    {
        _documents = documents ?? throw new ArgumentNullException(nameof(documents));
        _timeProvider = timeProvider ?? TimeProvider.System;
    }

    public LocalTaskRecord Create(string title, string details, string? due)
    {
        string normalizedTitle = NormalizeText(title, nameof(title), MaximumTitleUtf8Bytes, false, false);
        string normalizedDetails = NormalizeText(details, nameof(details), MaximumDetailsUtf8Bytes, true, true);
        DateTimeOffset? dueUtc = ParseDue(due);
        var payload = new TaskPayload(normalizedDetails, dueUtc, false, null);
        return ToTask(_documents.Create(normalizedTitle, Serialize(payload)));
    }

    public LocalTaskRecord Read(Guid id, bool includeDeleted = false) =>
        ToTask(ReadDocument(id, includeDeleted));

    public LocalTaskRecord ResolveExact(string title, bool includeDeleted)
    {
        string normalized = NormalizeText(title, nameof(title), MaximumTitleUtf8Bytes, false, false);
        LocalTaskRecord[] matches = _documents.List(includeDeleted ? NoteListScope.All : NoteListScope.Active)
            .Where(note => string.Equals(note.Title, normalized, StringComparison.OrdinalIgnoreCase))
            .Select(ToTask)
            .ToArray();
        return matches.Length switch
        {
            1 => matches[0],
            0 => throw new LocalTaskNotFoundException("No task has that exact title."),
            _ => throw new LocalTaskAmbiguousException("More than one task has that exact title."),
        };
    }

    public IReadOnlyList<LocalTaskRecord> List(
        TaskListStatus status,
        bool includeDeleted,
        int limit)
    {
        ValidateList(status, limit);
        return _documents.List(includeDeleted ? NoteListScope.All : NoteListScope.Active)
            .Select(ToTask)
            .Where(task => MatchesStatus(task, status))
            .OrderByDescending(static task => task.UpdatedAtUtc)
            .ThenBy(static task => task.Id)
            .Take(limit)
            .ToArray();
    }

    public IReadOnlyList<LocalTaskRecord> Search(string query, TaskListStatus status, int limit)
    {
        string normalized = NormalizeText(query, nameof(query), MaximumQueryUtf8Bytes, false, false);
        ValidateList(status, limit);
        return _documents.List(NoteListScope.Active)
            .Select(ToTask)
            .Where(task => MatchesStatus(task, status)
                && (task.Title.Contains(normalized, StringComparison.OrdinalIgnoreCase)
                    || task.Details.Contains(normalized, StringComparison.OrdinalIgnoreCase)))
            .OrderByDescending(static task => task.UpdatedAtUtc)
            .ThenBy(static task => task.Id)
            .Take(limit)
            .ToArray();
    }

    public LocalTaskRecord Update(
        Guid id,
        long expectedVersion,
        string title,
        string details,
        string? due)
    {
        NoteRecord current = ReadExpected(id, expectedVersion, includeDeleted: false);
        string normalizedTitle = NormalizeText(title, nameof(title), MaximumTitleUtf8Bytes, false, false);
        string normalizedDetails = NormalizeText(details, nameof(details), MaximumDetailsUtf8Bytes, true, true);
        TaskPayload payload = Open(current) with
        {
            Details = normalizedDetails,
            DueUtc = ParseDue(due),
        };
        return ToTask(_documents.UpdateSelected(Select(current), normalizedTitle, Serialize(payload)));
    }

    public LocalTaskRecord SetCompleted(Guid id, long expectedVersion, bool completed)
    {
        NoteRecord current = ReadExpected(id, expectedVersion, includeDeleted: false);
        TaskPayload payload = Open(current);
        if (payload.Completed == completed) return ToTask(current);
        payload = payload with
        {
            Completed = completed,
            CompletedAtUtc = completed ? GetUtcNow() : null,
        };
        return ToTask(_documents.UpdateSelected(Select(current), current.Title, Serialize(payload)));
    }

    public LocalTaskRecord Delete(Guid id, long expectedVersion, string reviewLabel)
    {
        NoteRecord current = ReadExpected(id, expectedVersion, includeDeleted: true);
        string normalizedLabel = NormalizeText(
            reviewLabel, nameof(reviewLabel), MaximumTitleUtf8Bytes, false, false);
        if (!string.Equals(current.Title, normalizedLabel, StringComparison.Ordinal))
        {
            throw new LocalTaskVersionConflictException(id);
        }

        if (current.IsTrashed) return ToTask(current);
        return ToTask(_documents.TrashSelected(Select(current)));
    }

    public LocalTaskRecord Restore(Guid id, long expectedVersion)
    {
        NoteRecord current = ReadExpected(id, expectedVersion, includeDeleted: true);
        if (!current.IsTrashed) return ToTask(current);
        return ToTask(_documents.RestoreSelected(Select(current)));
    }

    private NoteRecord ReadExpected(Guid id, long expectedVersion, bool includeDeleted)
    {
        if (id == Guid.Empty || expectedVersion < 1)
        {
            throw new LocalTaskValidationException("Task identity or version is invalid.");
        }

        NoteRecord current = ReadDocument(id, includeDeleted);
        if (current.Revision != expectedVersion)
        {
            throw new LocalTaskVersionConflictException(id);
        }

        return current;
    }

    private NoteRecord ReadDocument(Guid id, bool includeDeleted)
    {
        try
        {
            return _documents.Read(id, includeDeleted);
        }
        catch (NoteNotFoundException exception)
        {
            throw new LocalTaskNotFoundException("Task was not found.") { Source = exception.Source };
        }
    }

    private LocalTaskRecord ToTask(NoteRecord document)
    {
        TaskPayload payload = Open(document);
        return new LocalTaskRecord(
            document.Id,
            document.Title,
            payload.Details,
            payload.DueUtc,
            payload.Completed,
            payload.CompletedAtUtc,
            document.IsTrashed,
            document.CreatedAtUtc,
            document.UpdatedAtUtc,
            document.Revision);
    }

    private static TaskPayload Open(NoteRecord document)
    {
        try
        {
            TaskPayload? payload = JsonSerializer.Deserialize(
                document.Content,
                TaskStoreJsonContext.Default.TaskPayload);
            if (payload is null
                || payload.Completed != payload.CompletedAtUtc.HasValue
                || Encoding.UTF8.GetByteCount(payload.Details) > MaximumDetailsUtf8Bytes)
            {
                throw new JsonException();
            }

            return payload;
        }
        catch (JsonException exception)
        {
            throw new LocalTaskStoreException("Authenticated task payload is invalid.", exception);
        }
    }

    private static string Serialize(TaskPayload payload) =>
        JsonSerializer.Serialize(payload, TaskStoreJsonContext.Default.TaskPayload);

    private static NoteSelection Select(NoteRecord record) =>
        new(record.Id, record.Title, record.Revision, record.IsTrashed);

    private static bool MatchesStatus(LocalTaskRecord task, TaskListStatus status) => status switch
    {
        TaskListStatus.Open => !task.Completed,
        TaskListStatus.Completed => task.Completed,
        TaskListStatus.All => true,
        _ => false,
    };

    private static void ValidateList(TaskListStatus status, int limit)
    {
        if (!Enum.IsDefined(status) || limit is < 1 or > MaximumResultItems)
        {
            throw new LocalTaskValidationException("Task list filter is invalid.");
        }
    }

    private static string NormalizeText(
        string value,
        string field,
        int maximumUtf8Bytes,
        bool multiline,
        bool allowEmpty)
    {
        if (value is null) throw new LocalTaskValidationException($"{field} is required.");
        string normalized = value.Normalize(NormalizationForm.FormC);
        if (!multiline) normalized = normalized.Trim();
        bool invalidControl = normalized.Any(character => char.IsControl(character)
            && !(multiline && character is '\r' or '\n' or '\t'));
        if ((!allowEmpty && string.IsNullOrWhiteSpace(normalized))
            || invalidControl
            || Encoding.UTF8.GetByteCount(normalized) > maximumUtf8Bytes)
        {
            throw new LocalTaskValidationException($"{field} is invalid.");
        }

        return normalized;
    }

    private static DateTimeOffset? ParseDue(string? due)
    {
        if (due is null) return null;
        if (!DateTimeOffset.TryParse(
                due,
                CultureInfo.InvariantCulture,
                DateTimeStyles.AllowWhiteSpaces | DateTimeStyles.AssumeUniversal,
                out DateTimeOffset parsed))
        {
            throw new LocalTaskValidationException("due must be an ISO date-time with offset.");
        }

        return parsed.ToUniversalTime();
    }

    private DateTimeOffset GetUtcNow() => _timeProvider.GetUtcNow().ToUniversalTime();

    internal sealed record TaskPayload(
        string Details,
        DateTimeOffset? DueUtc,
        bool Completed,
        DateTimeOffset? CompletedAtUtc);
}

[JsonSourceGenerationOptions(
    PropertyNamingPolicy = JsonKnownNamingPolicy.CamelCase,
    PropertyNameCaseInsensitive = false,
    UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow)]
[JsonSerializable(typeof(LocalTaskStore.TaskPayload))]
internal sealed partial class TaskStoreJsonContext : JsonSerializerContext;
