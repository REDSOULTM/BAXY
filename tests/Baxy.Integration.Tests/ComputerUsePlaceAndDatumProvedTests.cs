using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Ronda 24, «lugar y dato probados, no supuestos»: an arrival or a datum is proved against the place or the question,
/// never against what BAXY typed nor against a label. Cases of the r23 pass: v3-59 (a query typed into the page's own
/// search cited as the arrival at another place), t-scroll-3 (the page reached denied because the search box keeps the
/// query), v3-44 (a click by name under the title the typing gave), v3-39 (the place itself taken for the datum).
/// </summary>
[TestFixture]
public sealed class ComputerUsePlaceAndDatumProvedTests
{
    private static JsonObject View(string json) => (JsonObject)JsonNode.Parse(json)!;

    // v3-59, sub-goal «ir a wikipedia» as the App saw it after step 4: the address bar kept the focus, the step named the
    // page's own search field, which took «Curicó».
    private const string NewTab = """
        {"window": {"title": "Nueva pestaña y 1 página más - Personal: Microsoft Edge", "process": "msedge",
                    "focused": {"kind": "Edit", "name": "Barra de direcciones y búsqueda", "i": 7}},
         "controls": [{"i": 7, "kind": "Edit", "name": "Barra de direcciones y búsqueda", "value": "wikipedia español", "zone": "T"},
                      {"i": 13, "kind": "Document", "name": "Nueva pestaña", "value": "https://ntp.msn.com/edge/ntp?locale=es-4", "zone": "C"},
                      {"i": 15, "kind": "Edit", "name": "Escribe el término de búsqueda", "value": "Curicó", "zone": "T"},
                      {"i": 18, "kind": "Hyperlink", "name": "Curicó: Soleado, 15 °C", "zone": "TR"}],
         "text": {"T": ["q curico"]}}
        """;

    private const string WikipediaCheck = "control:wikipedia:current|title:wikipedia|page:wikipedia|mark:wikipedia";

    private static JsonObject TypedReceipt(JsonObject arguments, JsonObject view, int step = 1)
    {
        var record = new JsonObject { ["step"] = step, ["operation"] = "input.text.type", ["ok"] = true, ["changed"] = true };
        ComputerUseMission.NoteWhereTheTextGoes(record, arguments, view);
        record["text"] = arguments["text"]?.DeepClone();
        if (arguments["field"] is JsonNode field)
            record["field"] = field.DeepClone();
        return record;
    }

    [Test]
    public void V3_59_TheFieldTheStepNamedIsWhereTheTextWentNotTheFocus()
    {
        JsonObject view = View(NewTab);
        JsonObject named = TypedReceipt(new JsonObject { ["text"] = "Curicó", ["field"] = "Escribe el término de búsqueda" }, view);
        JsonObject byIndex = TypedReceipt(new JsonObject { ["text"] = "Curicó", ["index"] = 15 }, view);
        JsonObject atFocus = TypedReceipt(new JsonObject { ["text"] = "Curicó", ["index"] = 7 }, view);
        JsonObject sameAsFocus = TypedReceipt(new JsonObject { ["text"] = "Curicó", ["field"] = "Barra de direcciones y búsqueda" }, view);
        var steps = new JsonArray(named.DeepClone(),
            new JsonObject { ["step"] = 2, ["operation"] = "input.visible.click", ["label"] = "wikipedia", ["ok"] = true });
        Assert.Multiple(() =>
        {
            Assert.That((string?)named["into"], Is.EqualTo("Escribe el término de búsqueda"));
            Assert.That((string?)byIndex["into"], Is.EqualTo("Escribe el término de búsqueda"));
            Assert.That(ComputerUseSuccessCheck.TypedIntoASearch(named), Is.True);
            // Counter-cases: the focused field, named by its index or by its name, stays the focus.
            Assert.That((string?)atFocus["into"], Is.EqualTo("Barra de direcciones y búsqueda"));
            Assert.That((string?)sameAsFocus["into"], Is.EqualTo("Barra de direcciones y búsqueda"));
            // The query the page's search holds is its echo, cited or not.
            Assert.That(ComputerUseSuccessCheck.QueryEchoNames("curico", view, steps, false), Is.True);
            Assert.That(ComputerUseSuccessCheck.CitationEchoesQuery("q curico", view, steps), Is.True);
        });
    }

