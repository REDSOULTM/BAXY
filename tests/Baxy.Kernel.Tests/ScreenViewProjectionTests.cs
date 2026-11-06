using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.App;
using Baxy.Providers.Windows.Infrastructure;
using NUnit.Framework;

namespace Baxy.Kernel.Tests;

/// <summary>
/// The view the model reads of a look (src/Baxy.App/ScreenViewProjection.cs, linked here: the App has no test project):
/// it keeps what the reader returned. A control the worker found several times is listed once with the times it was
/// found (its «repeated» counts the copies after the first), and a line of text that repeats stays each time.
/// </summary>
[TestFixture]
public sealed class ScreenViewProjectionTests
{
    // The receipt as WindowsVisibleControlAdapter writes it: «repeated» only when the worker counted copies.
    private const string Look =
        "{\"version\":2,\"ok\":true,\"error\":\"\"," +
        "\"window\":{\"title\":\"WhatsApp\",\"process\":\"WhatsApp\",\"processId\":42,\"hwnd\":1234," +
        "\"foreground\":true,\"focused\":null}," +
        "\"controls\":[" +
        "{\"i\":1,\"kind\":\"Button\",\"name\":\"Enviar\",\"state\":\"\",\"value\":null}," +
        "{\"i\":2,\"kind\":\"ListItem\",\"name\":\"prueba\",\"state\":\"\",\"value\":null,\"repeated\":1}," +
        "{\"i\":3,\"kind\":\"Button\",\"name\":\"Responder\",\"state\":\"\",\"value\":null,\"repeated\":2}]," +
        "\"controlCount\":3," +
        "\"text\":{\"T\":[\"Abuela\"],\"C\":[\"ok\",\"prueba BAXY\",\"prueba BAXY\"],\"B\":[\"ok\"]}," +
        "\"textAuthority\":\"windows_media_ocr_lines\",\"authority\":\"uia\"}";

    // Encargo 119 (F10): a text in an alphabet the OCR does not have came back as nonsense told as a read («CVIHVIVI yxoav»).
    [Test]
    public void TheRecognizedNoteSaysWhichLanguagesTheOcrReads()
    {
        string look = Look.Replace(
            "\"textAuthority\":\"windows_media_ocr_lines\",",
            "\"textAuthority\":\"windows_media_ocr_lines\",\"textLanguages\":[\"es-MX\",\"en-US\"],", StringComparison.Ordinal);

        JsonObject projected = Project("{\"status\":\"completed\",\"observed\":{\"controlCount\":3}}", look);

        Assert.That((string?)projected["view"], Does.Contain(
            "(ese OCR sólo reconoce es-MX, en-US: un texto en otro alfabeto sale como letras sin sentido; entonces di que no se pudo leer)\nTexto arriba: "));
    }

    [Test]
    public void AControlFoundSeveralTimesSaysTheTimesAndEveryRepeatedLineStays()
    {
        JsonObject projected = Project("{\"status\":\"completed\",\"observed\":{\"controlCount\":3}}");

        Assert.That((string?)projected["view"], Is.EqualTo(
            "Ventana «WhatsApp» (WhatsApp, window 1234), al frente\n" +
            "Controles:\n" +
            "[1] Button «Enviar»\n" +
            "[2] ListItem «prueba» ×2\n" +
            "[3] Button «Responder» ×3\n" +
            "(el «Texto» se reconoció de la imagen de la ventana (OCR): puede leer mal letras y cifras, como una coma " +
            "decimal tomada por un dígito; lo que nombran los controles lo da la propia aplicación y manda sobre ese texto)\n" +
            "Texto arriba: Abuela\n" +
            "Texto centro: ok | prueba BAXY | prueba BAXY\n" +
            "Texto abajo: ok"));
    }

    [Test]
    public void TheKernelsHeaderTravelsAndOnlyItsObservationBecomesTheView()
    {
        JsonObject projected = Project(
            "{\"status\":\"completed\",\"cause\":\"seen\",\"observed\":{\"controlCount\":3},\"observedLimit\":\"projected\"}");

        Assert.That(projected.Select(static fact => fact.Key), Is.EqualTo(new[] { "status", "cause", "view" }));
        Assert.That((string?)projected["status"], Is.EqualTo("completed"));
        Assert.That((string?)projected["cause"], Is.EqualTo("seen"));
    }

