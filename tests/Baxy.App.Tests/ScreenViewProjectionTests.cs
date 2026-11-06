using System.Text.Json;
using System.Text.Json.Nodes;
using NUnit.Framework;

namespace Baxy.App.Tests;

/// <summary>
/// The view the model reads of a look (src/Baxy.App/ScreenViewProjection.cs): what the reader marked as chosen is said
/// first, apart from the reading order.
/// </summary>
[TestFixture]
public sealed class ScreenViewProjectionTests
{
    // Sonda F019: Steam on its library, the store tab first in the reading order; the model said «quedó en la tienda».
    private const string Steam =
        "{\"version\":2,\"ok\":true,\"error\":\"\"," +
        "\"window\":{\"title\":\"Steam\",\"process\":\"steamwebhelper\",\"hwnd\":77,\"foreground\":true}," +
        "\"controls\":[" +
        "{\"i\":1,\"kind\":\"TabItem\",\"name\":\"Tienda\",\"state\":\"\",\"value\":null}," +
        "{\"i\":2,\"kind\":\"TabItem\",\"name\":\"Biblioteca\",\"state\":\"selected\",\"value\":null}," +
        "{\"i\":3,\"kind\":\"CheckBox\",\"name\":\"Sólo instalados\",\"state\":\"on focused\",\"value\":null}," +
        "{\"i\":4,\"kind\":\"Button\",\"name\":\"Menú\",\"state\":\"collapsed\",\"value\":null}]," +
        "\"controlCount\":4,\"textAuthority\":\"not_read\",\"authority\":\"uia\"}";

    [Test]
    public void WhatIsSelectedOrOnIsSaidBeforeTheControls()
    {
        string view = View(Steam);

        Assert.That(view, Does.StartWith(
            "Ventana «Steam» (steamwebhelper, window 77), al frente\n" +
            "Seleccionados o activados: [2] TabItem «Biblioteca» | [3] CheckBox «Sólo instalados»\n" +
            "Controles:\n" +
            "[1] TabItem «Tienda»\n" +
            "[2] TabItem «Biblioteca» (selected)\n"));
    }

    // Encargo 18 (banco de uso, U45): what the focused control that is no field shows (a terminal's output), as the
    // reader read it, is said under the focus line by line; a cut says only its last lines are there; nothing without it.
    [TestCase(false, "Lo que muestra el foco:\n")]
    [TestCase(true, "Lo que muestra el foco (cortado: sólo sus últimas líneas):\n")]
    public void WhatTheFocusedConsoleShowsIsSaidUnderTheFocus(bool cut, string heading)
    {
        const string Console =
            "{\"version\":2,\"ok\":true,\"error\":\"\"," +
            "\"window\":{\"title\":\"Consola\",\"process\":\"TerminalHost\",\"hwnd\":91,\"foreground\":true," +
            "\"focused\":{\"kind\":\"Text\",\"name\":\"Consola\",\"value\":null,\"i\":0," +
            "\"text\":\"C:\\\\carpeta>ver\\nMicrosoft Windows [Version 10.0]\\nC:\\\\carpeta>\"CUT}}," +
            "\"controls\":[{\"i\":0,\"kind\":\"Text\",\"name\":\"Consola\",\"state\":\"focused\",\"value\":null}]," +
            "\"controlCount\":1,\"textAuthority\":\"not_read\",\"authority\":\"uia\"}";

        string view = View(Console.Replace("CUT", cut ? ",\"textCut\":true" : string.Empty, StringComparison.Ordinal));

        Assert.Multiple(() =>
        {
            Assert.That(view, Does.Contain(
                "Foco: [0] Text «Consola»\n" + heading +
                "C:\\carpeta>ver\nMicrosoft Windows [Version 10.0]\nC:\\carpeta>\nControles:\n"));
            Assert.That(View(Steam), Does.Not.Contain("Lo que muestra el foco"));
        });
    }

    [Test]
    public void NothingChosenSaysNoLine()
    {
        string view = View(Steam.Replace("\"selected\"", "\"\"").Replace("\"on focused\"", "\"off\""));

        Assert.That(view, Does.Not.Contain("Seleccionados"));
    }

    // BAXY Renew al máximo 7.2: the text read off the drawing repeats the names of the controls already listed.
    [Test]
    public void ALineOfTextThatOnlyRepeatsAListedControlsNameIsLeftOutAndCounted()
    {
        string view = View(Steam.Replace(
            "\"textAuthority\":\"not_read\"",
            "\"text\":{\"T\":[\"Tienda\",\" BIBLIOTECA \",\"Comunidad\"],\"C\":[\"Sólo  instalados\",\"Sólo instalados (3)\"]}," +
            "\"textAuthority\":\"windows_media_ocr_lines\""));

        Assert.That(view, Does.EndWith(
            "Texto arriba: Comunidad\n" +
            "Texto centro: Sólo instalados (3)\n" +
            "(3 líneas de texto no se listan: repiten el nombre de un control listado)"));
    }

