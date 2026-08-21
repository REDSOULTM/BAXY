using System.Buffers;
using System.Globalization;
using System.Text.Json;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Tasks;

namespace Baxy.Core.Operations;

internal static class ReminderHandlers
{
    public static IOperationHandler[] Create(ILocalTaskStore store, TimeProvider? time = null) =>
    [
        new ReminderHandler("notification.dismiss", store, time ?? TimeProvider.System),
        new ReminderHandler("notification.list.due", store, time ?? TimeProvider.System),
        new ReminderHandler("reminder.create", store, time ?? TimeProvider.System),
        new ReminderHandler("reminder.delete", store, time ?? TimeProvider.System),
        new ReminderHandler("reminder.list", store, time ?? TimeProvider.System),
        new ReminderHandler("reminder.resolve.exact", store, time ?? TimeProvider.System),
        new ReminderHandler("reminder.restore", store, time ?? TimeProvider.System),
    ];
}

internal sealed class ReminderHandler(
    string operation,
    ILocalTaskStore store,
    TimeProvider time) : IOperationHandler
{
    private readonly ILocalTaskStore _store = store ?? throw new ArgumentNullException(nameof(store));
    private readonly TimeProvider _time = time ?? throw new ArgumentNullException(nameof(time));

    public OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition(operation);

    public ValueTask<OperationOutcome> ExecuteAsync(
        OperationInvocation invocation,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        try
        {
            JsonElement arguments = invocation.Arguments;
            OperationOutcome outcome = operation switch
            {
                "reminder.create" => Create(arguments),
                "reminder.list" => OperationOutcome.Success(List(arguments, dueOnly: false)),
                "notification.list.due" => OperationOutcome.Success(List(arguments, dueOnly: true)),
                "reminder.resolve.exact" => OperationOutcome.Success(ReminderResultJson.Selection(
                    Verify(_store.ResolveExact(
                        Required(arguments, "title"),
                        OptionalBoolean(arguments, "includeDeleted") ?? false)))),
                "reminder.delete" => VerifiedRecord(_store.Delete(
                    Id(arguments),
                    arguments.GetProperty("expectedVersion").GetInt64(),
                    Required(arguments, "reviewLabel"))),
                "reminder.restore" => VerifiedRecord(_store.Restore(
                    Id(arguments), arguments.GetProperty("expectedVersion").GetInt64())),
                "notification.dismiss" => VerifiedRecord(_store.SetCompleted(
                    Id(arguments), arguments.GetProperty("expectedVersion").GetInt64(), true)),
                _ => throw new InvalidOperationException("Unknown reminder operation."),
            };
            return ValueTask.FromResult(outcome);
        }
        catch (JsonException)
        {
            return ValueTask.FromResult(OperationOutcome.Failure("invalid_arguments"));
        }
        catch (LocalTaskValidationException)
        {
            return ValueTask.FromResult(OperationOutcome.Failure("invalid_reminder"));
        }
        catch (LocalTaskStoreException exception) when (exception is not LocalTaskNotFoundException
            and not LocalTaskAmbiguousException
            and not LocalTaskVersionConflictException)
        {
            return ValueTask.FromResult(OperationOutcome.Failure(
                "verification_failed",
                effectMayHaveOccurred: Definition.Risk != OperationRisk.ReadOnly));
        }
        catch (LocalTaskNotFoundException)
        {
            return ValueTask.FromResult(OperationOutcome.Failure("reminder_not_found"));
        }
        catch (LocalTaskAmbiguousException)
        {
            return ValueTask.FromResult(OperationOutcome.Failure("reminder_ambiguous"));
        }
        catch (LocalTaskVersionConflictException)
        {
            return ValueTask.FromResult(OperationOutcome.Failure("reminder_version_conflict"));
        }
    }

    private OperationOutcome Create(JsonElement arguments)
    {
        string due = Required(arguments, "dueUtc");
        if (!DateTimeOffset.TryParse(due, CultureInfo.InvariantCulture,
                DateTimeStyles.AssumeUniversal, out DateTimeOffset parsed)
            || parsed.ToUniversalTime() <= _time.GetUtcNow())
            throw new LocalTaskValidationException("Reminder due time must be in the future.");
        return VerifiedRecord(_store.Create(
            Required(arguments, "title"),
            OptionalString(arguments, "details") ?? string.Empty,
            due));
    }

    private OperationOutcome VerifiedRecord(LocalTaskRecord changed)
    {
        LocalTaskRecord observed;
        try
        {
            observed = Verify(changed);
        }
        catch (LocalTaskNotFoundException)
        {
            return OperationOutcome.Failure(
                "verification_failed",
                effectMayHaveOccurred: true);
        }

        return OperationOutcome.Success(ReminderResultJson.Record(observed));
    }

    private JsonElement List(JsonElement arguments, bool dueOnly)
    {
        int limit = OptionalInt(arguments, "limit") ?? 20;
        IReadOnlyList<LocalTaskRecord> listed = _store.List(
            TaskListStatus.Open,
            includeDeleted: false,
            limit);
        if (dueOnly)
        {
            DateTimeOffset now = _time.GetUtcNow();
            listed = listed.Where(item => item.DueUtc <= now).Take(limit).ToArray();
        }
        foreach (LocalTaskRecord item in listed) _ = Verify(item);
        return ReminderResultJson.List(listed, dueOnly ? "due" : "scheduled", limit);
    }

    private LocalTaskRecord Verify(LocalTaskRecord expected)
    {
        LocalTaskRecord observed = _store.Read(expected.Id, includeDeleted: true);
        if (observed != expected)
        {
            throw new LocalTaskStoreException("Reminder verification failed.");
        }

        return observed;
    }

    private static Guid Id(JsonElement arguments)
    {
        if (!Guid.TryParseExact(Required(arguments, "reminderId"), "D", out Guid id))
            throw new JsonException();
        return id;
    }
    private static string Required(JsonElement arguments, string name) =>
        arguments.GetProperty(name).GetString()!;
    private static string? OptionalString(JsonElement arguments, string name) =>
        arguments.TryGetProperty(name, out JsonElement value) && value.ValueKind != JsonValueKind.Null
            ? value.GetString() : null;
    private static int? OptionalInt(JsonElement arguments, string name) =>
        arguments.TryGetProperty(name, out JsonElement value) ? value.GetInt32() : null;
    private static bool? OptionalBoolean(JsonElement arguments, string name) =>
        arguments.TryGetProperty(name, out JsonElement value) ? value.GetBoolean() : null;
}