    // BAXY Renew cu (C11): a grid item says what the application calls it (Excel's «1» is the header of row 1).
    [Test]
    public void AGridItemSaysWhatTheApplicationCallsIt()
    {
        JsonObject projected = Project("{\"status\":\"completed\"}", Look.Replace(
            "{\"i\":1,\"kind\":\"Button\",\"name\":\"Enviar\",\"state\":\"\",\"value\":null}",
            "{\"i\":1,\"kind\":\"DataItem\",\"name\":\"1\",\"state\":\"\",\"value\":null,\"itemType\":\"Encabezado de fila\"}"));

        Assert.That((string?)projected["view"], Does.Contain("[1] DataItem «1» (tipo: Encabezado de fila)\n"));
    }

    // Renew al máximo (w9-dudas, falsedades F019): Steam's library read only by OCR, «Controles:» / «(ninguno)», was told
    // «no hay más botones en esa ventana». A list the reader says is not whole says so in its heading, an empty one is
    // «none read»; a whole list keeps its plain heading, and with the aid off the view is as before.
    [TestCase("{\"i\":1,\"kind\":\"Button\",\"name\":\"Enviar\",\"state\":\"\",\"value\":null}", 1, "", false)]
    [TestCase("", 0, "", true)]
    [TestCase("{\"i\":1,\"kind\":\"Button\",\"name\":\"Enviar\",\"state\":\"\",\"value\":null}", 4, "", true)]
    [TestCase("{\"i\":1,\"kind\":\"Button\",\"name\":\"Enviar\",\"state\":\"\",\"value\":null}", 1, ",\"partial\":true", true)]
    [TestCase("", 0, ",\"frameOnly\":true", true)]
    public void AListOfControlsTheReaderSaysIsNotWholeSaysSoInItsHeading(string controls, int count, string reading,
        bool notWhole)
    {
        string look = "{\"version\":2,\"ok\":true,\"error\":\"\"," +
            "\"window\":{\"title\":\"Steam\",\"process\":\"steamwebhelper\",\"hwnd\":77,\"foreground\":true}," +
            $"\"controls\":[{controls}],\"controlCount\":{count}{reading}," +
            "\"text\":{\"T\":[\"TIENDA BIBLIOTECA\"]}," +
            (controls.Length == 0 && reading.Length == 0
                ? "\"textAuthority\":\"windows_media_ocr_lines\"}"
                : "\"textAuthority\":\"uia_text\"}");
        string Read() => (string?)Project("{\"status\":\"completed\"}", look)["view"] ?? string.Empty;
        string on;
        string off;
        using (ModelAids.Use(ModelAids.ControlsNotComplete))
        {
            on = Read();
        }

        using (ModelAids.Use("none"))
        {
            off = Read();
        }

        Assert.Multiple(() =>
        {
            Assert.That(on.Contains("Controles (no es la lista completa de la ventana: puede tener más):\n"), Is.EqualTo(notWhole));
            Assert.That(on.Contains("Controles:\n"), Is.EqualTo(!notWhole));
            Assert.That(on, Does.Not.Contain("(ninguno)"));
            Assert.That(on.Contains("(no se leyó ninguno)"), Is.EqualTo(notWhole && controls.Length == 0));
            Assert.That(off, Does.Contain("Controles:\n").And.Not.Contain("no es la lista completa"));
            Assert.That(off.Contains("(ninguno)"), Is.EqualTo(controls.Length == 0));
        });
    }

    // Práctica e2e E017: Notepad's «Guardar como», as the look read it (cut to the controls that matter), with the facts
    // the provider read of the dialog by its structure (window.fileDialog, CommonFileDialog): the address bar was past
    // the look's limit and is not listed.
    private const string SaveAs =
        "{\"version\":2,\"ok\":true,\"error\":\"\"," +
        "\"window\":{\"title\":\"Guardar como\",\"process\":\"Notepad\",\"hwnd\":9045810,\"foreground\":true,\"modal\":true," +
        "\"fileDialog\":{\"folder\":\"C:\\\\Users\\\\ana\\\\BAXY-bench\",\"name\":\"lista pilas, cables\",\"nameIndex\":21," +
        "\"path\":\"C:\\\\Users\\\\ana\\\\BAXY-bench\\\\lista pilas, cables\",\"accept\":\"Guardar\",\"acceptIndex\":26}}," +
        "\"controls\":[" +
        "{\"i\":13,\"kind\":\"TreeItem\",\"name\":\"ana\",\"state\":\"selected\",\"value\":\"ana\"}," +
        "{\"i\":21,\"kind\":\"Edit\",\"name\":\"Nombre de archivo:\",\"zone\":\"B\",\"state\":\"focused\",\"value\":\"lista pilas, cables\"}," +
        "{\"i\":26,\"kind\":\"Button\",\"name\":\"Guardar\",\"zone\":\"BR\",\"state\":\"\",\"value\":null,\"shortcut\":\"Alt+G\"}]," +
        "\"controlCount\":40,\"textAuthority\":\"not_read\",\"authority\":\"uia\"}";

