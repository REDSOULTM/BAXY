using System.Diagnostics.CodeAnalysis;
using System.Text;
using System.Text.Json;

namespace Baxy.Contracts;

public static class ContractValidator
{
    private const int MaximumConfirmationTokenLength = 128;
    private const int MaximumOperationNameLength = 96;
    private const int MaximumTextLength = 4096;

    public static void Validate(ProtocolHello value)
    {
        ArgumentNullException.ThrowIfNull(value);

        RequireType(value.Type, ProtocolTypes.Hello);
        RequireEqual(value.Protocol, ProtocolVersion.Current, "protocol");
        RequireText(value.CoreVersion, "coreVersion");

        if (value.Pid <= 0)
        {
            ThrowInvalid("pid must be a positive process identifier");
        }

        if (value.Capabilities is null || value.Capabilities.Count == 0)
        {
            ThrowInvalid("capabilities must contain at least one operation descriptor");
        }

        var names = new HashSet<string>(StringComparer.Ordinal);
        foreach (var capability in value.Capabilities)
        {
            Validate(capability);
            if (!names.Add(capability.Name))
            {
                ThrowInvalid($"capabilities contains duplicate operation '{capability.Name}'");
            }
        }

        if (value.ApplicationCatalog is not null)
        {
            Validate(value.ApplicationCatalog);
        }

        if (value.GameCatalog is not null)
        {
            Validate(value.GameCatalog);
        }
    }

    public static void Validate(ApplicationCatalogSnapshot value)
    {
        ArgumentNullException.ThrowIfNull(value);

        if (value.Version != ApplicationCatalogContract.CurrentVersion)
        {
            ThrowInvalid(
                $"applicationCatalog.version must be {ApplicationCatalogContract.CurrentVersion}");
        }

        if (value.Names is null)
        {
            ThrowInvalid("applicationCatalog.names must be an array");
        }

        if (!value.Verified && (value.Complete || value.Names.Count != 0))
        {
            ThrowInvalid(
                "an unverified applicationCatalog must be incomplete and contain no names");
        }

        if (value.Names.Count > ApplicationCatalogContract.MaximumNames)
        {
            ThrowInvalid(
                $"applicationCatalog.names cannot exceed {ApplicationCatalogContract.MaximumNames} entries");
        }

        int totalUtf8Bytes = 0;
        int totalEscapedUtf8Bytes = 0;
        var normalizedNames = new HashSet<string>(StringComparer.Ordinal);
        foreach (string? name in value.Names)
        {
            if (string.IsNullOrWhiteSpace(name)
                || name.Any(static character =>
                    character == '\uFFFD'
                    || char.IsControl(character)
                    || char.IsWhiteSpace(character) && character != ' '))
            {
                ThrowInvalid("applicationCatalog contains an invalid application name");
            }

            if (name.Length > ApplicationCatalogContract.MaximumNameUtf8Bytes)
            {
                ThrowInvalid("applicationCatalog contains an oversized application name");
            }

            int utf8Bytes = Encoding.UTF8.GetByteCount(name);
            if (utf8Bytes > ApplicationCatalogContract.MaximumNameUtf8Bytes)
            {
                ThrowInvalid("applicationCatalog contains an oversized application name");
            }

            totalUtf8Bytes += utf8Bytes;
            totalEscapedUtf8Bytes += JsonEncodedText.Encode(name).EncodedUtf8Bytes.Length;
            if (totalUtf8Bytes > ApplicationCatalogContract.MaximumTotalNameUtf8Bytes
                || totalEscapedUtf8Bytes
                    > ApplicationCatalogContract.MaximumEscapedNamesUtf8Bytes)
            {
                ThrowInvalid("applicationCatalog exceeds its byte budget");
            }

            string normalizedName;
            try
            {
                normalizedName = ApplicationCatalogContract.NormalizeName(name);
            }
            catch (ArgumentException)
            {
                ThrowInvalid("applicationCatalog contains invalid Unicode");
                return;
            }

            if (normalizedName.Length == 0 || !normalizedNames.Add(normalizedName))
            {
                ThrowInvalid("applicationCatalog contains an ambiguous or duplicate name");
            }
        }
    }