    // Counter-case: «en el explorador andá a Descargas» typed with field «Buscar en Inicio»: still the echo of the search.
    [Test]
    public void ATypedFieldThatSearchesStillEchoesItsQuery()
    {
        JsonObject view = View("""
            {"window": {"title": "descargas - Resultados de la búsqueda en Inicio", "process": "explorer",
                        "focused": {"kind": "Edit", "name": "Barra de direcciones", "i": 2}},
             "controls": [{"i": 2, "kind": "Edit", "name": "Barra de direcciones", "value": "Inicio", "zone": "T"},
                          {"i": 3, "kind": "Edit", "name": "Buscar en Inicio", "value": "descargas", "zone": "TR"},
                          {"i": 9, "kind": "ListItem", "name": "Descargas viejas", "zone": "C"}]}
            """);
        JsonObject typed = TypedReceipt(new JsonObject { ["text"] = "descargas", ["field"] = "Buscar en Inicio" }, view);
        var steps = new JsonArray(typed, new JsonObject { ["step"] = 2, ["operation"] = "input.key.press", ["key"] = "enter", ["ok"] = true });
        Assert.Multiple(() =>
        {
            Assert.That((string?)typed["into"], Is.EqualTo("Buscar en Inicio"));
            Assert.That(ComputerUseSuccessCheck.QueryEchoNames("descargas", view, steps, false), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("title:descargas", view, steps, out _), Is.False);
        });
    }