    private const string FileDialogLine =
        "Diálogo de archivos de Windows: carpeta «C:\\Users\\ana\\BAXY-bench»; su campo de nombre [21] tiene «lista pilas, " +
        "cables», que daría C:\\Users\\ana\\BAXY-bench\\lista pilas, cables; una ruta entera escrita en ese campo " +
        "(C:\\…\\nombre.ext) guarda o abre ahí sin recorrer carpetas; «Guardar» [26] lo confirma\n";

    [Test]
    public void AFileDialogSaysItsFolderAndWhatItsNameFieldGivesWhateverTheLookListed()
    {
        string on;
        string off;
        using (ModelAids.Use(ModelAids.SaveDialogNext))
        {
            on = (string?)Project("{\"status\":\"completed\"}", SaveAs)["view"] ?? string.Empty;
        }

        using (ModelAids.Use("none"))
        {
            off = (string?)Project("{\"status\":\"completed\"}", SaveAs)["view"] ?? string.Empty;
        }

        Assert.Multiple(() =>
        {
            Assert.That(on, Does.Contain("es el diálogo modal que bloquea la ventana\n"));
            Assert.That(on, Does.Contain(FileDialogLine));
            Assert.That(on.Split("Diálogo de archivos de Windows").Length, Is.EqualTo(2), "said once");
            Assert.That(off, Is.EqualTo(on.Replace(FileDialogLine, string.Empty)));
        });
    }

    // A place of the address that is no folder of the disk, a name field the look did not list and a dialog with no name
    // field (picking a folder) are said as they are; a window with no fileDialog says nothing, whatever its controls.
    [TestCase("\"folder\":\"C:\\\\Users\\\\ana\\\\BAXY-bench\",", "\"shown\":\"Dirección: Este equipo\",",
        "carpeta «Dirección: Este equipo» (no es una carpeta del disco); su campo de nombre [21] tiene «lista pilas, cables»")]
    [TestCase(",\"path\":\"C:\\\\Users\\\\ana\\\\BAXY-bench\\\\lista pilas, cables\"", "",
        "su campo de nombre [21] tiene «lista pilas, cables»; una ruta entera")]
    [TestCase("\"nameIndex\":21,", "", "; su campo de nombre tiene «lista pilas, cables», que daría")]
    [TestCase("\"acceptIndex\":26", "\"acceptIndex\":null", "; «Guardar» lo confirma\n")]
    [TestCase(",\"fileDialog\":{", ",\"other\":{", null)]
    public void AFileDialogLineSaysOnlyWhatWasRead(string from, string to, string? expected)
    {
        using IDisposable setting = ModelAids.Use(ModelAids.SaveDialogNext);

        string view = (string?)Project("{\"status\":\"completed\"}", SaveAs.Replace(from, to))["view"] ?? string.Empty;

        if (expected is null)
            Assert.That(view, Does.Not.Contain("Diálogo de archivos"));
        else
            Assert.That(view, Does.Contain(expected));
    }

    // Prueba en vivo de la versión final (renew_v6, «abre la biblioteca de Steam»): Steam opened with no place, and six
    // looks at its store, read only by OCR, said «Lugar a la vista: store» and nothing else until the turn's calls ran
    // out. The view says beside the place in sight the application's other places, which app_open opens directly.
    private const string StoreInSight =
        "{\"version\":2,\"ok\":true,\"error\":\"\"," +
        "\"window\":{\"title\":\"Steam\",\"process\":\"steamwebhelper\",\"hwnd\":19662756,\"foreground\":false}," +
        "\"place\":{\"application\":\"Steam\",\"name\":\"store\",\"shown\":\"store.steampowered.com\"}," +
        "\"controls\":[],\"controlCount\":0," +
        "\"text\":{\"T\":[\"TIENDA | BIBLIOTECA COMUNIDAD\",\"https://store.steampowered.com/\"]}," +
        "\"textAuthority\":\"windows_media_ocr_lines\",\"authority\":\"uia\"}";

