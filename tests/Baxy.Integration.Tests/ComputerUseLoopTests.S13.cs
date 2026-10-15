using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Encargo S13 (banco fq1–fq3 s13 t3, fable/estab-fase3 5c9a9e2e1): after «en Discord andá al canal Cotele» → «no», the
/// turn «y ahora andá a configuración» went to the engine (until VZ the decider had read it as app.open of Discord). The
/// press of «Ajustes de usuario» opened Discord's settings over «Amigos - Discord»: the title stays, no navigation item
/// is chosen, and the page brings the heading «Barra lateral de ajustes». No atom of «ir a configuracion» held, the model
/// pressed «Ajustes de usuario» again and again and the mission stopped out of steps («No pude llegar a
/// «configuracion»…»). The heading the press brought is the page reached (HeaderAppeared, the «header:» judge).
/// </summary>
public sealed partial class ComputerUseLoopTests
{
    // The check the mind writes for «andá a configuración» (semantic.missions._read_act), as the live trace carried it.
    private const string S13Check =
        "control:configuracion:current|title:configuracion|page:configuracion|control:ajustes:current|title:ajustes|page:ajustes"
        + "|control:preferences:current|title:preferences|page:preferences|control:preferencias:current|title:preferencias"
        + "|page:preferencias|control:settings:current|title:settings|page:settings|mark:configuracion|mark:ajustes"
        + "|mark:preferences|mark:preferencias|mark:settings";

    private static JsonObject S13Control(int index, string kind, string name, string zone, string state = "", string? value = null)
    {
        JsonObject control = Control(index, kind, name, state, value);
        control["zone"] = zone;
        return control;
    }

    // S13b (fp1–3, war1–3): what the provider lists past its cap of 60 for the goal's words is marked «reserved».
    private static JsonObject S13Reserved(int index, string kind, string name, string zone)
    {
        JsonObject control = S13Control(index, kind, name, zone);
        control["reserved"] = true;
        return control;
    }

    // Discord's Friends page as the live look listed it (fq1 request 27), the button «Ajustes de usuario» at the bottom.
    private static JsonObject S13Friends(bool headingAlready = false, bool words = true)
    {
        JsonArray controls =
        [
            S13Control(0, "Document", "Amigos", "C", "readonly", "https://discord.com/channels/@me"),
            S13Control(4, "Button", "Atrás", "TL"),
            S13Control(5, "ListItem", VzSearchResult, "T"),
            S13Control(8, "TreeItem", "Mensajes directos", "TL", "selected"),
            S13Control(14, "TreeItem", "Amigos, carpeta Amigos", "L", "expanded"),
            S13Control(16, "TreeItem", "Choche", "L"),
            S13Control(21, "Button", "Buscar o iniciar una conversación", "TL"),
            S13Control(22, "ListItem", "Amigos", "TL"),
            S13Control(24, "ListItem", "Nitro", "TL"),
            S13Control(41, "Button", "Opciones de entrada", "BL"),
            S13Control(44, "Button", "Ajustes de usuario", "BL"),
            S13Control(45, "TabItem", "En línea", "T", "selected"),
            S13Control(51, "Edit", "Buscar", "T", value: "cotele"),
        ];
        if (words)
        {
            controls.Add(S13Reserved(60, "Group", "Estado y ajustes del usuario", "BL"));
        }

        if (headingAlready)
        {
            controls.Add(S13Reserved(62, "Text", "Barra lateral de ajustes", "TL"));
        }

        return Window("Amigos - Discord", "Discord", 9676, true, controls);
    }

