using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Encargo U1 de estabilización (banco ctl1 u1, 1 de 4 corridas): «andá a tu biblioteca» on a player read behind the
/// person's window. The rule pressed «Abre Tu biblioteca»; its post-read saw no change (1.9 s); the next look, now in
/// front, still showed the button as before (60 controls, then 62); the model saw no step and the final said «no vi en la
/// pantalla un control con el que seguir». (a) The rule's same click is taken once more in front; (b) a «none» after a
/// rule's press without effect whose control still shows says that press.
/// </summary>
public sealed partial class ComputerUseLoopTests
{
    // The player of R30 with the identities a real look carries; in front it lists one control more (ctl1: 60, then 62).
    private static JsonObject U1Player(int drawn, bool front)
    {
        JsonObject view = front ? R30Player(drawn, Control(30, "Text", "Reproduciendo")) : R30Player(drawn);
        view["window"]!["foreground"] = front;
        foreach (JsonObject control in view["controls"]!.AsArray().OfType<JsonObject>())
        {
            control["id"] = $"uia-{(int)control["i"]!}";
        }

        return view;
    }

    private async Task<(JsonObject Observed, Harness Harness)> U1Run(
        string source, bool behind, bool frontAfter, bool secondHolds)
    {
        int presses = 0;
        var harness = new Harness
        {
            Screen = _ => presses switch
            {
                0 => U1Player(0, front: !behind),
                1 => U1Player(0, front: frontAfter),
                _ => U1Player(secondHolds ? 2 : 0, front: true),
            },
            Mind = request => request.History.Count == 0
                ? new MindComputerUseStep("input.visible.click", new JsonObject { ["label"] = "Abre Tu biblioteca", ["index"] = 3 },
                    "el objetivo lo dice", Source: source)
                : Step("none", new JsonObject()),
        };
        harness.Receipt = (_, _) => ++presses == 2 && secondHolds ? R30Held() : R30Unchanged();
        var arguments = new JsonObject { ["goal"] = "ir a tu biblioteca", ["application"] = "Reproductor", ["successCheck"] = R30Library };
        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("abrí el reproductor y andá a tu biblioteca", arguments), arguments, CancellationToken.None);
        return (Observed(result), harness);
    }

    // ctl1 u1 as it should have gone: the second press, in front, opens the library; the model is never asked again.
    [Test]
    public async Task U1_ARulesPressBehindWithoutEffectIsTakenOnceMoreInFront()
    {
        (JsonObject observed, Harness harness) = await U1Run("rule", behind: true, frontAfter: true, secondHolds: true);

        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.True);
            Assert.That(harness.Acts, Has.Count.EqualTo(2));
            Assert.That(harness.Acts.Select(act => (string?)act.Arguments["label"]), Is.All.EqualTo("Abre Tu biblioteca"));
            Assert.That(harness.Requests, Has.Count.EqualTo(1), "the press again is not the model's");
            Assert.That((bool?)observed["steps"]![0]!["ok"], Is.False);
            Assert.That((bool?)observed["steps"]![1]!["ok"], Is.True);
        });
    }

    // Counter-case: the press again, in front, has no effect either. Never a third press; the stop says the press
    // (b), never «no vi un control».
    [Test]
    public async Task U1_APressWithoutEffectInFrontIsNeverTakenAgain()
    {
        (JsonObject observed, Harness harness) = await U1Run("rule", behind: true, frontAfter: true, secondHolds: false);

        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.Not.True);
            Assert.That(harness.Acts, Has.Count.EqualTo(2), "once more, no more");
            Assert.That(harness.Requests, Has.Count.EqualTo(2));
            Assert.That((string?)observed["stoppedBy"], Is.EqualTo("computer_use_click_without_effect"));
        });
    }

    // Counter-cases with no press again: the rule's press read in front (b only), the look after it still behind (b
    // only), and the model's press behind (as before: the model's «none» is its own).
    [TestCase("rule", false, true, "computer_use_click_without_effect", TestName = "U1_ARulesPressReadInFrontIsNotTakenAgain")]
    [TestCase("rule", true, false, "computer_use_click_without_effect", TestName = "U1_APressStillBehindIsNotTakenAgain")]
    [TestCase("", true, true, "computer_use_no_step_visible", TestName = "U1_TheModelsPressBehindIsNotTakenAgain")]
    public async Task U1_NoPressAgain(string source, bool behind, bool frontAfter, string stoppedBy)
    {
        (JsonObject observed, Harness harness) = await U1Run(source, behind, frontAfter, secondHolds: true);

        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.Not.True);
            Assert.That(harness.Acts, Has.Count.EqualTo(1));
            Assert.That(harness.Requests, Has.Count.EqualTo(2));
            Assert.That((string?)observed["stoppedBy"], Is.EqualTo(stoppedBy));
        });
    }

    // (b) needs the control as it was pressed: a look where it shows otherwise (renamed) keeps the stop as before.
    [Test]
    public void U1_APressWhoseControlNowShowsOtherwiseIsNoPressWithoutEffect()
    {
        var state = new JsonObject { ["clickedBefore"] = new JsonObject { ["1"] = new JsonObject { ["id"] = "uia-3", ["name"] = "Abre Tu biblioteca" } } };
        var step = new JsonObject
        {
            ["step"] = 1,
            ["operation"] = "input.visible.click",
            ["label"] = "Abre Tu biblioteca",
            ["index"] = 3,
            ["rule"] = true,
            ["ok"] = false,
            ["error"] = "visible_button_postread_unchanged",
        };
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.PressedWithoutEffect(state, step, U1Player(0, front: true)), Is.True);
            Assert.That(ComputerUseMission.PressedWithoutEffect(state, step, U1Player(2, front: true)), Is.False);
            step["error"] = "visible_label_not_found";
            Assert.That(ComputerUseMission.PressedWithoutEffect(state, step, U1Player(0, front: true)), Is.False);
        });
    }
}