    // BAXY Renew al máximo 7.3: two «Buscar» told apart by where each sits in the window; a control without a rect
    // has no zone and says none.
    [Test]
    public void AControlSaysItsZoneOnlyWhenTheReaderGaveOne()
    {
        string view = View(Steam.Replace(
            "{\"i\":4,\"kind\":\"Button\",\"name\":\"Menú\",\"state\":\"collapsed\",\"value\":null}",
            "{\"i\":4,\"kind\":\"Button\",\"name\":\"Buscar\",\"state\":\"\",\"value\":null,\"zone\":\"TR\"}," +
            "{\"i\":5,\"kind\":\"Button\",\"name\":\"Buscar\",\"state\":\"\",\"value\":null,\"zone\":\"L\"}," +
            "{\"i\":6,\"kind\":\"Button\",\"name\":\"Buscar\",\"state\":\"\",\"value\":null}"));

        Assert.That(view, Does.Contain(
            "[4] Button «Buscar» (arriba der.)\n" +
            "[5] Button «Buscar» (centro izq.)\n" +
            "[6] Button «Buscar»\n"));
    }

    // Uso-108 (A7): a value the reader cut says it, or a prefix reads as the whole value; a whole value says nothing.
    [Test]
    public void ACutValueSaysHowManyCharactersAreMissing()
    {
        string view = View(Steam.Replace(
            "\"name\":\"Menú\",\"state\":\"collapsed\",\"value\":null",
            "\"name\":\"Menú\",\"state\":\"\",\"value\":\"principio\",\"valueCut\":340"));

        Assert.That(view, Does.Contain("[4] Button «Menú» = principio (valor cortado: faltan 340 caracteres)\n"));
        Assert.That(view, Does.Contain("[1] TabItem «Tienda»\n"));
    }

    // R6-NB-5: a name the reader cut at its end says how many characters it lost; a whole one says nothing.
    [Test]
    public void ACutNameSaysHowManyCharactersAreMissing()
    {
        string view = View(Steam.Replace(
            "\"name\":\"Menú\",",
            "\"name\":\"Menú de una fila muy larga …\",\"nameCut\":42,"));

        Assert.That(view, Does.Contain("[4] Button «Menú de una fila muy larga …» (nombre cortado: faltan 42 caracteres) (collapsed)\n"));
        Assert.That(view, Does.Contain("[1] TabItem «Tienda»\n"));
    }

    // BAXY Renew al máximo (F019, E015): Steam's library read only by OCR («Página principal» is the library's own
    // home) was told «la página principal de Steam» or «la tienda». The place the reader said is in sight comes right
    // after the window, with the text that tells it; a look that said none says no line.
    [Test]
    public void ThePlaceInSightIsSaidRightAfterTheWindow()
    {
        string drawn = Steam.Replace(
            "\"controls\":[",
            "\"place\":{\"application\":\"Steam\",\"name\":\"library\",\"shown\":\"Página principal\"},\"controls\":[");

        Assert.Multiple(() =>
        {
            // With every aid on (sight_places): the application's other places, which app_open opens, beside it.
            Assert.That(View(drawn), Does.StartWith(
                "Ventana «Steam» (steamwebhelper, window 77), al frente\n" +
                "Lugar a la vista: library de Steam (sólo ahí sale «Página principal»)\n" +
                "(los otros lugares de Steam se abren directo, sin pulsar: app_open con appId «Steam» y place " +
                "community, game (placeValue: el nombre del juego), results (placeValue: lo que se busca), store)\n" +
                "Seleccionados o activados: "));
            Assert.That(View(Steam), Does.Not.Contain("Lugar a la vista"));
        });
    }

    // Renew al máximo (w8, falsedades F019): Steam's library with no control, its words read by OCR: «FAVORITOS (324)»
    // was told «tienes 324 juegos» and «no hay botón de Biblioteca» with «BIBLIOTECA» in the text. The view says how
    // such a window is read. Counter-cases: a window with its controls, and one whose text was not read, say nothing.
    [Test]
    public void AWindowDrawnWithoutControlsSaysItsTextIsTheScreensWordsAndPressedByLabel()
    {
        const string drawn =
            "{\"version\":2,\"ok\":true,\"error\":\"\"," +
            "\"window\":{\"title\":\"Steam\",\"process\":\"steamwebhelper\",\"hwnd\":77,\"foreground\":true}," +
            "\"controls\":[],\"controlCount\":0," +
            "\"text\":{\"T\":[\"TIENDA BIBLIOTECA\",\"FAVORITOS (324)\"]},\"textAuthority\":\"windows_media_ocr_lines\"}";
        string withControls = Steam.Replace(
            "\"textAuthority\":\"not_read\"",
            "\"text\":{\"T\":[\"Comunidad\"]},\"textAuthority\":\"windows_media_ocr_lines\"");

        Assert.Multiple(() =>
        {
            Assert.That(View(drawn), Does.Contain("(esta ventana no da sus controles: su «Texto» se leyó de la pantalla tal cual"));
            Assert.That(View(drawn), Does.Contain("que algo no salga en «Controles» no significa que no esté)"));
            Assert.That(View(withControls), Does.Not.Contain("no da sus controles"));
            Assert.That(View(drawn.Replace("windows_media_ocr_lines", "unavailable")), Does.Not.Contain("no da sus controles"));
        });
    }

    private static string View(string lookJson)
    {
        using JsonDocument look = JsonDocument.Parse(lookJson);
        Assert.That(ScreenViewProjection.TryCreate("{\"status\":\"completed\"}", look.RootElement, out string projected), Is.True);
        return (string?)JsonNode.Parse(projected)?["view"] ?? throw new AssertionException("the projection has no view");
    }
}
