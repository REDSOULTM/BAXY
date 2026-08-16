using System.Buffers;
using System.Diagnostics;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Contracts;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

[TestFixture]
public sealed class AppJsonHotPathTests
{
    private static readonly string[] JsonGoldenCases =
    [
        """{"type":"turn.decide","id":"42","text":"hola"}""",
        """{"unicode":"áéíóú ñ 中文 😀","escaped":"<\/script>\n\t\"","null":null}""",
        """{"nested":{"z":true,"a":[false,null,{"n":-1.2300e+09}]},"integer":9007199254740993}""",
        """{"ty\u0070e":"hello","type":"operation.response","type":"hello"}""",
    ];

    [TestCaseSource(nameof(JsonGoldenCases))]
    public void MindRequestUtf8SerializationIsByteEquivalentToTheLegacyPath(string json)
    {
        JsonObject request = JsonNode.Parse(json)!.AsObject();
        byte[] expected = Encoding.UTF8.GetBytes(request.ToJsonString());

        byte[] actual = MindSidecarClient.SerializeRequestToUtf8(request);

        Assert.That(actual, Is.EqualTo(expected));
    }

    [TestCaseSource(nameof(JsonGoldenCases))]
    public void JsonNodeElementSerializationIsByteEquivalentToTheLegacyPath(string json)
    {
        JsonNode value = JsonNode.Parse(json)!;
        JsonElement expected = LegacySerializeToElement(value);

        JsonElement actual = DurablePlanStore.SerializeNodeToElement(value);

        Assert.That(
            Encoding.UTF8.GetBytes(actual.GetRawText()),
            Is.EqualTo(Encoding.UTF8.GetBytes(expected.GetRawText())));
    }

    [Test]
    public void JsonNodeElementSnapshotOwnsItsStorageAndIgnoresLaterMutation()
    {
        var source = new JsonObject
        {
            ["title"] = "Compras",
            ["nested"] = new JsonObject { ["count"] = 1 },
        };

        JsonElement snapshot = DurablePlanStore.SerializeNodeToElement(source);
        source["title"] = "Mutado";
        source["nested"]!["count"] = 2;

        Assert.Multiple(() =>
        {
            Assert.That(snapshot.GetProperty("title").GetString(), Is.EqualTo("Compras"));
            Assert.That(
                snapshot.GetProperty("nested").GetProperty("count").GetInt32(),
                Is.EqualTo(1));
        });
    }

    [Test]
    public void PreparedOperationSnapshotsJsonObjectBeforeTheCallerCanMutateIt()
    {
        var source = new JsonObject
        {
            ["title"] = "Compras",
            ["nested"] = new JsonObject { ["count"] = 1 },
        };
        PreparedOperation prepared = PreparedOperation.Create("note.create", source);

        source["title"] = "Mutado";
        source["nested"]!["count"] = 2;

        JsonElement snapshot = prepared.Arguments;
        Assert.Multiple(() =>
        {
            Assert.That(snapshot.GetProperty("title").GetString(), Is.EqualTo("Compras"));
            Assert.That(
                snapshot.GetProperty("nested").GetProperty("count").GetInt32(),
                Is.EqualTo(1));
            Assert.That(prepared.CreateRequest().Arguments.GetRawText(), Is.EqualTo(snapshot.GetRawText()));
        });
    }

    [Test]
    public void RestoredPreparedOperationSurvivesTheSourceDocumentLifetime()
    {
        string missionId = Guid.NewGuid().ToString("D");
        string invocationId = Guid.NewGuid().ToString("D");
        PreparedOperation restored;
        using (JsonDocument document = JsonDocument.Parse(
                   """{"title":"Compras","nested":{"count":1}}"""))
        {
            restored = PreparedOperation.Restore(
                "note.create",
                document.RootElement,
                missionId,
                invocationId);
        }

        Assert.Multiple(() =>
        {
            Assert.That(restored.Arguments.GetProperty("title").GetString(), Is.EqualTo("Compras"));
            Assert.That(restored.MissionId, Is.EqualTo(missionId));
            Assert.That(restored.InvocationId, Is.EqualTo(invocationId));
        });
    }

    [Test]
    public void PreparedIdentityRemainsByteEquivalentAndPropertyOrderIndependent()
    {
        JsonObject original = JsonNode.Parse(
            """{"title":"Árbol 😀","nested":{"z":1.2300,"a":[true,null]},"content":"línea\n2"}""")!
            .AsObject();
        JsonObject reordered = JsonNode.Parse(
            """{"content":"línea\n2","nested":{"a":[true,null],"z":1.2300},"title":"Árbol 😀"}""")!
            .AsObject();

        PreparedOperation prepared = PreparedOperation.Create("note.create", original);

        Assert.Multiple(() =>
        {
            Assert.That(
                prepared.IdentityKey,
                Is.EqualTo(LegacyPreparedIdentity("note.create", original)));
            Assert.That(
                prepared.Matches(new RoutedOperation("note.create", reordered)),
                Is.True);
        });
    }

