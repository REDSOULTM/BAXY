using System.Text.Json.Nodes;
using Baxy.Kernel.Policy;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// P2.43: an action the mind sends <c>unsure</c> (System One's doubt) never runs; the App says whether the kernel, in the
/// current mode, would run that exact invocation without the «sí» that normal mode asks for it (NativeTurnLoop.UnsureHeld).
/// </summary>
[TestFixture]
public sealed class UnsureActionTests
{
    private static string Outcome(string observation) =>
        JsonNode.Parse(observation)?["outcome"]?.GetValue<string>() ?? "";

    private static JsonObject Click(string label) => new() { ["label"] = label };

    [Test]
    public void InBypassAnUnsureClickThatReachesAPersonIsHeldAsOneThatWouldRunUnasked()
    {
        string held = NativeTurnLoop.UnsureHeld("input.visible.click", Click("Enviar"), ConfirmationMode.Bypass);
        Assert.Multiple(() =>
        {
            Assert.That(JsonNode.Parse(held)?["status"]?.GetValue<string>(), Is.EqualTo("held"));
            Assert.That(Outcome(held), Is.EqualTo(NativeTurnLoop.WouldRunUnasked));
        });
    }

    [Test]
    public void InBypassAnUnsureClickThatCannotBeUndoneIsHeldAsOneThatWouldRunUnasked() =>
        Assert.That(Outcome(NativeTurnLoop.UnsureHeld("input.visible.click", Click("Eliminar"),
            ConfirmationMode.Bypass)), Is.EqualTo(NativeTurnLoop.WouldRunUnasked));

    [Test]
    public void AnUnsureClickOnANeutralLabelIsHeldOnlyToBeReadAgain() =>
        Assert.That(Outcome(NativeTurnLoop.UnsureHeld("input.visible.click", Click("Siguiente"),
            ConfirmationMode.Bypass)), Is.EqualTo(NativeTurnLoop.Unsure));

    [Test]
    public void InNormalModeTheKernelAsksItselfSoNothingWouldRunUnasked() =>
        Assert.That(Outcome(NativeTurnLoop.UnsureHeld("input.visible.click", Click("Enviar"),
            ConfirmationMode.Normal)), Is.EqualTo(NativeTurnLoop.Unsure));

    // Decisión del dueño 2026-11-02 («bypass no debe pedir confirmación nunca»): in Bypass a message runs unasked too.
    [Test]
    public void InBypassAMessageWouldRunUnasked() =>
        Assert.That(Outcome(NativeTurnLoop.UnsureHeld("message.send",
            new JsonObject { ["channel"] = "whatsapp", ["to"] = "Ana", ["text"] = "hola" },
            ConfirmationMode.Bypass)), Is.EqualTo("would_run_unasked"));

    [Test]
    public void AnOperationNoCatalogHasIsReadAgainAndItsCallSaysSo() =>
        Assert.That(Outcome(NativeTurnLoop.UnsureHeld("made.up", new JsonObject(), ConfirmationMode.Bypass)),
            Is.EqualTo(NativeTurnLoop.Unsure));

    // Held-out labels, written by a subagent that did not see this change.
    [TestCase("Publicar ahora")]
    [TestCase("Responder a todos")]
    [TestCase("Comprar ya")]
    [TestCase("Pagar 24,50 €")]
    [TestCase("Vaciar papelera")]
    [TestCase("Desinstalar")]
    [TestCase("Unirse a la reunión")]
    public void HeldOutClicksNormalModeAsksForWouldRunUnaskedInBypass(string label) =>
        Assert.That(Outcome(NativeTurnLoop.UnsureHeld("input.visible.click", Click(label), ConfirmationMode.Bypass)),
            Is.EqualTo(NativeTurnLoop.WouldRunUnasked));

    [TestCase("Ver más")]
    [TestCase("Volver atrás")]
    [TestCase("Abrir menú")]
    [TestCase("Cancelar")]
    public void HeldOutHarmlessClicksAreOnlyReadAgain(string label) =>
        Assert.That(Outcome(NativeTurnLoop.UnsureHeld("input.visible.click", Click(label), ConfirmationMode.Bypass)),
            Is.EqualTo(NativeTurnLoop.Unsure));

    [Test]
    public void TheMindsUnsureFlagIsReadOnlyAsATypedTrue()
    {
        JsonObject Reply(JsonNode? unsure)
        {
            var reply = new JsonObject
            {
                ["type"] = "turn.result", ["kind"] = "action", ["operation"] = "input.visible.click",
                ["arguments"] = Click("Enviar"),
            };
            if (unsure is not null)
            {
                reply["unsure"] = unsure;
            }

            return reply;
        }

        Assert.Multiple(() =>
        {
            Assert.That(MindSidecarClient.ParseStep(Reply(true))?.Unsure, Is.True);
            Assert.That(MindSidecarClient.ParseStep(Reply(null))?.Unsure, Is.False);
            Assert.That(MindSidecarClient.ParseStep(Reply("true"))?.Unsure, Is.False);
            Assert.That(MindSidecarClient.ParseStep(Reply(false))?.Unsure, Is.False);
        });
    }
}
