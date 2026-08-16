using System.Buffers;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Contracts;
using Baxy.Security.Windows;

namespace Baxy.App;

internal sealed class PreparedOperation
{
    private readonly JsonElement _arguments;

    private PreparedOperation(
        string operationName,
        JsonElement arguments,
        string missionId,
        string invocationId,
        bool cloneArguments)
    {
        if (!ContractValidator.IsOperationName(operationName))
        {
            throw new ArgumentException("El nombre de operación local no es válido.", nameof(operationName));
        }

        if (arguments.ValueKind != JsonValueKind.Object)
        {
            throw new ArgumentException("Los argumentos locales deben ser un objeto JSON.", nameof(arguments));
        }

        if (!ContractValidator.IsCanonicalIdentifier(missionId))
        {
            throw new ArgumentException("El ID de misión local no es válido.", nameof(missionId));
        }

        if (!ContractValidator.IsCanonicalIdentifier(invocationId))
        {
            throw new ArgumentException("El ID de invocación local no es válido.", nameof(invocationId));
        }

        OperationName = operationName;
        _arguments = cloneArguments ? arguments.Clone() : arguments;
        IdentityKey = CreateIdentityKey(operationName, _arguments);
        MissionId = missionId;
        InvocationId = invocationId;
    }

    public string OperationName { get; }

    public string IdentityKey { get; }

    public string MissionId { get; }

    public string InvocationId { get; }

    internal JsonElement Arguments => _arguments;

    public static PreparedOperation Create(string operationName, JsonObject arguments)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(operationName);
        ArgumentNullException.ThrowIfNull(arguments);
        EnsurePlaintextOperationAllowed(operationName);
        JsonElement ownedArguments = JsonSerializer.SerializeToElement(arguments);
        return new PreparedOperation(
            operationName,
            ownedArguments,
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            cloneArguments: false);
    }

    internal static PreparedOperation CreateFollowUp(
        string operationName,
        JsonObject arguments,
        string missionId)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(operationName);
        ArgumentNullException.ThrowIfNull(arguments);
        EnsurePlaintextOperationAllowed(operationName);
        if (!ContractValidator.IsCanonicalIdentifier(missionId))
        {
            throw new ArgumentException("El ID de misión local no es válido.", nameof(missionId));
        }

        JsonElement ownedArguments = JsonSerializer.SerializeToElement(arguments);
        return new PreparedOperation(
            operationName,
            ownedArguments,
            missionId,
            Guid.NewGuid().ToString("D"),
            cloneArguments: false);
    }

    internal static PreparedOperation Restore(
        string operationName,
        JsonElement arguments,
        string missionId,
        string invocationId) =>
        new(operationName, arguments, missionId, invocationId, cloneArguments: true);

    public OperationRequest CreateRequest(string? confirmationToken = null) => new(
        ProtocolTypes.OperationRequest,
        Guid.NewGuid().ToString("D"),
        MissionId,
        InvocationId,
        OperationName,
        _arguments,
        confirmationToken);

    internal bool Matches(RoutedOperation routed)
    {
        ArgumentNullException.ThrowIfNull(routed);
        if (!string.Equals(OperationName, routed.Name, StringComparison.Ordinal))
        {
            return false;
        }

        JsonElement ownedArguments = JsonSerializer.SerializeToElement(routed.Arguments);
        return string.Equals(
            IdentityKey,
            CreateIdentityKey(routed.Name, ownedArguments),
            StringComparison.Ordinal);
    }

    private static string CreateIdentityKey(string operationName, JsonElement arguments)
    {
        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            WriteCanonicalJson(writer, arguments);
        }

        return operationName + "\n" + Encoding.UTF8.GetString(buffer.WrittenSpan);
    }

    private static void EnsurePlaintextOperationAllowed(string operationName)
    {
        if (operationName.StartsWith("memory.", StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "Una operacion de memoria debe prepararse con su envelope autenticado.");
        }
    }

    private static void WriteCanonicalJson(Utf8JsonWriter writer, JsonElement value)
    {
        switch (value.ValueKind)
        {
            case JsonValueKind.Object:
                writer.WriteStartObject();
                foreach (JsonProperty property in value
                             .EnumerateObject()
                             .OrderBy(static property => property.Name, StringComparer.Ordinal))
                {
                    writer.WritePropertyName(property.Name);
                    WriteCanonicalJson(writer, property.Value);
                }

                writer.WriteEndObject();
                break;
            case JsonValueKind.Array:
                writer.WriteStartArray();
                foreach (JsonElement item in value.EnumerateArray())
                {
                    WriteCanonicalJson(writer, item);
                }

                writer.WriteEndArray();
                break;
            case JsonValueKind.String:
                writer.WriteStringValue(value.GetString());
                break;
            case JsonValueKind.Number:
                writer.WriteRawValue(value.GetRawText());
                break;
            case JsonValueKind.True:
                writer.WriteBooleanValue(true);
                break;
            case JsonValueKind.False:
                writer.WriteBooleanValue(false);
                break;
            case JsonValueKind.Null:
                writer.WriteNullValue();
                break;
            default:
                throw new JsonException("Los argumentos locales contienen un valor JSON no válido.");
        }
    }
}

internal sealed class RetryableOperationRegistry
{
    private readonly Dictionary<string, PreparedOperation> _operations = new(StringComparer.Ordinal);
    private readonly DurableRetryStore _store;
    private readonly MemoryOperationProtector? _memoryProtector;

    public RetryableOperationRegistry(string outboxPath)
        : this(new DurableRetryStore(outboxPath), memoryProtector: null)
    {
    }

    internal RetryableOperationRegistry(
        string outboxPath,
        MemoryOperationProtector memoryProtector)
        : this(
            new DurableRetryStore(outboxPath),
            memoryProtector ?? throw new ArgumentNullException(nameof(memoryProtector)))
    {
    }

