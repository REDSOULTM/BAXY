using System.Buffers;
using System.Text.Json;
using Baxy.Kernel.Operations;
using Baxy.Providers.Windows.Routines;
using Baxy.Providers.Windows.Tasks;

namespace Baxy.Core.Operations;

internal static class RoutineHandlers
{
    public static IOperationHandler[] Create(IRoutineStore store) =>
    [
        new RoutineHandler("routine.delete", store),
        new RoutineHandler("routine.list", store),
        new RoutineHandler("routine.phrase.create", store),
        new RoutineHandler("routine.read", store),
        new RoutineHandler("routine.resolve.exact", store),
        new RoutineHandler("routine.restore", store),
        new RoutineHandler("routine.set.enabled", store),
    ];
}

internal sealed class RoutineHandler(string operation, IRoutineStore store) : IOperationHandler
{
    private readonly IRoutineStore _store = store ?? throw new ArgumentNullException(nameof(store));
    public OperationDefinition Definition { get; } = ProductCatalog.CreateDefinition(operation);

    public ValueTask<OperationOutcome> ExecuteAsync(
        OperationInvocation invocation,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        try
        {
            JsonElement a = invocation.Arguments;
            OperationOutcome outcome = operation switch
            {
                "routine.phrase.create" => VerifiedRecord(_store.CreatePhrase(
                    a.GetProperty("name").GetString()!,
                    a.GetProperty("phrase").GetString()!,
                    a.TryGetProperty("action", out JsonElement action)
                        ? action.GetString()! : "media.control")),
                "routine.list" => OperationOutcome.Success(RoutineResultJson.List(
                    VerifyAll(_store.List(
                        Bool(a, "includeDeleted") ?? false, Int(a, "limit") ?? 20)))),
                "routine.read" => OperationOutcome.Success(RoutineResultJson.Record(
                    Verify(_store.Read(Id(a), Bool(a, "includeDeleted") ?? false)))),
                "routine.resolve.exact" => OperationOutcome.Success(RoutineResultJson.Selection(
                    Verify(_store.ResolveExact(
                        a.GetProperty("name").GetString()!, Bool(a, "includeDeleted") ?? false)))),
                "routine.set.enabled" => VerifiedMutation(_store.SetEnabled(
                    Id(a), a.GetProperty("expectedRevision").GetInt64(),
                    a.GetProperty("enabled").GetBoolean())),
                "routine.delete" => VerifiedMutation(_store.Delete(
                    Id(a), a.GetProperty("expectedRevision").GetInt64(),
                    a.GetProperty("reviewLabel").GetString()!)),
                "routine.restore" => VerifiedMutation(_store.Restore(
                    Id(a), a.GetProperty("expectedRevision").GetInt64())),
                _ => throw new InvalidOperationException("Unknown routine operation."),
            };
            return ValueTask.FromResult(outcome);
        }
        catch (JsonException) { return ValueTask.FromResult(OperationOutcome.Failure("invalid_arguments")); }
        catch (LocalTaskStoreException exception) when (exception is not LocalTaskNotFoundException
            and not LocalTaskAmbiguousException
            and not LocalTaskVersionConflictException)
        {
            return ValueTask.FromResult(OperationOutcome.Failure(
                "verification_failed",
                effectMayHaveOccurred: Definition.Risk != OperationRisk.ReadOnly));
        }
        catch (LocalTaskNotFoundException) { return ValueTask.FromResult(OperationOutcome.Failure("routine_not_found")); }
        catch (LocalTaskAmbiguousException) { return ValueTask.FromResult(OperationOutcome.Failure("routine_ambiguous")); }
        catch (LocalTaskVersionConflictException) { return ValueTask.FromResult(OperationOutcome.Failure("routine_version_conflict")); }
        catch (LocalTaskStoreException) { return ValueTask.FromResult(OperationOutcome.Failure("routine_store_failed")); }
    }

    private OperationOutcome VerifiedRecord(RoutineRecord changed) =>
        OperationOutcome.Success(RoutineResultJson.Record(Verify(changed)));

