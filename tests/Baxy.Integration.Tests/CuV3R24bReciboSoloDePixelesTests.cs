using System.IO;
using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Ronda 24b, «evidencia del banco legible y recibo sólo de píxeles» (banco r23). y12: «elegí el verde» se cerró con el
/// recibo de un clic de invoke sobre el ListItem «Verde» cuyo único efecto era surfaceChanged (el SHA de la ventana) con
/// selected=false; la mirada final no se re-evaluó. e1: el final «25 × 4 = 100» no dejaba en la traza ni en el
/// observado qué control mostró el 100. Las situaciones son las de la evidencia, recortadas a lo que se juzga.
/// </summary>
[TestFixture]
public sealed class CuV3R24bReciboSoloDePixelesTests
{
    private const string ColourCheck = "control:color 1: verde|stepDone:input.visible.click:=verde";

    private static JsonArray Steps(string click) => (JsonArray)JsonNode.Parse($$"""
        [{"step":1,"operation":"app.open","appId":"Paint","ok":true,"changed":true},
         {{click}}]
        """)!;

    // y12 seq 6270: el recibo del swatch, tal cual lo dio el Core (invoke, surfaceChanged, selected=false).
    private const string PixelOnlyClick =
        """{"step":2,"operation":"input.visible.click","label":"Verde","name":"Verde","kind":"ListItem","ok":true,"method":"invoke","surfaceChanged":true,"selected":false,"toggled":false,"absentOrDisabled":false}""";

    private static JsonObject Paint(string colour, string? focused = null, bool namedIndicator = true)
    {
        var controls = new JsonArray(
            new JsonObject { ["i"] = 0, ["kind"] = "ListItem", ["name"] = "Negro", ["state"] = "" },
            new JsonObject { ["i"] = 1, ["kind"] = "ListItem", ["name"] = "Verde", ["state"] = focused == "Verde" ? "focused" : "" },
            new JsonObject { ["i"] = 2, ["kind"] = "ListItem", ["name"] = "Rojo", ["state"] = "" });
        if (namedIndicator)
        {
            controls.Add((JsonNode)new JsonObject { ["i"] = 3, ["kind"] = "Button", ["name"] = $"Color 1: {colour}", ["state"] = "" });
        }

        return new JsonObject
        {
            ["window"] = new JsonObject
            {
                ["title"] = "Sin título - Paint",
                ["process"] = "mspaint",
                ["foreground"] = false,
                ["focused"] = focused is null ? null : new JsonObject { ["kind"] = "ListItem", ["name"] = focused },
            },
            ["controls"] = controls,
        };
    }