    [Test]
    public void APlaceInSightSaysTheApplicationsOtherPlacesThatAppOpenOpens()
    {
        string on;
        string off;
        using (ModelAids.Use(ModelAids.SightPlaces))
        {
            on = (string?)Project("{\"status\":\"completed\"}", StoreInSight)["view"] ?? string.Empty;
        }

        using (ModelAids.Use("none"))
        {
            off = (string?)Project("{\"status\":\"completed\"}", StoreInSight)["view"] ?? string.Empty;
        }

        const string others = "(los otros lugares de Steam se abren directo, sin pulsar: app_open con appId «Steam» y "
            + "place community, game (placeValue: el nombre del juego), library, results (placeValue: lo que se busca))\n";
        Assert.Multiple(() =>
        {
            Assert.That(on, Does.Contain(
                "Lugar a la vista: store de Steam (sólo ahí sale «store.steampowered.com»)\n" + others));
            Assert.That(off, Is.EqualTo(on.Replace(others, string.Empty)));
        });
    }

    // An application the data give no other place says no line; nor does a look that says no place in sight.
    [TestCase("\"name\":\"store\"", "\"name\":\"store\"", true)]
    [TestCase("\"application\":\"Steam\"", "\"application\":\"Bloc de notas\"", false)]
    [TestCase("\"place\":{\"application\":\"Steam\",\"name\":\"store\",\"shown\":\"store.steampowered.com\"},", "", false)]
    public void OnlyAPlaceInSightOfAnApplicationWithOtherPlacesSaysThem(string from, string to, bool said)
    {
        using IDisposable setting = ModelAids.Use(ModelAids.SightPlaces);

        string view = (string?)Project("{\"status\":\"completed\"}", StoreInSight.Replace(from, to))["view"] ?? string.Empty;

        Assert.That(view.Contains("(los otros lugares de"), Is.EqualTo(said));
    }

    // Práctica e2e E014 («abre la configuración de sonido», c3-junto-s0, 2026-10-25): app.open opened Settings at sound,
    // and the look, the same as in the runs that stopped there, did not say the window was where it was asked; the
    // model pressed «Sonido» in the breadcrumb and went on for 15 calls. Where the place in sight is the one this turn's
    // app.open asked of that application, the view says so, and the application's other places (sight_places), an
    // invitation to go elsewhere nobody asked for, are left out.
    private static readonly (string Application, string Place) AskedStore = ("steam", "store");

    [Test]
    public void ThePlaceInSightThatThisTurnsAppOpenAskedForIsSaidSoWithoutTheOtherPlaces()
    {
        string asked;
        string none;
        using (ModelAids.Use(ModelAids.SightPlaces + "," + ModelAids.AskedPlace))
        {
            asked = View(StoreInSight, AskedStore);
            none = View(StoreInSight, null);
        }

        Assert.Multiple(() =>
        {
            Assert.That(asked, Does.Contain(
                "Lugar a la vista: store de Steam (sólo ahí sale «store.steampowered.com»): es el que pidió app_open en "
                + "este turno\n"));
            Assert.That(asked, Does.Not.Contain("(los otros lugares de"));
            Assert.That(none, Does.Contain("(los otros lugares de Steam"), "no place asked in the turn: as before");
            Assert.That(none, Does.Not.Contain("pidió app_open"));
        });
    }

    // A place in sight other than the one asked says which was asked, and the other places stay (sight_places).
    [Test]
    public void APlaceInSightOtherThanTheAskedOneSaysWhichWasAskedAndTheOtherPlaces()
    {
        using IDisposable setting = ModelAids.Use(ModelAids.SightPlaces + "," + ModelAids.AskedPlace);

        string view = View(StoreInSight, ("Steam", "library"));

        Assert.That(view, Does.Contain(
            "Lugar a la vista: store de Steam (sólo ahí sale «store.steampowered.com»), no el que pidió app_open en "
            + "este turno (library)\n(los otros lugares de Steam se abren directo"));
    }

