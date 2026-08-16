using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Text.Json.Serialization.Metadata;

namespace Baxy.Security.Windows;

public static class ProtectedPayloadPurposes
{
    public const string MemoryArgumentsV1 = "memory.arguments.v1";
    public const string MemoryResultV1 = "memory.result.v1";
    public const string MemoryStoreV1 = "memory.store.v1";
    public const string MemoryIntentV1 = "memory.intent.v1";
    public const string MemoryWatermarkV1 = "memory.watermark.v1";
}

/// <summary>
/// Carries an authenticated binary protected payload through a JSON-only protocol.
/// The envelope contains ciphertext and public routing metadata only.
/// </summary>
public sealed class ProtectedJsonEnvelopeCodec
{
    public const int MaximumPlaintextBytes = 256 * 1024;

    private const int CurrentVersion = 1;
    private const int MaximumCiphertextBytes = MaximumPlaintextBytes + 64;
    private const int MaximumBase64Characters = ((MaximumCiphertextBytes + 2) / 3) * 4;

    private readonly IProtectedPayload _protector;

    public ProtectedJsonEnvelopeCodec(IProtectedPayload protector)
    {
        _protector = protector ?? throw new ArgumentNullException(nameof(protector));
    }

    public JsonElement Seal(ReadOnlySpan<byte> plaintextJson, string purpose)
    {
        if (plaintextJson.IsEmpty || plaintextJson.Length > MaximumPlaintextBytes)
        {
            throw new ProtectedPayloadException(
                plaintextJson.IsEmpty
                    ? ProtectedPayloadErrorCode.InvalidPlaintext
                    : ProtectedPayloadErrorCode.PayloadTooLarge);
        }

        ValidateJson(plaintextJson, ProtectedPayloadErrorCode.InvalidPlaintext);
        byte[] ciphertext = _protector.Seal(plaintextJson, purpose);
        try
        {
            if (ciphertext.Length > MaximumCiphertextBytes)
            {
                throw new ProtectedPayloadException(ProtectedPayloadErrorCode.PayloadTooLarge);
            }

            var envelope = new ProtectedJsonEnvelope(
                CurrentVersion,
                _protector.ProtectionMode,
                purpose,
                Convert.ToBase64String(ciphertext));
            return JsonSerializer.SerializeToElement(
                envelope,
                ProtectedEnvelopeJsonContext.Default.ProtectedJsonEnvelope);
        }
        finally
        {
            CryptographicOperations.ZeroMemory(ciphertext);
        }
    }

    public JsonElement Seal<T>(T value, JsonTypeInfo<T> typeInfo, string purpose)
    {
        ArgumentNullException.ThrowIfNull(typeInfo);
        byte[] plaintext = JsonSerializer.SerializeToUtf8Bytes(value, typeInfo);
        try
        {
            return Seal(plaintext, purpose);
        }
        finally
        {
            CryptographicOperations.ZeroMemory(plaintext);
        }
    }

    public byte[] Open(JsonElement envelopeElement, string expectedPurpose)
    {
        if (envelopeElement.ValueKind != JsonValueKind.Object)
        {
            throw InvalidEnvelope();
        }

        ValidateEnvelopeShape(envelopeElement);
        ProtectedJsonEnvelope envelope;
        try
        {
            envelope = JsonSerializer.Deserialize(
                    envelopeElement,
                    ProtectedEnvelopeJsonContext.Default.ProtectedJsonEnvelope)
                ?? throw InvalidEnvelope();
        }
        catch (JsonException)
        {
            throw InvalidEnvelope();
        }

        if (envelope.Version != CurrentVersion
            || !string.Equals(
                envelope.Protection,
                _protector.ProtectionMode,
                StringComparison.Ordinal)
            || !string.Equals(envelope.Purpose, expectedPurpose, StringComparison.Ordinal)
            || string.IsNullOrEmpty(envelope.Ciphertext)
            || envelope.Ciphertext.Length > MaximumBase64Characters
            || envelope.Ciphertext.Length % 4 != 0)
        {
            throw InvalidEnvelope();
        }

        byte[] ciphertext;
        try
        {
            ciphertext = Convert.FromBase64String(envelope.Ciphertext);
        }
        catch (FormatException)
        {
            throw InvalidEnvelope();
        }

        try
        {
            if (ciphertext.Length > MaximumCiphertextBytes
                || !string.Equals(
                    Convert.ToBase64String(ciphertext),
                    envelope.Ciphertext,
                    StringComparison.Ordinal))
            {
                throw InvalidEnvelope();
            }

            byte[] plaintext = _protector.Open(ciphertext, expectedPurpose);
            try
            {
                if (plaintext.Length == 0 || plaintext.Length > MaximumPlaintextBytes)
                {
                    throw InvalidEnvelope();
                }

                ValidateJson(plaintext, ProtectedPayloadErrorCode.InvalidEnvelope);
                return plaintext;
            }
            catch
            {
                CryptographicOperations.ZeroMemory(plaintext);
                throw;
            }
        }
        finally
        {
            CryptographicOperations.ZeroMemory(ciphertext);
        }
    }

