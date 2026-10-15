using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Ronda 24 (pasada r23, v3-53 t1): the done cited «Silenciar 'Audio del escritorio'», a box a verified click turned on,
/// and was refused «seen_at_start» because the citation lost its closing quote. One normalizer (Bare) for both sides,
/// and a control its own click changed by identity is new though its name showed before. Twins of
/// tests/test_cu_r24_llegada_por_el_acto.py; the weak final's twins are tests/data/cu_floor_twins.json
/// («cu-weak-done-seen-*»). Estabilización R16: the done itself is judged by the mind alone (the App's twin
/// EvidenceRefusal, ChangedByItsClick and TowardGoal went; their cases live in those Python twins and in
/// tests/test_cu_estab_r16_juez_unico.py); here stay what the App still reads: the slot written, the form left
/// unsaved, the field brought and the click that changed its own control.
/// </summary>
[TestFixture]
public sealed class ComputerUseR24ArrivalTests
{
    [TestCase("«Silenciar 'Audio del escritorio'»", "silenciar 'audio del escritorio'")]
    [TestCase("Silenciar 'Audio del escritorio'", "silenciar 'audio del escritorio'")]
    [TestCase("'Fecha de modificación'", "fecha de modificacion")]
    [TestCase("«Foo", "foo")]
    [TestCase("Foo»", "foo")]
    [TestCase("rock 'n' roll", "rock 'n' roll")]
    public void BareDropsOnlyTheWrappingQuotes(string text, string bare) =>
        Assert.That(ComputerUseSuccessCheck.Bare(text), Is.EqualTo(bare));

    // Revisión 1 de r24 (B2, v3-08): the OneNote view of the mind's test, «ponele de título Lista del super».
    private static JsonObject OneNoteView(bool inSearch) => (JsonObject)JsonNode.Parse(inSearch
        ? """
          {"window": {"title": "Sin título - APP", "process": "APP"},
           "controls": [{"i": 40, "kind": "Edit", "name": "Buscar", "state": "focused", "value": "Lista del super"},
                        {"i": 47, "kind": "Document", "name": "Título de página"},
                        {"i": 48, "kind": "Document", "name": "Cuerpo de página"}]}
          """
        : """
          {"window": {"title": "Sin título - APP", "process": "APP"},
           "controls": [{"i": 40, "kind": "Button", "name": "Buscar"},
                        {"i": 47, "kind": "Document", "name": "Título de página", "state": "focused", "value": "Lista del super"},
                        {"i": 48, "kind": "Document", "name": "Cuerpo de página"}]}
          """)!;

    private static JsonArray TypedInto(string field) => new()
    {
        new JsonObject
        {
            ["step"] = 3, ["operation"] = "input.text.type", ["text"] = "Lista del super", ["into"] = field, ["ok"] = true,
            ["changed"] = true,
        },
    };

    private const string OneNoteFirstLook = "sin titulo - app\ntitulo de pagina\n";