    // Revisión w11-rev4: a place that declares nothing it shows is never found in sight, so another one found is no proof
    // it is not there: a game's page shows the store's address too («store.steampowered.com», as the data say), and
    // «no el que pidió app_open (game)» was said with the game's page in sight. Only a place whose own text could be read
    // and was not is told as not the one in sight; else the view is as with no place asked.
    [Test]
    public void APlaceAskedThatDeclaresNothingShownIsNotToldAsNotInSight()
    {
        string game;
        string before;
        using (ModelAids.Use(ModelAids.SightPlaces + "," + ModelAids.AskedPlace))
        {
            game = View(StoreInSight, ("Steam", "game"));
            before = View(StoreInSight, null);
        }

        Assert.Multiple(() =>
        {
            Assert.That(game, Does.Not.Contain("pidió app_open"));
            Assert.That(game, Is.EqualTo(before));
        });
    }

    // A place asked of another application says nothing; with the aid off the view is as it was, asked or not.
    [Test]
    public void APlaceAskedOfAnotherApplicationOrWithTheAidOffChangesNothing()
    {
        string other;
        string off;
        string before;
        using (ModelAids.Use(ModelAids.SightPlaces + "," + ModelAids.AskedPlace))
        {
            other = View(StoreInSight, ("Epic Games Launcher", "store"));
            before = View(StoreInSight, null);
        }

        using (ModelAids.Use(ModelAids.SightPlaces))
        {
            off = View(StoreInSight, AskedStore);
        }

        Assert.Multiple(() =>
        {
            Assert.That(other, Is.EqualTo(before));
            Assert.That(off, Is.EqualTo(before));
        });
    }

    // Revisión de nb-w11-quieto: once Settings at Sonido says its place, a look with no place asked (Settings opened
    // with none, or asked_place off) listed its other 51 places, a block that invites going to them. An application
    // with more places than ScreenViewProjection.MaximumListedPlaces says only that app_open opens them directly, and how
    // many; one with few (Steam, 5) still lists them.
    private const string SoundInSight =
        "{\"version\":2,\"ok\":true,\"error\":\"\"," +
        "\"window\":{\"title\":\"Configuración\",\"process\":\"SystemSettings\",\"hwnd\":19925212,\"foreground\":true}," +
        "\"place\":{\"application\":\"Configuración\",\"name\":\"sound\",\"shown\":\"Elegir dónde reproducir el sonido\"}," +
        "\"controls\":[{\"i\":20,\"kind\":\"Button\",\"name\":\"Sonido\",\"state\":\"\",\"value\":null}],\"controlCount\":1," +
        "\"textAuthority\":\"not_read\",\"authority\":\"uia\"}";

    [Test]
    public void AnApplicationWithManyPlacesSaysOnlyThatAppOpenOpensThemNotTheirNames()
    {
        string view;
        using (ModelAids.Use(ModelAids.SightPlaces))
        {
            view = View(SoundInSight, null);
        }

        Assert.Multiple(() =>
        {
            Assert.That(view, Does.Contain(
                "Lugar a la vista: sound de Configuración (sólo ahí sale «Elegir dónde reproducir el sonido»)\n" +
                "(Configuración se abre directo, sin pulsar, en otros 51 lugares: app_open con appId «Configuración» y "
                + "su place)\n"));
            Assert.That(view, Does.Not.Contain("accessibility"));
            Assert.That(Baxy.Kernel.Operations.ApplicationPlaces.PlacesOf("Steam"),
                Has.Count.LessThanOrEqualTo(ScreenViewProjection.MaximumListedPlaces), "Steam's places are still listed");
        });
    }

    private static string View(string lookJson, (string Application, string Place)? asked)
    {
        using JsonDocument look = JsonDocument.Parse(lookJson);
        Assert.That(ScreenViewProjection.TryCreate("{\"status\":\"completed\"}", look.RootElement, out string projected,
            asked), Is.True);
        return (string?)JsonNode.Parse(projected)?["view"] ?? throw new AssertionException("the view is not an object");
    }

    // Práctica V5E023 («en el Notepad que tengo abierto, agrega al final …»): the look as it read the Notepad, with where
    // the reader found the caret of its focused document («caret»), or nothing said of it.
    private static string NotepadLook(string caret) =>
        "{\"version\":2,\"ok\":true,\"error\":\"\"," +
        "\"window\":{\"title\":\"borrador.txt: Bloc de notas\",\"process\":\"Notepad\",\"hwnd\":2688888,\"foreground\":false," +
        "\"focused\":{\"kind\":\"Document\",\"name\":\"Editor de texto\"," +
        "\"value\":\"Hola equipo, les cuento que el viernes no hay reunión.\",\"i\":0" + caret + "}}," +
        "\"controls\":[" +
        "{\"i\":0,\"kind\":\"Document\",\"name\":\"Editor de texto\",\"zone\":\"C\",\"state\":\"focused\"," +
        "\"value\":\"Hola equipo, les cuento que el viernes no hay reunión.\"}," +
        "{\"i\":24,\"kind\":\"Text\",\"name\":\"Línea 1, Columna 1\",\"zone\":\"BL\",\"state\":\"\",\"value\":null}]," +
        "\"controlCount\":2,\"textAuthority\":\"not_read\",\"authority\":\"uia\"}";

