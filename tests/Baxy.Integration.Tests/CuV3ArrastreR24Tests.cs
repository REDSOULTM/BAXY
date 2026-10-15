using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Ronda 24, pasada r23 t-drag-1: the confirmation of an act in a folder («¿Quieres confirmar que … en la carpeta …?»)
/// was vetoed as a machine slot ask («?» plus «la carpeta»), every recomposition too, and the person read
/// «⚠ (internal_code;retry_exhausted)». A confirmation names the place its pending act goes to and never asks for one;
/// a confirmation no draft could word is said from its pending act (data: confirmationFloor). Contracases: a
/// clarification asking for a folder is still vetoed, a confirmation leaking «app id» too, and a failed conversation
/// keeps its marker (owner's M75). Estabilización L: the drag of the pass is a declared limit now (no act drags), so
/// the pending act is a confirmed click in the same folder.
/// </summary>
[TestFixture]
public sealed class CuV3ArrastreR24Tests
{
    private const string Request = "en la carpeta baxy-prueba-v3 hacé clic en Eliminar";

    // The shape of the draft of v2-t-drag-1, turn 1, that the App refused: a confirmation that names its folder.
    private const string Draft =
        "¿Quieres confirmar que haga clic en Eliminar en la carpeta baxy-prueba-v3 o cancelar esta acción?";

    private static string ConfirmationFacts() =>
        TurnVisibleFacts.Confirmation(
            "step needs confirmation",
            ["confirmar", "cancelar"],
            new JsonObject
            {
                ["pendingRequest"] = Request,
                ["pendingAction"] = new JsonObject
                {
                    ["operation"] = "input.visible.click",
                    ["purpose"] = "Cumplir exactamente el efecto solicitado.",
                    ["arguments"] = new JsonObject
                    {
                        ["index"] = 36,
                        ["label"] = "Eliminar",
                    },
                },
                ["step"] = 1,
            });

    [Test]
    public void TDrag1_TheConfirmationOfAnActInAFolderIsNotAMachineSlotAsk()
    {
        var draft = new UserMessageDraft(ConfirmationFacts(), "confirmation", null);

        Assert.That(UserMessagePolicy.ModelResponseRejectionReason(Draft, draft, Request), Is.Null);
    }

    [Test]
    public void Contracase_AClarificationAskingForAFolderIsStillVetoed()
    {
        var draft = new UserMessageDraft(TurnVisibleFacts.Event("clarification", "missing_folder"), "clarification", null);

        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason("¿En qué carpeta lo guardo? Dime la carpeta que quieres.", draft, "guardalo"),
            Is.EqualTo("internal_code"));
    }

    [Test]
    public void Contracase_AConfirmationLeakingAnAppIdIsStillVetoed()
    {
        var draft = new UserMessageDraft(ConfirmationFacts(), "confirmation", null);

        Assert.That(
            UserMessagePolicy.ModelResponseRejectionReason(
                "¿Confirmas que haga clic en Eliminar? ¿Cuál es el app id de la carpeta?", draft, Request),
            Is.Not.Null);
    }

    [TestCase(false, "Antes de hacer clic en el botón «Eliminar», necesito que me lo confirmes: ¿confirmar o cancelar?")]
    [TestCase(true, "Before I click the button «Eliminar», I need you to confirm it: confirm or cancel?")]
    public void TDrag1_AConfirmationNoDraftCouldWordIsSaidFromItsPendingAct(bool english, string said)
    {
        var pending = new PendingModelMessage(
            new UserMessageDraft(ConfirmationFacts(), "confirmation", null),
            english ? "in the baxy-prueba-v3 folder click Delete" : Request,
            new JsonObject(),
            "t1");

        string line = MainWindowViewModel.CompositionFailureFallback(pending, "internal_code;retry_exhausted");

        Assert.Multiple(() =>
        {
            Assert.That(line, Is.EqualTo(said));
            Assert.That(line, Does.Not.Contain("internal_code").And.Not.Contain("⚠"));
        });
    }

    [Test]
    public void AConfirmationWithNoKnownActStillAsksWithoutACode()
    {
        var pending = new PendingModelMessage(
            new UserMessageDraft(TurnVisibleFacts.Confirmation("step needs confirmation", ["confirmar", "cancelar"]),
                "confirmation", null),
            Request,
            new JsonObject(),
            "t1");

        Assert.That(
            MainWindowViewModel.CompositionFailureFallback(pending, "retry_exhausted"),
            Is.EqualTo("Antes de seguir con el paso que viene, necesito que me lo confirmes: ¿confirmar o cancelar?"));
    }

    [Test]
    public void Contracase_AFailedConversationKeepsTheMarker()
    {
        var pending = new PendingModelMessage(
            new UserMessageDraft("{}", "conversation", null), "¿qué me recomendás para cenar?", new JsonObject(), "t0");

        Assert.That(MainWindowViewModel.CompositionFailureFallback(pending, "internal_code;retry_exhausted"),
            Is.EqualTo("⚠ (internal_code;retry_exhausted)"));
    }
}
