using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using Baxy.Contracts;
using Baxy.Security.Windows;

namespace Baxy.App;

// Memory arguments are private until the shell encrypts them. Keeping this type
// unrelated to RoutedOperation makes an unsealed memory request impossible to
// hand to RetryableOperationRegistry by accident.
internal sealed class MemoryRoutedOperation
{
    private readonly JsonObject _privateArguments;

    internal MemoryRoutedOperation(string name, JsonObject privateArguments)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(name);
        ArgumentNullException.ThrowIfNull(privateArguments);
        Name = name;
        _privateArguments = (JsonObject)privateArguments.DeepClone();
    }

    internal string Name { get; }

    internal JsonObject PrivateArguments => (JsonObject)_privateArguments.DeepClone();

    public override string ToString() =>
        $"{nameof(MemoryRoutedOperation)} {{ Name = {Name}, PrivateArguments = [REDACTED] }}";
}


internal sealed class MemoryOperationProtector
{
    private readonly BoundProtectedJsonCodec _codec;

    internal MemoryOperationProtector(BoundProtectedJsonCodec codec, string sessionId)
    {
        _codec = codec ?? throw new ArgumentNullException(nameof(codec));
        if (!ContractValidator.IsCanonicalIdentifier(sessionId))
        {
            throw new ArgumentException("La sesion privada no es valida.", nameof(sessionId));
        }

        SessionId = sessionId;
    }

    internal string SessionId { get; }

    internal static MemoryOperationProtector CreateDefault(string sessionId)
    {
        string dataRoot = ResolveDataRoot();
        var protectedPayload = new WindowsProtectedPayload(
            Path.Combine(dataRoot, "security", "private-payload.v1.key"));
        return new MemoryOperationProtector(
            new BoundProtectedJsonCodec(protectedPayload),
            sessionId);
    }

    internal ProtectedMemoryOperation Prepare(MemoryRoutedOperation privateOperation)
    {
        ArgumentNullException.ThrowIfNull(privateOperation);
        EnsureMemoryOperation(privateOperation.Name);
        JsonObject privateArguments = privateOperation.PrivateArguments;
        EnsureNoReservedPayloadProperties(privateArguments);

        string operation = ResolveWireOperationName(
            privateOperation.Name,
            privateArguments);
        ValidateWireRiskBinding(operation, privateArguments);
        string missionId = Guid.NewGuid().ToString("D");
        string invocationId = Guid.NewGuid().ToString("D");
        JsonElement envelope = _codec.SealArguments(
            operation,
            missionId,
            invocationId,
            SessionId,
            privateArguments);
        PreparedOperation prepared = PreparedOperation.Restore(
            operation,
            envelope,
            missionId,
            invocationId);
        return new ProtectedMemoryOperation(prepared);
    }

    internal OpenedBoundProtectedJson OpenPrivateArguments(PreparedOperation prepared)
    {
        ArgumentNullException.ThrowIfNull(prepared);
        EnsureMemoryOperation(prepared.OperationName);
        OpenedBoundProtectedJson opened = _codec.OpenArguments(
            prepared.Arguments,
            prepared.OperationName,
            prepared.MissionId,
            prepared.InvocationId);
        try
        {
            if (!string.Equals(opened.SessionId, SessionId, StringComparison.Ordinal))
            {
                throw new StaleMemorySessionException();
            }

            ValidateWireRiskBinding(prepared.OperationName, opened.Payload);
            return opened;
        }
        catch
        {
            opened.Dispose();
            throw;
        }
    }

    internal MemoryOperationInspection InspectForRecovery(PreparedOperation prepared)
    {
        ArgumentNullException.ThrowIfNull(prepared);
        EnsureMemoryOperation(prepared.OperationName);
        using OpenedBoundProtectedJson opened = _codec.OpenArguments(
            prepared.Arguments,
            prepared.OperationName,
            prepared.MissionId,
            prepared.InvocationId);
        ValidateWireRiskBinding(prepared.OperationName, opened.Payload);
        bool current = string.Equals(opened.SessionId, SessionId, StringComparison.Ordinal);
        return new MemoryOperationInspection(
            current,
            ShouldCancelAfterSessionChange(prepared.OperationName, opened.Payload));
    }

