using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Ronda 24b, «ya estaba» se reconoce y se dice (banco r23 u9, u5, x10). u9: Spotify was already on its search page, the
/// root document «Spotify – Buscar» under the window «Spotify Premium», and title:buscar never read it, so the rules
/// clicked over a screen that already held. u5: a blank «Libro1» already in front is the new workbook asked for. x10:
/// a part reached on its first look keeps how the window wrote it (arrivedAs) and whether an act got it there.
/// </summary>
[TestFixture]
public sealed class ComputerUseYaEstabaTests
{
    private static JsonObject Embedded(string page, params JsonObject[] more)
    {
        var controls = new JsonArray(
            new JsonObject
            {
                ["i"] = 0,
                ["kind"] = "Edit",
                ["name"] = "Address and search bar",
                ["state"] = "readonly",
                ["value"] = "xpui.app.spotify.com/index.html"
            },
            new JsonObject
            {
                ["i"] = 1,
                ["kind"] = "Document",
                ["name"] = page,
                ["state"] = "readonly",
                ["value"] = "https://xpui.app.spotify.com/index.html",
                ["rect"] = new JsonObject { ["x"] = 0, ["y"] = 0, ["w"] = 1500, ["h"] = 900 }
            },
            new JsonObject { ["i"] = 2, ["kind"] = "Button", ["name"] = "Buscar", ["zone"] = "TL" },
            new JsonObject { ["i"] = 3, ["kind"] = "Button", ["name"] = "Inicio", ["zone"] = "TL" });
        foreach (JsonObject control in more)
        {
            controls.Add(control);
        }

        return new JsonObject
        {
            ["window"] = new JsonObject
            {
                ["title"] = "Spotify Premium",
                ["process"] = "Spotify",
                ["rect"] = new JsonObject { ["x"] = 0, ["y"] = 0, ["w"] = 1500, ["h"] = 900 },
            },
            ["controls"] = controls,
        };
    }