internal static class ReminderResultJson
{
    public static JsonElement Record(LocalTaskRecord item) => Write(writer => WriteItem(writer, item));
    public static JsonElement Selection(LocalTaskRecord item) => Write(writer =>
    {
        writer.WriteString("reminderId", item.Id);
        writer.WriteNumber("expectedVersion", item.Version);
        writer.WriteString("reviewLabel", item.Title);
        writer.WriteBoolean("deleted", item.Deleted);
    });
    public static JsonElement List(IReadOnlyList<LocalTaskRecord> items, string mode, int limit) => Write(writer =>
    {
        writer.WritePropertyName("reminders");
        writer.WriteStartArray();
        foreach (LocalTaskRecord item in items) { writer.WriteStartObject(); WriteItem(writer, item); writer.WriteEndObject(); }
        writer.WriteEndArray();
        writer.WriteNumber("count", items.Count);
        writer.WriteString("mode", mode);
        writer.WriteNumber("limit", limit);
    });
    private static void WriteItem(Utf8JsonWriter writer, LocalTaskRecord item)
    {
        writer.WriteString("reminderId", item.Id);
        writer.WriteString("title", item.Title);
        writer.WriteString("details", item.Details);
        if (item.DueUtc is DateTimeOffset dueUtc) writer.WriteString("dueUtc", dueUtc);
        else writer.WriteNull("dueUtc");
        writer.WriteBoolean("dismissed", item.Completed);
        writer.WriteBoolean("deleted", item.Deleted);
        writer.WriteNumber("version", item.Version);
    }
    private static JsonElement Write(Action<Utf8JsonWriter> body)
    {
        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject(); writer.WriteNumber("version", 1); body(writer); writer.WriteEndObject();
        }
        using JsonDocument document = JsonDocument.Parse(buffer.WrittenMemory);
        return document.RootElement.Clone();
    }
}
