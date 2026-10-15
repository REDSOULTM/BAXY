using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Pasada r15b (2026-10-08), la parte del App. v3-43 y v3-61: la mente no dejó final (su suelo honrado murió en su
/// propio veto) y el suelo del App dijo «Lo hice en la aplicación «Panel de control»» a una misión con pregunta, sin el
/// dato. v3-42: «buscar chrome» se dio por cumplido por «Google Chrome» en la lista sin filtrar de Programas y
/// características. t-drag-4: «dibujá una línea horizontal con Pinceles» se dio por hecho tras un único clic que eligió
/// el pincel (hoy dibujar es un límite declarado: la misión para antes). Las situaciones son las de la evidencia (v2-v3-43, v2-v3-61), recortadas a lo que se juzga.
/// </summary>
[TestFixture]
public sealed class CuV3HonestidadR15bTests
{
    // v2-v3-43, último turno: llegó con la página aún «Cargando».
    private const string PowerPlan = """
        {"kind":"operation","operation":"mission.computer.use","polarity":"success","verified":true,"succeeded":true,
         "observed":{"goal":"hacer clic en opciones de energia; y responder: dime qué plan de energía está activo",
          "application":"Panel de control","reached":true,"successCheck":"stepDone:input.visible.click:opciones de energia",
          "stepCount":2,"steps":[
           {"step":1,"operation":"app.open","source":"procedure","appId":"Panel de control","ok":true,"alreadyRunning":false,"changed":true},
           {"step":2,"operation":"input.visible.click","source":"model","label":"Opciones de energía","index":32,"ok":true,
            "cascadeStage":"uia_surface","method":"invoke","surfaceChanged":true,"name":"Opciones de energía","kind":"Hyperlink","changed":true}],
          "window":{"title":"Sistema y seguridad","process":"explorer","requested":true,"foreground":true},
          "joined":false,"satisfiedBy":"stepDone:input.visible.click:opciones de energia",
          "screen":{"title":"Opciones de energía","values":[{"name":"Cargando","value":"0"}],
           "numbers":["Actualizar \"Opciones de energía\" (F5)"]}}}
        """;

    // v2-v3-61, último turno: la pantalla escribía la fecha del último examen.
    private const string LastScan = """
        {"kind":"operation","operation":"mission.computer.use","polarity":"success","verified":true,"succeeded":true,
         "observed":{"goal":"abrir Seguridad de Windows; y responder: decime cuándo fue el último examen de virus",
          "application":"Seguridad de Windows","reached":true,
          "successCheck":"title:Seguridad de Windows|process:Seguridad de Windows","stepCount":1,"steps":[
           {"step":1,"operation":"input.visible.click","source":"model","label":"Protección contra virus y amenazas","index":6,
            "ok":true,"cascadeStage":"uia","method":"select","selected":true,"name":"Protección contra virus y amenazas",
            "kind":"ListItem","changed":true}],
          "window":{"title":"Seguridad de Windows","process":"SecHealthUI","requested":true,"foreground":false},
          "joined":false,"satisfiedBy":"title:Seguridad de Windows",
          "screen":{"title":"Seguridad de Windows","values":[{"name":"Seguridad de Windows","value":"Seguridad de Windows"},
           {"name":"Protección contra virus y amenazas","state":"selected"}],
           "numbers":["Último examen: 08-10-2026 10:28 (examen rápido)","Se encontraron 0 amenazas."]}}}
        """;

    private static JsonObject Situation(string json) => (JsonObject)JsonNode.Parse(json)!;

    [Test]
    public void V3_43_AndV3_61_AQuestionMissionWithoutTheMindsFinalIsNeverLoHice()
    {
        string? plan = OperationFloor.Final(Situation(PowerPlan), english: false);
        string? scan = OperationFloor.Final(Situation(LastScan), english: false);
        Assert.Multiple(() =>
        {
            Assert.That(plan, Is.EqualTo(
                "Llegué a «Panel de control», pero no pude leer en la pantalla la respuesta a «dime qué plan de energía está activo»."));
            Assert.That(scan, Does.StartWith("Llegué a «Seguridad de Windows», pero no pude leer"));
            Assert.That(OperationFloor.Final(Situation(PowerPlan), english: true), Does.StartWith("I got to «Panel de control», but I couldn't read"));
            Assert.That(plan + scan, Does.Not.Contain("Lo hice").And.Not.Contain("Listo"));
        });
    }

    [Test]
    public void AFailedQuestionMissionIsStillToldAsItsFailure()
    {
        JsonObject failed = Situation(PowerPlan);
        failed["verified"] = false;
        failed["succeeded"] = false;
        failed["observed"]!["reached"] = false;
        Assert.That(OperationFloor.Final(failed, english: false) ?? string.Empty, Does.Not.Contain("pero no pude leer"));
    }

    // v2-v3-42: la vista de Programas y características (recortada) tras escribir «chrome» y Enter.
    private static JsonObject Programs(string boxValue) => (JsonObject)JsonNode.Parse($$$"""
        {"window":{"title":"Programas y características","process":"explorer","hwnd":8},
         "controls":[
          {"i":9,"kind":"Edit","name":"Cuadro de búsqueda","value":"{{{boxValue}}}"},
          {"i":20,"kind":"Edit","name":"Título","value":"Programas actualmente instalados"},
          {"i":31,"kind":"ListItem","name":"Google Chrome"},
          {"i":32,"kind":"ListItem","name":"AMD Chipset Software"}],
         "text":{"L":["Nombre","Google Chrome","AMD Chipset Software"],"C":["Google LLC","Advanced Micro Devices, Inc."]}}
        """)!;

    private static readonly JsonArray Searched = (JsonArray)JsonNode.Parse("""
        [{"step":5,"operation":"input.text.type","source":"model","text":"chrome","into":"Cuadro de búsqueda","ok":true,"method":"setvalue"},
         {"step":6,"operation":"input.key.press","source":"rule","key":"enter","ok":true}]
        """)!;

    private const string SearchCheck =
        "title:chrome&stepDone:input.key.press:enter|title:chrome&stepDone:input.visible.click:chrome"
        + "|stepDone:input.text.type&stepDone:input.key.press:enter&text:chrome";

    [Test]
    public void V3_42_AnUnfilteredListThatNamesTheQueryIsNoSearchDone()
    {
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.Evaluate(SearchCheck, Programs(string.Empty), Searched, out _), Is.False,
                "the box no longer holds «chrome»: the list is the installed programs, not the search's results");
            Assert.That(ComputerUseSuccessCheck.Evaluate(SearchCheck, Programs("chrome"), Searched, out string? by), Is.True,
                "the box holds «chrome» and a result besides it names it");
            Assert.That(ComputerUseSuccessCheck.Evaluate(SearchCheck, Programs("chrome"), Searched, out by) ? by : null,
                Is.EqualTo("stepDone:input.text.type&stepDone:input.key.press:enter&text:chrome"));
        });
    }

    [Test]
    public void ATextAtomWithoutASearchTypingKeepsItsOwnRule()
    {
        // No typing carries the needle: nothing is asked of a field (a plain «text:» of a place).
        Assert.That(ComputerUseSuccessCheck.Atom("text:google chrome", Programs(string.Empty), new JsonArray()), Is.True);
    }
}