    [Test]
    public void V3_59_ADoneForAPlaceCitingNothingOfThePlaceDoesNotClose()
    {
        JsonObject view = View(NewTab);
        JsonObject typed = TypedReceipt(new JsonObject { ["text"] = "Curicó", ["field"] = "Escribe el término de búsqueda" }, view);
        var steps = new JsonArray(typed);
        JsonObject arrived = View("""
            {"window": {"title": "Wikipedia, la enciclopedia libre - Personal: Microsoft Edge", "process": "msedge"},
             "controls": [{"i": 3, "kind": "TabItem", "name": "Wikipedia, la enciclopedia libre", "state": "selected", "zone": "TL"}]}
            """);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.CitationOffThePlace("q curico", "ir a wikipedia", WikipediaCheck, view, steps), Is.True);
            Assert.That(ComputerUseSuccessCheck.CitationOffThePlace("Curicó: Soleado, 15 °C", "ir a wikipedia", WikipediaCheck, view, steps), Is.True);
            // Counter-cases: a check that holds; a goal that is no place (the search of «en edge abre una pestaña y busca
            // Curicó» closes on its own suggestion as before).
            Assert.That(ComputerUseSuccessCheck.CitationOffThePlace("q curico", "ir a wikipedia", WikipediaCheck, arrived, steps), Is.False);
            Assert.That(ComputerUseSuccessCheck.CitationOffThePlace("Curicó: Soleado, 15 °C", "buscar Curicó", "title:curico", view, steps), Is.False);
            // Revisión 1 de r28 (rewritten: these three were judged on the new-tab view, where nothing shows the place;
            // naming it proved the arrival by itself, the hole of bloqueante 2). The names the check gives the place,
            // and those a translation gave it, are the place when the view reads the window there: the item chosen.
            Assert.That(ComputerUseSuccessCheck.CitationOffThePlace("Wikipedia, la enciclopedia libre", "ir a wikipedia", WikipediaCheck, view, steps), Is.True);
            JsonObject fonts = View("""{"window": {"title": "Configuración", "process": "SystemSettings"}, "controls": [{"i": 1, "kind": "ListItem", "name": "Fuentes", "state": "selected", "zone": "L"}]}""");
            JsonObject mail = View("""{"window": {"title": "Correo", "process": "mail"}, "controls": [{"i": 1, "kind": "TreeItem", "name": "Inbox (3)", "state": "selected", "zone": "L"}]}""");
            Assert.That(ComputerUseSuccessCheck.CitationOffThePlace("Fuentes", "ir a fonts", "control:fonts:current|title:fuentes", fonts, steps), Is.False);
            Assert.That(ComputerUseSuccessCheck.CitationOffThePlace("Inbox (3)", "ir a bandeja", "control:bandeja:current", mail, steps), Is.True);
            Assert.That(ComputerUseSuccessCheck.CitationOffThePlace("Inbox (3)", "ir a bandeja", "control:bandeja:current", mail, steps, ["Inbox"]), Is.False);
        });
    }

    // Ronda 28. Tanda c27u2 (redpc, 2026-10-10) t2-c03 t1, «abre configuracion que quiero ver lo de la pantalla»: the
    // view of model call 45 (Settings on Personalización > Pantalla de bloqueo), the planned check and the three steps
    // of the trace (t8, seq 238-266). The model said done citing «Pantalla de bloqueo» and the sub-goal closed
    // (computer_use.satisfied subgoal.1.model_evidence): «Listo, estoy en pantalla».
    private const string LockScreenPage = """
        {"window": {"title": "Configuración", "process": "SystemSettings"},
         "controls": [{"i": 4, "kind": "Edit", "name": "Cuadro de búsqueda, Buscar una opción", "zone": "T"},
                      {"i": 7, "kind": "ListItem", "name": "Inicio", "zone": "TL"},
                      {"i": 8, "kind": "ListItem", "name": "Sistema", "zone": "TL"},
                      {"i": 9, "kind": "ListItem", "name": "Bluetooth y dispositivos", "zone": "TL"},
                      {"i": 10, "kind": "ListItem", "name": "Red e Internet", "zone": "L"},
                      {"i": 11, "kind": "ListItem", "name": "Personalización", "state": "selected", "zone": "L"},
                      {"i": 19, "kind": "Button", "name": "Personalización", "zone": "TL"},
                      {"i": 20, "kind": "Button", "name": "Pantalla de bloqueo", "zone": "T"},
                      {"i": 23, "kind": "ComboBox", "name": "Personalizar la pantalla de bloqueo", "state": "collapsed",
                       "value": "Contenido destacado de Windows", "zone": "R"},
                      {"i": 24, "kind": "ListItem", "name": "Contenido destacado de Windows", "state": "selected", "zone": "R"},
                      {"i": 35, "kind": "Text", "name": "Pantalla de bloqueo", "zone": "T"},
                      {"i": 36, "kind": "Text", "name": "Vista previa de la pantalla de bloqueo", "zone": "T"},
                      {"i": 40, "kind": "Text", "name": "Personalizar la pantalla de bloqueo", "zone": "C"}],
         "text": {"TL": ["Configuración", "Personalización"]}}
        """;

    private const string ScreenCheck =
        "control:pantalla:current|title:pantalla|page:pantalla|control:display:current|title:display|page:display|mark:pantalla|mark:display";

    private static JsonArray LockScreenSteps() =>
    [
        new JsonObject { ["step"] = 1, ["operation"] = "app.open", ["appId"] = "Configuración", ["ok"] = true },
        new JsonObject { ["step"] = 2, ["operation"] = "input.visible.click", ["label"] = "Pantalla de bloqueo", ["ok"] = true },
        new JsonObject { ["step"] = 3, ["operation"] = "input.visible.click", ["label"] = "pantalla", ["ok"] = true },
    ];

    [Test]
    public void T2_C03_APlaceInsideALongerNameIsAnotherPlaceAndClosesNoArrival()
    {
        JsonObject view = View(LockScreenPage);
        JsonArray steps = LockScreenSteps();
        bool Off(string cited, string goal = "ir a pantalla", string check = ScreenCheck, string[]? names = null) =>
            ComputerUseSuccessCheck.CitationOffThePlace(cited, goal, check, view, steps, names);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate(ScreenCheck, view, steps, out _), Is.False, "the planned check does not hold");
            // The false success: the page reached is «Pantalla de bloqueo», which holds the place asked inside a longer name.
            Assert.That(Off("Pantalla de bloqueo"), Is.True);
            Assert.That(Off("Vista previa de la pantalla de bloqueo"), Is.True);
            Assert.That(Off("Personalización | Pantalla de bloqueo"), Is.True);
            // Revisión 1 de r28 (bloqueante 2): nothing on this page reads the window at «Pantalla», so no citation
            // closes it, however it names the place: alone, beside another text of the view, as a breadcrumb, by the
            // other name of its check, misspelt, or by a name a translation gave it.
            string[] said = ["Pantalla", "Display", "Sistema > Pantalla", "Sistema | Pantalla", "Pantalla | Brillo y color"];
            string[] shown = [.. view["controls"]!.AsArray().Select(control => (string)control!["name"]!)];
            foreach (string cited in said.Concat(shown).Concat(shown.Select(name => "Pantalla | " + name)))
            {
                Assert.That(Off(cited), Is.True, cited);
            }

            Assert.That(Off("Sistema > Pantalla", "ir a pantala", "control:pantala:current|title:pantala|page:pantala"), Is.True);
            Assert.That(Off("Pantalla", "ir a screen", "control:screen:current|title:screen", ["Pantalla"]), Is.True);
        });
    }

    // The place named whole and read as where the window is (banco B cd: s03 «Bluetooth y dispositivos», n5 «Red e
    // Internet», s02 «Cronómetro», u7 «Alarma»: the item chosen in the navigation). The check here names nothing, so
    // only the citation and the state read decide.
    private static JsonObject Navigation(string chosen, params string[] others) => new()
    {
        ["window"] = new JsonObject { ["title"] = "Ventana", ["process"] = "app" },
        ["controls"] = new JsonArray([.. others.Prepend(chosen).Select((name, at) => (JsonNode?)new JsonObject
        {
            ["i"] = at, ["kind"] = "ListItem", ["name"] = name, ["state"] = name == chosen ? "selected" : string.Empty, ["zone"] = "L",
        })]),
    };

    [Test]
    public void APlaceNamedWholeIsProvedOnlyByTheItemTheWindowShowsChosen()
    {
        static bool Off(string cited, string goal, JsonObject view) => ComputerUseSuccessCheck.CitationOffThePlace(
            cited, goal, "control:zzz:current", view, []);
        JsonObject devices = Navigation("Bluetooth y dispositivos", "Sistema", "Red e Internet");
        JsonObject network = Navigation("Red e Internet", "Sistema", "Wi-Fi");
        Assert.Multiple(() =>
        {
            Assert.That(Off("Bluetooth y dispositivos", "ir a bluetooth y dispositivos", devices), Is.False);
            Assert.That(Off("Bluetooth y dispositivos", "ir a dispositivos", devices), Is.False);
            // «Lo mal dicho lo arregla BAXY»: the misspelt place is the item chosen (five letters read it).
            Assert.That(Off("Bluetooth y dispositivos", "ir a bluetoth", devices), Is.False);
            Assert.That(Off("Red e Internet", "ir a internet", network), Is.False);
            Assert.That(Off("Cronómetro", "ir a cronometro", Navigation("Cronómetro", "Alarma")), Is.False);
            Assert.That(Off("Alarma", "ir a la alarma", Navigation("Alarma", "Cronómetro")), Is.False);
            // Counter-cases. A link to the place is not being there (n5: «Wi-Fi» listed, «Red e Internet» chosen).
            Assert.That(Off("Red e Internet > Wi-Fi", "ir a wifi", network), Is.True);
            Assert.That(Off("Wi-Fi", "ir a wi-fi", network), Is.True);
            Assert.That(Off("Sistema", "ir a sistema", devices), Is.True);
            // Another place chosen that holds the name inside a longer one (review r19 D).
            Assert.That(Off("Biblioteca de música", "ir a biblioteca", Navigation("Biblioteca de música", "Tienda")), Is.True);
            Assert.That(Off("Biblioteca", "ir a biblioteca", Navigation("Biblioteca de música", "Tienda")), Is.True);
            // The place chosen, named by its pieces too short to be words.
            Assert.That(Off("Wi-Fi", "ir a wifi", Navigation("Wi-Fi", "Sistema")), Is.False);
        });
    }

    [Test]
    public void TheNamesATranslationGaveAreReadFromTheMissionsState()
    {
        var state = new JsonObject
        {
            ["translations"] = new JsonObject
            {
                ["bandeja"] = new JsonObject { ["names"] = new JsonArray("Inbox", "Bandeja de entrada") },
                ["otra"] = new JsonObject { ["names"] = new JsonArray() },
            },
        };
        Assert.That(ComputerUseMission.TranslatedNames(state), Is.EqualTo(new[] { "Inbox", "Bandeja de entrada" }));
        Assert.That(ComputerUseMission.TranslatedNames(new JsonObject()), Is.Empty);
    }

    // t-scroll-3: «fuentes» typed into Settings' search, its match pressed, the page «Fuentes» in front while the box
    // keeps the query (Settings does not empty it).
    private static JsonArray FontsSteps() =>
    [
        new JsonObject
        {
            ["step"] = 1, ["operation"] = "input.text.type", ["text"] = "fuentes", ["into"] = "Buscar una configuración",
            ["ok"] = true, ["changed"] = true, ["windowTitle"] = "Configuración",
        },
        new JsonObject
        {
            ["step"] = 2, ["operation"] = "input.visible.click", ["label"] = "Fuentes", ["name"] = "Fuentes", ["kind"] = "ListItem",
            ["ok"] = true, ["changed"] = true,
        },
    ];

    private static JsonObject FontsView(bool navigated)
    {
        JsonObject view = View("""
            {"window": {"title": "Configuración", "process": "SystemSettings"},
             "controls": [{"i": 0, "kind": "Edit", "name": "Buscar una configuración", "value": "fuentes", "zone": "TL"},
                          {"i": 1, "kind": "Text", "name": "Fuentes", "zone": "T"},
                          {"i": 2, "kind": "ListItem", "name": "Agency FB", "zone": "C"},
                          {"i": 3, "kind": "ListItem", "name": "Arial", "zone": "C"},
                          {"i": 4, "kind": "ListItem", "name": "Bahnschrift", "zone": "C"},
                          {"i": 5, "kind": "ListItem", "name": "Calibri", "zone": "C"}]}
            """);
        JsonArray before = navigated
            ? new JsonArray("buscar una configuracion", "fuentes", "sistema", "bluetooth y dispositivos", "personalizacion")
            : new JsonArray("buscar una configuracion", "fuentes", "agency fb", "arial", "bahnschrift", "calibri");
        view["controlsBeforeClick"] = new JsonObject { ["2"] = before };
        return view;
    }

    [Test]
    public void T_Scroll_3_AMatchPressedThatHeadsANewPageEndsTheEchoOfAQueryTheBoxKeeps()
    {
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.QueryEchoNames("fuentes", FontsView(navigated: true), FontsSteps(), false), Is.False);
            // Counter-case: the same heading, but the window did not go anywhere since the click.
            Assert.That(ComputerUseSuccessCheck.QueryEchoNames("fuentes", FontsView(navigated: false), FontsSteps(), false), Is.True);
        });
    }

    // Revisión 1 r24, counter-case: «en el explorador andá a imagenes», «imagenes» typed into «Buscar en ETC» and its
    // suggestion pressed. The window went elsewhere (results are new) and its title has a part that is exactly the name,
    // but that part is the query BAXY typed over a page of search results: still the echo, no arrival.
    [TestCase("ETC")]
    [TestCase("imagenes - Resultados de la búsqueda en ETC")]
    public void ASuggestionPressedThatLeavesResultsTitledByTheQueryStaysTheEcho(string typedTitle)
    {
        JsonObject view = View("""
            {"window": {"title": "imagenes - Resultados de la búsqueda en ETC", "process": "explorer"},
             "controls": [{"i": 0, "kind": "Edit", "name": "Buscar en ETC", "value": "imagenes", "zone": "TR"},
                          {"i": 1, "kind": "ListItem", "name": "Imágenes viejas", "zone": "C"},
                          {"i": 2, "kind": "ListItem", "name": "foto imagenes.png", "zone": "C"},
                          {"i": 3, "kind": "ListItem", "name": "imagenes 2023", "zone": "C"},
                          {"i": 4, "kind": "ListItem", "name": "mis imagenes.docx", "zone": "C"}]}
            """);
        view["controlsBeforeClick"] = new JsonObject
        {
            ["2"] = new JsonArray("buscar en etc", "imagenes", "etc", "carpeta a", "carpeta b", "carpeta c"),
        };
        JsonArray steps =
        [
            new JsonObject
            {
                ["step"] = 1, ["operation"] = "input.text.type", ["text"] = "imagenes", ["into"] = "Buscar en ETC",
                ["ok"] = true, ["changed"] = true, ["windowTitle"] = typedTitle,
            },
            new JsonObject
            {
                ["step"] = 2, ["operation"] = "input.visible.click", ["label"] = "imagenes", ["name"] = "imagenes", ["kind"] = "ListItem",
                ["ok"] = true, ["changed"] = true,
            },
        ];
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.QueryEchoNames("imagenes", view, steps, false), Is.True);
            Assert.That(ComputerUseSuccessCheck.Evaluate("title:imagenes|control:imagenes:current|page:imagenes", view, steps, out _), Is.False);
        });
    }

    // Counter-cases: Explorer n8 («imagenes» typed and Enter, no match pressed) and Settings with «sonido» typed and its
    // suggestion shown, not pressed: still the echo.
    [Test]
    public void WithoutAMatchPressedTheBoxKeepingTheQueryStaysTheEcho()
    {
        JsonObject explorer = View("""
            {"window": {"title": "imagenes - Resultados de la búsqueda en ETC", "process": "explorer"},
             "controls": [{"i": 0, "kind": "Edit", "name": "Buscar en ETC", "value": "imagenes", "zone": "TR"},
                          {"i": 1, "kind": "Text", "name": "imagenes", "zone": "T"},
                          {"i": 2, "kind": "ListItem", "name": "Imágenes viejas", "zone": "C"}]}
            """);
        explorer["controlsBeforeClick"] = new JsonObject { ["2"] = new JsonArray("buscar en etc") };
        JsonArray entered =
        [
            new JsonObject { ["step"] = 1, ["operation"] = "input.text.type", ["text"] = "imagenes", ["into"] = "Buscar en ETC", ["ok"] = true },
            new JsonObject { ["step"] = 2, ["operation"] = "input.key.press", ["key"] = "enter", ["ok"] = true },
        ];
        JsonObject settings = View("""
            {"window": {"title": "Configuración", "process": "SystemSettings"},
             "controls": [{"i": 0, "kind": "Edit", "name": "Buscar una configuración", "value": "sonido", "zone": "TL"},
                          {"i": 1, "kind": "ListItem", "name": "Configuración de sonido", "zone": "TL"}]}
            """);
        JsonArray typedOnly =
        [
            new JsonObject { ["step"] = 1, ["operation"] = "input.text.type", ["text"] = "sonido", ["into"] = "Buscar una configuración", ["ok"] = true },
        ];
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.QueryEchoNames("imagenes", explorer, entered, false), Is.True);
            Assert.That(ComputerUseSuccessCheck.QueryEchoNames("sonido", settings, typedOnly, false), Is.True);
        });
    }

    // v3-44: «devices and printers» typed into the Control Panel's box retitled the window; a click by the whole name that
    // left the very same title and the box still holding the query ended nothing. Counter-case (v3-42 r18, sub-goal 1):
    // the same click under the typing's title with the box emptied, or with the title gone to the place, ends the echo.
    [Test]
    public void V3_44_AClickByNameUnderTheTypingsTitleWithTheQueryHeldEndsNoEcho()
    {
        const string Typed = "devices and printers - Panel de control";
        JsonArray steps =
        [
            new JsonObject
            {
                ["step"] = 1, ["operation"] = "input.text.type", ["text"] = "devices and printers", ["into"] = "Cuadro de búsqueda",
                ["ok"] = true, ["changed"] = true, ["windowTitle"] = Typed,
            },
            new JsonObject
            {
                ["step"] = 2, ["operation"] = "input.visible.click", ["label"] = "Devices and Printers", ["name"] = "Devices and Printers",
                ["kind"] = "Hyperlink", ["ok"] = true, ["selected"] = false, ["surfaceChanged"] = true, ["broughtNew"] = true,
            },
        ];
        JsonObject held = View("""
            {"window": {"title": "devices and printers - Panel de control", "process": "explorer"},
             "controls": [{"i": 0, "kind": "Edit", "name": "Cuadro de búsqueda", "value": "devices and printers", "zone": "TR"},
                          {"i": 1, "kind": "Hyperlink", "name": "Devices and Printers", "zone": "C"}]}
            """);
        JsonObject emptied = View(held.ToJsonString());
        emptied["controls"]![0]!["value"] = string.Empty;
        JsonObject retitled = View(held.ToJsonString());
        retitled["window"]!["title"] = "Dispositivos e impresoras";
        retitled["controls"]![0]!["value"] = string.Empty;
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.TitleEchoedTheTyping("devices and printers", steps, held), Is.True);
            Assert.That(ComputerUseSuccessCheck.QueryEchoNames("devices and printers", held, steps, false), Is.True);
            Assert.That(ComputerUseSuccessCheck.TitleEchoedTheTyping("devices and printers", steps, emptied), Is.False);
            Assert.That(ComputerUseSuccessCheck.QueryEchoNames("devices and printers", emptied, steps, false), Is.False);
            Assert.That(ComputerUseSuccessCheck.TitleEchoedTheTyping("devices and printers", steps, retitled), Is.False);
        });
    }

    // v3-39: «windows terminal: open settings and tell me which profile is the default» held on control:configuracion:current,
    // the place itself: like a title, it reads no datum; the model reads it. Counter-cases: the box shows its chosen
    // profile (the worker now says it), a RadioButton «Oscuro» chosen in «Elige tu modo», and an atom that names
    // something other than the place.
    [Test]
    public void V3_39_AnAtomNamingTheGoalsPlaceReadsNoDatum()
    {
        const string Asked = "ir a settings; y responder: tell me which profile is the default";
        const string Check = "control:settings:current|title:settings|page:settings|control:configuracion:current|title:configuracion|mark:settings";
        JsonArray clicked =
        [
            new JsonObject
            {
                ["step"] = 1, ["operation"] = "input.visible.click", ["label"] = "Configuración", ["name"] = "Configuración",
                ["kind"] = "TabItem", ["ok"] = true, ["changed"] = true,
            },
        ];
        JsonObject unread = View("""
            {"window": {"title": "Configuración", "process": "WindowsTerminal"},
             "controls": [{"i": 0, "kind": "TabItem", "name": "Configuración", "state": "selected", "zone": "TL"},
                          {"i": 4, "kind": "ComboBox", "name": "Perfil predeterminado", "state": "collapsed", "zone": "C"}]}
            """);
        JsonObject read = View(unread.ToJsonString());
        read["controls"]![1]!["value"] = "Windows PowerShell";
        const string Colors = "ir a colores; y responder: qué modo está activo";
        JsonObject dark = View("""
            {"window": {"title": "Configuración", "process": "SystemSettings"},
             "controls": [{"i": 0, "kind": "Text", "name": "Colores", "zone": "T"},
                          {"i": 3, "kind": "RadioButton", "name": "Oscuro", "state": "selected", "zone": "C"}]}
            """);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseMission.QuestionDatumUnread(Asked, "control:configuracion:current", unread, clicked, check: Check), Is.True);
            Assert.That(ComputerUseMission.QuestionDatumUnread(Asked, "mark:settings", unread, clicked, check: Check), Is.True);
            Assert.That(ComputerUseMission.QuestionDatumUnread(Asked, "control:configuracion:current", read, clicked, check: Check), Is.False);
            Assert.That(ComputerUseMission.QuestionDatumUnread(Asked, "control:perfil predeterminado:current", unread, clicked, check: Check), Is.False);
            Assert.That(ComputerUseMission.QuestionDatumUnread(Colors, "control:colores:current", dark, [], check: "control:colores:current|title:colores"), Is.False);
            Assert.That(ComputerUseMission.QuestionDatumUnread("ir a settings", "control:configuracion:current", unread, clicked, check: Check), Is.False,
                "a goal without a question");
        });
    }
}