    public static void Validate(GameCatalogSnapshot value)
    {
        ArgumentNullException.ThrowIfNull(value);

        if (value.Version != GameCatalogContract.CurrentVersion)
        {
            ThrowInvalid(
                $"gameCatalog.version must be {GameCatalogContract.CurrentVersion}");
        }

        if (value.Entries is null)
        {
            ThrowInvalid("gameCatalog.entries must be an array");
        }

        if (!value.Verified && (value.Complete || value.Entries.Count != 0))
        {
            ThrowInvalid(
                "an unverified gameCatalog must be incomplete and contain no entries");
        }

        if (value.Entries.Count > GameCatalogContract.MaximumEntries)
        {
            ThrowInvalid(
                $"gameCatalog.entries cannot exceed {GameCatalogContract.MaximumEntries} entries");
        }

        int totalUtf8Bytes = 0;
        var identities = new HashSet<string>(StringComparer.Ordinal);
        var providerNames = new HashSet<string>(StringComparer.Ordinal);
        foreach (GameCatalogEntry? entry in value.Entries)
        {
            if (entry is null || entry.Provider is not ("steam" or "epic"))
            {
                ThrowInvalid("gameCatalog contains an invalid provider");
            }

            if (string.IsNullOrWhiteSpace(entry.AppId)
                || entry.AppId.Length > GameCatalogContract.MaximumAppIdLength
                || entry.AppId.Any(static character =>
                    !char.IsAsciiLetterOrDigit(character)
                    && character is not ('.' or '_' or '-')))
            {
                ThrowInvalid("gameCatalog contains an invalid appId");
            }

            if (string.IsNullOrWhiteSpace(entry.Name)
                || entry.Name.Any(static character =>
                    character == '\uFFFD'
                    || char.IsControl(character)
                    || char.IsWhiteSpace(character) && character != ' '))
            {
                ThrowInvalid("gameCatalog contains an invalid game name");
            }

            int nameBytes = Encoding.UTF8.GetByteCount(entry.Name);
            if (nameBytes > GameCatalogContract.MaximumNameUtf8Bytes)
            {
                ThrowInvalid("gameCatalog contains an oversized game name");
            }

            totalUtf8Bytes += nameBytes
                + Encoding.UTF8.GetByteCount(entry.Provider)
                + Encoding.UTF8.GetByteCount(entry.AppId);
            if (totalUtf8Bytes > GameCatalogContract.MaximumTotalUtf8Bytes)
            {
                ThrowInvalid("gameCatalog exceeds its byte budget");
            }

            string normalizedName;
            try
            {
                normalizedName = GameCatalogContract.NormalizeName(entry.Name);
            }
            catch (ArgumentException)
            {
                ThrowInvalid("gameCatalog contains invalid Unicode");
                return;
            }

            if (normalizedName.Length == 0
                || !identities.Add(entry.Provider + "\n" + entry.AppId)
                || !providerNames.Add(entry.Provider + "\n" + normalizedName))
            {
                ThrowInvalid("gameCatalog contains an ambiguous or duplicate entry");
            }
        }
    }

    public static void Validate(OperationDescriptor value)
    {
        ArgumentNullException.ThrowIfNull(value);

        RequireOperationName(value.Name);
        if (!OperationRisks.IsKnown(value.Risk))
        {
            ThrowInvalid("risk is unknown");
        }

        RequireClosedArgumentsSchema(value.ArgumentsSchema);
        RequireVerifierContractId(value.VerifierContractId);
        RequireText(value.Description, "description");
    }

    public static void Validate(OperationRequest value)
    {
        ArgumentNullException.ThrowIfNull(value);

        RequireType(value.Type, ProtocolTypes.OperationRequest);
        RequireIdentifier(value.RequestId, "requestId");
        RequireIdentifier(value.MissionId, "missionId");
        RequireIdentifier(value.InvocationId, "invocationId");
        RequireOperationName(value.Operation);

        if (value.Arguments.ValueKind != JsonValueKind.Object)
        {
            ThrowInvalid("arguments must be a JSON object");
        }

        if (value.ConfirmationToken is not null)
        {
            RequireConfirmationToken(value.ConfirmationToken);
        }
    }

