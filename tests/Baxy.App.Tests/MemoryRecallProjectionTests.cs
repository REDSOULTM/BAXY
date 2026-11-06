using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Contracts;
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

    // Renew al máximo (w8): a value kept with a line break (the store allows it) is read back, never the whole page
    // result_unreadable.
    [Test]
    public void ARecalledValueWithALineBreakIsRead()
    {
        JsonObject payload = JsonNode.Parse(Recall(exactMatch: true).GetRawText())!.AsObject();
        payload["records"]![0]!["value"] = "pizza\ncon piña";

        Assert.That(MemoryOperationResponseProjection.TryCreateCompleted("memory.recall",
            JsonDocument.Parse(payload.ToJsonString()).RootElement.Clone(), out MemoryOperationResponseProjection? projection),
            Is.True);
        Assert.That((string?)JsonNode.Parse(projection!.Message)!["observed"]!["records"]![0]!["value"],
            Is.EqualTo("pizza\ncon piña"));
    }

    // Renew al máximo (w9): recall and list showed the name of a sensitive record beside «[REDACTED]» («mi clave del
    // banco»). A listing only counts it; an exact recall that named it may say its name, never its value.
    [TestCase("memory.list", null)]
    [TestCase("memory.recall", null)]
    [TestCase("memory.recall", false)]
    public void AListingCountsASensitiveRecordWithoutNamingIt(string operation, bool? exactMatch)
    {
        JsonObject payload = TwoRecords(exactMatch);

        Assert.That(MemoryOperationResponseProjection.TryCreateCompleted(operation,
            JsonDocument.Parse(payload.ToJsonString()).RootElement.Clone(), out MemoryOperationResponseProjection? projection),
            Is.True);
        JsonObject observed = JsonNode.Parse(projection!.Message)!["observed"]!.AsObject();
        Assert.Multiple(() =>
        {
            Assert.That(projection.Message, Does.Not.Contain("clave del banco"));
            Assert.That((int?)observed["sensitiveNotNamed"], Is.EqualTo(1));
            Assert.That((int?)observed["shown"], Is.EqualTo(1));
            Assert.That((string?)observed["records"]![0]!["label"], Is.EqualTo("comida favorita"));
        });
    }

    [Test]
    public void AListingOfOnlySensitiveRecordsCountsThem()
    {
        JsonObject payload = TwoRecords(exactMatch: null);
        payload["records"]!.AsArray().RemoveAt(0);
        payload["count"] = 1;
        payload["totalCount"] = 1;

        Assert.That(MemoryOperationResponseProjection.TryCreateCompleted("memory.list",
            JsonDocument.Parse(payload.ToJsonString()).RootElement.Clone(), out MemoryOperationResponseProjection? projection),
            Is.True);
        JsonNode message = JsonNode.Parse(projection!.Message)!;
        Assert.Multiple(() =>
        {
            Assert.That((string?)message["cause"], Is.EqualTo("memory_records"));
            Assert.That((int?)message["observed"]!["sensitiveNotNamed"], Is.EqualTo(1));
            Assert.That(projection.Message, Does.Not.Contain("clave del banco"));
        });
    }

    [Test]
    public void AnExactRecallOfASensitiveRecordNamesItButNotItsValue()
    {
        JsonObject payload = TwoRecords(exactMatch: true);
        payload["records"]!.AsArray().RemoveAt(0);
        payload["count"] = 1;
        payload["totalCount"] = 1;

        Assert.That(MemoryOperationResponseProjection.TryCreateCompleted("memory.recall",
            JsonDocument.Parse(payload.ToJsonString()).RootElement.Clone(), out MemoryOperationResponseProjection? projection),
            Is.True);
        JsonObject observed = JsonNode.Parse(projection!.Message)!["observed"]!.AsObject();
        Assert.Multiple(() =>
        {
            Assert.That((string?)observed["records"]![0]!["label"], Is.EqualTo("clave del banco"));
            Assert.That((string?)observed["records"]![0]!["value"], Is.EqualTo("[REDACTED]"));
            Assert.That(projection.Message, Does.Not.Contain("4417"));
            Assert.That(observed.ContainsKey("sensitiveNotNamed"), Is.False);
        });
    }

    private static JsonObject TwoRecords(bool? exactMatch)
    {
        JsonObject payload = JsonNode.Parse(Recall(exactMatch).GetRawText())!.AsObject();
        JsonObject sensitive = payload["records"]![0]!.DeepClone().AsObject();
        sensitive["recordId"] = Guid.NewGuid().ToString("D");
        sensitive["selector"] = "CLAVE DEL BANCO";
        sensitive["label"] = "clave del banco";
        sensitive["value"] = "4417";
        sensitive["sensitivity"] = "secret";
        payload["records"]!.AsArray().Add(sensitive);
        payload["count"] = 2;
        payload["totalCount"] = 2;
        return payload;
    }

    // Uso 83 (banco diag-946e, F13 6 of 6): memory.save failed with memory_disabled and BAXY said only «la memoria está
    // apagada», never offering to turn it on; memory.list said «no tengo nada guardado» of a memory it did not read. The
    // result leads with the call that asks the person to turn it on (memory.enable waits for their «sí», RiskPolicy) and
    // says the same call goes again after it.
    [TestCase("memory.save", "memory_save")]
    [TestCase("memory.sensitive.save", "memory_sensitive_save")]
    [TestCase("memory.correct", "memory_correct")]
    [TestCase("memory.recall", "memory_recall")]
    [TestCase("memory.list", "memory_list")]
    public void AFailureBecauseMemoryIsOffLeadsWithTheCallThatAsksToTurnItOn(string operation, string wire)
    {
        JsonObject facts = JsonNode.Parse(MemoryOperationResponseProjection.Failed(operation, Failure("memory_disabled")))!
            .AsObject();
        Assert.Multiple(() =>
        {
            Assert.That((string?)facts["status"], Is.EqualTo("failed"));
            Assert.That((string?)facts["error"], Is.EqualTo("memory_disabled"));
            Assert.That((string?)facts["next"], Does.StartWith("memory_enable {} "));
            Assert.That((string?)facts["next"], Does.Contain(wire + " again with the same arguments"));
        });
    }

    [TestCase("memory.save", "memory_not_found")]
    [TestCase("memory.forget", "memory_disabled")]
    public void AnotherFailureSaysOnlyWhatTheEngineSaid(string operation, string error)
    {
        OperationResponse response = Failure(error);
        Assert.That(MemoryOperationResponseProjection.Failed(operation, response), Is.EqualTo(response.Message));
    }

    // Encargo 82 (vivo del 81): a memory.save of a name the store already keeps failed with memory_conflict and nothing
    // else, and the model asked «¿hay otra regla guardada…?». The result says what is kept and the call that corrects it.
    [Test]
    public void ASaveThatConflictsSaysWhatIsKeptAndTheCallThatCorrectsIt()
    {
        JsonObject facts = Conflict(value: "lunes", keptValue: "pizza");

        Assert.Multiple(() =>
        {
            Assert.That((string?)facts["error"], Is.EqualTo("memory_conflict"));
            Assert.That((string?)facts["kept"]!["selector"], Is.EqualTo("comida favorita"));
            Assert.That((string?)facts["kept"]!["value"], Is.EqualTo("pizza"));
            Assert.That((string?)facts["next"], Does.Contain(
                """memory_correct {"selector":"comida favorita","value":"lunes","retention":"persistent"}"""));
            Assert.That((string?)facts["next"], Does.StartWith("nothing was saved"));
        });
    }

    [Test]
    public void ASaveOfTheValueAlreadyKeptOffersNoCorrection()
    {
        JsonObject facts = Conflict(value: "pizza", keptValue: "pizza");

        Assert.Multiple(() =>
        {
            Assert.That((string?)facts["kept"]!["value"], Is.EqualTo("pizza"));
            Assert.That((string?)facts["next"], Does.Not.Contain("memory_correct"));
            Assert.That((string?)facts["next"], Does.Contain("same value"));
        });
    }

    [TestCase("sensitive", "pizza")]
    [TestCase("secret", "pizza")]
    [TestCase("normal", "contraseña: Abc123!xyz")]
    public void AKeptValueThatIsSensitiveIsNeverSaid(string sensitivity, string keptValue)
    {
        JsonObject facts = Conflict(value: "lunes", keptValue: keptValue, sensitivity: sensitivity);

        Assert.Multiple(() =>
        {
            Assert.That(facts["kept"]!["value"], Is.Null);
            Assert.That((bool?)facts["kept"]!["sensitive"], Is.True);
            Assert.That(facts.ToJsonString(), Does.Not.Contain(keptValue));
            Assert.That((string?)facts["next"], Does.Contain("memory_correct"));
        });
    }

    // The value of a save is any scalar (memory.save's schema): a number is a value too.
    [Test]
    public void ASaveOfANumberThatConflictsIsToldLikeAnyOther()
    {
        using JsonDocument saved = JsonDocument.Parse("""{"selector":"comida favorita","value":41,"retention":"persistent"}""");
        using JsonDocument kept = JsonDocument.Parse(Recall(exactMatch: true).GetRawText());

        JsonObject facts = JsonNode.Parse(MemoryOperationResponseProjection.Conflict(
            "{\"status\":\"failed\",\"error\":\"memory_conflict\"}", saved.RootElement, kept.RootElement))!.AsObject();

        Assert.That((string?)facts["next"], Does.Contain("\"value\":\"41\""));
    }

    [Test]
    public void AConflictWithNothingToSayStaysAsTheEngineSaidIt()
    {
        const string Failed = "{\"status\":\"failed\",\"error\":\"memory_conflict\"}";
        using JsonDocument saved = JsonDocument.Parse("""{"selector":"comida favorita","value":"lunes","retention":"persistent"}""");
        using JsonDocument none = JsonDocument.Parse("""{"version":1,"records":[],"count":0,"totalCount":0,"offset":0,"limit":20}""");

        Assert.That(MemoryOperationResponseProjection.Conflict(Failed, saved.RootElement, none.RootElement), Is.EqualTo(Failed));
    }

    // Encargo 92 (banco diag-b1e7, F13 turno 3): «olvídalo» of a datum never saved (memory off) came back as
    // memory_forget_empty alone, and 2 of 6 answers said «la memoria sigue con ese dato» or «Borré… pero no quedó
    // nada». The result says what the store said: nothing matched, nothing was deleted, nothing changed.
    [TestCase("exact", "apodo", "keeps no saved memory that matches it")]
    [TestCase("all", null, "keeps no saved memories")]
    public void AForgetThatMatchedNothingSaysNothingWasKeptAndNothingChanged(string scope, string? selector, string kept)
    {
        using JsonDocument payload = JsonDocument.Parse("""{"version":1,"deletedCount":0,"replayed":false}""");
        using JsonDocument arguments = JsonDocument.Parse(new JsonObject
        {
            ["version"] = 1,
            ["scope"] = scope,
            ["selector"] = selector,
        }.ToJsonString());

        Assert.That(MemoryOperationResponseProjection.TryCreateCompleted("memory.forget", payload.RootElement,
            out MemoryOperationResponseProjection? projection, privateArguments: arguments.RootElement), Is.True);
        JsonObject facts = JsonNode.Parse(projection!.Message)!.AsObject();
        Assert.Multiple(() =>
        {
            Assert.That((string?)facts["status"], Is.EqualTo("failed"));
            Assert.That((string?)facts["error"], Is.EqualTo("memory_forget_empty"));
            Assert.That((int?)facts["deletedCount"], Is.EqualTo(0));
            Assert.That((bool?)facts["changed"], Is.False);
            Assert.That((string?)facts["next"], Does.StartWith("nothing was deleted: BAXY " + kept));
            Assert.That((string?)facts["next"], Does.EndWith("nothing changed"));
        });
    }

    [Test]
    public void AForgetThatDeletedSaysHowManyAsBefore()
    {
        using JsonDocument payload = JsonDocument.Parse("""{"version":1,"deletedCount":1,"replayed":false}""");

        Assert.That(MemoryOperationResponseProjection.TryCreateCompleted("memory.forget", payload.RootElement,
            out MemoryOperationResponseProjection? projection), Is.True);
        JsonObject facts = JsonNode.Parse(projection!.Message)!.AsObject();
        Assert.Multiple(() =>
        {
            Assert.That((string?)facts["status"], Is.EqualTo("completed"));
            Assert.That((string?)facts["cause"], Is.EqualTo("memory_deleted"));
            Assert.That((int?)facts["observed"]!["deletedCount"], Is.EqualTo(1));
            Assert.That(facts.ContainsKey("next"), Is.False);
        });
    }

    private static JsonObject Conflict(string value, string keptValue, string sensitivity = "normal")
    {
        JsonObject recalled = JsonNode.Parse(Recall(exactMatch: true).GetRawText())!.AsObject();
        recalled["records"]![0]!["value"] = keptValue;
        recalled["records"]![0]!["sensitivity"] = sensitivity;
        using JsonDocument saved = JsonDocument.Parse(new JsonObject
        {
            ["selector"] = "comida favorita",
            ["value"] = value,
            ["retention"] = "persistent",
        }.ToJsonString());
        using JsonDocument kept = JsonDocument.Parse(recalled.ToJsonString());
        return JsonNode.Parse(MemoryOperationResponseProjection.Conflict(
            "{\"status\":\"failed\",\"error\":\"memory_conflict\"}", saved.RootElement, kept.RootElement))!.AsObject();
    }

    private static OperationResponse Failure(string error) =>
        new(ProtocolTypes.OperationResponse, Guid.NewGuid().ToString("D"), Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"), OperationStatuses.Failed, "{\"status\":\"failed\",\"error\":\"" + error + "\"}",
            Verified: false, Replayed: false, Result: null, ErrorCode: error);

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
