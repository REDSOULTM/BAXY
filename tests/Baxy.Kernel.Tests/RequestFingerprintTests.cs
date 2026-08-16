using System.Diagnostics;
using System.Security.Cryptography;
using System.Text.Json;
using Baxy.Contracts;
using Baxy.Kernel.Mission;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

[TestFixture]
public sealed class RequestFingerprintTests
{
    private const string AdversarialArguments =
        """{"z":-0,"a":{"é":"café 😀\n\t\"\\/<script>\u2028","numbers":[0,1.2300,1e+09,-2E-7,9007199254740993,0.00000000000000000012300],"flags":[true,false,null],"dup":1,"dup":2},"arr":[{"b":2,"a":1},[],{}],"\u0061":"escaped-name"}""";

    private static readonly string[] EquivalenceCases =
    [
        "{}",
        """{"text":"áéíóú ñ 中文 😀","escaped":"\n\t\"\\\/"}""",
        """{"numbers":[-0,0,1.2300,1e+09,-2E-7,9007199254740993,0.00000000000000000012300]}""",
        """{"nested":{"z":true,"a":[false,null,{"n":1}]},"duplicate":1,"duplicate":2}""",
        AdversarialArguments,
    ];

    [TestCaseSource(nameof(EquivalenceCases))]
    public void ArrayBufferWriterFingerprintIsExactlyEquivalentToTheLegacyImplementation(
        string argumentsJson)
    {
        OperationRequest request = CreateRequest(argumentsJson);

        string actual = RequestFingerprint.Compute(request);
        string legacy = ComputeLegacy(request);

        Assert.That(actual, Is.EqualTo(legacy));
    }

    [Test]
    public void AdversarialJsonHasAStableExactFingerprint()
    {
        OperationRequest request = CreateRequest(AdversarialArguments);

        string actual = RequestFingerprint.Compute(request);

        Assert.Multiple(() =>
        {
            Assert.That(
                actual,
                Is.EqualTo("700ff5290e02d278bf6524d030ecf5592b84860a38965bf4f9c845d954c11d8b"));
            Assert.That(actual, Is.EqualTo(ComputeLegacy(request)));
            Assert.That(actual, Has.Length.EqualTo(64));
        });
    }

    [Test]
    public void CanonicalFingerprintPreservesLegacyOrderingEscapingAndNumericLexemes()
    {
        OperationRequest first = CreateRequest(
            """{"outer":{"z":1.2300,"a":"á 😀"},"array":[{"b":2,"a":1},-0,1e+09]}""");
        OperationRequest reordered = first with
        {
            Arguments = Parse(
                """{"array":[{"a":1,"b":2},-0,1e+09],"outer":{"a":"á 😀","z":1.2300}}"""),
        };

        Assert.Multiple(() =>
        {
            Assert.That(RequestFingerprint.Compute(first), Is.EqualTo(ComputeLegacy(first)));
            Assert.That(RequestFingerprint.Compute(reordered), Is.EqualTo(ComputeLegacy(reordered)));
            Assert.That(RequestFingerprint.Compute(reordered), Is.EqualTo(RequestFingerprint.Compute(first)));
        });
    }

    private static OperationRequest CreateRequest(string argumentsJson) => new(
        ProtocolTypes.OperationRequest,
        "00000000-0000-4000-8000-000000000001",
        "11111111-1111-4111-8111-111111111111",
        "22222222-2222-4222-8222-222222222222",
        "note.create",
        Parse(argumentsJson),
        null);

    private static JsonElement Parse(string json)
    {
        using JsonDocument document = JsonDocument.Parse(json);
        return document.RootElement.Clone();
    }

    private static string ComputeLegacy(OperationRequest request)
    {
        using var stream = new MemoryStream();
        using (var writer = new Utf8JsonWriter(stream))
        {
            writer.WriteStartObject();
            writer.WriteString("missionId", request.MissionId);
            writer.WriteString("invocationId", request.InvocationId);
            writer.WriteString("operation", request.Operation);
            writer.WritePropertyName("arguments");
            WriteLegacyCanonical(request.Arguments, writer);
            writer.WriteEndObject();
        }

        return Convert.ToHexStringLower(
            SHA256.HashData(stream.GetBuffer().AsSpan(0, checked((int)stream.Length))));
    }

