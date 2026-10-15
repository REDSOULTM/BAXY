using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Encargo IMP2 (imp1 imp-wa-abrir, imp-wa-leer: «musica» typed in a chat search and Escape pressed 550 ms later, the
/// result «Música» drawn under that Escape; measured on redpc 750 to 880 ms after the text): the mind's «search_pending»
/// is a moment's wait and one more look, once per act, the act marked «awaited»; then the loop decides anew. The mind's
/// side is tests/test_estab_imp2.py.
/// </summary>
public sealed partial class ComputerUseLoopTests
{
    private static JsonObject ChatSearch(bool drawn) => Window("(5) WhatsApp", "msedgewebview2", 60, true,
        drawn
            ? [Control(0, "Edit", "WhatsApp", "focused", "musica"), Control(1, "DataItem", "Música 29/9/2026")]
            : [Control(0, "Edit", "WhatsApp", "focused", "musica"), Control(1, "DataItem", "Contacto A 0:52")]);

    [Test]
    public async Task ASearchWhoseResultsAreNotDrawnIsLookedAtOnceMoreAfterAMoment()
    {
        int looks = 0;
        var harness = new Harness
        {
            Screen = _ => ChatSearch(drawn: looks++ >= 2),
            Mind = request => request.History.Count == 0
                ? Step("input.visible.click", new JsonObject { ["label"] = "Buscar un chat o iniciar uno nuevo" })
                : (bool?)request.History[^1]!["awaited"] == true
                    ? Step("done", new JsonObject { ["evidence"] = "Música 29/9/2026" })
                    : new MindComputerUseStep("none", new JsonObject(), "la búsqueda todavía no muestra sus resultados",
                        ComputerUseMission.SearchPending),
        };
        var arguments = new JsonObject { ["goal"] = "ir a musica", ["application"] = "WhatsApp" };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en WhatsApp abrí el chat Música", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That(observed["stoppedBy"], Is.Null);
            Assert.That(harness.Delays, Does.Contain(ComputerUseMission.SearchResultsWait));
            Assert.That(harness.Requests.Count(request => request.History.Count > 0), Is.EqualTo(2), "asked once, then decided anew");
            Assert.That((bool?)harness.Requests[^1].History[^1]!["awaited"], Is.True);
        });
    }

    [Test]
    public async Task ContracaseASecondSearchPendingOnTheSameActIsNoWait()
    {
        var harness = new Harness
        {
            Screen = _ => ChatSearch(drawn: false),
            Mind = request => request.History.Count == 0
                ? Step("input.visible.click", new JsonObject { ["label"] = "Buscar un chat o iniciar uno nuevo" })
                : new MindComputerUseStep("none", new JsonObject(), "la búsqueda todavía no muestra sus resultados",
                    ComputerUseMission.SearchPending),
        };
        var arguments = new JsonObject { ["goal"] = "ir a musica", ["application"] = "WhatsApp" };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en WhatsApp abrí el chat Música", arguments), arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That((string?)Observed(result)["stoppedBy"], Is.EqualTo("computer_use_no_step_visible"));
            Assert.That(harness.Delays.Count(delay => delay == ComputerUseMission.SearchResultsWait), Is.EqualTo(1));
        });
    }

    // imp2 imp-wa-abrir (notebook journal 06:04:41–45): «musica» typed, the result «Música 29/9/2026» pressed and the
    // group's message box took the keyboard; the window's chat list still shows every result and the search keeps the text.
    private static JsonObject WhatsAppAfter(bool opened)
    {
        JsonObject view = Window("(5) WhatsApp", "msedgewebview2", 60, true,
            opened
                ? [Control(0, "Edit", "WhatsApp", "", "musica"), Control(1, "Edit", "Escribir un mensaje para el grupo Música", "focused"),
                   Control(2, "DataItem", "Música 29/9/2026 Tú : . Chat silenciado Archivado"), Control(3, "DataItem", "Música 29/9/2026"),
                   Control(4, "DataItem", "Juanito 29/9/2026 pasame esa musica"), Control(5, "Button", "Música Tú")]
                : [Control(0, "Edit", "WhatsApp", "focused", "musica"),
                   Control(2, "DataItem", "Música 29/9/2026 Tú : . Chat silenciado Archivado"), Control(3, "DataItem", "Música 29/9/2026"),
                   Control(4, "DataItem", "Juanito 29/9/2026 pasame esa musica")]);
        view["window"]!["focused"] = opened
            ? new JsonObject { ["kind"] = "Edit", ["name"] = "Escribir un mensaje para el grupo Música" }
            : new JsonObject { ["kind"] = "Edit", ["name"] = "WhatsApp", ["value"] = "musica" };
        return view;
    }

    private const string ToMusica = "control:musica:current|title:musica|page:musica|control:music:current|title:music|page:music|mark:musica|mark:music";

    [TestCase(true)]
    [TestCase(false)]
    public async Task AResultPressedThatPutTheKeyboardInThePlacesOwnBoxIsArriving(bool opened)
    {
        var harness = new Harness
        {
            Mind = request => request.History.Count switch
            {
                0 => Step("input.text.type", new JsonObject { ["text"] = "musica" }),
                1 => Step("input.visible.click", new JsonObject { ["label"] = "Música 29/9/2026" }),
                _ => null,
            },
        };
        harness.Screen = _ => WhatsAppAfter(opened && harness.Acts.Any(act => act.Operation == "input.visible.click"));
        var arguments = new JsonObject { ["goal"] = "ir a musica", ["application"] = "WhatsApp", ["successCheck"] = ToMusica };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en WhatsApp abrí el chat Música", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            // Opened: the message box named for the group took the keyboard with the click. Contracase: the search kept
            // the keyboard and its text, the click changed nothing there: no arrival, the mission goes on.
            Assert.That((bool?)observed["reached"], Is.EqualTo(opened));
            Assert.That(harness.Acts.Count(act => act.Operation == "input.visible.click"), Is.EqualTo(1));
        });
    }

    [Test]
    public void ContracaseASearchBoxNamingThePlaceIsNoArrival()
    {
        JsonObject view = WhatsAppAfter(opened: true);
        view["window"]!["focused"] = new JsonObject { ["kind"] = "Edit", ["name"] = "Buscar en Música" };
        var steps = new JsonArray { new JsonObject { ["step"] = 1, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "Música 29/9/2026" } };
        view["focusBeforeStep"] = new JsonObject { ["1"] = "Edit|whatsapp" };
        view["controlsBeforeClick"] = new JsonObject { ["1"] = new JsonArray("whatsapp") };
        Assert.That(ComputerUseSuccessCheck.FocusedIntoThePlace(view, "musica", steps), Is.False);
        view["window"]!["focused"] = new JsonObject { ["kind"] = "Edit", ["name"] = "Escribir un mensaje para el grupo Música" };
        Assert.That(ComputerUseSuccessCheck.FocusedIntoThePlace(view, "musica", steps), Is.True);
    }

    // imp2 imp-dc-leer: the DM open, the look cut at 60 of 169 controls with no message among them; the tree's last entries
    // hold the newest messages (measured on redpc: the last 60 of 177 named on-screen entries hold ten «autor , texto ,
    // hora» groups).
    [Test]
    public async Task AQuestionMissionReadsTheTreesTailOnceWhenItsLookWasCut()
    {
        var harness = new Harness
        {
            Mind = static _ => Step("done", new JsonObject { ["evidence"] = "@Ron92 - Discord" }),
        };
        harness.Screen = look =>
        {
            if ((bool?)look["tail"] == true)
            {
                return Window("@Ron92 - Discord", "Discord", 60, true,
                    [Control(0, "Group", "RED Etiqueta del servidor: DEMO , prueba BAXY C6 , 01:17 a. m."),
                     Control(1, "Group", "RED Etiqueta del servidor: DEMO , prueba BAXY C6 , 02:55 a. m."),
                     Control(2, "Edit", "Mensaje @Ron92")]);
            }

            JsonObject cut = Window("@Ron92 - Discord", "Discord", 60, true,
                [.. Enumerable.Range(0, 60).Select(index => (JsonNode?)Control(index, "Hyperlink", $"enlace {index}"))]);
            cut["controlCount"] = 169;
            return cut;
        };
        var arguments = new JsonObject
        {
            ["goal"] = "ir a ron92; y responder: leé lo último que me escribió Ron92",
            ["application"] = "Discord",
            ["successCheck"] = "title:ron92",
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en Discord leé lo último que me escribió Ron92", arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That(harness.Looks.Count(look => (bool?)look["tail"] == true), Is.EqualTo(1));
            Assert.That(harness.Looks.Where(look => (bool?)look["tail"] == true).All(look => look["wanted"] is null), Is.True);
            Assert.That(((JsonArray)observed["screen"]!["groups"]!).Select(node => (string?)node),
                Is.EqualTo(new[] { "RED Etiqueta del servidor: DEMO , prueba BAXY C6 , 01:17 a. m.",
                    "RED Etiqueta del servidor: DEMO , prueba BAXY C6 , 02:55 a. m." }));
        });
    }

    // Encargo IMP4 (imp3 imp-wa-leer): the open chat's tree holds no message text; a mission reached that answers a
    // question, in an application whose data declare its conversation, reads the window's lines with their places once.
    [TestCase("WhatsApp", true)]
    [TestCase("Discord", false)]
    public async Task AChatWithoutATreeIsReadOnceFromItsLinesWithTheirPlaces(string application, bool read)
    {
        var harness = new Harness
        {
            Mind = static _ => Step("done", new JsonObject { ["evidence"] = "Escribir un mensaje para el grupo Música" }),
        };
        harness.Screen = look =>
        {
            JsonObject view = Window("(5) WhatsApp", application, 60, true,
                [Control(0, "Edit", "Escribir un mensaje para el grupo Música", "focused"), Control(1, "Button", "Música Tú")]);
            if ((bool?)look["lines"] == true)
            {
                view["textLines"] = new JsonArray(new JsonObject
                {
                    ["text"] = "nos vemos a las nueve",
                    ["x"] = 0.262,
                    ["y"] = 0.7,
                    ["w"] = 0.11,
                    ["h"] = 0.0153,
                });
            }

            return view;
        };
        var arguments = new JsonObject
        {
            ["goal"] = "ir a musica; y responder: leé lo último que me escribieron en Música",
            ["application"] = application,
            ["successCheck"] = "control:musica:current|page:musica",
        };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution("en WhatsApp leé lo último que me escribieron en Música", arguments), arguments,
            CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That(harness.Looks.Count(look => (bool?)look["lines"] == true), Is.EqualTo(read ? 1 : 0));
            Assert.That(observed["screen"]?["chatLines"] is JsonArray, Is.EqualTo(read));
        });
    }

    [Test]
    public void OnlyAnApplicationWhoseDataDeclareItsConversationIsReadByLines() =>
        Assert.Multiple(() =>
        {
            Assert.That(Baxy.Kernel.Operations.ApplicationPlaces.HasConversation("WhatsApp"), Is.True);
            Assert.That(Baxy.Kernel.Operations.ApplicationPlaces.HasConversation("Discord"), Is.False);
            Assert.That(Baxy.Kernel.Operations.ApplicationPlaces.HasConversation(null), Is.False);
        });
}
