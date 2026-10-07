using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// The shell side of the computer-use engine that needs no window
/// (documentacion/computer-use/CONTRATO_VISTA_ACCION.md): the deterministic
/// success check (§4.3), what the mind receives (§4.4), the confirmed-step
/// resume (§2.1) and the procedure memory (§5).
/// </summary>
[TestFixture]
public sealed class ComputerUseMissionTests
{
    private static JsonObject View(string json) => (JsonObject)JsonNode.Parse(json)!;

    private static readonly string SteamView = """
        {
          "window": {"title": "Steam", "process": "steamwebhelper", "processId": 12, "hwnd": 5,
                     "rect": {"x": 0, "y": 0, "w": 800, "h": 600}, "focused": null},
          "controls": [
            {"i": 0, "kind": "Button", "name": "Tienda", "id": "1.2", "state": "", "value": null, "rect": {"x": 10, "y": 10, "w": 60, "h": 20}, "zone": "TL", "color": "gray"},
            {"i": 1, "kind": "Button", "name": "Biblioteca", "id": "1.3", "state": "selected", "value": null, "rect": {"x": 80, "y": 10, "w": 60, "h": 20}, "zone": "TL", "color": "blue"},
            {"i": 2, "kind": "TabItem", "name": "Pestaña 1", "id": "1.4", "state": "", "value": null, "rect": null, "zone": "T", "color": "", "repeated": 2},
            {"i": 3, "kind": "Edit", "name": "Pantalla", "id": "1.5", "state": "readonly", "value": "La pantalla muestra 84", "rect": null, "zone": "C", "color": ""}
          ],
          "controlCount": 4,
          "text": {"T": ["TIENDA", "BIBLIOTECA"], "C": ["12 × 7 =", "84"]},
          "surface": "abc",
          "elapsedMs": {"uia": 100, "ocr": 500, "color": 10, "total": 620},
          "authority": "windows_uia_snapshot_ocr_zones"
        }
        """;

    [TestCase("control:Biblioteca:selected", true, "control:Biblioteca:selected")]
    [TestCase("control:biblioteca", true, "control:biblioteca")]
    [TestCase("control:Tienda:selected", false, null)]
    [TestCase("text:BIBLIOTECA", true, "text:BIBLIOTECA")]
    [TestCase("text:84", true, "text:84")]
    [TestCase("title:steam", true, "title:steam")]
    [TestCase("process:steam", true, "process:steam")]
    [TestCase("process:discord", false, null)]
    [TestCase("count:TabItem<=1", false, null)]
    [TestCase("count:TabItem<=3", true, "count:TabItem<=3")]
    [TestCase("count:TabItem==3", true, "count:TabItem==3")]
    [TestCase("value:Pantalla=84", true, "value:Pantalla=84")]
    [TestCase("process:discord|text:84", true, "text:84")]
    [TestCase("process:steam&control:Biblioteca:selected", true, "process:steam&control:Biblioteca:selected")]
    [TestCase("process:steam&control:Tienda:selected", false, null)]
    [TestCase("", false, null)]
    [TestCase("nonsense", false, null)]
    [TestCase("file:C:\\definitely\\not\\here.txt", false, null)]
    public void SuccessCheckIsEvaluatedOverTheViewWithoutAModel(string check, bool expected, string? satisfiedBy)
    {
        bool reached = ComputerUseSuccessCheck.Evaluate(check, View(SteamView), [], out string? by);
        Assert.Multiple(() =>
        {
            Assert.That(reached, Is.EqualTo(expected));
            Assert.That(by, Is.EqualTo(satisfiedBy));
        });
    }