    public static void Validate(OperationResponse value)
    {
        ArgumentNullException.ThrowIfNull(value);

        RequireType(value.Type, ProtocolTypes.OperationResponse);
        RequireIdentifier(value.RequestId, "requestId");
        RequireIdentifier(value.MissionId, "missionId");
        RequireIdentifier(value.InvocationId, "invocationId");

        if (!OperationStatuses.IsKnown(value.Status))
        {
            ThrowInvalid("status is unknown");
        }

        RequireText(value.Message, "message");
        if (value.Result is { ValueKind: JsonValueKind.Undefined })
        {
            ThrowInvalid("result cannot be undefined");
        }

        if (value.ErrorCode is not null)
        {
            RequireErrorCode(value.ErrorCode);
        }

        if (value.Status == OperationStatuses.Completed)
        {
            if (!value.Verified || value.ErrorCode is not null)
            {
                ThrowInvalid("completed responses must be verified and cannot contain errorCode");
            }
        }
        else if (value.Verified || value.ErrorCode is null)
        {
            ThrowInvalid("pending, failed, and rejected responses must be unverified and contain errorCode");
        }

        if (value.Status == OperationStatuses.Pending && value.Replayed)
        {
            ThrowInvalid("pending responses cannot be replayed");
        }
    }

    public static void Validate(ProtocolError value)
    {
        ArgumentNullException.ThrowIfNull(value);

        RequireType(value.Type, ProtocolTypes.ProtocolError);
        RequireErrorCode(value.ErrorCode);
        RequireText(value.Message, "message");
    }

    public static bool IsCanonicalIdentifier(string? value)
    {
        if (value is null || !Guid.TryParseExact(value, "D", out var parsed) || parsed == Guid.Empty)
        {
            return false;
        }

        return string.Equals(value, parsed.ToString("D"), StringComparison.Ordinal);
    }

    public static bool IsOperationName(string? value)
    {
        if (string.IsNullOrEmpty(value) || value.Length > MaximumOperationNameLength)
        {
            return false;
        }

        var segmentStart = true;
        var separatorSeen = false;

        foreach (var character in value)
        {
            if (character == '.')
            {
                if (segmentStart)
                {
                    return false;
                }

                separatorSeen = true;
                segmentStart = true;
                continue;
            }

            if (segmentStart)
            {
                if (character is < 'a' or > 'z')
                {
                    return false;
                }

                segmentStart = false;
                continue;
            }

            if (character is not (>= 'a' and <= 'z') and not (>= '0' and <= '9'))
            {
                return false;
            }
        }

        return separatorSeen && !segmentStart;
    }

    private static void RequireIdentifier(string? value, string fieldName)
    {
        if (!IsCanonicalIdentifier(value))
        {
            ThrowInvalid($"{fieldName} must be a non-empty canonical UUID");
        }
    }

    private static void RequireOperationName(string? value)
    {
        if (!IsOperationName(value))
        {
            ThrowInvalid("operation name must contain lowercase dot-separated ASCII segments");
        }
    }

    private static void RequireType(string? value, string expected)
    {
        if (!string.Equals(value, expected, StringComparison.Ordinal))
        {
            ThrowInvalid($"unknown message type; expected '{expected}'");
        }
    }

    private static void RequireEqual(string? value, string expected, string fieldName)
    {
        if (!string.Equals(value, expected, StringComparison.Ordinal))
        {
            ThrowInvalid($"{fieldName} must be '{expected}'");
        }
    }

    private static void RequireText(string? value, string fieldName)
    {
        if (string.IsNullOrWhiteSpace(value) || value.Length > MaximumTextLength)
        {
            ThrowInvalid($"{fieldName} must be non-empty and at most {MaximumTextLength} characters");
        }
    }

    private static void RequireErrorCode(string? value)
    {
        if (string.IsNullOrEmpty(value) || value.Length > 96)
        {
            ThrowInvalid("errorCode must be non-empty and at most 96 characters");
        }

        foreach (char character in value)
        {
            if (character is not (>= 'a' and <= 'z')
                and not (>= '0' and <= '9')
                and not '_'
                and not '.')
            {
                ThrowInvalid("errorCode must use lowercase ASCII, digits, underscore, or dot");
            }
        }
    }

