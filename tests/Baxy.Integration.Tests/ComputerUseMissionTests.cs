using System.Globalization;
using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// The shell side of the computer-use engine that needs no window
/// (documentacion/computer-use/CONTRATO_VISTA_ACCION.md): the deterministic
/// success check (§4.3), what the mind receives (§4.4), the confirmed-step
/// resume (§2.1).
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

    // Ronda 20b, revisión 1 (bloqueante 4): a 3000×1000 image with the aspect lock on, set to 500 high, moved the width
    // to 1500; «1500» held «value:horizontal=500» by containment and the form was accepted at 1500×500. A number holds
    // only within digit bounds; contracases: a value the window formats («500 px», «500px») and a text value.
    [TestCase("1500", "500", false)]
    [TestCase("5000", "500", false)]
    [TestCase("500,5", "500", false)]
    [TestCase("2.500", "500", false)]
    [TestCase("500", "500", true)]
    [TestCase("500 px", "500", true)]
    [TestCase("500px", "500", true)]
    [TestCase("ancho: 500", "500", true)]
    [TestCase("12,5 pt", "12,5", true)]
    [TestCase("hola mundo", "hola", true)]
    // Revisión 2 (bloqueante 2): the decimal zeros a window formats the number with hold it (a position and size
    // dialog, a numeric box with decimal places); contracases: a decimal that is not zero, a longer number.
    [TestCase("5,00 cm", "5", true)]
    [TestCase("500,00", "500", true)]
    [TestCase("500.0 px", "500", true)]
    [TestCase("12,50 pt", "12,5", true)]
    [TestCase("500,05", "500", false)]
    [TestCase("1500,00", "500", false)]
    [TestCase("12,55", "12,5", false)]
    public void ANumberHoldsInAFieldOnlyWithinDigitBounds(string shown, string value, bool holds)
    {
        JsonObject view = View($$"""{"controls": [{"i": 1, "kind": "Edit", "name": "Horizontal", "value": "{{shown}}"}]}""");
        Assert.That(ComputerUseSuccessCheck.Evaluate($"value:horizontal={value}", view, [], out _), Is.EqualTo(holds));
    }

    // Integration of round 2: «file:<ruta>» proves a save only when the sub-goal wrote it, so it exists and was last
    // written since the sub-goal began. Counter-cases: a file of that name that was already there (an hour old), and a
    // check evaluated with no start to compare against.
    [Test]
    public void AFileProvesTheActOnlyWhenWrittenSinceTheSubgoalBegan()
    {
        string folder = Path.Combine(Path.GetTempPath(), "baxy-file-atom-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(folder);
        try
        {
            string fresh = Path.Combine(folder, "baxy-x.txt");
            string old = Path.Combine(folder, "viejo.txt");
            DateTimeOffset began = DateTimeOffset.UtcNow;
            File.WriteAllText(fresh, "hola");
            File.WriteAllText(old, "antes");
            File.SetLastWriteTimeUtc(old, began.UtcDateTime.AddHours(-1));
            var state = new JsonObject { ["subgoalStartedUtc"] = began.ToString("O", CultureInfo.InvariantCulture) };
            DateTimeOffset? since = ComputerUseSuccessCheck.SubgoalStarted(state);
            var view = new JsonObject();

            Assert.Multiple(() =>
            {
                Assert.That(since, Is.EqualTo(began));
                Assert.That(ComputerUseSuccessCheck.Evaluate("file:" + fresh, view, [], out string? by, notBefore: since), Is.True);
                Assert.That(by, Is.EqualTo("file:" + fresh));
                Assert.That(ComputerUseSuccessCheck.EvaluateReceipts("file:" + fresh, [], out _, notBefore: since), Is.True);
                Assert.That(ComputerUseSuccessCheck.Evaluate("file:" + old, view, [], out _, notBefore: since), Is.False);
                Assert.That(ComputerUseSuccessCheck.EvaluateReceipts("file:" + old, [], out _, notBefore: since), Is.False);
                Assert.That(ComputerUseSuccessCheck.Evaluate("file:" + fresh, view, [], out _), Is.False);
                // Without the sub-goal's own start, the mission's start counts.
                var mission = new JsonObject { ["startedUtc"] = began.ToString("O", CultureInfo.InvariantCulture) };
                Assert.That(ComputerUseSuccessCheck.SubgoalStarted(mission), Is.EqualTo(began));
            });
        }
        finally
        {
            Directory.Delete(folder, recursive: true);
        }
    }

    [Test]
    public void APlaceIsCurrentWhenItsNavigationItemIsSelectedNeverAContentItemMerelyChosen()
    {
        // Explorer's Home view (measured 2026-10-07): one click on the «Descargas» folder of the content list selects
        // it and opens nothing; the navigation tree in the side column is what tells the place shown.
        JsonObject chosen = View("""
            {"window": {"title": "Inicio - Explorador de archivos", "process": "explorer", "processId": 7},
             "controls": [
               {"i": 0, "kind": "TreeItem", "name": "Inicio", "state": "selected", "zone": "L"},
               {"i": 1, "kind": "TreeItem", "name": "Descargas", "state": "", "zone": "L"},
               {"i": 2, "kind": "ListItem", "name": "Descargas", "state": "selected", "zone": "T"},
               {"i": 3, "kind": "DataItem", "name": "Imágenes", "state": "selected", "zone": "C"}
             ]}
            """);
        JsonObject side = View("""
            {"window": {"title": "Reloj", "process": "applicationframehost", "processId": 8},
             "controls": [
               {"i": 0, "kind": "ListItem", "name": "Cronómetro", "state": "selected", "zone": "L"},
               {"i": 1, "kind": "ListItem", "name": "Alarma", "state": "", "zone": "TL"}
             ]}
            """);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:descargas:current", chosen, [], out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:imagenes:current", chosen, [], out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:inicio:current", chosen, [], out _), Is.True);
            // Choosing an item is still «selected»: the state a choice asks for.
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:descargas:selected", chosen, [], out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:cronometro:current", side, [], out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:alarma:current", side, [], out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.IsContentItem((JsonObject)chosen["controls"]![2]!), Is.True);
            Assert.That(ComputerUseSuccessCheck.IsContentItem((JsonObject)side["controls"]![0]!), Is.False);
        });
    }

    // Explorer's Home on a maximized window (measured 2026-10-07): the first tiles of a row of folders sit in the left
    // third, the next ones in the centre; a tile merely selected there is content, not the place shown. A side list has
    // nothing beside it in its row; without rectangles the zone alone decides.
    [Test]
    public void ATileInTheLeftColumnIsContentWhenItsRowGoesOnOutOfIt()
    {
        JsonObject home = View("""
            {"window": {"title": "Inicio - Explorador de archivos", "process": "explorer", "processId": 7},
             "controls": [
               {"i": 0, "kind": "TreeItem", "name": "Inicio", "state": "selected", "zone": "L", "rect": {"x": 0, "y": 150, "w": 250, "h": 30}},
               {"i": 1, "kind": "ListItem", "name": "Escritorio", "state": "", "zone": "L", "rect": {"x": 300, "y": 200, "w": 180, "h": 100}},
               {"i": 2, "kind": "ListItem", "name": "Descargas", "state": "selected", "zone": "L", "rect": {"x": 500, "y": 200, "w": 180, "h": 100}},
               {"i": 3, "kind": "ListItem", "name": "Documentos", "state": "", "zone": "C", "rect": {"x": 700, "y": 200, "w": 180, "h": 100}},
               {"i": 4, "kind": "ListItem", "name": "Imágenes", "state": "", "zone": "C", "rect": {"x": 900, "y": 205, "w": 180, "h": 100}}
             ]}
            """);
        JsonObject settings = View("""
            {"window": {"title": "Configuración", "process": "systemsettings", "processId": 9},
             "controls": [
               {"i": 0, "kind": "ListItem", "name": "Sistema", "state": "", "zone": "L", "rect": {"x": 0, "y": 150, "w": 250, "h": 40}},
               {"i": 1, "kind": "ListItem", "name": "Personalización", "state": "selected", "zone": "L", "rect": {"x": 0, "y": 200, "w": 250, "h": 40}},
               {"i": 2, "kind": "ListItem", "name": "Fondo", "state": "", "zone": "C", "rect": {"x": 300, "y": 300, "w": 600, "h": 60}},
               {"i": 3, "kind": "ListItem", "name": "Colores", "state": "", "zone": "C", "rect": {"x": 300, "y": 380, "w": 600, "h": 60}}
             ]}
            """);
        JsonObject withoutRects = View("""
            {"window": {"title": "Reloj", "process": "applicationframehost", "processId": 8},
             "controls": [
               {"i": 0, "kind": "ListItem", "name": "Cronómetro", "state": "selected", "zone": "L"},
               {"i": 1, "kind": "ListItem", "name": "Alarma", "state": "", "zone": "C"}
             ]}
            """);
        var homeControls = (JsonArray)home["controls"]!;
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:descargas:current", home, [], out _), Is.False,
                "a tile selected in a grid that starts in the left third is not the place shown");
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:descargas:selected", home, [], out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:inicio:current", home, [], out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.IsContentItem((JsonObject)homeControls[1]!, homeControls), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:personalizacion:current", settings, [], out _), Is.True,
                "a side list with nothing beside it in its row is navigation");
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:cronometro:current", withoutRects, [], out _), Is.True);
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

    // Teclas sin efecto (r9, v3-37: Ctrl+K on the Terminal left the view as it was, then Escape, then the mission
    // stopped): the first look after a verified act that keeps the view's signature marks the act «sameView», and the
    // mind's history carries it. A look that changed, a failed act, a look behind (the person brought their window up:
    // revisión D, H4) and a later look of the same step leave it as it was.
    [Test]
    public void TheFirstLookAfterAnActThatChangedNothingMarksItSameViewForTheMind()
    {
        string before = ComputerUseMission.ViewSignature(View(SteamView));
        JsonObject moved = View(SteamView);
        ((JsonObject)((JsonArray)moved["controls"]!)[1]!)["state"] = "";
        string after = ComputerUseMission.ViewSignature(moved);

        JsonArray Steps(bool ok) =>
        [
            new JsonObject { ["step"] = 1, ["operation"] = "app.open", ["appId"] = "Terminal", ["ok"] = true },
            new JsonObject { ["step"] = 2, ["operation"] = "input.key.press", ["key"] = "ctrl_k", ["ok"] = ok, ["method"] = "keyboard" },
        ];

        JsonArray same = Steps(ok: true);
        var state = new JsonObject { ["lastSignature"] = before };
        ComputerUseMission.MarkSameView(state, same, 0, before, lookedBehind: false);
        JsonArray changed = Steps(ok: true);
        ComputerUseMission.MarkSameView(new JsonObject { ["lastSignature"] = before }, changed, 0, after, lookedBehind: false);
        JsonArray failed = Steps(ok: false);
        ComputerUseMission.MarkSameView(new JsonObject { ["lastSignature"] = before }, failed, 0, before, lookedBehind: false);
        JsonArray behind = Steps(ok: true);
        ComputerUseMission.MarkSameView(new JsonObject { ["lastSignature"] = before }, behind, 0, before, lookedBehind: true);
        JsonArray later = Steps(ok: true);
        var looked = new JsonObject { ["lastSignature"] = before };
        ComputerUseMission.MarkSameView(looked, later, 0, after, lookedBehind: false);
        looked["lastSignature"] = after;
        ComputerUseMission.MarkSameView(looked, later, 0, after, lookedBehind: false);

        JsonArray history = ComputerUseMission.HistoryForMind(same, 0);
        Assert.Multiple(() =>
        {
            Assert.That((bool?)same[1]!["sameView"], Is.True);
            Assert.That((bool?)history[1]!["sameView"], Is.True);
            Assert.That(changed[1]!["sameView"], Is.Null);
            Assert.That(failed[1]!["sameView"], Is.Null);
            Assert.That(behind[1]!["sameView"], Is.Null, "a look behind (revisión D, H4) proves nothing");
            Assert.That(later[1]!["sameView"], Is.Null, "only the first look after the act judges it");
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
    public void AClickOnThePlaceThatLeavesTheWindowAsItWasIsNotProofOfArriving()
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
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:tienda", store, clicked, out _), Is.False, "the page reached may not be drawn yet");
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:tienda", menu, clicked, out _), Is.False, "one new line is a menu, not the place");
        });
    }

    // Live 2026-10-07 (v2-s12, v2-c17): Steam already on its library, a click on «BIBLIOTECA» only opened its
    // menu under it. Not arriving (the same reads on another page whose word only opened a menu), but said honestly as
    // «parece que ya estabas»; a click on another word, a page that changed or a tree never are. A covered window is
    // (v3 point 0): its text is read from the window's own drawing, never from the cover on screen.
    [Test]
    public void AClickOnThePlacesOwnNameThatOnlyOpensItsMenuIsProbablyAlreadyThereNeverArrived()
    {
        string[] library = ["TIENDA", "BIBLIOTECA", "COMUNIDAD", "Esta semana", "Juegos recientes", "Todos (324)", "Cuphead",
            "Hades", "Celeste", "Hollow Knight", "Instalado localmente", "Favoritos"];
        JsonObject Look(IEnumerable<string> lines, string? extra = null)
        {
            var text = new JsonArray([.. lines.Select(line => (JsonNode?)JsonValue.Create(line))]);
            var view = new JsonObject
            {
                ["window"] = new JsonObject { ["title"] = "Steam" },
                ["controls"] = new JsonArray(new JsonObject { ["i"] = 0, ["kind"] = "Document", ["name"] = "Steam" }),
                ["text"] = new JsonObject { ["TL"] = text },
            };
            if (extra is not null)
            {
                view["window"]!["coveredBy"] = new JsonObject { ["title"] = extra };
            }

            return view;
        }

        JsonArray Click(string label) =>
        [
            new JsonObject { ["step"] = 1, ["operation"] = "app.open", ["ok"] = true },
            new JsonObject { ["step"] = 2, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = label },
        ];
        var state = new JsonObject
        {
            ["textBeforeClick"] = new JsonObject { ["2"] = ComputerUseSuccessCheck.TextLines(Look(library)) },
        };
        JsonObject menuOpen = Look([.. library, "Página principal", "Colecciones", "Descargas"]);
        JsonObject elsewhere = Look(["TIENDA", "BIBLIOTECA", "COMUNIDAD", "Destacados", "Ofertas especiales", "Explorar por categoría",
            "Lista de deseados", "Novedades", "Más vendidos", "Juegos gratuitos", "Página principal", "Colecciones"]);
        JsonObject tree = Look([.. library, "Página principal"]);
        tree["controls"] = new JsonArray(
            new JsonObject { ["i"] = 0, ["kind"] = "Button", ["name"] = "Biblioteca" },
            new JsonObject { ["i"] = 1, ["kind"] = "Button", ["name"] = "Tienda" });
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.ClickedPlaceLeftPageAsIs("Biblioteca", Click("biblioteca"), menuOpen, state), Is.True);
            Assert.That(ComputerUseSuccessCheck.ClickedPlaceLeftPageAsIs("Biblioteca", Click("biblioteca"), Look(library), state), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:biblioteca", menuOpen, Click("biblioteca"), out _), Is.False,
                "never told as arrived");
            Assert.That(ComputerUseSuccessCheck.ClickedPlaceLeftPageAsIs("Biblioteca", Click("tienda"), menuOpen, state), Is.False,
                "another word clicked");
            Assert.That(ComputerUseSuccessCheck.ClickedPlaceLeftPageAsIs("Biblioteca", Click("biblioteca"), elsewhere, state), Is.False,
                "the page changed");
            Assert.That(ComputerUseSuccessCheck.ClickedPlaceLeftPageAsIs("Biblioteca", Click("biblioteca"), Look(library, "Bloc de notas"), state), Is.True,
                "a covered window, read from its own drawing");
            Assert.That(ComputerUseSuccessCheck.ClickedPlaceLeftPageAsIs("Biblioteca", Click("biblioteca"), Look(ComputerUseSuccessCheck.TextLines(elsewhere).Select(line => (string?)line ?? string.Empty), "Bloc de notas"), state), Is.False,
                "a covered window whose page changed");
            Assert.That(ComputerUseSuccessCheck.ClickedPlaceLeftPageAsIs("Biblioteca", Click("biblioteca"), tree, state), Is.False,
                "a window with a tree");
            Assert.That(ComputerUseSuccessCheck.ClickedPlaceLeftPageAsIs("Biblioteca", Click("biblioteca"), menuOpen, new JsonObject()), Is.False,
                "the text before the click unknown");
        });
    }

    [Test]
    public void TypedTextIsNeverJudgedOnReceiptsAloneAndACutValueIsUnknown()
    {
        JsonArray typed = [new JsonObject { ["step"] = 2, ["operation"] = "input.text.type", ["ok"] = true, ["text"] = "lista: pan" }];
        JsonObject cut = View("""
            {"window": {"title": "Bloc de notas", "focused": {"kind": "Document", "name": "Editor de texto", "value": "VALUE"}}, "controls": []}
            """);
        cut["window"]!["focused"]!["value"] = new string('a', 120);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.EvaluateReceipts("stepDone:input.text.type", typed, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.EvaluateReceipts("stepDone:input.key.press:enter", typed, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.text.type", cut, typed, out _), Is.True);
        });
    }

    [Test]
    public void TheFinalSeesTheChosenValueTheQuestionIsAbout()
    {
        JsonObject colors = View("""
            {"window": {"title": "Configuración"}, "controls": [
              {"i": 0, "kind": "Edit", "name": "Buscar una opción", "value": ""},
              {"i": 1, "kind": "ListItem", "name": "Personalización", "state": "selected"},
              {"i": 2, "kind": "ListItem", "name": "Sistema"}, {"i": 3, "kind": "ListItem", "name": "Aplicaciones"},
              {"i": 4, "kind": "ComboBox", "name": "Elige tu modo", "value": "Oscuro"}]}
            """);
        JsonObject excerpt = ComputerUseMission.ScreenExcerpt(colors, "ir a colores; y responder: decime si el modo es claro u oscuro");
        JsonArray values = (JsonArray)excerpt["values"]!;
        Assert.Multiple(() =>
        {
            Assert.That((string?)values[0]!["name"], Is.EqualTo("Elige tu modo"));
            Assert.That((string?)values[0]!["value"], Is.EqualTo("Oscuro"));
            Assert.That(values.Any(value => (string?)value!["state"] == "selected"), Is.True);
        });
    }

    // Imprescindibles de mensajería (measured on redpc 2026-10-11, Discord's DM «Mensajes en Ron92» by UI Automation):
    // each message is a Group named «autor , texto , hora». With a question the excerpt keeps the last groups in the
    // view's order, for the mind to answer «qué me escribió Ron92» from; without one it adds nothing.
    [Test]
    public void AQuestionKeepsTheLastGroupsOfTheViewInItsOrder()
    {
        var controls = new JsonArray
        {
            new JsonObject { ["i"] = 0, ["kind"] = "Edit", ["name"] = "Enviar mensaje a @Ron92", ["value"] = "" },
            new JsonObject { ["i"] = 1, ["kind"] = "Group", ["name"] = "" },
        };
        for (int at = 0; at < 10; at++)
        {
            controls.Add(new JsonObject { ["i"] = at + 2, ["kind"] = "Group", ["name"] = $"Ron92 , mensaje {at} , 12:{at:00} p. m." });
        }

        controls.Add(new JsonObject { ["i"] = 12, ["kind"] = "Text", ["name"] = "RED Etiqueta del servidor: DEMO , no es un grupo , 01:12 p. m." });
        var chat = new JsonObject { ["window"] = new JsonObject { ["title"] = "@Ron92 - Discord" }, ["controls"] = controls };
        JsonObject asked = ComputerUseMission.ScreenExcerpt(chat, "ir a ron92; y responder: qué me escribió Ron92");
        JsonObject plain = ComputerUseMission.ScreenExcerpt(chat, "ir a ron92");
        JsonArray groups = (JsonArray)asked["groups"]!;
        Assert.Multiple(() =>
        {
            Assert.That(groups, Has.Count.EqualTo(ComputerUseMission.QuestionExcerptGroups));
            Assert.That((string?)groups[0], Is.EqualTo("Ron92 , mensaje 2 , 12:02 p. m."));
            Assert.That((string?)groups[^1], Is.EqualTo("Ron92 , mensaje 9 , 12:09 p. m."));
            // Counter-cases: no question, no groups; a Text is no group however it is named.
            Assert.That(plain.ContainsKey("groups"), Is.False);
            Assert.That(groups.Any(group => ((string?)group)!.Contains("no es un grupo")), Is.False);
        });
    }

    // Ronda 23, the look of live r21 v2-v3-62 (Seguridad de Windows, «Firewall y protección de red»): «Red privada
    // (activa)» was the eighth line read and the final named «Red de dominio».
    private const string FirewallPage = """
        {"window": {"title": "Seguridad de Windows", "process": "SecHealthUI"}, "controls": [
          {"i": 9, "kind": "ListItem", "name": "Firewall y protección de red", "state": "selected", "zone": "L"},
          {"i": 16, "kind": "Hyperlink", "name": "Red de dominio", "state": "focused", "zone": "TL"},
          {"i": 17, "kind": "Hyperlink", "name": "Red privada", "zone": "L"},
          {"i": 18, "kind": "Hyperlink", "name": "Red pública", "zone": "L"},
          {"i": 35, "kind": "Text", "name": "Red de dominio", "zone": "TL"},
          {"i": 36, "kind": "Text", "name": "El firewall está activado.", "zone": "TL"}],
         "text": {
          "TL": ["Seguridad de Windows", "«p) Firewall y protección de red", "(q» Firewall y protección de red",
                 "Quién y qué puede tener acceso a las redes.", "O", "Red de dominio", "EI firewall está activado."],
          "TR": ["x", "¿Tienes alguna pregunta?", "Obtener ayuda", "¿Quién me protege?", "Administrar proveedores"],
          "L": ["Red privada (activa)", "Red privada", "(activa)", "C? Red pública", "Red pública",
                "Permitir una aplicación a través de firewall"]}}
        """;

    [Test]
    public void AQuestionKeepsTheLinesThatBearOnItFirst()
    {
        JsonObject page = View(FirewallPage);
        string[] appeared = ["red privada (activa)", "(activa)", "red de dominio"];
        JsonObject asked = ComputerUseMission.ScreenExcerpt(
            page, "ir a firewall & network protection; y responder: tell me which network is active", appeared);
        JsonObject plain = ComputerUseMission.ScreenExcerpt(page, "ir a firewall & network protection", appeared);
        string[] askedLines = [.. ((JsonArray)asked["lines"]!).Select(line => (string?)line ?? string.Empty)];
        string[] plainLines = [.. ((JsonArray)plain["lines"]!).Select(line => (string?)line ?? string.Empty)];
        Assert.Multiple(() =>
        {
            // The line of the same root as «active» first, also between languages; up to twelve kept.
            Assert.That(askedLines[0], Is.EqualTo("Red privada (activa)"));
            Assert.That(askedLines[1], Is.EqualTo("(activa)"));
            Assert.That(askedLines, Has.Length.EqualTo(ComputerUseMission.QuestionExcerptLines));
            // Contracase: without a question, the first six as read (the marked network is not among them).
            Assert.That(plainLines, Has.Length.EqualTo(ComputerUseMission.ExcerptLines));
            Assert.That(plainLines[0], Is.EqualTo("Seguridad de Windows"));
            Assert.That(plainLines, Does.Not.Contain("Red privada (activa)"));
            // «activado» is no word of the root of «active».
            Assert.That(ComputerUseMission.SharesRoot("active", "activa"), Is.True);
            Assert.That(ComputerUseMission.SharesRoot("active", "activado"), Is.False);
            // Revision 2: nor is it of «activa» (a participle, not an inflection); «planes» and «activos» are.
            Assert.That(ComputerUseMission.SharesRoot("activa", "activado"), Is.False);
            Assert.That(ComputerUseMission.SharesRoot("activas", "activado"), Is.False);
            Assert.That(ComputerUseMission.SharesRoot("plan", "planes"), Is.True);
            Assert.That(ComputerUseMission.SharesRoot("activo", "activos"), Is.True);
        });
    }

    [Test]
    public void AGridRowTellsTheValueOfItsCellToAQuestion()
    {
        // Ronda 23, the table of live r21 v2-v3-46 (Información del sistema, «Componentes > Pantalla»).
        JsonObject table = View("""
            {"window": {"title": "Información del sistema", "process": "msinfo32"}, "controls": [
              {"i": 0, "kind": "TreeItem", "name": "Pantalla", "state": "selected"},
              {"i": 1, "kind": "HeaderItem", "name": "Elemento"}, {"i": 2, "kind": "HeaderItem", "name": "Valor"},
              {"i": 3, "kind": "DataItem", "name": "Nombre"},
              {"i": 4, "kind": "Text", "name": "Nombre"},
              {"i": 5, "kind": "Text", "name": "AMD Radeon(TM) Graphics"},
              {"i": 6, "kind": "DataItem", "name": "RAM de adaptador"},
              {"i": 7, "kind": "Text", "name": "RAM de adaptador"},
              {"i": 8, "kind": "Text", "name": "512,00 MB (536.870.912 bytes)"},
              {"i": 9, "kind": "DataItem", "name": "Resolución"},
              {"i": 10, "kind": "Text", "name": "Resolución"}]}
            """);
        JsonObject asked = ComputerUseMission.ScreenExcerpt(
            table, "ir a pantalla; y responder: decime qué tarjeta de video tengo");
        JsonObject plain = ComputerUseMission.ScreenExcerpt(table, "ir a pantalla");
        JsonObject[] values = [.. ((JsonArray)asked["values"]!).OfType<JsonObject>()];
        Assert.Multiple(() =>
        {
            Assert.That(values.Any(value => (string?)value["name"] == "Nombre" && (string?)value["value"] == "AMD Radeon(TM) Graphics"),
                Is.True);
            Assert.That(values.Any(value => (string?)value["name"] == "RAM de adaptador"
                && (string?)value["value"] == "512,00 MB (536.870.912 bytes)"), Is.True);
            // A row whose next cell is missing tells nothing.
            Assert.That(values.Any(value => (string?)value["name"] == "Resolución"), Is.False);
            // Contracase: without a question the rows are not read as values (the excerpt stays as before).
            Assert.That(((JsonArray)plain["values"]!).OfType<JsonObject>().Any(value => (string?)value["name"] == "Nombre"), Is.False);
            // A question's look reads the window's text (its answer is written there).
            Assert.That(ComputerUseMission.NeedsText(
                "ir a pantalla; y responder: decime qué tarjeta de video tengo", "Información del sistema", "control:pantalla:current", table),
                Is.True);
            Assert.That(ComputerUseMission.NeedsText("ir a pantalla", "Información del sistema", "control:pantalla:current", table),
                Is.False);
        });
    }

    [Test]
    public void TheLinesThatAreAControlsLabelAreMarkedApart()
    {
        // Revisión 2 de la ronda 22 (bloqueante 1): the ribbon's labels stay written whether or not the click on
        // «Modo de lectura» changed the mode; a line no control names (a status bar, a header) is not marked.
        JsonObject editor = View("""
            {"window": {"title": "Documento1"}, "controls": [
              {"i": 0, "kind": "TabItem", "name": "Archivo"}, {"i": 1, "kind": "TabItem", "name": "Vista"},
              {"i": 2, "kind": "Button", "name": "Modo de lectura"}, {"i": 3, "kind": "Button", "name": "Diseño de impresión"},
              {"i": 4, "kind": "Text", "name": "Página 1 de 1"}],
             "disabled": [{"kind": "Button", "name": "Diseño web"}],
             "text": {"T": ["Archivo Inicio Insertar Vista", "Modo de lectura", "Diseño de impresión", "Diseño web"],
                      "B": ["Página 1 de 1", "Lectura activa"]}}
            """);
        JsonObject excerpt = ComputerUseMission.ScreenExcerpt(editor, "poner el modo de lectura");
        int[] marked = [.. ((JsonArray)excerpt["controlLines"]!).Select(index => (int)index!)];
        JsonObject treeless = View("""
            {"window": {"title": "Steam"}, "controls": [{"i": 0, "kind": "Text", "name": "Steam"}],
             "text": {"TL": ["TIENDA BIBLIOTECA", "Modo Big Picture"]}}
            """);
        Assert.Multiple(() =>
        {
            Assert.That(marked, Is.EqualTo(new[] { 0, 1, 2, 3 }));
            Assert.That(((JsonArray)excerpt["lines"]!).Count, Is.EqualTo(6));
            // Without a control that names a label, no line can be told apart from one: every line is marked.
            Assert.That(((JsonArray)ComputerUseMission.ScreenExcerpt(treeless)["controlLines"]!).Count, Is.EqualTo(2));
        });
    }

    [Test]
    public void TheWordThatAsksForTheAnswerIsNoRootOfTheQuestion()
    {
        // Ronda 23 revision 3 (s01): the calculator always writes «Separador decimal», and «decime» shares its root.
        JsonObject calculator = View("""
            {"window": {"title": "Calculadora", "process": "CalculatorApp"}, "controls": [
              {"i": 3, "kind": "Text", "name": "La pantalla muestra 444"},
              {"i": 4, "kind": "Text", "name": "Expresión es 37 × 12="},
              {"i": 30, "kind": "Button", "name": "Separador decimal"}]}
            """);
        HashSet<string> voseo = ComputerUseMission.QuestionContentWords("abrir Calculadora; y responder: decime el resultado", calculator);
        HashSet<string> tuteo = ComputerUseMission.QuestionContentWords("abrir Calculadora; y responder: dime el resultado", calculator);
        HashSet<string> separator = ComputerUseMission.QuestionContentWords(
            "abrir Calculadora; y responder: decime cuál es el separador decimal", calculator);
        Assert.Multiple(() =>
        {
            Assert.That(voseo, Is.EquivalentTo(new[] { "resultado" }));
            Assert.That(tuteo, Is.EquivalentTo(voseo));
            Assert.That(ComputerUseMission.BearsQuestionRoot("Separador decimal", voseo), Is.False);
            // Contracase: a question about the separator still bears on it.
            Assert.That(separator, Does.Not.Contain("decime"));
            Assert.That(ComputerUseMission.BearsQuestionRoot("Separador decimal", separator), Is.True);
        });
    }

    [Test]
    public void WhatAFieldHoldsIsNotWhereTheWindowWent()
    {
        JsonObject typedOnly = View("""
            {"window": {"title": "Discord"}, "controls": [{"i": 0, "kind": "Edit", "name": "Nombre del canal", "value": "pruebas"}]}
            """);
        Assert.That(ComputerUseSuccessCheck.ViewContains(typedOnly, "pruebas"), Is.False);
    }

    [Test]
    public void TheWrittenAddressOfATreelessPageNamesWhereItIs()
    {
        JsonObject store = View("""
            {"window": {"title": "Steam"}, "controls": [],
             "text": {"TL": ["TIENDA BIBLIOTECA COMUNIDAD", "https://store.steampowered.com/", "Buscar en la tienda", "REBAJAS DE OTOÑO"]}}
            """);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:tienda|page:store", store, [], out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:biblioteca|page:library", store, [], out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:comunidad|page:community", View("""
                {"window": {"title": "Steam"}, "controls": [], "text": {"TL": ["TIENDA BIBLIOTECA COMUNIDAD", "https://steamcommunity.com/id/alguien/"]}}
                """), [], out _), Is.True, "a host word that ends with the place");
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:unit", store, [], out _), Is.False, "short places need a whole word");
        });
    }

    [Test]
    public void AVerifiedClickOnTheControlThatOpensThePlaceReachesItWhereControlsExist()
    {
        JsonObject library = View("""
            {"window": {"title": "Spotify - Reproductor web"}, "controls": [
              {"i": 0, "kind": "Button", "name": "Comprimir Tu biblioteca"}, {"i": 1, "kind": "Button", "name": "Crear"},
              {"i": 2, "kind": "Button", "name": "Playlists"}]}
            """);
        library["controlsBeforeClick"] = new JsonObject { ["2"] = new JsonArray("inicio", "abre tu biblioteca", "crear") };
        JsonArray opened = [new JsonObject { ["step"] = 2, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "Abre Tu biblioteca" }];
        JsonArray missed = [new JsonObject { ["step"] = 2, ["operation"] = "input.visible.click", ["ok"] = false, ["label"] = "Abre Tu biblioteca" }];
        JsonObject friends = View("""
            {"window": {"title": "Discord"},
             "controls": [{"i": 0, "kind": "TreeItem", "name": "Amigos", "state": "selected"}, {"i": 1, "kind": "Button", "name": "Choche Cotele!!!"}]}
            """);
        JsonArray card = [new JsonObject { ["step"] = 1, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "Choche Cotele!!!" }];
        // Encargo S (banco e1 y8, e2 u1): the library's own button says it is open («Comprimir Tu biblioteca»), whichever
        // step opened it, also one whose post-read did not hold (the step stays failed; the place is open). Counter-case:
        // the same failed press with the button still offering to open it.
        JsonObject stillClosed = View("""
            {"window": {"title": "Spotify - Reproductor web"}, "controls": [
              {"i": 0, "kind": "Button", "name": "Abre Tu biblioteca"}, {"i": 1, "kind": "Button", "name": "Crear"},
              {"i": 2, "kind": "Button", "name": "Playlists"}]}
            """);
        stillClosed["controlsBeforeClick"] = new JsonObject { ["2"] = new JsonArray("inicio", "abre tu biblioteca", "crear") };
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:tu biblioteca", library, opened, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:tu biblioteca", library, missed, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:tu biblioteca", stillClosed, missed, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:tu biblioteca", stillClosed, opened, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:cotele", friends, card, out _), Is.False);
        });
    }

    [Test]
    public void APanelOpenedBesideAFullPageReachesThePlaceWhenItsOpenerFlipped()
    {
        // Measured 2026-10-07 (z7): after «Inicio», «Abre Tu biblioteca» opened the side panel; the home page kept most
        // of its controls, so «most controls new» missed the arrival and the model collapsed the panel again.
        string[] page = ["inicio", "buscar", "crear", "novedades", "actividad reciente", "explorar", "tarjeta 1", "tarjeta 2",
            "tarjeta 3", "tarjeta 4", "tarjeta 5", "tarjeta 6", "tarjeta 7", "tarjeta 8", "tarjeta 9", "tarjeta 10"];
        JsonArray Names(params string[] extra) => new(page.Concat(extra).Select(name => (JsonNode?)JsonValue.Create(name)).ToArray());
        JsonObject Shown(params string[] extra)
        {
            var controls = new JsonArray();
            int index = 0;
            foreach (string name in page.Concat(extra))
            {
                controls.Add(new JsonObject { ["i"] = index++, ["kind"] = "Button", ["name"] = name });
            }

            return new JsonObject { ["window"] = new JsonObject { ["title"] = "Reproductor" }, ["controls"] = controls };
        }

        JsonArray opened = [new JsonObject { ["step"] = 4, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "Abre Tu biblioteca" }];
        JsonObject flipped = Shown("Comprimir Tu biblioteca", "Buscar en Tu biblioteca", "Playlists");
        flipped["controlsBeforeClick"] = new JsonObject { ["4"] = Names("abre tu biblioteca") };
        JsonObject unchanged = Shown("Abre Tu biblioteca", "Playlists");
        unchanged["controlsBeforeClick"] = new JsonObject { ["4"] = Names("abre tu biblioteca") };
        JsonObject goneNothingNamed = Shown("Tu biblioteca", "Playlists");
        goneNothingNamed["controlsBeforeClick"] = new JsonObject { ["4"] = Names("abre tu biblioteca", "tu biblioteca") };
        JsonObject stayed = Shown("Colores", "Paleta");
        stayed["controlsBeforeClick"] = new JsonObject { ["4"] = Names("colores") };
        // Encargo S: the place's own button says whether it is open, not the click (ComputerUseSuccessCheck.PlaceToggle):
        // a panel whose closing button is shown is open even after a click on a card of the same name.
        JsonObject toggled = Shown("Colores", "Comprimir Colores");
        toggled["controlsBeforeClick"] = new JsonObject { ["4"] = Names("colores") };
        JsonArray card = [new JsonObject { ["step"] = 4, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "Colores" }];
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:tu biblioteca", flipped, opened, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:tu biblioteca", unchanged, opened, out _), Is.False, "the opener still there: nothing opened");
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:tu biblioteca", goneNothingNamed, opened, out _), Is.False, "no new control names the place");
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:colores", stayed, card, out _), Is.False, "a card named as the place is no opener");
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:colores", toggled, card, out _), Is.True, "its own closing button says it is open");
        });
    }

    [Test]
    public void AClickNamedAsThePlaceThatMadeAnotherItemTheChosenOneDidNotArrive()
    {
        JsonObject pictures = View("""
            {"window": {"title": "Imágenes - Explorador de archivos"}, "controls": [
              {"i": 0, "kind": "TreeItem", "name": "Downloads"}, {"i": 1, "kind": "TreeItem", "name": "Imágenes", "state": "selected"},
              {"i": 2, "kind": "TreeItem", "name": "Documentos"}]}
            """);
        pictures["selectedBeforeClick"] = new JsonObject { ["2"] = new JsonArray("documentos") };
        JsonArray clicked = [new JsonObject { ["step"] = 2, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "Downloads" }];
        JsonObject display = View("""
            {"window": {"title": "Configuración"}, "controls": [
              {"i": 0, "kind": "ListItem", "name": "Sistema", "state": "selected"}, {"i": 1, "kind": "Button", "name": "Pantalla"},
              {"i": 2, "kind": "Button", "name": "Brillo"}, {"i": 3, "kind": "Button", "name": "Luz nocturna"},
              {"i": 4, "kind": "Button", "name": "Escala"}, {"i": 5, "kind": "Button", "name": "HDR"}]}
            """);
        display["selectedBeforeClick"] = new JsonObject { ["3"] = new JsonArray("sistema") };
        display["controlsBeforeClick"] = new JsonObject { ["3"] = new JsonArray("sistema", "pantalla", "sonido", "notificaciones") };
        JsonObject stayed = View("""
            {"window": {"title": "Configuración"}, "controls": [
              {"i": 0, "kind": "ListItem", "name": "Personalización", "state": "selected"}, {"i": 1, "kind": "Button", "name": "Colores"},
              {"i": 2, "kind": "Button", "name": "Temas"}]}
            """);
        stayed["controlsBeforeClick"] = new JsonObject { ["2"] = new JsonArray("personalizacion", "colores", "temas") };
        JsonArray card = [new JsonObject { ["step"] = 2, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "Colores" }];
        JsonArray screen = [new JsonObject { ["step"] = 3, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "Pantalla" }];
        JsonObject picturesSeen = (JsonObject)pictures.DeepClone();
        picturesSeen["controlsBeforeClick"] = new JsonObject { ["2"] = new JsonArray("downloads", "imagenes", "documentos") };
        foreach (string photo in new[] { "foto 1", "foto 2", "foto 3", "foto 4", "foto 5", "foto 6" })
        {
            ((JsonArray)picturesSeen["controls"]!).Add(new JsonObject { ["i"] = 9, ["kind"] = "ListItem", ["name"] = photo });
        }

        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:downloads", pictures, clicked, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:downloads", picturesSeen, clicked, out _), Is.False, "an item listed before became the chosen one");
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:pantalla", display, screen, out _), Is.True, "the section kept selected was chosen before");
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:colores", stayed, card, out _), Is.False, "the same controls: the click went nowhere");
        });
    }

    // Revision 3 of ronda 20b (B-A): a classic menu's entries read without opening it are listed to be pressed by their
    // command, never shown. «bajá hasta Opciones» on a list whose «Opciones» is further down, in a window whose closed
    // menu has «Herramientas › Opciones...», is not done before the list moves. Contracase: the item on screen proves it.
    [Test]
    public void AClosedMenuEntryProvesNothingShown()
    {
        JsonObject closed = View("""
            {"window": {"title": "Archivos"}, "controls": [
              {"i": 0, "kind": "List", "name": "Lista"},
              {"i": 1, "kind": "ListItem", "name": "Documentos"},
              {"i": 2, "kind": "MenuItem", "name": "Herramientas › Opciones...", "nameSource": "menu", "id": "hmenu.30", "state": ""},
              {"i": 3, "kind": "MenuItem", "name": "Favoritos › Agregar a favoritos", "nameSource": "menu", "id": "hmenu.31", "state": ""}]}
            """);
        JsonObject shown = View("""
            {"window": {"title": "Archivos"}, "controls": [
              {"i": 0, "kind": "List", "name": "Lista"},
              {"i": 1, "kind": "ListItem", "name": "Opciones"},
              {"i": 2, "kind": "MenuItem", "name": "Herramientas › Opciones...", "nameSource": "menu", "id": "hmenu.30", "state": ""}]}
            """);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:=opciones|control:=options", closed, [], out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:=favoritos", closed, [], out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("text:opciones", closed, [], out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.ViewContains(closed, "opciones"), Is.False);
            Assert.That(ComputerUseSuccessCheck.LookText(closed), Does.Not.Contain("opciones"));
            Assert.That(closed["controls"]!.AsArray(), Has.Count.EqualTo(4), "the view itself keeps the entries to press");
            // Contracase: the item drawn on screen proves it, and an entry of an opened menu (UIA) is on screen.
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:=opciones|control:=options", shown, [], out string? by), Is.True);
            Assert.That(by, Is.EqualTo("control:=opciones"));
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:=favoritos", View("""
                {"window": {"title": "Archivos"}, "controls": [{"i": 0, "kind": "MenuItem", "name": "Agregar a favoritos"}]}
                """), [], out _), Is.True);
        });
    }

    // Review of ronda 20b (finding 1): a toggle whose sibling's mark never appeared (ok=false, effectUncertain) may have
    // acted on the box: the box shown on afterwards is not «already chosen». A refused click that pressed nothing keeps it.
    // (A name without a closing quote: the citation's quote marks are trimmed before it is compared.)
    [Test]
    public void AnUncertainToggleOnTheControlIsNoAlreadyChosen()
    {
        JsonObject mixer = View("""
            {"window": {"title": "Mezclador"}, "controls": [
              {"kind": "CheckBox", "name": "Silenciar audio del escritorio", "state": "on"}],
             "chosenBeforeClick": {"1": [], "2": []}}
            """);
        JsonArray uncertain = new()
        {
            new JsonObject { ["step"] = 1, ["operation"] = "input.visible.click", ["label"] = "Mezclador", ["ok"] = true, ["surfaceChanged"] = true },
            new JsonObject
            {
                ["step"] = 2, ["operation"] = "input.visible.click", ["label"] = "Silenciar audio del escritorio", ["ok"] = false,
                ["effectUncertain"] = true, ["error"] = "visible_toggle_uncorroborated",
            },
        };
        JsonArray refused = new()
        {
            uncertain[0]!.DeepClone(),
            new JsonObject
            {
                ["step"] = 2, ["operation"] = "input.visible.click", ["label"] = "Silenciar audio del escritorio", ["ok"] = false,
                ["error"] = "visible_button_ambiguous",
            },
        };
        JsonArray untouched = new() { uncertain[0]!.DeepClone() };
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.AlreadyChosen("Silenciar audio del escritorio", mixer, uncertain), Is.False);
            Assert.That(ComputerUseSuccessCheck.AlreadyChosen("Silenciar audio del escritorio", mixer, refused), Is.True);
            Assert.That(ComputerUseSuccessCheck.AlreadyChosen("Silenciar audio del escritorio", mixer, untouched), Is.True);
        });
    }

    [Test]
    public void ThePagesOwnHeaderNamesWhereTheWindowIs()
    {
        static JsonObject Colors(string title, string zone, bool moreToTheRight)
        {
            JsonObject view = View("""
                {"window": {"title": "Configuración"}, "controls": [
                  {"i": 0, "kind": "ListItem", "name": "Personalización", "state": "selected", "zone": "L", "rect": {"x": 0, "y": 100, "w": 200, "h": 40}},
                  {"i": 1, "kind": "Button", "name": "Personalización", "zone": "T", "rect": {"x": 220, "y": 40, "w": 200, "h": 40}},
                  {"i": 2, "kind": "Button", "name": "Colores", "zone": "T", "rect": {"x": 440, "y": 40, "w": 120, "h": 40}},
                  {"i": 3, "kind": "ComboBox", "name": "Elige tu modo", "zone": "R", "rect": {"x": 700, "y": 200, "w": 200, "h": 30}}]}
                """);
            view["window"]!["title"] = title;
            view["controls"]![2]!["zone"] = zone;
            if (moreToTheRight)
            {
                view["controls"]!.AsArray().Add(View("""
                    {"i": 4, "kind": "Button", "name": "Compartir", "zone": "T", "rect": {"x": 600, "y": 45, "w": 80, "h": 30}}
                    """));
            }

            return view;
        }

        JsonObject personalization = View("""
            {"window": {"title": "Configuración"}, "controls": [
              {"i": 0, "kind": "ListItem", "name": "Personalización", "state": "selected", "zone": "L", "rect": {"x": 0, "y": 100, "w": 200, "h": 40}},
              {"i": 1, "kind": "Text", "name": "Personalización", "zone": "T", "rect": {"x": 220, "y": 40, "w": 200, "h": 40}},
              {"i": 2, "kind": "ListItem", "name": "Colores", "zone": "C", "rect": {"x": 220, "y": 200, "w": 400, "h": 60}},
              {"i": 3, "kind": "Text", "name": "Colores", "zone": "C", "rect": {"x": 230, "y": 210, "w": 100, "h": 20}}]}
            """);
        JsonArray clicked = [new JsonObject { ["step"] = 2, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "Colores" }];
        JsonArray failed = [new JsonObject { ["step"] = 2, ["operation"] = "input.visible.click", ["ok"] = false, ["label"] = "Colores" }];
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:colores", Colors("Configuración", "T", false), clicked, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:colores", Colors("Configuración", "T", false), [], out _), Is.False,
                "the sub-goal's first look is not an arrival");
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:colores", Colors("Configuración", "T", false), failed, out _), Is.False,
                "a click that did not verify brought nothing");
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:colores", Colors("Colores - Configuración", "T", false), [], out _), Is.True,
                "the title names the place");
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:colores", Colors("Configuración", "TL", false), clicked, out _), Is.True,
                "a lone heading of a maximized window lands in TL");
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:colores", Colors("Configuración", "TL", true), clicked, out _), Is.False,
                "a toolbar in TL has more controls to its right");
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:colores", Colors("Configuración", "TR", false), clicked, out _), Is.False,
                "the toolbars of TR are never the header");
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:colores", Colors("Configuración", "T", true), clicked, out _), Is.False,
                "a control with more to its right is a tab or a tool, not where the header ends");
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:colores", personalization, clicked, out _), Is.False);
        });
    }

    // Measured on the Calculator: the mode clicked in the navigation is written as the window's heading («Modo de
    // calculadora Científica»); a heading already there before the click, or one the last click did not name, is not it.
    [Test]
    public void AHeadingTheLastClickMadeAppearNamesTheModeReached()
    {
        JsonObject Calculator(string zone, params string[] before)
        {
            JsonObject view = View("""
                {"window": {"title": "Calculadora"}, "controls": [
                  {"i": 0, "kind": "Button", "name": "Abrir navegación", "zone": "TL"},
                  {"i": 1, "kind": "Text", "name": "Modo de calculadora Científica", "zone": "T"},
                  {"i": 2, "kind": "Button", "name": "Seno", "zone": "C"}]}
                """);
            view["controls"]![1]!["zone"] = zone;
            view["controlsBeforeClick"] = new JsonObject { ["2"] = new JsonArray([.. before.Select(name => (JsonNode?)JsonValue.Create(name))]) };
            return view;
        }

        JsonArray Steps(string lastLabel, bool lastOk = true) =>
        [
            new JsonObject { ["step"] = 1, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "Abrir navegación" },
            new JsonObject { ["step"] = 2, ["operation"] = "input.visible.click", ["ok"] = lastOk, ["label"] = lastLabel },
        ];
        JsonObject noBefore = Calculator("T");
        noBefore.Remove("controlsBeforeClick");
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("header:Científica", Calculator("T", "modo de calculadora estandar", "abrir navegacion"),
                Steps("Calculadora Científica"), out string? by), Is.True);
            Assert.That(by, Is.EqualTo("header:Científica"));
            Assert.That(ComputerUseSuccessCheck.Evaluate("header:Científica", Calculator("TR", "modo de calculadora estandar"),
                Steps("Científica"), out _), Is.True, "any top zone holds a heading");
            Assert.That(ComputerUseSuccessCheck.Evaluate("header:Científica", Calculator("T", "modo de calculadora cientifica"),
                Steps("Calculadora Científica"), out _), Is.False, "the heading was there before the click");
            Assert.That(ComputerUseSuccessCheck.Evaluate("header:Científica", Calculator("T", "modo de calculadora estandar"),
                Steps("Historial"), out _), Is.False, "the last click named something else");
            Assert.That(ComputerUseSuccessCheck.Evaluate("header:Científica", Calculator("T", "modo de calculadora estandar"),
                Steps("Calculadora Científica", lastOk: false), out _), Is.False, "the click on it did not verify");
            Assert.That(ComputerUseSuccessCheck.Evaluate("header:Científica", Calculator("C", "modo de calculadora estandar"),
                Steps("Calculadora Científica"), out _), Is.False, "written in the body, not as a heading");
            Assert.That(ComputerUseSuccessCheck.Evaluate("header:Científica", noBefore, Steps("Calculadora Científica"), out _), Is.False,
                "what was there before the click is unknown");
            Assert.That(ComputerUseSuccessCheck.Evaluate("header:Científica", Calculator("T", "modo de calculadora estandar"), [], out _), Is.False);
        });
    }

    // Measured on Steam: «BIBLIOTECA» and then «TIENDA», both written in the header before the first click, and the store
    // passed for the library as if «TIENDA» were an entry of the library's menu. A click that failed in between (a
    // learned «Inicio» no longer there) changes nothing: the entry picked after it still reaches the place.
    [Test]
    public void OnlyAnEntryTheMenuShowedCountsAsReachingThePlaceAfterTheClickOnIt()
    {
        JsonObject library = View("""
            {"window": {"title": "Steam"}, "controls": [],
             "text": {"TL": ["TIENDA", "BIBLIOTECA COMUNIDAD", "Pagina principal", "Juegos y Software", "FAVORITOS (324)"],
                      "C": ["TUS COLECCIONES", "INSTALADO LOCALMENTE"]}}
            """);
        library["textBeforeClick"] = new JsonObject
        {
            ["1"] = new JsonArray("tienda", "biblioteca comunidad", "explorar", "buscar en la tienda", "rebajas de otono", "lista de deseados"),
        };
        JsonArray thenTheStore =
        [
            new JsonObject { ["step"] = 1, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "BIBLIOTECA" },
            new JsonObject { ["step"] = 2, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "TIENDA" },
        ];
        JsonArray throughAFailedEntry =
        [
            new JsonObject { ["step"] = 1, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "BIBLIOTECA" },
            new JsonObject { ["step"] = 2, ["operation"] = "input.visible.click", ["ok"] = false, ["label"] = "Inicio" },
            new JsonObject { ["step"] = 3, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "Página principal" },
        ];
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:biblioteca", library, thenTheStore, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:biblioteca", library, throughAFailedEntry, out _), Is.True);
        });
    }

    // A search typed in this sub-goal and still echoing (its box holds it, nothing went from its results to the place)
    // makes any citation holding it an echo (measured on Explorer: «imagenes - Resultados de la búsqueda en ETC» cited as
    // evidence). Only a click on the place itself, not on a result that merely holds the name, ends the echo.
    [Test]
    public void EvidenceHoldingAQueryThatStillEchoesIsNotProof()
    {
        JsonObject results = View("""
            {"window": {"title": "imagenes - Resultados de la búsqueda en Trabajo - Explorador de archivos", "process": "explorer",
                        "focused": {"kind": "Edit", "name": "Buscar en Trabajo", "value": "imagenes"}},
             "controls": [{"i": 0, "kind": "TabItem", "name": "imagenes - Resultados de la búsqueda en Trabajo", "state": "selected"},
                          {"i": 1, "kind": "Edit", "name": "Buscar en Trabajo", "state": "focused", "value": "imagenes"},
                          {"i": 2, "kind": "ListItem", "name": "Imagenes viejas", "state": ""}],
             "text": {}}
            """);
        JsonObject arrived = View("""
            {"window": {"title": "Imágenes - Explorador de archivos", "process": "explorer",
                        "focused": {"kind": "Pane", "name": "Imágenes", "value": null}},
             "controls": [{"i": 0, "kind": "TabItem", "name": "Imágenes", "state": "selected"}], "text": {}}
            """);
        JsonArray Searched(params JsonObject[] after)
        {
            var steps = new JsonArray
            {
                new JsonObject { ["step"] = 1, ["operation"] = "input.visible.click", ["label"] = "Buscar en Trabajo", ["ok"] = true },
                new JsonObject { ["step"] = 2, ["operation"] = "input.text.type", ["text"] = "imagenes", ["into"] = "Buscar en Trabajo", ["ok"] = true },
                new JsonObject { ["step"] = 3, ["operation"] = "input.key.press", ["key"] = "enter", ["ok"] = true },
            };
            foreach (JsonObject step in after)
            {
                steps.Add(step);
            }

            return steps;
        }

        JsonObject Click(string label) => new() { ["step"] = 4, ["operation"] = "input.visible.click", ["label"] = label, ["ok"] = true };
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.CitationEchoesQuery("imagenes - Resultados de la búsqueda en Trabajo", results, Searched()), Is.True);
            Assert.That(ComputerUseSuccessCheck.CitationEchoesQuery("«imagenes»", results, Searched()), Is.True);
            Assert.That(ComputerUseSuccessCheck.CitationEchoesQuery("Imágenes - Explorador de archivos", arrived, Searched(Click("Imágenes"))), Is.False,
                "a click on the place by its name went there");
            Assert.That(ComputerUseSuccessCheck.CitationEchoesQuery("Imagenes viejas", results, []), Is.False, "nothing typed in this sub-goal");
            Assert.That(ComputerUseSuccessCheck.Evaluate("title:Imágenes", results, Searched(Click("Imagenes viejas")), out _), Is.False,
                "a result that holds the name is one of the matches, not the place");
            Assert.That(ComputerUseSuccessCheck.Evaluate("title:Imágenes", arrived, Searched(Click("Abrir Imágenes")), out _), Is.True);
        });
    }

    // «buscá pdf en Descargas»: the sub-goal is the search itself (its check also asks for the act), so its results
    // titled by the query are its evidence, not an echo; a sub-goal that wants the place still rejects them.
    [Test]
    public void ASearchGoalTakesItsResultsAsEvidence()
    {
        JsonObject results = View("""
            {"window": {"title": "pdf - Resultados de la búsqueda en Descargas - Explorador de archivos", "process": "explorer",
                        "focused": {"kind": "Edit", "name": "Buscar en Descargas", "value": "pdf"}},
             "controls": [{"i": 0, "kind": "TabItem", "name": "pdf - Resultados de la búsqueda en Descargas", "state": "selected"},
                          {"i": 1, "kind": "Edit", "name": "Buscar en Descargas", "state": "focused", "value": "pdf"}],
             "text": {}}
            """);
        var steps = new JsonArray
        {
            new JsonObject { ["step"] = 1, ["operation"] = "input.visible.click", ["label"] = "Buscar en Descargas", ["ok"] = true },
            new JsonObject { ["step"] = 2, ["operation"] = "input.text.type", ["text"] = "pdf", ["into"] = "Buscar en Descargas", ["ok"] = true },
            new JsonObject { ["step"] = 3, ["operation"] = "input.key.press", ["key"] = "enter", ["ok"] = true },
        };
        const string cited = "pdf - Resultados de la búsqueda en Descargas";
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.SearchResultsProve("title:pdf&stepDone:input.key.press:enter"), Is.True);
            Assert.That(ComputerUseSuccessCheck.SearchResultsProve("title:Descargas | control:pdf:selected"), Is.False);
            Assert.That(ComputerUseSuccessCheck.SearchResultsProve(null), Is.False);
            Assert.That(ComputerUseSuccessCheck.CitationEchoesQuery(cited, results, steps,
                ComputerUseSuccessCheck.SearchResultsProve("title:pdf&stepDone:input.key.press:enter")), Is.False);
            Assert.That(ComputerUseSuccessCheck.CitationEchoesQuery(cited, results, steps,
                ComputerUseSuccessCheck.SearchResultsProve("title:pdf")), Is.True);
            Assert.That(ComputerUseSuccessCheck.CitationEchoesQuery("pdf", results, steps, searchResultsProve: true), Is.True,
                "the bare query is its own echo");
        });
    }

    // Pasada r15b (v3-27, v3-29): the buttons the window shows disabled reach the mind apart from the controls, with no
    // index; a view without any carries no such list.
    [Test]
    public void TheDisabledButtonsReachTheMindApart()
    {
        var view = new JsonObject
        {
            ["controls"] = new JsonArray(new JsonObject { ["i"] = 0, ["kind"] = "Edit", ["name"] = "Caracteres para copiar:" }),
            ["disabled"] = new JsonArray(new JsonObject { ["kind"] = "Button", ["name"] = "Copiar", ["state"] = "disabled", ["zone"] = "R" }),
        };
        JsonObject compact = ComputerUseMission.CompactForTheMind(view);
        Assert.Multiple(() =>
        {
            Assert.That((string?)compact["disabled"]?[0]?["name"], Is.EqualTo("Copiar"));
            Assert.That(((JsonArray)compact["controls"]!).Count, Is.EqualTo(1), "never among the controls a step presses");
            Assert.That(ComputerUseMission.CompactForTheMind(new JsonObject { ["controls"] = new JsonArray() }).ContainsKey("disabled"), Is.False);
        });
    }

    // r26 (banco c25 x5, y4): the mind's rule read «value == ""» for a document's empty body, and the view it receives
    // never carried an empty value: the rule passed its tests and never ran. The view says «empty» only for a value
    // the provider read and found empty; one it could not read (null) and one that holds text never say it.
    [Test]
    public void AValueReadEmptyReachesTheMindAsEmptyAndAnUnreadOneDoesNot()
    {
        var view = new JsonObject
        {
            ["window"] = new JsonObject { ["title"] = "Sin título: Bloc de notas", ["process"] = "Notepad", ["foreground"] = false },
            ["controls"] = new JsonArray(
                new JsonObject { ["i"] = 0, ["kind"] = "Document", ["name"] = "Editor de texto", ["value"] = "" },
                new JsonObject { ["i"] = 1, ["kind"] = "Document", ["name"] = "Página 1 contenido", ["value"] = null },
                new JsonObject { ["i"] = 2, ["kind"] = "Edit", ["name"] = "Buscar", ["value"] = "mouse" },
                new JsonObject { ["i"] = 3, ["kind"] = "Button", ["name"] = "Guardar" }),
        };
        JsonObject compact = ComputerUseMission.CompactForTheMind(view);
        JsonArray controls = (JsonArray)compact["controls"]!;
        Assert.Multiple(() =>
        {
            // The mind is never told front from behind: a rule of it that reads «foreground» runs in its tests only
            // (the r25 rule did; r26 reads what the view does carry: no focus read at all).
            Assert.That(((JsonObject)compact["window"]!).ContainsKey("foreground"), Is.False);
            Assert.That((bool?)controls[0]!["empty"], Is.True);
            Assert.That(((JsonObject)controls[0]!).ContainsKey("value"), Is.False, "the prompt prints no empty value");
            Assert.That(((JsonObject)controls[1]!).ContainsKey("empty"), Is.False, "unread: it may hold the person's work");
            Assert.That((string?)controls[2]!["value"], Is.EqualTo("mouse"));
            Assert.That(((JsonObject)controls[2]!).ContainsKey("empty"), Is.False);
            Assert.That(((JsonObject)controls[3]!).ContainsKey("empty"), Is.False);
        });
    }

    // Every view the mind receives carries what the sub-goal's last verified click made appear (the look right after
    // it), kept while the screen stays and forgotten with the sub-goal.
    [Test]
    public void EveryViewCarriesWhatTheLastVerifiedClickMadeAppear()
    {
        static JsonObject Look(params string[] lines) =>
            new() { ["text"] = new JsonObject { ["C"] = new JsonArray([.. lines.Select(line => (JsonNode?)JsonValue.Create(line))]) } };
        static string[] After(JsonObject view) =>
            [.. ((JsonArray)ComputerUseMission.CompactForTheMind(view)["newTextAfterClick"]!).Select(node => (string?)node ?? string.Empty)];

        var state = new JsonObject
        {
            ["subgoals"] = new JsonArray(new JsonObject { ["goal"] = "abrir el menu" }, new JsonObject { ["goal"] = "ir a ajustes" }),
            ["steps"] = new JsonArray(),
        };
        var steps = (JsonArray)state["steps"]!;
        void Note(JsonObject view, int start) =>
            ComputerUseMission.NoteWhatAppeared(state, view, ComputerUseSuccessCheck.TextLines(view), steps, start);

        JsonObject first = Look("Archivo", "Editar");
        Note(first, 0);
        steps.Add(new JsonObject { ["step"] = 1, ["operation"] = "input.visible.click", ["label"] = "Archivo", ["ok"] = true });
        JsonObject menu = Look("Archivo", "Editar", "Abrir", "Guardar");
        Note(menu, 0);
        JsonObject again = Look("Archivo", "Editar", "Abrir", "Guardar");
        Note(again, 0);
        steps.Add(new JsonObject { ["step"] = 2, ["operation"] = "input.visible.click", ["label"] = "Ayuda", ["ok"] = false });
        JsonObject afterFailure = Look("Archivo", "Editar", "Abrir", "Guardar", "Reloj");
        Note(afterFailure, 0);
        ComputerUseMission.EnterSubgoal(state, 1);
        JsonObject nextSubgoal = Look("Ajustes");
        Note(nextSubgoal, steps.Count);
        Assert.Multiple(() =>
        {
            Assert.That(After(first), Is.Empty);
            Assert.That(After(menu), Is.EqualTo(new[] { "abrir", "guardar" }));
            Assert.That(After(again), Is.EqualTo(new[] { "abrir", "guardar" }), "the same screen: the click's effect stands");
            Assert.That((JsonArray)again["newText"]!, Is.Empty);
            Assert.That(After(afterFailure), Is.EqualTo(new[] { "abrir", "guardar" }), "a failed click made nothing appear");
            Assert.That(After(nextSubgoal), Is.Empty, "a new sub-goal starts without it");
            Assert.That(ComputerUseMission.CompactForTheMind(View(SteamView))["newTextAfterClick"], Is.InstanceOf<JsonArray>());
        });
    }

    // Review of v3 r5a M5: an elevated window whose program stays unraised (the view's «reopensUnraised») stops with the
    // reopenable limit, whose floor offers to reopen it without administrator rights; without it (the Task Manager,
    // which raises itself again) the limit carries no offer. Both codes fit a trace label.
    [Test]
    public void AnElevatedWindowIsOfferedToReopenOnlyWhenItsProgramStaysUnraised()
    {
        JsonObject View(bool? reopens)
        {
            var window = new JsonObject { ["elevated"] = true };
            if (reopens is { } value)
                window["reopensUnraised"] = value;
            return new JsonObject { ["window"] = window };
        }

        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.ElevatedStop(View(true)), Is.EqualTo("computer_use_window_elevated_reopenable"));
            Assert.That(ComputerUseMission.ElevatedStop(View(false)), Is.EqualTo("computer_use_window_elevated"));
            Assert.That(ComputerUseMission.ElevatedStop(View(null)), Is.EqualTo("computer_use_window_elevated"));
            Assert.That(ComputerUseMission.ElevatedStop(null), Is.EqualTo("computer_use_window_elevated"));
            Assert.That(
                ShellTrace.SanitizeLabel("computer_use_window_elevated_reopenable"),
                Is.EqualTo("computer_use_window_elevated_reopenable"));
        });
    }

    // cu-v3-elevacion, twin of r9 v3-65 turn 2 (the Services console left raised, «cambiala a la vista estándar»): before
    // any step, a raised window whose program opens again with the person's rights is reopened (the mind's first step is
    // app.open), not a stop; once a step was done, or for a program that raises itself (the Task Manager, v3-20..22,
    // v3-72; the Resource Monitor, v3-69..71), the limit stands.
    [Test]
    public void ARaisedConsoleIsReopenedBeforeAnyStepAndOnlyThen()
    {
        JsonObject View(bool? reopens)
        {
            var window = new JsonObject { ["elevated"] = true };
            if (reopens is { } value)
                window["reopensUnraised"] = value;
            return new JsonObject { ["window"] = window };
        }

        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.ReopensUnraisedFirst(View(true), 0, "Servicios"), Is.True);
            Assert.That(ComputerUseMission.ReopensUnraisedFirst(View(true), 1, "Servicios"), Is.False, "reopened once already");
            Assert.That(ComputerUseMission.ReopensUnraisedFirst(View(false), 0, "Servicios"), Is.False, "raises itself again");
            Assert.That(ComputerUseMission.ReopensUnraisedFirst(View(null), 0, "Servicios"), Is.False);
            Assert.That(ComputerUseMission.ReopensUnraisedFirst(null, 0, "Servicios"), Is.False);
            Assert.That(ComputerUseMission.ReopensUnraisedFirst(View(true), 0, null), Is.False, "no application to reopen");
            Assert.That(ComputerUseMission.ReopensUnraisedFirst(View(true), 0, " "), Is.False);
        });
    }

    // Review of cu-v3-elevacion (finding 5): on the raised console of v3-65 the only decision carried out is the
    // reopening (app.open). A «done» citing what OCR read on it, a click Windows would swallow, a mission on the window
    // in front with no application named, or any step after the reopening stop with the elevated limit; a window that
    // is not raised allows everything.
    [TestCase("app.open", 0, "Servicios", true, true)]
    [TestCase("done", 0, "Servicios", true, false)]
    [TestCase("input.visible.click", 0, "Servicios", true, false)]
    [TestCase("app.open", 0, null, true, false)]
    [TestCase("app.open", 1, "Servicios", true, false)]
    [TestCase("app.open", 0, "Administrador de tareas", false, false)]
    public void OnARaisedWindowOnlyTheReopeningIsCarriedOut(
        string operation, int stepsDone, string? application, bool reopens, bool allowed)
    {
        var raised = new JsonObject { ["window"] = new JsonObject { ["elevated"] = true, ["reopensUnraised"] = reopens } };
        var plain = new JsonObject { ["window"] = new JsonObject { ["title"] = "Servicios" } };

        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.ElevatedViewAllows(raised, stepsDone, application, operation, ofTheApplication: true),
                Is.EqualTo(allowed));
            Assert.That(ComputerUseMission.ElevatedViewAllows(plain, stepsDone, application, operation, ofTheApplication: true), Is.True);
            Assert.That(ComputerUseMission.ElevatedStop(raised),
                Is.EqualTo(reopens ? "computer_use_window_elevated_reopenable" : "computer_use_window_elevated"));
        });
    }

    // Ronda 19b (r17 t2-c03): the person's raised Task Manager in front of «abre configuración» is not the mission's
    // application: only the opening (of the application or of its file) is carried out on it, and the elevated limit is
    // never said of it. The application's own raised window, or a mission with no application (the window in front is
    // its own), keeps the limit as before.
    [TestCase("app.open", 0, "Configuración", false, true)]
    [TestCase("app.open", 1, "Configuración", false, true)]
    [TestCase("file.open", 0, "Configuración", false, true)]
    [TestCase("input.visible.click", 0, "Configuración", false, false)]
    [TestCase("done", 0, "Configuración", false, false)]
    [TestCase("app.open", 0, "Configuración", true, false)]
    [TestCase("app.open", 0, null, false, false)]
    public void OnAnotherProgramsRaisedWindowOnlyTheOpeningIsCarriedOut(
        string operation, int stepsDone, string? application, bool ofTheApplication, bool allowed)
    {
        // The Task Manager raises itself again (no «reopensUnraised»): the reopening rule does not apply to it.
        var raised = new JsonObject { ["window"] = new JsonObject { ["elevated"] = true, ["reopensUnraised"] = false } };

        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.ElevatedViewAllows(raised, stepsDone, application, operation, ofTheApplication),
                Is.EqualTo(allowed));
            Assert.That(ComputerUseMission.ElevatedElsewhere(raised, application, ofTheApplication),
                Is.EqualTo(application is not null && !ofTheApplication));
            Assert.That(ComputerUseMission.ElevatedElsewhere(new JsonObject { ["window"] = new JsonObject() }, application, false), Is.False);
        });
    }

    // Ronda 19b (r15b v3-34): a mission left without a look says why: its window closed, or it could not be read.
    [Test]
    public void AMissionWithoutALookSaysWhetherItsWindowClosed()
    {
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.NoViewStop(new JsonObject()), Is.EqualTo("computer_use_view_unavailable"));
            Assert.That(ComputerUseMission.NoViewStop(new JsonObject { ["windowClosed"] = true }), Is.EqualTo("computer_use_window_closed"));
            // Encargo CS: an opening whose progress window outlived ColdStartWait: the application did not finish showing.
            Assert.That(ComputerUseMission.NoViewStop(new JsonObject { ["stillStarting"] = true }), Is.EqualTo("computer_use_app_not_shown"));
            var closed = (JsonObject)JsonNode.Parse(
                """{"kind":"operation","operation":"mission.computer.use","polarity":"failure","verified":true,"succeeded":false,"observed":{"goal":"escribir una nota","application":"Notas rápidas","reached":false,"steps":[],"stoppedBy":"computer_use_window_closed"}}""")!;
            Assert.That(OperationFloor.Final(closed, english: false), Does.Contain("se cerró").And.Not.Contain("no se dejó leer"),
                "the cause is said, from data");
            Assert.That(OperationFloor.Final(closed, english: true), Does.Contain("closed"));
        });
    }

    // Ronda 19b (r15b v3-34): a mission tied to the window of an application it started is tied again once, when that
    // window closed; never a second time, never untied, never for an application that was already running. Review of
    // ronda 19b (finding 1): the windows it refused (the person's) and the ones it created are kept, and the look that
    // follows is judged.
    [Test]
    public void OnlyAWindowOfAnApplicationTheMissionStartedIsTiedAgainAndOnlyOnce()
    {
        JsonObject Tied() => new()
        {
            ["windows"] = new JsonArray(100L),
            ["known"] = new JsonArray(7L, 8L),
            ["refused"] = new JsonArray(8L),
            ["created"] = new JsonArray(100L),
            ["tiedAtStep"] = 1,
        };
        var started = new JsonArray(new JsonObject { ["operation"] = "app.open", ["ok"] = true });
        var running = new JsonArray(new JsonObject { ["operation"] = "app.open", ["ok"] = true, ["alreadyRunning"] = true });

        JsonObject state = Tied();
        bool first = ComputerUseMissionWindow.Retie(state, started);
        bool untied = !ComputerUseMissionWindow.Tied(state) && state["known"] is null;
        bool keptRefused = state["refused"] is JsonArray refused && refused.Select(node => (long?)node).SequenceEqual([8L]);
        bool keptCreated = state["created"] is JsonArray { Count: 1 };
        bool judged = ComputerUseMissionWindow.TakeRetieLook(state) && !ComputerUseMissionWindow.TakeRetieLook(state);
        state["windows"] = new JsonArray(200L);
        bool second = ComputerUseMissionWindow.Retie(state, started);

        Assert.Multiple(() =>
        {
            Assert.That(first, Is.True);
            Assert.That(untied, Is.True, "the look that follows names no window");
            Assert.That(keptRefused, Is.True, "the windows it refused are never read again");
            Assert.That(keptCreated, Is.True);
            Assert.That(judged, Is.True, "the look that follows is judged, once");
            Assert.That(second, Is.False, "once");
            Assert.That(ComputerUseMissionWindow.Retie(Tied(), running), Is.False, "already running");
            Assert.That(ComputerUseMissionWindow.Retie(Tied(), []), Is.False, "nothing opened");
            Assert.That(ComputerUseMissionWindow.Retie(new JsonObject(), started), Is.False, "not tied");
        });
    }

    // Review of ronda 19b (finding 1): the look after tying again is kept only when it shows the application, is no
    // window the mission refused, and is kept as a born window is; kept, it ties the mission with the refused windows
    // and the process's other windows known.
    [TestCase(true, 300L, null, true, "created")]
    [TestCase(false, 300L, null, false, "not_application")]
    [TestCase(true, 8L, null, false, "refused")]
    [TestCase(true, 300L, 40L, false, "person")]
    public void TheLookAfterTyingAgainIsJudgedAsABornWindow(
        bool ofTheApplication, long hwnd, long? personInputAgoMs, bool keeps, string why)
    {
        DateTimeOffset now = DateTimeOffset.UtcNow;
        var state = new JsonObject
        {
            ["objective"] = "escribir una nota",
            ["application"] = "Notas rápidas",
            ["startedUtc"] = now.AddSeconds(-10).ToString("O"),
            ["windows"] = new JsonArray(100L),
            ["known"] = new JsonArray(8L),
            ["refused"] = new JsonArray(8L),
            ["created"] = new JsonArray(100L),
            ["tiedAtStep"] = 1,
        };
        var steps = new JsonArray(new JsonObject { ["operation"] = "app.open", ["ok"] = true });
        ComputerUseMissionWindow.Retie(state, steps);
        var view = new JsonObject
        {
            ["window"] = new JsonObject { ["title"] = "Notas rápidas", ["hwnd"] = hwnd, ["others"] = new JsonArray(9L) },
            ["controls"] = new JsonArray(),
        };
        if (personInputAgoMs is long ago)
            view["window"]!["personInputAgoMs"] = ago;

        bool kept = ComputerUseMissionWindow.KeepsRetied(state, view, ofTheApplication, steps, now, out string said);
        if (kept)
            ComputerUseMissionWindow.TieAgain(state, view, said, steps);

        Assert.Multiple(() =>
        {
            Assert.That(kept, Is.EqualTo(keeps));
            Assert.That(said, Is.EqualTo(why));
            if (keeps)
            {
                Assert.That(ComputerUseMissionWindow.OnTheTiedWindow(state, view), Is.True);
                Assert.That(((JsonArray)state["known"]!).Select(node => (long?)node), Is.EquivalentTo(new long?[] { 8L, 9L }));
            }
        });
    }

    // v3 limits (M3): «reached.false.steps.1.ms.2317.model_ms.15.computer_use_window_elevated» passed the trace's 64
    // characters and the whole end line was written «invalid»; the counts stay and the code has its own line.
    [Test]
    public void TheEndTraceLineNeverHidesItsCountsBehindALongStopCode()
    {
        string longStop = ComputerUseMission.EndTraceDetail(false, 1, 2317, 15, "computer_use_window_elevated");
        string shortStop = ComputerUseMission.EndTraceDetail(true, 3, 900, 0, null);
        Assert.Multiple(() =>
        {
            Assert.That(longStop, Is.EqualTo("reached.false.steps.1.ms.2317.model_ms.15"));
            Assert.That(ShellTrace.SanitizeLabel(longStop), Is.EqualTo(longStop));
            Assert.That(shortStop, Is.EqualTo("reached.true.steps.3.ms.900.model_ms.0.ok"));
            Assert.That(ShellTrace.SanitizeLabel("computer_use_window_elevated"), Is.EqualTo("computer_use_window_elevated"));
        });
    }

    // lat-e5 (r13a: «model_ms» summed 728 s where the model took 188 s; the rest was the wait for a loading E5): the
    // mind's encoder time goes apart, the model's time is what is left, and the end line says both.
    [Test]
    public void TheEncodersTimeIsToldApartFromTheModels()
    {
        var cold = new MindComputerUseStep("input.visible.click", new JsonObject(), "", EncoderMs: 9_000);
        var lying = new MindComputerUseStep("input.visible.click", new JsonObject(), "", EncoderMs: 50_000);
        var plain = new MindComputerUseStep("input.visible.click", new JsonObject(), "");
        string withEncoder = ComputerUseMission.EndTraceDetail(true, 4, 33783, 2271, null, 19000);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.SplitDecideTime(9_870, cold), Is.EqualTo((870L, 9_000L)));
            // Contracases: never more encoder time than the whole decision, none when the mind says none.
            Assert.That(ComputerUseMission.SplitDecideTime(9_870, lying), Is.EqualTo((0L, 9_870L)));
            Assert.That(ComputerUseMission.SplitDecideTime(870, plain), Is.EqualTo((870L, 0L)));
            Assert.That(ComputerUseMission.SplitDecideTime(870, null), Is.EqualTo((870L, 0L)));
            Assert.That(withEncoder, Is.EqualTo("reached.true.steps.4.ms.33783.model_ms.2271.encoder_ms.19000.ok"));
            Assert.That(ShellTrace.SanitizeLabel(withEncoder), Is.EqualTo(withEncoder));
            Assert.That(ComputerUseMission.EndTraceDetail(true, 3, 900, 0, null, 0), Is.EqualTo("reached.true.steps.3.ms.900.model_ms.0.ok"));
            Assert.That(MindSidecarClient.EncoderMilliseconds(JsonValue.Create(1520)), Is.EqualTo(1520));
            Assert.That(MindSidecarClient.EncoderMilliseconds(JsonValue.Create(-3)), Is.Zero);
            Assert.That(MindSidecarClient.EncoderMilliseconds(JsonValue.Create(999_999)), Is.Zero);
            Assert.That(MindSidecarClient.EncoderMilliseconds(JsonValue.Create("1520")), Is.Zero);
            Assert.That(MindSidecarClient.EncoderMilliseconds(null), Is.Zero);
        });
    }

    // Review of lat-e5 (finding 4): a long chained mission's counts with the encoder's time passed the trace's 64
    // characters and the whole end line was written «invalid»; then the encoder's time is left to the step lines.
    [Test]
    public void TheEndLineFitsTheTraceWithTheEncodersTime()
    {
        string longest = ComputerUseMission.EndTraceDetail(false, 30, 312000, 104000, null, 10000);
        string fits = ComputerUseMission.EndTraceDetail(false, 3, 31200, 10400, null, 1000);
        Assert.Multiple(() =>
        {
            Assert.That(longest, Is.EqualTo("reached.false.steps.30.ms.312000.model_ms.104000.ok"));
            Assert.That(ShellTrace.SanitizeLabel(longest), Is.EqualTo(longest));
            Assert.That(fits, Is.EqualTo("reached.false.steps.3.ms.31200.model_ms.10400.encoder_ms.1000.ok"));
            Assert.That(ShellTrace.SanitizeLabel(fits), Is.EqualTo(fits));
        });
    }

    // v3 limits (M2, live v3-05): a gate the mind names is said only with a text the view really shows and a kind the
    // floor knows; anything else stays a stop without a step.
    [TestCase("Configuración de cuenta de correo electrónico", "account", true)]
    [TestCase("¿No tiene ninguna cuenta?", "account", true)]
    [TestCase("Iniciar sesión", "account", false)]
    [TestCase("Configuración de cuenta de correo electrónico", "invented", false)]
    public void AGateIsSaidOnlyWithTextTheViewShows(string text, string kind, bool said)
    {
        JsonObject view = View("""
            {"window": {"title": "Configuración de cuenta de correo electrónico", "process": "OUTLOOK"},
             "controls": [], "text": {"C": ["Outlook", "¿No tiene ninguna cuenta?"]}}
            """);
        var decision = new MindComputerUseStep(
            "none", new JsonObject { ["evidence"] = text, ["gate"] = kind }, "puerta", "app_gate");
        JsonObject? gate = ComputerUseMission.GateSeen(decision, view);
        Assert.That(gate is not null, Is.EqualTo(said));
        if (said)
        {
            Assert.That((string?)gate!["text"], Is.EqualTo(text));
            Assert.That((string?)gate["kind"], Is.EqualTo(kind));
        }

        // A «none» with another code is no gate whatever it carries.
        Assert.That(ComputerUseMission.GateSeen(decision with { Code = "no_step_visible" }, view), Is.Null);
    }

    // Revisión v3 límites: the control pressed on the gate to pass it («Ahora no») travels with the gate, so the final
    // never says nothing was pressed; a gate where nothing was pressed carries no such field.
    [TestCase("Ahora no", true)]
    [TestCase("", false)]
    public void AGateCarriesTheSkipPressedOnIt(string pressed, bool carried)
    {
        JsonObject view = View("""
            {"window": {"title": "Notas", "process": "NOTAS"},
             "controls": [], "text": {"C": ["Notas", "Inicia sesión para sincronizar tus notas"]}}
            """);
        var arguments = new JsonObject { ["evidence"] = "Inicia sesión para sincronizar tus notas", ["gate"] = "account" };
        if (pressed.Length > 0)
        {
            arguments["pressed"] = pressed;
        }

        JsonObject? gate = ComputerUseMission.GateSeen(new MindComputerUseStep("none", arguments, "puerta", "app_gate"), view);
        Assert.That(gate, Is.Not.Null);
        Assert.That(gate!.ContainsKey("pressed"), Is.EqualTo(carried));
        if (carried)
        {
            Assert.That((string?)gate["pressed"], Is.EqualTo(pressed));
        }
    }

    // Pasada v3 05:40 (v3-14): every step's trace read «model» and a literal step of an E5 still loading could not be
    // told from a literal choice. The trace carries the mind's source and a cold or failed encoder.
    [TestCase("", "", "model")]
    [TestCase("rule", "", "rule")]
    [TestCase("semantic", "ready", "semantic")]
    [TestCase("rule", "cold", "rule.e5_cold")]
    [TestCase("model", "failed", "model.e5_failed")]
    public void TraceSaysWhereTheStepCameFromAndAColdEncoder(string source, string encoder, string expected)
    {
        var decision = new MindComputerUseStep("input.visible.click", new JsonObject(), "r", Source: source, Encoder: encoder);
        Assert.That(ComputerUseMission.DecisionSource(decision), Is.EqualTo(expected));
        string label = $"step.2.input.visible.click.{expected}";
        Assert.That(ShellTrace.SanitizeLabel(label), Is.EqualTo(label));
    }

    [Test]
    public void TraceWordsFromTheMindAreShortLowercaseWordsOnly()
    {
        Assert.That(MindSidecarClient.TraceWord(JsonValue.Create("semantic")), Is.EqualTo("semantic"));
        Assert.That(MindSidecarClient.TraceWord(JsonValue.Create("Semantic")), Is.Empty);
        Assert.That(MindSidecarClient.TraceWord(JsonValue.Create("rule.e5")), Is.Empty);
        Assert.That(MindSidecarClient.TraceWord(JsonValue.Create(3)), Is.Empty);
        Assert.That(MindSidecarClient.TraceWord(null), Is.Empty);
    }

    // Safety review r10a: switching windows, the Start menu and the Task Manager act on the desktop over the person
    // wherever the key is bound: never a mission step, also when a rule or a model names them.
    // Contracase: keys that act inside the window, and other operations, pass on to the window binding.
    [TestCase("input.key.press", "alt_tab", true)]
    [TestCase("input.key.press", "win", true)]
    [TestCase("input.key.press", "ctrl_shift_escape", true)]
    [TestCase("input.key.press", "Win ", true)]
    [TestCase("input.key.press", "escape", false)]
    [TestCase("input.key.press", "tab", false)]
    [TestCase("input.key.press", "context_menu", false)]
    [TestCase("input.text.type", "win", false)]
    public void KeysThatActOutsideTheWindowAreNeverAMissionStep(string operation, string key, bool leaves)
    {
        var arguments = new JsonObject { ["key"] = key };
        Assert.That(ComputerUseMission.KeyLeavesTheWindow(operation, arguments), Is.EqualTo(leaves));
    }

    // Live n5: «Wi-Fi» on a PC without Wi-Fi. The window's own search typed the name and listed no item a person clicks
    // called so (only a description that mentions it): the place is not in that window. A result that names it, a name
    // never searched, or a text typed into a box that is no search keep the old stop.
    [TestCase("Cuadro de búsqueda, Buscar una opción", "wi-fi", "Text", true)]
    [TestCase("Cuadro de búsqueda, Buscar una opción", "wi-fi", "ListItem", false)]
    [TestCase("Cuadro de búsqueda, Buscar una opción", "proxy", "Text", false)]
    [TestCase("Nombre", "wi-fi", "Text", false)]
    public void APlaceSearchedByNameAndNotListedIsNotFound(string into, string typed, string resultKind, bool notFound)
    {
        var steps = new JsonArray
        {
            new JsonObject { ["step"] = 1, ["operation"] = "input.visible.click", ["label"] = "wi-fi", ["ok"] = true, ["name"] = "Wi-Fi" },
            new JsonObject { ["step"] = 2, ["operation"] = "input.text.type", ["into"] = into, ["text"] = typed, ["ok"] = true },
        };
        var view = new JsonObject
        {
            ["controls"] = new JsonArray
            {
                new JsonObject { ["kind"] = "Edit", ["name"] = into, ["value"] = typed },
                new JsonObject { ["kind"] = "ListItem", ["name"] = "Red e Internet" },
                new JsonObject { ["kind"] = resultKind, ["name"] = "Usa un servidor proxy para conexiones Ethernet o Wi-Fi." },
            },
        };
        Assert.That(OperationFloor.PlaceAsked("ir a wi-fi"), Is.EqualTo("wi-fi"));
        Assert.That(ComputerUseSuccessCheck.SearchedAndNotFound("wi-fi", steps, view), Is.EqualTo(notFound));
    }

    // The first look after a click can come before its effect is drawn: every look until the next step measures what
    // appeared against the text seen right before the click, and the next step keeps the last measure.
    [Test]
    public void WhatAClickMadeAppearIsMeasuredAgainstTheTextBeforeItOnEveryLook()
    {
        static JsonObject Look(params string[] lines) =>
            new() { ["text"] = new JsonObject { ["C"] = new JsonArray([.. lines.Select(line => (JsonNode?)JsonValue.Create(line))]) } };
        static string[] After(JsonObject view) =>
            [.. ((JsonArray)view["newTextAfterClick"]!).Select(node => (string?)node ?? string.Empty)];

        var state = new JsonObject
        {
            ["subgoals"] = new JsonArray(new JsonObject { ["goal"] = "abrir el menu" }),
            ["steps"] = new JsonArray(),
        };
        var steps = (JsonArray)state["steps"]!;
        void Note(JsonObject view) =>
            ComputerUseMission.NoteWhatAppeared(state, view, ComputerUseSuccessCheck.TextLines(view), steps, 0);

        JsonObject first = Look("Archivo", "Editar");
        Note(first);
        state["textBeforeClick"] = new JsonObject { ["1"] = ComputerUseSuccessCheck.TextLines(first) };
        steps.Add(new JsonObject { ["step"] = 1, ["operation"] = "input.visible.click", ["label"] = "Archivo", ["ok"] = true });
        JsonObject tooSoon = Look("Archivo", "Editar");
        Note(tooSoon);
        JsonObject drawn = Look("Archivo", "Editar", "Abrir", "Guardar");
        Note(drawn);
        steps.Add(new JsonObject { ["step"] = 2, ["operation"] = "input.key.press", ["key"] = "down", ["ok"] = true });
        JsonObject afterNextStep = Look("Archivo", "Editar", "Abrir", "Guardar", "Reciente");
        Note(afterNextStep);
        Assert.Multiple(() =>
        {
            Assert.That(After(tooSoon), Is.Empty, "the effect is not drawn yet");
            Assert.That(After(drawn), Is.EqualTo(new[] { "abrir", "guardar" }), "a later look finds it");
            Assert.That(After(afterNextStep), Is.EqualTo(new[] { "abrir", "guardar" }), "the next step keeps the last measure");
        });
    }

    [Test]
    public void ALaterClickElsewhereUndoesAnEarlierArrivalByClick()
    {
        JsonObject store = View("""
            {"window": {"title": "Steam"}, "controls": [],
             "text": {"TL": ["TIENDA", "Explorar", "Recomendaciones", "Categorías", "Buscar en la tienda", "REBAJAS"]}}
            """);
        store["textBeforeClick"] = new JsonObject
        {
            ["1"] = new JsonArray("comunidad", "actividad", "perfil", "amigos", "grupos", "insignias"),
            ["3"] = new JsonArray("biblioteca", "pagina principal", "colecciones", "descargas", "juegos", "batman"),
        };
        JsonArray steps =
        [
            new JsonObject { ["step"] = 1, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "BIBLIOTECA" },
            new JsonObject { ["step"] = 3, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "TIENDA" },
        ];
        Assert.That(ComputerUseSuccessCheck.Evaluate("page:biblioteca", store, steps, out _), Is.False);
    }

    [Test]
    public void AnItemNamedWithItsApplicationAfterThePlaceIsThePlace()
    {
        JsonObject scientific = View("""
            {"window": {"title": "Calculadora"}, "controls": [
              {"i": 0, "kind": "Button", "name": "Abrir navegación", "zone": "TL"}, {"i": 1, "kind": "Button", "name": "Alternar grados", "zone": "L"},
              {"i": 2, "kind": "Button", "name": "Notación científica", "zone": "L"}, {"i": 3, "kind": "Button", "name": "Seno", "zone": "C"},
              {"i": 4, "kind": "Button", "name": "Coseno", "zone": "C"}]}
            """);
        scientific["selectedBeforeClick"] = new JsonObject { ["3"] = new JsonArray("estandar calculadora") };
        scientific["controlsBeforeClick"] = new JsonObject { ["3"] = new JsonArray("cerrar navegacion", "estandar calculadora", "cientifica calculadora", "graficar calculadora") };
        JsonArray clicked = [new JsonObject { ["step"] = 3, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "Científica Calculadora" }];
        Assert.That(ComputerUseSuccessCheck.Evaluate("page:cientifica", scientific, clicked, out _), Is.True);
    }

    [Test]
    public void AModeReachedFromAnotherModeWhoseNewPageBringsATabChosenArrived()
    {
        // Measured 2026-10-07 (x1): the Calculator left in Programador; «Científica Calculadora» clicked in its
        // navigation, the pane closed and the scientific page came with its «Historial» tab selected (absent before).
        string[] shared = ["abrir navegacion", "borrar", "retroceso", "cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete",
            "ocho", "nueve", "mas", "menos", "es igual a", "dividido por", "multiplicar por", "modulo", "parentesis de apertura"];
        string[] pane = ["cerrar navegacion", "estandar calculadora", "cientifica calculadora", "graficar calculadora",
            "programador calculadora", "configuracion", "no hay nada guardado en la memoria. memoria", "hexadecimal 0", "decimal 0",
            "bit a bit", "desplazamiento de bits", "mayus izquierda"];
        JsonObject Page(string selected, params string[] names)
        {
            var controls = new JsonArray();
            int index = 0;
            foreach (string name in names)
            {
                var control = new JsonObject { ["i"] = index++, ["kind"] = name.EndsWith("calculadora", StringComparison.Ordinal) ? "ListItem" : "Button", ["name"] = name };
                if (name == selected)
                {
                    control["kind"] = name.Contains("historial", StringComparison.Ordinal) ? "TabItem" : "ListItem";
                    control["state"] = "selected";
                }

                controls.Add(control);
            }

            JsonObject view = View("""{"window": {"title": "Calculadora"}, "controls": []}""");
            view["controls"] = controls;
            view["selectedBeforeClick"] = new JsonObject { ["3"] = new JsonArray("programador calculadora", "no hay nada guardado en la memoria. memoria") };
            view["controlsBeforeClick"] = new JsonObject { ["3"] = new JsonArray(pane.Concat(shared[1..]).Select(name => (JsonNode?)JsonValue.Create(name)).ToArray()) };
            return view;
        }

        string[] scientificPage = [.. shared, "alternar grados", "notacion cientifica", "sumar memoria", "trigonometria", "funciones",
            "pi", "numero de euler", "cuadrado", "raiz cuadrada", "logaritmo", "factorial", "no hay historial todavia. historial"];
        JsonObject scientific = Page("no hay historial todavia. historial", scientificPage);
        // The pane still open with another listed item chosen: the click landed on it, not on the place.
        JsonObject landedElsewhere = Page("estandar calculadora", [.. scientificPage[..^1], .. pane[1..4]]);
        JsonArray Click(string label) => [new JsonObject { ["step"] = 3, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = label }];
        JsonArray escaped =
        [
            new JsonObject { ["step"] = 2, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "Abrir navegación" },
            new JsonObject { ["step"] = 3, ["operation"] = "input.key.press", ["ok"] = true, ["key"] = "escape" },
        ];
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:cientifica", scientific, Click("Científica Calculadora"), out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:cientifica", scientific, escaped, out _), Is.False, "the menu closed, nothing chosen");
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:cientifica", scientific, Click("Graficar Calculadora"), out _), Is.False, "another item clicked");
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:conversor", scientific, Click("Conversor Calculadora"), out _), Is.False, "a place absent");
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:cientifica", landedElsewhere, Click("Científica Calculadora"), out _), Is.False, "another listed item chosen");
        });
    }

    [Test]
    public void ANavigationItemBesideACardOfThePageIsStillNavigation()
    {
        JsonObject clock = View("""
            {"window": {"title": "Reloj"}, "controls": [
              {"i": 0, "kind": "ListItem", "name": "Alarma", "state": "selected", "zone": "TL", "rect": {"x": 10, "y": 200, "w": 180, "h": 40}},
              {"i": 1, "kind": "ListItem", "name": "7:00 Alarma", "zone": "C", "rect": {"x": 300, "y": 160, "w": 420, "h": 120}}]}
            """);
        JsonObject tiles = View("""
            {"window": {"title": "Inicio - Explorador de archivos"}, "controls": [
              {"i": 0, "kind": "ListItem", "name": "Descargas", "state": "selected", "zone": "TL", "rect": {"x": 200, "y": 200, "w": 160, "h": 60}},
              {"i": 1, "kind": "ListItem", "name": "Documentos", "zone": "T", "rect": {"x": 380, "y": 200, "w": 160, "h": 60}}]}
            """);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:alarma:current", clock, [], out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:descargas:current", tiles, [], out _), Is.False, "a tile of a grid only chosen");
        });
    }

    // Ronda 20b, palanca 8 (pasada r18, v3-62): the frame of a packaged application as its first look read it (the
    // evidence's view: three caption buttons named after the window, its title as Window and Text, the title bar and
    // the system menu chain the provider marks). It is nothing to act on, so the window is still starting.
    private static JsonObject PackagedFrame() => View("""
        {"window": {"title": "Seguridad de Windows", "process": "SecHealthUI", "hwnd": 10012}, "controls": [
          {"i": 0, "kind": "Button", "name": "Minimizar Seguridad de Windows", "rect": {"x": 1580, "y": 0, "w": 46, "h": 32}},
          {"i": 1, "kind": "Button", "name": "Maximizar Seguridad de Windows", "rect": {"x": 1626, "y": 0, "w": 46, "h": 32}},
          {"i": 2, "kind": "Button", "name": "Cerrar Seguridad de Windows", "rect": {"x": 1672, "y": 0, "w": 46, "h": 32}},
          {"i": 3, "kind": "Window", "name": "Seguridad de Windows", "state": "readonly", "value": "Seguridad de Windows", "rect": {"x": 0, "y": 0, "w": 1720, "h": 1000}},
          {"i": 4, "kind": "MenuBar", "name": "Sistema", "systemMenu": true, "rect": {"x": 0, "y": 0, "w": 32, "h": 32}},
          {"i": 5, "kind": "MenuItem", "name": "Sistema", "systemMenu": true, "rect": {"x": 0, "y": 0, "w": 32, "h": 32}},
          {"i": 6, "kind": "Text", "name": "Seguridad de Windows", "rect": {"x": 40, "y": 6, "w": 160, "h": 20}},
          {"i": 7, "kind": "TitleBar", "name": "Seguridad de Windows", "rect": {"x": 0, "y": 0, "w": 1720, "h": 32}}],
         "text": {"TL": ["Seguridad de Windows"], "TR": ["x"]}}
        """);

    [Test]
    public void TheFrameOfAWindowAndItsSystemMenuAreNothingToActOn()
    {
        JsonObject frame = PackagedFrame();
        JsonObject content = PackagedFrame();
        ((JsonArray)content["controls"]!).Add(View("""
            {"i": 8, "kind": "ListItem", "name": "Firewall y protección de red", "rect": {"x": 0, "y": 300, "w": 300, "h": 40}}
            """));
        // Contracase: an application with two real controls (a notepad) and a caption-named button of its content.
        JsonObject notepad = View("""
            {"window": {"title": "Sin título: Bloc de notas", "hwnd": 77}, "controls": [
              {"i": 0, "kind": "TitleBar", "name": "Sin título: Bloc de notas", "rect": {"x": 0, "y": 0, "w": 900, "h": 32}},
              {"i": 1, "kind": "Button", "name": "Cerrar Sin título: Bloc de notas", "rect": {"x": 850, "y": 0, "w": 46, "h": 32}},
              {"i": 2, "kind": "MenuItem", "name": "Archivo", "rect": {"x": 0, "y": 40, "w": 60, "h": 24}},
              {"i": 3, "kind": "Button", "name": "Cerrar todas las pestañas", "rect": {"x": 300, "y": 40, "w": 24, "h": 24}},
              {"i": 4, "kind": "Document", "name": "Editor de texto", "rect": {"x": 0, "y": 70, "w": 900, "h": 600}}]}
            """);
        // Contracase: a system menu the provider did not mark (an older look) still counts as before.
        JsonObject unmarked = PackagedFrame();
        foreach (JsonObject control in ((JsonArray)unmarked["controls"]!).OfType<JsonObject>())
        {
            control.Remove("systemMenu");
        }

        static bool StartingAfterSettle(JsonObject view)
        {
            var state = new JsonObject();
            _ = ComputerUseMission.StillStarting(state, view, TimeSpan.FromMilliseconds(1000));
            return ComputerUseMission.StillStarting(state, view, TimeSpan.FromMilliseconds(1000) + ComputerUseMission.StartSettle);
        }

        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.ActionableCount(frame), Is.EqualTo(0), "v3-62: caption buttons in the title bar, system menu");
            Assert.That(ComputerUseMission.ShowsOnlyTheFrame(frame), Is.True);
            Assert.That(StartingAfterSettle(frame), Is.True, "v3-62: a frame alone is still starting until StartWait");
            Assert.That(ComputerUseMission.StillStarting(new JsonObject(), frame, ComputerUseMission.StartWait), Is.False,
                "at StartWait it is taken as it is");
            Assert.That(ComputerUseMission.ActionableCount(content), Is.EqualTo(1));
            Assert.That(ComputerUseMission.ShowsOnlyTheFrame(content), Is.False);
            Assert.That(ComputerUseMission.ActionableCount(notepad), Is.EqualTo(2), "«Archivo» and «Cerrar todas las pestañas» outside the title bar");
            Assert.That(StartingAfterSettle(notepad), Is.False, "two real controls: started at the second look as today");
            Assert.That(ComputerUseMission.ActionableCount(unmarked), Is.EqualTo(2), "unmarked menus keep counting");
        });
    }

    // Review 3 of palanca 8 (B2): a notice that only writes, with its title-bar close, is a window to leave, not a
    // frame still waiting for its content; nor is a dialog drawn over the window. Contracase: the frame alone (v3-62).
    [Test]
    public void ANoticeWhoseCloseIsTheWayOutIsNotAFrameAlone()
    {
        JsonObject notice = View("""
            {"window": {"title": "Aviso", "hwnd": 501}, "controls": [
              {"i": 0, "kind": "TitleBar", "name": "Aviso", "rect": {"x": 300, "y": 300, "w": 400, "h": 30}},
              {"i": 1, "kind": "Button", "name": "Cerrar", "rect": {"x": 660, "y": 302, "w": 36, "h": 26}},
              {"i": 2, "kind": "Text", "name": "La operación terminó", "rect": {"x": 320, "y": 360, "w": 300, "h": 20}}],
             "text": {"C": ["La operación terminó"]}}
            """);
        JsonObject framed = PackagedFrame();
        ((JsonArray)framed["controls"]!).Add(View("""{"i": 8, "kind": "TitleBar", "name": "Aviso", "rect": {"x": 300, "y": 300, "w": 400, "h": 30}}"""));
        ((JsonArray)framed["controls"]!).Add(View("""{"i": 9, "kind": "Button", "name": "Cerrar", "rect": {"x": 660, "y": 302, "w": 36, "h": 26}}"""));
        JsonObject bare = View("""
            {"window": {"title": "Añadir escena", "hwnd": 502}, "controls": [
              {"i": 0, "kind": "Button", "name": "Cerrar", "rect": {"x": 660, "y": 102, "w": 36, "h": 26}},
              {"i": 1, "kind": "TitleBar", "name": "Añadir escena", "rect": {"x": 100, "y": 100, "w": 600, "h": 30}}]}
            """);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.CloseIsTheWayOut(notice), Is.True);
            Assert.That(ComputerUseMission.ShowsOnlyTheFrame(notice), Is.False, "its close leaves it");
            Assert.That(ComputerUseMission.ShowsOnlyTheFrame(framed), Is.False, "a dialog over the window, its own close");
            Assert.That(ComputerUseMission.ShowsOnlyTheFrame(PackagedFrame()), Is.True, "v3-62: the frame alone");
            Assert.That(ComputerUseMission.ShowsOnlyTheFrame(bare), Is.True, "v3-51: the frame alone, its content not read");
        });
    }

    [Test]
    public void AShellWithAnAddressBarAndPanesIsNothingToActOn()
    {
        JsonObject starting = View("""
            {"window": {"title": "Spotify"}, "controls": [
              {"i": 0, "kind": "Edit", "name": "Address and search bar", "state": "readonly", "value": "xpui.app.spotify.com/index.html"},
              {"i": 1, "kind": "Pane", "name": "Spotify"}, {"i": 2, "kind": "Pane", "name": "Spotify"}],
             "text": {"TR": ["x"]}}
            """);
        JsonObject loaded = View("""
            {"window": {"title": "Spotify"}, "controls": [
              {"i": 0, "kind": "Button", "name": "Inicio"}, {"i": 1, "kind": "Button", "name": "Tu biblioteca"}]}
            """);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.ActionableCount(starting), Is.EqualTo(0));
            Assert.That(ComputerUseMission.ActionableCount(loaded), Is.EqualTo(2));
            Assert.That(ComputerUseMission.ActionableCount(View("""
                {"window": {"title": "WhatsApp"}, "controls": [
                  {"i": 0, "kind": "Button", "name": "Minimize"}, {"i": 1, "kind": "Button", "name": "Maximize"},
                  {"i": 2, "kind": "Button", "name": "Close"}, {"i": 3, "kind": "Pane", "name": "AppWindow Custom Title Bar"}]}
                """)), Is.EqualTo(0), "caption buttons are not content");
        });
    }

    [Test]
    public void TypingCountsOnlyWhenTheFocusedFieldShowsTheTextOrDoesNotExposeIt()
    {
        JsonArray typed = [new JsonObject { ["step"] = 2, ["operation"] = "input.text.type", ["ok"] = true, ["text"] = "lista: pan" }];
        JsonObject garbled = View("""
            {"window": {"title": "Sin título: Bloc de notas", "focused": {"kind": "Document", "name": "Editor de texto", "value": "lista:nnnn"}}, "controls": []}
            """);
        JsonObject whole = View("""
            {"window": {"title": "Sin título: Bloc de notas", "focused": {"kind": "Document", "name": "Editor de texto", "value": "lista: pan\rleche"}}, "controls": []}
            """);
        JsonObject unexposed = View("""
            {"window": {"title": "Discord", "focused": {"kind": "Edit", "name": "Enviar mensaje a @Ron92", "value": null}}, "controls": []}
            """);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.text.type", garbled, typed, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.text.type", whole, typed, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.text.type", unexposed, typed, out _), Is.True);
        });
    }

    // Ronda 20 P1 (pasada r18, v3-11 t2 seq 81-82): «escribe ahí» went into the empty «Título de página» of the page
    // «Sin título» that already existed, and the term passed on the receipt alone.
    [Test]
    public void TypingIntoAPartOfTheDocumentTheStepDidNotChooseReachesNoSubGoal()
    {
        JsonObject page = View("""
            {"window": {"title": "Comprar pan - OneNote", "focused": {"kind": "Document", "name": "Título de página", "value": "Comprar pan"}}, "controls": []}
            """);
        JsonArray atCaret = [new JsonObject { ["step"] = 1, ["operation"] = "input.text.type", ["ok"] = true, ["text"] = "Comprar pan", ["into"] = "Título de página" }];
        JsonArray chosen = [new JsonObject { ["step"] = 1, ["operation"] = "input.text.type", ["ok"] = true, ["text"] = "Comprar pan", ["into"] = "Título de página", ["field"] = "Título de página" }];
        JsonObject notepad = View("""
            {"window": {"title": "Sin título: Bloc de notas", "focused": {"kind": "Document", "name": "Editor de texto", "value": "Comprar pan"}}, "controls": []}
            """);
        JsonArray body = [new JsonObject { ["step"] = 1, ["operation"] = "input.text.type", ["ok"] = true, ["text"] = "Comprar pan", ["into"] = "Editor de texto" }];
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.text.type", page, atCaret, out _), Is.False);
            // Contracases: the part the step chose («ponele de título …»), and a document's body at the caret.
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.text.type", page, chosen, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.text.type", notepad, body, out _), Is.True);
        });
    }

    // Review of r20 P1 (finding 2): «into» is what had the keyboard before the step; a text the step sent to the field it
    // chose (by «field», or the «index» it was resolved to) went there, and the step is done. Finding 3: «Sin título» and
    // «Untitled» name a whole document without a title, never its title part.
    [Test]
    public void ATextSentToItsChosenFieldOrIntoAnUntitledDocumentIsNoTextIntoAnUnnamedPart()
    {
        JsonObject form = View("""
            {"window": {"title": "Nueva tarea", "focused": {"kind": "Edit", "name": "Agregar un título"}}, "controls": [{"i": 5, "kind": "Edit", "name": "Descripción", "value": "Comprar pan"}]}
            """);
        JsonArray byField = [new JsonObject { ["step"] = 1, ["operation"] = "input.text.type", ["ok"] = true, ["text"] = "Comprar pan", ["into"] = "Agregar un título", ["field"] = "Descripción", ["replace"] = true }];
        JsonArray byIndex = [new JsonObject { ["step"] = 1, ["operation"] = "input.text.type", ["ok"] = true, ["text"] = "Comprar pan", ["into"] = "Agregar un título", ["index"] = 5, ["replace"] = true }];
        JsonArray atCaret = [new JsonObject { ["step"] = 1, ["operation"] = "input.text.type", ["ok"] = true, ["text"] = "Comprar pan", ["into"] = "Agregar un título" }];
        JsonObject untitled = View("""
            {"window": {"title": "Documento sin título - Documentos de Google", "focused": {"kind": "Document", "name": "Documento sin título - Documentos de Google", "value": "hola mundo"}}, "controls": []}
            """);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.text.type", form, byField, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.text.type", form, byIndex, out _), Is.True);
            Assert.That(OperationFloor.TypedIntoUnnamedPart((JsonObject)byField[0]!), Is.False);
            // Contracase: the same text at the caret went into the title the step did not choose.
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.text.type", form, atCaret, out _), Is.False);
            foreach (string name in new[] { "Sin título", "Documento sin título - Documentos de Google", "Untitled", "No title" })
            {
                JsonArray typed = [new JsonObject { ["step"] = 1, ["operation"] = "input.text.type", ["ok"] = true, ["text"] = "hola mundo", ["into"] = name }];
                Assert.That(OperationFloor.TypedIntoUnnamedPart((JsonObject)typed[0]!), Is.False, name);
                Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.text.type", untitled, typed, out _), Is.True, name);
            }

            Assert.That(OperationFloor.TypedIntoUnnamedPart(new JsonObject { ["into"] = "Page title" }), Is.True);
        });
    }

    // Review 2 of r20 P1 (finding 1, v3-11 t2 as the App runs it): the worker gives window.focused its «i» (39 ·
    // Document · «Título de página» · focused), BindToMissionWindow names that index for a text at the caret and the
    // receipt copies it. That index is the App's, read from the focus, never a choice of the step: the text that went
    // into the page's title reaches no sub-goal. Contracases: the same title named by the step («field»), and the
    // field the sub-goal's last click aimed at while the window reports no focus.
    [Test]
    public void AnIndexReadFromTheFocusIsNoChoiceOfTheStepThatTypedIntoAPart()
    {
        JsonObject page = View("""
            {"window": {"title": "Sin título - OneNote", "processId": 55, "hwnd": 8, "focused": {"kind": "Document", "name": "Título de página", "i": 39}},
             "controls": [{"i": 36, "kind": "ListItem", "name": "Sin título", "state": "selected"},
                          {"i": 39, "kind": "Document", "name": "Título de página", "state": "focused"},
                          {"i": 41, "kind": "Document", "name": "Contenido de la página", "state": ""}]}
            """);
        JsonObject after = View("""
            {"window": {"title": "comprar pan - OneNote", "processId": 55, "hwnd": 8, "focused": {"kind": "Document", "name": "Título de página", "i": 39}},
             "controls": [{"i": 39, "kind": "Document", "name": "Título de página", "value": "comprar pan", "state": "focused"}]}
            """);
        var state = new JsonObject { ["processId"] = 55 };
        JsonObject Receipt(JsonObject arguments, JsonObject view, JsonArray? before = null)
        {
            Assert.That(ComputerUseMission.BindToMissionWindow("input.text.type", arguments, view, state, "OneNote", before), Is.True);
            var record = new JsonObject { ["step"] = 1, ["operation"] = "input.text.type", ["ok"] = true };
            ComputerUseMission.NoteWhereTheTextGoes(record, arguments, view);
            foreach (string key in new[] { "index", "text", "field", "replace" })
            {
                if (arguments[key] is JsonNode value)
                    record[key] = value.DeepClone();
            }

            return record;
        }

        JsonObject atCaret = Receipt(new JsonObject { ["text"] = "comprar pan" }, page);
        JsonObject named = Receipt(new JsonObject { ["text"] = "comprar pan", ["field"] = "Título de página" }, page);
        JsonObject unfocused = View("""
            {"window": {"title": "Sin título - OneNote", "processId": 55, "hwnd": 8, "focused": {"kind": "Pane", "name": "Título"}},
             "controls": [{"i": 39, "kind": "Document", "name": "Título de página", "state": ""},
                          {"i": 41, "kind": "Document", "name": "Contenido de la página", "state": ""}]}
            """);
        var clicked = new JsonArray(new JsonObject { ["operation"] = "input.visible.click", ["label"] = "Contenido de la página", ["ok"] = true });
        JsonObject byClick = Receipt(new JsonObject { ["text"] = "comprar pan" }, unfocused, clicked);
        Assert.Multiple(() =>
        {
            Assert.That((int?)atCaret["index"], Is.EqualTo(39), "the App names the focused field's index, as live");
            Assert.That((bool?)atCaret["atCaret"], Is.True);
            Assert.That(OperationFloor.TypedIntoUnnamedPart(atCaret), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.text.type", after, [atCaret], out _), Is.False);
            Assert.That((int?)named["index"], Is.EqualTo(39));
            Assert.That(named["atCaret"], Is.Null);
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.text.type", after, [named], out _), Is.True);
            Assert.That((int?)byClick["index"], Is.EqualTo(41));
            Assert.That(byClick["atCaret"], Is.Null, "the clicked body's index is the sub-goal's choice");
            Assert.That(OperationFloor.TypedIntoUnnamedPart(byClick), Is.False);
        });
    }

    // Review 3 of r20 P1 (B1): Word exposes its focused body as the Document called as the file. A person's file called
    // «Proyecto de título» (or «Seminario de Título - Capítulo 2», «Cover letter header») is the document itself, never
    // its title part: the text at the caret went into it, the step is done, and the final names no part. Contracases:
    // a part of a document («Título de página» in «Sin título - OneNote», «Título 1» in Word) stays a part.
    [Test]
    public void ADocumentCalledAsTheWindowsFileIsNoPartOfItself()
    {
        var state = View("""{"processId": 77}""");
        foreach ((string document, string title) in new[]
                 {
                     ("Proyecto de título", "Proyecto de título - Word"),
                     ("Proyecto de título", "Proyecto de título.docx  -  Modo de compatibilidad - Word"),
                     ("Seminario de Título - Capítulo 2", "Seminario de Título - Capítulo 2 - Word"),
                     ("Cover letter header", "Cover letter header - Word"),
                 })
        {
            JsonObject view = View("""
                {"window": {"title": "", "processId": 77, "hwnd": 9, "focused": {"kind": "Document", "name": "", "i": 50}},
                 "controls": [{"i": 50, "kind": "Document", "name": "", "value": "Introducción hola mundo", "state": "focused"}]}
                """);
            view["window"]!["title"] = title;
            view["window"]!["focused"]!["name"] = document;
            view["controls"]![0]!["name"] = document;
            var arguments = new JsonObject { ["text"] = "hola mundo" };
            Assert.That(ComputerUseMission.BindToMissionWindow("input.text.type", arguments, view, state, "Word", null), Is.True);
            var record = new JsonObject { ["step"] = 1, ["operation"] = "input.text.type", ["ok"] = true, ["text"] = "hola mundo" };
            ComputerUseMission.NoteWhereTheTextGoes(record, arguments, view);
            if (arguments["index"] is JsonNode index)
                record["index"] = index.DeepClone();
            Assert.Multiple(() =>
            {
                Assert.That((bool?)record["intoDocument"], Is.True, title);
                Assert.That(OperationFloor.TypedIntoUnnamedPart(record), Is.False, title);
                Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.text.type", view, [record.DeepClone()], out _), Is.True, title);
            });
        }

        Assert.Multiple(() =>
        {
            Assert.That(OperationFloor.NamesTheWindow("Sin título", "Sin título: Bloc de notas"), Is.True);
            foreach ((string name, string title) in new[]
                     {
                         ("Título de página", "Sin título - OneNote"), ("Título", "Sin título - OneNote"),
                         ("Título 1", "Proyecto de título - Word"), ("Título de la pestaña", "Windows PowerShell"),
                     })
            {
                Assert.That(OperationFloor.NamesTheWindow(name, title), Is.False, name);
            }

            var page = new JsonObject { ["step"] = 1, ["operation"] = "input.text.type", ["ok"] = true, ["text"] = "pan", ["into"] = "Título de página", ["index"] = 39, ["atCaret"] = true };
            Assert.That(OperationFloor.TypedIntoUnnamedPart(page), Is.True);
        });
    }

    // cu-v3 texto-webview, live wa-1 (journal 2026-10-08 18:36): the keys went to the frame of a WebView2 messaging
    // client (focus on no field), Windows accepted all 68 events and «stepDone» passed while the search box kept its
    // placeholder. The view after the step, as read: the frame's eight controls and its written text.
    private const string WebViewFrameAfterTyping = """
        {"window": {"title": "WhatsApp", "process": "WhatsApp.Root", "requested": true, "foreground": false,
          "focused": {"kind": "Pane", "name": "Non Client Input Sink Window", "value": null}},
         "controls": [
          {"i": 0, "kind": "Button", "name": "Minimize"}, {"i": 1, "kind": "Button", "name": "Maximize"},
          {"i": 2, "kind": "Button", "name": "Close"}, {"i": 3, "kind": "MenuItem", "name": "Sistema", "state": "collapsed"},
          {"i": 4, "kind": "Pane", "name": "Non Client Input Sink Window"}, {"i": 5, "kind": "Pane", "name": "AppWindow Custom Title Bar"},
          {"i": 6, "kind": "TitleBar", "name": "WhatsApp"}, {"i": 7, "kind": "MenuBar", "name": "Barra de menús del sistema"}],
         "text": {"TL": ["s", "WhatsApp", "Chats", "Q, Buscar un chat o iniciar uno nuevo", "Buscar un chat o iniciar uno nuevo",
                         "Todos", "No leídos 7", "Favoritos"],
                  "L": ["Contacto A", "Dale, nos vemos", "Juanito", "es revisar el informe nomas"], "C": ["15:31", "Enviar documento"]}}
        """;

    [Test]
    public void TypedTextOnAFocusThatIsNoFieldMustShowInTheViewsWrittenText()
    {
        JsonArray typed = [new JsonObject
        {
            ["step"] = 1, ["operation"] = "input.text.type", ["ok"] = true, ["text"] = "baxyprueba",
        }];
        JsonObject frame = View(WebViewFrameAfterTyping);
        JsonObject arrived = View(WebViewFrameAfterTyping.Replace(
            "\"Q, Buscar un chat o iniciar uno nuevo\", \"Buscar un chat o iniciar uno nuevo\"", "\"Q baxy prueba\"", StringComparison.Ordinal));
        // The content surface of the same client, the field holding the text (the worker's view of the WebView2).
        JsonObject surface = View("""
            {"window": {"title": "(5) WhatsApp", "process": "msedgewebview2", "focused": {"kind": "TabItem", "name": "Todos", "value": null}},
             "controls": [{"i": 4, "kind": "Document", "name": "(5) WhatsApp", "state": "readonly", "value": "https://web.whatsapp.com/"},
                          {"i": 16, "kind": "Edit", "name": "Buscar un chat o iniciar uno nuevo", "value": "baxyprueba"},
                          {"i": 17, "kind": "TabItem", "name": "Todos", "state": "selected"}]}
            """);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.text.type", frame, typed, out _), Is.False,
                "the placeholder still written: the text never arrived");
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.text.type", arrived, typed, out _), Is.True,
                "contracase: the written text shows it (the reading split the word)");
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.text.type", surface, typed, out _), Is.True,
                "contracase: a field of the view holds it");
        });
    }

    [Test]
    public void TypingIntoTheSearchBoxIsArrivedOnlyWhenTheBoxHoldsTheText()
    {
        // The check the mind writes for «escribí baxyprueba en el buscador de chats» (test_cu_v3_texto_webview: the
        // act, judged by the view after it) and the step its field rule sends (the box by its label, the focus kept).
        const string check = "stepDone:input.text.type";
        JsonArray typed = [new JsonObject
        {
            ["step"] = 1, ["operation"] = "input.text.type", ["ok"] = true, ["text"] = "baxyprueba",
            ["field"] = "Buscar un chat o iniciar uno nuevo", ["replace"] = true,
        }];
        // The keyboard stays on another field that shows its value (the address): the named box decides.
        JsonObject empty = View("""
            {"window": {"title": "(5) WhatsApp", "focused": {"kind": "Edit", "name": "Dirección", "value": "web.whatsapp.com"}},
             "controls": [{"i": 16, "kind": "Edit", "name": "Buscar un chat o iniciar uno nuevo", "value": ""}]}
            """);
        JsonObject held = View("""
            {"window": {"title": "(5) WhatsApp", "focused": {"kind": "Edit", "name": "Dirección", "value": "web.whatsapp.com"}},
             "controls": [{"i": 16, "kind": "Edit", "name": "Buscar un chat o iniciar uno nuevo", "value": "baxyprueba"}]}
            """);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, empty, typed, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, View(WebViewFrameAfterTyping), typed, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, held, typed, out _), Is.True);
            // Review r2 texto-webview, finding 3: a first look (no act) never passes, whatever the view shows.
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, held, [], out _), Is.False);
        });
    }

    // Review r2 texto-webview, finding 4: what the view showed right before the typing step, as the mission records it.
    private static JsonObject WithViewBeforeTyping(JsonObject after, JsonObject before)
    {
        after["viewBeforeTyping"] = new JsonObject { ["1"] = ComputerUseSuccessCheck.ViewBeforeTyping(before) };
        return after;
    }

    [Test]
    public void TypedTextAlreadyOnScreenBeforeTheStepIsNoProofOfTheTyping()
    {
        static JsonArray Typed(string text) =>
            [new JsonObject { ["step"] = 1, ["operation"] = "input.text.type", ["ok"] = true, ["text"] = text }];
        JsonObject frame = View(WebViewFrameAfterTyping);
        JsonObject Unchanged() => WithViewBeforeTyping(View(WebViewFrameAfterTyping), frame);
        // The surface whose read-only document holds the address before and after.
        const string surface = """
            {"window": {"title": "(5) WhatsApp", "focused": {"kind": "TabItem", "name": "Todos", "value": null}},
             "controls": [{"i": 4, "kind": "Document", "name": "(5) WhatsApp", "state": "readonly", "value": "https://web.whatsapp.com/"},
                          {"i": 16, "kind": "Edit", "name": "Buscar un chat o iniciar uno nuevo", "value": ""}],
             "text": {"TL": ["Chats", "Buscar un chat o iniciar uno nuevo"], "L": ["Juanito"]}}
            """;
        JsonObject arrivedOnSurface = WithViewBeforeTyping(
            View(surface.Replace("\"value\": \"\"}", "\"value\": \"whatsapp\"}", StringComparison.Ordinal)), View(surface));
        JsonObject arrivedAsText = WithViewBeforeTyping(View(WebViewFrameAfterTyping.Replace(
            "\"Q, Buscar un chat o iniciar uno nuevo\", \"Buscar un chat o iniciar uno nuevo\"", "\"Q Juanito\"", StringComparison.Ordinal)), frame);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.text.type", Unchanged(), Typed("Juanito"), out _), Is.False,
                "«Juanito» was in the chat list before the step");
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.text.type", Unchanged(), Typed("Buscar"), out _), Is.False,
                "the placeholder's word was there before");
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.text.type", Unchanged(), Typed("a"), out _), Is.False,
                "one letter is everywhere before the step too");
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.text.type",
                WithViewBeforeTyping(View(surface), View(surface)), Typed("whatsapp"), out _), Is.False,
                "the address the document held before");
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.text.type", arrivedOnSurface, Typed("whatsapp"), out _), Is.True,
                "contracase: the search box holds it now");
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.text.type", arrivedAsText, Typed("Juanito"), out _), Is.True,
                "contracase: the written text shows it one more time than before");
        });
    }

    [Test]
    public void TypedTextReadInPiecesOrHiddenStillCounts()
    {
        // Review r2 texto-webview, finding 5: false failures of the written-text rule.
        const string message = "¿Nos vemos mañana a las cinco, en la plaza de siempre?";
        JsonArray typed = [new JsonObject { ["step"] = 1, ["operation"] = "input.text.type", ["ok"] = true, ["text"] = message }];
        JsonObject before = View("""
            {"window": {"title": "Chat", "focused": {"kind": "Pane", "name": "frame"}}, "controls": [],
             "text": {"TL": ["Chat"], "B": ["Escribe un mensaje"]}}
            """);
        // Wrapped over two lines, «¿» read as «z» and the comma lost.
        JsonObject wrapped = WithViewBeforeTyping(View("""
            {"window": {"title": "Chat", "focused": {"kind": "Pane", "name": "frame"}}, "controls": [],
             "text": {"TL": ["Chat"], "B": ["Nos vemos mañana a las", "cinco en la plaza de siempre?"]}}
            """), before);
        // A one-line box scrolled to the end of the text.
        JsonObject scrolled = WithViewBeforeTyping(View("""
            {"window": {"title": "Chat", "focused": {"kind": "Pane", "name": "frame"}}, "controls": [],
             "text": {"TL": ["Chat"], "B": ["s cinco, en la plaza de siempre?"]}}
            """), before);
        // A long value set into a field without moving the focus, cut by the worker at 120 characters.
        string longText = new('x', 130);
        JsonObject cutBefore = View("""{"window": {"title": "Form"}, "controls": [{"i": 1, "kind": "Edit", "name": "Notas", "value": ""}]}""");
        JsonObject cut = WithViewBeforeTyping(View("""
            {"window": {"title": "Form"}, "controls": [{"i": 1, "kind": "Edit", "name": "Notas", "value": "CUT"}],
             "text": {"TL": ["Form"]}}
            """.Replace("CUT", new string('x', 120), StringComparison.Ordinal)), cutBefore);
        JsonArray typedLong = [new JsonObject { ["step"] = 1, ["operation"] = "input.text.type", ["ok"] = true, ["text"] = longText }];
        // A password shows dots.
        JsonObject password = View("""
            {"window": {"title": "Login", "focused": {"kind": "Edit", "name": "Contraseña", "state": "focused password", "value": null}},
             "controls": [{"i": 1, "kind": "Edit", "name": "Contraseña", "state": "focused password"}], "text": {"C": ["Login", "••••••"]}}
            """);
        JsonObject missing = WithViewBeforeTyping(View("""
            {"window": {"title": "Chat", "focused": {"kind": "Pane", "name": "frame"}}, "controls": [],
             "text": {"TL": ["Chat"], "B": ["Escribe un mensaje"]}}
            """), before);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.text.type", wrapped, typed, out _), Is.True, "wrapped");
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.text.type", scrolled, typed, out _), Is.True, "scrolled to its end");
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.text.type", cut, typedLong, out _), Is.True, "cut and changed");
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.text.type", password,
                [new JsonObject { ["step"] = 1, ["operation"] = "input.text.type", ["ok"] = true, ["text"] = "secreto" }], out _), Is.True, "password");
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.text.type", missing, typed, out _), Is.False,
                "contracase: the box still shows its placeholder");
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

    // v3 point 1, measured live: a messaging client's content is a window of a WebView2 child process drawn over its
    // empty WinUI frame. The provider reads that window as the application's surface and names the family (the
    // application's process first); the mission keeps the application's process and binds keys and text to the family,
    // never to another process.
    [Test]
    public void TheMissionBindsToTheFamilyOfItsApplicationAndToNoOtherProcess()
    {
        JsonObject surface = View("""
            {"window": {"title": "(2) WhatsApp", "process": "msedgewebview2", "processId": 11216, "hwnd": 66898,
             "requested": true, "family": [13884, 11216, 11220]}}
            """);
        var adopted = new JsonObject();
        ComputerUseMission.AdoptWindow(adopted, "WhatsApp", surface);
        var opened = new JsonObject { ["processId"] = 13884 };
        ComputerUseMission.AdoptWindow(opened, "WhatsApp", surface);
        var other = new JsonObject { ["processId"] = 500 };
        ComputerUseMission.AdoptWindow(other, "WhatsApp", surface);
        JsonObject unrequested = View("""
            {"window": {"title": "(2) WhatsApp", "process": "msedgewebview2", "processId": 11216, "hwnd": 66898}}
            """);
        JsonObject stranger = View("""
            {"window": {"title": "Sin título: Bloc de notas", "process": "notepad", "processId": 9, "hwnd": 77}}
            """);
        Assert.Multiple(() =>
        {
            Assert.That((int?)adopted["processId"], Is.EqualTo(13884), "the application's process, not its child's");
            Assert.That(adopted["family"]?.AsArray().Select(member => (int?)member), Is.EqualTo(new int?[] { 13884, 11216, 11220 }));
            Assert.That(opened["family"], Is.Not.Null);
            Assert.That(other["family"], Is.Null, "a family that does not start with the mission's process is not kept");
            Assert.That(ComputerUseMission.BindToMissionWindow("input.text.type", new JsonObject(), unrequested, opened, "WhatsApp"), Is.True,
                "a view of the family's window takes the text");
            Assert.That(ComputerUseMission.BindToMissionWindow("input.text.type", new JsonObject(), unrequested, new JsonObject { ["processId"] = 13884 }, "WhatsApp"), Is.False,
                "without the family read from the application, the child's window is another process");
            Assert.That(ComputerUseMission.BindToMissionWindow("input.key.press", new JsonObject(), stranger, opened, "WhatsApp"), Is.False);
            Assert.That(ComputerUseMission.OfTheMissionFamily(new JsonObject { ["processId"] = 500, ["family"] = new JsonArray(13884, 11216) },
                unrequested["window"] as JsonObject), Is.False, "a family is the mission's only when it starts with its process");
        });
    }

    // v3 point 1, measured on a game launcher with no accessible tree, opened cold: 2 written lines (its splash) at
    // 4.5 s, 16 at 8.2 s while the page filled, 35 from 11.8 s on. The window was the same throughout; the old rule took
    // the 16-line page. It is still starting while two looks at least 400 ms apart differ, and has started when they
    // coincide.
    [Test]
    public void AColdWindowIsStartingUntilTwoLooksApartCoincide()
    {
        static JsonObject Lines(int count) => new()
        {
            ["window"] = new JsonObject { ["title"] = "Iniciador de Epic Games", ["hwnd"] = 4242 },
            ["controls"] = new JsonArray(),
            ["text"] = new JsonObject { ["MC"] = new JsonArray([.. Enumerable.Range(0, count).Select(line => (JsonNode?)$"línea {line}")]) },
        };
        var state = new JsonObject();
        bool[] seen =
        [
            ComputerUseMission.StillStarting(state, Lines(2), TimeSpan.FromMilliseconds(4500)),
            ComputerUseMission.StillStarting(state, Lines(16), TimeSpan.FromMilliseconds(8200)),
            ComputerUseMission.StillStarting(state, Lines(35), TimeSpan.FromMilliseconds(11800)),
            ComputerUseMission.StillStarting(state, Lines(35), TimeSpan.FromMilliseconds(12000)),
            ComputerUseMission.StillStarting(state, Lines(35), TimeSpan.FromMilliseconds(12300)),
        ];
        Assert.That(seen, Is.EqualTo(new[] { true, true, true, true, false }),
            "the second 35-line look 200 ms after the first is not two looks apart yet; the one 500 ms after is");
    }

    [Test]
    public void AStillWindowThatShowsNothingIsTakenAtTheStartWait()
    {
        static JsonObject Blank() => new()
        {
            ["window"] = new JsonObject { ["title"] = "Launcher", ["hwnd"] = 7 },
            ["controls"] = new JsonArray(),
            ["surface"] = "ABCDEF",
        };
        var state = new JsonObject();
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.StillStarting(state, Blank(), TimeSpan.FromSeconds(1)), Is.True);
            Assert.That(ComputerUseMission.StillStarting(state, Blank(), TimeSpan.FromSeconds(5)), Is.True, "still a splash");
            Assert.That(ComputerUseMission.StillStarting(state, Blank(), ComputerUseMission.StartWait), Is.False);
        });
    }

    // Counter-case: a loaded window (a tree to act on) is taken as soon as two looks apart coincide, and a caret
    // blinking (only the image changes) does not keep it starting.
    [Test]
    public void ALoadedWindowWithABlinkingCaretHasStarted()
    {
        static JsonObject Loaded(string surface) => new()
        {
            ["window"] = new JsonObject { ["title"] = "Sin título: Bloc de notas", ["hwnd"] = 8 },
            ["controls"] = new JsonArray(
                new JsonObject { ["i"] = 0, ["kind"] = "MenuItem", ["name"] = "Archivo" },
                new JsonObject { ["i"] = 1, ["kind"] = "MenuItem", ["name"] = "Editar" }),
            ["surface"] = surface,
        };
        var state = new JsonObject();
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.StillStarting(state, Loaded("caret-on"), TimeSpan.FromMilliseconds(300)), Is.True);
            Assert.That(ComputerUseMission.StillStarting(state, Loaded("caret-off"), TimeSpan.FromMilliseconds(800)), Is.False);
        });
    }

    // Ronda 22 (r18 t2-c10 Word, t4-c06 Excel): a document window already drawn, whose status line and whole-tree count
    // keep moving a little between looks, has started; it never waits the whole StartWait.
    private static JsonObject DocumentWindow(int hwnd, int count, IEnumerable<string> names) => new()
    {
        ["window"] = new JsonObject { ["title"] = "Documento1 - Editor", ["hwnd"] = hwnd },
        ["controlCount"] = count,
        ["controls"] = new JsonArray([.. names.Select((name, at) => (JsonNode?)new JsonObject { ["i"] = at, ["kind"] = "Button", ["name"] = name })]),
    };

    [Test]
    public void ADrawnDocumentWindowWhoseTreeMovesALittleHasStarted()
    {
        string[] ribbon = [.. Enumerable.Range(0, 40).Select(at => $"Comando {at}")];
        string before = ComputerUseMission.OpeningTree(DocumentWindow(9, 95, [.. ribbon, "Página 1 de 1, 0 palabras"]));
        JsonObject now = DocumentWindow(9, 96, [.. ribbon, "Página 1 de 1, 1 palabra"]);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.OpeningTree(now), Is.Not.EqualTo(before), "an exact comparison never took it");
            Assert.That(ComputerUseMission.InterfaceUpAndSettled(now, before), Is.True);
            // Ronda 26: the one rule holds what the exact one (InterfaceUpAndStill, removed) took: the same tree twice,
            // whatever its values; and nothing under InterfaceUp controls to act on, nor a first look.
            Assert.That(ComputerUseMission.InterfaceUpAndSettled(now, ComputerUseMission.OpeningTree(now)), Is.True, "the same tree");
            Assert.That(ComputerUseMission.InterfaceUpAndSettled(now, previousTree: null), Is.False, "a first look");
            JsonObject small = DocumentWindow(9, 19, ribbon.Take(ComputerUseMission.InterfaceUp - 1));
            Assert.That(ComputerUseMission.InterfaceUpAndSettled(small, ComputerUseMission.OpeningTree(small)), Is.False, "too few");
        });
    }

    // Counter-cases: a tree still growing, another window, or controls mostly replaced are still starting.
    [Test]
    public void AGrowingOrReplacedTreeIsNotSettled()
    {
        string[] ribbon = [.. Enumerable.Range(0, 40).Select(at => $"Comando {at}")];
        string before = ComputerUseMission.OpeningTree(DocumentWindow(9, 95, ribbon));
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.InterfaceUpAndSettled(DocumentWindow(9, 152, ribbon), before), Is.False, "the tree still grows");
            // Review 1 of motor-listas-abiertas (finding 2): growth under 5 % is growth too.
            Assert.That(ComputerUseMission.InterfaceUpAndSettled(DocumentWindow(9, 97, ribbon), before), Is.False, "two more controls");
            Assert.That(ComputerUseMission.InterfaceUpAndSettled(DocumentWindow(9, 93, ribbon), before), Is.True, "two fewer: settled");
            Assert.That(ComputerUseMission.InterfaceUpAndSettled(DocumentWindow(10, 95, ribbon), before), Is.False, "another window");
            Assert.That(ComputerUseMission.InterfaceUpAndSettled(
                DocumentWindow(9, 95, [.. ribbon.Take(30), .. Enumerable.Range(0, 10).Select(at => $"Otro {at}")]), before), Is.False,
                "a quarter of the controls replaced");
            Assert.That(ComputerUseMission.InterfaceUpAndSettled(DocumentWindow(9, 20, ribbon.Take(10)),
                ComputerUseMission.OpeningTree(DocumentWindow(9, 20, ribbon.Take(10)))), Is.False, "fewer than InterfaceUp controls");
        });
    }

    // Ronda 22 (r18 t2-c10): OCR read «Documentol» one look and «Documento1» the next; the two looks coincide.
    [Test]
    public void OcrLettersReadOneForAnotherDoNotKeepAWindowStarting()
    {
        static JsonObject Written(params string[] lines) => new()
        {
            ["window"] = new JsonObject { ["title"] = "Documento1 - Editor", ["hwnd"] = 11 },
            ["controls"] = new JsonArray(
                new JsonObject { ["i"] = 0, ["kind"] = "MenuItem", ["name"] = "Archivo" },
                new JsonObject { ["i"] = 1, ["kind"] = "MenuItem", ["name"] = "Editar" }),
            ["text"] = new JsonObject { ["T"] = new JsonArray([.. lines.Select(line => (JsonNode?)line)]) },
        };
        var state = new JsonObject();
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.StillStarting(state, Written("Documentol - Editor", "Inicio"), TimeSpan.FromMilliseconds(300)), Is.True);
            Assert.That(ComputerUseMission.StillStarting(state, Written("Documento1 - Editor", "lnicio"), TimeSpan.FromMilliseconds(800)), Is.False);
        });
    }

    // Counter-case: a launcher showing 2 written lines and nothing to act on, the same twice, is still a splash; and a
    // window that writes other words changes its look.
    [Test]
    public void ALauncherShowingTwoLinesStillWaits()
    {
        static JsonObject Splash(params string[] lines) => new()
        {
            ["window"] = new JsonObject { ["title"] = "Launcher", ["hwnd"] = 12 },
            ["controls"] = new JsonArray(),
            ["text"] = new JsonObject { ["MC"] = new JsonArray([.. lines.Select(line => (JsonNode?)line)]) },
        };
        var state = new JsonObject();
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.StillStarting(state, Splash("Cargando", "Iniciando"), TimeSpan.FromMilliseconds(300)), Is.True);
            Assert.That(ComputerUseMission.StillStarting(state, Splash("Cargando", "lniciando"), TimeSpan.FromMilliseconds(800)), Is.True,
                "two lines and nothing to act on: a splash");
            Assert.That(ComputerUseMission.OcrSteady("Biblioteca"), Is.Not.EqualTo(ComputerUseMission.OcrSteady("Tienda")));
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

    // Live case n8 (2026-10-07): «andá a Imágenes» typed «imagenes» into the folder's search box and stopped there; the
    // window's title and its selected tab echoed the query and the mission said it had arrived.
    [Test]
    public void APlaceNamedOnlyByAnUnsubmittedQueryIsNotReached()
    {
        const string Check = "control:Imágenes:selected|title:Imágenes|page:Imágenes";
        JsonObject results = View("""
            {"window": {"title": "imagenes - Resultados de la búsqueda en Trabajo - Explorador de archivos", "process": "explorer",
                        "focused": {"kind": "Edit", "name": "Buscar en Trabajo", "value": "imagenes"}},
             "controls": [{"i": 0, "kind": "TabItem", "name": "imagenes - Resultados de la búsqueda en Trabajo", "state": "selected"},
                          {"i": 1, "kind": "Edit", "name": "Buscar en Trabajo", "state": "focused", "value": "imagenes"},
                          {"i": 2, "kind": "ListItem", "name": "Imagenes viejas", "state": ""}],
             "text": {}}
            """);
        JsonObject arrived = View("""
            {"window": {"title": "Imágenes - Explorador de archivos", "process": "explorer",
                        "focused": {"kind": "Pane", "name": "Imágenes", "value": null}},
             "controls": [{"i": 0, "kind": "TabItem", "name": "Imágenes", "state": "selected"}], "text": {}}
            """);
        JsonArray Steps(string into, params JsonObject[] after)
        {
            var steps = new JsonArray
            {
                new JsonObject { ["step"] = 1, ["operation"] = "input.visible.click", ["label"] = into, ["ok"] = true },
                new JsonObject { ["step"] = 2, ["operation"] = "input.text.type", ["text"] = "imagenes", ["into"] = into, ["ok"] = true },
            };
            foreach (JsonObject step in after)
            {
                steps.Add(step);
            }

            return steps;
        }

        JsonObject Enter() => new() { ["step"] = 3, ["operation"] = "input.key.press", ["key"] = "enter", ["ok"] = true };
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate(Check, results, Steps("Buscar en Trabajo"), out string? by), Is.False, by);
            Assert.That(ComputerUseSuccessCheck.Evaluate(Check, results, Steps("Buscar en Trabajo",
                new JsonObject { ["step"] = 3, ["operation"] = "input.key.press", ["key"] = "down", ["ok"] = true }), out _), Is.False,
                "a key that moves inside the suggestions submits nothing");
            Assert.That(ComputerUseSuccessCheck.Evaluate(Check, results, Steps("Buscar en Trabajo", Enter()), out _), Is.False,
                "a search entered lists what matches; it is not the place");
            Assert.That(ComputerUseSuccessCheck.Evaluate(Check, arrived, Steps("Buscar en Trabajo", Enter(),
                new JsonObject { ["step"] = 4, ["operation"] = "input.visible.click", ["label"] = "Imágenes", ["ok"] = true }), out _),
                Is.True, "a click from the results to the place by its name went there");
            Assert.That(ComputerUseSuccessCheck.Evaluate(Check, arrived, Steps("Barra de direcciones", Enter()), out _), Is.True,
                "the address typed and entered leads to the place it names");
            Assert.That(ComputerUseSuccessCheck.Evaluate(Check, arrived, Steps("Buscar en Trabajo", Enter()), out _), Is.True,
                "a search whose Enter opened the place is titled by the place, not by the query");
            Assert.That(ComputerUseSuccessCheck.Evaluate(Check, arrived, [], out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("title:imagenes&stepDone:input.key.press:enter", results,
                Steps("Buscar en Trabajo", Enter()), out _), Is.True, "a search submitted is titled by what it searched");
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

    // The Calculator's alternative «stepDone:input.text.type:=»: an expression typed with its equals sign is the
    // typing step's own text, which carries no key and no label.
    [Test]
    public void StepDoneArgumentAlsoNamesWhatWasTyped()
    {
        JsonArray typed = [new JsonObject { ["step"] = 1, ["operation"] = "input.text.type", ["text"] = "12*12=", ["ok"] = true }];
        JsonObject view = View("""{"window": {"title": "Calculadora", "focused": null}, "controls": [], "text": {}}""");
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.text.type:=", view, typed, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.text.type:13", view, typed, out _), Is.False);
        });
    }

    // «control:=informe»: the name whole. A longer name holding it («informe2») is another item; a name that says it
    // and then its kind («general (canal de texto)») is that item.
    [Test]
    public void AWholeNameControlAtomIgnoresLongerNamesThatHoldIt()
    {
        JsonObject view = View("""
            {"window": {"title": "Documentos", "process": "explorer"},
             "controls": [{"i": 0, "kind": "ListItem", "name": "informe2", "state": ""},
                          {"i": 1, "kind": "Hyperlink", "name": "general (canal de texto)", "state": "selected"}], "text": {}}
            """);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:informe", view, [], out _), Is.True, "contains, as before");
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:=informe", view, [], out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:=informe2", view, [], out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:=general", view, [], out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:=general:selected", view, [], out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:=canal", view, [], out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:=gene", view, [], out _), Is.False);
        });
    }

    // Live v11 2026-10-07 on Settings: «hacer clic en «bluetooth y dispositivos»» typed the name into the search box and
    // clicked the message «No hay resultados para «bluetooth y dispositivos»»; the containment of the click atom passed
    // it and the mission learned that click as the way there.
    [Test]
    public void AClickOnATextThatRepeatsTheTypedQueryIsNoClickOnThatName()
    {
        JsonObject view = View("""{"window": {"title": "Configuración", "process": "ApplicationFrameHost"}, "controls": [], "text": {}}""");
        JsonObject Typed(string text) => new()
        {
            ["operation"] = "input.text.type",
            ["text"] = text,
            ["into"] = "Cuadro de búsqueda, Buscar una opción",
            ["ok"] = true,
        };
        JsonObject Click(string name, string kind, bool? surfaceChanged = null, bool? broughtNew = null)
        {
            var click = new JsonObject
            {
                ["operation"] = "input.visible.click",
                ["label"] = name,
                ["name"] = name,
                ["kind"] = kind,
                ["ok"] = true,
            };
            if (surfaceChanged is { } changed)
            {
                click["surfaceChanged"] = changed;
            }

            if (broughtNew is { } brought)
            {
                click["broughtNew"] = brought;
            }

            return click;
        }

        // UI Automation's own receipt when its postread holds (DesktopUiaWorker Click-Result): the item gone, never
        // surfaceChanged. A result that navigates and the suggestion that only closed its list carry the same one.
        JsonObject Uia(string name, string kind, bool? broughtNew, bool toggled = false)
        {
            JsonObject click = Click(name, kind, surfaceChanged: false, broughtNew: broughtNew);
            click["absentOrDisabled"] = !toggled;
            click["toggled"] = toggled;
            click["cascadeStage"] = "uia";
            return click;
        }

        JsonArray echo = new() { Typed("«bluetooth y dispositivos»"), Click("No hay resultados para «bluetooth y dispositivos»", "Text") };
        JsonArray plain = new() { Typed("sistema"), Click("No hay resultados para «sistema»", "Text") };
        JsonArray navigatedMessage = new() { Typed("sistema"), Click("No hay resultados para «sistema»", "Text", surfaceChanged: true) };
        // Falsos éxitos v3 M2: a result that is or holds the query, whose look after it showed nothing the look before
        // lacked, only closed the list of suggestions; on receipts alone (no look yet) it is undecided and waits.
        JsonArray resultUnchanged = new() { Typed("sistema"), Uia("Sistema", "ListItem", broughtNew: false) };
        JsonArray longerUnchanged = new() { Typed("sonido"), Click("Configuración de sonido", "ListItem") };
        // Counter-cases: a result (an item) that holds the query, the result that is the query, the navigation item
        // clicked with nothing typed, and a message clicked when nothing was typed into a search. With UI
        // Automation's real receipt (surfaceChanged:false) a result that navigated is told by the look after it, and
        // a switch that repeats the query («bluetooth» typed, its toggle pressed) by its receipt. A query shorter than
        // three letters is in too many names to be echoed.
        JsonArray result = new() { Typed("sistema"), Click("Sistema", "ListItem") };
        JsonArray resultText = new() { Typed("sistema"), Click("Sistema", "Text", surfaceChanged: true) };
        JsonArray longerResult = new() { Typed("sonido"), Click("Configuración de sonido", "ListItem") };
        JsonArray uiaResult = new() { Typed("sistema"), Uia("Sistema", "ListItem", broughtNew: true) };
        JsonArray uiaLonger = new() { Typed("sonido"), Uia("Configuración de sonido", "ListItem", broughtNew: true) };
        JsonArray toggle = new() { Typed("bluetooth"), Uia("Bluetooth", "Button", broughtNew: false, toggled: true) };
        JsonArray shortQuery = new() { Typed("ok"), Uia("OK", "Button", broughtNew: false) };
        JsonArray item = new() { Click("Bluetooth y dispositivos", "ListItem") };
        JsonArray untyped = new() { Click("Sistema y seguridad", "Text") };
        JsonArray typedAfter = new() { Click("Sistema y seguridad", "Text"), Typed("sistema") };
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.visible.click:«bluetooth y dispositivos»", view, echo, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.visible.click:bluetooth y dispositivos", view, echo, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.visible.click:sistema", view, plain, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.visible.click:=sistema", view, plain, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.EvaluateReceipts("stepDone:input.visible.click:sistema", plain, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.visible.click:sistema", view, navigatedMessage, out _), Is.False,
                "a message that repeats the query is the echo whatever the receipt");
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.visible.click:sistema", view, resultUnchanged, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.EvaluateReceipts("stepDone:input.visible.click:sistema", resultUnchanged, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.EvaluateReceipts("stepDone:input.visible.click:sonido", longerUnchanged, out _), Is.False,
                "no look after it yet: undecided, the check waits for one");
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.visible.click:sistema", view, uiaResult, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.EvaluateReceipts("stepDone:input.visible.click:sistema", uiaResult, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.EvaluateReceipts("stepDone:input.visible.click:sonido", uiaLonger, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.EvaluateReceipts("stepDone:input.visible.click:bluetooth", toggle, out _), Is.True);
            // Estabilización R16: the toggle that repeats the query is no echo the mind is told of (HistoryForMind).
            Assert.That(ComputerUseMission.HistoryForMind(toggle, 0)[1]!["echo"], Is.Null);
            Assert.That(ComputerUseSuccessCheck.EvaluateReceipts("stepDone:input.visible.click:ok", shortQuery, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.visible.click:sistema", view, result, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.visible.click:sistema", view, resultText, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.visible.click:sonido", view, longerResult, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.visible.click:bluetooth y dispositivos", view, item, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.visible.click:sistema", view, untyped, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.visible.click:sistema", view, typedAfter, out _), Is.True);
        });
    }

    // «stepDone:input.visible.click:=red»: the clicked name holds the word whole. Measured on Paint: «red» inside
    // «Rectángulo redondeado» passed a click on that shape as the colour chosen. A bare «=» stays the equals key.
    [Test]
    public void AWholeNameClickAtomIgnoresAWordInsideALongerOne()
    {
        JsonObject view = View("""{"window": {"title": "Dibujo", "process": "dibujo"}, "controls": [], "text": {}}""");
        JsonArray shape = new() { new JsonObject { ["operation"] = "input.visible.click", ["label"] = "Rectángulo redondeado", ["ok"] = true } };
        JsonArray colour = new() { new JsonObject { ["operation"] = "input.visible.click", ["label"] = "red", ["name"] = "Red", ["ok"] = true } };
        JsonArray darker = new() { new JsonObject { ["operation"] = "input.visible.click", ["label"] = "Rojo oscuro", ["ok"] = true } };
        JsonArray equals = new() { new JsonObject { ["operation"] = "input.visible.click", ["label"] = "=", ["ok"] = true } };
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.visible.click:red", view, shape, out _), Is.True, "contains, as before");
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.visible.click:=red", view, shape, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.visible.click:=red", view, colour, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.visible.click:=rojo", view, darker, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.visible.click:=", view, equals, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:=red:on", View("""
                {"window": {"title": "Dibujo", "process": "dibujo"},
                 "controls": [{"i": 0, "kind": "Button", "name": "Rectángulo redondeado", "state": "on"}], "text": {}}
                """), [], out _), Is.False);
        });
    }

    [Test]
    public void TheMindReceivesIndicesNamesStatesZonesColoursRectanglesAndTextButNoIdentitiesOrHashes()
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
            // The rectangles are the mind's geometry (never printed in the model's prompt).
            Assert.That((int?)compact["window"]!["rect"]!["w"], Is.EqualTo(800));
            Assert.That((int?)compact["controls"]![0]!["rect"]!["w"], Is.EqualTo(60));
            Assert.That(compact["controls"]![2]!["rect"], Is.Null);
            Assert.That((string?)compact["text"]!["C"]![0], Is.EqualTo("12 × 7 ="));
            // How many controls the tree holds: a name beyond the listing is told from one the window lacks.
            Assert.That((int?)compact["controlCount"], Is.EqualTo(4));
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

    // GOAL v3 point 0, fix 2: how a click pressed (a pattern, a designated field, the pointer) reaches the journal and
    // the mind with the step. A designated field is no change of the screen (counter-case of a press that changed it).
    [TestCase("""{"name":"Buscar","kind":"Edit","method":"target","targeted":true,"focused":true}""", "target", false)]
    [TestCase("""{"name":"Servidor","selected":true,"method":"pointer"}""", "pointer", true)]
    [TestCase("""{"name":"Aceptar","absentOrDisabled":true,"method":"invoke"}""", "invoke", true)]
    public void TheClickMethodReachesTheMissionStep(string receipt, string method, bool changed)
    {
        var execution = new PendingMindPlanExecution(
            "haz clic",
            [new MindPlanStep("step_1", ComputerUseMission.OperationName, "clic", [], "literal", new JsonObject { ["goal"] = "clic" })])
        {
            ComputerUse = new JsonObject { ["goal"] = "clic", ["steps"] = new JsonArray() },
        };
        PreparedOperation click = PreparedOperation.Create("input.visible.click", new JsonObject { ["label"] = "x" });
        var response = new Baxy.Contracts.OperationResponse(
            Baxy.Contracts.ProtocolTypes.OperationResponse, click.InvocationId, click.MissionId, click.InvocationId,
            Baxy.Contracts.OperationStatuses.Completed, "{}", true, false,
            System.Text.Json.JsonDocument.Parse(receipt).RootElement, null);

        ComputerUseMission.RecordConfirmedStep(execution, click, response);

        JsonNode step = execution.ComputerUse!["steps"]![0]!;
        Assert.Multiple(() =>
        {
            Assert.That((string?)step["method"], Is.EqualTo(method));
            Assert.That((bool?)step["focused"], Is.EqualTo(method == "target" ? true : null),
                "a designation says it took the keyboard's focus");
            Assert.That((bool?)step["ok"], Is.True);
            Assert.That((bool?)step["changed"], Is.EqualTo(changed));
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

    private const string ExplorerSearchResults = """
        {"window": {"title": "imagenes - Resultados de la búsqueda en Trabajo - Explorador de archivos", "process": "explorer",
                    "focused": {"kind": "ListItem", "name": "Imágenes", "value": null}},
         "controls": [{"i": 0, "kind": "TabItem", "name": "imagenes - Resultados de la búsqueda en Trabajo", "state": "selected"},
                      {"i": 1, "kind": "Edit", "name": "Buscar en Trabajo", "state": "", "value": "imagenes"},
                      {"i": 2, "kind": "ListItem", "name": "Imágenes", "state": "selected focused", "zone": "C"}],
         "text": {}}
        """;

    private static JsonArray SearchedInTrabajo(params JsonObject[] after)
    {
        var steps = new JsonArray
        {
            new JsonObject { ["step"] = 1, ["operation"] = "input.visible.click", ["label"] = "Buscar en Trabajo", ["ok"] = true },
            new JsonObject { ["step"] = 2, ["operation"] = "input.text.type", ["text"] = "imagenes", ["into"] = "Buscar en Trabajo", ["ok"] = true },
            new JsonObject { ["step"] = 3, ["operation"] = "input.key.press", ["key"] = "enter", ["ok"] = true },
        };
        foreach (JsonObject step in after)
        {
            steps.Add(step);
        }

        return steps;
    }

    // Review 2026-10-07: the tab of the results, selected after «imagenes» was searched, is the query's echo for
    // «current» as it is for «selected».
    [Test]
    public void TheCurrentTabOfASearchStillEchoingIsNotThePlace()
    {
        JsonObject results = View(ExplorerSearchResults);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:imagenes:current", results, SearchedInTrabajo(), out string? by), Is.False, by);
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:imagenes:current", results, [], out _), Is.True,
                "nothing typed: the tab is what the window shows");
        });
    }

    // Review 2026-10-07: a click on the result named like the place only selected it; the window still shows the
    // results titled by the query.
    [Test]
    public void AClickThatOnlySelectedTheResultNamedLikeThePlaceIsNoArrival()
    {
        JsonObject results = View(ExplorerSearchResults);
        JsonObject Click(bool selected, string kind) => new()
        {
            ["step"] = 4,
            ["operation"] = "input.visible.click",
            ["label"] = "Imágenes",
            ["ok"] = true,
            ["selected"] = selected,
            ["kind"] = kind,
        };
        JsonObject arrived = View("""
            {"window": {"title": "Imágenes - Explorador de archivos", "process": "explorer",
                        "focused": {"kind": "Pane", "name": "Imágenes", "value": null}},
             "controls": [{"i": 0, "kind": "TabItem", "name": "Imágenes", "state": "selected"},
                          {"i": 1, "kind": "Edit", "name": "Buscar en Imágenes", "state": "", "value": ""}], "text": {}}
            """);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("title:imagenes", results, SearchedInTrabajo(Click(true, "ListItem")), out _), Is.False,
                "the receipt says the click only selected the item");
            Assert.That(ComputerUseSuccessCheck.Evaluate("title:imagenes", results, SearchedInTrabajo(Click(false, "ListItem")), out _), Is.False,
                "a content item clicked is selected, not opened");
            Assert.That(ComputerUseSuccessCheck.Evaluate("title:imagenes", arrived, SearchedInTrabajo(Click(false, "ListItem")), out _), Is.True,
                "once the place opened its search box no longer holds the query");
            Assert.That(ComputerUseSuccessCheck.Evaluate("title:imagenes", arrived, SearchedInTrabajo(Click(false, "Button")), out _), Is.True);
        });
    }

    // Safety review 2026-10-07: a click or a scroll, like a key or a text, never goes to a window that is not the named
    // application's (BAXY's own, another one that came up meanwhile).
    [TestCase("input.visible.click")]
    [TestCase("input.scroll")]
    [TestCase("input.key.press")]
    public void APointerStepOnAWindowThatIsNotTheApplicationIsRefused(string operation)
    {
        JsonObject other = View("""{"window": {"title": "BAXY", "process": "Baxy.App", "processId": 77, "hwnd": 9}}""");
        JsonObject requested = View("""{"window": {"title": "Calculadora", "process": "x", "processId": 55, "hwnd": 8, "requested": true}}""");
        JsonObject owned = View("""{"window": {"title": "Calculadora", "process": "x", "processId": 55, "hwnd": 8}}""");
        var state = new JsonObject { ["processId"] = 55 };
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.BindToMissionWindow(operation, new JsonObject(), other, state, "Calculadora"), Is.False);
            Assert.That(ComputerUseMission.BindToMissionWindow(operation, new JsonObject(), requested, new JsonObject(), "Calculadora"), Is.True);
            Assert.That(ComputerUseMission.BindToMissionWindow(operation, new JsonObject(), owned, state, "Calculadora"), Is.True);
            // Goal v3 destino, extended by the round-5 integration: with no application named no step goes to the
            // window in front (the person's), only to a window the mission opened or had resolved.
            Assert.That(ComputerUseMission.BindToMissionWindow(operation, new JsonObject(), other, new JsonObject(), null),
                Is.False, "no application named: no step goes to the person's window in front");
            Assert.That(ComputerUseMission.BindToMissionWindow(operation, new JsonObject(), owned, state, null), Is.True,
                "no application named: the window of the process the mission opened takes every step");
        });
    }

    // Goal v3 destino (r5a M5, v3-35 T3 typed «morado» into the person's window), extended by the round-5 integration
    // (t-menu-1 right-clicked there): a mission with no application resolved does nothing — no key, no text, no click,
    // no scroll — on a window it neither opened nor had resolved; the stop says so
    // (computer_use_no_application). Counter-cases: the window of the process it opened, one resolved for it, and the
    // person's window when the person named it as the destination («en esta ventana…»: frontWindow).
    [Test]
    public void WithNoApplicationResolvedNothingIsDoneInThePersonsWindow()
    {
        JsonObject persons = View("""{"window": {"title": "BAXY usuario simulado", "process": "pwsh", "processId": 40, "hwnd": 7}}""");
        JsonObject opened = View("""{"window": {"title": "Notas rápidas", "process": "x", "processId": 55, "hwnd": 8}}""");
        JsonObject resolved = View("""{"window": {"title": "Notas rápidas", "process": "x", "processId": 56, "hwnd": 9, "requested": true}}""");
        var state = new JsonObject { ["processId"] = 55 };
        var named = new JsonObject { ["frontWindow"] = true };
        Assert.Multiple(() =>
        {
            foreach (string operation in new[] { "input.text.type", "input.key.press", "input.visible.click", "input.scroll" })
            {
                var arguments = new JsonObject { ["text"] = "morado", ["key"] = "enter", ["index"] = 0 };
                Assert.That(ComputerUseMission.BindToMissionWindow(operation, arguments, persons, new JsonObject(), null), Is.False, operation);
                Assert.That(arguments["window"], Is.Null, operation);
                Assert.That(ComputerUseMission.NoApplicationActs(operation, null, new JsonObject(), persons["window"] as JsonObject), Is.True, operation);
                Assert.That(ComputerUseMission.BindToMissionWindow(operation, new JsonObject(), opened, state, null), Is.True, operation);
                Assert.That(ComputerUseMission.BindToMissionWindow(operation, new JsonObject(), resolved, new JsonObject(), null), Is.True, operation);
                Assert.That(ComputerUseMission.NoApplicationActs(operation, "Notas rápidas", new JsonObject(), persons["window"] as JsonObject), Is.False, operation);
                // The person named the window in front: it is the destination, bound like any mission window.
                var allowed = new JsonObject { ["index"] = 0 };
                Assert.That(ComputerUseMission.BindToMissionWindow(operation, allowed, persons, named.DeepClone().AsObject(), null), Is.True, operation);
                Assert.That((long?)allowed["window"], Is.EqualTo(7), operation);
            }

            // An app.open or a look is no act on the person's window.
            Assert.That(ComputerUseMission.NoApplicationActs("app.open", null, new JsonObject(), persons["window"] as JsonObject), Is.False);
        });
    }

    // Review 2026-10-07: a running packaged app found by its title showed the ApplicationFrameHost frame, and the
    // frame host's pid (shared by Settings, the Store, the Calculator) was adopted; a later look could take the Store's
    // frame and keys were allowed there. The shared host is never adopted; the provider names the hosted app instead,
    // so two frames of the same host keep apart.
    [Test]
    public void TheSharedFrameHostIsNeverTheMissionsProcess()
    {
        var byHost = new JsonObject();
        ComputerUseMission.AdoptWindow(byHost, "Configuración", View("""
            {"window": {"title": "Configuración", "process": "ApplicationFrameHost", "processId": 3, "hwnd": 30, "requested": true}}
            """));
        var byHosted = new JsonObject();
        ComputerUseMission.AdoptWindow(byHosted, "Configuración", View("""
            {"window": {"title": "Configuración", "process": "SystemSettings", "processId": 40, "hwnd": 30, "requested": true}}
            """));
        JsonObject store = View("""{"window": {"title": "Microsoft Store", "process": "WinStore.App", "processId": 41, "hwnd": 31}}""");
        JsonObject settings = View("""{"window": {"title": "Configuración", "process": "SystemSettings", "processId": 40, "hwnd": 30}}""");
        Assert.Multiple(() =>
        {
            Assert.That(byHost["processId"], Is.Null, "the frame host every packaged app shares is no app's process");
            Assert.That((int?)byHosted["processId"], Is.EqualTo(40));
            Assert.That(ComputerUseMission.BindToMissionWindow("input.key.press", new JsonObject(), store, byHosted, "Configuración"), Is.False,
                "another packaged app's frame of the same host gets no key");
            Assert.That(ComputerUseMission.BindToMissionWindow("input.key.press", new JsonObject(), settings, byHosted, "Configuración"), Is.True);
        });
    }

    // v3 point 0 review: a look no longer brings its window to the front, so a click or a scroll, like a key, names the
    // window of the view it was decided on (the provider fronts that window or does nothing). Before, a pointer step
    // carried no window because the look had left it in front. A step on no view names none.
    [Test]
    public void APointerStepIsBoundToTheWindowOfItsView()
    {
        JsonObject owned = View("""{"window": {"title": "Calculadora", "processId": 55, "hwnd": 8}}""");
        var click = new JsonObject { ["label"] = "Igual" };
        var scroll = new JsonObject { ["direction"] = "down", ["amount"] = 3 };
        var key = new JsonObject { ["key"] = "enter" };
        var unseen = new JsonObject { ["label"] = "Igual" };
        ComputerUseMission.BindToMissionWindow("input.visible.click", click, owned, new JsonObject { ["processId"] = 55 }, "Calculadora");
        ComputerUseMission.BindToMissionWindow("input.scroll", scroll, owned, new JsonObject { ["processId"] = 55 }, "Calculadora");
        ComputerUseMission.BindToMissionWindow("input.key.press", key, owned, new JsonObject { ["processId"] = 55 }, "Calculadora");
        ComputerUseMission.BindToMissionWindow("input.visible.click", unseen, null, new JsonObject(), null);
        Assert.Multiple(() =>
        {
            Assert.That((long?)click["window"], Is.EqualTo(8L));
            Assert.That((long?)scroll["window"], Is.EqualTo(8L));
            Assert.That((long?)key["window"], Is.EqualTo(8L));
            Assert.That(unseen["window"], Is.Null);
        });
    }

    // Goal v3 B3 (orders in closed menus): the mind's open, menu and double acts reach the click as «manner», bound to
    // the mission's window like any click, and the arguments the App sends satisfy the real catalog's schema.
    [Test]
    public void AClickInAnotherMannerIsBoundAndFitsTheCatalog()
    {
        JsonObject view = View("""
            {"window": {"title": "Windows PowerShell", "processId": 55, "hwnd": 8, "focused": null},
             "controls": [{"i": 0, "kind": "TabItem", "name": "Windows PowerShell", "state": "selected"},
                          {"i": 2, "kind": "SplitButton", "name": "Nueva pestaña", "state": "collapsed"}]}
            """);
        var state = new JsonObject { ["processId"] = 55 };
        var arrow = new JsonObject { ["label"] = "Nueva pestaña", ["index"] = 2, ["manner"] = "open" };
        var menu = new JsonObject { ["label"] = "Windows PowerShell", ["index"] = 0, ["manner"] = "menu" };
        var twice = new JsonObject { ["label"] = "Windows PowerShell", ["index"] = 0, ["manner"] = "double" };

        Assert.Multiple(() =>
        {
            foreach (JsonObject arguments in new[] { arrow, menu, twice })
            {
                Assert.That(ComputerUseMission.BindToMissionWindow("input.visible.click", arguments, view, state, "Terminal"), Is.True);
                Assert.That((long?)arguments["window"], Is.EqualTo(8L));
                Assert.That(MindPlanBoundary.ArgumentsSatisfyExactSchema("input.visible.click", arguments), Is.True);
            }

            Assert.That(MindPlanBoundary.ArgumentsSatisfyExactSchema(
                "input.visible.click", new JsonObject { ["label"] = "Nueva pestaña", ["index"] = 2, ["manner"] = "right" }), Is.False);
            // A click and the open of the same control are two acts: a failed click does not count against the open.
            var failed = new JsonArray(new JsonObject
            {
                ["operation"] = "input.visible.click",
                ["label"] = "Nueva pestaña",
                ["index"] = 2,
                ["ok"] = false,
            });
            Assert.That(ComputerUseSuccessCheck.RefusedClicks(failed, arrow), Is.EqualTo(0));
            Assert.That(ComputerUseSuccessCheck.RefusedClicks(failed, new JsonObject { ["label"] = "Nueva pestaña" }), Is.EqualTo(1));
        });
    }

    // Review of B3, finding 3: the history the mind reads carries the manner, so its repetition guard tells an opening
    // from a click and its history line never tells an opening as a press.
    [Test]
    public void TheMindsHistoryCarriesTheManner()
    {
        var steps = new JsonArray
        {
            new JsonObject
            {
                ["step"] = 1, ["operation"] = "input.visible.click", ["label"] = "Archivo", ["index"] = 4, ["manner"] = "menu",
                ["ok"] = false, ["error"] = "visible_control_no_context_menu",
            },
            new JsonObject { ["step"] = 2, ["operation"] = "input.visible.click", ["label"] = "Archivo", ["index"] = 4, ["ok"] = true },
        };
        JsonArray history = ComputerUseMission.HistoryForMind(steps, 0);
        Assert.Multiple(() =>
        {
            Assert.That((string?)history[0]!["manner"], Is.EqualTo("menu"));
            Assert.That(history[1]!["manner"], Is.Null);
        });
    }

    // Review of B3, finding 4 (false success): «hacer clic en Nueva pestaña» answered by opening its arrow is not done;
    // the opening is no click for stepDone and no act with an effect. A double click is a press.
    [Test]
    public void AnOpenedArrowOrMenuIsNoClickOnTheControl()
    {
        JsonObject view = View("""
            {"window": {"title": "Windows PowerShell", "processId": 55, "hwnd": 8, "focused": null},
             "controls": [{"i": 2, "kind": "SplitButton", "name": "Nueva pestaña", "state": "expanded"}]}
            """);
        JsonArray Steps(string? manner)
        {
            var step = new JsonObject
            {
                ["step"] = 1,
                ["operation"] = "input.visible.click",
                ["label"] = "Nueva pestaña",
                ["index"] = 2,
                ["ok"] = true,
                ["surfaceChanged"] = true,
            };
            if (manner is not null)
            {
                step["manner"] = manner;
            }

            return new JsonArray(step);
        }

        const string check = "stepDone:input.visible.click:Nueva pestaña";
        Assert.Multiple(() =>
        {
            foreach (string manner in new[] { "open", "menu" })
            {
                Assert.That(ComputerUseSuccessCheck.Evaluate(check, view, Steps(manner), out _), Is.False, manner);
                // Estabilización R16: no act with an effect is the mind's reading (cu_evidence.only_opened) of the
                // «manner» the App tells it (HistoryForMind), and the App's own OnlyOpened.
                Assert.That(ComputerUseSuccessCheck.OnlyOpened(Steps(manner)[0]!.AsObject()), Is.True, manner);
                Assert.That((string?)ComputerUseMission.HistoryForMind(Steps(manner), 0)[0]!["manner"], Is.EqualTo(manner), manner);
            }

            Assert.That(ComputerUseSuccessCheck.Evaluate(check, view, Steps(null), out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, view, Steps("double"), out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.OnlyOpened(Steps(null)[0]!.AsObject()), Is.False);
        });
    }

    // Goal v3, point 0, fix 1: a text names the field of its view it goes to (the provider writes it there without
    // the keyboard or the front): the focused field, or the one the last click aimed at when the window in the
    // background reports no focus.
    [Test]
    public void AMissionTextNamesTheFieldOfItsView()
    {
        JsonObject focused = View("""
            {"window": {"title": "Ajustes", "processId": 55, "hwnd": 8, "focused": {"kind": "Edit", "name": "Buscar", "i": 2}},
             "controls": [{"i": 0, "kind": "Button", "name": "Inicio"}, {"i": 2, "kind": "Edit", "name": "Buscar", "state": "focused"}]}
            """);
        JsonObject unfocused = View("""
            {"window": {"title": "Ajustes", "processId": 55, "hwnd": 8, "focused": null},
             "controls": [{"i": 0, "kind": "Button", "name": "Buscar"}, {"i": 4, "kind": "Edit", "name": "Buscar", "state": ""}]}
            """);
        var clicked = new JsonArray(new JsonObject { ["operation"] = "input.visible.click", ["label"] = "Buscar", ["ok"] = true });
        var byFocus = new JsonObject { ["text"] = "mouse" };
        var byClick = new JsonObject { ["text"] = "mouse" };
        var carried = new JsonObject { ["text"] = "mouse", ["index"] = 9 };
        var key = new JsonObject { ["key"] = "enter" };
        var state = new JsonObject { ["processId"] = 55 };

        ComputerUseMission.BindToMissionWindow("input.text.type", byFocus, focused, state, "Configuración");
        ComputerUseMission.BindToMissionWindow("input.text.type", byClick, unfocused, state, "Configuración", clicked);
        ComputerUseMission.BindToMissionWindow("input.text.type", carried, unfocused, state, "Configuración");
        ComputerUseMission.BindToMissionWindow("input.key.press", key, focused, state, "Configuración", clicked);
        Assert.Multiple(() =>
        {
            Assert.That((int?)byFocus["index"], Is.EqualTo(2));
            Assert.That((long?)byFocus["window"], Is.EqualTo(8L));
            Assert.That((int?)byClick["index"], Is.EqualTo(4), "the clicked field, never the same-named button");
            Assert.That(carried["index"], Is.Null, "an index carried from another view never names a field of this one");
            Assert.That(key["index"], Is.Null, "a key goes where the window's focus is");
            Assert.That(MindPlanBoundary.ArgumentsSatisfyExactSchema("input.text.type", byClick), Is.True);
        });
    }

    // Contracase: nothing that takes no text (a button, a read-only or password field) is named as the text's field, and a click
    // whose label names two fields names none.
    [Test]
    public void ATextNamesNoFieldThatDoesNotTakeText()
    {
        JsonObject view = View("""
            {"window": {"title": "Formulario", "hwnd": 8, "focused": {"kind": "Button", "name": "Enviar", "i": 0}},
             "controls": [{"i": 0, "kind": "Button", "name": "Enviar", "state": "focused"},
                          {"i": 1, "kind": "Edit", "name": "Total", "state": "readonly"},
                          {"i": 2, "kind": "Edit", "name": "Nombre", "state": ""},
                          {"i": 3, "kind": "Edit", "name": "Nombre", "state": ""},
                          {"i": 4, "kind": "Edit", "name": "Clave", "state": "password"}]}
            """);
        static JsonArray Clicked(string label) =>
            new(new JsonObject { ["operation"] = "input.visible.click", ["label"] = label, ["ok"] = true });
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.TextField(view, null), Is.Null);
            Assert.That(ComputerUseMission.TextField(view, Clicked("Total")), Is.Null);
            Assert.That(ComputerUseMission.TextField(view, Clicked("Nombre")), Is.Null);
            Assert.That(ComputerUseMission.TextField(view, Clicked("Enviar")), Is.Null);
            Assert.That(ComputerUseMission.TextField(view, Clicked("Clave")), Is.Null, "never a password field");
        });
    }

    // The type of a list or tree item the provider reports (a folder, a shortcut) reaches the mind.
    [Test]
    public void TheItemTypeOfAControlReachesTheMind()
    {
        JsonObject compact = ComputerUseMission.CompactForTheMind(View("""
            {"window": {"title": "Trabajo"},
             "controls": [{"i": 0, "kind": "ListItem", "name": "Imágenes", "state": "", "itemType": "Carpeta de archivos"},
                          {"i": 1, "kind": "ListItem", "name": "notas.txt", "state": "", "itemType": ""},
                          {"i": 2, "kind": "Button", "name": "Atrás", "state": ""}]}
            """));
        JsonArray controls = compact["controls"]!.AsArray();
        Assert.Multiple(() =>
        {
            Assert.That((string?)controls[0]!["itemType"], Is.EqualTo("Carpeta de archivos"));
            Assert.That(controls[1]!.AsObject().ContainsKey("itemType"), Is.False);
            Assert.That(controls[2]!.AsObject().ContainsKey("itemType"), Is.False);
        });
    }

    [Test]
    public void ASearchTypedIntoABoxDrawnWithoutATreeIsProvedByItsResultsNeverByTheBoxAlone()
    {
        // Measured on Steam's library: the box holds «Cuphead» whether the library has it or not.
        const string check = "stepDone:input.text.type&stepDone:input.key.press:enter&text:Cuphead";
        var steps = new JsonArray
        {
            new JsonObject { ["step"] = 1, ["operation"] = "input.key.press", ["ok"] = true, ["key"] = "ctrl_f" },
            new JsonObject { ["step"] = 2, ["operation"] = "input.text.type", ["ok"] = true, ["text"] = "Cuphead" },
            new JsonObject { ["step"] = 3, ["operation"] = "input.key.press", ["ok"] = true, ["key"] = "enter" },
        };
        JsonObject onlyTheBox = View("""
            {"window": {"title": "Steam", "process": "steamwebhelper", "focused": null},
             "controls": [{"i": 0, "kind": "Pane", "name": "Chrome Legacy Window"}],
             "text": {"TL": ["Juegos y Software", "Q Cuphead", "FAVORITOS (0)"]}}
            """);
        JsonObject withResult = View("""
            {"window": {"title": "Steam", "process": "steamwebhelper", "focused": null},
             "controls": [{"i": 0, "kind": "Pane", "name": "Chrome Legacy Window"}],
             "text": {"TL": ["Juegos y Software", "Q Cuphead", "FAVORITOS (1)"], "L": ["Cuphead"]}}
            """);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, onlyTheBox, steps, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, withResult, steps, out _), Is.True);
            // Text that was never typed reads the screen as before.
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.key.press:enter&text:FAVORITOS", onlyTheBox, steps, out _), Is.True);
        });
    }

    // Spotify's web player as read at x7 (2026-10-07): the search box focused, with its recent searches, after the
    // click on «Buscar»; the frame's read-only «Address and search bar» never counts. Ronda 24b: by default the steps 1
    // and 2 were decided with the keyboard on the «Buscar» button (focusBeforeStep), so the act moved it.
    private static JsonObject SearchView(string focusedKind, string focusedName, string? focusAtStart, string state = "expanded focused",
        bool focusMoved = true)
    {
        JsonObject view = View("""
            {"window": {"title": "Spotify Premium", "process": "Spotify", "focused": null},
             "controls": [
               {"i": 0, "kind": "Edit", "name": "Address and search bar", "state": "readonly", "value": "xpui.app.spotify.com/index.html"},
               {"i": 1, "kind": "Button", "name": "Buscar", "state": ""},
               {"i": 2, "kind": "ComboBox", "name": "¿Qué quieres reproducir?", "state": ""},
               {"i": 3, "kind": "Hyperlink", "name": "Viva Latino", "state": "readonly"}
             ]}
            """);
        view["window"]!["focused"] = new JsonObject { ["kind"] = focusedKind, ["name"] = focusedName, ["value"] = "" };
        foreach (JsonObject control in ((JsonArray)view["controls"]!).OfType<JsonObject>())
        {
            if ((string?)control["name"] == focusedName)
            {
                control["state"] = state;
            }
        }

        if (focusAtStart is not null)
        {
            view["focusAtStart"] = focusAtStart;
        }

        if (focusMoved)
        {
            view["focusBeforeStep"] = new JsonObject { ["1"] = "Button|buscar", ["2"] = "Button|buscar" };
        }

        return view;
    }

    // Ronda 24b: the focus each step was decided on (state focusBeforeStep, step number → FocusSignature).
    private static JsonObject FocusBefore(JsonObject view, params string[] focusPerStep)
    {
        var before = new JsonObject();
        for (int index = 0; index < focusPerStep.Length; index++)
        {
            before[(index + 1).ToString(System.Globalization.CultureInfo.InvariantCulture)] = focusPerStep[index];
        }

        view["focusBeforeStep"] = before;
        return view;
    }

    [Test]
    public void TheSearchIsReachedWhenThisMissionPutsTheKeyboardInItsField()
    {
        const string check = "control:search:current|title:search|control:buscar:current|title:buscar|focus:search";
        var clicked = new JsonArray
        {
            new JsonObject { ["step"] = 1, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "Buscar" },
        };
        var findKey = new JsonArray
        {
            new JsonObject { ["step"] = 1, ["operation"] = "input.visible.click", ["ok"] = false, ["label"] = "Address and search bar" },
            new JsonObject { ["step"] = 2, ["operation"] = "input.key.press", ["ok"] = true, ["key"] = "ctrl_f" },
        };
        JsonObject arrived = SearchView("ComboBox", "¿Qué quieres reproducir?", "Document|spotify");
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, arrived, clicked, out string? by), Is.True);
            Assert.That(by, Is.EqualTo("focus:search"));
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, arrived, findKey, out _), Is.True);
        });
    }

    // v3 point 0 review, ronda 24b: the application looked at behind the person's window still tells where its keyboard
    // is (the worker reads HasKeyboardFocus behind; x7 journal: Group → Button → ComboBox). The start read behind is
    // the guard, never an unknown that lets any act pass: the arrival rests on the act that moved the keyboard into
    // the search field, and another act proves nothing.
    [Test]
    public void AStartReadBehindThePersonsWindowLeavesTheSearchToTheActThatMovedTheKeyboard()
    {
        const string check = "focus:search";
        var clicked = new JsonArray
        {
            new JsonObject { ["step"] = 1, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "Buscar" },
        };
        var otherClick = new JsonArray
        {
            new JsonObject { ["step"] = 1, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "Inicio" },
        };
        JsonObject view = SearchView("ComboBox", "¿Qué quieres reproducir?", "Group|spotify - reproductor web");
        view["window"]!["foreground"] = false;
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.LookedBehind(view), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, view, clicked, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, view, otherClick, out _), Is.False);
        });
    }

    // Ronda 24b, banco r23 x7 (falso éxito «Listo, estoy en «search»»): Spotify read behind the person's window; a
    // click on «Buscar» brought the keyboard to the button, ctrl_f moved it into the box (the real arrival), and after
    // Escape and a scroll a last click on «Buscar» found the box focused before and after. That click brought nothing:
    // only the act that moved the keyboard into the field arrives, whatever the label it pressed says.
    [Test]
    public void X7AClickOnBuscarWithTheBoxFocusedBeforeAndAfterIsNoArrival()
    {
        const string check = "control:search:current|title:search|control:buscar:current|title:buscar|focus:search";
        JsonObject view = SearchView("ComboBox", "¿Qué quieres reproducir?", "Group|spotify - reproductor web: musica para todos");
        view["window"]!["foreground"] = false;
        string box = ComputerUseSuccessCheck.FocusSignature(view);
        FocusBefore(view, "Group|spotify - reproductor web: musica para todos", "Button|buscar", box, box, box);
        var steps = new JsonArray
        {
            new JsonObject { ["step"] = 1, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "Buscar" },
            new JsonObject { ["step"] = 2, ["operation"] = "input.key.press", ["ok"] = true, ["key"] = "ctrl_f" },
            new JsonObject { ["step"] = 3, ["operation"] = "input.key.press", ["ok"] = true, ["key"] = "escape" },
            new JsonObject { ["step"] = 4, ["operation"] = "input.scroll", ["ok"] = true, ["direction"] = "down" },
            new JsonObject { ["step"] = 5, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "Buscar" },
        };
        var throughFindKey = new JsonArray { steps[0]!.DeepClone(), steps[1]!.DeepClone() };
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, view, steps, out _), Is.False);
            // The ctrl_f of step 2 moved the keyboard from the button into the box behind the person's window: arrived.
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, view, throughFindKey, out string? by), Is.True);
            Assert.That(by, Is.EqualTo("focus:search"));
        });
    }

    // Ronda 24b contracases: an application whose search is only a box (a quick switcher, the ctrl_f of a library):
    // the click or the shortcut moves the keyboard from a button or a group into the box, read in front or behind,
    // and focus:search holds on that step. A box that had the keyboard since before the mission (the person was
    // typing there) is no arrival, and neither is a step decided with the keyboard already in it.
    [Test]
    public void TheSearchIsTheActThatMovedTheKeyboardIntoTheBoxInFrontOrBehind()
    {
        const string check = "focus:search";
        var clicked = new JsonArray
        {
            new JsonObject { ["step"] = 1, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "Buscar" },
        };
        var findKey = new JsonArray
        {
            new JsonObject { ["step"] = 1, ["operation"] = "input.key.press", ["ok"] = true, ["key"] = "ctrl_f" },
        };
        JsonObject Box(bool inFront, string atStart, string before)
        {
            JsonObject view = SearchView("Edit", "Buscar en la biblioteca", atStart, "focused", focusMoved: false);
            view["window"]!["foreground"] = inFront;
            return FocusBefore(view, before);
        }

        Assert.Multiple(() =>
        {
            foreach (bool inFront in new[] { true, false })
            {
                Assert.That(ComputerUseSuccessCheck.Evaluate(check, Box(inFront, "Group|biblioteca", "Button|buscar"), clicked, out _), Is.True);
                Assert.That(ComputerUseSuccessCheck.Evaluate(check, Box(inFront, "Group|biblioteca", "Group|biblioteca"), findKey, out _), Is.True);
                // The person was typing in the box before the mission: start and the step's look both had it there.
                Assert.That(ComputerUseSuccessCheck.Evaluate(check, Box(inFront, "Edit|buscar en la biblioteca", "Edit|buscar en la biblioteca"), findKey, out _), Is.False);
                // The step was decided with the keyboard already in the box: it moved nothing, whatever the start was.
                Assert.That(ComputerUseSuccessCheck.Evaluate(check, Box(inFront, "Group|biblioteca", "Edit|buscar en la biblioteca"), clicked, out _), Is.False);
                Assert.That(ComputerUseSuccessCheck.Evaluate(check, Box(inFront, "Group|biblioteca", "Edit|buscar en la biblioteca"), findKey, out _), Is.False);
            }

            // Where the keyboard was before the step is not known: no proof.
            JsonObject unknown = SearchView("Edit", "Buscar en la biblioteca", "Group|biblioteca", "focused", focusMoved: false);
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, unknown, clicked, out _), Is.False);
        });
    }

    [Test]
    public void ASearchBoxShownOrFocusedWithoutThisMissionOrHoldingTypedTextIsNoArrival()
    {
        const string check = "focus:search";
        var clicked = new JsonArray
        {
            new JsonObject { ["step"] = 1, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "Buscar" },
        };
        var typed = new JsonArray
        {
            new JsonObject { ["step"] = 1, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "Buscar" },
            new JsonObject { ["step"] = 2, ["operation"] = "input.text.type", ["ok"] = true, ["text"] = "search" },
        };
        var otherClick = new JsonArray
        {
            new JsonObject { ["step"] = 1, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "Inicio" },
        };
        var scrolled = new JsonArray
        {
            new JsonObject { ["step"] = 1, ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "Buscar" },
            new JsonObject { ["step"] = 2, ["operation"] = "input.scroll", ["ok"] = true, ["direction"] = "down" },
        };
        Assert.Multiple(() =>
        {
            // Present on every page, never focused: no arrival.
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, SearchView("Document", "Spotify", "Document|spotify", "collapsed"), clicked, out _), Is.False);
            // It had the keyboard at the first look: not brought there by this mission.
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, SearchView("ComboBox", "¿Qué quieres reproducir?", "ComboBox|¿que quieres reproducir?"), clicked, out _), Is.False);
            // Review 2 of r24b (B2): no first look known is no start guard, and the proof rests on the step alone. The
            // click decided with the keyboard on «Buscar» moved it into the box: arrived. Contracases: decided with the
            // keyboard already in the box, or with where it was unknown, the click proves nothing.
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, SearchView("ComboBox", "¿Qué quieres reproducir?", null), clicked, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, FocusBefore(SearchView("ComboBox", "¿Qué quieres reproducir?", null, focusMoved: false),
                "ComboBox|¿que quieres reproducir?"), clicked, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, SearchView("ComboBox", "¿Qué quieres reproducir?", null, focusMoved: false), clicked, out _), Is.False);
            // Text typed into it: an echo, never arriving.
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, SearchView("ComboBox", "¿Qué quieres reproducir?", "Document|spotify"), typed, out _), Is.False);
            // The last verified act was not toward the search.
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, SearchView("ComboBox", "¿Qué quieres reproducir?", "Document|spotify"), otherClick, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, SearchView("ComboBox", "¿Qué quieres reproducir?", "Document|spotify"), scrolled, out _), Is.False);
            // The read-only address field is never the search.
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, SearchView("Edit", "Address and search bar", "Document|spotify", "readonly focused"), clicked, out _), Is.False);
        });
    }

    [Test]
    public void AClickRefusedTwiceInTheSubgoalIsCountedWhateverCameBetween()
    {
        var steps = new JsonArray
        {
            new JsonObject { ["operation"] = "input.visible.click", ["ok"] = false, ["label"] = "Address and search bar", ["index"] = 0 },
            new JsonObject { ["operation"] = "input.visible.click", ["ok"] = true, ["label"] = "Buscar" },
            new JsonObject { ["operation"] = "input.visible.click", ["ok"] = false, ["label"] = "address and search bar", ["index"] = 2 },
        };
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.RefusedClicks(steps, new JsonObject { ["label"] = "Address and search bar" }), Is.EqualTo(2));
            Assert.That(ComputerUseSuccessCheck.RefusedClicks(steps, new JsonObject { ["label"] = "Buscar" }), Is.EqualTo(0));
        });
    }

    // v3 point 0 review: a look behind the person's window has no keyboard focus to read; it is told from a look in
    // front (the side list of y9). Contracase: a window in front without a tree.
    [Test]
    public void AWindowLookedAtBehindThePersonsIsToldFromOneInFront()
    {
        JsonObject behind = View("{\"window\": {\"title\": \"Ajustes\", \"foreground\": false, \"focused\": null}, \"controls\": []}");
        JsonObject inFront = View("{\"window\": {\"title\": \"Ajustes\", \"foreground\": true, \"focused\": null}, \"controls\": []}");
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.LookedBehind(behind), Is.True);
            Assert.That(ComputerUseSuccessCheck.LookedBehind(inFront), Is.False);
        });
    }

    // ------------------------------------------------------- falsos éxitos v3 M1-M3 (cu-v3 r3a)

    private static JsonObject TypedInto(string text, string into) =>
        new() { ["operation"] = "input.text.type", ["text"] = text, ["into"] = into, ["ok"] = true, ["changed"] = true };

    private static JsonObject PressedControl(string label, string kind, bool surfaceChanged, bool absentOrDisabled = false) => new()
    {
        ["operation"] = "input.visible.click",
        ["label"] = label,
        ["name"] = label,
        ["kind"] = kind,
        ["ok"] = true,
        ["surfaceChanged"] = surfaceChanged,
        ["absentOrDisabled"] = absentOrDisabled,
    };

    // Review of cu-v3-documento-nuevo (finding 7), twin of t4-c06 «bro abre excel y crea un blank workbook»: the opening
    // that made the new document asked for (its receipt says newDocument) is the act of «crear un blank workbook», and
    // «Libro1» it shows is its effect; an opening that only brought the application up acts on nothing.
    [Test]
    public void AnOpeningThatMadeTheNewDocumentIsTheActOfCreatingIt()
    {
        JsonObject made = new() { ["operation"] = "app.open", ["ok"] = true, ["newDocument"] = true };
        JsonObject reused = new() { ["operation"] = "app.open", ["ok"] = true };
        JsonObject view = new() { ["window"] = new JsonObject { ["title"] = "Libro1 - Excel" } };
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.MayHaveActed(made), Is.True);
            Assert.That(ComputerUseMission.MayHaveActed(reused), Is.False);
            // Estabilización R16: the App no longer judges the done again (EvidenceRefusal and its ActedWithEffect went);
            // the opening that made the document is the mind's to cite (cu_documents), and the one that only brought the
            // application up proves nothing in the mind's judge (tests/test_cu_estab_r16_juez_unico.py).
            Assert.That(ComputerUseMission.MadeNewDocument(made), Is.True);
            Assert.That(ComputerUseMission.MadeNewDocument(reused), Is.False);
            Assert.That((string?)view["window"]!["title"], Is.EqualTo("Libro1 - Excel"));
        });
    }

    // Twin of v3-11 (OneNote, «crea una pagina nueva»): the clause reader left a label with a quote inside; the model
    // typed it into «Búsqueda de Microsoft» and pressed its own suggestion, whose receipt saw no surface change and the
    // control gone (the list of suggestions closed). No click on that name, no effect.
    [Test]
    public void AClickOnTheSuggestionOfTheMissionsOwnQueryIsNoReceipt()
    {
        const string Label = "pagina» para crear una nueva pagina";
        JsonArray steps = new()
        {
            TypedInto(Label, "Búsqueda de Microsoft"),
            PressedControl("\"" + Label + "\"", "MenuItem", surfaceChanged: false, absentOrDisabled: true),
        };
        // Counter-cases: a result that navigates (Cuphead in a store's results), «Aceptar» gone with nothing typed.
        JsonArray navigated = new() { TypedInto("Cuphead", "Buscar en la tienda"), PressedControl("Cuphead", "ListItem", surfaceChanged: true) };
        JsonArray accepted = new() { PressedControl("Aceptar", "Button", surfaceChanged: false, absentOrDisabled: true) };
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.EvaluateReceipts("stepDone:input.visible.click:" + Label, steps, out _), Is.False);
            // The look after the suggestion showed nothing new (v3-11's «después»: the same tabs and tree, the box back
            // to «Buscar»): neither the query typed into the search nor its own suggestion is an act.
            JsonArray looked = (JsonArray)steps.DeepClone();
            looked[1]!["broughtNew"] = false;
            // Estabilización R16: what the mind's acted_with_effect reads of them (HistoryForMind): the text typed into a
            // box that only searches («query») and the click that echoes it («echo») are no act there.
            JsonArray told = ComputerUseMission.HistoryForMind(looked, 0);
            Assert.That((bool?)told[0]!["query"], Is.True);
            Assert.That((bool?)told[1]!["echo"], Is.True);
            Assert.That(ComputerUseSuccessCheck.EvaluateReceipts("stepDone:input.visible.click:" + Label, looked, out _), Is.False);
            Assert.That(ComputerUseMission.HistoryForMind([steps[1]!.DeepClone()], 0)[0]!["echo"], Is.Null,
                "with nothing typed before it, a control gone is no echo");
            Assert.That(ComputerUseSuccessCheck.EvaluateReceipts("stepDone:input.visible.click:cuphead", navigated, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.EvaluateReceipts("stepDone:input.visible.click:aceptar", accepted, out _), Is.True);
        });
    }

    // Twin of v3-58 (turn 1, «anda a la configuracion» in Edge): «configuracion» typed into a help search and the result
    // «Herramienta de configuración de webcam – Link» pressed; the tab it opened passed control:configuracion:current.
    // A match that only holds the name inside a longer one keeps the echo; the place itself, its whole name, does not.
    [Test]
    public void ATabOpenedFromAMatchThatOnlyHoldsTheNameIsNoArrival()
    {
        JsonObject webcam = View("""
            {"window": {"title": "Herramienta de configuración de webcam - Microsoft Edge", "process": "msedge"},
             "controls": [{"kind": "TabItem", "name": "Herramienta de configuración de webcam - Descargar", "state": "selected current"}]}
            """);
        JsonObject settings = View("""
            {"window": {"title": "Configuración - Microsoft Edge", "process": "msedge"},
             "controls": [{"kind": "TabItem", "name": "Configuración", "state": "selected current"}]}
            """);
        JsonArray match = new()
        {
            TypedInto("configuracion", "Buscar en la ayuda"),
            PressedControl("Herramienta de configuración de webcam – Link", "ListItem", surfaceChanged: true),
            new JsonObject { ["operation"] = "input.key.press", ["key"] = "enter", ["ok"] = true },
        };
        JsonArray whole = new() { TypedInto("configuracion", "Buscar en la ayuda"), PressedControl("Configuración", "Hyperlink", surfaceChanged: true) };
        JsonArray address = new()
        {
            TypedInto("edge://settings", "Barra de direcciones y de búsqueda"),
            new JsonObject { ["operation"] = "input.key.press", ["key"] = "enter", ["ok"] = true },
        };
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:configuracion:current", webcam, match, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("title:configuracion", webcam, match, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.QueryEchoNames("configuracion", webcam, match, false), Is.True);
            Assert.That(ComputerUseSuccessCheck.QueryEchoNames("configuracion", settings, whole, false), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("title:configuracion", settings, whole, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.QueryEchoNames("configuracion", settings, address, false), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:configuracion:current", settings, address, out _), Is.True);
        });
    }

    // Ronda 23 (v2-v3-58, r21 13:08–13:47): turn 1 typed «configuracion» into Edge's new-tab web search and left Bing's
    // results «configuración - Búsqueda»; turn 2 («busca cookies ahi en la configuracion») began with no step and its
    // first look passed control:configuracion:current on that selected tab. The view of the journal (seq 2436/2438).
    private const string SettingsPlaceCheck =
        "control:configuracion:current|title:configuracion|page:configuracion|control:ajustes:current|title:ajustes|page:ajustes"
        + "|control:settings:current|title:settings|page:settings|mark:configuracion|mark:ajustes|mark:settings";

    private static JsonObject SearchEchoView(string address) => View($$$"""
        {"window": {"title": "configuración - Búsqueda - Personal: Microsoft​ Edge", "process": "msedge",
                    "focused": {"kind": "Document", "name": "configuración - Búsqueda", "state": "readonly focused", "value": "{{{address}}}"}},
         "controls": [
           {"kind": "Button", "name": "Cerrar"},
           {"kind": "TabItem", "name": "configuración - Búsqueda", "state": "selected"},
           {"kind": "Button", "name": "Cerrar pestaña"},
           {"kind": "Edit", "name": "Barra de direcciones y búsqueda", "state": "collapsed", "value": "{{{address}}}"},
           {"kind": "Document", "name": "configuración - Búsqueda", "state": "readonly focused", "value": "{{{address}}}"},
           {"kind": "Hyperlink", "name": "Volver a la búsqueda de Bing"},
           {"kind": "Button", "name": "Buscar"},
           {"kind": "Edit", "name": "Escribe tu búsqueda aquí; irán apareciendo sugerencias de búsqueda", "value": "configuración"}]}
        """);

    [Test]
    public void ASearchResultsPageNamingThePlaceAsTheQueryAnEarlierTurnTypedIsNoArrival()
    {
        JsonObject echo = SearchEchoView("https://www.bing.com/search?q=configuración&form=QBLH");
        JsonObject encoded = SearchEchoView("https://www.bing.com/search?q=configuraci%C3%B3n&form=QBLH");
        // Contracase: the real settings page (edge://settings is no search address, no field holds the name).
        JsonObject settings = View("""
            {"window": {"title": "Configuración - Personal: Microsoft​ Edge", "process": "msedge"},
             "controls": [{"kind": "TabItem", "name": "Configuración", "state": "selected"},
                          {"kind": "Edit", "name": "Barra de direcciones y búsqueda", "value": "edge://settings/profiles"},
                          {"kind": "Edit", "name": "Buscar configuración", "value": ""}]}
            """);
        IReadOnlyList<TypedEarlier> earlier = [new("configuracion", "Escribe el término de búsqueda", "msedge")];
        Assert.Multiple(() =>
        {
            // No step: the earlier turn's typing in memory says the results page is that search's echo.
            Assert.That(ComputerUseSuccessCheck.Evaluate(SettingsPlaceCheck, echo, [], out _, typedBefore: earlier), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate(SettingsPlaceCheck, encoded, [], out _, typedBefore: earlier), Is.False);
            Assert.That(ComputerUseSuccessCheck.QueryEchoNames("configuracion", encoded, [], false, earlier), Is.True);
            // Revisión 3: with nothing BAXY typed, the screen alone never says it (the person's own search tab).
            Assert.That(ComputerUseSuccessCheck.Evaluate(SettingsPlaceCheck, echo, [], out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.SearchResultsEchoThePlace("configuracion", echo), Is.True);
            Assert.That(ComputerUseSuccessCheck.SearchResultsEchoThePlace("configuracion", encoded), Is.True);
            Assert.That(ComputerUseSuccessCheck.SearchResultsEchoThePlace("configuracion", settings), Is.False);
            // The real settings page counts, with the earlier turn's typing in memory too.
            Assert.That(ComputerUseSuccessCheck.Evaluate(SettingsPlaceCheck, settings, [], out string? by, typedBefore: earlier), Is.True);
            Assert.That(by, Is.EqualTo("control:configuracion:current"));
            // A search's own proof still takes its results page.
            JsonArray searched = new()
            {
                TypedInto("configuracion", "Escribe el término de búsqueda"),
                new JsonObject { ["operation"] = "input.key.press", ["key"] = "enter", ["ok"] = true },
            };
            Assert.That(ComputerUseSuccessCheck.Evaluate(
                "title:configuracion&stepDone:input.key.press:enter", echo, searched, out _, typedBefore: earlier), Is.True);
        });
    }

    // Revisión r23: only the query is the echo, never the site's own name in its address. A site's own results page
    // («gatos - YouTube» on youtube.com/results?search_query=gatos) still is that site: «andá a youtube.com» or «ir a la
    // pestaña YouTube» arrive there; the query («gatos») is what is echoed.
    [Test]
    public void ASitesOwnResultsPageStillIsTheSiteOnlyItsQueryIsTheEcho()
    {
        JsonObject results = View("""
            {"window": {"title": "gatos - YouTube - Personal: Microsoft​ Edge", "process": "msedge"},
             "controls": [
               {"kind": "TabItem", "name": "gatos - YouTube", "state": "selected"},
               {"kind": "Edit", "name": "Barra de direcciones y búsqueda", "value": "https://www.youtube.com/results?search_query=gatos"},
               {"kind": "Document", "name": "gatos - YouTube", "value": "https://www.youtube.com/results?search_query=gatos"},
               {"kind": "ComboBox", "name": "Buscar", "value": "gatos"}]}
            """);
        JsonObject encyclopedia = View("""
            {"window": {"title": "Curicó - Buscar - Wikipedia, la enciclopedia libre - Personal: Microsoft​ Edge", "process": "msedge"},
             "controls": [
               {"kind": "TabItem", "name": "Curicó - Buscar - Wikipedia, la enciclopedia libre", "state": "selected"},
               {"kind": "Edit", "name": "Barra de direcciones y búsqueda", "value": "es.wikipedia.org/w/index.php?search=Valpara%C3%ADso&title=Especial%3ABuscar"}]}
            """);
        JsonObject engine = View("""
            {"window": {"title": "gatos - Buscar con Google - Personal: Microsoft​ Edge", "process": "msedge"},
             "controls": [
               {"kind": "Edit", "name": "Barra de direcciones y búsqueda", "value": "https://www.google.com/search?q=gatos&sourceid=chrome"}]}
            """);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.SearchResultsEchoThePlace("youtube", results), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("title:youtube", results, [], out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:youtube:selected|title:youtube", results, [], out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate(
                "control:wikipedia:current|title:wikipedia|page:wikipedia", encyclopedia, [], out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("title:google", engine, [], out _), Is.True);
            // Revisión 2: the site's address typed in an earlier turn («abrí youtube en edge», then «buscá gatos») leaves
            // its own results page still that site; only a query that holds the name is the earlier echo.
            IReadOnlyList<TypedEarlier> youtubeTyped = [new("youtube.com", "Barra de direcciones y búsqueda", "msedge")];
            IReadOnlyList<TypedEarlier> googleTyped = [new("google.com", "Barra de direcciones y búsqueda", "msedge")];
            Assert.That(ComputerUseSuccessCheck.QueryEchoNames("youtube", results, [], false, youtubeTyped), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate(
                "control:youtube:selected|title:youtube", results, [], out _, typedBefore: youtubeTyped), Is.True);
            Assert.That(ComputerUseSuccessCheck.QueryEchoNames("google", engine, [], false, googleTyped), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("title:google", engine, [], out _, typedBefore: googleTyped), Is.True);
            // Contracase: the earlier turn typed the query itself, and the results page still holds it.
            IReadOnlyList<TypedEarlier> gatosTyped = [new("gatos", "Barra de direcciones y búsqueda", "msedge")];
            Assert.That(ComputerUseSuccessCheck.QueryEchoNames("gatos", results, [], false, gatosTyped), Is.True);
            Assert.That(ComputerUseSuccessCheck.QueryEchoNames("gatos", engine, [], false, gatosTyped), Is.True);
            // Contracases: the query BAXY typed is the echo, in the address (escapes read) or in the page's own box.
            IReadOnlyList<TypedEarlier> curicoTyped = [new("curico", "Buscar en Wikipedia", "msedge")];
            Assert.That(ComputerUseSuccessCheck.SearchResultsEchoThePlace("gatos", results), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("title:gatos", results, [], out _, typedBefore: gatosTyped), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("title:curico", encyclopedia, [], out _, typedBefore: curicoTyped), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("title:gatos", engine, [], out _, typedBefore: gatosTyped), Is.False);
        });
    }

    // Revisión 3 r23: the person's own search tab («gatos - Buscar con Google», google.com/search?q=gatos) is a tab BAXY
    // can take them to and read («andá a la pestaña de gatos», «¿qué dice la pestaña de clima?»): with nothing BAXY typed,
    // the screen alone is no echo, before or after the click that brought the tab to the front.
    [Test]
    public void ThePersonsOwnSearchTabIsAPlaceToGoToAndRead()
    {
        JsonObject tab = View("""
            {"window": {"title": "gatos - Buscar con Google - Personal: Microsoft​ Edge", "process": "msedge"},
             "controls": [
               {"kind": "TabItem", "name": "Correo - Outlook"},
               {"kind": "TabItem", "name": "gatos - Buscar con Google", "state": "selected"},
               {"kind": "Edit", "name": "Barra de direcciones y búsqueda", "value": "https://www.google.com/search?q=gatos&sourceid=chrome"},
               {"kind": "Document", "name": "gatos - Buscar con Google", "value": "https://www.google.com/search?q=gatos&sourceid=chrome"},
               {"kind": "ComboBox", "name": "Buscar", "value": "gatos"}]}
            """);
        JsonObject weather = View("""
            {"window": {"title": "clima curicó - Buscar con Google - Personal: Microsoft​ Edge", "process": "msedge"},
             "controls": [
               {"kind": "TabItem", "name": "clima curicó - Buscar con Google", "state": "selected"},
               {"kind": "Edit", "name": "Barra de direcciones y búsqueda", "value": "https://www.google.com/search?q=clima+valpara%C3%ADso"},
               {"kind": "ComboBox", "name": "Buscar", "value": "clima curicó"}]}
            """);
        const string tabCheck = "control:gatos:selected|title:gatos";
        JsonArray clicked = new() { PressedControl("gatos - Buscar con Google", "TabItem", surfaceChanged: true) };
        IReadOnlyList<TypedEarlier> elsewhere = [new("notas", "Buscar", "explorer")];
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate(tabCheck, tab, [], out string? by), Is.True);
            Assert.That(by, Is.EqualTo("control:gatos:selected"));
            Assert.That(ComputerUseSuccessCheck.Evaluate(tabCheck, tab, clicked, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate(tabCheck, tab, clicked, out _, typedBefore: elsewhere), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:clima:selected|title:clima", weather, [], out _), Is.True);
        });
    }

    // Ronda 23 (v3-58): the text an earlier turn typed into a search box of the same application echoes while a field
    // still holds it; once the place opened (the box emptied) it is the arrival, and another application's typing is no echo.
    [Test]
    public void AnEarlierTurnsSearchOnTheSameWindowStillEchoesWhileTheBoxHoldsIt()
    {
        JsonObject held = View("""
            {"window": {"title": "informe - Resultados de la búsqueda en Trabajo", "process": "explorer"},
             "controls": [{"kind": "TabItem", "name": "informe - Resultados de la búsqueda en Trabajo", "state": "selected"},
                          {"kind": "Edit", "name": "Buscar en Trabajo", "value": "informe"}]}
            """);
        JsonObject opened = View("""
            {"window": {"title": "informe - Explorador de archivos", "process": "explorer"},
             "controls": [{"kind": "TabItem", "name": "informe", "state": "selected"},
                          {"kind": "Edit", "name": "Buscar en informe", "value": ""}]}
            """);
        IReadOnlyList<TypedEarlier> searched = [new("informe", "Buscar en Trabajo", "explorer")];
        IReadOnlyList<TypedEarlier> elsewhere = [new("informe", "Buscar en Trabajo", "msedge")];
        IReadOnlyList<TypedEarlier> written = [new("informe", "", "explorer")];
        JsonArray none = new();
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.QueryEchoNames("informe", held, none, false, searched), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:informe:current|title:informe", held, none, out _, typedBefore: searched), Is.False);
            Assert.That(ComputerUseSuccessCheck.QueryEchoNames("informe", held, none, false), Is.False);
            Assert.That(ComputerUseSuccessCheck.QueryEchoNames("informe", held, none, false, elsewhere), Is.False);
            Assert.That(ComputerUseSuccessCheck.QueryEchoNames("informe", held, none, false, written), Is.False);
            Assert.That(ComputerUseSuccessCheck.QueryEchoNames("informe", held, none, true, searched), Is.False);
            Assert.That(ComputerUseSuccessCheck.QueryEchoNames("informe", opened, none, false, searched), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:informe:current|title:informe", opened, none, out _, typedBefore: searched), Is.True);
            // A click on the place by its whole name in these steps ends the earlier echo.
            JsonArray went = new() { PressedControl("informe", "Hyperlink", surfaceChanged: true) };
            Assert.That(ComputerUseSuccessCheck.QueryEchoNames("informe", held, went, false, searched), Is.False);
        });
    }

    // Ronda 23: the session's ledger keeps the box and the application each text was typed on; a step's receipt names them.
    [Test]
    public void TheSessionLedgerKeepsWhereEachTextWasTyped()
    {
        var ledger = new ComputerUseTypedLedger();
        var record = new JsonObject();
        ComputerUseMission.NoteWhereTheTextGoes(record, new JsonObject { ["text"] = "configuracion" }, View("""
            {"window": {"title": "Nueva pestaña - Microsoft Edge", "process": "msedge",
                        "focused": {"kind": "Edit", "name": "Escribe el término de búsqueda"}}, "controls": []}
            """));
        ledger.Add("configuracion", (string?)record["into"], (string?)record["typedOn"]);
        ledger.Add("  ");
        Assert.Multiple(() =>
        {
            Assert.That(ledger.Texts, Is.EqualTo(new[] { "configuracion" }));
            Assert.That(ledger.Entries, Is.EqualTo(new[] { new TypedEarlier("configuracion", "Escribe el término de búsqueda", "msedge") }));
        });
    }

    // M3: «No hay resultados para «cookies»» repeats the query and is no result of the search.
    [Test]
    public void ALineSayingNothingWasFoundIsNoResult()
    {
        JsonArray steps = new()
        {
            TypedInto("cookies", "Buscar configuración"),
            new JsonObject { ["operation"] = "input.key.press", ["key"] = "enter", ["ok"] = true },
        };
        JsonObject nothing = View("""
            {"window": {"title": "Configuración", "process": "msedge"}, "controls": [],
             "text": {"C": ["cookies", "No hay resultados para cookies"]}}
            """);
        JsonObject found = View("""
            {"window": {"title": "Configuración", "process": "msedge"}, "controls": [],
             "text": {"C": ["cookies", "Cookies y permisos del sitio"]}}
            """);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.OnlyTheQueryShows("cookies", nothing, steps), Is.True);
            Assert.That(ComputerUseSuccessCheck.OnlyTheQueryShows("cookies", found, steps), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("text:cookies&stepDone:input.key.press:enter", nothing, steps, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("text:cookies&stepDone:input.key.press:enter", found, steps, out _), Is.True);
        });
    }

    // Pasada v3 r9 (v3-02, v3-13), falsos fracasos: the option the act chose proves the done though its name was on the
    // first look; one chosen before any act touched it is told as already chosen, never as done.
    [Test]
    public void AnOptionTheClickChoseProvesTheDoneAndOneChosenBeforeIsAlreadyThere()
    {
        JsonObject before = View("""
            {"window": {"title": "Presentación1 - PowerPoint", "process": "POWERPNT"},
             "controls": [{"kind": "TabItem", "name": "Inicio", "state": "selected"}, {"kind": "TabItem", "name": "Transiciones"},
                          {"kind": "ListItem", "name": "Ninguna", "state": "selected"}, {"kind": "ListItem", "name": "Desvanecer"}]}
            """);
        JsonObject after = View("""
            {"window": {"title": "Presentación1 - PowerPoint", "process": "POWERPNT"},
             "controls": [{"kind": "TabItem", "name": "Inicio"}, {"kind": "TabItem", "name": "Transiciones", "state": "selected focused"},
                          {"kind": "ListItem", "name": "Ninguna"}, {"kind": "ListItem", "name": "Desvanecer", "state": "selected"}]}
            """);
        JsonArray clickedFade = new()
        {
            new JsonObject { ["step"] = 1, ["operation"] = "input.visible.click", ["label"] = "Desvanecer", ["ok"] = true, ["selected"] = true },
        };
        JsonObject chosenByTheClick = (JsonObject)after.DeepClone();
        chosenByTheClick["chosenBeforeClick"] = new JsonObject { ["1"] = ComputerUseSuccessCheck.ChosenNames(before) };
        JsonObject chosenAlready = (JsonObject)after.DeepClone();
        chosenAlready["chosenBeforeClick"] = new JsonObject { ["1"] = new JsonArray("transiciones", "desvanecer") };
        JsonObject player = View("""
            {"window": {"title": "Reproductor multimedia", "process": "Microsoft.Media.Player"},
             "controls": [{"kind": "ListItem", "name": "Configuración", "state": "selected"}, {"kind": "RadioButton", "name": "Claro"},
                          {"kind": "RadioButton", "name": "Oscuro", "state": "selected"}, {"kind": "Text", "name": "Oscuro"}],
             "chosenBeforeClick": {"1": [], "2": ["configuracion"]}}
            """);
        JsonArray openedSettings = new()
        {
            new JsonObject { ["step"] = 1, ["operation"] = "input.visible.click", ["label"] = "Configuración", ["ok"] = true, ["selected"] = true },
            new JsonObject { ["step"] = 2, ["operation"] = "input.visible.click", ["label"] = "Tema de la aplicación", ["ok"] = true, ["surfaceChanged"] = true },
        };
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.ChosenNames(before).Select(node => (string?)node), Is.EqualTo(new[] { "inicio", "ninguna" }));
            Assert.That(ComputerUseSuccessCheck.AlreadyChosen("Desvanecer", chosenByTheClick, clickedFade), Is.False);
            // Counter-case: the click found it chosen already; told as it already was (the mind's judge refuses it as
            // an act: tests/test_cu_estab_r16_juez_unico.py).
            Assert.That(ComputerUseSuccessCheck.AlreadyChosen("Desvanecer", chosenAlready, clickedFade), Is.True);
            // v3-13: the theme was «Oscuro» before the mission; no act chose it.
            Assert.That(ComputerUseSuccessCheck.AlreadyChosen("Oscuro", player, openedSettings), Is.True);
            Assert.That(ComputerUseSuccessCheck.AlreadyChosen("Configuración", player, openedSettings), Is.False);
            Assert.That(ComputerUseSuccessCheck.AlreadyChosen("Claro", player, openedSettings), Is.False);
        });
    }

    [Test]
    public void TheMindsClosingsOfWhatIsAlreadyDoneAreToldAsAlreadyChosen()
    {
        // Pasada r15b (A2): the mind closes without the model's «done» the option already chosen at the first look
        // (v3-31). Estabilización R16: the App no longer judges the mind's closings again (its EvidenceRefusal went;
        // the slide counted one more and the first look's «Diapositiva 1 de 1» are the mind's judge's:
        // tests/test_cu_estab_r16_juez_unico.py); what it still reads is whether the option was chosen already.
        JsonObject snip = View("""
            {"window": {"title": "Herramienta Recortes", "process": "SnippingTool"},
             "controls": [{"kind": "ComboBox", "name": "Menú desplegable de área de recorte y captura", "state": "collapsed"},
                          {"kind": "ListItem", "name": "Ventana", "state": "selected"}, {"kind": "Group", "name": "Ventana"}]}
            """);
        JsonArray opened = new() { new JsonObject { ["step"] = 1, ["operation"] = "app.open", ["appId"] = "Herramienta Recortes", ["ok"] = true } };
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.AlreadyChosen("Ventana", snip, opened), Is.True);
            // Counter-case: an option not chosen was never already there.
            Assert.That(ComputerUseSuccessCheck.AlreadyChosen("Rectángulo", snip, opened), Is.False);
        });
    }

    // Review of falsos éxitos v3 M2: the look after a click is what tells a result that navigated from the suggestion
    // of the query that only closed its list (UI Automation's receipt is the same for both: the item gone).
    [Test]
    public void TheLookAfterAClickTellsWhetherItBroughtSomethingNew()
    {
        JsonObject Searched() => new()
        {
            ["step"] = 2,
            ["operation"] = "input.visible.click",
            ["label"] = "Sistema",
            ["name"] = "Sistema",
            ["kind"] = "ListItem",
            ["ok"] = true,
            ["surfaceChanged"] = false,
            ["absentOrDisabled"] = true,
            ["cascadeStage"] = "uia",
        };
        JsonArray Steps() => new() { TypedInto("sistema", "Buscar una opción"), Searched() };
        var before = new JsonObject { ["2"] = new JsonArray("buscar una opcion", "inicio", "sistema") };
        JsonObject closed = View("""
            {"window": {"title": "Configuración", "process": "SystemSettings"},
             "controls": [{"kind": "Edit", "name": "Buscar una opción"}, {"kind": "ListItem", "name": "Inicio"}]}
            """);
        closed["controlsBeforeClick"] = before.DeepClone();
        JsonObject navigated = View("""
            {"window": {"title": "Configuración", "process": "SystemSettings"},
             "controls": [{"kind": "Edit", "name": "Buscar una opción"}, {"kind": "Text", "name": "Sistema"},
                          {"kind": "ListItem", "name": "Pantalla"}, {"kind": "ListItem", "name": "Sonido"}]}
            """);
        navigated["controlsBeforeClick"] = before.DeepClone();
        JsonArray onlyClosed = Steps();
        ComputerUseSuccessCheck.NoteWhatTheClickBrought(closed, onlyClosed);
        JsonArray wentThere = Steps();
        ComputerUseSuccessCheck.NoteWhatTheClickBrought(navigated, wentThere);
        JsonArray lateDrawn = Steps();
        ComputerUseSuccessCheck.NoteWhatTheClickBrought(closed, lateDrawn);
        ComputerUseSuccessCheck.NoteWhatTheClickBrought(navigated, lateDrawn);
        ComputerUseSuccessCheck.NoteWhatTheClickBrought(closed, lateDrawn);
        JsonArray typedLast = new() { Searched(), TypedInto("sistema", "Buscar una opción") };
        ComputerUseSuccessCheck.NoteWhatTheClickBrought(closed, typedLast);
        var queries = new List<string> { "sistema" };
        Assert.Multiple(() =>
        {
            Assert.That((bool?)onlyClosed[1]!["broughtNew"], Is.False);
            Assert.That(ComputerUseSuccessCheck.ClickEchoesQuery(onlyClosed[1]!.AsObject(), queries), Is.True);
            // Estabilización R16: what the mind's acted_with_effect reads of them (HistoryForMind).
            Assert.That((bool?)ComputerUseMission.HistoryForMind(onlyClosed, 0)[1]!["echo"], Is.True,
                "the query typed into a search and its own suggestion that only closed the list are no act");
            Assert.That((bool?)wentThere[1]!["broughtNew"], Is.True);
            Assert.That(ComputerUseSuccessCheck.ClickEchoesQuery(wentThere[1]!.AsObject(), queries), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.visible.click:sistema", navigated, wentThere, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.visible.click:sistema", closed, onlyClosed, out _), Is.False);
            Assert.That((bool?)lateDrawn[1]!["broughtNew"], Is.True, "a page drawn late: once new, it stays");
            Assert.That(typedLast[0]!["broughtNew"], Is.Null, "only the last step, when it is a click, is noted");
        });
    }

    // Review of falsos éxitos v3 M3: a match pressed whose page shows the place by its whole name arrived (Settings:
    // «sonido» typed, «Configuración de sonido» pressed, the page headed «Sonido» and the box empty again).
    [Test]
    public void AMatchPressedWhosePageShowsThePlaceWholeArrived()
    {
        JsonArray steps = new()
        {
            TypedInto("sonido", "Buscar una opción"),
            PressedControl("Configuración de sonido", "ListItem", surfaceChanged: false, absentOrDisabled: true),
        };
        JsonObject heading = View("""
            {"window": {"title": "Configuración", "process": "SystemSettings"},
             "controls": [{"kind": "Edit", "name": "Buscar una opción", "value": ""}, {"kind": "Text", "name": "Sonido"},
                          {"kind": "ListItem", "name": "Sonido", "state": "selected current"}]}
            """);
        JsonObject inTitle = View("""
            {"window": {"title": "Sonido - Configuración", "process": "SystemSettings"}, "controls": []}
            """);
        JsonObject stillMatches = View("""
            {"window": {"title": "Configuración", "process": "SystemSettings"},
             "controls": [{"kind": "Text", "name": "Configuración de sonido avanzada"}]}
            """);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.QueryEchoNames("sonido", heading, steps, false), Is.False);
            Assert.That(ComputerUseSuccessCheck.QueryEchoNames("sonido", inTitle, steps, false), Is.False);
            Assert.That(ComputerUseSuccessCheck.QueryEchoNames("sonido", stillMatches, steps, false), Is.True);
        });
    }

    // v3 r5a M2 (v3-44): «devices and printers» typed into the Control Panel's box (no «into» on the step), a help
    // match pressed; the title «devices and printers - Panel de control» is the query repeated while the box still
    // holds it or the window says nothing matched. Counter-cases: the same title once the box is empty and no line says
    // nothing was found, and a folder named like the query in a window with no field holding it.
    [Test]
    public void ATitlePartThatIsTheTypedQueryIsNoArrivalWhileTheBoxHoldsIt()
    {
        JsonArray steps = new()
        {
            new JsonObject { ["operation"] = "input.text.type", ["text"] = "devices and printers", ["ok"] = true, ["changed"] = true },
            PressedControl("Buscar «devices and printers» en Ayuda y soporte técnico", "Hyperlink", surfaceChanged: true),
        };
        JsonObject echo = View("""
            {"window": {"title": "devices and printers - Panel de control", "process": "explorer"},
             "controls": [{"kind": "Edit", "name": "Buscar en el Panel de control", "value": "devices and printers"}]}
            """);
        JsonObject nothing = View("""
            {"window": {"title": "devices and printers - Panel de control", "process": "explorer"},
             "controls": [{"kind": "Text", "name": "Ningún elemento coincide con la búsqueda."}]}
            """);
        JsonObject arrived = View("""
            {"window": {"title": "devices and printers - Panel de control", "process": "explorer"},
             "controls": [{"kind": "Edit", "name": "Buscar en el Panel de control", "value": ""}]}
            """);
        JsonArray folder = new()
        {
            TypedInto("informe", "Buscar en Documentos"),
            PressedControl("informe final", "ListItem", surfaceChanged: true),
        };
        JsonObject folderOpen = View("""
            {"window": {"title": "informe - Explorador de archivos", "process": "explorer"},
             "controls": [{"kind": "Edit", "name": "Buscar en informe", "value": ""}]}
            """);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.QueryEchoNames("devices and printers", echo, steps, false), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("title:devices and printers", echo, steps, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.QueryEchoNames("devices and printers", nothing, steps, false), Is.True);
            Assert.That(ComputerUseSuccessCheck.QueryEchoNames("devices and printers", arrived, steps, false), Is.False);
            Assert.That(ComputerUseSuccessCheck.QueryEchoNames("informe", folderOpen, folder, false), Is.False);
        });
    }

    // v3-59 r7: «wikipedia» typed into Edge's address bar, a suggestion pressed, and the tab left on a web search's
    // results («wikipedia español - Búsqueda» on bing.com/search): its title passed «ir a wikipedia». A place typed and
    // left on a search results page was searched, not reached. Counter-cases: the place's own page (the address went
    // there), a click on the result named the place, and a search the goal asks for (searchResultsProve).
    [Test]
    public void APlaceTypedThatLeftASearchResultsPageWasSearchedNotReached()
    {
        JsonArray steps = new()
        {
            TypedInto("wikipedia", "Barra de direcciones y búsqueda"),
            PressedControl("Búsqueda de wikipedia español, Bing", "ListItem", surfaceChanged: false),
        };
        JsonObject results = View("""
            {"window": {"title": "wikipedia español - Búsqueda y 3 páginas más - Personal: Microsoft Edge", "process": "msedge"},
             "controls": [{"kind": "Edit", "name": "Barra de direcciones y búsqueda", "value": "https://www.bing.com/search?qs=AS&pq=wik"},
                          {"kind": "Hyperlink", "name": "Wikipedia"}]}
            """);
        JsonObject page = View("""
            {"window": {"title": "Wikipedia, la enciclopedia libre y 3 páginas más - Personal: Microsoft Edge", "process": "msedge"},
             "controls": [{"kind": "Edit", "name": "Barra de direcciones y búsqueda", "value": "https://es.wikipedia.org/wiki/Wikipedia:Portada"},
                          {"kind": "Hyperlink", "name": "Wikipedia"}]}
            """);
        JsonArray pressed = new()
        {
            TypedInto("wikipedia", "Barra de direcciones y búsqueda"),
            new JsonObject { ["operation"] = "input.key.press", ["key"] = "enter", ["ok"] = true },
            PressedControl("Wikipedia", "Hyperlink", surfaceChanged: true),
        };
        JsonArray searched = new()
        {
            TypedInto("curico", "Barra de direcciones y búsqueda"),
            new JsonObject { ["operation"] = "input.key.press", ["key"] = "enter", ["ok"] = true },
        };
        JsonObject found = View("""
            {"window": {"title": "Curicó - Búsqueda - Personal: Microsoft Edge", "process": "msedge"},
             "controls": [{"kind": "Edit", "name": "Barra de direcciones y búsqueda", "value": "https://www.bing.com/search?q=Curico"}]}
            """);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.ShowsSearchResultsPage(results), Is.True);
            Assert.That(ComputerUseSuccessCheck.QueryEchoNames("wikipedia", results, steps, false), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("title:wikipedia", results, steps, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.ShowsSearchResultsPage(page), Is.False);
            // An address bar that shows the address without its scheme (Chromium) is the same results page; a field
            // holding only the word typed is no address.
            Assert.That(ComputerUseSuccessCheck.ShowsSearchResultsPage(View("""
                {"window": {"title": "wikipedia - Búsqueda", "process": "chrome"},
                 "controls": [{"kind": "Edit", "name": "Barra de direcciones", "value": "bing.com/search?q=wikipedia"}]}
                """)), Is.True);
            Assert.That(ComputerUseSuccessCheck.ShowsSearchResultsPage(View("""
                {"window": {"title": "Wikipedia", "process": "chrome"},
                 "controls": [{"kind": "Edit", "name": "Buscar", "value": "wikipedia/search"}]}
                """)), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("title:wikipedia", page, steps, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.QueryEchoNames("wikipedia", results, pressed, false), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate(
                "title:curico&stepDone:input.key.press:enter", found, searched, out _), Is.True);
        });
    }

    // Review of falsos éxitos v3 M1: finding the thing is not doing it. Typing its name into a box that only searches
    // and sending it are no act for a goal that is not a search; a scroll that moved nothing is none either.
    // Estabilización R16: that reading is the mind's (cu_evidence.acted_with_effect, its judge of the done:
    // tests/test_cu_estab_r16_juez_unico.py); the App tells it which text went into a box that only searches («query»).
    [Test]
    public void SearchingTheNameIsNoActForAGoalOfDoingSomethingElse()
    {
        JsonArray searched = new()
        {
            TypedInto("cuphead", "Buscar en la tienda"),
            new JsonObject { ["operation"] = "input.key.press", ["key"] = "enter", ["ok"] = true },
        };
        JsonArray named = new()
        {
            TypedInto("informe", "Nombre"),
            new JsonObject { ["operation"] = "input.key.press", ["key"] = "enter", ["ok"] = true },
        };
        Assert.Multiple(() =>
        {
            Assert.That((bool?)ComputerUseMission.HistoryForMind(searched, 0)[0]!["query"], Is.True);
            Assert.That(ComputerUseMission.HistoryForMind(named, 0)[0]!["query"], Is.Null, "a name box is no search");
        });
    }

    // ------------------------------------------------------- pasada v3 r9: v3-42 on the views read live

    // Sub-goal 1 «ir a programas y caracteristicas»: one verified click on the link «Programas» (journal seq 492) and
    // the view after it (seq 494). The link «Programas y características», alone at the top left of its row, passed
    // page: as the page's header. A link named as the place leads there; a heading named so is where the window is.
    [Test]
    public void V3_42_ALinkNamedAsThePlaceIsNotItsHeader()
    {
        JsonArray clicked = new()
        {
            new JsonObject
            {
                ["step"] = 1, ["operation"] = "input.visible.click", ["label"] = "Programas", ["name"] = "Programas",
                ["kind"] = "Hyperlink", ["ok"] = true, ["surfaceChanged"] = false, ["absentOrDisabled"] = true,
            },
        };
        JsonObject linked = View(ComputerUseRealViews.V342ProgramsPage);
        JsonObject headed = View(ComputerUseRealViews.V342ProgramsPage);
        headed["controls"]![19]!["kind"] = "Text";
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate(ComputerUseRealViews.V342Check1, linked, clicked, out string? by), Is.False, by);
            Assert.That(ComputerUseSuccessCheck.Evaluate(ComputerUseRealViews.V342Check1, headed, clicked, out string? heading), Is.True);
            Assert.That(heading, Is.EqualTo("page:programas y caracteristicas"));
        });
    }

    // Sub-goal 2 «buscar chrome»: the search box clicked, «chrome» typed (its receipt reread the title «chrome -
    // Programas» at once) and Enter (journal seq 496–504), over the view after it (seq 506). The title repeating the
    // query passed title:chrome&Enter; the window says nothing matched. Counter-case: a results page that takes the query
    // into its title only after the submit still proves the search.
    [Test]
    public void V3_42_TheTitleRepeatingTheTypedQueryIsNoArrivalNorResult()
    {
        static JsonArray Searched(string titleWhenTyped) => new()
        {
            new JsonObject
            {
                ["step"] = 2, ["operation"] = "input.visible.click", ["label"] = "Cuadro de búsqueda", ["name"] = "Cuadro de búsqueda",
                ["kind"] = "Edit", ["ok"] = true, ["surfaceChanged"] = true,
            },
            new JsonObject
            {
                ["step"] = 3, ["operation"] = "input.text.type", ["text"] = "chrome", ["into"] = "Cuadro de búsqueda", ["ok"] = true,
                ["changed"] = true, ["windowTitle"] = titleWhenTyped,
            },
            new JsonObject { ["step"] = 4, ["operation"] = "input.key.press", ["key"] = "enter", ["ok"] = true, ["changed"] = true },
        };

        JsonObject nothing = View(ComputerUseRealViews.V342SearchedNothing);
        JsonObject results = View("""
            {"window": {"title": "chrome - Buscar con Google", "process": "msedge"},
             "controls": [{"i": 0, "kind": "Edit", "name": "Buscar", "value": "chrome"},
                          {"i": 1, "kind": "Hyperlink", "name": "Google Chrome - Descargar"}],
             "text": {"C": ["Google Chrome: el navegador web rápido y seguro"]}}
            """);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.TitleEchoedTheTyping("chrome", Searched("chrome - Programas")), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate(ComputerUseRealViews.V342Check2, nothing, Searched("chrome - Programas"), out string? by),
                Is.False, by);
            Assert.That(ComputerUseSuccessCheck.TitleEchoedTheTyping("chrome", Searched("Google")), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate(ComputerUseRealViews.V342Check2, results, Searched("Google"), out string? proved),
                Is.True);
            Assert.That(proved, Is.EqualTo("title:chrome&stepDone:input.key.press:enter"));
        });
    }

    // The trace says which term of the planned check held, as a label with no content.
    [Test]
    public void TheSatisfiedLabelNamesTheTermThatHeldWithoutItsContent()
    {
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.SatisfiedLabel(ComputerUseRealViews.V342Check1, "page:programas y caracteristicas"),
                Is.EqualTo("term.3.page"));
            Assert.That(ComputerUseMission.SatisfiedLabel(ComputerUseRealViews.V342Check2, "title:chrome&stepDone:input.key.press:enter"),
                Is.EqualTo("term.1.title-stepdone"));
            Assert.That(ComputerUseMission.SatisfiedLabel(ComputerUseRealViews.V342Check1, "page:programas y caracteristicas&similar:programas"),
                Is.EqualTo("term.3.page-similar"));
            Assert.That(ComputerUseMission.SatisfiedLabel(ComputerUseRealViews.V342Check1, "page:programs and features"),
                Is.EqualTo("alias.page"));
            Assert.That(ComputerUseMission.SatisfiedLabel(ComputerUseRealViews.V342Check1, "model_evidence"), Is.EqualTo("model_evidence"));
            Assert.That(ComputerUseMission.SatisfiedLabel(ComputerUseRealViews.V342Check1, null), Is.EqualTo("none"));
            Assert.That(ShellTrace.SanitizeLabel("subgoal.2." + ComputerUseMission.SatisfiedLabel(
                ComputerUseRealViews.V342Check2, "stepDone:input.text.type&stepDone:input.key.press:enter&text:chrome")),
                Is.EqualTo("subgoal.2.term.3.stepdone-stepdone-text"));
        });
    }

    // Menús efímeros (pasada r15b t-form-2, t-file-4, t-form-3): the opener's popup died when the person took the front
    // back, its item failed as not found, and reopening the opener from the same screen is no cycle, once.
    [Test]
    public void ReopeningAnOpenerWhosePopupDiedUnderTheItemIsNoCycleOnce()
    {
        JsonArray steps =
        [
            new JsonObject
            {
                ["step"] = 1, ["operation"] = "input.visible.click", ["label"] = "Editar", ["index"] = 9, ["ok"] = true,
                ["surfaceChanged"] = true, ["changed"] = true, ["broughtNew"] = true, ["opener"] = true, ["viewHash"] = "main",
            },
            new JsonObject
            {
                ["step"] = 2, ["operation"] = "input.visible.click", ["label"] = "Reemplazar", ["index"] = 3, ["ok"] = false,
                ["error"] = "visible_button_not_found", ["viewHash"] = "popup",
            },
        ];
        var again = new JsonObject { ["label"] = "Editar", ["index"] = 9 };

        bool first = ComputerUseMission.RepeatsAnActThatCycled(steps, "input.visible.click", again, "main", out bool reopens);
        steps.Add((JsonNode?)new JsonObject
        {
            ["step"] = 3,
            ["operation"] = "input.visible.click",
            ["label"] = "Editar",
            ["index"] = 9,
            ["ok"] = true,
            ["surfaceChanged"] = true,
            ["broughtNew"] = true,
            ["opener"] = true,
            ["reopens"] = true,
            ["viewHash"] = "main",
        });
        steps.Add((JsonNode?)new JsonObject
        {
            ["step"] = 4,
            ["operation"] = "input.visible.click",
            ["label"] = "Reemplazar",
            ["index"] = 3,
            ["ok"] = false,
            ["error"] = "visible_button_not_found",
            ["viewHash"] = "popup",
        });
        bool second = ComputerUseMission.RepeatsAnActThatCycled(steps, "input.visible.click", again, "main", out bool reopensAgain);

        Assert.Multiple(() =>
        {
            Assert.That(first, Is.False);
            Assert.That(reopens, Is.True);
            Assert.That(second, Is.True, "the second real round is a cycle");
            Assert.That(reopensAgain, Is.False);
        });
    }

    // Ronda 21 (t-file-4) rewritten for estabilización D: «Archivo» opened (opened:true) with the mission's window in
    // front, which it keeps while it acts: no opening is lost with the front any more, so the same act from the same
    // screen is a cycle, whatever an old receipt said of the front (frontHeld:false); and an opening is no click done.
    [Test]
    public void AnOpeningFromTheSameScreenIsACycleNowThatTheFrontIsKept()
    {
        static JsonObject Archivo(bool? frontHeld)
        {
            var archivo = new JsonObject
            {
                ["step"] = 1,
                ["operation"] = "input.visible.click",
                ["label"] = "Archivo",
                ["index"] = 2,
                ["ok"] = true,
                ["manner"] = "open",
                ["opened"] = true,
                ["viewHash"] = "main",
            };
            if (frontHeld is { } held)
            {
                archivo["frontHeld"] = held;
            }

            return archivo;
        }

        var again = new JsonObject { ["label"] = "Archivo", ["index"] = 2, ["manner"] = "open" };
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.RepeatsAnActThatCycled([Archivo(false)], "input.visible.click", again, "main", out bool reopens), Is.True);
            Assert.That(reopens, Is.False);
            Assert.That(ComputerUseMission.RepeatsAnActThatCycled([Archivo(null)], "input.visible.click", again, "main"), Is.True,
                "the same act with the same screen is a cycle");
            Assert.That(ComputerUseSuccessCheck.Atom("stepDone:input.visible.click:archivo", new JsonObject(), [Archivo(null)]), Is.False,
                "an opening is no click done");
        });
    }

    // Ronda 21 (t-menu-1, t-menu-2): the context menu opened by the menu act on X closes «abrir el menu contextual de X»
    // by the state it left (its receipt, or a menu on the view), not only by the key. Counter-cases: a menu act that
    // failed or that opened nothing proves nothing; a menu on the view without
    // any menu act of the sub-goal proves nothing either. Revisión 1 (hallazgo 3): the atom carries X: a menu opened on
    // another element («lista.txt» for «notas.txt») proves nothing, and an empty space's (no name) takes only the menu
    // act on a container, never on an item.
    [Test]
    public void TheContextMenuCheckTakesTheStateTheMenuActLeftOnItsOwnTarget()
    {
        const string Keys = "stepDone:input.key.press:context_menu|stepDone:input.key.press:shift_f10";
        const string Check = Keys + "|menuOpened:notas.txt";
        const string EmptySpace = Keys + "|menuOpened:";
        static JsonObject Menu(bool ok, bool? opened = null, bool? frontHeld = null, string label = "notas.txt", string? targetKind = null)
        {
            var step = new JsonObject
            {
                ["operation"] = "input.visible.click",
                ["label"] = label,
                ["index"] = 1,
                ["manner"] = "menu",
                ["ok"] = ok,
            };
            if (opened is { } o)
            {
                step["opened"] = o;
            }

            if (frontHeld is { } f)
            {
                step["frontHeld"] = f;
            }

            if (targetKind is not null)
            {
                step["targetKind"] = targetKind;
            }

            return step;
        }

        var withMenu = new JsonObject { ["controls"] = new JsonArray(new JsonObject { ["i"] = 5, ["name"] = "Contexto", ["kind"] = "Menu" }) };
        var plain = new JsonObject { ["controls"] = new JsonArray(new JsonObject { ["i"] = 1, ["name"] = "notas.txt", ["kind"] = "ListItem" }) };
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.EvaluateReceipts(Check, [Menu(true, opened: true)], out string? by), Is.True);
            Assert.That(by, Is.EqualTo("menuOpened:notas.txt"));
            Assert.That(ComputerUseSuccessCheck.Evaluate(Check, withMenu, [Menu(true)], out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.EvaluateReceipts(Check, [Menu(false, opened: true)], out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.EvaluateReceipts(Check, [Menu(true, opened: false)], out _), Is.False);
            // Estabilización D: the window keeps the front while the mission acts; an old «frontHeld: false» loses nothing.
            Assert.That(ComputerUseSuccessCheck.EvaluateReceipts(Check, [Menu(true, opened: true, frontHeld: false)], out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate(Check, plain, [Menu(true)], out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate(Check, withMenu, [], out _), Is.False);
            // Hallazgo 3: the menu opened on another element is none of X's, by its receipt or by the menu on the view.
            Assert.That(ComputerUseSuccessCheck.EvaluateReceipts(Check, [Menu(true, opened: true, label: "lista.txt")], out _), Is.False,
                "a menu opened on lista.txt is not notas.txt's");
            Assert.That(ComputerUseSuccessCheck.Evaluate(Check, withMenu, [Menu(true, label: "lista.txt")], out _), Is.False);
            // An empty space: the menu act on a container (its kind in the view it was decided on), never on an item.
            Assert.That(ComputerUseSuccessCheck.EvaluateReceipts(EmptySpace, [Menu(true, opened: true, label: "Vista de elementos", targetKind: "List")], out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.EvaluateReceipts(EmptySpace, [Menu(true, opened: true, targetKind: "ListItem")], out _), Is.False,
                "an item's menu is no empty space's");
            Assert.That(ComputerUseSuccessCheck.EvaluateReceipts(EmptySpace, [Menu(true, opened: true)], out _), Is.False,
                "a menu act whose target is unknown proves no empty space");
            JsonArray key = [new JsonObject { ["operation"] = "input.key.press", ["key"] = "context_menu", ["ok"] = true }];
            Assert.That(ComputerUseSuccessCheck.EvaluateReceipts(Check, key, out _), Is.True, "the key stays the fallback");
        });
    }

    // Revisión 1 de la ronda 21 (hallazgo 3): the kind a menu act was decided on is read from the view by its index.
    [Test]
    public void AMenuActsTargetKindIsTheViewsControlAtItsIndex()
    {
        var view = new JsonObject
        {
            ["controls"] = new JsonArray(
                new JsonObject { ["i"] = 0, ["name"] = "Vista de elementos", ["kind"] = "List" },
                new JsonObject { ["i"] = 1, ["name"] = "notas.txt", ["kind"] = "ListItem" }),
        };
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.MenuTargetKind(view, JsonValue.Create(0)), Is.EqualTo("List"));
            Assert.That(ComputerUseSuccessCheck.MenuTargetKind(view, JsonValue.Create(1)), Is.EqualTo("ListItem"));
            Assert.That(ComputerUseSuccessCheck.MenuTargetKind(view, JsonValue.Create(7)), Is.Null);
            Assert.That(ComputerUseSuccessCheck.MenuTargetKind(view, null), Is.Null);
            Assert.That(ComputerUseSuccessCheck.MenuTargetKind(null, JsonValue.Create(0)), Is.Null);
        });
    }

    // t-menu-3: «Ver» said surfaceChanged while the look after it saw the window as before (the drop-down closed before
    // the look): reopening it is no cycle the first time, and is the second.
    [Test]
    public void AnOpenerWhoseOpeningClosedBeforeTheLookIsReopenedOnceOnly()
    {
        static JsonObject Ver(int step, bool reopened)
        {
            var ver = new JsonObject
            {
                ["step"] = step,
                ["operation"] = "input.visible.click",
                ["label"] = "Ver",
                ["index"] = 10,
                ["ok"] = true,
                ["surfaceChanged"] = true,
                ["changed"] = true,
                ["sameView"] = true,
                ["opener"] = true,
                ["viewHash"] = "main",
            };
            if (reopened)
            {
                ver["reopens"] = true;
            }

            return ver;
        }

        var again = new JsonObject { ["label"] = "Ver", ["index"] = 10 };
        JsonArray once = [Ver(1, reopened: false)];
        JsonArray twice = [Ver(1, reopened: false), Ver(2, reopened: true)];
        JsonObject notAnOpener = Ver(1, reopened: false);
        notAnOpener.Remove("opener");

        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.RepeatsAnActThatCycled(once, "input.visible.click", again, "main", out bool reopens), Is.False);
            Assert.That(reopens, Is.True);
            Assert.That(ComputerUseMission.RepeatsAnActThatCycled(twice, "input.visible.click", again, "main"), Is.True);
            Assert.That(ComputerUseMission.RepeatsAnActThatCycled([notAnOpener], "input.visible.click", again, "main"), Is.True,
                "a control that opens nothing by its structure keeps the cycle");
        });
    }

    // Contracases: a toggle pressed twice back to its state, and a menu its own second press closed (no front handed
    // back, no item failed), are still cycles.
    [Test]
    public void ATogglePressedTwiceOrAMenuClosedByItsOwnActStaysACycle()
    {
        JsonArray toggle =
        [
            new JsonObject { ["step"] = 1, ["operation"] = "input.visible.click", ["label"] = "Negrita", ["index"] = 13, ["ok"] = true, ["toggled"] = true, ["changed"] = true, ["viewHash"] = "off" },
            new JsonObject { ["step"] = 2, ["operation"] = "input.visible.click", ["label"] = "Negrita", ["index"] = 13, ["ok"] = true, ["toggled"] = true, ["changed"] = true, ["viewHash"] = "on" },
        ];
        JsonArray menu =
        [
            new JsonObject { ["step"] = 1, ["operation"] = "input.visible.click", ["label"] = "Menú", ["ok"] = true, ["surfaceChanged"] = true, ["broughtNew"] = true, ["opener"] = true, ["viewHash"] = "closed" },
            new JsonObject { ["step"] = 2, ["operation"] = "input.visible.click", ["label"] = "Menú", ["ok"] = true, ["surfaceChanged"] = true, ["opener"] = true, ["viewHash"] = "open" },
        ];
        // Review of the branch (finding 2): the same menu as the real receipt says it when pressed in the person's
        // pause: a chain's front taken (chain, frontChanged), and still the look after it saw it open.
        JsonArray chained =
        [
            new JsonObject { ["step"] = 1, ["operation"] = "input.visible.click", ["label"] = "Fuente", ["ok"] = true, ["surfaceChanged"] = true, ["broughtNew"] = true, ["opener"] = true, ["chain"] = true, ["frontChanged"] = true, ["frontRestored"] = true, ["viewHash"] = "closed" },
            new JsonObject { ["step"] = 2, ["operation"] = "input.visible.click", ["label"] = "Fuente", ["ok"] = true, ["surfaceChanged"] = true, ["opener"] = true, ["chain"] = true, ["frontChanged"] = true, ["viewHash"] = "open" },
        ];

        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.RepeatsAnActThatCycled(toggle, "input.visible.click", new JsonObject { ["label"] = "Negrita", ["index"] = 13 }, "off"), Is.True);
            Assert.That(ComputerUseMission.RepeatsAnActThatCycled(menu, "input.visible.click", new JsonObject { ["label"] = "Menú" }, "closed"), Is.True);
            Assert.That(ComputerUseMission.RepeatsAnActThatCycled(chained, "input.visible.click", new JsonObject { ["label"] = "Fuente" }, "closed", out bool reopens), Is.True,
                "a front taken by the chain proves no opening lost");
            Assert.That(reopens, Is.False);
        });
    }

    // Review of the branch (finding 2): an opener that took the front while the look after it saw the window as before
    // lost its opening before the look, and is reopened once; one whose look saw something new is not, front or not.
    [TestCase(true, false, true)]
    [TestCase(false, true, false)]
    [TestCase(false, false, false)]
    public void AFrontTakenCountsOnlyWithTheLookThatSawNothingOpen(bool sameView, bool broughtNew, bool reopened)
    {
        var act = new JsonObject
        {
            ["step"] = 1,
            ["operation"] = "input.visible.click",
            ["label"] = "Ver",
            ["index"] = 10,
            ["ok"] = true,
            ["opener"] = true,
            ["frontChanged"] = true,
            ["frontRestored"] = true,
            ["viewHash"] = "main",
        };
        if (sameView)
        {
            act["sameView"] = true;
        }

        if (broughtNew)
        {
            act["broughtNew"] = true;
        }

        bool cycled = ComputerUseMission.RepeatsAnActThatCycled(
            [act], "input.visible.click", new JsonObject { ["label"] = "Ver", ["index"] = 10 }, "main", out bool reopens);

        Assert.Multiple(() =>
        {
            Assert.That(reopens, Is.EqualTo(reopened));
            Assert.That(cycled, Is.EqualTo(!reopened));
        });
    }

    // Ronda 20 (P7, v3-28): the arrow of «Fuente:» opened inside a chain, as its real receipt says it (opened, chain,
    // frontHeld; no surfaceChanged nor frontChanged), and the look after it saw the window as before: the list closed when
    // the person took the front back, and opening it again is no cycle, once. Contracases: the same receipt whose look saw
    // the list (no sameView), a toggle that says opened, and a second reopening, stay cycles.
    [TestCase(true, false, false, true, TestName = "opened in a chain, look as before: reopened once")]
    [TestCase(false, false, false, false, TestName = "opened in a chain, the look saw it: a cycle")]
    [TestCase(true, true, false, false, TestName = "a toggle: a cycle")]
    [TestCase(true, false, true, false, TestName = "already reopened once: a cycle")]
    public void AnArrowOpenedInAChainWhoseListClosedBeforeTheLookIsReopenedOnce(bool sameView, bool toggled, bool reopenedBefore, bool reopened)
    {
        JsonObject Fuente(int step)
        {
            var act = new JsonObject
            {
                ["step"] = step,
                ["operation"] = "input.visible.click",
                ["label"] = "Fuente:",
                ["index"] = 8,
                ["manner"] = "open",
                ["ok"] = true,
                ["opened"] = true,
                ["chain"] = true,
                ["method"] = "expand",
                ["opener"] = true,
                ["viewHash"] = "main",
            };
            if (sameView)
            {
                act["sameView"] = true;
            }

            if (toggled)
            {
                act["toggled"] = true;
            }

            return act;
        }

        JsonArray steps = [Fuente(1)];
        if (reopenedBefore)
        {
            JsonObject again = Fuente(2);
            again["reopens"] = true;
            steps.Add((JsonNode?)again);
        }

        bool cycled = ComputerUseMission.RepeatsAnActThatCycled(
            steps, "input.visible.click", new JsonObject { ["label"] = "Fuente:", ["index"] = 8, ["manner"] = "open" }, "main", out bool reopens);

        Assert.Multiple(() =>
        {
            Assert.That(reopens, Is.EqualTo(reopened));
            Assert.That(cycled, Is.EqualTo(!reopened));
        });
    }

    // Ronda 20 (P7, v3-37): an arrow or a context menu opened by its manner is an opener whatever the control says (a split
    // button with no state); the same control clicked plainly is not, and a double click never is.
    [TestCase("open", true)]
    [TestCase("menu", true)]
    [TestCase("double", false)]
    [TestCase(null, false)]
    public void AnArrowOrAContextMenuIsAnOpenerByItsManner(string? manner, bool opener)
    {
        JsonObject view = View("""
            {"window": {"title": "Terminal", "hwnd": 5},
             "controls": [{"i": 2, "kind": "SplitButton", "name": "Nueva pestaña", "state": ""}]}
            """);
        var arguments = new JsonObject { ["label"] = "Nueva pestaña", ["index"] = 2 };
        if (manner is not null)
        {
            arguments["manner"] = manner;
        }

        Assert.That(ComputerUseMission.ClicksAnOpener("input.visible.click", arguments, view), Is.EqualTo(opener));
    }

    // Review of the branch (finding 4): «Eliminar» is a button, no opener; it brought its confirmation, whose «Sí» then
    // failed as not found, and pressing «Eliminar» again from the same screen is a cycle, never a reopening.
    [Test]
    public void AButtonThatBroughtADialogIsNoOpenerToReopen()
    {
        JsonArray steps =
        [
            new JsonObject
            {
                ["step"] = 1, ["operation"] = "input.visible.click", ["label"] = "Eliminar", ["index"] = 4, ["ok"] = true,
                ["surfaceChanged"] = true, ["changed"] = true, ["broughtNew"] = true, ["frontChanged"] = true, ["viewHash"] = "list",
            },
            new JsonObject
            {
                ["step"] = 2, ["operation"] = "input.visible.click", ["label"] = "Sí", ["index"] = 2, ["ok"] = false,
                ["error"] = "visible_button_not_found", ["viewHash"] = "dialog",
            },
        ];

        bool cycled = ComputerUseMission.RepeatsAnActThatCycled(
            steps, "input.visible.click", new JsonObject { ["label"] = "Eliminar", ["index"] = 4 }, "list", out bool reopens);

        Assert.Multiple(() =>
        {
            Assert.That(cycled, Is.True);
            Assert.That(reopens, Is.False);
        });
    }

    [Test]
    public void AnOpenerIsReadFromTheViewsStructureNeverFromAName()
    {
        JsonObject view = View("""
            {"window": {"title": "Bloc de notas", "hwnd": 5},
             "controls": [
               {"i": 0, "kind": "MenuItem", "name": "Editar", "state": "collapsed"},
               {"i": 1, "kind": "Button", "name": "Tabla", "state": "collapsed"},
               {"i": 2, "kind": "Button", "name": "Negrita", "state": "off"},
               {"i": 3, "kind": "ComboBox", "name": "Fuente", "state": ""},
               {"i": 4, "kind": "MenuItem", "name": "Guardar", "state": ""}
             ]}
            """);

        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.ClicksAnOpener("input.visible.click", new JsonObject { ["label"] = "Editar", ["index"] = 0 }, view), Is.True);
            Assert.That(ComputerUseMission.ClicksAnOpener("input.visible.click", new JsonObject { ["label"] = "Tabla" }, view), Is.True);
            Assert.That(ComputerUseMission.ClicksAnOpener("input.visible.click", new JsonObject { ["label"] = "Negrita", ["index"] = 2 }, view), Is.False);
            Assert.That(ComputerUseMission.ClicksAnOpener("input.visible.click", new JsonObject { ["label"] = "Fuente", ["index"] = 3 }, view), Is.True);
            Assert.That(ComputerUseMission.ClicksAnOpener("input.visible.click", new JsonObject { ["label"] = "Guardar", ["index"] = 4 }, view), Is.False,
                "a menu entry that acts opens nothing");
            Assert.That(ComputerUseMission.ClicksAnOpener("input.key.press", new JsonObject { ["key"] = "alt" }, view), Is.False);
        });
    }

    // Ronda 20 P8: the search's proof on the character map as read in the r18 pass (v3-29, t-scroll-2).
    private static JsonArray SearchedFor(string query, params string[] appeared) =>
    [
        new JsonObject { ["operation"] = "input.visible.click", ["label"] = "Buscar:", ["ok"] = true },
        TypedInto(query, "Buscar:"),
        new JsonObject
        {
            ["operation"] = "input.key.press", ["key"] = "enter", ["ok"] = true,
            ["appeared"] = new JsonArray([.. appeared.Select(name => (JsonNode?)JsonValue.Create(name))]),
        },
    ];

    private static JsonObject CharacterMap(string searchValue, string status, params string[] lineB)
    {
        JsonObject view = View("""
            {"window": {"title": "Mapa de caracteres", "process": "charmap"},
             "controls": [
               {"i": 0, "kind": "Edit", "name": "Caracteres para copiar:", "value": ""},
               {"i": 6, "kind": "Document", "name": "Buscar:", "zone": "B"},
               {"i": 7, "kind": "Button", "name": "Restablecer", "zone": "BR"},
               {"i": 14, "kind": "Pane", "name": "Cuadrícula de caracteres", "zone": "C"},
               {"i": 18, "kind": "Text", "name": "Buscar:", "zone": "BL"}
             ],
             "text": {"TL": ["Mapa de caracteres", "Fuente: Arial"]}}
            """);
        if (searchValue.Length > 0)
        {
            ((JsonObject)view["controls"]![1]!)["value"] = searchValue;
        }

        ((JsonArray)view["controls"]!).Add(new JsonObject { ["i"] = 20, ["kind"] = "Text", ["name"] = status, ["zone"] = "B" });
        ((JsonObject)view["text"]!)["B"] = new JsonArray([.. lineB.Select(line => (JsonNode?)JsonValue.Create(line))]);
        return view;
    }

    [Test]
    public void ASearchThatSaysNoneIsAvailableOrOnlyEchoesTwiceIsNoResult()
    {
        const string check = "stepDone:input.text.type&stepDone:input.key.press:enter&text:copyright symbol";
        JsonArray steps = SearchedFor("copyright symbol", "restablecer", "no hay caracteres disponibles");
        // v3-29 as read: the OCR read the box twice and the window said nothing was found.
        JsonObject nothing = CharacterMap("", "No hay caracteres disponibles",
            "Unicode", "copyright symboll", "copyright symbol", "No hay caracteres disponibles");
        // The double echo alone (no line saying nothing was found) is still one place.
        JsonObject echoedTwice = CharacterMap("", "Unicode", "Unicode", "copyright symboll", "copyright symbol");
        // Counter-case: a line of the results besides the box is a result.
        JsonObject found = CharacterMap("", "U+00A9: Copyright symbol sign", "Unicode", "copyright symbol", "Todo",
            "U+00A9: copyright symbol sign");
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, nothing, steps, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.OnlyTheQueryShows("copyright symbol", echoedTwice, steps), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, echoedTwice, steps, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, found, steps, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.EchoLine("copyright symboll", "copyright symbol"), Is.True);
            Assert.That(ComputerUseSuccessCheck.EchoLine("q copyright symbol", "copyright symbol"), Is.True);
            Assert.That(ComputerUseSuccessCheck.EchoLine("u+00a9: copyright symbol sign", "copyright symbol"), Is.False);
        });
    }

    [Test]
    public void AThingsAvailableLineAndASearchThatFoundSomethingStayResults()
    {
        // Counter-cases: «Hay 3 actualizaciones disponibles» is no «nothing found»; Control Panel's search for «chrome»
        // finds «Google Chrome - Programas y características».
        JsonArray steps = SearchedFor("chrome");
        JsonObject panel = View("""
            {"window": {"title": "chrome - Programas", "process": "explorer"},
             "controls": [{"i": 0, "kind": "Edit", "name": "Buscar en Panel de control", "value": "chrome"},
                          {"i": 1, "kind": "Hyperlink", "name": "Desinstalar un programa"},
                          {"i": 2, "kind": "ListItem", "name": "Google Chrome"}],
             "text": {"C": ["Hay 3 actualizaciones disponibles", "Google Chrome - Programas y características"]}}
            """);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.OnlyTheQueryShows("chrome", panel, steps), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate(
                "stepDone:input.text.type&stepDone:input.key.press:enter&text:chrome", panel, steps, out _), Is.True);
        });
    }

    [Test]
    public void ASearchBoxDrawnAsADocumentMustStillHoldTheQueryWhenItSaysWhatItHolds()
    {
        JsonArray steps = SearchedFor("copyright symbol");
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.TypedQueryHeld("copyright symbol", CharacterMap("copyright symbol", "x"), steps), Is.True);
            Assert.That(ComputerUseSuccessCheck.TypedQueryHeld("copyright symbol", CharacterMap("otra cosa", "x"), steps), Is.False);
            // A Document that exposes no value says nothing either way.
            Assert.That(ComputerUseSuccessCheck.TypedQueryHeld("copyright symbol", CharacterMap("", "x"), steps), Is.True);
        });
    }

    [Test]
    public void AResultThatSaysTheQuerysWordsInAnotherOrderProvesTheSearch()
    {
        // t-scroll-2 as read: «omega mayúscula» found as «U+038F: Letra griega mayúscula Omega con tonos».
        const string check = "stepDone:input.text.type&stepDone:input.key.press:enter&text:omega mayuscula";
        const string status = "U+038F: Letra griega mayúscula Omega con tonos";
        JsonObject view = CharacterMap("", status, "Unicode", "omega mayúsculal", "Ll+038F: Letra griega mayúscula Omega", status);
        JsonArray found = SearchedFor("omega mayúscula", "u+038f: letra griega mayuscula omega con tonos", "restablecer");
        // Counter-cases: a name with only part of the words (a font list's «Omega»), the box's echo read again, and a
        // result that did not appear after the submit.
        JsonObject partial = CharacterMap("", "Omega", "Unicode", "omega mayúscula", "Omega");
        JsonArray partialSteps = SearchedFor("omega mayúscula", "omega");
        JsonObject echo = CharacterMap("", "Unicode", "Unicode", "omega mayúsculal", "omega mayúscula");
        JsonArray echoSteps = SearchedFor("omega mayúscula", "omega mayuscula");
        JsonArray notAfterSubmit = SearchedFor("omega mayúscula");
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, view, found, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, partial, partialSteps, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, echo, echoSteps, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, view, notAfterSubmit, out _), Is.False);
            // Without a step done the atom reads the screen as before (contiguous words only).
            Assert.That(ComputerUseSuccessCheck.Evaluate("text:omega mayuscula", partial, partialSteps, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("text:mayuscula omega", view, found, out _), Is.True);
        });
    }

    private static JsonObject Terminal(string firstTabs, params (string Name, bool Selected)[] tabs)
    {
        var controls = new JsonArray();
        foreach ((string name, bool selected) in tabs)
        {
            controls.Add(new JsonObject { ["kind"] = "TabItem", ["name"] = name, ["state"] = selected ? "selected" : "" });
        }

        controls.Add(new JsonObject { ["kind"] = "SplitButton", ["name"] = "Nueva pestaña" });
        return new JsonObject
        {
            ["window"] = new JsonObject { ["title"] = tabs.FirstOrDefault(tab => tab.Selected).Name ?? "Terminal", ["process"] = "terminal" },
            ["controls"] = controls,
            ["subgoalFirstText"] = "windows powershell\n",
            ["subgoalFirstTabs"] = new JsonArray([.. firstTabs.Split('|', StringSplitOptions.RemoveEmptyEntries)
                .Select(name => (JsonNode?)JsonValue.Create(name))]),
        };
    }

    [Test]
    public void ANewTabOfAKindIsOneBornInTheSubgoalAndChosen()
    {
        const string check = "born:simbolo del sistema|born:command prompt";
        Assert.Multiple(() =>
        {
            // v3-37: a tab of the kind born and chosen.
            Assert.That(ComputerUseSuccessCheck.Evaluate(check,
                Terminal("windows powershell", ("Windows PowerShell", false), ("Símbolo del sistema", true)), [], out _), Is.True);
            // The tab of another kind the split button's main part opened is no tab of the kind.
            Assert.That(ComputerUseSuccessCheck.Evaluate(check,
                Terminal("windows powershell", ("Windows PowerShell", false), ("Windows PowerShell", true)), [], out _), Is.False);
            // Counter-case: one of the kind already open is no new one, until another is born.
            Assert.That(ComputerUseSuccessCheck.Evaluate(check,
                Terminal("simbolo del sistema", ("Símbolo del sistema", true)), [], out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate(check,
                Terminal("simbolo del sistema", ("Símbolo del sistema", false), ("Símbolo del sistema", true)), [], out _), Is.True);
            // Born but not chosen.
            Assert.That(ComputerUseSuccessCheck.Evaluate(check,
                Terminal("windows powershell", ("Windows PowerShell", true), ("Símbolo del sistema", false)), [], out _), Is.False);
            // A window of the kind that came during the mission, when the first look's title was another.
            Assert.That(ComputerUseSuccessCheck.Evaluate("born:incognito", View("""
                {"window": {"title": "Nueva pestaña - Incognito", "process": "browser", "born": true, "hwnd": 200}, "controls": [],
                 "subgoalFirstText": "nueva pestana - navegador\n", "subgoalFirstWindows": [100]}
                """), [], out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("born:incognito", View("""
                {"window": {"title": "Nueva pestaña - Incognito", "process": "browser", "hwnd": 200}, "controls": [],
                 "subgoalFirstText": "nueva pestana - navegador\n", "subgoalFirstWindows": [100]}
                """), [], out _), Is.False);
        });
    }

    [Test]
    public void ATabRenamedByGoingSomewhereOrAWindowKnownBeforeTheFirstLookIsNoneBorn()
    {
        // Review 1 of r20 P8 (finding 1): «abrí una pestaña nueva de youtube», the address typed into the person's
        // «Google» tab, which now reads «YouTube»: no tab was born.
        static JsonObject Browser(string firstTabs, params (string Name, bool Selected)[] tabs)
        {
            JsonObject view = Terminal(firstTabs, tabs);
            view["subgoalFirstText"] = "google - navegador\n";
            return view;
        }

        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("born:youtube", Browser("google", ("YouTube", true)), [], out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("born:youtube",
                Browser("google|wikipedia", ("YouTube", true), ("Wikipedia", false)), [], out _), Is.False);
            // Counter-case: the tab beside the person's, born and chosen.
            Assert.That(ComputerUseSuccessCheck.Evaluate("born:youtube",
                Browser("google", ("Google", false), ("YouTube", true)), [], out _), Is.True);
            // A window born earlier in the mission (known at the sub-goal's first look) is no window born in it.
            Assert.That(ComputerUseSuccessCheck.Evaluate("born:incognito", View("""
                {"window": {"title": "Nueva pestaña - Incognito", "process": "browser", "born": true, "hwnd": 200}, "controls": [],
                 "subgoalFirstText": "nueva pestana - navegador\n", "subgoalFirstWindows": [100, 200]}
                """), [], out _), Is.False);
            // Nor one read by a look that does not know what the first look knew.
            Assert.That(ComputerUseSuccessCheck.Evaluate("born:incognito", View("""
                {"window": {"title": "Nueva pestaña - Incognito", "process": "browser", "born": true, "hwnd": 200}, "controls": [],
                 "subgoalFirstText": "nueva pestana - navegador\n"}
                """), [], out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.KnownWindows(new JsonArray(7L), View("""
                {"window": {"title": "x", "hwnd": 9}}
                """)).Select(node => (long?)node).ToArray(), Is.EqualTo(new long?[] { 7, 9 }));
        });
    }

    [Test]
    public void ATabOrWindowBornOnASearchForTheKindIsNoneOfTheKind()
    {
        // Review 3 of r20 P8 (blocker 1): Edge, Ctrl+T (or Ctrl+N), «youtube» typed into the address bar and entered:
        // Bing opens «youtube - Búsqueda», chosen, on bing.com/search. title: and control: refuse it; born: too.
        static JsonArray Typed(string text) =>
        [
            new JsonObject { ["operation"] = "input.key.press", ["key"] = "ctrl+t", ["ok"] = true },
            TypedInto(text, "Barra de direcciones y búsqueda"),
            new JsonObject { ["operation"] = "input.key.press", ["key"] = "enter", ["ok"] = true },
        ];
        static JsonObject Tab(string name, string address)
        {
            JsonObject view = Terminal("google", ("Google", false), (name, true));
            view["window"] = new JsonObject
            {
                ["title"] = name + " - Microsoft Edge",
                ["process"] = "msedge",
                ["hwnd"] = 100,
            };
            view["subgoalFirstText"] = "google - microsoft edge\n";
            ((JsonArray)view["controls"]!).Add(new JsonObject
            {
                ["kind"] = "Edit",
                ["name"] = "Barra de direcciones y búsqueda",
                ["value"] = address,
            });
            return view;
        }

        static JsonObject Window(string title, string address) => View($$"""
            {"window": {"title": "{{title}}", "process": "msedge", "born": true, "hwnd": 200},
             "controls": [{"kind": "Edit", "name": "Barra de direcciones y búsqueda", "value": "{{address}}"}],
             "subgoalFirstText": "google - microsoft edge\n", "subgoalFirstWindows": [100]}
            """);

        const string search = "https://www.bing.com/search?q=youtube&form=QBLH";
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("born:youtube",
                Tab("youtube - Búsqueda", search), Typed("youtube"), out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("born:youtube",
                Window("youtube - Búsqueda - Microsoft Edge", search), Typed("youtube"), out _), Is.False);
            // A results page is no born container of the kind whatever was typed (a suggestion pressed, no record).
            Assert.That(ComputerUseSuccessCheck.Evaluate("born:youtube",
                Tab("youtube - Búsqueda", search), [], out _), Is.False);
            // Unless the goal asks for a search's results.
            Assert.That(ComputerUseSuccessCheck.Evaluate("born:youtube&stepDone:input.key.press:enter",
                Tab("youtube - Búsqueda", search), Typed("youtube"), out _), Is.True);
            // Counter-cases: the address sent leads to the place, in a tab or a window born.
            Assert.That(ComputerUseSuccessCheck.Evaluate("born:youtube",
                Tab("YouTube", "https://www.youtube.com/"), Typed("youtube.com"), out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("born:youtube",
                Window("YouTube - Microsoft Edge", "https://www.youtube.com/"), Typed("youtube.com"), out _), Is.True);
        });
    }

    [Test]
    public void ASearchInAnyOrderIsNoResultWhereTheWindowSaysNothingWasFoundOrOnlyItsTitleRepeatsTheQuery()
    {
        // Review 1 of r20 P8 (finding 2): Explorer's search for «informe mensual» that found nothing.
        const string check = "stepDone:input.text.type&stepDone:input.key.press:enter&text:informe mensual";
        const string title = "informe mensual - Resultados de la búsqueda en Documentos";
        static JsonArray Steps(params string[] appeared) =>
        [
            TypedInto("informe mensual", "Buscar en Documentos"),
            new JsonObject
            {
                ["operation"] = "input.key.press", ["key"] = "enter", ["ok"] = true,
                ["appeared"] = new JsonArray([.. appeared.Select(name => (JsonNode?)JsonValue.Create(name))]),
            },
        ];
        static JsonObject Explorer(params JsonObject[] more)
        {
            var controls = new JsonArray(
                new JsonObject { ["kind"] = "Edit", ["name"] = "Buscar en Documentos", ["value"] = "informe mensual" },
                new JsonObject { ["kind"] = "Window", ["name"] = title });
            foreach (JsonObject control in more)
            {
                controls.Add(control);
            }

            return new JsonObject
            {
                ["window"] = new JsonObject { ["title"] = title, ["process"] = "explorer" },
                ["controls"] = controls,
            };
        }

        string folded = "informe mensual - resultados de la busqueda en documentos";
        JsonObject nothing = Explorer(new JsonObject { ["kind"] = "Text", ["name"] = "Ningún elemento coincide con el criterio de búsqueda." });
        JsonObject titleOnly = Explorer();
        JsonObject found = Explorer(new JsonObject { ["kind"] = "ListItem", ["name"] = "Informe de gastos mensual.docx" });
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.ResultInAnyOrder("informe mensual", nothing, Steps(folded)), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, nothing, Steps(folded), out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.ResultInAnyOrder("informe mensual", titleOnly, Steps(folded)), Is.False);
            // Counter-case: a file of the results that holds the query's words in another order.
            Assert.That(ComputerUseSuccessCheck.ResultInAnyOrder("informe mensual", found,
                Steps(folded, "informe de gastos mensual.docx")), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, found, Steps(folded, "informe de gastos mensual.docx"), out _), Is.True);
        });
    }

    // Ronda 22 (pasada r18, t4-c06 «crea un blank workbook», t4-c13 «DOCUMENTO DE SOLO LECTURA» cited as the bold
    // applied): a citation new on screen that relates to nothing the goal says proves nothing. Estabilización R16: that
    // judge is the mind's (cu_evidence._unrelated_evidence; the App's twin Unrelated and EvidenceRefusal went, their
    // cases in tests/test_cu_estab_r16_juez_unico.py and tests/test_cu_v3_hecho_solo_con_prueba.py). The App keeps the
    // stems its checks of a place read: five letters, an alias of data relating «Libro en blanco» to «blank workbook».
    [Test]
    public void TheProofStemsReadTheGoalsWordsWithTheirAliases()
    {
        Assert.That(ComputerUseSuccessCheck.ProofStems("crea un blank workbook",
            ["crea", "un"], [new JsonArray("blanco", "blank"), new JsonArray("libro", "workbook")]),
            Is.EquivalentTo(new[] { "blanc", "libro" }));
    }

    // ------------------------------------------- pasada r18: what the act itself chose or typed proves no arrival nor datum

    // A click receipt as the provider returns it, with what the look after it marked (broughtNew, appeared).
    private static JsonObject ClickReceipt(
        int step, string label, string kind, bool surfaceChanged = false, bool? broughtNew = false, bool selected = true,
        string? windowTitle = null) => new()
        {
            ["step"] = step,
            ["operation"] = "input.visible.click",
            ["label"] = label,
            ["name"] = label,
            ["kind"] = kind,
            ["ok"] = true,
            ["method"] = selected ? "select" : "invoke",
            ["surfaceChanged"] = surfaceChanged,
            ["selected"] = selected,
            ["changed"] = true,
            ["broughtNew"] = broughtNew,
            ["appeared"] = new JsonArray(),
            ["windowTitle"] = windowTitle,
        };

    private static JsonObject AppOpened(int step) => new()
    {
        ["step"] = step,
        ["operation"] = "app.open",
        ["ok"] = true,
        ["changed"] = true,
    };

    // v3-50 «en 7-zip abrí prueba.zip»: the procedure's click on «prueba.zip» (trace seq 51–58) selected the entry of the
    // one-column list (every entry in zone L) by its pattern: receipt method=select, surfaceChanged=false, appeared=[];
    // the path stayed the folder's (UIA after: «D:\Perfil\Documentos\baxy-prueba-v3\», prueba.zip selected).
    private const string SevenZipFolder = """
        {"window": {"title": "D:\\Perfil\\Documentos\\baxy-prueba-v3\\", "process": "7zFM", "requested": true},
         "controls": [
           {"i": 0, "kind": "ComboBox", "name": "", "value": "D:\\Perfil\\Documentos\\baxy-prueba-v3\\", "zone": "T"},
           {"i": 1, "kind": "ListItem", "name": "archivo", "state": "", "zone": "L", "rect": {"x": 8, "y": 120, "w": 220, "h": 18}},
           {"i": 2, "kind": "ListItem", "name": "foto.png", "state": "", "zone": "L", "rect": {"x": 8, "y": 138, "w": 220, "h": 18}},
           {"i": 3, "kind": "ListItem", "name": "lista.txt", "state": "", "zone": "L", "rect": {"x": 8, "y": 156, "w": 220, "h": 18}},
           {"i": 4, "kind": "ListItem", "name": "notas.txt", "state": "", "zone": "L", "rect": {"x": 8, "y": 174, "w": 220, "h": 18}},
           {"i": 5, "kind": "ListItem", "name": "paisaje.jpg", "state": "", "zone": "L", "rect": {"x": 8, "y": 192, "w": 220, "h": 18}},
           {"i": 6, "kind": "ListItem", "name": "prueba.png", "state": "", "zone": "L", "rect": {"x": 8, "y": 210, "w": 220, "h": 18}},
           {"i": 7, "kind": "ListItem", "name": "prueba.zip", "state": "selected", "zone": "L", "rect": {"x": 8, "y": 228, "w": 220, "h": 18}}
         ],
         "selectedAtStart": []}
        """;

    [Test]
    public void V3_50_AnEntryOnlySelectedInAOneColumnListIsNotWhereTheWindowIs()
    {
        const string Term = "control:==prueba.zip:current";
        JsonObject folder = View(SevenZipFolder);
        JsonArray selectedOnly = [AppOpened(1), ClickReceipt(2, "prueba.zip", "ListItem")];
        // Counter-case: a double click that opened the archive retitles the window and lists its entries.
        JsonObject inside = View(SevenZipFolder);
        inside["window"]!["title"] = "D:\\Perfil\\Documentos\\baxy-prueba-v3\\prueba.zip\\";
        JsonArray openedIt = [AppOpened(1), ClickReceipt(2, "prueba.zip", "ListItem", broughtNew: true,
            windowTitle: "D:\\Perfil\\Documentos\\baxy-prueba-v3\\prueba.zip\\")];
        JsonObject unrecorded = View(SevenZipFolder);
        unrecorded.Remove("selectedAtStart");
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate(Term, folder, selectedOnly, out string? by), Is.False, by);
            Assert.That(ComputerUseSuccessCheck.Evaluate(Term, unrecorded, selectedOnly, out _), Is.False,
                "the click that chose it moved nothing, whatever the first look kept");
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:==prueba.zip:selected", folder, selectedOnly, out _), Is.True,
                "choosing the entry is still «selected»");
            Assert.That(ComputerUseSuccessCheck.Evaluate(Term, inside, openedIt, out _), Is.True);
        });
    }

    // v3-52 «in obs open settings, go to the video section»: «Vídeo» selected by the click's pattern (trace seq 74–82)
    // while the page beside the list still showed General (UIA after: Idioma, Actualizar canal…).
    private const string SettingsList = """
        {"window": {"title": "Ajustes", "process": "obs64", "requested": true},
         "controls": [
           {"i": 0, "kind": "ListItem", "name": "General", "state": "", "zone": "L"},
           {"i": 1, "kind": "ListItem", "name": "Emisión", "state": "", "zone": "L"},
           {"i": 2, "kind": "ListItem", "name": "Vídeo", "state": "selected", "zone": "L"},
           {"i": 3, "kind": "ComboBox", "name": "Idioma", "value": "Español", "zone": "C"}
         ],
         "selectedAtStart": ["general"]}
        """;

    [Test]
    public void V3_52_ASectionSelectedWithoutThePageChangingIsNotReached()
    {
        JsonObject view = View(SettingsList);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:video:current", view,
                [ClickReceipt(3, "Vídeo", "ListItem")], out string? by), Is.False, by);
            // Counter-cases: the click whose look after it showed the page's new controls, or whose receipt saw the
            // surface change, reached it.
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:video:current", view,
                [ClickReceipt(3, "Vídeo", "ListItem", broughtNew: true)], out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:video:current", view,
                [ClickReceipt(3, "Vídeo", "ListItem", surfaceChanged: true, broughtNew: null)], out _), Is.True);
        });
    }

    // Counter-case: a settings window's side list, «Bluetooth» pressed and its page drawn, stays current.
    [Test]
    public void ASettingsSectionClickedThatChangedThePageStaysCurrent()
    {
        JsonObject settings = View("""
            {"window": {"title": "Configuración", "process": "systemsettings", "requested": true},
             "controls": [
               {"i": 0, "kind": "ListItem", "name": "Sistema", "state": "", "zone": "L"},
               {"i": 1, "kind": "ListItem", "name": "Bluetooth y dispositivos", "state": "selected", "zone": "L"},
               {"i": 2, "kind": "Button", "name": "Agregar dispositivo", "state": "", "zone": "C"}
             ],
             "selectedAtStart": ["sistema"]}
            """);
        JsonArray appeared = [ClickReceipt(1, "Bluetooth y dispositivos", "ListItem", broughtNew: null)];
        ((JsonObject)appeared[0]!)["appeared"] = new JsonArray("agregar dispositivo");
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:bluetooth y dispositivos:current", settings,
                [ClickReceipt(1, "Bluetooth y dispositivos", "ListItem", surfaceChanged: true)], out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:bluetooth y dispositivos:current", settings, appeared, out _), Is.True);
            // Selected with no act of the sub-goal that moved the window: not where it is.
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:bluetooth y dispositivos:current", settings, [AppOpened(1)], out _), Is.False);
        });
    }

    // v3-31 counter-case: «Ventana» was selected at the sub-goal's first look; it closes without any act.
    [Test]
    public void V3_31_AnEntrySelectedAtTheFirstLookIsWhereTheWindowIs()
    {
        JsonObject view = View("""
            {"window": {"title": "Personalización", "process": "app", "requested": true},
             "controls": [
               {"i": 0, "kind": "TreeItem", "name": "Ventana", "state": "selected", "zone": "L"},
               {"i": 1, "kind": "TreeItem", "name": "Fuentes", "state": "", "zone": "L"}
             ],
             "selectedAtStart": ["ventana"]}
            """);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:ventana:current", view, [], out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:ventana:current", view, [AppOpened(1)], out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:ventana:current", view,
                [AppOpened(1), ClickReceipt(2, "Ventana", "TreeItem")], out _), Is.True, "clicked again where it already was");
        });
    }

    private static readonly string Asked = "ir a la pagina" + OperationFloor.QuestionMark + "decime el dato";

    // v3-46 «andá a Componentes > Pantalla y decime qué tarjeta de video tengo»: the look 176 ms after the click on
    // «Pantalla» (trace seq 72→74), before the table was drawn: its only «datum» was the entry the click chose.
    [Test]
    public void V3_46_TheTreeEntryTheActChoseIsNoDatum()
    {
        JsonObject early = View("""
            {"window": {"title": "Información del sistema", "process": "msinfo32", "requested": true},
             "controls": [
               {"i": 0, "kind": "TreeItem", "name": "Componentes", "state": "expanded", "zone": "L"},
               {"i": 1, "kind": "TreeItem", "name": "Pantalla", "state": "selected", "zone": "L"},
               {"i": 2, "kind": "HeaderItem", "name": "Elemento", "state": "", "zone": "C"}
             ]}
            """);
        JsonObject drawn = View(early.ToJsonString());
        ((JsonArray)drawn["controls"]!).Add((JsonNode)new JsonObject
        {
            ["i"] = 3,
            ["kind"] = "DataItem",
            ["name"] = "Nombre",
            ["value"] = "NVIDIA GeForce RTX 3060 Laptop GPU",
            ["zone"] = "C",
        });
        JsonArray clicked = [ClickReceipt(1, "Pantalla", "TreeItem")];
        const string By = "stepDone:input.visible.click:pantalla";
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.QuestionDatumUnread(Asked, By, early, clicked), Is.True);
            Assert.That(ComputerUseMission.QuestionDatumUnread(Asked, By, drawn, clicked), Is.False, "the table drawn holds the datum");
            Assert.That(ComputerUseMission.QuestionDatumUnread("ir a la pagina", By, early, clicked), Is.False, "no question");
        });
    }

    // v3-61 «en seguridad de windows decime cuándo fue el último examen»: the model pressed «Historial de protección» by
    // mistake (req 7, i=13) and the identity term closed the question on that entry, the only chosen thing on screen.
    [Test]
    public void V3_61_TheNavigationEntryTheActPressedIsNoAnswer()
    {
        JsonObject view = View("""
            {"window": {"title": "Seguridad de Windows", "process": "SecHealthUI", "requested": true},
             "controls": [
               {"i": 0, "kind": "ListItem", "name": "Inicio", "state": "", "zone": "L"},
               {"i": 1, "kind": "ListItem", "name": "Protección contra virus y amenazas", "state": "", "zone": "L"},
               {"i": 2, "kind": "ListItem", "name": "Historial de protección", "state": "selected", "zone": "L"}
             ]}
            """);
        JsonArray steps =
        [
            new JsonObject
            {
                ["step"] = 1, ["operation"] = "input.visible.click", ["label"] = "Protección contra virus y amenazas",
                ["ok"] = false, ["error"] = "visible_button_ambiguous",
            },
            ClickReceipt(2, "Historial de protección", "ListItem"),
        ];
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.QuestionDatumUnread(Asked, "title:seguridad de windows", view, steps), Is.True);
            // Without the sub-goal's steps the chosen entry counts as the datum, as before this pasada.
            Assert.That(ComputerUseMission.QuestionDatumUnread(Asked, "title:seguridad de windows", view), Is.False);
        });
    }

    // v3-43 counter-case: «Equilibrado» was chosen before and the act pressed «Opciones de energía»: it stays the datum.
    // «andá a Hora e idioma y decime la zona horaria»: the entry pressed is no datum, the zone's value is.
    [Test]
    public void AChoiceTheActDidNotMakeAndAValueOfThePageStayData()
    {
        JsonObject power = View("""
            {"window": {"title": "Opciones de energía", "process": "explorer", "requested": true},
             "controls": [
               {"i": 0, "kind": "Hyperlink", "name": "Opciones de energía", "state": "", "zone": "TL"},
               {"i": 1, "kind": "RadioButton", "name": "Equilibrado (recomendado)", "state": "selected", "zone": "C"}
             ]}
            """);
        JsonObject time = View("""
            {"window": {"title": "Configuración", "process": "systemsettings", "requested": true},
             "controls": [
               {"i": 0, "kind": "ListItem", "name": "Hora e idioma", "state": "selected", "zone": "L"},
               {"i": 1, "kind": "ComboBox", "name": "Zona horaria", "value": "(UTC-04:00) Santiago", "zone": "C"}
             ]}
            """);
        JsonObject bare = View("""
            {"window": {"title": "Configuración", "process": "systemsettings", "requested": true},
             "controls": [{"i": 0, "kind": "ListItem", "name": "Hora e idioma", "state": "selected", "zone": "L"}]}
            """);
        JsonArray pressed = [ClickReceipt(1, "Hora e idioma", "ListItem", broughtNew: true)];
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.QuestionDatumUnread(Asked, "stepDone:input.visible.click:opciones de energia", power,
                [ClickReceipt(1, "Opciones de energía", "Hyperlink", surfaceChanged: true, selected: false)]), Is.False);
            Assert.That(ComputerUseMission.QuestionDatumUnread(Asked, "title:configuracion", time, pressed), Is.False);
            Assert.That(ComputerUseMission.QuestionDatumUnread(Asked, "title:configuracion", bare, pressed), Is.True);
        });
    }

    // The value of a field the sub-goal wrote repeats the typing; another value of the page is a datum.
    [Test]
    public void AFieldHoldingWhatTheSubgoalTypedIsNoDatum()
    {
        JsonObject view = View("""
            {"window": {"title": "Panel de control", "process": "explorer", "requested": true},
             "controls": [{"i": 0, "kind": "Edit", "name": "Cuadro de búsqueda", "value": "chrome", "zone": "TR"}]}
            """);
        JsonArray typed =
        [
            new JsonObject
            {
                ["step"] = 1, ["operation"] = "input.text.type", ["text"] = "chrome", ["into"] = "Cuadro de búsqueda",
                ["ok"] = true, ["changed"] = true,
            },
        ];
        JsonObject withResult = View(view.ToJsonString());
        ((JsonArray)withResult["controls"]!).Add((JsonNode)new JsonObject
        {
            ["i"] = 1,
            ["kind"] = "Text",
            ["name"] = "Versión",
            ["value"] = "141.0",
            ["zone"] = "C",
        });
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.QuestionDatumUnread(Asked, "title:panel de control", view, typed), Is.True);
            Assert.That(ComputerUseMission.QuestionDatumUnread(Asked, "title:panel de control", withResult, typed), Is.False);
            Assert.That(ComputerUseSuccessCheck.EchoesTyping("chrome", typed), Is.True);
            Assert.That(ComputerUseSuccessCheck.EchoesTyping("buscar chrome ahora", typed), Is.True);
            Assert.That(ComputerUseSuccessCheck.EchoesTyping("chromecast", typed), Is.False, "whole words only");
        });
    }

    // v3-42 sub-goal 1 «ir a programas y caracteristicas»: the name typed into the Control Panel's search retitled the
    // window at once; then a verified click on the link «Programas y características» (Hyperlink, ok, surfaceChanged,
    // broughtNew) opened the page. The title that names the place now is the arrival, not the box's echo.
    [Test]
    public void V3_42_AVerifiedClickOnThePlaceByItsNameEndsTheTitlesEcho()
    {
        const string Typed = "programas y caracteristicas - Todos los elementos de Panel de control";
        static JsonArray Steps(bool clicked)
        {
            JsonArray steps =
            [
                new JsonObject
                {
                    ["step"] = 1, ["operation"] = "input.visible.click", ["label"] = "Cuadro de búsqueda", ["name"] = "Cuadro de búsqueda",
                    ["kind"] = "Edit", ["ok"] = true, ["surfaceChanged"] = true,
                },
                new JsonObject
                {
                    ["step"] = 2, ["operation"] = "input.text.type", ["text"] = "programas y caracteristicas",
                    ["into"] = "Cuadro de búsqueda", ["ok"] = true, ["changed"] = true, ["windowTitle"] = Typed,
                },
            ];
            if (clicked)
            {
                steps.Add((JsonNode)ClickReceipt(3, "Programas y características", "Hyperlink", surfaceChanged: true, broughtNew: true, selected: false));
            }

            return steps;
        }

        JsonObject page = View("""
            {"window": {"title": "Programas y características", "process": "explorer", "requested": true},
             "controls": [{"i": 0, "kind": "Edit", "name": "Cuadro de búsqueda", "value": "", "zone": "TR"}]}
            """);
        JsonObject echoing = View(page.ToJsonString());
        echoing["window"]!["title"] = Typed;
        const string Check = "title:programas y caracteristicas";
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate(Check, page, Steps(clicked: true), out string? by), Is.True);
            Assert.That(by, Is.EqualTo(Check));
            Assert.That(ComputerUseSuccessCheck.TitleEchoedTheTyping("programas y caracteristicas", Steps(clicked: true), page), Is.False);
            // The same title as the typing's, but the click on the place by its whole name changed the surface.
            Assert.That(ComputerUseSuccessCheck.TitleEchoedTheTyping("programas y caracteristicas", Steps(clicked: true), echoing), Is.False);
            // Counter-case: no click, the window still bears the title the typing gave it.
            Assert.That(ComputerUseSuccessCheck.TitleEchoedTheTyping("programas y caracteristicas", Steps(clicked: false), echoing), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate(Check, echoing, Steps(clicked: false), out _), Is.False);
        });
    }

    // v3-42 sub-goal 2 counter-case: «chrome» retitled the window «chrome - Programas» and Enter changed nothing; the
    // title is still the typing's, so the r9 veto stands. v3-44: «devices and printers - Panel de control» over «Ningún
    // elemento coincide…»: no click on the place, still the echo.
    [Test]
    public void TheTitleStillAsTheTypingLeftItStaysTheEcho()
    {
        JsonArray chrome =
        [
            new JsonObject
            {
                ["step"] = 1, ["operation"] = "input.text.type", ["text"] = "chrome", ["into"] = "Cuadro de búsqueda", ["ok"] = true,
                ["changed"] = true, ["windowTitle"] = "chrome - Programas",
            },
            new JsonObject { ["step"] = 2, ["operation"] = "input.key.press", ["key"] = "enter", ["ok"] = true, ["changed"] = true },
        ];
        JsonObject nothing = View(ComputerUseRealViews.V342SearchedNothing);
        JsonArray devices =
        [
            new JsonObject
            {
                ["step"] = 1, ["operation"] = "input.text.type", ["text"] = "devices and printers", ["into"] = "Cuadro de búsqueda",
                ["ok"] = true, ["changed"] = true, ["windowTitle"] = "devices and printers - Panel de control",
            },
            new JsonObject { ["step"] = 2, ["operation"] = "input.key.press", ["key"] = "enter", ["ok"] = true, ["changed"] = true },
        ];
        JsonObject unmatched = View("""
            {"window": {"title": "devices and printers - Panel de control", "process": "explorer", "requested": true},
             "controls": [{"i": 0, "kind": "Edit", "name": "Cuadro de búsqueda", "value": "devices and printers", "zone": "TR"}],
             "text": {"C": ["Ningún elemento coincide con el criterio de búsqueda."]}}
            """);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.TitleEchoedTheTyping("chrome", chrome, nothing), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate(ComputerUseRealViews.V342Check2, nothing, chrome, out string? by), Is.False, by);
            Assert.That(ComputerUseSuccessCheck.TitleEchoedTheTyping("devices and printers", devices, unmatched), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("title:devices and printers", unmatched, devices, out _), Is.False);
        });
    }

    // ------------------------------------------- review 1 of ronda 20b: the act that chose the entry, not any act before it

    // A key or a typing receipt, with the title it reread and what the look after it showed new (appeared).
    private static JsonObject KeyReceipt(int step, string operation, string? key, string? text, string windowTitle,
        params string[] appeared) => new()
        {
            ["step"] = step,
            ["operation"] = operation,
            ["key"] = key,
            ["text"] = text,
            ["ok"] = true,
            ["changed"] = true,
            ["surfaceChanged"] = false,
            ["windowTitle"] = windowTitle,
            ["appeared"] = new JsonArray(appeared.Select(name => (JsonNode?)name).ToArray()),
        };

    private static JsonObject SelectedBefore(params string[][] perStep)
    {
        var record = new JsonObject();
        for (int index = 0; index < perStep.Length; index++)
        {
            record[(index + 1).ToString(System.Globalization.CultureInfo.InvariantCulture)] =
                new JsonArray(perStep[index].Select(name => (JsonNode?)name).ToArray());
        }

        return record;
    }

    // Variant of v3-50 driven by the keyboard in a one-column file manager: the path typed, Enter that opened the folder
    // (title and entries changed), then End that only selected the archive. Enter moved the window, but the act that
    // chose «prueba.zip» was End, which moved nothing: no «abrí prueba.zip».
    [Test]
    public void AnEntrySelectedByAKeyAfterAnotherActMovedTheWindowIsNotReached()
    {
        const string Term = "control:==prueba.zip:current";
        JsonObject folder = View("""
            {"window": {"title": "D:\\P\\baxy\\", "process": "filemanager", "requested": true},
             "controls": [
               {"i": 0, "kind": "ListItem", "name": "notas.txt", "state": "", "zone": "L"},
               {"i": 1, "kind": "ListItem", "name": "prueba.zip", "state": "selected", "zone": "L"}
             ],
             "selectedAtStart": []}
            """);
        JsonArray steps =
        [
            KeyReceipt(1, "input.text.type", null, @"D:\P\baxy", @"D:\P\"),
            KeyReceipt(2, "input.key.press", "enter", null, @"D:\P\baxy\", "notas.txt", "prueba.zip"),
            KeyReceipt(3, "input.key.press", "end", null, @"D:\P\baxy\"),
        ];
        JsonObject recorded = folder.DeepClone().AsObject();
        recorded["selectedBeforeClick"] = SelectedBefore([], [], []);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate(Term, recorded, steps, out string? by), Is.False, by);
            Assert.That(ComputerUseSuccessCheck.Evaluate(Term, folder, steps, out _), Is.False,
                "without the record, the last act may have chosen it");
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:==prueba.zip:selected", recorded, steps, out _), Is.True,
                "choosing the entry is still «selected»");
        });
    }

    // Counter-cases: the key that chose a section of a settings list and drew its page, or a later Enter on the entry
    // the arrow selected that drew it, reached it; the arrow alone did not.
    [Test]
    public void AnEntryChosenByAKeyThatMovedTheWindowIsReached()
    {
        JsonObject view = View(SettingsList);
        JsonArray drawn = [KeyReceipt(1, "input.key.press", "down", null, "Ajustes", "resolucion base")];
        JsonArray arrowOnly = [KeyReceipt(1, "input.key.press", "down", null, "Ajustes")];
        JsonArray thenEnter = [KeyReceipt(1, "input.key.press", "down", null, "Ajustes"),
            KeyReceipt(2, "input.key.press", "enter", null, "Ajustes", "resolucion base")];
        JsonObject one = view.DeepClone().AsObject();
        one["selectedBeforeClick"] = SelectedBefore(["general"]);
        JsonObject two = view.DeepClone().AsObject();
        two["selectedBeforeClick"] = SelectedBefore(["general"], ["video"]);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:video:current", one, drawn, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:video:current", one, arrowOnly, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:video:current", two, thenEnter, out _), Is.True);
        });
    }

    // The section's page was drawn by the first click; the model pressed the entry again and that click changed nothing.
    // The click that chose it is the first one: the window is there.
    [Test]
    public void ASecondClickOnTheEntryAlreadyReachedTakesNothingBack()
    {
        JsonObject view = View(SettingsList);
        JsonArray twice =
        [
            ClickReceipt(1, "Vídeo", "ListItem", surfaceChanged: true, broughtNew: true),
            ClickReceipt(2, "Vídeo", "ListItem", surfaceChanged: false, broughtNew: false),
        ];
        JsonObject recorded = view.DeepClone().AsObject();
        recorded["selectedBeforeClick"] = SelectedBefore(["general"], ["video"]);
        // Counter-cases: two presses that never drew the page; and back to General in between, then a press on «Vídeo»
        // that only selected it (the first arrival was undone, the last choice moved nothing).
        JsonArray neither =
        [
            ClickReceipt(1, "Vídeo", "ListItem"),
            ClickReceipt(2, "Vídeo", "ListItem"),
        ];
        JsonArray backAndAgain =
        [
            ClickReceipt(1, "Vídeo", "ListItem", surfaceChanged: true, broughtNew: true),
            ClickReceipt(2, "General", "ListItem", surfaceChanged: true, broughtNew: true),
            ClickReceipt(3, "Vídeo", "ListItem"),
        ];
        JsonObject undone = view.DeepClone().AsObject();
        undone["selectedBeforeClick"] = SelectedBefore(["general"], ["video"], ["general"]);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:video:current", recorded, twice, out string? by), Is.True, by);
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:video:current", view, twice, out _), Is.True, "without the record");
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:video:current", view, neither, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("control:video:current", undone, backAndAgain, out _), Is.False);
        });
    }

    // ------------------------------------------- revision 2 of ronda 20b: a menu opened on the entry is no arrival

    // The context menu a click or a key opened over the one-column list: its entries appeared, the path stayed.
    private static JsonObject FolderWithMenu()
    {
        JsonObject view = View(SevenZipFolder);
        var controls = (JsonArray)view["controls"]!;
        controls.Add((JsonNode)new JsonObject { ["i"] = 8, ["kind"] = "Menu", ["name"] = "Contexto", ["zone"] = "C" });
        controls.Add((JsonNode)new JsonObject { ["i"] = 9, ["kind"] = "MenuItem", ["name"] = "Abrir", ["zone"] = "C" });
        controls.Add((JsonNode)new JsonObject { ["i"] = 10, ["kind"] = "MenuItem", ["name"] = "Abrir dentro", ["zone"] = "C" });
        return view;
    }

    private static JsonObject MenuClick(int step, string label)
    {
        JsonObject click = ClickReceipt(step, label, "ListItem", surfaceChanged: true);
        click["manner"] = "menu";
        click["appeared"] = new JsonArray("contexto", "abrir", "abrir dentro");
        return click;
    }

    private const string ArchiveFolder = @"D:\Perfil\Documentos\baxy-prueba-v3\";

    // v3-50 class: the entry selected, then its context menu opened by a click (manner «menu»): the archive is not open.
    [Test]
    public void AClickThatOpenedTheEntrysMenuAfterSelectingItIsNoArrival()
    {
        const string Term = "control:==prueba.zip:current";
        JsonArray steps = [ClickReceipt(1, "prueba.zip", "ListItem"), MenuClick(2, "prueba.zip")];
        JsonObject recorded = FolderWithMenu();
        recorded["selectedBeforeClick"] = SelectedBefore([], ["prueba.zip"]);
        // Counter-case: a double click after the selection that opened the archive (window retitled, its entries listed).
        JsonArray opened = [ClickReceipt(1, "prueba.zip", "ListItem"),
            ClickReceipt(2, "prueba.zip", "ListItem", broughtNew: true, windowTitle: ArchiveFolder + @"prueba.zip\")];
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate(Term, recorded, steps, out string? by), Is.False, by);
            Assert.That(ComputerUseSuccessCheck.Evaluate(Term, View(SevenZipFolder), steps, out _), Is.False, "without the record");
            Assert.That(ComputerUseSuccessCheck.Evaluate(Term, recorded, opened, out _), Is.True);
        });
    }

    // A single click that opened the entry's context menu chose it and moved nothing.
    [Test]
    public void ASingleClickThatOpenedTheEntrysMenuIsNoArrival()
    {
        const string Term = "control:==prueba.zip:current";
        JsonArray steps = [MenuClick(1, "prueba.zip")];
        JsonObject recorded = FolderWithMenu();
        recorded["selectedBeforeClick"] = SelectedBefore([]);
        // Counter-case: the ordinary press of the entry that changed the surface and listed the archive's entries.
        JsonArray pressed = [ClickReceipt(1, "prueba.zip", "ListItem", surfaceChanged: true, broughtNew: true)];
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate(Term, recorded, steps, out string? by), Is.False, by);
            Assert.That(ComputerUseSuccessCheck.Evaluate(Term, View(SevenZipFolder), steps, out _), Is.False, "without the record");
            Assert.That(ComputerUseSuccessCheck.Evaluate(Term, View(SevenZipFolder), pressed, out _), Is.True);
        });
    }

    // The entry selected, then a key (Shift+F10) that opened its context menu: only menu entries appeared and the title
    // stayed, so the key moved nothing. Counter-cases: a later key that retitled the window, or that brought the page's
    // own controls, moved it.
    [Test]
    public void ALaterKeyThatOnlyOpenedAMenuIsNoArrival()
    {
        const string Term = "control:==prueba.zip:current";
        JsonObject menuKey = KeyReceipt(2, "input.key.press", "shift+f10", null, ArchiveFolder, "contexto", "abrir", "abrir dentro");
        menuKey["surfaceChanged"] = true;
        JsonArray steps = [ClickReceipt(1, "prueba.zip", "ListItem", windowTitle: ArchiveFolder), menuKey];
        JsonObject flagged = menuKey.DeepClone().AsObject();
        flagged["appearedOnlyMenu"] = true;
        JsonArray stepsFlagged = [ClickReceipt(1, "prueba.zip", "ListItem", windowTitle: ArchiveFolder), flagged];
        JsonObject recorded = FolderWithMenu();
        recorded["selectedBeforeClick"] = SelectedBefore([], ["prueba.zip"]);
        JsonObject recordedClosed = View(SevenZipFolder);
        recordedClosed["selectedBeforeClick"] = SelectedBefore([], ["prueba.zip"]);
        JsonArray retitled = [ClickReceipt(1, "prueba.zip", "ListItem", windowTitle: ArchiveFolder),
            KeyReceipt(2, "input.key.press", "enter", null, ArchiveFolder + @"prueba.zip\")];
        JsonArray broughtPage = [ClickReceipt(1, "prueba.zip", "ListItem", windowTitle: ArchiveFolder),
            KeyReceipt(2, "input.key.press", "enter", null, ArchiveFolder, "documento.txt")];
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate(Term, recorded, steps, out string? by), Is.False, by);
            Assert.That(ComputerUseSuccessCheck.Evaluate(Term, recordedClosed, stepsFlagged, out _), Is.False,
                "the receipt's mark tells the menu once it closed");
            Assert.That(ComputerUseSuccessCheck.Evaluate(Term, recordedClosed, retitled, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate(Term, recordedClosed, broughtPage, out _), Is.True);
        });
    }

    // MarkAppeared marks a look whose new controls are only a menu's entries, and no other.
    [Test]
    public void TheLookAfterAnActMarksWhenItBroughtOnlyAMenu()
    {
        JsonObject before = View(SevenZipFolder);
        var state = new JsonObject();
        JsonArray steps = [ClickReceipt(1, "prueba.zip", "ListItem")];
        ComputerUseMission.MarkAppeared(state, steps, 0, before);
        steps.Add((JsonNode)KeyReceipt(2, "input.key.press", "shift+f10", null, "x"));
        ComputerUseMission.MarkAppeared(state, steps, 0, FolderWithMenu());
        JsonObject page = View(SevenZipFolder);
        ((JsonArray)page["controls"]!).Add((JsonNode)new JsonObject { ["i"] = 8, ["kind"] = "ListItem", ["name"] = "documento.txt", ["zone"] = "L" });
        var other = new JsonObject();
        JsonArray stepsOther = [ClickReceipt(1, "prueba.zip", "ListItem")];
        ComputerUseMission.MarkAppeared(other, stepsOther, 0, before);
        stepsOther.Add((JsonNode)KeyReceipt(2, "input.key.press", "enter", null, "x"));
        ComputerUseMission.MarkAppeared(other, stepsOther, 0, page);
        Assert.Multiple(() =>
        {
            Assert.That((bool?)steps[1]!["appearedOnlyMenu"], Is.True);
            Assert.That(steps[1]!["appeared"]!.AsArray(), Has.Count.EqualTo(3));
            Assert.That(stepsOther[1]!["appearedOnlyMenu"], Is.Null);
            Assert.That(ComputerUseSuccessCheck.BroughtOnlyMenu((JsonObject)stepsOther[1]!, page), Is.False);
        });
    }

    // Encargo K (banco def1 x8): the keyboard's receipt said «125+75» typed (it counts what was sent) and the look after
    // it showed «La expresión es 25 +» «Se muestra 75»: the text did not arrive whole, and the step says so («arrived»
    // false, the final's «intentó escribir»). Contracases: c2's «12*12» shown whole, a thousands separator («1000» shown
    // «1.000»), the same text shown whole, a text a field took by its value (no keyboard), and a look that shows none of it.
    [TestCase("125+75", "keyboard", new[] { "La expresión es 25 +", "Se muestra 75" }, false)]
    [TestCase("12*12", "keyboard", new[] { "La expresión es 12 ×", "Se muestra 12" }, null)]
    [TestCase("1000", "keyboard", new[] { "Se muestra 1.000" }, null)]
    [TestCase("125+75", "keyboard", new[] { "La expresión es 125 +", "Se muestra 75" }, null)]
    [TestCase("125+75", "value", new[] { "La expresión es 25 +", "Se muestra 75" }, null)]
    [TestCase("Querido Ron", "keyboard", new[] { "Sin título: Bloc de notas" }, null)]
    public void ATextTheLookAfterItShowsCutAtItsStartDidNotArriveWhole(
        string text, string method, string[] shown, bool? arrived)
    {
        static JsonObject Calculator(params string[] names)
        {
            var controls = new JsonArray();
            controls.Add((JsonNode)new JsonObject { ["i"] = 0, ["kind"] = "Button", ["name"] = "Es igual a", ["zone"] = "B" });
            int index = 1;
            foreach (string name in names)
                controls.Add((JsonNode)new JsonObject { ["i"] = index++, ["kind"] = "Text", ["name"] = name, ["zone"] = "T" });
            return new JsonObject
            {
                ["window"] = new JsonObject { ["title"] = "Calculadora", ["process"] = "CalculatorApp", ["hwnd"] = 6229570 },
                ["controls"] = controls,
            };
        }

        var state = new JsonObject();
        JsonArray steps = [new JsonObject { ["step"] = 1, ["operation"] = "app.open", ["ok"] = true }];
        ComputerUseMission.MarkAppeared(state, steps, 0, Calculator("Se muestra 0"));
        JsonObject typed = KeyReceipt(2, "input.text.type", null, text, "Calculadora");
        typed.Remove("appeared");
        typed["method"] = method;
        steps.Add((JsonNode)typed);
        ComputerUseMission.MarkAppeared(state, steps, 0, Calculator(shown));

        Assert.That((bool?)typed["arrived"], Is.EqualTo(arrived));
    }

    // Revision 1 of ronda 21: the look before a sub-goal's first act carries no goal's words and the look after it does,
    // so in a folder of 200 entries the second lists «Informes 2023.xlsx» and «Informes viejos» past the cut
    // («reserved»). A click that only selected «Informes» brought none of them: no appeared, no broughtNew, the same
    // signature, no moved place, and a pressed echo of the query stays an echo.
    [Test]
    public void WhatALookListsOnlyForTheGoalsWordsIsNotWhatTheClickBrought()
    {
        JsonObject Folder(bool selected, bool reserved)
        {
            var controls = new JsonArray();
            foreach (string name in new[] { "Atrás", "Adelante", "Arriba", "Nuevo", "Ordenar", "Ver" })
            {
                controls.Add((JsonNode)new JsonObject { ["kind"] = "Button", ["name"] = name, ["zone"] = "T" });
            }

            for (int k = 0; k < 38; k++)
            {
                string name = k == 20 ? "Informes" : $"archivo {k}.txt";
                controls.Add((JsonNode)new JsonObject
                {
                    ["kind"] = "ListItem",
                    ["name"] = name,
                    ["zone"] = "L",
                    ["state"] = selected && k == 20 ? "selected" : string.Empty,
                });
            }

            if (reserved)
            {
                foreach (string name in new[] { "Informes 2023.xlsx", "Informes viejos" })
                {
                    controls.Add((JsonNode)new JsonObject { ["kind"] = "ListItem", ["name"] = name, ["zone"] = "L", ["reserved"] = true });
                }
            }

            for (int k = 0; k < controls.Count; k++)
            {
                controls[k]!["i"] = k;
            }

            return new JsonObject
            {
                ["window"] = new JsonObject { ["title"] = @"C:\Users\p\Documentos", ["process"] = "explorer", ["requested"] = true },
                ["controls"] = controls,
                ["controlCount"] = 220,
            };
        }

        static JsonObject Unselected(JsonObject receipt)
        {
            JsonObject copy = receipt.DeepClone().AsObject();
            copy["selected"] = false;
            return copy;
        }

        JsonObject before = Folder(selected: false, reserved: false);
        JsonObject after = Folder(selected: true, reserved: true);
        var namesBefore = new JsonObject { ["1"] = ComputerUseSuccessCheck.ControlNames(before) };
        after["controlsBeforeClick"] = namesBefore.DeepClone();
        var state = new JsonObject();
        JsonArray steps = [];
        ComputerUseMission.MarkAppeared(state, steps, 0, before);
        JsonObject click = ClickReceipt(1, "Informes", "ListItem", broughtNew: null);
        click.Remove("appeared");
        steps.Add((JsonNode)click);
        ComputerUseMission.MarkAppeared(state, steps, 0, after);
        ComputerUseSuccessCheck.NoteWhatTheClickBrought(after, steps);

        // Contracase: the same names really new on the window (no reservation) are what the click brought.
        JsonObject listed = Folder(selected: true, reserved: true);
        foreach (JsonObject control in ((JsonArray)listed["controls"]!).OfType<JsonObject>())
        {
            control.Remove("reserved");
        }

        listed["controlsBeforeClick"] = namesBefore.DeepClone();
        JsonArray stepsListed = [ClickReceipt(1, "Informes", "ListItem", broughtNew: null)];
        ComputerUseSuccessCheck.NoteWhatTheClickBrought(listed, stepsListed);
        Assert.Multiple(() =>
        {
            Assert.That(click["appeared"]!.AsArray(), Is.Empty);
            Assert.That((bool?)click["broughtNew"], Is.False);
            Assert.That(ComputerUseSuccessCheck.MovedThePlace(click, steps, after), Is.False);
            // The same receipt as a pressed suggestion of the query that selected nothing (M2, v3-11) stays an echo.
            Assert.That(ComputerUseSuccessCheck.ClickEchoesQuery(Unselected(click), ["informes"]), Is.True);
            Assert.That(ComputerUseMission.ViewSignature(Folder(selected: false, reserved: true)),
                Is.EqualTo(ComputerUseMission.ViewSignature(before)));
            Assert.That((bool?)stepsListed[0]!["broughtNew"], Is.True);
            Assert.That(ComputerUseSuccessCheck.ControlNames(after).Count, Is.EqualTo(44));
        });
    }

    // Revision 2 of ronda 21: the evidence judge reads a look's parts (LookText) without what it listed only for the
    // goal's words. A folder of 300 entries, goal «comprime el archivo presupuesto 2023»: the sub-goal's first look (no
    // words) already shows «Presupuesto 2023.xlsx» in its written text; a verified click that only selected «archivo
    // 3.txt» brings the next look, which lists the reserved ListItem «Presupuesto 2023.xlsx». Citing it is seen at the
    // start: nothing was compressed. Contracase: the same entry listed by the base cut (not reserved) is new on screen.
    [Test]
    public void AControlListedOnlyForTheGoalsWordsIsNoEvidenceOfTheAct()
    {
        JsonObject Folder(bool selected, string? entry, bool reserved)
        {
            var controls = new JsonArray();
            foreach (string name in new[] { "Atrás", "Adelante", "Arriba", "Nuevo", "Ordenar", "Ver" })
            {
                controls.Add((JsonNode)new JsonObject { ["kind"] = "Button", ["name"] = name, ["zone"] = "T" });
            }

            for (int k = 0; k < 40; k++)
            {
                controls.Add((JsonNode)new JsonObject
                {
                    ["kind"] = "ListItem",
                    ["name"] = $"archivo {k}.txt",
                    ["zone"] = "L",
                    ["state"] = selected && k == 3 ? "selected" : string.Empty,
                });
            }

            if (entry is not null)
            {
                var item = new JsonObject { ["kind"] = "ListItem", ["name"] = entry, ["zone"] = "L" };
                if (reserved)
                {
                    item["reserved"] = true;
                }

                controls.Add((JsonNode)item);
            }

            for (int k = 0; k < controls.Count; k++)
            {
                controls[k]!["i"] = k;
            }

            return new JsonObject
            {
                ["window"] = new JsonObject { ["title"] = @"C:\Users\p\Documentos", ["process"] = "explorer", ["requested"] = true },
                ["controls"] = controls,
                ["controlCount"] = 300,
                ["text"] = new JsonObject { ["L"] = new JsonArray("Presupuesto 2023.xlsx", "archivo 0.txt") },
            };
        }

        // Estabilización R16: the look the App keeps for the mind (LookText, the first look its judge reads) leaves the
        // reserved entry out; the citation of it is refused by the mind's judge (tests/test_cu_estab_r16_juez_unico.py).
        JsonObject reservedLook = Folder(selected: true, entry: "Presupuesto 2023.xlsx", reserved: true);
        JsonObject listedLook = Folder(selected: true, entry: "Presupuesto 2023.xlsx", reserved: false);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.LookText(reservedLook),
                Is.EqualTo(ComputerUseSuccessCheck.LookText(Folder(selected: true, entry: null, reserved: false))));
            Assert.That(ComputerUseSuccessCheck.LookText(listedLook), Is.Not.EqualTo(ComputerUseSuccessCheck.LookText(reservedLook)),
                "listed by the base cut, the entry is a part of the look");
        });
    }

    // Revision 3 of ronda 21: the judges that ask whether something besides a field shows a text, or how many places
    // show it, read no control listed only for the goal's words («reserved»): its name carries the goal's words, which
    // are mostly what BAXY typed or searched. A full folder, goal «crea una carpeta nueva llamada Informe», BAXY typed
    // «Informe» into «Nombre»: «Informe 2023.xlsx» listed past the cut leaves the veto typed_by_baxy as without it; the
    // same entry listed by the base cut lifts it. The same for a search's places and for a place searched and not found.
    [Test]
    // Estabilización R16: the done of «crea una carpeta nueva llamada informe» citing «Informe» typed into «Nombre» is the
    // mind's judge's (tests/test_cu_estab_r16_juez_unico.py); the App's checks of a search below still read no
    // reserved control.
    public void AControlListedOnlyForTheGoalsWordsShowsNothingElsewhere()
    {
        JsonObject Look(JsonObject? entry, JsonObject field, JsonObject? text = null)
        {
            var controls = new JsonArray { (JsonNode)field };
            for (int k = 0; k < 40; k++)
            {
                controls.Add((JsonNode)new JsonObject { ["kind"] = "ListItem", ["name"] = $"archivo {k}.txt", ["zone"] = "L" });
            }

            if (entry is not null)
            {
                controls.Add((JsonNode)entry);
            }

            for (int k = 0; k < controls.Count; k++)
            {
                controls[k]!["i"] = k;
            }

            var view = new JsonObject
            {
                ["window"] = new JsonObject { ["title"] = "Documentos", ["process"] = "explorer", ["requested"] = true },
                ["controls"] = controls,
                ["controlCount"] = 300,
            };
            if (text is not null)
            {
                view["text"] = text;
            }

            return view;
        }

        JsonObject Entry(string name, bool reserved, string kind = "ListItem")
        {
            var item = new JsonObject { ["kind"] = kind, ["name"] = name, ["zone"] = "L" };
            if (reserved)
            {
                item["reserved"] = true;
            }

            return item;
        }


        JsonObject SearchField() => new() { ["kind"] = "Edit", ["name"] = "Cuadro de búsqueda, Buscar", ["value"] = "wi-fi" };
        JsonObject Echo() => new() { ["C"] = new JsonArray("wi-fi") };
        JsonArray searched =
        [
            new JsonObject { ["step"] = 1, ["operation"] = "input.text.type", ["into"] = "Cuadro de búsqueda, Buscar", ["text"] = "wi-fi", ["ok"] = true },
        ];
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.OnlyTheQueryShows("wi-fi", Look(null, SearchField(), Echo()), searched), Is.True);
            Assert.That(ComputerUseSuccessCheck.OnlyTheQueryShows(
                "wi-fi", Look(Entry("Wi-Fi Direct.txt", reserved: true), SearchField(), Echo()), searched), Is.True);
            Assert.That(ComputerUseSuccessCheck.OnlyTheQueryShows(
                "wi-fi", Look(Entry("Wi-Fi Direct.txt", reserved: false), SearchField(), Echo()), searched), Is.False);

            Assert.That(ComputerUseSuccessCheck.SearchedAndNotFound("wi-fi", searched, Look(null, SearchField())), Is.True);
            Assert.That(ComputerUseSuccessCheck.SearchedAndNotFound(
                "wi-fi", searched, Look(Entry("Wi-Fi Direct.txt", reserved: true), SearchField())), Is.True);
            Assert.That(ComputerUseSuccessCheck.SearchedAndNotFound(
                "wi-fi", searched, Look(Entry("Wi-Fi Direct.txt", reserved: false), SearchField())), Is.False);
        });
    }

    // ------------------------------------------- revision 3 of ronda 20b: a key's title against the look it was decided on

    // The title of the look an act was decided on, as the mission records it (titleBefore).
    private static JsonObject DecidedOn(JsonObject step, string title)
    {
        step["titleBefore"] = title;
        return step;
    }

    // The same steps without the record of the look each act was decided on (steps recorded before it existed).
    private static JsonArray WithoutTitleBefore(JsonArray steps) =>
        new(steps.Select(step =>
        {
            JsonObject copy = step!.DeepClone().AsObject();
            copy.Remove("titleBefore");
            return (JsonNode?)copy;
        }).ToArray());

    private static JsonArray Prefix(JsonArray steps, int count) =>
        new(steps.Take(count).Select(step => step!.DeepClone()).ToArray());

    private const string ObsMain = "OBS 31.0.0 - Perfil: Sin título - Escenas: Sin título";

    // v3-52 class, as the real provider answers: the first look is OBS's main window; a click on «Ajustes» opened the
    // dialog (its receipt bears no title), a click on «Vídeo» only selected it (method select, nothing changed) and the
    // page beside it still shows General (Idioma); then Enter did nothing (its receipt rereads «Ajustes»). Measured
    // against an older title (the first look's) that Enter passed for the arrival: it is none.
    [Test]
    public void AKeyThatDidNothingAfterAClickThatChangedTheWindowIsNoArrival()
    {
        const string Term = "control:video:current";
        JsonObject view = View(SettingsList);
        view["selectedAtStart"] = new JsonArray();
        view["subgoalFirstText"] = ObsMain + "\nAjustes";
        view["selectedBeforeClick"] = SelectedBefore([], ["general"], ["video"]);
        JsonArray steps =
        [
            DecidedOn(ClickReceipt(1, "Ajustes", "Button", surfaceChanged: true, broughtNew: true, selected: false), ObsMain),
            DecidedOn(ClickReceipt(2, "Vídeo", "ListItem"), "Ajustes"),
            DecidedOn(KeyReceipt(3, "input.key.press", "enter", null, "Ajustes"), "Ajustes"),
        ];
        JsonObject opened = AppOpened(1);
        opened["windowTitle"] = ObsMain;
        JsonArray fromOpening = [opened, .. steps.Select(step => step!.DeepClone())];
        for (int index = 1; index < fromOpening.Count; index++)
        {
            fromOpening[index]!["step"] = index + 1;
        }

        // Counter-cases: an Enter that drew the section's page, or one that retitled the window, moved it.
        JsonArray drew = Prefix(steps, 2);
        drew.Add((JsonNode)DecidedOn(KeyReceipt(3, "input.key.press", "enter", null, "Ajustes", "resolucion base"), "Ajustes"));
        JsonArray retitled = Prefix(steps, 2);
        retitled.Add((JsonNode)DecidedOn(KeyReceipt(3, "input.key.press", "enter", null, "Ajustes - Vídeo"), "Ajustes"));
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate(Term, view, Prefix(steps, 2), out string? by), Is.False, by);
            Assert.That(ComputerUseSuccessCheck.Evaluate(Term, view, steps, out by), Is.False, by);
            Assert.That(ComputerUseSuccessCheck.Evaluate(Term, view, WithoutTitleBefore(steps), out by), Is.False,
                "without the record, a click's receipt bears no title to measure the key against");
            Assert.That(ComputerUseSuccessCheck.Evaluate(Term, view, drew, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate(Term, view, retitled, out _), Is.True);
        });
    }

    // v3-50 class, as the real provider answers: the first look is «Documentos»; a double click entered the folder (its
    // receipt bears no title), a click only selected «prueba.zip», Shift+F10 opened its context menu (only menu entries
    // appeared, the title stayed the folder's) and Escape closed it. None opened the archive.
    [Test]
    public void AMenuKeyAfterAClickThatEnteredTheFolderIsNoArrival()
    {
        const string Term = "control:==prueba.zip:current";
        const string Documents = @"D:\Perfil\Documentos\";
        JsonObject entered = ClickReceipt(1, "baxy-prueba-v3", "ListItem", surfaceChanged: true, broughtNew: true, selected: false);
        entered["manner"] = "double";
        JsonObject menuKey = KeyReceipt(3, "input.key.press", "shift+f10", null, ArchiveFolder, "contexto", "abrir", "abrir dentro");
        menuKey["surfaceChanged"] = true;
        menuKey["appearedOnlyMenu"] = true;
        JsonArray steps =
        [
            DecidedOn(entered, Documents),
            DecidedOn(ClickReceipt(2, "prueba.zip", "ListItem"), ArchiveFolder),
            DecidedOn(menuKey, ArchiveFolder),
            DecidedOn(KeyReceipt(4, "input.key.press", "escape", null, ArchiveFolder), ArchiveFolder),
        ];
        JsonObject Look(JsonObject view)
        {
            view["selectedAtStart"] = new JsonArray();
            view["subgoalFirstText"] = Documents + "\nbaxy-prueba-v3";
            view["selectedBeforeClick"] = SelectedBefore([], [], ["prueba.zip"], ["prueba.zip"]);
            return view;
        }

        JsonObject closed = Look(View(SevenZipFolder));
        JsonObject withMenu = Look(FolderWithMenu());
        // Counter-case: after the selection, an Enter that opened the archive (the window retitled by it).
        JsonArray opened = Prefix(steps, 2);
        opened.Add((JsonNode)DecidedOn(KeyReceipt(3, "input.key.press", "enter", null, ArchiveFolder + @"prueba.zip\"), ArchiveFolder));
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate(Term, closed, Prefix(steps, 2), out string? by), Is.False, by);
            Assert.That(ComputerUseSuccessCheck.Evaluate(Term, withMenu, Prefix(steps, 3), out by), Is.False, by);
            Assert.That(ComputerUseSuccessCheck.Evaluate(Term, closed, steps, out by), Is.False, by);
            Assert.That(ComputerUseSuccessCheck.Evaluate(Term, withMenu, WithoutTitleBefore(Prefix(steps, 3)), out by), Is.False, by);
            Assert.That(ComputerUseSuccessCheck.Evaluate(Term, closed, WithoutTitleBefore(steps), out by), Is.False, by);
            Assert.That(ComputerUseSuccessCheck.Evaluate(Term, closed, opened, out _), Is.True);
        });
    }

    // Ronda 21 (pasada r18 v3-23): «hacer clic en Sistema» closed on the summary row «Sistema» (DataItem of the central
    // list) under the selected, collapsed node «Registros de Windows» (verificacion-despues: TreeItem «Registros de
    // Windows» selected, DataItem «Sistema» selected, no TreeItem «Sistema»). A content row named like a navigation
    // node shown in the tree is no arrival. Review 2 of r21: a row only selected under a collapsed node has the
    // structure of a node's own untyped row (the registry editor's values), so the look holds it as the click asked;
    // contracases beside it.
    private static JsonObject TreeView(string nodeState, bool sistemaNode = false, bool tree = true)
    {
        var controls = new JsonArray();
        int i = 0;
        if (tree)
        {
            controls.Add(new JsonObject { ["i"] = i++, ["kind"] = "TreeItem", ["name"] = "Visor de eventos (local)", ["zone"] = "TL", ["state"] = "expanded" });
            controls.Add(new JsonObject { ["i"] = i++, ["kind"] = "TreeItem", ["name"] = "Registros de Windows", ["zone"] = "L", ["state"] = nodeState });
            if (sistemaNode)
            {
                controls.Add(new JsonObject { ["i"] = i++, ["kind"] = "TreeItem", ["name"] = "Sistema", ["zone"] = "L" });
            }
        }

        foreach (string row in new[] { "Aplicación", "Seguridad", "Instalación", "Sistema", "Eventos reenviados" })
        {
            controls.Add(new JsonObject
            {
                ["i"] = i++,
                ["kind"] = "DataItem",
                ["name"] = row,
                ["zone"] = "C",
                ["state"] = row == "Sistema" ? "selected" : null,
            });
        }

        return new JsonObject
        {
            ["window"] = new JsonObject { ["title"] = "Visor de eventos", ["foreground"] = true },
            ["controls"] = controls,
        };
    }

    private static JsonArray RowClick(string label, string kind, bool selected, bool surfaceChanged) => new()
    {
        new JsonObject
        {
            ["step"] = 1,
            ["operation"] = "input.visible.click",
            ["label"] = label,
            ["name"] = label,
            ["kind"] = kind,
            ["ok"] = true,
            ["selected"] = selected,
            ["surfaceChanged"] = surfaceChanged,
            ["source"] = "model",
        },
    };

    [Test]
    public void AContentRowNamedLikeANavigationNodeIsNoArrival()
    {
        const string Term = "stepDone:input.visible.click:sistema";
        JsonArray onlySelected = RowClick("Sistema", "DataItem", selected: true, surfaceChanged: false);
        JsonArray redrawn = RowClick("Sistema", "DataItem", selected: true, surfaceChanged: true);
        Assert.Multiple(() =>
        {
            // v3-23: the row only selected under the collapsed node is undecided on receipts alone; the look holds it
            // (no structure tells it from a row of the node's own).
            Assert.That(ComputerUseSuccessCheck.EvaluateReceipts(Term, onlySelected, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate(Term, TreeView("selected collapsed"), onlySelected, out _), Is.True);
            // The node of the same name is in the tree: the row is not it, whatever its receipt.
            Assert.That(ComputerUseSuccessCheck.Evaluate(Term, TreeView("selected expanded", sistemaNode: true), redrawn, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate(Term, TreeView("selected expanded", sistemaNode: true), onlySelected, out _), Is.False);

            // Contracases. The click on the tree node itself holds.
            Assert.That(ComputerUseSuccessCheck.Evaluate(Term, TreeView("selected expanded", sistemaNode: true),
                RowClick("Sistema", "TreeItem", selected: true, surfaceChanged: false), out _), Is.True);
            // A row with no tree beside it (a palette's colour, «hacer clic en Rojo» in Paint) holds as before on the look.
            Assert.That(ComputerUseSuccessCheck.Evaluate(Term, TreeView("selected collapsed", tree: false), onlySelected, out _), Is.True);
            // A row selected under a node that is not collapsed (a folder with no subfolders, its files listed) holds.
            Assert.That(ComputerUseSuccessCheck.Evaluate(Term, TreeView("selected"), onlySelected, out _), Is.True);
            // A row whose click changed the surface, with no node of its name, holds as before (and on receipts).
            Assert.That(ComputerUseSuccessCheck.Evaluate(Term, TreeView("selected collapsed"), redrawn, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.EvaluateReceipts(Term, redrawn, out _), Is.True);
        });
    }

    // Review 1 of r21 (blocker 1): the file view's tree keeps a chosen, collapsed node as its normal state (t-menu-2,
    // model_calls: «TreeItem · «M.2 ADATA (D:)» · selected collapsed · BL» while the list showed baxy-prueba-v3). A click
    // on a file there, whose receipt is only its selection, is the click asked: the row's own item type (UIA ItemType)
    // says it is an item in its own right, never a summary standing for a node.
    private static JsonObject FileView(string nodeState, string? fileType, bool folderNode = false)
    {
        var controls = new JsonArray
        {
            new JsonObject { ["i"] = 0, ["kind"] = "TreeItem", ["name"] = "Este equipo", ["zone"] = "TL", ["state"] = "expanded" },
            new JsonObject { ["i"] = 1, ["kind"] = "TreeItem", ["name"] = "M.2 ADATA (D:)", ["zone"] = "L", ["state"] = nodeState },
        };
        if (folderNode)
        {
            controls.Add(new JsonObject { ["i"] = 2, ["kind"] = "TreeItem", ["name"] = "baxy-prueba-v3", ["zone"] = "L", ["state"] = "collapsed" });
        }

        controls.Add(new JsonObject
        {
            ["i"] = 3,
            ["kind"] = "ListItem",
            ["name"] = "baxy-prueba-v3",
            ["zone"] = "C",
            ["itemType"] = fileType is null ? null : "Carpeta de archivos",
        });
        controls.Add(new JsonObject
        {
            ["i"] = 4,
            ["kind"] = "ListItem",
            ["name"] = "informe.txt",
            ["zone"] = "C",
            ["state"] = "selected",
            ["itemType"] = fileType,
        });
        return new JsonObject
        {
            ["window"] = new JsonObject { ["title"] = "baxy-prueba-v3", ["foreground"] = true },
            ["controls"] = controls,
        };
    }

    [Test]
    public void AFileClickedBesideAChosenCollapsedNodeIsTheClickAsked()
    {
        JsonArray file = RowClick("informe.txt", "ListItem", selected: true, surfaceChanged: false);
        JsonArray folder = RowClick("baxy-prueba-v3", "ListItem", selected: true, surfaceChanged: false);
        Assert.Multiple(() =>
        {
            // The common state of a file view: the drive chosen and collapsed, the file only selected.
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.visible.click:informe.txt",
                FileView("selected collapsed", "Documento de texto"), file, out _), Is.True);
            // A folder row the application types holds too, even beside a node of its name in the tree.
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.visible.click:baxy-prueba-v3",
                FileView("selected collapsed", "Documento de texto", folderNode: true), folder, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.visible.click:baxy-prueba-v3",
                FileView("selected expanded", "Documento de texto", folderNode: true), folder, out _), Is.True);

            // Review 2 of r21: an untyped file row under the chosen, collapsed node is the click asked as well (a file
            // manager that fills no ItemType); an empty type says nothing either way.
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.visible.click:informe.txt",
                FileView("selected collapsed", null), file, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.visible.click:informe.txt",
                FileView("selected collapsed", string.Empty), file, out _), Is.True);
            // Contracase kept: an untyped row named like a node the tree shows is not that node.
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.visible.click:baxy-prueba-v3",
                FileView("selected expanded", null, folderNode: true), folder, out _), Is.False);
        });
    }

    // Review 2 of r21 (blocker 1): the registry editor with «HKCU\Control Panel\Desktop» chosen (it has subkeys:
    // «selected collapsed»), «hacé clic en el valor WallPaper»: the click only selects the untyped row «WallPaper»
    // (zone C, a Win32 list view's DataItem fills no ItemType), nothing changed nor appeared. It is the click asked.
    private static JsonObject KeyView() => new()
    {
        ["window"] = new JsonObject { ["title"] = "Editor del Registro", ["foreground"] = true },
        ["controls"] = new JsonArray
        {
            new JsonObject { ["i"] = 0, ["kind"] = "TreeItem", ["name"] = "Control Panel", ["zone"] = "L", ["state"] = "expanded" },
            new JsonObject { ["i"] = 1, ["kind"] = "TreeItem", ["name"] = "Desktop", ["zone"] = "L", ["state"] = "selected collapsed" },
            new JsonObject { ["i"] = 2, ["kind"] = "DataItem", ["name"] = "(Predeterminado)", ["zone"] = "C" },
            new JsonObject { ["i"] = 3, ["kind"] = "DataItem", ["name"] = "ActiveWndTrkTimeout", ["zone"] = "C" },
            new JsonObject { ["i"] = 4, ["kind"] = "DataItem", ["name"] = "WallPaper", ["zone"] = "C", ["state"] = "selected" },
        },
    };

    [Test]
    public void AnUntypedRowOnlySelectedUnderAChosenCollapsedNodeIsTheClickAsked()
    {
        const string Term = "stepDone:input.visible.click:wallpaper";
        JsonArray click = RowClick("WallPaper", "DataItem", selected: true, surfaceChanged: false);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate(Term, KeyView(), click, out string? by), Is.True, by);
            // Undecided on receipts alone: the look after it decides, as for any row only selected.
            Assert.That(ComputerUseSuccessCheck.EvaluateReceipts(Term, click, out _), Is.False);
            // Contracase: the same row named like a node the tree shows is not that node.
            JsonObject withNode = KeyView();
            ((JsonArray)withNode["controls"]!).Add(new JsonObject { ["i"] = 5, ["kind"] = "TreeItem", ["name"] = "WallPaper", ["zone"] = "L" });
            Assert.That(ComputerUseSuccessCheck.Evaluate(Term, withNode, click, out _), Is.False);
        });
    }

    // ------------------------------------------- revisión 2 de r22 (bloqueante 1): the act changed its own control

    // A view of one window from its controls (a JSON array), with ids.
    private static JsonObject ControlsView(string process, string controls) =>
        View($$"""{"window": {"title": "Ventana", "process": "{{process}}"}, "controls": {{controls}}}""");

    // Revisión 3 de r22 (bloqueante B1): new text after the act proves whatever its words, when the act was a key of
    // the catalog or the result showed in another control than the one clicked (the song after «Siguiente»).
    // Estabilización R16: that judge is the mind's (tests/test_cu_v3_hecho_solo_con_prueba.py and
    // tests/test_cu_estab_r16_juez_unico.py); the App tells it which clicks changed their own control, here none.
    [Test]
    public void NewTextInAnotherControlIsNoChangeOfTheClickedOne()
    {
        JsonObject songBefore = ControlsView("Spotify", """
            [{"i": 0, "kind": "Button", "name": "Siguiente", "id": "3.1"}, {"i": 1, "kind": "Text", "name": "Bohemian Rhapsody", "id": "3.2"}]
            """);
        JsonObject songAfter = ControlsView("Spotify", """
            [{"i": 0, "kind": "Button", "name": "Siguiente", "id": "3.1"}, {"i": 1, "kind": "Text", "name": "Under Pressure", "id": "3.2"}]
            """);
        songAfter["clickedBefore"] = new JsonObject
        {
            ["1"] = ComputerUseSuccessCheck.ClickedControl(songBefore, new JsonObject { ["index"] = 0, ["label"] = "Siguiente" }),
        };
        Assert.That(ComputerUseSuccessCheck.ChangedByClick(songAfter, (JsonObject)songAfter["clickedBefore"]!), Is.Empty);
    }

    // Revisión 2 de r22 (bloqueante 1) with ronda 20b: an entry the click only selected in place (t4-c06 «Nuevo») is no
    // control the click changed, by identity either; the mind's judge gets the steps whose control changed, never ids.
    [Test]
    public void AnEntryOnlySelectedIsNoControlTheClickChanged()
    {
        JsonObject start = View("""
            {"window": {"title": "Excel", "process": "EXCEL"},
             "controls": [{"i": 0, "kind": "ListItem", "name": "Inicio", "id": "5.1", "state": "selected"},
                          {"i": 1, "kind": "ListItem", "name": "Nuevo", "id": "5.2"}],
             "text": {"TL": ["Excel", "Inicio", "Nuevo"]}}
            """);
        JsonObject gallery = View("""
            {"window": {"title": "Excel", "process": "EXCEL"},
             "controls": [{"i": 0, "kind": "ListItem", "name": "Inicio", "id": "5.1"},
                          {"i": 1, "kind": "ListItem", "name": "Nuevo", "id": "5.2", "state": "selected focused"}],
             "text": {"TL": ["Excel", "Inicio", "1", "Nuevo", "2", "3"]}}
            """);
        var clickedBefore = new JsonObject
        {
            ["1"] = ComputerUseSuccessCheck.ClickedControl(start, new JsonObject { ["index"] = 1, ["label"] = "Nuevo" }),
        };
        gallery["clickedBefore"] = clickedBefore.DeepClone();
        JsonObject playBefore = ControlsView("msedge", """[{"i": 0, "kind": "Button", "name": "Reproducir (k)", "id": "42.7.1"}]""");
        JsonObject playAfter = ControlsView("msedge", """[{"i": 0, "kind": "Button", "name": "Pausa (k)", "id": "42.7.1"}]""");
        var state = new JsonObject
        {
            ["clickedBefore"] = new JsonObject
            {
                ["1"] = ComputerUseSuccessCheck.ClickedControl(playBefore, new JsonObject { ["label"] = "Reproducir (k)" }),
            },
        };
        JsonObject judged = ComputerUseMission.ForTheJudge(ComputerUseMission.CompactForTheMind(playAfter), state, null, playAfter);

        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.ChangedByClick(gallery, clickedBefore), Is.Empty);
            Assert.That(judged["changedByClick"]!.AsArray().Select(step => (int?)step), Is.EqualTo(new int?[] { 1 }));
            Assert.That(judged["controls"]!.AsArray().OfType<JsonObject>().All(control => control["id"] is null));
            Assert.That(ComputerUseSuccessCheck.ClickedControl(
                ControlsView("msedge", """[{"i": 0, "kind": "Button", "name": "Reproducir (k)"}]"""),
                new JsonObject { ["index"] = 0 }), Is.Null, "a control with no id has no identity to follow");
        });
    }
}
