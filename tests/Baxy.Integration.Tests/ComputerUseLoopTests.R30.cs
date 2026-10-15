using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Ronda 30 (banco Br28, u1 e y8): «andá a tu biblioteca» on a player whose library is a panel that unfolds. The act
/// and the window's repaint race: the arrival is judged on a window already drawn. What proves the arrival does not
/// change, nor what verifies a press; only when the window is looked at.
/// </summary>
public sealed partial class ComputerUseLoopTests
{
    private const string R30Library = "control:tu biblioteca:current|title:tu biblioteca|page:tu biblioteca|mark:tu biblioteca";

    // The player on its home page. drawn 0: the panel folded; 1: the panel listed and its button not yet renamed (the
    // look of y8 176 ms after the click); 2: the panel unfolded.
    private static JsonObject R30Player(int drawn, params JsonObject[] extra)
    {
        JsonArray controls =
        [
            Control(0, "Button", "Inicio"), Control(1, "Button", "Buscar"), Control(2, "ComboBox", "¿Qué quieres reproducir?", value: ""),
            Control(3, "Button", drawn < 2 ? "Abre Tu biblioteca" : "Comprimir Tu biblioteca"), Control(4, "Button", "Reproducir"),
            Control(5, "Button", "Siguiente"), Control(6, "Button", "Anterior"), Control(7, "Hyperlink", "Mix diario 1"),
            Control(8, "Hyperlink", "Mix diario 2"), Control(9, "Hyperlink", "Descubrimiento semanal"),
        ];
        if (drawn >= 1)
        {
            controls.Add(Control(10, "Text", "Tu biblioteca"));
            controls.Add(Control(11, "DataGrid", "Tu biblioteca"));
        }

        if (drawn >= 2)
        {
            controls.Add(Control(12, "Button", "Buscar en Tu biblioteca"));
        }

        foreach (JsonObject control in extra)
        {
            controls.Add(control);
        }

        return Window("Reproductor", "player", 9, true, controls);
    }