    private static void RequireClosedArgumentsSchema(JsonElement schema)
    {
        if (schema.ValueKind != JsonValueKind.Object)
        {
            ThrowInvalid("argumentsSchema must be an object");
        }

        var topLevelNames = new HashSet<string>(StringComparer.Ordinal);
        foreach (JsonProperty property in schema.EnumerateObject())
        {
            if (!topLevelNames.Add(property.Name)
                || property.Name is not ("type" or "properties" or "required" or "additionalProperties"))
            {
                ThrowInvalid("argumentsSchema must use the closed canonical object shape");
            }
        }

        JsonElement type = default;
        JsonElement properties = default;
        JsonElement required = default;
        JsonElement additional = default;
        if (topLevelNames.Count != 4
            || !schema.TryGetProperty("type", out type)
            || type.ValueKind != JsonValueKind.String
            || !string.Equals(type.GetString(), "object", StringComparison.Ordinal)
            || !schema.TryGetProperty("properties", out properties)
            || properties.ValueKind != JsonValueKind.Object
            || !schema.TryGetProperty("required", out required)
            || required.ValueKind != JsonValueKind.Array
            || !schema.TryGetProperty("additionalProperties", out additional)
            || additional.ValueKind is not (JsonValueKind.True or JsonValueKind.False)
            || additional.GetBoolean())
        {
            ThrowInvalid("argumentsSchema must be a closed object schema");
        }

        var propertyNames = new HashSet<string>(StringComparer.Ordinal);
        foreach (JsonProperty property in properties.EnumerateObject())
        {
            if (!propertyNames.Add(property.Name) || property.Value.ValueKind != JsonValueKind.Object)
            {
                ThrowInvalid("argumentsSchema properties must be unique named objects");
            }
        }

        var requiredNames = new HashSet<string>(StringComparer.Ordinal);
        foreach (JsonElement requiredName in required.EnumerateArray())
        {
            if (requiredName.ValueKind != JsonValueKind.String
                || string.IsNullOrEmpty(requiredName.GetString())
                || !requiredNames.Add(requiredName.GetString()!)
                || !propertyNames.Contains(requiredName.GetString()!))
            {
                ThrowInvalid("argumentsSchema required entries must name unique properties");
            }
        }
    }

    private static void RequireVerifierContractId(string? value)
    {
        if (string.IsNullOrEmpty(value) || value.Length > 128)
        {
            ThrowInvalid("verifierContractId must be a canonical dotted identifier");
        }

        bool segmentStart = true;
        foreach (char character in value)
        {
            if (character == '.')
            {
                if (segmentStart)
                {
                    ThrowInvalid("verifierContractId must be a canonical dotted identifier");
                }

                segmentStart = true;
            }
            else if (segmentStart)
            {
                if (character is < 'a' or > 'z')
                {
                    ThrowInvalid("verifierContractId must be a canonical dotted identifier");
                }

                segmentStart = false;
            }
            else if (character is not (>= 'a' and <= 'z')
                and not (>= '0' and <= '9'))
            {
                ThrowInvalid("verifierContractId must be a canonical dotted identifier");
            }
        }

        if (segmentStart)
        {
            ThrowInvalid("verifierContractId must be a canonical dotted identifier");
        }
    }

    private static void RequireConfirmationToken(string value)
    {
        if (value.Length == 0 || value.Length > MaximumConfirmationTokenLength)
        {
            ThrowInvalid(
                $"confirmationToken must be non-empty and at most {MaximumConfirmationTokenLength} characters");
        }

        foreach (char character in value)
        {
            if (character is not (>= 'A' and <= 'Z')
                and not (>= 'a' and <= 'z')
                and not (>= '0' and <= '9')
                and not '-'
                and not '_')
            {
                ThrowInvalid("confirmationToken must be canonical unpadded base64url");
            }
        }

        int remainder = value.Length % 4;
        if (remainder == 1)
        {
            ThrowInvalid("confirmationToken must be canonical unpadded base64url");
        }

        if (remainder == 2 && (Base64UrlValue(value[^1]) & 0x0F) != 0
            || remainder == 3 && (Base64UrlValue(value[^1]) & 0x03) != 0)
        {
            ThrowInvalid("confirmationToken must be canonical unpadded base64url");
        }
    }

    private static int Base64UrlValue(char character) => character switch
    {
        >= 'A' and <= 'Z' => character - 'A',
        >= 'a' and <= 'z' => character - 'a' + 26,
        >= '0' and <= '9' => character - '0' + 52,
        '-' => 62,
        '_' => 63,
        _ => -1,
    };

    [DoesNotReturn]
    private static void ThrowInvalid(string message) =>
        throw new JsonException($"Invalid BAXY protocol message: {message}.");
}