    [Test]
    public void U9TheRootDocumentTitlesThePage()
    {
        JsonObject view = Embedded("Spotify – Buscar");
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.PageTitle(view), Is.EqualTo("Spotify – Buscar"));
            Assert.That(ComputerUseSuccessCheck.Atom("title:buscar", view, []), Is.True, "already on the search page");
        });
    }

    [Test]
    public void ContracaseOnTheHomePageTheSearchIsStillToGo()
    {
        JsonObject view = Embedded("Spotify - Reproductor web: música para todos");
        Assert.That(ComputerUseSuccessCheck.Atom("title:buscar", view, []), Is.False);
    }

    [Test]
    public void ContracaseANestedDocumentNeverTitlesThePage()
    {
        // A small card named «Buscar» inside the root page «Inicio», with no address field: only the root counts.
        JsonObject view = Embedded("Inicio", new JsonObject
        {
            ["i"] = 4,
            ["kind"] = "Document",
            ["name"] = "Buscar",
            ["rect"] = new JsonObject { ["x"] = 900, ["y"] = 600, ["w"] = 300, ["h"] = 200 },
        });
        ((JsonArray)view["controls"]!).RemoveAt(0);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.PageTitle(view), Is.EqualTo("Inicio"));
            Assert.That(ComputerUseSuccessCheck.Atom("title:buscar", view, []), Is.False);
        });
    }

    [Test]
    public void ContracaseAPageTitleThatEchoesTheTypingIsNoArrival()
    {
        JsonObject view = Embedded("cumbia - Buscar");
        var typed = new JsonArray(new JsonObject
        {
            ["step"] = 1,
            ["operation"] = "input.text.type",
            ["ok"] = true,
            ["text"] = "cumbia",
            ["into"] = "¿Qué quieres reproducir? (buscar)",
            ["windowTitle"] = "Spotify Premium",
        });
        Assert.That(ComputerUseSuccessCheck.Atom("title:cumbia", view, typed), Is.False);
    }

    [Test]
    public void ContracaseABrowserTitleHoldsAsBefore()
    {
        var view = new JsonObject
        {
            ["window"] = new JsonObject { ["title"] = "Configuración - Microsoft Edge", ["process"] = "msedge" },
            ["controls"] = new JsonArray(new JsonObject { ["i"] = 0, ["kind"] = "Button", ["name"] = "Atrás" }),
        };
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.PageTitle(view), Is.Empty);
            Assert.That(ComputerUseSuccessCheck.Atom("title:configuracion", view, []), Is.True);
        });
    }

    [Test]
    public void X10ThePlaceIsKeptAsTheWindowWroteIt()
    {
        JsonObject library = ComputerUseMarkTests.Capture("library");
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.ArrivedAs("mark:biblioteca", library), Is.EqualTo("BIBLIOTECA"));
            Assert.That(ComputerUseSuccessCheck.ArrivedAs("title:buscar", Embedded("Spotify – Buscar")), Is.EqualTo("Buscar"));
            Assert.That(ComputerUseSuccessCheck.ArrivedAs("model_evidence", library), Is.Empty);
            Assert.That(ComputerUseSuccessCheck.ArrivedAs("stepDone:input.key.press:enter", library), Is.Empty);
        });
    }

    // r30 (bancos Br28 y Bb3tb: e2, v7, x9, y6): «seleccionar eraser» closed on its verified click on «Borrador» and the
    // final, with only the person's word, went to the model. The pick is kept as the control the click pressed.
    [Test]
    public void R30AVerifiedClickTheTermNamesIsKeptAsTheControlItPressed()
    {
        var view = new JsonObject { ["window"] = new JsonObject { ["title"] = "Borrador - Paint" } };
        static JsonObject Click(string name, bool ok) =>
            new() { ["operation"] = "input.visible.click", ["ok"] = ok, ["name"] = name };
        var steps = new JsonArray(
            new JsonObject { ["operation"] = "app.open", ["ok"] = true, ["name"] = "Borrador" },
            Click("Herramienta Borrador", true));
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.ArrivedAs("stepDone:input.visible.click:=borrador", view, steps), Is.EqualTo("Borrador"));
            Assert.That(ComputerUseSuccessCheck.ArrivedAs("stepDone:input.visible.click:borrador&page:x", view, steps), Is.EqualTo("Borrador"));
            // Contracases: only a verified click of the mission names it; never the title, a failed click, a click
            // on another control or a key.
            Assert.That(ComputerUseSuccessCheck.ArrivedAs("stepDone:input.visible.click:=borrador", view), Is.Empty);
            Assert.That(ComputerUseSuccessCheck.ArrivedAs(
                "stepDone:input.visible.click:=borrador", view, new JsonArray(Click("Borrador", false))), Is.Empty);
            Assert.That(ComputerUseSuccessCheck.ArrivedAs("stepDone:input.visible.click:=lapiz", view, steps), Is.Empty);
            Assert.That(ComputerUseSuccessCheck.ArrivedAs("stepDone:input.key.press:borrador", view, steps), Is.Empty);
        });
    }

    [Test]
    public void StrongTermsAreTheOnesThatSayAlready()
    {
        Assert.Multiple(() =>
        {
            Assert.That(OperationFloor.StrongArrival("mark:biblioteca"), Is.True);
            Assert.That(OperationFloor.StrongArrival("title:buscar"), Is.True);
            Assert.That(OperationFloor.StrongArrival("control:=tienda:selected"), Is.True);
            Assert.That(OperationFloor.StrongArrival("page:biblioteca"), Is.False);
            Assert.That(OperationFloor.StrongArrival("control:tienda"), Is.False);
        });
    }

    private static JsonObject Sheet(string title, string? a1 = null)
    {
        var cell = new JsonObject { ["i"] = 1, ["kind"] = "DataItem", ["name"] = "A1", ["state"] = "focused" };
        if (a1 is not null)
        {
            cell["value"] = a1;
        }

        return new JsonObject
        {
            ["window"] = new JsonObject
            {
                ["title"] = title,
                ["process"] = "EXCEL",
                ["rect"] = new JsonObject { ["x"] = 0, ["y"] = 0, ["w"] = 1600, ["h"] = 900 },
            },
            ["controls"] = new JsonArray(
                new JsonObject { ["i"] = 0, ["kind"] = "ComboBox", ["name"] = "Cuadro de nombres", ["value"] = "A1" },
                cell),
        };
    }

    [Test]
    public void U5ABlankUnnamedWorkbookIsTheOneAskedFor()
    {
        Assert.Multiple(() =>
        {
            // Revisión 1 (B3): the real u5 view lists no cell but the focused empty A1: the grid is not read, so «Libro1»
            // is not proved blank (the person's unsaved data may be elsewhere in it); a status count of zero proves it.
            Assert.That(ComputerUseMissionWindow.BlankDocumentAlready("Libro1", Sheet("Libro1 - Excel"), []), Is.False,
                "an unread grid");
            Assert.That(ComputerUseMissionWindow.DocumentContentShown(Sheet("Libro1 - Excel")), Is.Null);
            JsonObject counted = Sheet("Libro1 - Excel");
            ((JsonArray)counted["controls"]!).Add(new JsonObject { ["i"] = 2, ["kind"] = "StatusBar", ["name"] = "0 palabras" });
            Assert.That(ComputerUseMissionWindow.BlankDocumentAlready("Libro1", counted, []), Is.True, "counted zero");
            Assert.That(ComputerUseMissionWindow.BlankDocumentAlready("Libro1", Sheet("Libro1 - Excel", "hola"), []), Is.False,
                "text in A1");
            Assert.That(ComputerUseMissionWindow.BlankDocumentAlready("Presupuesto", Sheet("Presupuesto - Excel"), []), Is.False,
                "a saved workbook");
            var clicked = new JsonArray(new JsonObject { ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "x" });
            Assert.That(ComputerUseMissionWindow.BlankDocumentAlready("Libro1", counted, clicked), Is.False,
                "an act of the sub-goal");
        });
    }

    // Revisión 1 (B2): the real view of the round (tests/data/cu_v3_r24_vistas_reales.json «word_panel_navegacion»): the
    // person's unsaved draft «Documento1  -  Autorecuperado - Word», whose Document gives no value and whose status text
    // counts 13 characters.
    private static JsonObject RealWordDraft()
    {
        DirectoryInfo? directory = new(AppContext.BaseDirectory);
        while (directory is not null && !File.Exists(Path.Combine(directory.FullName, "Baxy.slnx")))
        {
            directory = directory.Parent;
        }

        string root = directory?.FullName ?? throw new DirectoryNotFoundException("Baxy.slnx was not found.");
        var views = (JsonObject)JsonNode.Parse(File.ReadAllText(Path.Combine(root, "tests", "data", "cu_v3_r24_vistas_reales.json")))!;
        return (JsonObject)views["word_panel_navegacion"]!.DeepClone();
    }

    private static void SetCount(JsonObject view, string? name)
    {
        var controls = (JsonArray)view["controls"]!;
        JsonObject counted = controls.OfType<JsonObject>().First(control => ((string?)control["name"] ?? string.Empty).Contains("caracteres", StringComparison.Ordinal));
        if (name is null)
        {
            controls.Remove(counted);
        }
        else
        {
            counted["name"] = name;
        }
    }

    [Test]
    public void B2ThePersonsWordDraftIsNoBlankDocument()
    {
        JsonObject view = RealWordDraft();
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMissionWindow.StatusCountShowsContent(view), Is.True);
            Assert.That(ComputerUseMissionWindow.BlankDocumentShown(view), Is.False);
            Assert.That(ComputerUseMissionWindow.BlankDocumentAlready("Documento1", view, []), Is.False);
        });
    }

    [Test]
    public void B2AnUnreadDocumentWithNoCountIsNotTakenAsEmpty()
    {
        JsonObject view = RealWordDraft();
        SetCount(view, null);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMissionWindow.StatusCountShowsContent(view), Is.Null);
            Assert.That(ComputerUseMissionWindow.BlankDocumentShown(view), Is.False);
        });
    }

    [Test]
    public void ContracaseB2TheSameWordViewCountingZeroIsBlank()
    {
        JsonObject view = RealWordDraft();
        SetCount(view, "Mensaje de estado Documento1: 0 caracteres (valor aproximado).");
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMissionWindow.StatusCountShowsContent(view), Is.False);
            Assert.That(ComputerUseMissionWindow.BlankDocumentShown(view), Is.True);
            Assert.That(ComputerUseMissionWindow.BlankDocumentAlready("Documento1", view, []), Is.True);
        });
    }

    [Test]
    public void B3APlaceWhereTheLaunchLeftTheApplicationIsNeverAlready()
    {
        var launched = new JsonObject { ["steps"] = new JsonArray(new JsonObject { ["operation"] = "app.open", ["ok"] = true, ["alreadyRunning"] = false }) };
        var running = new JsonObject { ["steps"] = new JsonArray(new JsonObject { ["operation"] = "app.open", ["ok"] = true, ["alreadyRunning"] = true }) };
        Assert.Multiple(() =>
        {
            Assert.That(OperationFloor.MissionLaunched(launched), Is.True);
            Assert.That(OperationFloor.MissionLaunched(running), Is.False, "contracase: the application was already open");
        });
    }

    [Test]
    public void B3AnUnreadCanvasIsNeverBlankAndAReadEmptyDocumentIs()
    {
        var frame = new JsonObject { ["x"] = 0, ["y"] = 0, ["w"] = 1600, ["h"] = 900 };
        var canvas = new JsonObject
        {
            ["window"] = new JsonObject { ["title"] = "Sin título - Paint", ["process"] = "mspaint", ["rect"] = frame.DeepClone() },
            ["controls"] = new JsonArray(new JsonObject { ["i"] = 0, ["kind"] = "Pane", ["name"] = "Lienzo" }),
        };
        var empty = new JsonObject
        {
            ["window"] = new JsonObject { ["title"] = "Sin título - Bloc de notas", ["process"] = "Notepad", ["rect"] = frame.DeepClone() },
            ["controls"] = new JsonArray(new JsonObject { ["i"] = 0, ["kind"] = "Document", ["name"] = "Editor de texto", ["value"] = "" }),
        };
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMissionWindow.DocumentContentShown(canvas), Is.Null);
            Assert.That(ComputerUseMissionWindow.BlankDocumentShown(canvas), Is.False);
            Assert.That(ComputerUseMissionWindow.DocumentContentShown(empty), Is.False, "contracase: read empty");
            Assert.That(ComputerUseMissionWindow.BlankDocumentShown(empty), Is.True);
        });
    }

    // Revisión 1 (B4): «ir a opciones; luego ir a general; luego ir a privacidad»: the click on «Opciones» opened the
    // dialog with «General» selected; «General» was reached with no act of its own, after an act of the mission.
    private static JsonObject Options()
    {
        static JsonObject Part(string goal, string satisfied, bool acted, string arrived) => new()
        {
            ["goal"] = goal,
            ["application"] = "Steam",
            ["reached"] = true,
            ["satisfiedBy"] = satisfied,
            ["acted"] = acted,
            ["arrivedAs"] = arrived,
        };

        return new JsonObject
        {
            ["steps"] = new JsonArray(
                new JsonObject { ["operation"] = "app.open", ["ok"] = true, ["alreadyRunning"] = true, ["subgoal"] = 0 },
                new JsonObject { ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "opciones", ["subgoal"] = 0 },
                new JsonObject { ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "privacidad", ["subgoal"] = 2 }),
            ["subgoals"] = new JsonArray(
                Part("ir a opciones", "title:opciones", true, "Opciones"),
                Part("ir a general", "control:general:selected", false, "General"),
                Part("ir a privacidad", "control:privacidad:selected", true, "Privacidad")),
        };
    }

    [Test]
    public void B4APlaceAnEarlierClickOpenedWasNeverAlready()
    {
        JsonObject observed = Options();
        List<JsonObject> parts = ((JsonArray)observed["subgoals"]!).OfType<JsonObject>().ToList();
        JsonObject stepsOnly = Options();
        List<JsonObject> unmarked = ((JsonArray)stepsOnly["subgoals"]!).OfType<JsonObject>().ToList();
        unmarked[0]["acted"] = false;
        Assert.Multiple(() =>
        {
            Assert.That(OperationFloor.MissionActedUntil(observed, parts, 1), Is.True, "the earlier part acted");
            Assert.That(OperationFloor.MissionActedUntil(stepsOnly, unmarked, 1), Is.True, "the click step of part 0");
            Assert.That(OperationFloor.MissionActedUntil(stepsOnly, unmarked, 0), Is.True, "part 0's own click");
        });
    }

    [Test]
    public void ContracaseB4NoActBeforeThePartClosedKeepsItAlready()
    {
        // x10's shape: the first part reached with no act; the only click is a later part's.
        var observed = new JsonObject
        {
            ["steps"] = new JsonArray(
                new JsonObject { ["operation"] = "app.open", ["ok"] = true, ["alreadyRunning"] = true, ["subgoal"] = 0 },
                new JsonObject { ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "tienda", ["subgoal"] = 1 }),
        };
        var parts = new List<JsonObject>
        {
            new() { ["goal"] = "ir a biblioteca", ["acted"] = false },
            new() { ["goal"] = "ir a tienda", ["acted"] = true },
        };
        Assert.That(OperationFloor.MissionActedUntil(observed, parts, 0), Is.False);
    }
}
