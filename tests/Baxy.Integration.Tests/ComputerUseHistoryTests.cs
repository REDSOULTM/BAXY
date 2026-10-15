using System.Text.Json.Nodes;
using Baxy.App;
using NUnit.Framework;

namespace Baxy.Integration.Tests;

/// <summary>
/// Pasada r7 del goal v3 (v3-58): the history the mind gets is the sub-goal's last six steps, and the names of the
/// place a click by label alone found nowhere in the whole tree stay in it past that window, so the mind never looks
/// them up again and the five names of «configuración» are not tried a second time.
/// </summary>
[TestFixture]
public sealed class ComputerUseHistoryTests
{
    private static JsonObject Step(int number, string operation, bool ok, string? label = null, string? error = null, int? index = null)
    {
        var step = new JsonObject { ["step"] = number, ["operation"] = operation, ["ok"] = ok };
        if (label is not null)
        {
            step["label"] = label;
        }

        if (error is not null)
        {
            step["error"] = error;
        }

        if (index is not null)
        {
            step["index"] = index;
        }

        return step;
    }

    private static string[] Labels(JsonArray history) =>
        [.. history.Select(item => (string?)item?["label"] ?? (string?)item?["operation"] ?? "")];

    [Test]
    public void NamesNotFoundStayPastTheWindowAndNothingElseDoes()
    {
        var steps = new JsonArray(
            Step(1, "input.visible.click", false, "configuracion", "visible_button_not_found"),
            Step(2, "input.visible.click", false, "ajustes", "visible_button_not_found"),
            Step(3, "input.visible.click", true, "Atrás", index: 6),
            Step(4, "input.key.press", true),
            Step(5, "app.open", true),
            Step(6, "input.visible.click", true, "Actualizar", index: 7),
            Step(7, "input.visible.click", false, "Favoritos", "visible_button_postread_unchanged", 12),
            Step(8, "input.key.press", true),
            Step(9, "input.visible.click", true, "Extensiones", index: 11));

        JsonArray history = ComputerUseMission.HistoryForMind(steps, 0);

        // The window is steps 4–9; before it only the two names found nowhere, in their order, first.
        Assert.That(Labels(history), Is.EqualTo(new[]
        {
            "configuracion", "ajustes", "input.key.press", "app.open", "Actualizar", "Favoritos", "input.key.press", "Extensiones",
        }));
        Assert.That((string?)history[0]!["error"], Is.EqualTo("visible_button_not_found"));
    }

    [Test]
    public void WhereATextWentReachesTheMind()
    {
        // Review r10 campo-texto, finding 3: the mind's «a text that did not arrive is not sent again» reads the field
        // a text named and the control that had the keyboard; without them it compared nothing.
        var named = Step(1, "input.text.type", true);
        named["text"] = "Proyecto final";
        named["field"] = "Título 1";
        named["into"] = "Búsqueda de Microsoft";
        named["replace"] = true;
        var focus = Step(2, "input.text.type", true);
        focus["text"] = "sí";
        focus["into"] = "B2";

        JsonArray history = ComputerUseMission.HistoryForMind(new JsonArray(named, focus), 0);

        Assert.That((string?)history[0]!["field"], Is.EqualTo("Título 1"));
        Assert.That((string?)history[0]!["into"], Is.EqualTo("Búsqueda de Microsoft"));
        Assert.That(history[0]!["replace"], Is.Null);
        Assert.That(history[1]!["field"], Is.Null);
        Assert.That((string?)history[1]!["into"], Is.EqualTo("B2"));
    }

    [Test]
    public void WhatAClickBroughtReachesTheMind()
    {
        // Pasada r15b (A2, v3-03): the mind's creates_again reads «broughtNew» on the click (NoteWhatTheClickBrought);
        // the history never carried it, so «Nueva diapositiva» was pressed four times in a goal of adding one slide.
        var created = Step(1, "input.visible.click", true, "Nueva diapositiva", index: 28);
        created["broughtNew"] = true;
        var undecided = Step(2, "input.visible.click", true, "Insertar", index: 14);

        JsonArray history = ComputerUseMission.HistoryForMind(new JsonArray(created, undecided), 0);

        Assert.That((bool?)history[0]!["broughtNew"], Is.True);
        Assert.That(history[1]!["broughtNew"], Is.Null, "a click with no look before it stays undecided");
    }

