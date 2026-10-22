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