    public T Open<T>(
        JsonElement envelopeElement,
        JsonTypeInfo<T> typeInfo,
        string expectedPurpose)
    {
        ArgumentNullException.ThrowIfNull(typeInfo);
        byte[] plaintext = Open(envelopeElement, expectedPurpose);
        try
        {
            return JsonSerializer.Deserialize(plaintext, typeInfo)
                ?? throw InvalidEnvelope();
        }
        catch (JsonException)
        {
            throw InvalidEnvelope();
        }
        finally
        {
            CryptographicOperations.ZeroMemory(plaintext);
        }
    }

    private static void ValidateEnvelopeShape(JsonElement element)
    {
        var names = new HashSet<string>(StringComparer.Ordinal);
        int count = 0;
        foreach (JsonProperty property in element.EnumerateObject())
        {
            count++;
            if (!names.Add(property.Name)
                || property.Name is not ("version" or "protection" or "purpose" or "ciphertext"))
            {
                throw InvalidEnvelope();
            }
        }

        if (count != 4)
        {
            throw InvalidEnvelope();
        }
    }

    private static void ValidateJson(
        ReadOnlySpan<byte> utf8Json,
        ProtectedPayloadErrorCode errorCode)
    {
        byte[] ownedJson = utf8Json.ToArray();
        try
        {
            using JsonDocument document = JsonDocument.Parse(
                ownedJson,
                new JsonDocumentOptions
                {
                    AllowTrailingCommas = false,
                    CommentHandling = JsonCommentHandling.Disallow,
                    MaxDepth = 32,
                });
            ValidateNoDuplicateProperties(document.RootElement, depth: 0);
        }
        catch (JsonException)
        {
            throw new ProtectedPayloadException(errorCode);
        }
        finally
        {
            CryptographicOperations.ZeroMemory(ownedJson);
        }
    }

    private static void ValidateNoDuplicateProperties(JsonElement element, int depth)
    {
        if (depth > 32)
        {
            throw new JsonException("Protected JSON is too deep.");
        }

        if (element.ValueKind == JsonValueKind.Object)
        {
            var names = new HashSet<string>(StringComparer.Ordinal);
            foreach (JsonProperty property in element.EnumerateObject())
            {
                if (!names.Add(property.Name))
                {
                    throw new JsonException("Protected JSON contains duplicate properties.");
                }

                ValidateNoDuplicateProperties(property.Value, depth + 1);
            }
        }
        else if (element.ValueKind == JsonValueKind.Array)
        {
            foreach (JsonElement item in element.EnumerateArray())
            {
                ValidateNoDuplicateProperties(item, depth + 1);
            }
        }
    }

    private static ProtectedPayloadException InvalidEnvelope() =>
        new(ProtectedPayloadErrorCode.InvalidEnvelope);
}

internal sealed record ProtectedJsonEnvelope(
    [property: JsonRequired] int Version,
    [property: JsonRequired] string Protection,
    [property: JsonRequired] string Purpose,
    [property: JsonRequired] string Ciphertext);

[JsonSourceGenerationOptions(
    PropertyNamingPolicy = JsonKnownNamingPolicy.CamelCase,
    PropertyNameCaseInsensitive = false,
    UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow,
    GenerationMode = JsonSourceGenerationMode.Default)]
[JsonSerializable(typeof(ProtectedJsonEnvelope))]
internal sealed partial class ProtectedEnvelopeJsonContext : JsonSerializerContext;