    private const string NotepadFocus =
        "Foco: [0] Document «Editor de texto» = Hola equipo, les cuento que el viernes no hay reunión.";

    [TestCase("start", " (cursor al principio del texto: lo que se escriba va antes de lo que ya tiene)")]
    [TestCase("end", " (cursor al final del texto: lo que se escriba va después de lo que ya tiene)")]
    [TestCase("middle", " (cursor en medio del texto: lo que se escriba va ahí, ni al principio ni al final)")]
    [TestCase("selection", " (hay texto seleccionado: lo que se escriba lo reemplaza)")]
    public void TheFocusedTextSaysWhereItsCaretIs(string caret, string note)
    {
        string look = NotepadLook(",\"caret\":\"" + caret + "\"");
        string on;
        string off;
        using (ModelAids.Use(ModelAids.CaretPlace))
        {
            on = (string?)Project("{\"status\":\"completed\"}", look)["view"] ?? string.Empty;
        }

        using (ModelAids.Use("none"))
        {
            off = (string?)Project("{\"status\":\"completed\"}", look)["view"] ?? string.Empty;
        }

        Assert.Multiple(() =>
        {
            Assert.That(on, Does.Contain(NotepadFocus + note + "\n"));
            Assert.That(on.Split("cursor").Length + on.Split("seleccionado:").Length, Is.EqualTo(3), "said once, on the focus");
            Assert.That(off, Is.EqualTo(on.Replace(note, string.Empty)), "with the aid off the view is as before");
        });
    }

    // Nothing is said of a caret the reader did not read (no TextPattern, a password, an empty text) or named otherwise.
    [TestCase("")]
    [TestCase(",\"caret\":\"\"")]
    [TestCase(",\"caret\":\"line 1\"")]
    public void AFocusWhoseCaretWasNotReadSaysNothingOfIt(string caret)
    {
        using IDisposable setting = ModelAids.Use(ModelAids.CaretPlace);

        string view = (string?)Project("{\"status\":\"completed\"}", NotepadLook(caret))["view"] ?? string.Empty;

        Assert.Multiple(() =>
        {
            Assert.That(view, Does.Contain(NotepadFocus + "\n"));
            Assert.That(view, Does.Not.Contain("cursor").And.Not.Contain("seleccionado"));
        });
    }

    // uso-89 (diag-b5bd, R06, 5 of 6): the look at the ranking page in Edge, its frame's controls (cut to a few) and the
    // text the provider read by OCR, as it came; the page says «El faro del norte - calificacion 8,9».
    private const string RankingOcr =
        "\"text\":{\"T\":[\"Ranking de prueba\",\"C : C) File C:/Users/baxy/BAXY-bench/ranking/ranking.html\"," +
        "\"1 _ Rio de inviemo - calificacion 724\"," +
        "\"1 _ Rio de invlemo - calificacion 724\",\"2. El del norte - calificaclon 829\"," +
        "\"2. El åro del norte - calificacion\",\"3 _ Ciudad de papel - calificacion 8.1\"]}," +
        "\"textAuthority\":\"windows_media_ocr_lines\",\"authority\":\"uia\"}";

    private const string RankingFrame =
        "{\"version\":2,\"ok\":true,\"error\":\"\"," +
        "\"window\":{\"title\":\"Ranking de prueba - Microsoft Edge\",\"process\":\"msedge\",\"hwnd\":131406,\"foreground\":true}," +
        "\"controls\":[" +
        "{\"i\":3,\"kind\":\"Button\",\"name\":\"Back\",\"zone\":\"TL\",\"state\":\"\",\"value\":null}," +
        "{\"i\":16,\"kind\":\"TabItem\",\"name\":\"Ranking de prueba\",\"zone\":\"TL\",\"state\":\"selected\",\"value\":null}," +
        "{\"i\":19,\"kind\":\"Pane\",\"name\":\"Ranking de prueba - Microsoft Edge\",\"zone\":\"C\",\"state\":\"\",\"value\":null}]," +
        "\"controlCount\":3," + RankingOcr;