    // The mission over a screen told by how many looks came after the press; the model presses the panel's button and,
    // asked again, sees no step.
    private async Task<(JsonObject Observed, Harness Harness)> R30Run(Func<int, JsonObject> afterThePress, JsonObject receipt)
    {
        bool pressed = false;
        int looksAfter = 0;
        var harness = new Harness
        {
            Screen = _ => pressed ? afterThePress(++looksAfter) : R30Player(0),
            Mind = request => request.History.Count == 0
                ? Step("input.visible.click", new JsonObject { ["label"] = "Abre Tu biblioteca" })
                : Step("none", new JsonObject()),
        };
        harness.Receipt = (_, _) =>
        {
            pressed = true;
            return (JsonObject)receipt.DeepClone();
        };
        var arguments = new JsonObject { ["goal"] = "ir a tu biblioteca", ["application"] = "Reproductor", ["successCheck"] = R30Library };
        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("abrí el reproductor y andá a tu biblioteca", arguments), arguments, CancellationToken.None);
        return (Observed(result), harness);
    }

    private static JsonObject R30Held() => new() { ["surfaceChanged"] = true, ["name"] = "Abre Tu biblioteca", ["kind"] = "Button" };

    private static JsonObject R30Unchanged() => new() { ["failWith"] = "visible_button_postread_unchanged", ["effectUncertain"] = true };

    // y8: the press held and the first look came before the repaint. One look more, Settle later, and the arrival is
    // read there: one step, the model never asked for another. Counter-case in the same run: a window drawn at the
    // first look is not looked at again.
    [TestCase(1, 3, 2, TestName = "R30_AnArrivalStillBeingDrawnIsLookedAtOnceMoreBeforeAnotherStep")]
    [TestCase(0, 2, 1, TestName = "R30_AnArrivalDrawnAtTheFirstLookCostsNoLookMore")]
    public async Task R30_TheArrivalIsJudgedOnTheWindowDrawn(int looksHalfDrawn, int looks, int settles)
    {
        (JsonObject observed, Harness harness) = await R30Run(look => R30Player(look > looksHalfDrawn ? 2 : 1), R30Held());

        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.True);
            Assert.That((string?)observed["satisfiedBy"], Is.EqualTo("page:tu biblioteca"));
            Assert.That(harness.Acts, Has.Count.EqualTo(1), "one step");
            Assert.That(harness.Requests, Has.Count.EqualTo(1), "no other step was asked for");
            Assert.That(harness.Looks, Has.Count.EqualTo(looks));
            Assert.That(harness.Delays.Count(delay => delay == ComputerUseMission.Settle), Is.EqualTo(settles));
        });
    }

    // A window that never stops changing (a clock, a counter) and never shows the place: that one look more and no
    // other, then the loop decides as before. Nothing passes for the arrival.
    [Test]
    public async Task R30_AWindowThatNeverStopsChangingGetsOneLookMoreAndNoMore()
    {
        (JsonObject observed, Harness harness) = await R30Run(
            look => R30Player(1, Control(20, "Text", $"0:{look:00}")), R30Held());

        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.Not.True);
            Assert.That(harness.Looks, Has.Count.EqualTo(3), "the first look, the look after the press and one more");
            Assert.That(harness.Delays.Count(delay => delay == ComputerUseMission.Settle), Is.EqualTo(2));
            Assert.That(harness.Requests, Has.Count.EqualTo(2), "then the model is asked");
        });
    }

    // The press that did nothing (post-read unchanged, the look as before): failed as before, with no look and no wait
    // more than before, and never an arrival. So is a press after which the window lists something else than what it
    // pressed.
    [TestCase(false, TestName = "R30_APressThatChangedNothingStaysFailedWithNoLookMore")]
    [TestCase(true, TestName = "R30_APressAfterWhichSomethingElseAppearedStaysFailed")]
    public async Task R30_APressWhosePostReadSawNoChangeStaysFailed(bool somethingElse)
    {
        (JsonObject observed, Harness harness) = await R30Run(
            _ => somethingElse ? R30Player(0, Control(20, "Text", "Sin conexión")) : R30Player(0), R30Unchanged());

        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.Not.True);
            Assert.That((bool?)observed["steps"]![0]!["ok"], Is.False);
            Assert.That((string?)observed["steps"]![0]!["error"], Is.EqualTo("visible_button_postread_unchanged"));
            Assert.That(harness.Looks, Has.Count.EqualTo(2), "the first look and the look after the press");
            Assert.That(harness.Delays.Count(delay => delay == ComputerUseMission.Settle), Is.EqualTo(1), "the one wait every act has");
        });
    }

    // Review of r30: a press whose post-read saw no change is never verified by what the next look lists, whatever it
    // names. The three scenes of the review, none of which closes, each with the two looks it had before.
    private async Task<(JsonObject Observed, Harness Harness)> R30Unheld(
        Func<bool, JsonObject> screen, string label, string goal, string application, string check)
    {
        bool pressed = false;
        var harness = new Harness
        {
            Screen = _ => screen(pressed),
            Mind = request => request.History.Count == 0
                ? Step("input.visible.click", new JsonObject { ["label"] = label })
                : Step("none", new JsonObject()),
        };
        harness.Receipt = (_, _) =>
        {
            pressed = true;
            return R30Unchanged();
        };
        var arguments = new JsonObject { ["goal"] = goal, ["application"] = application, ["successCheck"] = check };
        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution(goal, arguments), arguments, CancellationToken.None);
        return (Observed(result), harness);
    }

    private static void R30NeverClosed(JsonObject observed, Harness harness) => Assert.Multiple(() =>
    {
        Assert.That((bool?)observed["reached"], Is.Not.True);
        Assert.That((string?)observed["satisfiedBy"], Is.Null.Or.Empty);
        Assert.That((bool?)observed["steps"]![0]!["ok"], Is.False);
        Assert.That((string?)observed["steps"]![0]!["error"], Is.EqualTo("visible_button_postread_unchanged"));
        Assert.That(observed["steps"]![0]!["verifiedBy"], Is.Null);
        Assert.That((string?)observed["stoppedBy"], Is.Not.EqualTo("computer_use_already_there_unconfirmed"));
        Assert.That(harness.Looks, Has.Count.EqualTo(2), "the first look and the look after the press");
        Assert.That(harness.Delays, Is.EqualTo(new[] { ComputerUseMission.Settle }), "the one wait every act has");
    });

    // 1: «Reproducir» pressed without effect and the window says it could not, naming what was pressed. The step is
    // not done: «stepDone» never holds on it.
    [Test]
    public async Task R30_AnErrorThatNamesWhatWasPressedNeverMakesThePressDone()
    {
        (JsonObject observed, Harness harness) = await R30Unheld(
            pressed => pressed ? Player(Control(20, "Text", "No se puede reproducir esta canción")) : Player(),
            "Reproducir", "hacer clic en reproducir", "Reproductor", "stepDone:input.visible.click:reproducir");

        R30NeverClosed(observed, harness);
    }

    // 2: «Tu biblioteca» pressed without effect and the window says it could not load it. Neither an arrival nor
    // «parece que ya estabas», and no look more.
    [Test]
    public async Task R30_AnErrorThatNamesThePlaceIsNeitherAnArrivalNorAlreadyThere()
    {
        (JsonObject observed, Harness harness) = await R30Unheld(
            pressed => pressed ? Player(Control(20, "Text", "No se pudo cargar Tu biblioteca")) : Player(),
            "Tu biblioteca", "ir a tu biblioteca", "Reproductor", R30Library);

        R30NeverClosed(observed, harness);
    }

    // 3: a launcher with an accessible tree on its store; the press on «Biblioteca» whose post-read saw no change only
    // unfolds a menu, one of whose entries carries the name («Biblioteca familiar»). Never the library.
    [Test]
    public async Task R30_AMenuWithAnEntryNamedAsThePlaceIsNoArrivalAfterAPressThatDidNotHold()
    {
        static JsonObject Launcher(bool menu)
        {
            JsonArray controls =
            [
                Control(0, "Button", "Tienda"), Control(1, "Button", "Biblioteca"), Control(2, "Button", "Comunidad"),
                Control(3, "Edit", "Buscar en la tienda", value: ""), Control(4, "Hyperlink", "Novedades"),
                Control(5, "Hyperlink", "Ofertas"), Control(6, "Button", "Perfil"),
            ];
            if (menu)
            {
                foreach ((int index, string name) in new[]
                    { (10, "Inicio"), (11, "Colecciones"), (12, "Descargas"), (13, "Biblioteca familiar"), (14, "Actualizaciones") })
                {
                    controls.Add(Control(index, "MenuItem", name));
                }
            }

            return Window("Lanzador", "launcher", 14, true, controls);
        }

        (JsonObject observed, Harness harness) = await R30Unheld(
            Launcher, "Biblioteca", "ir a biblioteca", "Lanzador",
            "control:biblioteca:current|title:biblioteca|page:biblioteca|mark:biblioteca");

        R30NeverClosed(observed, harness);
    }
}