    [Test]
    public void TheControlLeftUnpressedForTheConfirmationReachesTheMindByItsName()
    {
        // Encargo V (banco e2, c7): «cotele» resolved to the voice channel «Cotele!!!😎, Canal de voz, Choche», which the
        // worker refused to press without its name in the invocation; the mind's next step names it so RiskPolicy asks.
        var refused = Step(1, "input.visible.click", false, "cotele", "visible_control_needs_confirmation");
        refused["name"] = "Cotele!!!😎, Canal de voz, Choche";
        var other = Step(2, "input.visible.click", false, "Tabla", "visible_control_label_mismatch");
        other["name"] = "Tabla dinámica";

        JsonArray history = ComputerUseMission.HistoryForMind(new JsonArray(refused, other), 0);

        Assert.That((string?)history[0]!["name"], Is.EqualTo("Cotele!!!😎, Canal de voz, Choche"));
        Assert.That(history[1]!["name"], Is.Null, "contracase: any other failure keeps the history as it was");
    }

    [Test]
    public void AChosenPlaceReceiptReachesTheMindWithWhetherThePlaceMoved()
    {
        // Ronda 24b (banco r23 s04): «Downloads» of the navigation tree chosen by Invoke, selected, the surface and the
        // place still; the mind read «changed» alone and looked the place up blind in the window's search.
        var chosen = Step(1, "input.visible.click", true, "Downloads", index: 3);
        chosen["selected"] = true;
        chosen["surfaceChanged"] = false;
        chosen["placeMoved"] = false;
        chosen["changed"] = true;
        var moved = Step(2, "input.visible.click", true, "Bluetooth", index: 5);
        moved["selected"] = true;
        moved["placeMoved"] = true;

        JsonArray history = ComputerUseMission.HistoryForMind(new JsonArray(chosen, moved), 0);

        Assert.That((bool?)history[0]!["selected"], Is.True);
        Assert.That((bool?)history[0]!["surfaceChanged"], Is.False);
        Assert.That((bool?)history[0]!["placeMoved"], Is.False);
        Assert.That((bool?)history[1]!["placeMoved"], Is.True, "contracase: a node that navigated says so");
        Assert.That(history[1]!["surfaceChanged"], Is.Null, "a receipt without the key stays without it");
    }

    [Test]
    public void ATabThatRepeatsTheTypedQueryEchoesItEvenSelected()
    {
        // Ronda 24b (banco r23 s04): the tab «descargas - Este equipo» of the search typed, pressed and left selected.
        var tab = new JsonObject
        {
            ["operation"] = "input.visible.click",
            ["ok"] = true,
            ["label"] = "descargas - Este equipo",
            ["name"] = "descargas - Este equipo",
            ["kind"] = "TabItem",
            ["selected"] = true,
            ["surfaceChanged"] = false,
        };
        Assert.That(ComputerUseSuccessCheck.ClickEchoesQuery(tab, ["descargas"]), Is.True);
        // Contracase: a tab whose name is not the query in a longer text, or no query typed, echoes nothing.
        var other = (JsonObject)tab.DeepClone();
        other["name"] = "Este equipo";
        other["label"] = "Este equipo";
        Assert.That(ComputerUseSuccessCheck.ClickEchoesQuery(other, ["descargas"]), Is.False);
        Assert.That(ComputerUseSuccessCheck.ClickEchoesQuery(tab, []), Is.False);
        var exact = (JsonObject)tab.DeepClone();
        exact["name"] = "descargas";
        exact["label"] = "descargas";
        Assert.That(ComputerUseSuccessCheck.ClickEchoesQuery(exact, ["descargas"]), Is.False,
            "a selected tab named exactly the query is that place, not an echo");
    }

    private static JsonObject Key(int number, string key, string? process = "Notepad")
    {
        var step = Step(number, "input.key.press", true);
        step["key"] = key;
        if (process is not null)
        {
            step["process"] = process;
        }

        return step;
    }

    [Test]
    public void ASearchKeyClosedWithEscapeInAnEarlierSubgoalIsSpentForTheNext()
    {
        // t-menu-3 / t-long-4 (r9): ctrl_k opened Notepad's «Vínculo», the mind closed it with Escape, and the next
        // sub-goal pressed ctrl_k again. The key reaches the next sub-goal marked spent, with its application.
        var steps = new JsonArray(
            Step(1, "input.visible.click", false, "view", "visible_button_not_found"),
            Key(2, "ctrl_k"),
            Key(3, "escape"),
            Key(4, "ctrl_f"),
            Step(5, "input.visible.click", true, "Ver", index: 9));

        JsonArray history = ComputerUseMission.HistoryForMind(steps, 4);

        Assert.That(history.Count, Is.EqualTo(2));
        Assert.That((string?)history[0]!["key"], Is.EqualTo("ctrl_k"));
        Assert.That((bool?)history[0]!["spent"], Is.True);
        Assert.That((string?)history[0]!["process"], Is.EqualTo("Notepad"));
        Assert.That((string?)history[1]!["label"], Is.EqualTo("Ver"));
        Assert.That(history[1]!["spent"], Is.Null);
    }