    internal OpenedBoundProtectedJson OpenResult(
        OperationResponse response,
        PreparedOperation prepared)
    {
        ArgumentNullException.ThrowIfNull(response);
        ArgumentNullException.ThrowIfNull(prepared);
        EnsureMemoryOperation(prepared.OperationName);
        if (!string.Equals(response.Type, ProtocolTypes.OperationResponse, StringComparison.Ordinal)
            || !string.Equals(response.Status, OperationStatuses.Completed, StringComparison.Ordinal)
            || !response.Verified
            || response.ErrorCode is not null
            || !string.Equals(response.MissionId, prepared.MissionId, StringComparison.Ordinal)
            || !string.Equals(response.InvocationId, prepared.InvocationId, StringComparison.Ordinal)
            || response.Result is not { ValueKind: JsonValueKind.Object } result)
        {
            throw new InvalidDataException("La respuesta privada no coincide con la peticion.");
        }

        string expectedSession;
        using (OpenedBoundProtectedJson arguments = _codec.OpenArguments(
                   prepared.Arguments,
                   prepared.OperationName,
                   prepared.MissionId,
                   prepared.InvocationId))
        {
            expectedSession = arguments.SessionId;
        }

        OpenedBoundProtectedJson opened = _codec.OpenResult(
            result,
            prepared.OperationName,
            prepared.MissionId,
            prepared.InvocationId);
        if (!string.Equals(opened.SessionId, expectedSession, StringComparison.Ordinal))
        {
            opened.Dispose();
            throw new InvalidDataException("La respuesta privada cambio de sesion.");
        }

        return opened;
    }

    internal static bool IsMemoryOperation(string operationName) => operationName is
        "memory.correct"
        or "memory.disable"
        or "memory.enable"
        or "memory.export"
        or "memory.forget"
        or "memory.list"
        or "memory.recall"
        or "memory.save"
        or "memory.sensitive.save"
        or "memory.session.clear"
        or "memory.status";

