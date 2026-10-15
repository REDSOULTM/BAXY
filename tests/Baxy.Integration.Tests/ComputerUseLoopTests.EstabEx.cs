using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Encargo EX (tandas n5 y n6, t4-c06 «bro abre excel y crea un blank workbook»). n5: the click on «Libro en blanco» on
/// Excel's start page made «Libro1 - Excel» and nothing recorded it, so the model pressed the title's «Libro1 - Excel»
/// (it opened «Guardar este archivo») and the final denied the workbook. n6: Excel was read through that dialog, left
/// open, and the mission said only «no vi en la pantalla un control con el que seguir».
/// </summary>
public sealed partial class ComputerUseLoopTests
{
    private const string BlankWorkbookRequest = "bro abre excel y crea un blank workbook";

    // Excel's start page as the look of n5 read it (step 1): no document in the title, the offer and a recent «Libro1».
    private static JsonObject ExcelStartPage() => Tied(Window("Excel", "EXCEL", 9280, true,
        [Control(5, "ListItem", "Inicio", "selected"), Control(6, "ListItem", "Nuevo"),
         Control(11, "ListItem", "Libro en blanco", "selected focused"), Control(18, "ListItem", "Libro1"),
         Control(19, "ListItem", "YOUTUBE OFF MELI"), Control(39, "List", "Plantillas"), Control(41, "List", "Recientes")]), 330818);

    // The look after the click (step 2 of n5): the new workbook, its title button and its first sheet.
    private static JsonObject ExcelNewWorkbook() => Tied(Window("Libro1 - Excel", "EXCEL", 9280, true,
        [Control(8, "Button", "Guardar"), Control(10, "Button", "‪Libro1‬ - Excel"),
         Control(17, "TabItem", "Inicio", "selected"), Control(51, "TabItem", "Hoja1", "selected"),
         Control(61, "Pane", "Libro1"), Control(63, "Pane", "Hoja Hoja1", "selected")]), 330818);

    private static (JsonObject State, JsonArray Steps) TiedToExcelStartPage()
    {
        var state = new JsonObject { ["objective"] = BlankWorkbookRequest, ["application"] = "Excel" };
        var steps = new JsonArray();
        state["steps"] = steps;
        JsonObject first = ExcelStartPage();
        ComputerUseMission.AdoptWindow(state, "Excel", first);
        ComputerUseMissionWindow.Tie(state, "Excel", first, ofTheApplication: true, steps);
        return (state, steps);
    }

    [Test]
    public void ExTheBlankOfferClickedOnAStartPageMadeTheWorkbookItShows()
    {
        (JsonObject state, JsonArray steps) = TiedToExcelStartPage();
        JsonObject click = Click(1, "Libro en blanco", "Excel");
        click["kind"] = "ListItem";
        steps.Add(click);
        ComputerUseMissionWindow.NoteCreatedDocument(state, ExcelNewWorkbook(), steps);
        Assert.That((string?)steps[0]!["createdDocument"], Is.EqualTo("Libro1"),
            "a recent «Libro1» listed on the start page is no document the window showed");

        // The mind reads that record on the click (its twin of the rule is gone).
        JsonArray history = ComputerUseMission.HistoryForMind(steps, 0);
        Assert.That((string?)history[0]!["createdDocument"], Is.EqualTo("Libro1"));
    }

    [Test]
    public void ExARecentFileOrAPageWithADocumentMakesNoWorkbook()
    {
        // Contracase: the click on the recent «Libro1» opened the person's file of that name.
        (JsonObject recentState, JsonArray recentSteps) = TiedToExcelStartPage();
        JsonObject recent = Click(1, "Libro1", "Excel");
        recent["kind"] = "ListItem";
        recentSteps.Add(recent);
        ComputerUseMissionWindow.NoteCreatedDocument(recentState, ExcelNewWorkbook(), recentSteps);
        Assert.That(recentSteps[0]!["createdDocument"], Is.Null);

        // Contracase: a click decided over a window that already titled a document is no start page; a default name
        // («Libro1») there is no untitled document, and nothing is recorded.
        (JsonObject titledState, JsonArray titledSteps) = TiedToExcelStartPage();
        JsonObject titled = Click(1, "Libro en blanco", "Presupuesto - Excel");
        titled["kind"] = "ListItem";
        titledSteps.Add(titled);
        ComputerUseMissionWindow.NoteCreatedDocument(titledState, ExcelNewWorkbook(), titledSteps);
        Assert.That(titledSteps[0]!["createdDocument"], Is.Null);
    }

    [Test]
    public void ExTheModalDialogReachesTheMind()
    {
        JsonObject view = ExcelNewWorkbook();
        view["window"]!["modal"] = true;
        Assert.That((bool?)ComputerUseMission.CompactForTheMind(view)["window"]!["modal"], Is.True);
        // Contracase: a window read as itself carries no such mark.
        Assert.That(ComputerUseMission.CompactForTheMind(ExcelNewWorkbook())["window"]!["modal"], Is.Null);
    }

    [TestCase("dialog", true)]
    [TestCase("source", false)]
    [TestCase("dialogSource", false)]
    public void ExAGateKindIsOneTheFloorSays(string kind, bool said)
    {
        // n6: the view of Excel read through «Guardar este archivo» (its title empty).
        JsonObject view = Window("", "EXCEL", 9280, true,
            [Control(0, "Edit", "Nombre de archivo", "focused", "Libro1"), Control(6, "Button", "Guardar"),
             Control(7, "Button", "Cancelar"), Control(10, "Window", "Guardar este archivo"),
             Control(11, "Text", "Guardar este archivo")]);
        var decision = new MindComputerUseStep(
            "none", new JsonObject { ["evidence"] = "Guardar este archivo", ["gate"] = kind }, "diálogo", "app_gate");
        JsonObject? gate = ComputerUseMission.GateSeen(decision, view);
        Assert.That(gate is not null, Is.EqualTo(said));
    }
}