    [Test]
    public void ALongTabTitleIsNamedByTheSiteItEndsWith()
    {
        JsonObject view = View("""
            {"window": {"title": "Never Gonna Give You Up - YouTube - Opera", "process": "opera", "processId": 7},
             "controls": [
               {"i": 0, "kind": "TabItem", "name": "Correo - Bandeja de entrada", "state": ""},
               {"i": 1, "kind": "TabItem", "name": "Never Gonna Give You Up - YouTube", "state": "selected"}
             ]}
            """);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:youtube:selected", view, [], out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:correo:selected", view, [], out _), Is.False);
        });
    }

    // Measured on Steam (CEF, one control): clicking «BIBLIOTECA» first opened its menu, three new lines of twenty-five;
    // only the library page itself replaces most of the written text.
    [Test]
    public void APlaceIsReachedWhenMostOfTheWrittenTextIsNewNotWhenAMenuOpens()
    {
        const string Store = """["TIENDA", "BIBLIOTECA COMUNIDAD", "https://store.steampowered.com/", "Explorar", "Buscar en la tienda", "REBAJAS DE OTOÑO", "Lista de deseados"]""";
        JsonArray clicked = [new JsonObject { ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "biblioteca" }];
        JsonObject menu = View("""
            {"window": {"title": "Steam"}, "controls": [],
             "text": {"TL": ["TIENDA", "BIBLIOTECA COMUNIDAD", "https://store.steampowered.com/", "Explorar", "Pagina principal", "Colecciones"],
                      "C": ["Buscar en la tienda", "REBAJAS DE OTOÑO", "Lista de deseados"]}}
            """);
        JsonObject library = View("""
            {"window": {"title": "Steam"}, "controls": [],
             "text": {"TL": ["TIENDA", "BIBLIOTECA COMUNIDAD", "Pagina principal", "Juegos y Software", "FAVORITOS (324)"],
                      "C": ["TUS COLECCIONES", "INSTALADO LOCALMENTE"]}}
            """);
        foreach (JsonObject view in new[] { menu, library })
        {
            view["baselineText"] = ComputerUseSuccessCheck.TextLines(View("{\"text\": {\"TL\": " + Store + "}}"));
        }

        // Only a click that went there counts: one naming the place, or the entry picked from the menu a click on it
        // opened (even when that click itself did not verify); a click on anything else does not.
        JsonArray elsewhere = [new JsonObject { ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "Tienda" }];
        JsonArray throughItsMenu =
        [
            new JsonObject { ["operation"] = "input.visible.click", ["ok"] = false, ["label"] = "BIBLIOTECA" },
            new JsonObject { ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "Inicio" },
        ];
        JsonArray menuThenElsewhere =
        [
            new JsonObject { ["operation"] = "input.visible.click", ["ok"] = false, ["label"] = "BIBLIOTECA" },
            new JsonObject { ["operation"] = "input.key.press", ["ok"] = true, ["key"] = "escape" },
            new JsonObject { ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "Inicio" },
        ];
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:biblioteca", menu, clicked, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:biblioteca", library, clicked, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:biblioteca", library, [], out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:biblioteca", library, elsewhere, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:biblioteca", library, throughItsMenu, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:biblioteca", library, menuThenElsewhere, out _), Is.False);
        });
    }

    // A check held by verified receipts alone (a step done, a file) needs no new look; a term that reads the screen
    // does, even when another of its atoms is a receipt.
    [TestCase("stepDone:input.visible.click:biblioteca", true)]
    [TestCase("text:84|stepDone:input.visible.click:biblioteca", true)]
    [TestCase("stepDone:input.visible.click:biblioteca&text:84", false)]
    [TestCase("stepDone:input.key.press:enter", false)]
    [TestCase("control:Biblioteca", false)]
    [TestCase("", false)]
    public void ReceiptsAloneDecideOnlyTermsThatReadNoScreen(string check, bool expected)
    {
        JsonArray steps = [new JsonObject { ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "Biblioteca" }];
        Assert.That(ComputerUseSuccessCheck.EvaluateReceipts(check, steps, out _), Is.EqualTo(expected));
    }

    // «Did the screen change» compares the controls; the written text counts only on a window without a useful
    // accessible tree, where the provider always reads it. A look with OCR and one without compare equal.
    [Test]
    public void TheViewSignatureIgnoresTheTextWhenTheControlsDescribeTheScreen()
    {
        JsonObject withText = View(SteamView);
        JsonObject withoutText = View(SteamView);
        withoutText.Remove("text");
        JsonObject canvas = View("""{"window": {"title": "Steam"}, "controls": [{"i": 0, "kind": "Document", "name": "Steam"}], "text": {"C": ["TIENDA"]}}""");
        JsonObject canvasMoved = View("""{"window": {"title": "Steam"}, "controls": [{"i": 0, "kind": "Document", "name": "Steam"}], "text": {"C": ["BIBLIOTECA"]}}""");
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.ViewSignature(withText), Is.EqualTo(ComputerUseMission.ViewSignature(withoutText)));
            Assert.That(ComputerUseMission.ViewSignature(canvas), Is.Not.EqualTo(ComputerUseMission.ViewSignature(canvasMoved)));
        });
    }

    // Two false successes measured live: Steam's start-up window was the baseline and the store passed for the library;
    // Discord's Friends page passed for a channel because the channel's name was written in an activity card.
    [Test]
    public void APlaceIsMeasuredAgainstTheViewBeforeItsClickAndOnlyInAWindowWithoutATree()
    {
        JsonArray clicked = [new JsonObject { ["step"] = 2, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "biblioteca" }];
        JsonObject store = View("""
            {"window": {"title": "Steam"}, "controls": [],
             "text": {"TL": ["TIENDA", "BIBLIOTECA COMUNIDAD", "Pagina principal", "Colecciones", "Descargas", "Explorar", "REBAJAS DE OTOÑO"]}}
            """);
        store["baselineText"] = ComputerUseSuccessCheck.TextLines(View("""{"text": {"TL": ["Iniciar sesion en Steam", "Conectando"]}}"""));
        store["textBeforeClick"] = new JsonObject
        {
            ["2"] = ComputerUseSuccessCheck.TextLines(View("""{"text": {"TL": ["TIENDA", "BIBLIOTECA COMUNIDAD", "Explorar", "REBAJAS DE OTOÑO", "Lista de deseados"]}}""")),
        };
        JsonObject friends = View("""
            {"window": {"title": "Discord"},
             "controls": [{"i": 0, "kind": "TreeItem", "name": "Amigos", "state": "selected"}, {"i": 1, "kind": "Button", "name": "Choche Cotele!!!"}],
             "text": {"TL": ["Amigos", "En linea", "Choche", "Cotele!!!", "burrollegua", "Activo ahora"]}}
            """);
        JsonArray cardClick = [new JsonObject { ["step"] = 1, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "Choche Cotele!!!" }];
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:biblioteca", store, clicked, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:cotele", friends, cardClick, out _), Is.False);
        });
    }

    [Test]
    public void AClickOnThePlaceThatLeavesTheWindowAsItWasMeansThePlaceWasAlreadyOpen()
    {
        JsonArray clicked = [new JsonObject { ["step"] = 5, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "TIENDA" }];
        JsonObject store = View("""
            {"window": {"title": "Steam"}, "controls": [],
             "text": {"TL": ["TIENDA", "BIBLIOTECA COMUNIDAD", "Buscar en la tienda", "Explorar", "REBAJAS DE OTOÑO"]}}
            """);
        store["textBeforeClick"] = new JsonObject { ["5"] = ComputerUseSuccessCheck.TextLines(store) };
        JsonObject menu = View("""
            {"window": {"title": "Steam"}, "controls": [],
             "text": {"TL": ["TIENDA", "BIBLIOTECA COMUNIDAD", "Buscar en la tienda", "Explorar", "REBAJAS DE OTOÑO", "Destacados"]}}
            """);
        menu["textBeforeClick"] = new JsonObject { ["5"] = ComputerUseSuccessCheck.TextLines(store) };
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:tienda", store, clicked, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:tienda", menu, clicked, out _), Is.False, "one new line is a menu, not the place");
        });
    }

    [Test]
    public void TheMissionAdoptsTheWindowTheProviderResolvedForItsApplication()
    {
        var browser = new JsonObject();
        var foreground = new JsonObject();
        var unnamed = new JsonObject();
        JsonObject opera = View("""
            {"window": {"title": "Inicio - Opera", "process": "opera", "processId": 7, "requested": true}}
            """);
        ComputerUseMission.AdoptWindow(browser, "navegador", opera);
        ComputerUseMission.AdoptWindow(foreground, "navegador", View("""
            {"window": {"title": "navegador - Bloc de notas", "process": "notepad", "processId": 9, "requested": false}}
            """));
        ComputerUseMission.AdoptWindow(unnamed, null, opera);
        Assert.Multiple(() =>
        {
            Assert.That((int?)browser["processId"], Is.EqualTo(7));
            Assert.That(foreground["processId"], Is.Null, "a window that only held the front is never adopted");
            Assert.That(unnamed["processId"], Is.Null, "a sub-goal that names no application adopts nothing");
        });
    }

    [Test]
    public void ANameTypedIntoASearchNeverProvesTheItemButOneTypedIntoItsNameBoxDoes()
    {
        JsonObject view = View("""
            {"window": {"title": "Documentos", "process": "explorer"},
             "controls": [{"i": 0, "kind": "ListItem", "name": "baxy-prueba", "state": ""}], "text": {}}
            """);
        JsonArray Typed(string? into)
        {
            var step = new JsonObject { ["step"] = 1, ["operation"] = "input.text.type", ["text"] = "baxy-prueba", ["ok"] = true };
            if (into is not null)
            {
                step["into"] = into;
            }

            return [step];
        }

        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:baxy-prueba", view, Typed("Buscar en Documentos"), out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:baxy-prueba", view, Typed("Barra de direcciones"), out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:baxy-prueba", view, Typed(null), out _), Is.False, "where it went unknown, an echo");
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:baxy-prueba", view, Typed("Nombre"), out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:baxy-prueba", view, [], out _), Is.True);
        });
    }

    [Test]
    public void StepDoneNeedsAVerifiedStepOfThatOperationAndArgument()
    {
        var steps = new JsonArray
        {
            new JsonObject { ["step"] = 1, ["operation"] = "app.open", ["ok"] = true },
            new JsonObject { ["step"] = 2, ["operation"] = "input.visible.click", ["label"] = "Biblioteca", ["ok"] = true },
            new JsonObject { ["step"] = 3, ["operation"] = "input.key.press", ["key"] = "enter", ["ok"] = false },
        };
        JsonObject view = View(SteamView);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.visible.click:biblioteca", view, steps, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.visible.click:tienda", view, steps, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:app.open", view, steps, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.key.press:enter", view, steps, out _), Is.False);
        });
    }

    [Test]
    public void TheMindReceivesIndicesNamesStatesZonesColoursAndTextButNoIdentitiesOrHashes()
    {
        JsonObject compact = ComputerUseMission.CompactForTheMind(View(SteamView));
        string serialized = compact.ToJsonString();
        Assert.Multiple(() =>
        {
            Assert.That((string?)compact["window"]!["title"], Is.EqualTo("Steam"));
            Assert.That(compact["controls"]!.AsArray(), Has.Count.EqualTo(4));
            Assert.That((string?)compact["controls"]![1]!["name"], Is.EqualTo("Biblioteca"));
            Assert.That((string?)compact["controls"]![1]!["state"], Is.EqualTo("selected"));
            Assert.That((string?)compact["controls"]![1]!["color"], Is.EqualTo("blue"));
            Assert.That((int?)compact["controls"]![2]!["repeated"], Is.EqualTo(2));
            Assert.That(serialized, Does.Not.Contain("\"id\""));
            Assert.That(serialized, Does.Not.Contain("surface"));
            Assert.That(serialized, Does.Not.Contain("rect"));
            Assert.That((string?)compact["text"]!["C"]![0], Is.EqualTo("12 × 7 ="));
        });
    }

    [Test]
    public void AConfirmedPrimitiveJoinsTheMissionStepsAndMarksAJoinedVoiceChannel()
    {
        var execution = new PendingMindPlanExecution(
            "ve a Cotele en Discord",
            [new MindPlanStep("step_1", ComputerUseMission.OperationName, "ir a Cotele", [], "literal", new JsonObject { ["goal"] = "ir a Cotele" })])
        {
            ComputerUse = new JsonObject
            {
                ["goal"] = "ir a Cotele",
                ["steps"] = new JsonArray(),
                ["pendingStep"] = new JsonObject { ["step"] = 1, ["operation"] = "input.visible.click", ["label"] = "Cotele (canal de voz)", ["source"] = "model" },
            },
        };
        PreparedOperation click = PreparedOperation.Create("input.visible.click", new JsonObject { ["label"] = "Cotele (canal de voz)" });
        var response = new Baxy.Contracts.OperationResponse(
            Baxy.Contracts.ProtocolTypes.OperationResponse, click.InvocationId, click.MissionId, click.InvocationId,
            Baxy.Contracts.OperationStatuses.Completed, "{}", true, false,
            System.Text.Json.JsonDocument.Parse("""{"name":"Cotele (canal de voz)","selected":true,"cascadeStage":"uia"}""").RootElement, null);

        ComputerUseMission.RecordConfirmedStep(execution, click, response);

        JsonObject state = execution.ComputerUse!;
        Assert.Multiple(() =>
        {
            Assert.That(state["pendingStep"], Is.Null);
            Assert.That(state["steps"]!.AsArray(), Has.Count.EqualTo(1));
            Assert.That((bool?)state["steps"]![0]!["ok"], Is.True);
            Assert.That((bool?)state["steps"]![0]!["confirmed"], Is.True);
            Assert.That((bool?)state["steps"]![0]!["selected"], Is.True);
            Assert.That((bool?)state["joined"], Is.True);
        });
    }

    // Sending, publishing or deleting is confirmed too, but only a click that joins a channel, a call or a meeting
    // lets the final say the person joined.
    [TestCase("Enviar", false)]
    [TestCase("Publicar", false)]
    [TestCase("Join meeting", true)]
    [TestCase("General, voice channel", true)]
    public void OnlyAConfirmedJoinMarksTheMissionJoined(string label, bool joined)
    {
        var execution = new PendingMindPlanExecution(
            "haz clic",
            [new MindPlanStep("step_1", ComputerUseMission.OperationName, "clic", [], "literal", new JsonObject { ["goal"] = "clic" })])
        {
            ComputerUse = new JsonObject { ["goal"] = "clic", ["steps"] = new JsonArray() },
        };
        PreparedOperation click = PreparedOperation.Create("input.visible.click", new JsonObject { ["label"] = label });
        var response = new Baxy.Contracts.OperationResponse(
            Baxy.Contracts.ProtocolTypes.OperationResponse, click.InvocationId, click.MissionId, click.InvocationId,
            Baxy.Contracts.OperationStatuses.Completed, "{}", true, false,
            System.Text.Json.JsonDocument.Parse("""{"surfaceChanged":true}""").RootElement, null);

        ComputerUseMission.RecordConfirmedStep(execution, click, response);

        Assert.That((bool?)execution.ComputerUse!["joined"] == true, Is.EqualTo(joined));
    }

    [Test]
    public void ProceduresLearnAReachedMissionAndReplayItByKey()
    {
        string directory = Path.Combine(Path.GetTempPath(), "baxy-cu-procedures-" + Guid.NewGuid().ToString("N"));
        try
        {
            var procedures = new ComputerUseProcedures(Path.Combine(directory, "procedures.v1.json"));
            Assert.That(procedures.Find("Steam", "ir a la biblioteca"), Is.Null);
            var state = new JsonObject
            {
                ["goal"] = "ir a la biblioteca",
                ["application"] = "Steam",
                ["successCheck"] = "stepDone:input.visible.click:biblioteca",
                ["elapsedMs"] = 6100L,
                ["modelMs"] = 2400L,
            };
            var steps = new JsonArray
            {
                new JsonObject { ["step"] = 1, ["operation"] = "app.open", ["appId"] = "Steam", ["ok"] = true, ["source"] = "model" },
                new JsonObject { ["step"] = 2, ["operation"] = "input.visible.click", ["label"] = "Biblioteca", ["index"] = 1, ["ok"] = true, ["surfaceChanged"] = true, ["source"] = "model" },
            };
            // Contract §5 (measured on Steam: a dropped failed click left a meaningless procedure): a mission with a
            // failed step is not learned; an opening that did not verify does not count as failed.
            var withAFailure = (JsonArray)steps.DeepClone();
            withAFailure.Add(new JsonObject { ["step"] = 3, ["operation"] = "input.scroll", ["direction"] = "down", ["ok"] = false, ["source"] = "model" });
            Assert.That(procedures.Learn(state, withAFailure), Is.EqualTo("none"));

            Assert.That(procedures.Learn(state, steps), Is.EqualTo("learned"));

            var reloaded = new ComputerUseProcedures(Path.Combine(directory, "procedures.v1.json"));
            JsonObject? found = reloaded.Find("steam", "Por favor, ir a la biblioteca.");
            Assert.That(found, Is.Not.Null);
            JsonArray recorded = found!["steps"]!.AsArray();
            Assert.Multiple(() =>
            {
                Assert.That(recorded, Has.Count.EqualTo(2));
                Assert.That((string?)recorded[1]!["operation"], Is.EqualTo("input.visible.click"));
                Assert.That((string?)recorded[1]!["arguments"]!["label"], Is.EqualTo("Biblioteca"));
                Assert.That(recorded[1]!["arguments"]!["index"], Is.Null, "an index belongs to one view, never to a procedure");
                Assert.That((string?)recorded[1]!["expect"], Is.EqualTo("surfaceChanged"));
                Assert.That((long?)found["lastModelMs"], Is.EqualTo(2400L));
            });

            var replayState = new JsonObject
            {
                ["goal"] = "ir a la biblioteca",
                ["application"] = "Steam",
                ["procedureKey"] = ComputerUseProcedures.Key("Steam", "ir a la biblioteca"),
                ["elapsedMs"] = 900L,
                ["modelMs"] = 0L,
            };
            var replaySteps = new JsonArray
            {
                new JsonObject { ["step"] = 1, ["operation"] = "app.open", ["ok"] = true, ["source"] = "procedure" },
                new JsonObject { ["step"] = 2, ["operation"] = "input.visible.click", ["label"] = "Biblioteca", ["ok"] = true, ["source"] = "procedure" },
            };
            Assert.That(reloaded.Learn(replayState, replaySteps), Is.EqualTo("replayed"));
            JsonObject again = reloaded.Find("Steam", "ir a la biblioteca")!;
            Assert.Multiple(() =>
            {
                Assert.That((int?)again["replays"], Is.EqualTo(1));
                Assert.That((long?)again["lastReplayMs"], Is.EqualTo(900L));
            });
        }
        finally
        {
            if (Directory.Exists(directory))
            {
                Directory.Delete(directory, recursive: true);
            }
        }
    }

    [TestCase("Steam", "Ir a la biblioteca", "steam|ir a la biblioteca")]
    [TestCase("steam", "por favor ir a la biblioteca.", "steam|ir a la biblioteca")]
    [TestCase(null, "Activá el modo avión", "|activa el modo avion")]
    public void ProcedureKeysFoldTheApplicationAndTheGoal(string? application, string goal, string expected)
    {
        Assert.That(ComputerUseProcedures.Key(application, goal), Is.EqualTo(expected));
    }
}