    [Test]
    public void Y12_APixelOnlyChoiceNeverClosesOnItsReceipt()
    {
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.PixelOnlyChoice((JsonObject)Steps(PixelOnlyClick)[1]!), Is.True);
            Assert.That(ComputerUseSuccessCheck.EvaluateReceipts(ColourCheck, Steps(PixelOnlyClick), out string? by), Is.False);
            Assert.That(by, Is.Null);
        });
    }

    // The look after it shows «Color 1: Verde»: the state term closes it and becomes the proof.
    [Test]
    public void Y12_TheFinalLookDecidesAndTheStateTermBecomesTheProof()
    {
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate(ColourCheck, Paint("Verde", "Verde"), Steps(PixelOnlyClick), out string? by), Is.True);
            Assert.That(by, Is.EqualTo("control:color 1: verde"));
            // The stepDone term listed first is set aside, never the proof.
            Assert.That(ComputerUseSuccessCheck.Evaluate(
                "stepDone:input.visible.click:=verde|control:color 1: verde", Paint("Verde"), Steps(PixelOnlyClick), out by), Is.True);
            Assert.That(by, Is.EqualTo("control:color 1: verde"));
        });
    }

    // Contracase: the swatch only took the focus and Color 1 is still black: the sub-goal stays open.
    [Test]
    public void Y12_Contracase_AClickThatOnlyFocusedTheSwatchStaysOpen()
    {
        Assert.That(ComputerUseSuccessCheck.Evaluate(ColourCheck, Paint("Negro", "Verde"), Steps(PixelOnlyClick), out string? by), Is.False);
        Assert.That(by, Is.Null);
    }

    // Contracase: a palette whose active indicator has no UIA name never holds in silence.
    [Test]
    public void Y12_Contracase_AnUnnamedIndicatorDoesNotHoldSilently()
    {
        Assert.That(ComputerUseSuccessCheck.Evaluate(
            ColourCheck, Paint("Verde", "Verde", namedIndicator: false), Steps(PixelOnlyClick), out _), Is.False);
    }

    // Revision 1 of r24b (B1), e2 r23 (mission 6216088e): the swatch «Añil» said selected=false and only surfaceChanged,
    // but the look after it found «Color 1: Añil», a name no look before had (MarkAppeared). That is more than pixels:
    // the shade's own stepDone term closes it, on the receipts once the look is read and on the final look.
    private const string BlueCheck =
        "control:=blue:selected|control:=blue:on|stepDone:input.visible.click:=blue|control:=azul:selected|control:=azul:on"
        + "|stepDone:input.visible.click:=azul|stepDone:input.visible.click:=anil|stepDone:input.visible.click:=celeste";

    private const string ShadeClick =
        """{"step":2,"operation":"input.visible.click","label":"Añil","name":"Añil","kind":"ListItem","ok":true,"method":"invoke","surfaceChanged":true,"selected":false,"toggled":false,"absentOrDisabled":false}""";

    private static JsonObject PaintAfterShade() => new()
    {
        ["window"] = new JsonObject
        {
            ["title"] = "Sin título - Paint",
            ["process"] = "mspaint",
            ["focused"] = new JsonObject { ["kind"] = "ListItem", ["name"] = "Añil" },
        },
        ["controls"] = new JsonArray(
            new JsonObject { ["i"] = 0, ["kind"] = "ListItem", ["name"] = "Negro", ["state"] = "" },
            new JsonObject { ["i"] = 1, ["kind"] = "ListItem", ["name"] = "Añil", ["state"] = "focused" },
            new JsonObject { ["i"] = 2, ["kind"] = "Button", ["name"] = "Color 1: Añil", ["state"] = "selected" }),
    };

    [Test]
    public void E2_AShadeWhoseClickBroughtANewNameClosesOnItsOwnTerm()
    {
        JsonArray steps = Steps(ShadeClick);
        steps[1]!["appeared"] = new JsonArray("color 1: anil");
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.PixelOnlyChoice((JsonObject)steps[1]!), Is.False);
            Assert.That(ComputerUseSuccessCheck.EvaluateReceipts(BlueCheck, steps, out string? by), Is.True);
            Assert.That(by, Is.EqualTo("stepDone:input.visible.click:=anil"));
            Assert.That(ComputerUseSuccessCheck.Evaluate(BlueCheck, PaintAfterShade(), steps, out by), Is.True);
            Assert.That(by, Is.EqualTo("stepDone:input.visible.click:=anil"));
            // A learned proof that is only the shade's click reads the same.
            Assert.That(ComputerUseSuccessCheck.Evaluate("stepDone:input.visible.click:=anil", PaintAfterShade(), steps, out _), Is.True);
        });
    }

    // Contracase: before the look after the click is read, its receipt alone does not close it (the look decides).
    [Test]
    public void E2_Contracase_BeforeTheLookTheReceiptAloneDoesNotClose()
    {
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.PixelOnlyChoice((JsonObject)Steps(ShadeClick)[1]!), Is.True);
            Assert.That(ComputerUseSuccessCheck.EvaluateReceipts(BlueCheck, Steps(ShadeClick), out _), Is.False);
        });
    }

    // Revision 1 of r24b (B2): the gallery opened by an earlier step (its names appeared then) never proves a pixel-only
    // choice made in it: «Color 1: Negro» still selected, the y12 check stays open.
    [Test]
    public void B2_ANameBroughtByTheStepThatOpenedTheGalleryProvesNoChoice()
    {
        var steps = (JsonArray)JsonNode.Parse("""
            [{"step":1,"operation":"app.open","appId":"Paint","ok":true,"changed":true},
             {"step":2,"operation":"input.visible.click","label":"Colores","name":"Colores","kind":"Button","ok":true,"surfaceChanged":true,"appeared":["negro","verde","rojo"]},
             {"step":3,"operation":"input.visible.click","label":"Verde","name":"Verde","kind":"ListItem","ok":true,"method":"invoke","surfaceChanged":true,"selected":false,"toggled":false,"absentOrDisabled":false,"appeared":[]}]
            """)!;
        JsonObject view = Paint("Negro", "Verde");
        view["controls"]!.AsArray()[^1]!["state"] = "selected";
        const string check = "control:=verde:selected|control:=verde:on|stepDone:input.visible.click:=verde"
            + "|control:=green:selected|control:=green:on|stepDone:input.visible.click:=green";
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, view, steps, out string? by), Is.False);
            Assert.That(by, Is.Null);
            Assert.That(ComputerUseSuccessCheck.EvaluateReceipts(check, steps, out _), Is.False);
        });
    }

    // Revision 1 of r24b (B3), c5 r23: a ListItem that navigates («Colores» in Settings) says selected=false; the page it
    // brought is new names on the look after it, so «hacer clic en Colores» closes on its receipt.
    [Test]
    public void B3_ANavigatingEntryWhosePageCameClosesOnItsReceipt()
    {
        var steps = (JsonArray)JsonNode.Parse("""
            [{"step":1,"operation":"input.visible.click","label":"Personalización","name":"Personalización","kind":"ListItem","ok":true,"method":"select","selected":true},
             {"step":2,"operation":"input.visible.click","label":"Colores","name":"Colores","kind":"ListItem","ok":true,"method":"invoke","surfaceChanged":true,"selected":false,"toggled":false,"absentOrDisabled":false,"appeared":["elige tu modo","oscuro","manual"]}]
            """)!;
        var view = new JsonObject
        {
            ["window"] = new JsonObject { ["title"] = "Configuración", ["process"] = "SystemSettings" },
            ["controls"] = new JsonArray(
                new JsonObject { ["i"] = 0, ["kind"] = "ListItem", ["name"] = "Colores", ["state"] = "" },
                new JsonObject { ["i"] = 1, ["kind"] = "Text", ["name"] = "Colores", ["state"] = "" },
                new JsonObject { ["i"] = 2, ["kind"] = "ComboBox", ["name"] = "Elige tu modo", ["state"] = "focused" }),
        };
        const string check = "stepDone:input.visible.click:=colores";
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.EvaluateReceipts(check, steps, out string? by), Is.True);
            Assert.That(by, Is.EqualTo(check));
            Assert.That(ComputerUseSuccessCheck.Evaluate(check, view, steps, out by), Is.True);
            Assert.That(by, Is.EqualTo(check));
        });
    }

    // Contracase: a gallery that closes on choosing («Color de fuente → Rojo») brings its own effect and still closes
    // on its receipt; so do a choice the receipt says selected and a plain button press.
    [TestCase("""{"step":2,"operation":"input.visible.click","label":"Rojo","name":"Rojo","kind":"ListItem","ok":true,"surfaceChanged":true,"selected":false,"absentOrDisabled":true}""", "stepDone:input.visible.click:=rojo")]
    [TestCase("""{"step":2,"operation":"input.visible.click","label":"Rojo","name":"Rojo","kind":"ListItem","ok":true,"surfaceChanged":true,"selected":true}""", "stepDone:input.visible.click:=rojo")]
    [TestCase("""{"step":2,"operation":"input.visible.click","label":"Rojo","name":"Rojo","kind":"RadioButton","ok":true,"surfaceChanged":true,"toggled":true}""", "stepDone:input.visible.click:=rojo")]
    [TestCase("""{"step":2,"operation":"input.visible.click","label":"Guardar","name":"Guardar","kind":"Button","ok":true,"surfaceChanged":true,"selected":false}""", "stepDone:input.visible.click:=guardar")]
    public void Contracase_AReceiptWithItsOwnEffectStillCloses(string click, string check)
    {
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.PixelOnlyChoice((JsonObject)Steps(click)[1]!), Is.False);
            Assert.That(ComputerUseSuccessCheck.EvaluateReceipts(check, Steps(click), out string? by), Is.True);
            Assert.That(by, Is.EqualTo(check));
        });
    }

    private static JsonObject Calculator(string display, params string[] history)
    {
        var controls = new JsonArray(
            new JsonObject { ["i"] = 0, ["kind"] = "Button", ["name"] = "Es igual a" },
            new JsonObject { ["i"] = 1, ["kind"] = "Text", ["name"] = $"Se muestra {display}" });
        foreach (string entry in history)
        {
            controls.Add((JsonNode)new JsonObject { ["i"] = controls.Count, ["kind"] = "ListItem", ["name"] = entry });
        }

        return new JsonObject
        {
            ["window"] = new JsonObject { ["title"] = "Calculadora", ["process"] = "CalculatorApp" },
            ["controls"] = controls,
            ["text"] = new JsonObject { ["TL"] = new JsonArray("Calculadora", "Estándar") },
        };
    }

    private static JsonArray Typed() => (JsonArray)JsonNode.Parse("""
        [{"step":1,"operation":"input.text.type","text":"25*4","ok":true},
         {"step":2,"operation":"input.key.press","key":"enter","ok":true,"surfaceChanged":true}]
        """)!;

    // e1 seq 5598: the display «Se muestra 100» is the witness of result:25*4, read from the UIA Text control.
    [Test]
    public void E1_TheResultThatClosedItCarriesItsMeasuredWitness()
    {
        JsonObject view = Calculator("100", "25 × 4= 100");
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate("result:25*4", view, Typed(), out string? by), Is.True);
            JsonObject? witness = ComputerUseSuccessCheck.Witness(by, view);
            Assert.That(witness, Is.Not.Null);
            Assert.That((string?)witness!["atom"], Is.EqualTo("result:25*4"));
            Assert.That((string?)witness["via"], Is.EqualTo("uia.Text"));
            Assert.That((string?)witness["shown"], Is.EqualTo("Se muestra 100"));
            // The trace keeps where it was read, never what it showed.
            Assert.That(ComputerUseSuccessCheck.WitnessLabel(witness), Is.EqualTo("result.uia.text"));
        });
    }

    // Contracase: an Enter that did not evaluate leaves «Se muestra 4» and an empty history: nothing holds and there is
    // no witness to quote.
    [Test]
    public void E1_Contracase_AnEnterThatDidNotEvaluateHasNoWitness()
    {
        JsonObject view = Calculator("4");
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.ResultShows("25*4", view), Is.False);
            Assert.That(ComputerUseSuccessCheck.Evaluate("result:25*4", view, Typed(), out string? by), Is.False);
            Assert.That(ComputerUseSuccessCheck.Witness("result:25*4", view), Is.Null);
            Assert.That(ComputerUseSuccessCheck.Witness(by, view), Is.Null);
        });
    }

    // Revision 1 of r24b (B4): a witness names the journal read it came from, and a count is what the look counted,
    // never the atom's own text.
    [Test]
    public void TheWitnessNamesItsReadAndACountIsMeasured()
    {
        JsonObject view = Calculator("100", "25 × 4= 100", "3 + 3= 6");
        view["readMission"] = "6216088e115d4372b379b40d79a47452";
        Assert.Multiple(() =>
        {
            JsonObject? result = ComputerUseSuccessCheck.Witness("result:25*4", view);
            Assert.That((string?)result?["read"], Is.EqualTo("6216088e115d4372b379b40d79a47452"));
            JsonObject? count = ComputerUseSuccessCheck.Witness("count:ListItem>=2", view);
            Assert.That((string?)count?["via"], Is.EqualTo("count.ListItem"));
            Assert.That((string?)count?["shown"], Is.EqualTo("2"));
            Assert.That(ComputerUseSuccessCheck.WitnessLabel(count!), Is.EqualTo("count.count.listitem"));
            // Contracase: a view with no journal read has no «read».
            Assert.That(ComputerUseSuccessCheck.Witness("result:25*4", Calculator("100"))?.ContainsKey("read"), Is.False);
        });
    }

    // A file's witness is its size and last write time on disk; a file that is not there has none.
    [Test]
    public void AFileIsWitnessedByWhatTheDiskSays()
    {
        string path = Path.Combine(Path.GetTempPath(), $"baxy-r24b-{Guid.NewGuid():N}.txt");
        File.WriteAllText(path, "hola");
        try
        {
            JsonObject? witness = ComputerUseSuccessCheck.Witness("file:" + path, null);
            Assert.Multiple(() =>
            {
                Assert.That((string?)witness?["via"], Is.EqualTo("file"));
                Assert.That((string?)witness?["shown"], Does.StartWith("4 B, "));
                Assert.That((string?)witness?["shown"], Does.Not.Contain(path));
            });
        }
        finally
        {
            File.Delete(path);
        }

        Assert.That(ComputerUseSuccessCheck.Witness("file:" + path, null), Is.Null);
    }

    // A window without a tree (CEF): the witness of a mark is the OCR mark with its ink; a term without exact atoms
    // has none.
    [Test]
    public void AMarkIsWitnessedByItsInkAndAPlaceTermHasNone()
    {
        var view = new JsonObject
        {
            ["window"] = new JsonObject { ["title"] = "Steam" },
            ["controls"] = new JsonArray(new JsonObject { ["i"] = 0, ["kind"] = "Pane", ["name"] = "Steam" }),
            ["textMarks"] = new JsonArray(
                new JsonObject { ["text"] = "TIENDA", ["zone"] = "TL", ["ink"] = "grey" },
                new JsonObject { ["text"] = "BIBLIOTECA", ["zone"] = "TL", ["ink"] = "blue" }),
        };
        Assert.Multiple(() =>
        {
            JsonObject? witness = ComputerUseSuccessCheck.Witness("mark:biblioteca", view);
            Assert.That((string?)witness?["via"], Is.EqualTo("mark.TL"));
            Assert.That((string?)witness?["shown"], Is.EqualTo("BIBLIOTECA ink=blue"));
            Assert.That(ComputerUseSuccessCheck.Witness("title:steam", view), Is.Null);
            Assert.That(ComputerUseSuccessCheck.Witness(null, view), Is.Null);
        });
    }
}
