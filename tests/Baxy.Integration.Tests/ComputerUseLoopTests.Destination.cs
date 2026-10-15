using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Revision 1 of ronda 21 (B5), destino por contenido: the mission's search for the window its request names, end to end
/// over the scripted screen. The listing (<c>candidates</c>) is the first look of a mission with no application and a
/// referent; a window bound is the one every later look reads; an ambiguous, absent, person's or unlisted destination
/// ends the mission with nothing done and the model never asked; a provider that lists no windows leaves the mission as
/// it was.
/// </summary>
public sealed partial class ComputerUseLoopTests
{
    private const string RotateGoal = "Gira la imagen 90 grados a la derecha desde el menú Imagen > Girar";

    private static JsonObject RotateArguments() => new()
    {
        ["goal"] = RotateGoal,
        ["referentLabels"] = new JsonArray("imagen", "girar"),
    };

    private static JsonObject Candidate(long hwnd, int processId, string process, string title, bool foreground = false,
        long? personAgo = null, params (string Kind, string Name)[] controls)
    {
        var window = new JsonObject
        {
            ["hwnd"] = hwnd,
            ["processId"] = processId,
            ["process"] = process,
            ["title"] = title,
            ["foreground"] = foreground,
            ["controls"] = new JsonArray([.. controls.Select(control => (JsonNode?)new JsonObject
            {
                ["kind"] = control.Kind,
                ["name"] = control.Name,
            })]),
        };
        if (personAgo is long ago)
            window["personInputAgoMs"] = ago;
        return window;
    }

    private static JsonObject PaintCandidate(long hwnd, string title, bool foreground = false, long? personAgo = null) => Candidate(
        hwnd, 900 + (int)hwnd, "mspaint", title, foreground, personAgo,
        ("MenuItem", "Archivo"), ("Text", "Imagen"), ("Button", "Girar"));

    private static JsonObject PersonCandidate() => Candidate(
        1, 800, "python", "BAXY usuario simulado", true, null, ("Document", "el usuario escribe aquí"));

    private static JsonObject Listing(params JsonObject[] windows) => new()
    {
        ["candidateWindows"] = new JsonArray([.. windows.Select(window => (JsonNode?)window)]),
    };

    private static bool AsksCandidates(JsonObject look) => (bool?)look["candidates"] == true;

