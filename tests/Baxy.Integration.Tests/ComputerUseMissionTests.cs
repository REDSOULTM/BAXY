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
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:tu biblioteca", library, opened, out _), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:tu biblioteca", library, missed, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:cotele", friends, card, out _), Is.False);
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
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:downloads", pictures, clicked, out _), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:pantalla", display, screen, out _), Is.True, "the section kept selected was chosen before");
            Assert.That(ComputerUseSuccessCheck.Evaluate("page:colores", stayed, card, out _), Is.False, "the same controls: the click went nowhere");
        });
    }

    [Test]
    public void ALearnedClickIsPinnedToTheOnlyControlOfTheViewThatCarriesItsName()
    {
        JsonObject clock = View("""
            {"window": {"title": "Reloj"}, "controls": [
              {"i": 3, "kind": "ListItem", "name": "Temporizador"}, {"i": 4, "kind": "ListItem", "name": "Alarma"}]}
            """);
        var learned = new MindComputerUseStep("input.visible.click", new JsonObject { ["label"] = "Alarma" }, "procedure");
        var twice = View("""
            {"window": {"title": "X"}, "controls": [{"i": 1, "kind": "Button", "name": "Alarma"}, {"i": 2, "kind": "Text", "name": "Alarma"}]}
            """);
        Assert.Multiple(() =>
        {
            Assert.That((int?)ComputerUseMission.IdentifyOnView(learned, clock)!.Arguments["index"], Is.EqualTo(4));
            Assert.That(ComputerUseMission.IdentifyOnView(learned, twice)!.Arguments["index"], Is.Null, "two controls carry it: the label decides");
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
        ComputerUseMission.EnterSubgoal(state, 1, procedures: null);
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

    // A learned sequence is forgotten when it deviated or when the screen did not answer its replayed steps; a stop that
    // says nothing about it (no view, a covered or elevated window, no decision, a step that could not be sent) keeps it.
    [TestCase(false, "computer_use_surface_unchanged", true, true)]
    [TestCase(false, "computer_use_no_step_visible", true, true)]
    [TestCase(false, "computer_use_evidence_not_visible", true, true)]
    [TestCase(false, "computer_use_repeated_step", true, true)]
    [TestCase(false, "computer_use_budget_exhausted", true, true)]
    [TestCase(false, "computer_use_time_exhausted", true, true)]
    [TestCase(false, "computer_use_view_unavailable", true, false)]
    [TestCase(false, "computer_use_window_covered", true, false)]
    [TestCase(false, "computer_use_window_elevated", true, false)]
    [TestCase(false, "computer_use_decision_unavailable", true, false)]
    [TestCase(false, "computer_use_step_failed", true, false)]
    [TestCase(false, "computer_use_surface_unchanged", false, false)]
    [TestCase(true, "computer_use_view_unavailable", true, true)]
    public void AProcedureIsForgottenOnlyWhenItDeviatedOrTheScreenDidNotAnswerIt(bool deviated, string errorCode, bool replayed, bool forgotten)
    {
        var steps = new JsonArray
        {
            new JsonObject { ["step"] = 1, ["operation"] = "app.open", ["ok"] = true, ["source"] = replayed ? "procedure" : "model" },
        };
        Assert.That(ComputerUseMission.ForgetsProcedure(deviated, errorCode, steps), Is.EqualTo(forgotten));
    }

    // A procedure whose own step broke the loop (its arguments no longer fit, its window is not the application, it
    // could not be sent) breaks again when replayed: it is forgotten; so is any sub-goal stopped on invalid arguments.
    [TestCase("computer_use_step_arguments_invalid", false, true)]
    [TestCase("computer_use_window_not_application", true, true)]
    [TestCase("computer_use_step_failed", true, true)]
    [TestCase("computer_use_window_not_application", false, false)]
    [TestCase("computer_use_step_failed", false, false)]
    public void AProcedureWhoseStepBrokeTheLoopIsForgotten(string errorCode, bool procedureStepBroke, bool forgotten)
    {
        var steps = new JsonArray
        {
            new JsonObject { ["step"] = 1, ["operation"] = "app.open", ["ok"] = true, ["source"] = "model" },
        };
        Assert.That(ComputerUseMission.ForgetsProcedure(false, errorCode, steps, procedureStepBroke), Is.EqualTo(forgotten));
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