    [Test]
    public void ContracaseAKeyNotFollowedByEscapeOrOfThisSubgoalIsNotSpent()
    {
        // ctrl_f followed by a typed name was a search that worked; an Escape after a click spends nothing; the key and
        // its Escape inside the current sub-goal are its own steps, never marked.
        var typed = Step(2, "input.text.type", true);
        typed["text"] = "hola";
        var steps = new JsonArray(
            Key(1, "ctrl_f"),
            typed,
            Step(3, "input.visible.click", true, "Archivo", index: 7),
            Key(4, "escape"),
            Key(5, "ctrl_k"),
            Key(6, "escape"));

        JsonArray earlier = ComputerUseMission.HistoryForMind(steps, 4);
        Assert.That(earlier.Any(item => (bool?)item!["spent"] == true), Is.False);
        Assert.That(earlier.Count, Is.EqualTo(2));
        Assert.That(ComputerUseMission.SpentKey(steps, 0), Is.Null);
        Assert.That(ComputerUseMission.SpentKey(steps, 4), Is.Not.Null);
    }

    [Test]
    public void ContracaseAnotherSubgoalsNamesAndAListedControlsFailureStayOut()
    {
        var steps = new JsonArray(
            Step(1, "input.visible.click", false, "configuracion", "visible_button_not_found"),
            Step(2, "input.visible.click", false, "Opciones", "visible_button_not_found", 3),
            Step(3, "input.visible.click", false, "Ver", "visible_button_postread_unchanged"),
            Step(4, "input.key.press", true),
            Step(5, "input.key.press", true),
            Step(6, "input.key.press", true),
            Step(7, "input.key.press", true),
            Step(8, "input.key.press", true),
            Step(9, "input.key.press", true),
            Step(10, "input.key.press", true));

        // The sub-goal started at step 2: step 1 belongs to the one before. A listed control's failure (with its
        // index) and a click that found its control but changed nothing are no lookup of a name.
        JsonArray history = ComputerUseMission.HistoryForMind(steps, 1);
        Assert.That(history.Count, Is.EqualTo(6));
        Assert.That(history.All(item => (string?)item!["operation"] == "input.key.press"), Is.True);
    }

    // Recibo del clic por estado (r15b v3-52), review of the branch (finding 1): the click's receipt «selected» false,
    // recorded by RecordResponse as the App records every step, reaches the mind through the real projection, so the
    // mind's choice without effect reads what the worker said and not a field only a test put there.
    [TestCase("""{"name":"Vídeo","kind":"ListItem","method":"select","surfaceChanged":true,"selected":false,"selectable":true}""", false)]
    [TestCase("""{"name":"Vídeo","kind":"ListItem","method":"invoke","surfaceChanged":true,"selected":true,"selectable":true}""", true)]
    public void TheClicksSelectedReceiptReachesTheMind(string receipt, bool selected)
    {
        var record = new JsonObject { ["step"] = 3, ["operation"] = "input.visible.click", ["label"] = "Vídeo", ["index"] = 7 };
        var response = new Baxy.Contracts.OperationResponse(
            Baxy.Contracts.ProtocolTypes.OperationResponse, "inv", "mission", "inv",
            Baxy.Contracts.OperationStatuses.Completed, "{}", true, false,
            System.Text.Json.JsonDocument.Parse(receipt).RootElement, null);

        ComputerUseMission.RecordResponse(record, response);
        JsonNode item = ComputerUseMission.HistoryForMind(new JsonArray(record), 0)[0]!;

        Assert.Multiple(() =>
        {
            Assert.That((bool?)item["ok"], Is.True);
            Assert.That((bool?)item["changed"], Is.True);
            Assert.That(item["selected"], Is.Not.Null, "the receipt's «selected» is projected to the mind");
            Assert.That((bool?)item["selected"], Is.EqualTo(selected));
        });
    }

    [Test]
    public void ContracaseAReceiptThatSaysNothingOfSelectedProjectsNone()
    {
        var record = new JsonObject { ["step"] = 1, ["operation"] = "input.visible.click", ["label"] = "Aceptar" };
        var response = new Baxy.Contracts.OperationResponse(
            Baxy.Contracts.ProtocolTypes.OperationResponse, "inv", "mission", "inv",
            Baxy.Contracts.OperationStatuses.Completed, "{}", true, false,
            System.Text.Json.JsonDocument.Parse("""{"name":"Aceptar","kind":"Button","absentOrDisabled":true}""").RootElement, null);

        ComputerUseMission.RecordResponse(record, response);
        JsonNode item = ComputerUseMission.HistoryForMind(new JsonArray(record), 0)[0]!;

        // No «selected» is invented for a press that said nothing of it (the mind reads only «is False»).
        Assert.That(item.AsObject().ContainsKey("selected"), Is.False);
    }
}