    [TestCase("ambiguous", "computer_use_destination_ambiguous")]
    [TestCase("none", "computer_use_destination_not_found")]
    [TestCase("persons", "computer_use_destination_persons_window")]
    [TestCase("unlisted", "computer_use_destination_unlisted")]
    public async Task Revision1B5ADestinationNotBoundEndsTheMissionWithNothingDone(string desktop, string stop)
    {
        var harness = new Harness
        {
            Screen = look => !AsksCandidates(look)
                ? Window("BAXY usuario simulado", "python", 800, false, [Control(0, "Document", "el usuario escribe aquí")])
                : desktop switch
                {
                    "ambiguous" => Listing(PersonCandidate(), PaintCandidate(4, "uno.png - Paint"), PaintCandidate(9, "dos.png - Paint")),
                    "none" => Listing(PersonCandidate()),
                    "persons" => Listing(PaintCandidate(4, "uno.png - Paint", foreground: true, personAgo: 1500)),
                    // The listing could not be read in time: the provider's answer failed.
                    _ => null,
                },
            Mind = _ => Step("input.visible.click", new JsonObject { ["label"] = "Girar" }),
        };
        JsonObject arguments = RotateArguments();

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution(RotateGoal, arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.Multiple(() =>
        {
            Assert.That((string?)observed["stoppedBy"], Is.EqualTo(stop));
            Assert.That((bool?)observed["reached"], Is.Not.True);
            Assert.That(harness.Acts, Is.Empty, "nothing pressed, typed or opened");
            Assert.That(harness.Requests, Is.Empty, "the model is never asked over a window that is not the destination");
            Assert.That(harness.Looks, Has.Count.EqualTo(1), "only the listing, never the person's window in front");
            Assert.That(AsksCandidates(harness.Looks[0]), Is.True);
        });
        if (desktop == "ambiguous")
        {
            Assert.That(observed["destinationCandidates"]!.ToJsonString(), Does.Contain("uno.png - Paint").And.Contain("dos.png - Paint"));
        }
    }

    [Test]
    public async Task Revision1B5TheBoundWindowIsWhatEveryLaterLookReads()
    {
        var harness = new Harness
        {
            Screen = look => AsksCandidates(look)
                ? Listing(PersonCandidate(), PaintCandidate(4, "lienzo - Paint"))
                : Window("lienzo - Paint", "mspaint", 904, true, [Control(0, "Text", "Imagen"), Control(1, "Button", "Girar")]),
            Mind = _ => null,
        };
        JsonObject arguments = RotateArguments();

        await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution(RotateGoal, arguments), arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(harness.Looks, Has.Count.GreaterThan(1));
            Assert.That(harness.Looks.Count(AsksCandidates), Is.EqualTo(1), "the desktop is listed once");
            JsonObject next = harness.Looks[1];
            Assert.That(AsksCandidates(next), Is.False);
            Assert.That(next["windows"]?.ToJsonString(), Is.EqualTo("[4]"), "the bound window, never the one in front");
            Assert.That((int?)next["processId"], Is.EqualTo(904));
        });
    }

    [Test]
    public async Task Revision1B5AProviderThatListsNoWindowsLeavesTheMissionAsItWas()
    {
        // A provider without the listing answers the look with an ordinary view: the mission goes on exactly as a mission
        // without referent does.
        JsonObject front = Window("BAXY usuario simulado", "python", 800, false, [Control(0, "Document", "el usuario escribe aquí")]);
        var withReferent = new Harness { Screen = _ => front.DeepClone().AsObject(), Mind = _ => null };
        var without = new Harness { Screen = _ => front.DeepClone().AsObject(), Mind = _ => null };
        JsonObject arguments = RotateArguments();
        var plain = new JsonObject { ["goal"] = RotateGoal };

        ComputerUseMission.Result referred = await ComputerUseMission.RunAsync(
            withReferent.Context(_root), Execution(RotateGoal, arguments), arguments, CancellationToken.None);
        ComputerUseMission.Result unreferred = await ComputerUseMission.RunAsync(
            without.Context(_root), Execution(RotateGoal, plain), plain, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(AsksCandidates(withReferent.Looks[0]), Is.True);
            Assert.That(withReferent.Looks.Skip(1).Select(look => look.ToJsonString()),
                Is.EqualTo(without.Looks.Select(look => look.ToJsonString())));
            Assert.That((string?)Observed(referred)["stoppedBy"], Is.EqualTo((string?)Observed(unreferred)["stoppedBy"]));
            Assert.That(withReferent.Acts.Select(act => act.Operation + act.Arguments.ToJsonString()),
                Is.EqualTo(without.Acts.Select(act => act.Operation + act.Arguments.ToJsonString())));
        });
    }

    [TestCase(300L, false)]
    [TestCase(ComputerUseMissionWindow.PersonRecentMs + 2000, true)]
    public async Task Revision2B1WithoutRawInputTheWindowInFrontWithRecentInputIsNeverBound(long unknownAgo, bool bound)
    {
        // The simulated person types without Raw Input: the listing knows no window of theirs, only that the session's
        // last input came «unknownAgo» ms ago. The one window that shows «Imagen» and «Girar» is the one in front.
        var harness = new Harness
        {
            Screen = look =>
            {
                if (!AsksCandidates(look))
                {
                    return Window("lienzo - Paint", "mspaint", 904, true, [Control(0, "Text", "Imagen"), Control(1, "Button", "Girar")]);
                }

                JsonObject listing = Listing(PaintCandidate(4, "lienzo - Paint", foreground: true));
                listing["personInputUnknownAgoMs"] = unknownAgo;
                return listing;
            },
            Mind = _ => Step("input.visible.click", new JsonObject { ["label"] = "Girar" }),
        };
        JsonObject arguments = RotateArguments();

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution(RotateGoal, arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        if (!bound)
        {
            Assert.Multiple(() =>
            {
                Assert.That((string?)observed["stoppedBy"], Is.EqualTo("computer_use_destination_persons_window"));
                Assert.That(harness.Acts, Is.Empty, "nothing pressed in the window where the person just typed");
                Assert.That(harness.Requests, Is.Empty);
                Assert.That(harness.Looks, Has.Count.EqualTo(1));
            });
            return;
        }

        // Contracase: the input is older than a moment; the window is bound and the click goes to it, as before.
        Assert.That(harness.Acts.Select(act => act.Operation + act.Arguments.ToJsonString()),
            Does.Contain("input.visible.click{\"label\":\"Girar\"}"));
    }

    [Test]
    public async Task Revision2B2APointedFrontIsNeverReplacedByAWindowBehind()
    {
        // «en esta ventana, desde el menú Archivo, guardala como pagina.html» with Edge in front: the person points at
        // it. The Bloc de notas behind (with «Archivo») is never listed for, bound nor read. Estabilización L: the save
        // referent is retired, so the window behind would fit by the menu said.
        const string goal = "en esta ventana, desde el menú Archivo, guardala como pagina.html";
        JsonObject listing = Listing(
            Candidate(12, 911, "msedge", "Noticias - Microsoft Edge", true, null, ("Document", "Noticias")),
            Candidate(3, 902, "Notepad", "lista del super.txt - Bloc de notas", false, null, ("MenuItem", "Archivo")));
        var harness = new Harness
        {
            Screen = look => AsksCandidates(look)
                ? listing.DeepClone().AsObject()
                : Window("Noticias - Microsoft Edge", "msedge", 911, false, [Control(0, "Document", "Noticias")]),
            Mind = _ => null,
        };
        var arguments = new JsonObject { ["goal"] = goal, ["frontWindow"] = true, ["referentLabels"] = new JsonArray("archivo") };

        await ComputerUseMission.RunAsync(harness.Context(_root), Execution(goal, arguments), arguments, CancellationToken.None);

        Assert.Multiple(() =>
        {
            Assert.That(harness.Looks, Is.Not.Empty);
            Assert.That(harness.Looks.Any(AsksCandidates), Is.False, "the desktop is not weighed against the pointed window");
            Assert.That(harness.Looks.Any(look => look["windows"]?.ToJsonString() == "[3]"), Is.False, "the Bloc de notas is never read");
            Assert.That(harness.Acts.Any(act => (int?)act.Arguments["processId"] == 902), Is.False);
        });
    }

    [TestCase("input.key.press", "{\"key\":\"ctrl_a\"}", false)]
    [TestCase("input.key.press", "{\"key\":\"ctrl_v\"}", false)]
    [TestCase("input.text.type", "{\"text\":\"hola\"}", false)]
    [TestCase("input.visible.click", "{\"label\":\"Insertar\"}", true)]
    public async Task Revision3B1TheBoundWindowsDocumentIsNotOneTheRequestNames(string operation, string step, bool acted)
    {
        // «desde la pestaña Insertar seleccioná todo y ponelo en negrita» with the owner's thesis open in Word behind,
        // with no recent input: the tab's name binds the window, but «Insertar» names no document. What selects, pastes
        // or writes over the thesis is refused as over any document the request does not name (as it is when the request
        // names Word); a click on the tab still goes to the bound window.
        const string goal = "desde la pestaña Insertar seleccioná todo y ponelo en negrita";
        var harness = new Harness
        {
            Screen = look =>
            {
                if (AsksCandidates(look))
                {
                    return Listing(PersonCandidate(), Candidate(2002, 60, "WINWORD", ThesisTitle, false, null,
                        ("TabItem", "Inicio"), ("TabItem", "Insertar"), ("Document", "Proyecto_Puente_15_Dias_Desde_Maqueta")));
                }

                JsonObject thesis = OwnersThesis(born: false);
                ((JsonArray)thesis["controls"]!).Add(Control(46, "TabItem", "Insertar"));
                return thesis;
            },
            Mind = _ => Step(operation, (JsonObject)JsonNode.Parse(step)!),
        };
        var arguments = new JsonObject { ["goal"] = goal, ["referentLabels"] = new JsonArray("insertar") };

        ComputerUseMission.Result result = await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution(goal, arguments), arguments, CancellationToken.None);

        JsonObject observed = Observed(result);
        Assert.That(harness.Looks.Skip(1).First()["windows"]?.ToJsonString(), Is.EqualTo("[2002]"), "the thesis's window is bound");
        if (!acted)
        {
            Assert.Multiple(() =>
            {
                Assert.That((string?)observed["stoppedBy"], Is.EqualTo("computer_use_document_not_named"));
                Assert.That(harness.Acts, Is.Empty, "nothing selected, pasted or written over the thesis");
            });
            return;
        }

        // Contracase: the tab is no content of the document; the click goes to the bound window.
        Assert.That(harness.Acts.Any(act => act.Operation == "input.visible.click" && (string?)act.Arguments["label"] == "Insertar"),
            Is.True, string.Join(" | ", harness.Acts.Select(act => act.Operation + act.Arguments.ToJsonString())));
    }

    [Test]
    public async Task Revision1B5ContracaseAMissionWithAnApplicationNeverListsTheDesktop()
    {
        var harness = new Harness
        {
            Screen = _ => Window("lienzo - Paint", "mspaint", 904, true, [Control(0, "Button", "Girar")]),
            Mind = _ => null,
        };
        JsonObject arguments = RotateArguments();
        arguments["application"] = "Paint";

        await ComputerUseMission.RunAsync(
            harness.Context(_root), Execution(RotateGoal, arguments), arguments, CancellationToken.None);

        Assert.That(harness.Looks.Any(AsksCandidates), Is.False);
    }

}
