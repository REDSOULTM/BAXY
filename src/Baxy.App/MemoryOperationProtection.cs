using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;
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

        // The operation is the one the model chose: arguments that do not fit it are refused, never re-routed.
        JsonElement payload = JsonSerializer.SerializeToElement(privateArguments);
        string operation = privateOperation.Name;
        ValidateWireRiskBinding(operation, payload);
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
                throw new InvalidDataException("La operacion privada pertenece a una sesion anterior.");
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

    private static void ValidateWireRiskBinding(string operation, JsonElement payload)
    {
        if (payload.ValueKind != JsonValueKind.Object)
        {
            throw new MemoryRequestRefusedException("memory_arguments_shape", "The arguments are not an object.");
        }

        switch (operation)
        {
            case "memory.enable":
                if (!RequiredBoolean(payload, "enabled"))
                {
                    throw new MemoryRequestRefusedException("memory_enable_needs_enabled_true",
                        "memory_enable turns memory on (enabled true); to turn it off use memory_disable.");
                }

                break;
            case "memory.disable":
                if (RequiredBoolean(payload, "enabled"))
                {
                    throw new MemoryRequestRefusedException("memory_disable_needs_enabled_false",
                        "memory_disable turns memory off (enabled false); to turn it on use memory_enable.");
                }

                break;
            case "memory.save":
                {
                    if (RequiredString(payload, "sensitivity") is not ("normal" or "personal"))
                    {
                        throw new MemoryRequestRefusedException("memory_sensitive_value_needs_sensitive_save",
                            "memory_save keeps normal or personal values; a sensitive or secret one is saved with "
                            + "memory_sensitive_save.");
                    }

                    if (payload.TryGetProperty("value", out JsonElement value)
                        && value.ValueKind == JsonValueKind.String
                        && SensitiveText.Contains(value.GetString()!))
                    {
                        throw new MemoryValueNeedsSensitiveChannelException();
                    }

                    break;
                }
            // Renew al máximo (w8): a correct skipped the secret check, so a normal record corrected to a password was
            // kept as normal and shown in clear by recall, list and the export. A value that looks like a secret is
            // corrected only by forgetting the record and saving it with memory_sensitive_save.
            case "memory.correct":
                if (payload.TryGetProperty("value", out JsonElement corrected)
                    && corrected.ValueKind == JsonValueKind.String
                    && SensitiveText.Contains(corrected.GetString()!))
                {
                    throw new MemoryRequestRefusedException("memory_value_needs_sensitive_channel",
                        "This value looks like a secret and memory_correct keeps it as the record already is: forget "
                        + "the record with memory_forget, then save the value with memory_sensitive_save.");
                }

                break;
            case "memory.sensitive.save":
                if (RequiredString(payload, "sensitivity") is not ("sensitive" or "secret"))
                {
                    throw new MemoryRequestRefusedException("memory_plain_value_needs_save",
                        "memory_sensitive_save keeps sensitive or secret values; a normal or personal one is saved with "
                        + "memory_save.");
                }

                break;
            case "memory.forget":
                if (RequiredString(payload, "scope") == "session"
                    || !RequiredBoolean(payload, "confirmationRequired"))
                {
                    throw new MemoryRequestRefusedException("memory_forget_scope_invalid",
                        "memory_forget forgets saved memories by scope all, exact, kind or topic; what this session "
                        + "remembers is cleared with memory_session_clear.");
                }

                break;
            case "memory.session.clear":
                if (RequiredString(payload, "scope") != "session"
                    || RequiredBoolean(payload, "confirmationRequired")
                    || !RequiredBoolean(payload, "mustNotDeletePersistent")
                    || !payload.TryGetProperty("selector", out JsonElement selector)
                    || selector.ValueKind != JsonValueKind.Null)
                {
                    throw new MemoryRequestRefusedException("memory_session_clear_scope_invalid",
                        "memory_session_clear clears only this session (scope session, no selector) and never what is "
                        + "saved; saved memories are forgotten with memory_forget.");
                }

                break;
        }
    }

    private static string RequiredString(JsonElement arguments, string name)
    {
        if (arguments.TryGetProperty(name, out JsonElement value)
            && value.ValueKind == JsonValueKind.String
            && !string.IsNullOrWhiteSpace(value.GetString()))
        {
            return value.GetString()!;
        }

        throw new MemoryRequestRefusedException("memory_argument_missing", $"The argument {name} must be non-empty text.");
    }

    private static bool RequiredBoolean(JsonElement arguments, string name)
    {
        if (arguments.TryGetProperty(name, out JsonElement value)
            && value.ValueKind is JsonValueKind.True or JsonValueKind.False)
        {
            return value.GetBoolean();
        }

        throw new MemoryRequestRefusedException("memory_argument_missing", $"The argument {name} must be true or false.");
    }

    private static void EnsureNoReservedPayloadProperties(JsonObject arguments)
    {
        if (arguments.ContainsKey("operation")
            || arguments.ContainsKey("missionId")
            || arguments.ContainsKey("invocationId")
            || arguments.ContainsKey("sessionId")
            || arguments.ContainsKey("payload"))
        {
            throw new MemoryRequestRefusedException("memory_arguments_reserved",
                "Arguments may not carry operation, missionId, invocationId, sessionId or payload.");
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

/// <summary>
/// A memory call whose arguments do not fit the operation's risk or shape, with a closed code the model reads so it
/// knows what to change (audit 2026-10-15, App 5: every such refusal came back as a bare «arguments_invalid»).
/// </summary>
internal sealed class MemoryRequestRefusedException(string code, string message) : Exception(message)
{
    internal string Code { get; } = code;
}

/// <summary>
/// memory.save was given a value that looks like a secret (<see cref="SensitiveText"/>): it is kept only through the
/// sensitive channel, so the call is refused with that reason instead of «arguments invalid».
/// </summary>
internal sealed class MemoryValueNeedsSensitiveChannelException : Exception
{
    internal MemoryValueNeedsSensitiveChannelException()
        : base("La memoria requiere el canal sensible.")
    {
    }
}
