using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace Baxy.Security.Windows;

/// <summary>
/// Seals private JSON together with the public operation identity that is allowed
/// to carry it. The same ciphertext cannot be relabeled to another operation or
/// invocation without failing authentication and the inner binding checks.
/// </summary>
public sealed class BoundProtectedJsonCodec
{
    private const int CurrentVersion = 1;
    private const int MaximumOperationNameLength = 96;
    private const string ArgumentsDomain = "memory.arguments.v1";
    private const string ResultDomain = "memory.result.v1";
    private readonly ProtectedJsonEnvelopeCodec _codec;

    public BoundProtectedJsonCodec(IProtectedPayload protector)
    {
        _codec = new ProtectedJsonEnvelopeCodec(
            protector ?? throw new ArgumentNullException(nameof(protector)));
    }

    public JsonElement SealArguments(
        string operation,
        string missionId,
        string invocationId,
        string sessionId,
        JsonObject payload)
    {
        ArgumentNullException.ThrowIfNull(payload);
        return Seal(
            ArgumentsDomain,
            operation,
            missionId,
            invocationId,
            sessionId,
            writer => payload.WriteTo(writer));
    }

    public JsonElement SealResult(
        string operation,
        string missionId,
        string invocationId,
        string sessionId,
        JsonElement payload)
    {
        if (payload.ValueKind != JsonValueKind.Object)
        {
            throw new ProtectedPayloadException(ProtectedPayloadErrorCode.InvalidPlaintext);
        }

        return Seal(
            ResultDomain,
            operation,
            missionId,
            invocationId,
            sessionId,
            payload.WriteTo);
    }

    public OpenedBoundProtectedJson OpenArguments(
        JsonElement envelope,
        string operation,
        string missionId,
        string invocationId) =>
        Open(ArgumentsDomain, envelope, operation, missionId, invocationId);

    public OpenedBoundProtectedJson OpenResult(
        JsonElement envelope,
        string operation,
        string missionId,
        string invocationId) =>
        Open(ResultDomain, envelope, operation, missionId, invocationId);

    private JsonElement Seal(
        string domain,
        string operation,
        string missionId,
        string invocationId,
        string sessionId,
        Action<Utf8JsonWriter> writePayload)
    {
        ValidateBinding(operation, missionId, invocationId, sessionId);
        string purpose = CreatePurpose(domain, operation, missionId, invocationId);
        using var stream = new MemoryStream(capacity: 1024);
        try
        {
            using (var writer = new Utf8JsonWriter(stream))
            {
                writer.WriteStartObject();
                writer.WriteNumber("version", CurrentVersion);
                writer.WriteString("operation", operation);
                writer.WriteString("missionId", missionId);
                writer.WriteString("invocationId", invocationId);
                writer.WriteString("sessionId", sessionId);
                writer.WritePropertyName("payload");
                writePayload(writer);
                writer.WriteEndObject();
            }

            ArraySegment<byte> buffer = stream.GetBuffer();
            return _codec.Seal(
                buffer.AsSpan(0, checked((int)stream.Length)),
                purpose);
        }
        catch (JsonException)
        {
            throw new ProtectedPayloadException(ProtectedPayloadErrorCode.InvalidPlaintext);
        }
        finally
        {
            CryptographicOperations.ZeroMemory(stream.GetBuffer());
        }
    }

