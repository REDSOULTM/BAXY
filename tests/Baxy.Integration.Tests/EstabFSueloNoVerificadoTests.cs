using System.Security.Cryptography;
using System.Text;
using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Estabilización F (owner, 2026-10-11: «Ningún final afirma algo no verificado»). In the phase-1 runs a plan's
/// message.send left unconfirmed reached the mind as its objective alone, and the writer filled it with an act («Se le
/// envió a Ron92…», «No he enviado…», estab2 t4-c03 t2 and estab1 t3-c07 t1); a send verified by the hash of its text
/// was told with a text nobody gave (estab2 t2-c07 t1). The App now hands over the unconfirmed step's own facts and the
/// text its receipt's hash proves, and its floor (the mind's twin) says both.
/// </summary>
[TestFixture]
public sealed class EstabFSueloNoVerificadoTests
{
    private const string RecipientId = "recipient_0645b6087d344fab8f92972740aae988";

    private const string Resolved =
        """{"kind":"operation","operation":"message.recipient.resolve","polarity":"success","verified":true,"succeeded":true,"observed":{"version":1,"recipientId":"recipient_0645b6087d344fab8f92972740aae988","channel":"discord","displayName":"Ron92","verified":true}}""";

    private static PendingMindPlanExecution SendPlan(string text)
    {
        var execution = new PendingMindPlanExecution(
            "mandale a Ron92 que si se conecta a las 9 pa jugar",
            [
                new MindPlanStep("resolve", "message.recipient.resolve", "Buscar a Ron92.", [], "literal",
                    new JsonObject { ["channel"] = "discord", ["recipient"] = "Ron92" }),
                new MindPlanStep("send", "message.send", "Enviar el mensaje.", ["resolve"], "after_dependencies",
                    new JsonObject { ["recipientId"] = RecipientId, ["text"] = text }),
            ]);
        execution.CompletedMessages.Add(Resolved);
        execution.NextIndex = 1;
        return execution;
    }

    [TestCase(false, "Intenté enviar el mensaje a «Ron92»: «si se conecta a las 9 para jugar», pero no pude confirmar si se hizo.")]
    [TestCase(true, "I tried to send the message to «Ron92»: «si se conecta a las 9 para jugar», but I couldn't confirm whether it was done.")]
    public void ASendLeftUnconfirmedGoesWithItsOwnFactsAndTheFloorSaysItAsTried(bool english, string expected)
    {
        foreach (bool terminal in new[] { false, true })
        {
            var facts = (JsonObject)JsonNode.Parse(MissionNarration.CreateUncertainEffectMessage(
                SendPlan("si se conecta a las 9 para jugar"), terminal))!;
            Assert.Multiple(() =>
            {
                Assert.That((string?)facts["cause"], Is.EqualTo("result_unverified"));
                Assert.That((bool?)facts["pending"], Is.EqualTo(!terminal));
                Assert.That((string?)facts["reason"]?["operation"], Is.EqualTo("message.send"));
                Assert.That((bool?)facts["reason"]?["effectUncertain"], Is.True);
                // The identifier is never said; the name the resolve observed for it is.
                Assert.That((string?)facts["reason"]?["target"], Is.EqualTo("Ron92"));
                Assert.That((string?)facts["reason"]?["attempted"]?["text"], Is.EqualTo("si se conecta a las 9 para jugar"));
                Assert.That(facts["reason"]?["attempted"]?["recipientId"], Is.Null);
                Assert.That(OperationFloor.Final(facts, english), Is.EqualTo(expected));
            });
        }
    }

    [Test]
    public void ContracaseAPlanWithNoCurrentStepKeepsTheBareFacts()
    {
        PendingMindPlanExecution execution = SendPlan("voy");
        execution.NextIndex = 2;
        var facts = (JsonObject)JsonNode.Parse(MissionNarration.CreateUncertainEffectMessage(execution))!;
        Assert.That(facts["reason"], Is.Null);
        Assert.That(OperationFloor.Final(facts, english: false) ?? string.Empty, Is.Empty);
    }

    private static string Receipt(string sha256) =>
        new JsonObject
        {
            ["kind"] = "operation",
            ["operation"] = "message.send",
            ["polarity"] = "success",
            ["verified"] = true,
            ["succeeded"] = true,
            ["observed"] = new JsonObject
            {
                ["version"] = 1,
                ["recipientId"] = RecipientId,
                ["channel"] = "discord",
                ["displayName"] = "Ron92",
                ["contentSha256"] = sha256,
                ["delivery"] = "visible_postcondition",
            },
        }.ToJsonString();

    [Test]
    public void ASendVerifiedByTheHashOfItsTextIsToldWithThatText()
    {
        const string Text = "llego en 10 min y que lleve el cargador";
        // The hash of the measured receipt (estab2 t2-c07 t1) is that of the person's own words.
        Assert.That(Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(Text))),
            Is.EqualTo("d2feab60cbfabf2d27df2319d96861b67d421fd7e063b801fdd433f25297a249"));
        var arguments = new JsonObject { ["recipientId"] = RecipientId, ["text"] = Text };
        string sent = MindPlanBoundary.WithVerifiedContent(
            Receipt("d2feab60cbfabf2d27df2319d96861b67d421fd7e063b801fdd433f25297a249"), arguments);
        Assert.That((string?)JsonNode.Parse(sent)!["observed"]!["text"], Is.EqualTo(Text));
        var mission = (JsonObject)JsonNode.Parse(MissionNarration.CreateCompletionMessage([Resolved, sent], Text))!;
        Assert.That(OperationFloor.Final(mission, english: false),
            Is.EqualTo("Envié el mensaje a «Ron92» en Discord: dice «llego en 10 min y que lleve el cargador»."));
    }

    [Test]
    public void ContracaseATextTheHashDoesNotProveIsNeverAdded()
    {
        string receipt = Receipt("d2feab60cbfabf2d27df2319d96861b67d421fd7e063b801fdd433f25297a249");
        Assert.Multiple(() =>
        {
            Assert.That(MindPlanBoundary.WithVerifiedContent(receipt,
                new JsonObject { ["recipientId"] = RecipientId, ["text"] = "Llego en 10 min y llevo el cargador" }),
                Is.EqualTo(receipt));
            Assert.That(MindPlanBoundary.WithVerifiedContent(receipt, null), Is.EqualTo(receipt));
            Assert.That(MindPlanBoundary.WithVerifiedContent("Listo.", new JsonObject { ["text"] = "x" }),
                Is.EqualTo("Listo."));
        });
    }

    [Test]
    public void AnAppAlreadyRunningIsToldAsAlreadyOpen()
    {
        var opened = (JsonObject)JsonNode.Parse(
            """{"kind":"operation","operation":"app.open","polarity":"success","verified":true,"succeeded":true,"observed":{"appId":"Microsoft Edge","displayName":"Microsoft Edge","alreadyRunning":true}}""")!;
        Assert.That(OperationFloor.Final(opened, english: false), Is.EqualTo("La aplicación «Microsoft Edge» ya estaba abierta."));
        opened["observed"]!["alreadyRunning"] = false;
        Assert.That(OperationFloor.Final(opened, english: false), Is.EqualTo("Abrí la aplicación «Microsoft Edge»."));
    }
}