    internal RetryableOperationRegistry(
        DurableRetryStore store,
        MemoryOperationProtector? memoryProtector = null)
    {
        ArgumentNullException.ThrowIfNull(store);
        _store = store;
        _memoryProtector = memoryProtector;
        foreach (PreparedOperation operation in store.Load())
        {
            AuthenticateLoadedMemoryOperation(operation);
            if (!_operations.TryAdd(operation.IdentityKey, operation))
            {
                throw new InvalidDataException("La cola durable contiene operaciones duplicadas.");
            }
        }
    }

    public static RetryableOperationRegistry CreateDefault(
        MemoryOperationProtector? memoryProtector = null) =>
        new(
            new DurableRetryStore(DurableRetryStore.ResolveDefaultPath()),
            memoryProtector);

    public PreparedOperation GetOrAdd(RoutedOperation routed)
    {
        ArgumentNullException.ThrowIfNull(routed);
        PreparedOperation candidate = PreparedOperation.Create(routed.Name, routed.Arguments);
        return GetOrAddPrepared(candidate);
    }

    public PreparedOperation GetOrAdd(ProtectedMemoryOperation protectedOperation)
    {
        ArgumentNullException.ThrowIfNull(protectedOperation);
        if (_memoryProtector is null
            || !_memoryProtector.Authenticates(protectedOperation))
        {
            throw new InvalidOperationException(
                "La cola durable no puede autenticar esta operacion privada.");
        }

        _ = _memoryProtector.AuthenticateForOutbox(protectedOperation.Prepared);
        return GetOrAddPrepared(protectedOperation.Prepared);
    }

    private void AuthenticateLoadedMemoryOperation(PreparedOperation operation)
    {
        if (!MemoryOperationProtector.IsMemoryOperation(operation.OperationName))
        {
            return;
        }

        if (_memoryProtector is null)
        {
            throw new InvalidDataException(
                "La cola durable contiene memoria sin una autoridad privada disponible.");
        }

        try
        {
            _ = _memoryProtector.InspectForRecovery(operation);
        }
        catch (Exception exception) when (exception is ProtectedPayloadException
            or InvalidDataException
            or StaleMemorySessionException)
        {
            throw new InvalidDataException(
                "La cola durable contiene una operacion privada no autenticada.",
                exception);
        }
    }

    private PreparedOperation GetOrAddPrepared(PreparedOperation candidate)
    {
        if (_operations.TryGetValue(candidate.IdentityKey, out PreparedOperation? existing))
        {
            return existing;
        }

        var next = _operations.Values.Append(candidate).ToArray();
        _store.Save(next);
        _operations.Add(candidate.IdentityKey, candidate);
        return candidate;
    }

    public PreparedOperation Replace(PreparedOperation current, RoutedOperation routed)
        => Replace(current, routed, preserveMission: false);

    public PreparedOperation ReplaceWithFollowUp(
        PreparedOperation current,
        RoutedOperation routed)
        => Replace(current, routed, preserveMission: true);

    private PreparedOperation Replace(
        PreparedOperation current,
        RoutedOperation routed,
        bool preserveMission)
    {
        ArgumentNullException.ThrowIfNull(current);
        ArgumentNullException.ThrowIfNull(routed);
        if (routed.Name.StartsWith("memory.", StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "Una operacion de memoria no puede reemplazar una peticion en texto claro.");
        }

        if (!_operations.TryGetValue(current.IdentityKey, out PreparedOperation? registered)
            || !ReferenceEquals(current, registered))
        {
            throw new InvalidOperationException("La petición pendiente ya no pertenece a la cola durable.");
        }

        PreparedOperation candidate = preserveMission
            ? PreparedOperation.CreateFollowUp(routed.Name, routed.Arguments, current.MissionId)
            : PreparedOperation.Create(routed.Name, routed.Arguments);
        if (string.Equals(candidate.IdentityKey, current.IdentityKey, StringComparison.Ordinal))
        {
            return current;
        }

        bool candidateAlreadyPending = _operations.TryGetValue(
            candidate.IdentityKey,
            out PreparedOperation? existing);
        PreparedOperation replacement = candidateAlreadyPending ? existing! : candidate;
        List<PreparedOperation> next = _operations.Values
            .Where(operation => !ReferenceEquals(operation, current))
            .ToList();
        if (!candidateAlreadyPending)
        {
            next.Add(candidate);
        }

        _store.Save(next);
        _operations.Remove(current.IdentityKey);
        if (!candidateAlreadyPending)
        {
            _operations.Add(candidate.IdentityKey, candidate);
        }

        return replacement;
    }

    public void MarkResolved(PreparedOperation operation)
    {
        ArgumentNullException.ThrowIfNull(operation);
        if (_operations.TryGetValue(operation.IdentityKey, out PreparedOperation? current)
            && ReferenceEquals(current, operation))
        {
            PreparedOperation[] remaining = _operations.Values
                .Where(candidate => !ReferenceEquals(candidate, operation))
                .ToArray();
            _store.Save(remaining);
            _operations.Remove(operation.IdentityKey);
        }
    }

    public IReadOnlyList<PreparedOperation> SnapshotPendingOperations() =>
        _operations.Values.ToArray();

    internal PreparedOperation RestorePlanOperation(PreparedOperation restored)
    {
        ArgumentNullException.ThrowIfNull(restored);
        if (restored.OperationName.StartsWith("memory.", StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "El planner general no puede restaurar operaciones privadas.");
        }

        if (_operations.TryGetValue(restored.IdentityKey, out PreparedOperation? existing))
        {
            return existing;
        }

        return GetOrAddPrepared(restored);
    }
}