    internal static string ResolveDataRoot()
    {
        string? configured = Environment.GetEnvironmentVariable("BAXY_DATA_DIR");
        string dataRoot = string.IsNullOrWhiteSpace(configured)
            ? Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "BAXY",
                "1")
            : configured;
        return WindowsPrivateStorage.PreparePrivateDataRoot(dataRoot);
    }

    private static string ResolveWireOperationName(
        string operationName,
        JsonObject arguments) =>
        operationName switch
        {
            "memory.save" when RequiredString(arguments, "sensitivity")
                is "sensitive" or "secret" => "memory.sensitive.save",
            "memory.save" => "memory.save",
            "memory.forget" when RequiredString(arguments, "scope") == "session"
                => "memory.session.clear",
            _ => operationName,
        };

    private static void ValidateWireRiskBinding(string operation, JsonElement payload)
    {
        if (payload.ValueKind != JsonValueKind.Object)
        {
            throw new InvalidDataException("La peticion privada no tiene la forma esperada.");
        }

        switch (operation)
        {
            case "memory.enable":
                if (!RequiredBoolean(payload, "enabled"))
                {
                    throw new InvalidDataException("La operacion no coincide con su riesgo.");
                }

                break;
            case "memory.disable":
                if (RequiredBoolean(payload, "enabled"))
                {
                    throw new InvalidDataException("La operacion no coincide con su riesgo.");
                }

                break;
            case "memory.save":
                {
                    string sensitivity = RequiredString(payload, "sensitivity");
                    if (sensitivity is not ("normal" or "personal")
                        || payload.TryGetProperty("value", out JsonElement value)
                        && value.ValueKind == JsonValueKind.String
                        && SensitiveText.Contains(value.GetString()!))
                    {
                        throw new InvalidDataException("La memoria requiere el canal sensible.");
                    }

                    break;
                }
            case "memory.sensitive.save":
                if (RequiredString(payload, "sensitivity") is not ("sensitive" or "secret"))
                {
                    throw new InvalidDataException("La operacion no coincide con su riesgo.");
                }

                break;
            case "memory.forget":
                if (RequiredString(payload, "scope") == "session"
                    || !RequiredBoolean(payload, "confirmationRequired"))
                {
                    throw new InvalidDataException("La eliminacion requiere confirmacion.");
                }

                break;
            case "memory.session.clear":
                if (RequiredString(payload, "scope") != "session"
                    || RequiredBoolean(payload, "confirmationRequired")
                    || !RequiredBoolean(payload, "mustNotDeletePersistent")
                    || !payload.TryGetProperty("selector", out JsonElement selector)
                    || selector.ValueKind != JsonValueKind.Null)
                {
                    throw new InvalidDataException("La limpieza de sesion excede su alcance.");
                }

                break;
        }
    }

    private static void ValidateWireRiskBinding(string operation, JsonObject payload)
    {
        switch (operation)
        {
            case "memory.enable":
                if (!RequiredBoolean(payload, "enabled"))
                {
                    throw new InvalidDataException("La operacion no coincide con su riesgo.");
                }

                break;
            case "memory.disable":
                if (RequiredBoolean(payload, "enabled"))
                {
                    throw new InvalidDataException("La operacion no coincide con su riesgo.");
                }

                break;
            case "memory.save":
                {
                    string sensitivity = RequiredString(payload, "sensitivity");
                    if (sensitivity is not ("normal" or "personal")
                        || payload["value"] is JsonValue value
                        && value.TryGetValue(out string? clearValue)
                        && SensitiveText.Contains(clearValue!))
                    {
                        throw new InvalidDataException("La memoria requiere el canal sensible.");
                    }

                    break;
                }
            case "memory.sensitive.save":
                if (RequiredString(payload, "sensitivity") is not ("sensitive" or "secret"))
                {
                    throw new InvalidDataException("La operacion no coincide con su riesgo.");
                }

                break;
            case "memory.forget":
                if (RequiredString(payload, "scope") == "session"
                    || !RequiredBoolean(payload, "confirmationRequired"))
                {
                    throw new InvalidDataException("La eliminacion requiere confirmacion.");
                }

                break;
            case "memory.session.clear":
                if (RequiredString(payload, "scope") != "session"
                    || RequiredBoolean(payload, "confirmationRequired")
                    || !RequiredBoolean(payload, "mustNotDeletePersistent")
                    || payload["selector"] is not null)
                {
                    throw new InvalidDataException("La limpieza de sesion excede su alcance.");
                }

                break;
        }
    }

    private static bool ShouldCancelAfterSessionChange(
        string operation,
        JsonElement payload)
    {
        if (operation is "memory.recall"
            or "memory.list"
            or "memory.status"
            or "memory.correct"
            or "memory.session.clear")
        {
            return true;
        }

        if (operation is "memory.save" or "memory.sensitive.save")
        {
            return !payload.TryGetProperty("retention", out JsonElement retention)
                || retention.ValueKind != JsonValueKind.String
                || !string.Equals(retention.GetString(), "persistent", StringComparison.Ordinal);
        }

        return false;
    }

    private static string RequiredString(JsonObject arguments, string name)
    {
        if (arguments[name] is JsonValue value
            && value.TryGetValue(out string? result)
            && !string.IsNullOrWhiteSpace(result))
        {
            return result;
        }

        throw new InvalidDataException("La peticion privada no tiene la forma esperada.");
    }

    private static bool RequiredBoolean(JsonObject arguments, string name)
    {
        if (arguments[name] is JsonValue value && value.TryGetValue(out bool result))
        {
            return result;
        }

        throw new InvalidDataException("La peticion privada no tiene la forma esperada.");
    }

    private static string RequiredString(JsonElement arguments, string name)
    {
        if (arguments.TryGetProperty(name, out JsonElement value)
            && value.ValueKind == JsonValueKind.String
            && !string.IsNullOrWhiteSpace(value.GetString()))
        {
            return value.GetString()!;
        }

        throw new InvalidDataException("La peticion privada no tiene la forma esperada.");
    }

    private static bool RequiredBoolean(JsonElement arguments, string name)
    {
        if (arguments.TryGetProperty(name, out JsonElement value)
            && value.ValueKind is JsonValueKind.True or JsonValueKind.False)
        {
            return value.GetBoolean();
        }

        throw new InvalidDataException("La peticion privada no tiene la forma esperada.");
    }

    private static void EnsureNoReservedPayloadProperties(JsonObject arguments)
    {
        if (arguments.ContainsKey("operation")
            || arguments.ContainsKey("missionId")
            || arguments.ContainsKey("invocationId")
            || arguments.ContainsKey("sessionId")
            || arguments.ContainsKey("payload"))
        {
            throw new InvalidDataException("La peticion privada contiene estado reservado.");
        }
    }

    private static void EnsureMemoryOperation(string operationName)
    {
        if (!IsMemoryOperation(operationName))
        {
            throw new InvalidDataException("La operacion no pertenece a memoria privada.");
        }
    }

}

