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