    private OpenedBoundProtectedJson Open(
        string domain,
        JsonElement envelope,
        string operation,
        string missionId,
        string invocationId)
    {
        ValidateBinding(operation, missionId, invocationId, sessionId: null);
        string purpose = CreatePurpose(domain, operation, missionId, invocationId);
        byte[] plaintext = _codec.Open(envelope, purpose);
        JsonDocument? document = null;
        try
        {
            document = JsonDocument.Parse(
                plaintext.AsMemory(),
                new JsonDocumentOptions
                {
                    AllowTrailingCommas = false,
                    CommentHandling = JsonCommentHandling.Disallow,
                    MaxDepth = 32,
                });
            JsonElement root = document.RootElement;
            if (root.ValueKind != JsonValueKind.Object
                || !HasExactProperties(
                    root,
                    ["version", "operation", "missionId", "invocationId", "sessionId", "payload"])
                || !root.TryGetProperty("version", out JsonElement version)
                || version.ValueKind != JsonValueKind.Number
                || !version.TryGetInt32(out int versionNumber)
                || versionNumber != CurrentVersion
                || !HasExactString(root, "operation", operation)
                || !HasExactString(root, "missionId", missionId)
                || !HasExactString(root, "invocationId", invocationId)
                || !root.TryGetProperty("sessionId", out JsonElement sessionElement)
                || sessionElement.ValueKind != JsonValueKind.String
                || !IsCanonicalIdentifier(sessionElement.GetString())
                || !root.TryGetProperty("payload", out JsonElement payload)
                || payload.ValueKind != JsonValueKind.Object)
            {
                throw InvalidEnvelope();
            }

            string sessionId = sessionElement.GetString()!;
            var opened = new OpenedBoundProtectedJson(plaintext, document, sessionId);
            plaintext = null!;
            document = null;
            return opened;
        }
        catch (JsonException)
        {
            throw InvalidEnvelope();
        }
        finally
        {
            document?.Dispose();
            if (plaintext is not null)
            {
                CryptographicOperations.ZeroMemory(plaintext);
            }
        }
    }

    private static bool HasExactString(JsonElement root, string name, string expected) =>
        root.TryGetProperty(name, out JsonElement value)
        && value.ValueKind == JsonValueKind.String
        && string.Equals(value.GetString(), expected, StringComparison.Ordinal);

    private static bool HasExactProperties(JsonElement root, string[] expected)
    {
        var names = new HashSet<string>(StringComparer.Ordinal);
        foreach (JsonProperty property in root.EnumerateObject())
        {
            if (!names.Add(property.Name))
            {
                return false;
            }
        }

        return names.Count == expected.Length
            && expected.All(names.Contains);
    }

    private static string CreatePurpose(
        string domain,
        string operation,
        string missionId,
        string invocationId) =>
        string.Concat(domain, "|", operation, "|", missionId, "|", invocationId);

    private static void ValidateBinding(
        string operation,
        string missionId,
        string invocationId,
        string? sessionId)
    {
        if (!IsOperationName(operation)
            || !IsCanonicalIdentifier(missionId)
            || !IsCanonicalIdentifier(invocationId)
            || (sessionId is not null && !IsCanonicalIdentifier(sessionId)))
        {
            throw new ProtectedPayloadException(ProtectedPayloadErrorCode.InvalidPurpose);
        }
    }

    private static bool IsCanonicalIdentifier(string? value) =>
        value is not null
        && Guid.TryParseExact(value, "D", out Guid parsed)
        && parsed != Guid.Empty
        && string.Equals(value, parsed.ToString("D"), StringComparison.Ordinal);

    private static bool IsOperationName(string? value)
    {
        if (string.IsNullOrEmpty(value) || value.Length > MaximumOperationNameLength)
        {
            return false;
        }

        bool separatorSeen = false;
        bool segmentStart = true;
        foreach (char character in value)
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

    private static ProtectedPayloadException InvalidEnvelope() =>
        new(ProtectedPayloadErrorCode.InvalidEnvelope);
}

public sealed class OpenedBoundProtectedJson : IDisposable
{
    private byte[]? _plaintext;
    private JsonDocument? _document;

    internal OpenedBoundProtectedJson(
        byte[] plaintext,
        JsonDocument document,
        string sessionId)
    {
        _plaintext = plaintext;
        _document = document;
        SessionId = sessionId;
    }

    public string SessionId { get; }

    public JsonElement Payload => (_document
        ?? throw new ObjectDisposedException(nameof(OpenedBoundProtectedJson)))
        .RootElement
        .GetProperty("payload");

    public void Dispose()
    {
        _document?.Dispose();
        _document = null;
        if (_plaintext is not null)
        {
            CryptographicOperations.ZeroMemory(_plaintext);
            _plaintext = null;
        }
    }

    public override string ToString() =>
        $"{nameof(OpenedBoundProtectedJson)} {{ SessionId = {SessionId}, Payload = [REDACTED] }}";
}