    private static void WriteLegacyCanonical(JsonElement element, Utf8JsonWriter writer)
    {
        switch (element.ValueKind)
        {
            case JsonValueKind.Object:
                writer.WriteStartObject();
                foreach (JsonProperty property in element.EnumerateObject()
                             .OrderBy(static property => property.Name, StringComparer.Ordinal))
                {
                    writer.WritePropertyName(property.Name);
                    WriteLegacyCanonical(property.Value, writer);
                }

                writer.WriteEndObject();
                break;
            case JsonValueKind.Array:
                writer.WriteStartArray();
                foreach (JsonElement item in element.EnumerateArray())
                {
                    WriteLegacyCanonical(item, writer);
                }

                writer.WriteEndArray();
                break;
            case JsonValueKind.String:
                writer.WriteStringValue(element.GetString());
                break;
            case JsonValueKind.Number:
                writer.WriteRawValue(element.GetRawText(), skipInputValidation: false);
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
                throw new ArgumentException(
                    "Arguments contain an unsupported JSON value.",
                    nameof(element));
        }
    }
}

[TestFixture]
public sealed class RequestFingerprintMicrobenchmarkTests
{
    private const int Iterations = 50_000;

    [Test]
    [Explicit("Microbenchmark reproducible del fingerprint; no es una compuerta temporal.")]
    public void CompareMemoryStreamAndArrayBufferWriterImplementations()
    {
        OperationRequest request = CreateBenchmarkRequest();

        _ = ComputeLegacy(request);
        _ = RequestFingerprint.Compute(request);

        Measurement legacy = Measure(() => ComputeLegacy(request));
        Measurement current = Measure(() => RequestFingerprint.Compute(request));

        TestContext.Out.WriteLine(Format("MemoryStream", legacy));
        TestContext.Out.WriteLine(Format("ArrayBufferWriter", current));

        Assert.That(current.Checksum, Is.EqualTo(legacy.Checksum));
    }

    private static Measurement Measure(Func<string> operation)
    {
        GC.Collect();
        GC.WaitForPendingFinalizers();
        GC.Collect();
        long allocationStart = GC.GetAllocatedBytesForCurrentThread();
        var stopwatch = Stopwatch.StartNew();
        int checksum = 0;
        for (int index = 0; index < Iterations; index++)
        {
            string fingerprint = operation();
            checksum = unchecked(checksum + fingerprint[0]);
        }

        stopwatch.Stop();
        return new Measurement(
            stopwatch.Elapsed,
            GC.GetAllocatedBytesForCurrentThread() - allocationStart,
            checksum);
    }

    private static OperationRequest CreateBenchmarkRequest()
    {
        string payload = new('x', 768);
        using JsonDocument document = JsonDocument.Parse(
            $$$"""{"z":-0,"text":"{{{payload}}} á 😀","nested":{"numbers":[0,1.2300,1e+09,-2E-7,9007199254740993],"items":[{"b":2,"a":1},true,false,null]}}""");
        return new OperationRequest(
            ProtocolTypes.OperationRequest,
            "00000000-0000-4000-8000-000000000001",
            "11111111-1111-4111-8111-111111111111",
            "22222222-2222-4222-8222-222222222222",
            "note.create",
            document.RootElement.Clone(),
            null);
    }

    private static string ComputeLegacy(OperationRequest request)
    {
        using var stream = new MemoryStream();
        using (var writer = new Utf8JsonWriter(stream))
        {
            writer.WriteStartObject();
            writer.WriteString("missionId", request.MissionId);
            writer.WriteString("invocationId", request.InvocationId);
            writer.WriteString("operation", request.Operation);
            writer.WritePropertyName("arguments");
            WriteLegacyCanonical(request.Arguments, writer);
            writer.WriteEndObject();
        }

        return Convert.ToHexStringLower(
            SHA256.HashData(stream.GetBuffer().AsSpan(0, checked((int)stream.Length))));
    }

    private static void WriteLegacyCanonical(JsonElement element, Utf8JsonWriter writer)
    {
        switch (element.ValueKind)
        {
            case JsonValueKind.Object:
                writer.WriteStartObject();
                foreach (JsonProperty property in element.EnumerateObject()
                             .OrderBy(static property => property.Name, StringComparer.Ordinal))
                {
                    writer.WritePropertyName(property.Name);
                    WriteLegacyCanonical(property.Value, writer);
                }

                writer.WriteEndObject();
                break;
            case JsonValueKind.Array:
                writer.WriteStartArray();
                foreach (JsonElement item in element.EnumerateArray())
                {
                    WriteLegacyCanonical(item, writer);
                }

                writer.WriteEndArray();
                break;
            case JsonValueKind.String:
                writer.WriteStringValue(element.GetString());
                break;
            case JsonValueKind.Number:
                writer.WriteRawValue(element.GetRawText(), skipInputValidation: false);
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
                throw new ArgumentException(
                    "Arguments contain an unsupported JSON value.",
                    nameof(element));
        }
    }

    private static string Format(string name, Measurement measurement) =>
        $"{name}: {measurement.Elapsed.TotalMilliseconds:F2} ms, " +
        $"{measurement.AllocatedBytes:N0} B, checksum {measurement.Checksum}";

    private readonly record struct Measurement(
        TimeSpan Elapsed,
        long AllocatedBytes,
        int Checksum);
}