    private OperationOutcome VerifiedMutation(RoutineRecord changed) =>
        OperationOutcome.Success(RoutineResultJson.Mutation(Verify(changed)));

    private IReadOnlyList<RoutineRecord> VerifyAll(IReadOnlyList<RoutineRecord> items)
    {
        foreach (RoutineRecord item in items)
        {
            _ = Verify(item);
        }

        return items;
    }

    private RoutineRecord Verify(RoutineRecord expected)
    {
        RoutineRecord observed;
        try
        {
            observed = _store.Read(expected.Id, includeDeleted: true);
        }
        catch (LocalTaskNotFoundException)
        {
            throw new LocalTaskStoreException("Routine verification failed.");
        }

        if (observed.Id != expected.Id
            || observed.Revision != expected.Revision
            || observed.Enabled != expected.Enabled
            || observed.Deleted != expected.Deleted
            || !string.Equals(observed.Name, expected.Name, StringComparison.Ordinal)
            || !string.Equals(observed.WorkflowId, expected.WorkflowId, StringComparison.Ordinal))
        {
            throw new LocalTaskStoreException("Routine verification failed.");
        }

        return observed;
    }

    private static Guid Id(JsonElement a)
    {
        if (!Guid.TryParseExact(a.GetProperty("routineId").GetString(), "D", out Guid id)) throw new JsonException();
        return id;
    }
    private static bool? Bool(JsonElement a, string name) =>
        a.TryGetProperty(name, out JsonElement value) ? value.GetBoolean() : null;
    private static int? Int(JsonElement a, string name) =>
        a.TryGetProperty(name, out JsonElement value) ? value.GetInt32() : null;
}

internal static class RoutineResultJson
{
    public static JsonElement Record(RoutineRecord item) => Write(w => { w.WritePropertyName("routine"); WriteRecord(w, item); });
    public static JsonElement List(IReadOnlyList<RoutineRecord> items) => Write(w =>
    {
        w.WritePropertyName("routines"); w.WriteStartArray();
        foreach (RoutineRecord item in items) WriteRecord(w, item);
        w.WriteEndArray(); w.WriteNumber("count", items.Count);
    });
    public static JsonElement Selection(RoutineRecord item) => Write(w =>
    {
        w.WriteString("routineId", item.Id); w.WriteNumber("expectedRevision", item.Revision);
        w.WriteString("reviewLabel", item.Name); w.WriteBoolean("deleted", item.Deleted);
        w.WriteBoolean("enabled", item.Enabled);
    });
    public static JsonElement Mutation(RoutineRecord item) => Write(w =>
    {
        w.WriteString("routineId", item.Id); w.WriteNumber("revision", item.Revision);
        w.WriteBoolean("enabled", item.Enabled); w.WriteBoolean("deleted", item.Deleted);
    });
    private static void WriteRecord(Utf8JsonWriter w, RoutineRecord item)
    {
        w.WriteStartObject(); w.WriteString("routineId", item.Id); w.WriteNumber("revision", item.Revision);
        w.WriteString("name", item.Name); w.WriteString("workflowId", item.WorkflowId);
        w.WriteString("workflowVersion", item.WorkflowVersion); w.WritePropertyName("inputFields");
        w.WriteStartArray(); foreach (string field in item.InputFields) w.WriteStringValue(field); w.WriteEndArray();
        w.WriteString("triggerKind", item.TriggerKind);
        if (item.AppKey is null) w.WriteNull("appKey"); else w.WriteString("appKey", item.AppKey);
        w.WriteBoolean("enabled", item.Enabled); w.WriteBoolean("deleted", item.Deleted); w.WriteEndObject();
    }
    private static JsonElement Write(Action<Utf8JsonWriter> body)
    {
        var buffer = new ArrayBufferWriter<byte>();
        using (var w = new Utf8JsonWriter(buffer)) { w.WriteStartObject(); w.WriteNumber("version", 1); body(w); w.WriteEndObject(); }
        using JsonDocument document = JsonDocument.Parse(buffer.WrittenMemory); return document.RootElement.Clone();
    }
}
