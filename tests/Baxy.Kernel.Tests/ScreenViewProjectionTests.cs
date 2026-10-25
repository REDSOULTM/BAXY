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

    // Práctica e2e E017: Notepad's «Guardar como», as the look read it (cut to the controls that matter).
    private const string SaveAs =
        "{\"version\":2,\"ok\":true,\"error\":\"\"," +
        "\"window\":{\"title\":\"Guardar como\",\"process\":\"Notepad\",\"hwnd\":9045810,\"foreground\":true,\"modal\":true}," +
        "\"controls\":[" +
        "{\"i\":13,\"kind\":\"TreeItem\",\"name\":\"ana\",\"state\":\"selected\",\"value\":\"ana\"}," +
        "{\"i\":20,\"kind\":\"ComboBox\",\"name\":\"Nombre de archivo:\",\"state\":\"collapsed\",\"value\":\"lista pilas, cables\"}," +
        "{\"i\":21,\"kind\":\"Edit\",\"name\":\"Nombre de archivo:\",\"zone\":\"B\",\"state\":\"focused\",\"value\":\"lista pilas, cables\"}," +
        "{\"i\":26,\"kind\":\"Button\",\"name\":\"Guardar\",\"zone\":\"BR\",\"state\":\"\",\"value\":null,\"shortcut\":\"Alt+G\"}," +
        "{\"i\":27,\"kind\":\"Button\",\"name\":\"Cancelar\",\"zone\":\"BR\",\"state\":\"\",\"value\":null}," +
        "{\"i\":55,\"kind\":\"ToolBar\",\"name\":\"Dirección: C:\\\\Users\\\\ana\\\\BAXY-bench\",\"zone\":\"T\",\"state\":\"\",\"value\":null}]," +
        "\"controlCount\":6,\"textAuthority\":\"not_read\",\"authority\":\"uia\"}";

    private const string SaveFieldLine =
        "[21] Edit «Nombre de archivo:» (abajo) = lista pilas, cables (focused)\n" +
        "(lo que tiene este campo es el nombre que recibe el archivo, en la carpeta que muestra el diálogo, " +
        "C:\\Users\\ana\\BAXY-bench; una ruta entera escrita en él, C:\\…\\nombre.ext, lo guarda en esa ruta)\n" +
        "[26] Button «Guardar»";

    [Test]
    public void ASaveDialogsFileNameSaysItIsTheNameInTheFolderItsAddressShows()
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
            Assert.That(on, Does.Contain(SaveFieldLine));
            Assert.That(on.Split("(lo que tiene este campo").Length, Is.EqualTo(2), "said once, after the edit only");
            Assert.That(off, Is.EqualTo(on.Replace(
                "(lo que tiene este campo es el nombre que recibe el archivo, en la carpeta que muestra el diálogo, " +
                "C:\\Users\\ana\\BAXY-bench; una ruta entera escrita en él, C:\\…\\nombre.ext, lo guarda en esa ruta)\n",
                string.Empty)));
        });
    }

    [Test]
    public void ASaveDialogWithNoAddressListedNamesNoFolder()
    {
        string look = SaveAs.Replace("\"kind\":\"ToolBar\",\"name\":\"Dirección: ", "\"kind\":\"ToolBar\",\"name\":\"Banda ");
        using IDisposable setting = ModelAids.Use(ModelAids.SaveDialogNext);

        string view = (string?)Project("{\"status\":\"completed\"}", look)["view"] ?? string.Empty;

        Assert.That(view, Does.Contain(
            "(lo que tiene este campo es el nombre que recibe el archivo, en la carpeta que muestra el diálogo; " +
            "una ruta entera escrita en él, C:\\…\\nombre.ext, lo guarda en esa ruta)\n"));
    }

    // An «Abrir» dialog has the same edit and no «Guardar»; a message box has neither; a window that is not modal is not
    // the dialog; and the English dialog is the same dialog.
    [TestCase("\"name\":\"Guardar\"", "\"name\":\"&Abrir\"", false)]
    [TestCase("\"kind\":\"Edit\",\"name\":\"Nombre de archivo:\"", "\"kind\":\"Text\",\"name\":\"¿Quiere guardar los cambios?\"", false)]
    [TestCase(",\"modal\":true", "", false)]
    [TestCase("\"name\":\"Guardar\"", "\"name\":\"&Save\"", true)]
    public void OnlyAModalSaveDialogSaysWhatItsFileNameIs(string from, string to, bool said)
    {
        string look = SaveAs.Replace(from, to);
        if (said)
        {
            look = look.Replace("\"name\":\"Nombre de archivo:\"", "\"name\":\"File name:\"")
                .Replace("Dirección: ", "Address: ");
        }

        using IDisposable setting = ModelAids.Use(ModelAids.SaveDialogNext);

        string view = (string?)Project("{\"status\":\"completed\"}", look)["view"] ?? string.Empty;

        Assert.That(view.Contains("(lo que tiene este campo es el nombre que recibe el archivo, en la carpeta que muestra "
            + "el diálogo, C:\\Users\\ana\\BAXY-bench;"), Is.EqualTo(said));
    }

    private static JsonObject Project(string facts, string lookJson = Look)
    {
        using JsonDocument look = JsonDocument.Parse(lookJson);
        Assert.That(ScreenViewProjection.TryCreate(facts, look.RootElement, out string projected), Is.True);
        return JsonNode.Parse(projected) as JsonObject ?? throw new AssertionException("the view is not an object");
    }
}