    // The next look, once the page's tree was there: its ListItems say the page's words, and the OCR still came.
    private const string RankingTree =
        "{\"version\":2,\"ok\":true,\"error\":\"\"," +
        "\"window\":{\"title\":\"Ranking de prueba - Microsoft Edge\",\"process\":\"msedge\",\"hwnd\":131406,\"foreground\":true}," +
        "\"controls\":[" +
        "{\"i\":14,\"kind\":\"Document\",\"name\":\"Ranking de prueba\",\"zone\":\"C\",\"state\":\"readonly\",\"value\":null}," +
        "{\"i\":15,\"kind\":\"ListItem\",\"name\":\"Rio de invierno - calificacion 7,4\",\"zone\":\"T\",\"state\":\"\",\"value\":null}," +
        "{\"i\":17,\"kind\":\"ListItem\",\"name\":\"El faro del norte - calificacion 8,9\",\"zone\":\"T\",\"state\":\"\",\"value\":null}," +
        "{\"i\":19,\"kind\":\"ListItem\",\"name\":\"Ciudad de papel - calificacion 8,1\",\"zone\":\"T\",\"state\":\"\",\"value\":null}]," +
        "\"controlCount\":4," + RankingOcr;

    // uso-89: Windows.Media.Ocr gives each line's text and box and no confidence (OcrLine, OcrWord), and in R06 the model
    // told its «829» as the page's. Where the window gives its controls, the view says its text was recognized from the
    // image, may misread letters and digits, and that what the controls name comes from the application; every line
    // stays. A window drawn without controls keeps its own note; with the aid off the view is as before.
    private const string RecognizedNote = "(el «Texto» se reconoció de la imagen de la ventana (OCR): puede leer mal "
        + "letras y cifras, como una coma decimal tomada por un dígito; lo que nombran los controles lo da la propia "
        + "aplicación y manda sobre ese texto)\nTexto arriba: ";

    private static (string On, string Off) Both(string look)
    {
        string on;
        string off;
        using (ModelAids.Use(ModelAids.ScreenTextRecognized))
        {
            on = (string?)Project("{\"status\":\"completed\"}", look)["view"] ?? string.Empty;
        }

        using (ModelAids.Use("none"))
        {
            off = (string?)Project("{\"status\":\"completed\"}", look)["view"] ?? string.Empty;
        }

        return (on, off);
    }

    [Test]
    public void TextRecognizedFromTheImageBesideTheControlsSaysSoBeforeIt()
    {
        (string on, string off) = Both(RankingFrame);

        Assert.Multiple(() =>
        {
            Assert.That(on, Does.Contain(RecognizedNote + "C : C) File"));
            Assert.That(on, Does.Contain("2. El del norte - calificaclon 829 | 2. El åro del norte - calificacion"));
            Assert.That(on, Does.Not.Contain("del texto reconocido no se listan"));
            Assert.That(off, Does.Not.Contain("(OCR)"));
            Assert.That(off.Replace(RecognizedNote, "Texto arriba: "), Is.EqualTo(on.Replace(RecognizedNote, "Texto arriba: ")));
        });
    }

    // uso-89: with the page's ListItems listed, the OCR lines that are their names misread («calificaclon 829» for
    // «calificacion 8,9», «724» for «7,4») are left out and counted; the line no control names stays, after the note.
    [Test]
    public void AnOcrLineThatIsAListedNameMisreadIsLeftOutAndCounted()
    {
        (string on, string off) = Both(RankingTree);

        Assert.Multiple(() =>
        {
            Assert.That(on, Does.Contain(RecognizedNote + "C : C) File C:/Users/baxy/BAXY-bench/ranking/ranking.html\n"));
            Assert.That(on, Does.Not.Contain("829").And.Not.Contain("724").And.Not.Contain("8.1"));
            Assert.That(on, Does.Contain("[17] ListItem «El faro del norte - calificacion 8,9»"));
            Assert.That(on, Does.Contain("(5 líneas del texto reconocido no se listan: repetían el nombre de un "
                + "control listado con letras o cifras mal leídas)"));
            Assert.That(on, Does.Contain("(1 líneas de texto no se listan: repiten el nombre de un control listado)"));
            Assert.That(off, Does.Contain("2. El del norte - calificaclon 829").And.Not.Contain("texto reconocido"));
        });
    }

