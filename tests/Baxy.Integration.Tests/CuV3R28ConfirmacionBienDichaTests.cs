using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Contracts;
using Baxy.Kernel.Planning;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Ronda 28 (banco c7 t2, «no» → «no_response;retry_exhausted»): the sentence the mind says as the last resort of a
/// cancelled plan (data: cancelledFloor; tests/test_cu_v3_r28_confirmacion_bien_dicha.py, word for word) is published
/// by the App's policy over the facts the App itself writes for that cancellation, which stay as in the base (the
/// review of r28u took the act's <c>about</c> out).
/// </summary>
[TestFixture]
public sealed class CuV3R28ConfirmacionBienDichaTests
{
    private const string Recipient = "recipient_1deafb00c7314918b3fff70b4d3b9d08";

    private const string Resolved =
        """{"kind":"operation","operation":"message.recipient.resolve","polarity":"success","verified":true,"succeeded":true,"observed":{"version":1,"recipientId":"recipient_1deafb00c7314918b3fff70b4d3b9d08","channel":"discord","displayName":"Ron92","verified":true}}""";

    private const string Opened =
        """{"kind":"operation","operation":"app.open","polarity":"success","verified":true,"succeeded":true,"observed":{"application":"Discord"}}""";

    private static UserMessageDraft CancelledClick(string request)
    {
        var execution = new PendingMindPlanExecution(request,
            [new MindPlanStep("step_1", "mission.computer.use", "Cumplir exactamente el efecto solicitado.", [], "literal",
                new JsonObject { ["goal"] = "ir a canal cotele; luego ir a tienda" })]);
        execution.PendingOperation = PreparedOperation.Create("input.visible.click",
            new JsonObject { ["label"] = "Cotele!!!😎, Canal de voz, Choche", ["index"] = 60, ["window"] = 68208 });
        return new UserMessageDraft(MissionNarration.CreateCancellationMessage(execution), "status", null);
    }

    private static UserMessageDraft CancelledSend(string request, params string[] done)
    {
        var execution = new PendingMindPlanExecution(request,
            [new MindPlanStep("send", "message.send", request, [], "literal", new JsonObject { ["text"] = "hola" })]);
        execution.PendingOperation = PreparedOperation.Create("message.send",
            new JsonObject { ["recipientId"] = Recipient, ["text"] = "hola" });
        execution.CompletedMessages.AddRange(done);
        return new UserMessageDraft(MissionNarration.CreateCancellationMessage(execution), "status", null);
    }

    [Test]
    public void BancoC7_TheLastResortOfTheCancelledClickIsPublished()
    {
        const string request = "en Discord andá al canal Cotele y después en Steam andá a la tienda";

        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "No llegué a hacer clic en el botón «Cotele!!!😎, Canal de voz, Choche» porque se canceló.",
                CancelledClick(request), "no", request),
            Is.Null);
    }

    // C7Y5 (banco fp c7, evidencia_fp1/v2-c7): the click waited for its confirmation in the first sub-goal of the chain
    // «Discord → Steam»; the «no» leaves the Steam store undone, which the facts carry and the floor says.
    private static UserMessageDraft CancelledChain(string request, params (string Goal, string App)[] subgoals)
    {
        var execution = new PendingMindPlanExecution(request,
            [new MindPlanStep("step_1", "mission.computer.use", "Cumplir exactamente el efecto solicitado.", [], "literal",
                new JsonObject())]);
        execution.PendingOperation = PreparedOperation.Create("input.visible.click",
            new JsonObject { ["label"] = "Cotele!!!😎, Canal de voz, Choche", ["index"] = 60, ["window"] = 919326 });
        execution.ComputerUse = new JsonObject
        {
            ["subgoals"] = new JsonArray([.. subgoals.Select(item =>
                (JsonNode)new JsonObject { ["goal"] = item.Goal, ["application"] = item.App, ["budgetSteps"] = 10 })]),
            ["subgoal"] = 0,
        };
        return new UserMessageDraft(MissionNarration.CreateCancellationMessage(execution), "status", null);
    }

    [Test]
    public void BancoFpC7_TheCancelledChainCarriesTheStoreLeftUndoneAndItsFinalIsPublished()
    {
        const string request = "en Discord andá al canal Cotele y después en Steam andá a la tienda";
        UserMessageDraft draft = CancelledChain(request, ("ir al canal Cotele", "Discord"), ("ir a la tienda", "Steam"));
        JsonNode facts = JsonNode.Parse(draft.Source)!;

        Assert.Multiple(() =>
        {
            Assert.That(facts["cancelledGoals"]?.ToJsonString(), Is.EqualTo("""[{"goal":"ir a la tienda","application":"Steam"}]"""));
            Assert.That(
                UserMessagePolicy.ModelResponseRejectionReason(
                    "No llegué a hacer clic en el botón «Cotele!!!😎» porque se canceló y no fui a «tienda» en Steam.",
                    draft, "no", request),
                Is.Null);
            Assert.That(
                UserMessagePolicy.ModelResponseRejectionReason(
                    "I didn't click the button «Cotele!!!😎» because it was cancelled and I didn't go to «tienda» in Steam.",
                    draft, "no", request),
                Is.Null);
        });
    }

    [Test]
    public void BancoFpC7_Contracase_AOneGoalMissionAndAPlanWithoutMissionCarryNoGoalsLeft()
    {
        JsonNode single = JsonNode.Parse(CancelledChain("en Discord andá al canal Cotele", ("ir al canal Cotele", "Discord")).Source)!;
        JsonNode plain = JsonNode.Parse(CancelledClick("en Discord andá al canal Cotele").Source)!;

        Assert.Multiple(() =>
        {
            Assert.That(single["cancelledGoals"], Is.Null);
            Assert.That(plain["cancelledGoals"], Is.Null);
        });
    }

    [TestCase("No llegué a enviar el mensaje a «Ron92» porque se canceló.", false)]
    [TestCase("I didn't send the message to «Ron92» because it was cancelled.", false)]
    [TestCase("Abrí la aplicación «Discord», pero no llegué a enviar el mensaje a «Ron92» porque se canceló.", true)]
    [TestCase("I opened the app «Discord», but I didn't send the message to «Ron92» because it was cancelled.", true)]
    public void TheLastResortOfACancelledSendIsPublished(string said, bool opened)
    {
        const string request = "abrí Discord y mandale a Ron92 hola";
        UserMessageDraft draft = opened ? CancelledSend(request, Opened, Resolved) : CancelledSend(request, Resolved);

        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(said, draft, "no", request), Is.Null);
    }

    [Test]
    public void TheCancellationFactsAreTheBaseOnes_TheActAndNoProjectedObservation()
    {
        JsonNode facts = JsonNode.Parse(CancelledSend("mandale a Ron92 hola", Resolved).Source)!;

        Assert.Multiple(() =>
        {
            Assert.That((string?)facts["cause"], Is.EqualTo("remaining_steps_cancelled"));
            Assert.That((string?)facts["cancelledAction"]?["operation"], Is.EqualTo("message.send"));
            Assert.That((string?)facts["cancelledAction"]?["arguments"]?["recipientId"], Is.EqualTo(Recipient));
            Assert.That(facts["cancelledAction"]?["about"], Is.Null);
        });
    }
}
