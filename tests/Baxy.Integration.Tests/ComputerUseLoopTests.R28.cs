using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Ronda 28, revisión 1: the loop over the two real turns of the tanda c27u2. An arrival is closed by the state the
/// view reads, never by how the model words its citation; and an option chosen closes its sub-goal through the plan's
/// own check.
/// </summary>
public sealed partial class ComputerUseLoopTests
{
    private const string R28ScreenCheck =
        "control:pantalla:current|title:pantalla|page:pantalla|control:display:current|title:display|page:display|mark:pantalla|mark:display";

    // t2-c03 t1, model call 45: Settings on Personalización > Pantalla de bloqueo.
    private static JsonObject R28LockScreen() => Window("Configuración", "SystemSettings", 40, true,
    [
        Control(4, "Edit", "Cuadro de búsqueda, Buscar una opción"),
        Control(8, "ListItem", "Sistema"),
        Control(11, "ListItem", "Personalización", "selected"),
        Control(19, "Button", "Personalización"),
        Control(20, "Button", "Pantalla de bloqueo"),
        Control(24, "ListItem", "Contenido destacado de Windows", "selected"),
        Control(35, "Text", "Pantalla de bloqueo"),
        Control(36, "Text", "Vista previa de la pantalla de bloqueo"),
    ]);

    private async Task<JsonObject> R28Run(Harness harness, string goal, string? check)
    {
        var arguments = new JsonObject { ["goal"] = goal, ["application"] = "Configuración", ["successCheck"] = check };
        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution(goal, arguments), arguments, CancellationToken.None);
        return Observed(result);
    }

    // Bloqueante 2: after the first citation is refused the model cites again. No pair of citations closes the lock
    // screen as «Pantalla» (before: «Pantalla» and «Pantalla | Personalización» gave reached=true model_evidence).
    [TestCase("Pantalla de bloqueo", "Pantalla")]
    [TestCase("Pantalla de bloqueo", "Pantalla | Personalización")]
    [TestCase("Pantalla", "Sistema | Pantalla")]
    [TestCase("Pantalla | Personalización", "Pantalla de bloqueo | Pantalla")]
    [TestCase("Pantalla de bloqueo", "Pantalla de bloqueo")]
    public async Task R28_T2_C03_NoCitationClosesTheLockScreenAsTheScreenPage(string first, string second)
    {
        int cited = 0;
        var harness = new Harness
        {
            Screen = _ => R28LockScreen(),
            Mind = request => request.History.Count == 0
                ? Step("input.visible.click", new JsonObject { ["label"] = "Pantalla de bloqueo" })
                : Step("done", new JsonObject { ["evidence"] = cited++ == 0 ? first : second }),
        };

        JsonObject observed = await R28Run(harness, "ir a pantalla", R28ScreenCheck);

        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.Not.True);
            Assert.That((string?)observed["satisfiedBy"], Is.Not.EqualTo("model_evidence"));
            Assert.That((string?)observed["stoppedBy"], Is.Not.Null.And.Not.Empty);
        });
    }

    // Bloqueante 1 / t4-c04 t3: with the check the plan gives «en configuracion pon el modo oscuro», the theme the click
    // left selected closes the sub-goal by that check, with no «done» of the model. Counter-case: the same theme never
    // closes «pon el modo claro» (its check asks for «claro» chosen), and the model's none ends it as not reached.
    [TestCase("activar modo oscuro", "control:modo oscuro:on|control:dark mode:on|control:oscuro:selected", true)]
    [TestCase("activar modo claro", "control:modo claro:on|control:light mode:on|control:claro:selected", false)]
    public async Task R28_T4_C04_TheThemeLeftSelectedClosesOnlyTheCheckThatAsksForIt(string goal, string check, bool reached)
    {
        bool pressed = false;
        var harness = new Harness
        {
            Screen = _ => Window("Configuración", "SystemSettings", 40, true,
            [
                Control(11, "ListItem", "Personalización", "selected"),
                Control(20, "ListItem", "Windows (oscuro), 1 imágenes", pressed ? "selected focused" : string.Empty),
                Control(22, "ListItem", "Windows (claro), 1 imágenes"),
                Control(26, "ListItem", "Fondo"),
            ]),
            Mind = request => request.History.Count == 0
                ? Step("input.visible.click", new JsonObject { ["label"] = "Windows (oscuro), 1 imágenes" })
                : Step("none", new JsonObject()),
        };
        harness.Receipt = (_, _) =>
        {
            pressed = true;
            return new JsonObject { ["surfaceChanged"] = true, ["selected"] = true, ["kind"] = "ListItem" };
        };

        JsonObject observed = await R28Run(harness, goal, check);

        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"] == true, Is.EqualTo(reached));
            if (reached)
            {
                Assert.That((string?)observed["satisfiedBy"], Is.EqualTo("control:oscuro:selected"));
                Assert.That(harness.Requests, Has.Count.EqualTo(1), "closed by the check, the model is not asked again");
            }
        });
    }
}