    // The settings drawn over the same window (fq1 request 29): its own sidebar and pages, the window's title unchanged.
    private static JsonObject S13Settings(bool heading = true)
    {
        JsonArray controls =
        [
            S13Control(0, "Document", "Amigos", "C", "readonly", "https://discord.com/channels/@me"),
            S13Control(4, "Button", "Atrás", "TL"),
            S13Control(9, "Hyperlink", "Amigos", "TL", "readonly", "https://discord.com/channels/@me"),
            S13Control(13, "Button", "Más", "L", "collapsed"),
            S13Control(27, "Button", "Ajustes de usuario", "BL"),
            S13Control(28, "TabItem", "En línea", "T", "selected"),
            S13Control(34, "Edit", "Buscar", "T", value: "cotele"),
            S13Control(43, "Hyperlink", "Avatar RED Editar perfiles", "TL", "readonly"),
            S13Control(44, "Hyperlink", "Cuenta", "TL", "readonly"),
            S13Control(45, "Hyperlink", "Información de cuenta", "L", "readonly"),
            S13Control(46, "Hyperlink", "Contraseña y seguridad", "L", "readonly"),
            S13Control(47, "Hyperlink", "Datos y privacidad", "L", "readonly"),
            S13Control(56, "Hyperlink", "Condiciones del Servicio", "T", "readonly"),
            S13Control(59, "Button", "Eliminar cuenta", "BR", "focused"),
            S13Reserved(60, "Group", "Estado y ajustes del usuario", "BL"),
        ];
        if (heading)
        {
            controls.Add(S13Reserved(61, "Group", "Barra lateral de ajustes", "L"));
            controls.Add(S13Reserved(62, "Text", "Barra lateral de ajustes", "TL"));
            controls.Add(S13Reserved(63, "Group", "Páginas de ajustes", "L"));
        }

        return Window("Amigos - Discord", "Discord", 9676, true, controls);
    }

    private async Task<(JsonObject Observed, Harness Harness)> S13Run(Func<int, JsonObject> screen, string label = "Ajustes de usuario")
    {
        int presses = 0;
        var harness = new Harness
        {
            Screen = _ => screen(presses),
            Mind = _ => Step("input.visible.click", new JsonObject { ["label"] = label, ["index"] = label == "Más" ? 13 : 44 }),
        };
        harness.Receipt = (operation, _) =>
        {
            presses += operation == "input.visible.click" ? 1 : 0;
            return new JsonObject { ["surfaceChanged"] = true };
        };
        var arguments = new JsonObject { ["goal"] = "ir a configuracion", ["application"] = "Discord", ["successCheck"] = S13Check };
        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en Discord, andá a configuración", arguments), arguments, CancellationToken.None);
        return (Observed(result), harness);
    }

    private static string[] S13Clicks(Harness harness) =>
        [.. harness.Acts.Where(act => act.Operation == "input.visible.click").Select(act => (string?)act.Arguments["label"] ?? string.Empty)];

    // fq2, fq3: the settings drawn right after the press. One press arrives (fq1: on the look that first shows them).
    [Test]
    public async Task S13_TheSettingsThePressOpenedOverTheSameTitleAreThePlaceReached()
    {
        (JsonObject observed, Harness harness) = await S13Run(presses => presses == 0 ? S13Friends() : S13Settings());

        Assert.Multiple(() =>
        {
            Assert.That((bool?)observed["reached"], Is.True);
            Assert.That(S13Clicks(harness), Is.EqualTo(new[] { "Ajustes de usuario" }));
        });
    }