internal sealed class ProtectedMemoryOperation
{
    internal ProtectedMemoryOperation(PreparedOperation prepared)
    {
        Prepared = prepared ?? throw new ArgumentNullException(nameof(prepared));
        if (!MemoryOperationProtector.IsMemoryOperation(prepared.OperationName))
        {
            throw new ArgumentException("La operacion preparada no es memoria protegida.", nameof(prepared));
        }
    }

    internal PreparedOperation Prepared { get; }

    public override string ToString() =>
        $"{nameof(ProtectedMemoryOperation)} {{ Operation = {Prepared.OperationName}, Arguments = [PROTECTED] }}";
}

internal sealed record MemoryOperationInspection(
    bool OriginatesInCurrentSession,
    bool CancelAfterSessionChange);

internal sealed class StaleMemorySessionException : Exception
{
    internal StaleMemorySessionException()
        : base("La operacion privada pertenece a una sesion anterior.")
    {
    }
}

internal sealed class PendingMemoryConfirmation
{
    private PendingMemoryConfirmation(
        PreparedOperation prepared,
        string token,
        DateTimeOffset expiresAtUtc,
        bool reconciliationRequired)
    {
        Prepared = prepared;
        Token = token;
        ExpiresAtUtc = expiresAtUtc;
        ReconciliationRequired = reconciliationRequired;
    }

    internal PreparedOperation Prepared { get; }

    internal string Token { get; }

    internal DateTimeOffset ExpiresAtUtc { get; }

    internal bool ReconciliationRequired { get; }

    internal static bool TryCreate(
        OperationResponse response,
        PreparedOperation prepared,
        TimeProvider timeProvider,
        out PendingMemoryConfirmation? confirmation)
    {
        ArgumentNullException.ThrowIfNull(response);
        ArgumentNullException.ThrowIfNull(prepared);
        ArgumentNullException.ThrowIfNull(timeProvider);
        confirmation = null;
        if (!MemoryOperationProtector.IsMemoryOperation(prepared.OperationName)
            || !ConfirmationChallengeParser.TryParse(
                response,
                prepared,
                timeProvider,
                out ValidatedConfirmationChallenge challenge))
        {
            return false;
        }

        confirmation = new PendingMemoryConfirmation(
            prepared,
            challenge.Token,
            challenge.ExpiresAtUtc,
            challenge.ReconciliationRequired);
        return true;
    }

    public override string ToString() =>
        $"{nameof(PendingMemoryConfirmation)} {{ Operation = {Prepared.OperationName}, Token = [REDACTED], ExpiresAtUtc = {ExpiresAtUtc:O}, ReconciliationRequired = {ReconciliationRequired} }}";
}