    [Test]
    public void RequestValidationStillRejectsAnInvalidConfirmationTokenAtTheSendBoundary()
    {
        PreparedOperation prepared = PreparedOperation.Create(
            "note.create",
            new JsonObject { ["title"] = "Compras", ["content"] = "pan" });

        Assert.That(
            () => ProtocolJson.SerializeToUtf8Bytes(prepared.CreateRequest("not+base64")),
            Throws.TypeOf<JsonException>());
    }

    [Test]
    public void PreparedOperationConstructionStillFailsClosedWithTheSamePublicExceptions()
    {
        using JsonDocument array = JsonDocument.Parse("[]");
        string missionId = Guid.NewGuid().ToString("D");
        string invocationId = Guid.NewGuid().ToString("D");

        Assert.Multiple(() =>
        {
            Assert.That(
                () => PreparedOperation.Create("", new JsonObject()),
                Throws.TypeOf<ArgumentException>());
            Assert.That(
                () => PreparedOperation.Create("memory.store", new JsonObject()),
                Throws.TypeOf<InvalidOperationException>());
            Assert.That(
                () => PreparedOperation.Restore(
                    "note.create",
                    array.RootElement,
                    missionId,
                    invocationId),
                Throws.TypeOf<ArgumentException>());
            Assert.That(
                () => PreparedOperation.Restore(
                    "note.create",
                    JsonSerializer.SerializeToElement(new JsonObject()),
                    "not-a-guid",
                    invocationId),
                Throws.TypeOf<ArgumentException>());
        });
    }

    private static JsonElement LegacySerializeToElement(JsonNode value)
    {
        using JsonDocument document = JsonDocument.Parse(value.ToJsonString());
        return document.RootElement.Clone();
    }

    private static string LegacyPreparedIdentity(string operationName, JsonObject arguments)
    {
        using JsonDocument document = JsonDocument.Parse(arguments.ToJsonString());
        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            WriteLegacyCanonicalJson(writer, document.RootElement);
        }

        return operationName + "\n" + Encoding.UTF8.GetString(buffer.WrittenSpan);
    }

    private static void WriteLegacyCanonicalJson(Utf8JsonWriter writer, JsonElement value)
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
                    WriteLegacyCanonicalJson(writer, property.Value);
                }

                writer.WriteEndObject();
                break;
            case JsonValueKind.Array:
                writer.WriteStartArray();
                foreach (JsonElement item in value.EnumerateArray())
                {
                    WriteLegacyCanonicalJson(writer, item);
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
                throw new JsonException();
        }
    }
}

[TestFixture]
public sealed class AppJsonHotPathMicrobenchmarkTests
{
    private const int Iterations = 25_000;