    // The bank's whole sequence behind the Kernel in Normal: turn 1 asks before joining Cotele (VZ: one question), «no»
    // leaves it unpressed, and turn 3, a new mission, presses «Ajustes de usuario» without any question and arrives.
    [Test]
    public async Task S13_TheCancelledJoinLeavesTheNextMissionToTheSettingsUnasked()
    {
        bool settings = false;
        bool turnThree = false;
        var harness = new Harness
        {
            Screen = _ => settings ? S13Settings() : S13Friends(),
            Mind = _ => turnThree
                ? Step("input.visible.click", new JsonObject { ["label"] = "Ajustes de usuario", ["index"] = 44 })
                : Step("input.visible.click", new JsonObject { ["label"] = VzSearchResult, ["index"] = 5 }),
        };
        harness.Receipt = (_, arguments) =>
        {
            settings |= (string?)arguments["label"] == "Ajustes de usuario";
            return new JsonObject { ["surfaceChanged"] = true };
        };
        var asked = new List<string>();
        var confirmed = new List<string>();
        ComputerUseMission.Context context = VzBehindTheKernel(
            harness.Context(_root), Baxy.Kernel.Policy.ConfirmationMode.Normal, asked, confirmed);
        var join = new JsonObject { ["goal"] = "entrá al canal Cotele", ["application"] = "Discord" };

        ComputerUseMission.Result first = await ComputerUseMission.RunAsync(
            context, Execution("en Discord andá al canal Cotele", join), join, CancellationToken.None);
        turnThree = true;
        var arguments = new JsonObject { ["goal"] = "ir a configuracion", ["application"] = "Discord", ["successCheck"] = S13Check };
        ComputerUseMission.Result third = await ComputerUseMission.RunAsync(
            context, Execution("en Discord, andá a configuración", arguments), arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(first.Confirmation, Is.Not.Null, "turn 1 asks once");
            Assert.That(third.Confirmation, Is.Null);
            Assert.That(asked, Is.EqualTo(new[] { VzSearchResult }));
            Assert.That(confirmed, Is.Empty);
            Assert.That((bool?)Observed(third)["reached"], Is.True);
            Assert.That(S13Clicks(harness), Is.EqualTo(new[] { "Ajustes de usuario" }), "the join was never pressed");
        });
    }

    // S13b, seguridad (fp1–3: the mission ended with Discord's focus on «Eliminar cuenta», put there by Discord, never
    // pressed): in Normal the Kernel asks before a click on it and before Enter or space while it has the keyboard; a
    // mission that already arrived stops before any of them.
    [Test]
    public async Task S13_DeletingTheAccountIsAskedByClickOrByKeyAndNeverReachedAfterArriving()
    {
        var asked = new List<string>();
        var confirmed = new List<string>();
        var harness = new Harness
        {
            Screen = _ => S13Settings(),
            Mind = _ => Step("input.visible.click", new JsonObject { ["label"] = "Eliminar cuenta", ["index"] = 59 }),
        };
        var arguments = new JsonObject { ["goal"] = "abrir mi perfil", ["application"] = "Discord" };
        ComputerUseMission.Result clicked = await ComputerUseMission.RunAsync(
            VzBehindTheKernel(harness.Context(_root), Baxy.Kernel.Policy.ConfirmationMode.Normal, asked, confirmed),
            Execution("en Discord abrí mi perfil", arguments), arguments, CancellationToken.None);
        JsonObject focusedThere = S13Settings();
        focusedThere["window"]!["focused"] = new JsonObject { ["kind"] = "Button", ["name"] = "Eliminar cuenta" };
        string? onto = ComputerUseMission.KeyLandsOnWhatAsks(focusedThere, "enter");
        using System.Text.Json.JsonDocument enter = System.Text.Json.JsonDocument.Parse(
            new JsonObject { ["key"] = "enter", ["onto"] = onto }.ToJsonString());

        (JsonObject arrived, Harness settings) = await S13Run(presses => presses == 0 ? S13Friends() : S13Settings());

        Assert.Multiple(() =>
        {
            Assert.That(clicked.Confirmation, Is.Not.Null);
            Assert.That(asked, Is.EqualTo(new[] { "Eliminar cuenta" }));
            Assert.That(harness.Acts.Where(act => act.Operation == "input.visible.click"), Is.Empty);
            Assert.That(onto, Is.EqualTo("Eliminar cuenta"));
            Assert.That(
                Baxy.Kernel.Policy.RiskPolicy.Evaluate(
                    Baxy.Kernel.Operations.OperationRisk.Reversible, Baxy.Kernel.Policy.ConfirmationMode.Normal,
                    "input.key.press", enter.RootElement),
                Is.EqualTo(Baxy.Kernel.Policy.PolicyDecision.RequireConfirmation));
            Assert.That((bool?)arrived["reached"], Is.True);
            Assert.That(S13Clicks(settings), Has.None.Contains("Eliminar"));
        });
    }

    // S13b contracase: the look before the press carried no goal's words (no reserved control of this look listed in it):
    // a reserved heading may have been cut from it, so it proves nothing.
    [Test]
    public async Task S13_AReservedHeadingAgainstALookWithoutTheWordsIsNoArrival()
    {
        (JsonObject observed, _) = await S13Run(presses => presses == 0 ? S13Friends(words: false) : S13Settings());

        Assert.That((bool?)observed["reached"], Is.Not.True);
    }

    // Contracases: a heading that was already there before the press, a page without a heading naming the place, and a
    // press of a control that does not name it («Más») prove nothing.
    [TestCase(true, true, "Ajustes de usuario", TestName = "S13_AHeadingAlreadyThereBeforeThePressIsNoArrival")]
    [TestCase(false, false, "Ajustes de usuario", TestName = "S13_APageWithoutAHeadingNamingThePlaceIsNoArrival")]
    [TestCase(false, true, "Más", TestName = "S13_APressThatDoesNotNameThePlaceIsNoArrival")]
    public async Task S13_NoArrival(bool headingAlready, bool heading, string label)
    {
        (JsonObject observed, _) = await S13Run(
            presses => presses == 0 ? S13Friends(headingAlready) : headingAlready ? S13Friends(headingAlready) : S13Settings(heading),
            label);

        Assert.That((bool?)observed["reached"], Is.Not.True);
    }
}
