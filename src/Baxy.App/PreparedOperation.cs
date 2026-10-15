using System.Buffers;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Contracts;

namespace Baxy.App;

/// <summary>A catalog operation the model called, with its plain arguments (never a memory operation).</summary>
internal sealed record RoutedOperation(string Name, JsonObject Arguments);

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
            throw new ArgumentException("The local mission id is not valid.", nameof(missionId));
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

/// <summary>
/// The calls of this App session still unresolved: the same call made again while one is unresolved gets the same
/// invocation, so the kernel's journal replays it instead of running it twice. It lives in memory only; a new start
/// begins empty, since a call of an earlier session is never resumed or retried by itself.
/// </summary>
internal sealed class RetryableOperationRegistry
{
    private readonly Dictionary<string, PreparedOperation> _operations = new(StringComparer.Ordinal);

    public PreparedOperation GetOrAdd(RoutedOperation routed)
    {
        ArgumentNullException.ThrowIfNull(routed);
        PreparedOperation candidate = PreparedOperation.Create(routed.Name, routed.Arguments);
        if (_operations.TryGetValue(candidate.IdentityKey, out PreparedOperation? existing))
        {
            return existing;
        }

        _operations.Add(candidate.IdentityKey, candidate);
        return candidate;
    }

    public void MarkResolved(PreparedOperation operation)
    {
        ArgumentNullException.ThrowIfNull(operation);
        if (_operations.TryGetValue(operation.IdentityKey, out PreparedOperation? current)
            && ReferenceEquals(current, operation))
        {
            _operations.Remove(operation.IdentityKey);
        }
    }
}