    // Another line with the same words and other figures is another thing on screen, and stays; so does one that adds a
    // figure to a name that has none (a count beside a check box).
    [TestCase("3 _ Ciudad de papel - calificacion 5432")]
    [TestCase("Rio de invierno - calificacion (3)")]
    public void AnOcrLineWithTheSameWordsAndOtherFiguresStays(string line)
    {
        string look = RankingTree.Replace("\"3 _ Ciudad de papel - calificacion 8.1\"", $"\"{line}\"")
            .Replace("\"Rio de invierno - calificacion 7,4\"", "\"Rio de invierno - calificacion\"");
        (string on, _) = Both(look);

        Assert.That(on, Does.Contain(line));
    }

    // Uso-108 (B5): the line of a look cut by its limit names the way to what it left out; only a cut look has that line.
    [Test]
    public void TheCutLineNamesWantedAndAWholeLookHasNoSuchLine()
    {
        const string Cut = "{\"controls\":[{\"i\":0,\"kind\":\"Button\",\"name\":\"Guardar\",\"state\":\"\",\"value\":null}],\"controlCount\":38}";
        const string Whole = "{\"controls\":[{\"i\":0,\"kind\":\"Button\",\"name\":\"Guardar\",\"state\":\"\",\"value\":null}],\"controlCount\":1}";
        string on;
        string whole;
        string off;
        using (ModelAids.Use(ModelAids.CutNamesWanted))
        {
            on = (string?)Project("{\"status\":\"completed\"}", Cut)["view"] ?? string.Empty;
            whole = (string?)Project("{\"status\":\"completed\"}", Whole)["view"] ?? string.Empty;
        }

        using (ModelAids.Use("none"))
        {
            off = (string?)Project("{\"status\":\"completed\"}", Cut)["view"] ?? string.Empty;
        }

        Assert.Multiple(() =>
        {
            Assert.That(on, Does.Contain("(+37 más, sin listar por el tope: wanted los busca)"));
            Assert.That(whole, Does.Not.Contain("wanted"));
            Assert.That(off, Does.Contain("(+37 más, sin listar por el tope)"));
        });
    }

    // Uso-108 (B15): what wanted did not find is said, beside the cut; nothing when the receipt has no such words.
    [Test]
    public void AWantedThatFoundNothingIsSaid()
    {
        const string Cut = "{\"controls\":[{\"i\":0,\"kind\":\"Button\",\"name\":\"Guardar\",\"state\":\"\",\"value\":null}],\"controlCount\":9";
        string said = (string?)Project("{\"status\":\"completed\"}", Cut + ",\"wantedMissing\":[\"firmas\",\"plantillas\"]}")["view"] ?? string.Empty;
        string plain = (string?)Project("{\"status\":\"completed\"}", Cut + "}")["view"] ?? string.Empty;

        Assert.Multiple(() =>
        {
            // Review 16, I3: a row scrolled out of the list is not walked: only what is in sight can be said not to have it.
            Assert.That(said, Does.Contain("(ningún control a la vista lleva «firmas», «plantillas» en su nombre)"));
            Assert.That(plain, Does.Not.Contain("ningún control"));
        });
    }

    [Test]
    public void AWindowDrawnWithoutControlsKeepsItsOwnNoteOnly()
    {
        string drawn = RankingFrame.Replace(
            "{\"i\":3,\"kind\":\"Button\",\"name\":\"Back\",\"zone\":\"TL\",\"state\":\"\",\"value\":null}," +
            "{\"i\":16,\"kind\":\"TabItem\",\"name\":\"Ranking de prueba\",\"zone\":\"TL\",\"state\":\"selected\",\"value\":null},", "")
            .Replace("\"controlCount\":3", "\"controlCount\":1");
        string view = (string?)Project("{\"status\":\"completed\"}", drawn)["view"] ?? string.Empty;

        Assert.That(view, Does.Contain("no da sus controles").And.Not.Contain("(OCR)"));
    }

    private static JsonObject Project(string facts, string lookJson = Look)
    {
        using JsonDocument look = JsonDocument.Parse(lookJson);
        Assert.That(ScreenViewProjection.TryCreate(facts, look.RootElement, out string projected), Is.True);
        return JsonNode.Parse(projected) as JsonObject ?? throw new AssertionException("the view is not an object");
    }
}