    [Test]
    public void TheTitleTypedIntoTheTitleFieldIsDone()
    {
        const string goal = "ponele de título Lista del super";
        JsonArray steps = TypedInto("Título de página");
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.SlotWritten("Lista del super", goal, OneNoteView(false), steps, OneNoteFirstLook), Is.True);
        });
    }

    [Test]
    public void TheTitleTypedIntoASearchBoxIsNoTitle()
    {
        const string goal = "ponele de título Lista del super";
        JsonArray steps = TypedInto("Buscar");
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.SlotWritten("Lista del super", goal, OneNoteView(true), steps, OneNoteFirstLook), Is.False);
            // A search goal never: its proof is a result line.
            Assert.That(ComputerUseSuccessCheck.SlotWritten("receta", "buscar receta", OneNoteView(true), TypedInto("Buscar"), OneNoteFirstLook), Is.False);
        });
    }

    // Revisión 2 de r24 (B1): «buscar receta», a click on the empty box «Buscar», then «receta» typed into it. The click
    // takes no credit for the value the typing wrote, and a search never goes by a value.
    private static JsonObject SearchView(string kind, string name, string value, string before) => (JsonObject)JsonNode.Parse("""
        {"window": {"title": "Notas - APP", "process": "APP"},
         "controls": [{"id": "q", "kind": "KIND", "name": "NAME", "value": "VALUE", "state": "focused"},
                      {"id": "h", "kind": "Button", "name": "Inicio"}],
         "clickedBefore": {"2": {"id": "q", "name": "NAME", "value": "BEFORE"}}}
        """.Replace("KIND", kind, StringComparison.Ordinal).Replace("NAME", name, StringComparison.Ordinal)
        .Replace("VALUE", value, StringComparison.Ordinal).Replace("BEFORE", before, StringComparison.Ordinal))!;

    private static JsonObject Step(int step, string operation, string key, string text, string? into = null)
    {
        var node = new JsonObject { ["step"] = step, ["operation"] = operation, ["ok"] = true, [key] = text, ["changed"] = true };
        if (into is not null)
        {
            node["into"] = into;
        }

        return node;
    }

    [Test]
    public void TheSearchBoxClickedThenTypedIntoIsNoArrival()
    {
        JsonObject view = SearchView("Edit", "Buscar", "receta", string.Empty);
        // The App tells the mind the click changed its box (the value the typing wrote); the mind's judge never takes
        // that change for an arrival in a search (tests/test_cu_r24_llegada_por_el_acto.py, r2_b1).
        Assert.That(ComputerUseSuccessCheck.ChangedByClick(view, (JsonObject)view["clickedBefore"]!), Is.EqualTo(new[] { 2 }));
    }

    // Revisión 3 de r24 (B1): «ponele de nombre «Gym» a la playlist». The click on «Editar detalles» brought a dialog
    // with «Nombre», «Descripción», «Guardar» and «Cerrar»; «Gym» typed into «Nombre» sits in a form still to save.
    private static JsonObject PlaylistDialog(string appeared) => (JsonObject)JsonNode.Parse("""
        {"window": {"title": "Mi playlist - APP", "process": "APP"},
         "controls": [{"i": 10, "kind": "Text", "name": "Mi playlist"},
                      {"i": 20, "kind": "Edit", "name": "Nombre", "state": "focused", "value": "Gym"},
                      {"i": 21, "kind": "Edit", "name": "Descripción"},
                      {"i": 22, "kind": "Button", "name": "Guardar"},
                      {"i": 23, "kind": "Button", "name": "Cerrar"}],
         "newTextAfterClick": APPEARED}
        """.Replace("APPEARED", appeared, StringComparison.Ordinal))!;

    private const string PlaylistFirstLook = "mi playlist - app\nmi playlist\neditar detalles\n";

    [TestCase("ponele de nombre «Gym» a la playlist")]
    [TestCase("escribí «Gym» en el nombre")]
    public void TheNameTypedIntoAFormStillToSaveIsNotSet(string goal)
    {
        JsonObject view = PlaylistDialog("""["Editar detalles", "Nombre", "Descripción", "Guardar", "Cerrar"]""");
        JsonArray steps = [Step(2, "input.visible.click", "label", "Editar detalles"), Step(3, "input.text.type", "text", "Gym", "Nombre")];
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.SlotWritten("Gym", goal, view, steps, PlaylistFirstLook), Is.False);
            Assert.That(ComputerUseSuccessCheck.FormLeftUnsaved(view, [], PlaylistFirstLook), Is.True);
        });
    }

    [Test]
    public void TheSameFormAfterTheVerifiedClickOnSaveIsSet()
    {
        const string goal = "ponele de nombre «Gym» a la playlist";
        JsonObject view = PlaylistDialog("""["Cambios guardados"]""");
        JsonArray steps =
        [
            Step(2, "input.visible.click", "label", "Editar detalles"), Step(3, "input.text.type", "text", "Gym", "Nombre"),
            Step(4, "input.visible.click", "label", "Guardar"),
        ];
        Assert.Multiple(() =>
        {
            // The dialog is still on screen, so its «Guardar» shows more than on the first look: brought, and pressed.
            Assert.That(ComputerUseSuccessCheck.BroughtThisSubgoal(
                (JsonObject)view["controls"]![3]!, view, PlaylistFirstLook), Is.True);
            Assert.That(ComputerUseSuccessCheck.SlotWritten("Gym", goal, view, steps, PlaylistFirstLook), Is.True);
        });
    }

    [Test]
    public void ASaveButtonOnScreenAllAlongIsNoFormBrought()
    {
        // v3-08 with the quick access bar's «Guardar», already on the first look: the title is still written.
        const string goal = "ponele de título Lista del super";
        JsonObject view = OneNoteView(false);
        ((JsonArray)view["controls"]!).Add(new JsonObject { ["i"] = 41, ["kind"] = "Button", ["name"] = "Guardar" });
        JsonArray steps = TypedInto("Título de página");
        Assert.That(ComputerUseSuccessCheck.SlotWritten(
            "Lista del super", goal, view, steps, OneNoteFirstLook + "guardar\n"), Is.True);
    }

    // Revisión 4 de r24 (B1): «ponele de título «pruebas» a la pestaña». The click on «Cambiar nombre de pestaña»
    // brought the box «Título de la pestaña»; «pruebas» typed into it, no Enter, the tab still named the old way.
    private static JsonObject TerminalRenaming(string extra) => (JsonObject)JsonNode.Parse("""
        {"window": {"title": "Windows PowerShell - APP", "process": "APP"},
         "controls": [{"i": 10, "kind": "TabItem", "name": "Windows PowerShell"},
                      {"i": 12, "kind": "Edit", "name": "Título de la pestaña", "state": "focused", "value": "pruebas"}]EXTRA}
        """.Replace("EXTRA", extra, StringComparison.Ordinal))!;

    private const string TerminalFirstLook = "windows powershell - app\nwindows powershell\ncambiar nombre de pestana\n";

    [TestCase(", \"newTextAfterClick\": [\"Título de la pestaña\"]")]
    [TestCase("")]
    public void TheRenameBoxBroughtByTheClickIsNoNameSet(string extra)
    {
        const string goal = "ponele de título «pruebas» a la pestaña";
        JsonObject view = TerminalRenaming(extra);
        JsonArray steps =
        [
            Step(2, "input.visible.click", "label", "Cambiar nombre de pestaña"),
            Step(3, "input.text.type", "text", "pruebas", "Título de la pestaña"),
        ];
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.FieldBrought((JsonObject)view["controls"]![1]!, view, TerminalFirstLook), Is.True);
            Assert.That(ComputerUseSuccessCheck.SlotWritten("pruebas", goal, view, steps, TerminalFirstLook), Is.False);
        });
    }

    [Test]
    public void TheRenameBoxBesideAColumnOfTheSameNameIsBrought()
    {
        // Explorer: F2 brings the box «Nombre» while the column «Nombre» was on the first look already.
        const string goal = "ponele de nombre «pruebas» a la carpeta Nueva carpeta";
        var view = (JsonObject)JsonNode.Parse("""
            {"window": {"title": "Documentos - APP", "process": "APP"},
             "controls": [{"i": 5, "kind": "HeaderItem", "name": "Nombre"},
                          {"i": 6, "kind": "ListItem", "name": "Nueva carpeta"},
                          {"i": 7, "kind": "Edit", "name": "Nombre", "state": "focused", "value": "pruebas"}]}
            """)!;
        const string firstLook = "documentos - app\nnombre\nnueva carpeta\n";
        JsonArray steps = [Step(2, "input.key.press", "keys", "F2"), Step(3, "input.text.type", "text", "pruebas", "Nombre")];
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.SlotWritten("pruebas", goal, view, steps, firstLook), Is.False);
        });
    }

    [Test]
    public void ABroughtFieldConfirmedByAVerifiedClickIsSet()
    {
        const string goal = "ponele de título «Informe» al documento";
        var view = (JsonObject)JsonNode.Parse("""
            {"window": {"title": "Documento - APP", "process": "APP"},
             "controls": [{"i": 3, "kind": "Button", "name": "Propiedades"},
                          {"i": 4, "kind": "Edit", "name": "Título", "value": "Informe"},
                          {"i": 5, "kind": "Button", "name": "Aceptar"}]}
            """)!;
        const string firstLook = "documento - app\npropiedades\n";
        JsonArray typed = [Step(2, "input.visible.click", "label", "Propiedades"), Step(3, "input.text.type", "text", "Informe", "Título")];
        JsonArray confirmed =
        [
            Step(2, "input.visible.click", "label", "Propiedades"), Step(3, "input.text.type", "text", "Informe", "Título"),
            Step(4, "input.visible.click", "label", "Aceptar"),
        ];
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.SlotWritten("Informe", goal, view, typed, firstLook), Is.False);
            Assert.That(ComputerUseSuccessCheck.SlotWritten("Informe", goal, view, confirmed, firstLook), Is.True);
        });
    }

    [Test]
    public void AFieldOnTheFirstLookIsNoBoxBrought()
    {
        // v3-08: «Título de página» was on the sub-goal's first look, empty; its value changed, not its presence.
        JsonObject view = OneNoteView(false);
        Assert.Multiple(() =>
        {
            Assert.That(ComputerUseSuccessCheck.FieldBrought((JsonObject)view["controls"]![1]!, view, OneNoteFirstLook), Is.False);
            Assert.That(ComputerUseSuccessCheck.SlotWritten(
                "Lista del super", "ponele de título Lista del super", view, TypedInto("Título de página"), OneNoteFirstLook), Is.True);
        });
    }
}
