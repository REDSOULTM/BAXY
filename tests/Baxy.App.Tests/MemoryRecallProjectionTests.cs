using System.Text.Json;
using System.Text.Json.Nodes;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// Al máximo 11.2: an exact recall that matched nothing comes back with what is remembered, said as no exact match
/// (MemoryHandlers' exactMatch); the model reads it beside the records, never the records alone as the one it named.
/// </summary>
[TestFixture]
public sealed class MemoryRecallProjectionTests
{
    [Test]
    public void AnExactRecallThatMatchedNothingIsSaidAsSo()
    {
        Assert.That(MemoryOperationResponseProjection.TryCreateCompleted("memory.recall",
            Recall(exactMatch: false), out MemoryOperationResponseProjection? projection), Is.True);
        JsonObject observed = JsonNode.Parse(projection!.Message)!["observed"]!.AsObject();
        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["exactMatch"], Is.False);
            Assert.That((string?)observed["records"]![0]!["value"], Is.EqualTo("pizza"));
        });
    }

    [Test]
    public void ARecallThatNamesNothingSaysNothingOfAMatch()
    {
        Assert.That(MemoryOperationResponseProjection.TryCreateCompleted("memory.recall",
            Recall(exactMatch: null), out MemoryOperationResponseProjection? projection), Is.True);
        Assert.That(JsonNode.Parse(projection!.Message)!["observed"]!.AsObject().ContainsKey("exactMatch"), Is.False);
    }

    // Al máximo 8.2: a memory result says how it was verified as every other completed call does (a read is output
    // only; the same datum already kept is unchanged), never «completado y verificado» for a datum already there.
    [Test]
    public void AMemoryResultSaysHowItWasVerified()
    {
        Assert.That(MemoryOperationResponseProjection.TryCreateCompleted("memory.recall",
            Recall(exactMatch: true), out MemoryOperationResponseProjection? recall), Is.True);
        JsonElement saved = JsonDocument.Parse("{\"version\":1,\"recordId\":\"" + Guid.NewGuid().ToString("D")
            + "\",\"revision\":1,\"selector\":\"COMIDA FAVORITA\",\"replayed\":false,\"changed\":false}").RootElement.Clone();
        Assert.That(MemoryOperationResponseProjection.TryCreateCompleted("memory.save", saved,
            out MemoryOperationResponseProjection? save), Is.True);
        Assert.Multiple(() =>
        {
            Assert.That((string?)JsonNode.Parse(recall!.Message)!["verification"], Is.EqualTo("output_only"));
            Assert.That((string?)JsonNode.Parse(save!.Message)!["verification"], Is.EqualTo("unchanged"));
        });
    }

    // Renew al máximo (w8): a memory.correct said the new value back («remembered») whatever the record was, so correcting
    // a sensitive record put its value in clear in what the model reads and in the step's trace. A record the handler
    // marks sensitive, or a value that looks like a secret, is never said back.
    [TestCase(true, "Calle Falsa 123")]
    [TestCase(false, "sk-live_abcdefghijklmnop1234")]
    public void ACorrectOfASensitiveRecordOrToASecretNeverSaysTheValue(bool sensitiveRecord, string value)
    {
        string wire = "{\"version\":1,\"recordId\":\"" + Guid.NewGuid().ToString("D")
            + "\",\"revision\":2,\"selector\":\"MI DIRECCION\",\"replayed\":false,\"changed\":true"
            + (sensitiveRecord ? ",\"sensitive\":true}" : "}");
        JsonElement arguments = JsonDocument.Parse(new JsonObject
        {
            ["version"] = 1, ["selector"] = "mi direccion", ["value"] = value, ["retention"] = "persistent",
        }.ToJsonString()).RootElement.Clone();

        Assert.That(MemoryOperationResponseProjection.TryCreateCompleted("memory.correct",
            JsonDocument.Parse(wire).RootElement.Clone(), out MemoryOperationResponseProjection? projection,
            privateArguments: arguments), Is.True);
        Assert.Multiple(() =>
        {
            Assert.That(projection!.Message, Does.Not.Contain(value));
            Assert.That(JsonNode.Parse(projection.Message)!["observed"]!.AsObject().ContainsKey("remembered"), Is.False);
        });
    }

    [Test]
    public void ACorrectOfAPlainRecordStillSaysTheValue()
    {
        string wire = "{\"version\":1,\"recordId\":\"" + Guid.NewGuid().ToString("D")
            + "\",\"revision\":2,\"selector\":\"COMIDA FAVORITA\",\"replayed\":false,\"changed\":true}";
        JsonElement arguments = JsonDocument.Parse(
            "{\"version\":1,\"selector\":\"comida favorita\",\"value\":\"sushi\",\"retention\":\"persistent\"}")
            .RootElement.Clone();

        Assert.That(MemoryOperationResponseProjection.TryCreateCompleted("memory.correct",
            JsonDocument.Parse(wire).RootElement.Clone(), out MemoryOperationResponseProjection? projection,
            privateArguments: arguments), Is.True);
        Assert.That((string?)JsonNode.Parse(projection!.Message)!["observed"]!["remembered"], Is.EqualTo("sushi"));
    }

    // Renew al máximo (w8): memory.correct skipped the secret check memory.save has, so a plain record corrected to a
    // password was kept as plain (shown in clear by recall, list and the export). It is refused before anything is
    // sealed, with what to call instead.
    [Test]
    public void ACorrectToAValueThatLooksLikeASecretIsRefusedBeforeItIsSealed()
    {
        var protector = new MemoryOperationProtector(
            new Baxy.Security.Windows.BoundProtectedJsonCodec(new UnusedPayload()), Guid.NewGuid().ToString("D"));
        var call = new MemoryRoutedOperation("memory.correct", new JsonObject
        {
            ["version"] = 1, ["selector"] = "wifi", ["value"] = "la contraseña es Hunter2", ["retention"] = "persistent",
        });

        MemoryRequestRefusedException refused = Assert.Throws<MemoryRequestRefusedException>(() => protector.Prepare(call))!;
        Assert.Multiple(() =>
        {
            Assert.That(refused.Code, Is.EqualTo("memory_value_needs_sensitive_channel"));
            Assert.That(refused.Message, Does.Contain("memory_sensitive_save"));
            Assert.That(refused.Message, Does.Not.Contain("Hunter2"));
        });
    }

    private sealed class UnusedPayload : Baxy.Security.Windows.IProtectedPayload
    {
        public string ProtectionMode => "test";

        public byte[] Seal(ReadOnlySpan<byte> plaintext, string purpose) => throw new InvalidOperationException("sealed");

        public byte[] Open(ReadOnlySpan<byte> envelope, string purpose) => throw new InvalidOperationException("opened");
    }

    private static JsonElement Recall(bool? exactMatch)
    {
        const string at = "2026-10-22T10:00:00+00:00";
        var payload = new JsonObject
        {
            ["version"] = 1,
            ["records"] = new JsonArray(new JsonObject
            {
                ["recordId"] = Guid.NewGuid().ToString("D"),
                ["revision"] = 1,
                ["selector"] = "COMIDA FAVORITA",
                ["label"] = "comida favorita",
                ["value"] = "pizza",
                ["kind"] = "fact",
                ["origin"] = "explicit",
                ["sensitivity"] = "normal",
                ["retention"] = "persistent",
                ["tags"] = new JsonArray(),
                ["createdAtUtc"] = at,
                ["updatedAtUtc"] = at,
                ["expiresAtUtc"] = null,
                ["sourceMissionId"] = null,
                ["capturedAtUtc"] = at,
                ["sessionId"] = null,
            }),
            ["count"] = 1,
            ["totalCount"] = 1,
            ["offset"] = 0,
            ["limit"] = 20,
        };
        if (exactMatch is bool exact)
        {
            payload["exactMatch"] = exact;
        }

        return JsonDocument.Parse(payload.ToJsonString()).RootElement.Clone();
    }
}