    [Test]
    [Explicit("Microbenchmark reproducible de hot paths JSON/App; no es una compuerta temporal.")]
    public void CompareLegacyAndCurrentJsonHotPaths()
    {
        var request = new JsonObject
        {
            ["type"] = "turn.decide",
            ["id"] = "42",
            ["text"] = new string('x', 768) + " \u00E1 \U0001F600",
            ["nested"] = new JsonObject
            {
                ["items"] = new JsonArray(1, 2, 3),
                ["enabled"] = true,
            },
        };
        var observations = new JsonArray
        {
            new JsonObject
            {
                ["message"] = new string('y', 512),
                ["ok"] = true,
            },
            new JsonObject { ["n"] = 1.23e9 },
        };
        using Process currentProcess = Process.GetCurrentProcess();

        _ = Encoding.UTF8.GetBytes(request.ToJsonString());
        _ = MindSidecarClient.SerializeRequestToUtf8(request);
        _ = LegacySerializeToElement(observations);
        _ = DurablePlanStore.SerializeNodeToElement(observations);
        PreparedOperation prepared = PreparedOperation.Create("note.create", request);
        _ = RunLegacyPreparedOperation(request);
        _ = currentProcess.HasExited;

        Measurement legacyUtf8 = Measure(
            () => Encoding.UTF8.GetBytes(request.ToJsonString()).Length);
        Measurement currentUtf8 = Measure(
            () => MindSidecarClient.SerializeRequestToUtf8(request).Length);
        Measurement legacyElement = Measure(
            () => LegacySerializeToElement(observations).GetArrayLength());
        Measurement currentElement = Measure(
            () => DurablePlanStore.SerializeNodeToElement(observations).GetArrayLength());
        Measurement legacyPrepared = Measure(
            () => RunLegacyPreparedOperation(request));
        Measurement currentPrepared = Measure(
            () => PreparedOperation.Create("note.create", request).IdentityKey.Length);
        Measurement clonedPreparedArguments = Measure(
            () => prepared.Arguments.Clone()
                .GetProperty("nested")
                .GetProperty("items")
                .GetArrayLength());
        Measurement directPreparedArguments = Measure(
            () => prepared.Arguments
                .GetProperty("nested")
                .GetProperty("items")
                .GetArrayLength());
        Measurement duplicatedHasExited = Measure(
            () => (currentProcess.HasExited ? 1 : 0) + (currentProcess.HasExited ? 1 : 0));
        Measurement singleHasExited = Measure(
            () => currentProcess.HasExited ? 2 : 0);

        TestContext.Out.WriteLine(Format("mind UTF-16 + UTF-8", legacyUtf8));
        TestContext.Out.WriteLine(Format("mind UTF-8 directo", currentUtf8));
        TestContext.Out.WriteLine(Format("JsonNode string/parse/clone", legacyElement));
        TestContext.Out.WriteLine(Format("JsonNode SerializeToElement", currentElement));
        TestContext.Out.WriteLine(Format("PreparedOperation legado", legacyPrepared));
        TestContext.Out.WriteLine(Format("PreparedOperation actual", currentPrepared));
        TestContext.Out.WriteLine(Format("Arguments.Clone", clonedPreparedArguments));
        TestContext.Out.WriteLine(Format("Arguments directo", directPreparedArguments));
        TestContext.Out.WriteLine(Format("Process.HasExited duplicado", duplicatedHasExited));
        TestContext.Out.WriteLine(Format("Process.HasExited único", singleHasExited));

        Assert.Multiple(() =>
        {
            Assert.That(currentUtf8.Checksum, Is.EqualTo(legacyUtf8.Checksum));
            Assert.That(currentElement.Checksum, Is.EqualTo(legacyElement.Checksum));
            Assert.That(currentPrepared.Checksum, Is.EqualTo(legacyPrepared.Checksum));
            Assert.That(
                directPreparedArguments.Checksum,
                Is.EqualTo(clonedPreparedArguments.Checksum));
            Assert.That(singleHasExited.Checksum, Is.EqualTo(duplicatedHasExited.Checksum));
        });
    }

    private static Measurement Measure(Func<int> operation)
    {
        GC.Collect();
        GC.WaitForPendingFinalizers();
        GC.Collect();
        long allocationStart = GC.GetAllocatedBytesForCurrentThread();
        var stopwatch = Stopwatch.StartNew();
        int checksum = 0;
        for (int index = 0; index < Iterations; index++)
        {
            checksum = unchecked(checksum + operation());
        }

        stopwatch.Stop();
        return new Measurement(
            stopwatch.Elapsed,
            GC.GetAllocatedBytesForCurrentThread() - allocationStart,
            checksum);
    }

    private static JsonElement LegacySerializeToElement(JsonNode value)
    {
        using JsonDocument document = JsonDocument.Parse(value.ToJsonString());
        return document.RootElement.Clone();
    }

    private static int RunLegacyPreparedOperation(JsonObject arguments)
    {
        string argumentsJson = arguments.ToJsonString();
        using JsonDocument document = JsonDocument.Parse(argumentsJson);
        string missionId = Guid.NewGuid().ToString("D");
        string invocationId = Guid.NewGuid().ToString("D");
        JsonElement clonedArguments = document.RootElement.Clone();
        string identityKey = CreateLegacyIdentity("note.create", document.RootElement);
        var request = new OperationRequest(
            ProtocolTypes.OperationRequest,
            Guid.NewGuid().ToString("D"),
            missionId,
            invocationId,
            "note.create",
            clonedArguments,
            null);
        _ = ProtocolJson.SerializeToUtf8Bytes(request);
        return identityKey.Length;
    }

    private static string CreateLegacyIdentity(string operationName, JsonElement arguments)
    {
        var buffer = new ArrayBufferWriter<byte>();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            WriteLegacyCanonicalJson(writer, arguments);
        }

        return operationName + "\n" + Encoding.UTF8.GetString(buffer.WrittenSpan);
    }

    private static void WriteLegacyCanonicalJson(Utf8JsonWriter writer, JsonElement value)
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
                    WriteLegacyCanonicalJson(writer, property.Value);
                }

                writer.WriteEndObject();
                break;
            case JsonValueKind.Array:
                writer.WriteStartArray();
                foreach (JsonElement item in value.EnumerateArray())
                {
                    WriteLegacyCanonicalJson(writer, item);
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
                throw new JsonException();
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
