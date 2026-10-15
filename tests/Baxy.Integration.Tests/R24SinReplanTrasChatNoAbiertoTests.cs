using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Contracts;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Revisión 2 de r24, bloqueante 2: «mandale a NadieSeLlamaAsi por discord que hola» with Discord open. The resolve
/// answers «recipient_not_opened» without effect (its chat search already retried once inside the step). Before the
/// fix the plan resolve+send asked the mind for a replan (MindPlanSession, MayReplan) whose only safe suffix repeats
/// the same resolve over the person's window, up to twice more. Now the chain that hangs on that step ends at once;
/// a rest that does not hang on it, a failure that may have had an effect, or another code keep their own path.
/// Pure plan boundary: no core, no window, nothing is typed.
/// </summary>
[TestFixture]
public sealed class R24SinReplanTrasChatNoAbiertoTests
{
    private static readonly MindPlanStep Resolve = new(
        "resolve", "message.recipient.resolve", "Encuentra el chat.", [], "literal",
        new JsonObject { ["recipient"] = "NadieSeLlamaAsi", ["channel"] = "discord" });

    private static readonly MindPlanStep Send = new(
        "send", "message.send", "Envía el mensaje.", ["resolve"], "after_dependencies",
        new JsonObject { ["text"] = "hola" });

    private static OperationResponse Failed(string code, bool effect = false) =>
        new(
            ProtocolTypes.OperationResponse,
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            Guid.NewGuid().ToString("D"),
            OperationStatuses.Failed,
            "No se abrió el chat.",
            false,
            false,
            null,
            code,
            EffectMayHaveOccurred: effect);

    [Test]
    public void AChatNotOpenedWithoutEffectEndsTheSendWithoutAReplan()
    {
        var execution = new PendingMindPlanExecution("mandale a NadieSeLlamaAsi por discord que hola", [Resolve, Send]);
        OperationResponse notOpened = Failed("recipient_not_opened");
        Assert.Multiple(() =>
        {
            Assert.That(MindPlanBoundary.LeavesOnlyStepsOnAnUnopenedTarget(execution, notOpened), Is.True);
            Assert.That(MindPlanBoundary.MayReplan(execution, notOpened), Is.False);
            Assert.That(MindPlanBoundary.IndependentRemainder(execution, notOpened), Is.Null,
                "the send hangs on the resolve, so nothing else runs either");
        });
    }

    // Contracasos: the rule is the step's own target not reached, nothing else.
    [Test]
    public void OtherFailuresOfTheSameResolveKeepTheirPath()
    {
        var execution = new PendingMindPlanExecution("mandale a Ron92 por discord que hola", [Resolve, Send]);
        Assert.Multiple(() =>
        {
            // A transient failure without effect still may replan, as before the branch.
            Assert.That(MindPlanBoundary.MayReplan(execution, Failed("provider_unavailable")), Is.True);
            // A failure that may have typed near a composer never replans (unchanged).
            Assert.That(MindPlanBoundary.MayReplan(execution, Failed("recipient_identity_not_verified", effect: true)),
                Is.False);
            Assert.That(MindPlanBoundary.MayReplan(execution, Failed("recipient_not_opened", effect: true)), Is.False);
        });
    }

    [Test]
    public void ARestThatDoesNotHangOnTheUnopenedChatIsNotEndedByIt()
    {
        MindPlanStep volume = new(
            "volume", "audio.volume.set", "Sube el volumen.", [], "literal", new JsonObject { ["level"] = 50 });
        var execution = new PendingMindPlanExecution(
            "mandale a Ron92 por discord que hola y subí el volumen", [Resolve, Send, volume]);
        Assert.That(
            MindPlanBoundary.LeavesOnlyStepsOnAnUnopenedTarget(execution, Failed("recipient_not_opened")), Is.False);
    }
}
