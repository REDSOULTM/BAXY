using System.Buffers;
using System.Globalization;
using System.Text;
using System.Text.Json;
using Baxy.Providers.Windows.Tasks;

namespace Baxy.Providers.Windows.Routines;

/// <summary>
/// Recovered routine lifecycle store. Creation remains a trusted-controller
/// boundary and execution is intentionally absent from this provider.
/// </summary>
public sealed class LocalRoutineStore : IRoutineStore
{
    private readonly ILocalTaskStore _store;

    public LocalRoutineStore(string rootDirectory)
        : this(new LocalTaskStore(rootDirectory))
    {
    }

    internal LocalRoutineStore(ILocalTaskStore store)
    {
        _store = store ?? throw new ArgumentNullException(nameof(store));
    }

    internal RoutineRecord CreateTrusted(
        string name,
        string workflowId,
        string workflowVersion,
        IReadOnlyList<string> inputFields,
        string triggerKind,
        string? appKey)
    {
        if (triggerKind is not ("manual" or "on_app_open" or "on_phrase")
            || (triggerKind == "on_app_open") != !string.IsNullOrWhiteSpace(appKey)
            || inputFields.Count > 64
            || inputFields.Any(string.IsNullOrWhiteSpace))
            throw new LocalTaskValidationException("Routine metadata is invalid.");
        string payload = Serialize(workflowId, workflowVersion, inputFields, triggerKind, appKey);
        return ToRoutine(_store.Create(name, payload, null));
    }

    public RoutineRecord CreatePhrase(
        string name,
        string phrase,
        string action = "media.control")
    {
        string normalizedName = RequiredText(name, 640);
        string normalizedPhrase = FoldPhrase(RequiredText(phrase, 640));
        if (normalizedPhrase.Length == 0)
            throw new LocalTaskValidationException("Routine phrase is invalid.");
        if (action is not ("media.control" or "capture.screenshot"))
            throw new LocalTaskValidationException("Routine action is invalid.");
        return CreateTrusted(
            normalizedName,
            action,
            "1",
            action == "media.control"
                ? ["action=toggle", "phrase=" + normalizedPhrase]
                : ["phrase=" + normalizedPhrase],
            "on_phrase",
            null);
    }

    public RoutineRecord Read(Guid id, bool includeDeleted) =>
        ToRoutine(_store.Read(id, includeDeleted));

    public IReadOnlyList<RoutineRecord> List(bool includeDeleted, int limit) =>
        _store.List(TaskListStatus.All, includeDeleted, limit).Select(ToRoutine).ToArray();

    public RoutineRecord ResolveExact(string name, bool includeDeleted) =>
        ToRoutine(_store.ResolveExact(name, includeDeleted));

    public RoutineRecord SetEnabled(Guid id, long expectedRevision, bool enabled) =>
        ToRoutine(_store.SetCompleted(id, expectedRevision, completed: !enabled));

    public RoutineRecord Delete(Guid id, long expectedRevision, string reviewLabel) =>
        ToRoutine(_store.Delete(id, expectedRevision, reviewLabel));

    public RoutineRecord Restore(Guid id, long expectedRevision) =>
        ToRoutine(_store.Restore(id, expectedRevision));

    private static string RequiredText(string value, int maximumUtf8Bytes)
    {
        if (string.IsNullOrWhiteSpace(value))
            throw new LocalTaskValidationException("Routine text is required.");
        string normalized = value.Trim().Normalize(NormalizationForm.FormC);
        if (Encoding.UTF8.GetByteCount(normalized) > maximumUtf8Bytes)
            throw new LocalTaskValidationException("Routine text is too long.");
        return normalized;
    }

    private static string FoldPhrase(string value)
    {
        string decomposed = value.Normalize(NormalizationForm.FormD);
        var builder = new StringBuilder(decomposed.Length);
        bool pendingSpace = false;
        foreach (char character in decomposed)
        {
            if (CharUnicodeInfo.GetUnicodeCategory(character) == UnicodeCategory.NonSpacingMark)
                continue;
            if (char.IsLetterOrDigit(character))
            {
                if (pendingSpace && builder.Length > 0) builder.Append(' ');
                builder.Append(char.ToLowerInvariant(character));
                pendingSpace = false;
            }
            else pendingSpace = true;
        }
        return builder.ToString();
    }

    private static RoutineRecord ToRoutine(LocalTaskRecord task)
    {
        try
        {
            using JsonDocument document = JsonDocument.Parse(task.Details);
            JsonElement root = document.RootElement;
            string[] fields = root.GetProperty("inputFields").EnumerateArray()
                .Select(static item => item.GetString()!).ToArray();
            return new RoutineRecord(
                task.Id,
                task.Title,
                root.GetProperty("workflowId").GetString()!,
                root.GetProperty("workflowVersion").GetString()!,
                fields,
                root.GetProperty("triggerKind").GetString()!,
                root.GetProperty("appKey").ValueKind == JsonValueKind.Null
                    ? null : root.GetProperty("appKey").GetString(),
                !task.Completed,
                task.Deleted,
                task.Version,
                task.CreatedAtUtc,
                task.UpdatedAtUtc);
        }
        catch (Exception exception) when (exception is JsonException or InvalidOperationException)
        {
            throw new LocalTaskStoreException("Authenticated routine metadata is invalid.", exception);
        }
    }

    private static string Serialize(
        string workflowId,
        string workflowVersion,
        IReadOnlyList<string> inputFields,
        string triggerKind,
        string? appKey)
    {
        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            writer.WriteString("workflowId", workflowId);
            writer.WriteString("workflowVersion", workflowVersion);
            writer.WritePropertyName("inputFields"); writer.WriteStartArray();
            foreach (string field in inputFields.Order(StringComparer.Ordinal)) writer.WriteStringValue(field);
            writer.WriteEndArray();
            writer.WriteString("triggerKind", triggerKind);
            if (appKey is null) writer.WriteNull("appKey"); else writer.WriteString("appKey", appKey);
            writer.WriteEndObject();
        }
        return System.Text.Encoding.UTF8.GetString(buffer.WrittenSpan);
    }
}
