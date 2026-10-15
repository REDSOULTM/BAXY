using System.Text.Json.Nodes;

namespace Baxy.App;

// What the mission refuses or holds before an act: the mission's window, elevation, a foreign document, a key
// that leaves the window, overwriting, and the refusals handed back to the model.
internal static partial class ComputerUseMission
{
    /// <summary>
    /// The stop of a mission whose window runs as administrator. Review of M5: the limit offers to reopen it without
    /// administrator rights («…_reopenable») only when the view says its program would stay unraised; a program that
    /// raises itself again (the Task Manager, measured) keeps the limit without the offer.
    /// </summary>
    internal static string ElevatedStop(JsonObject? view) =>
        (bool?)view?["window"]?["reopensUnraised"] == true
            ? "computer_use_window_elevated_reopenable"
            : "computer_use_window_elevated";

    /// <summary>
    /// cu-v3-elevacion (r9 v3-23, v3-65): a window that runs as administrator, whose program opens again with the
    /// person's rights (a console, measured live), is opened again that way before anything else, instead of stopping:
    /// the mind's first step is then app.open (computer_use.py, the same rule), and the provider starts a new copy
    /// instead of reusing the raised one. Once the mission has a step, a raised window stops it as before.
    /// Review of cu-v3-elevacion (finding 5): only for a mission with a named application, the one the mind reopens
    /// (computer_use.py opens only the request's application); without one there is nothing to reopen.
    /// </summary>
    internal static bool ReopensUnraisedFirst(JsonObject? view, int stepsDone, string? application) =>
        stepsDone == 0 && !string.IsNullOrWhiteSpace(application) && (bool?)view?["window"]?["reopensUnraised"] == true;

    /// <summary>
    /// Review of cu-v3-elevacion (finding 5): whether the decision may be carried out on the view. On a window that runs
    /// as administrator the only step is the reopening (<see cref="ReopensUnraisedFirst"/>), an app.open; any other
    /// decision, «done» included, stops the mission with <see cref="ElevatedStop"/>.
    /// Ronda 19b (r17 t2-c03): a raised window of another program than the mission's named application (the person's
    /// Task Manager in front before «abre configuración» opened anything) allows only opening the application or its
    /// file (<see cref="ElevatedElsewhere"/>).
    /// </summary>
    internal static bool ElevatedViewAllows(
        JsonObject? view, int stepsDone, string? application, string operation, bool ofTheApplication) =>
        (bool?)view?["window"]?["elevated"] != true
        || (ElevatedElsewhere(view, application, ofTheApplication)
            ? OpensTheWindow(operation)
            : ReopensUnraisedFirst(view, stepsDone, application) && string.Equals(operation, "app.open", StringComparison.Ordinal));

    /// <summary>
    /// Ronda 19b (r17 t2-c03): the view is a window that runs as administrator and is not of the mission's named
    /// application (neither resolved for it nor of its process family): another program's raised window in front, of
    /// which the limit «runs as administrator» is never said. Without a named application the window in front is the
    /// mission's, and its limit stands.
    /// </summary>
    internal static bool ElevatedElsewhere(JsonObject? view, string? application, bool ofTheApplication) =>
        (bool?)view?["window"]?["elevated"] == true && !string.IsNullOrWhiteSpace(application) && !ofTheApplication;

    // v3 r5a M5: the app.open argument saying the application is opened for the mission to control its window.
    internal const string ForControlArgument = "forControl";

    // Estabilización, encargo C: the app.open arguments naming a place of the application with an address of its own
    // (data app_places.v1.json) and the value of its slot; the receipt says the address was opened («placeOpened»).
    internal const string PlaceArgument = "place";
    internal const string PlaceValueArgument = "placeValue";

    /// <summary>
    /// The mission's own app.open opens the application to read and press its window: a program Windows would raise to
    /// administrator unasked is started with the person's rights (InvokerLaunch). Other acts carry nothing.
    /// </summary>
    internal static void MarkOpeningForControl(string operation, JsonObject arguments)
    {
        if (string.Equals(operation, "app.open", StringComparison.Ordinal))
        {
            arguments[ForControlArgument] = true;
        }
    }

    /// <summary>
    /// Safety review r10a: a key of the catalog whose effect is not in the window it is sent to — switching to another
    /// window, the Start menu, the Task Manager — is never a step of a mission. Bound to the mission's window it would
    /// still act on the desktop over the person, and the lease would take the front it moved for the person's own
    /// choice and give nothing back. The mind does not offer these keys; a step that names one stops here.
    /// </summary>
    internal static bool KeyLeavesTheWindow(string operation, JsonObject arguments) =>
        operation == "input.key.press"
        && ComputerUseSuccessCheck.Fold((string?)arguments["key"]).Trim() is "alt_tab" or "win" or "ctrl_shift_escape";

    /// <summary>
    /// Ronda 21 (pasada r18 v3-36: ctrl_k of the search rule on a note's editor stopped the mission with 0 steps and a
    /// false cause): the step the model is handed when the guard of documents the mission may not touch refused a key
    /// of the mind's rule that alters no content (never one of data
    /// «computerUse.contentKeys.altering»), the first time that key is refused in the sub-goal: {step, operation, key,
    /// ok false, error «document_not_named», source, refused}. Null for the model's own act, any act but a key, an
    /// altering key, or a key already refused in the sub-goal: the mission stops as before.
    /// </summary>
    /// <summary>
    /// Ronda 21 (revisión 1, hallazgo b): the cause a mission stopped by the guard of documents it may not touch says,
    /// by what the refused act does (data «computerUse.contentKeys»): a key that opens a new container or goes to the
    /// window's bar (<c>computer_use_document_not_named_container</c>), another key that alters no content by itself
    /// (<c>computer_use_document_not_named_key</c>), and any act that selects, erases or writes the content
    /// (<c>computer_use_document_not_named</c>).
    /// </summary>
    internal static string ForeignDocumentCause(string operation, JsonObject arguments, bool restored = false)
    {
        // Ronda 24 (pasada r23 v3-34): the window the mission's own opening started showed the person's content that
        // was already there; «I neither opened nor created it» would be false.
        if (restored)
        {
            return "computer_use_document_restored";
        }

        string key = ComputerUseSuccessCheck.Fold((string?)arguments["key"]).Trim().Replace(' ', '_');
        if (operation != "input.key.press" || key.Length == 0 || ComputerUseMissionWindow.AlteringKey(key))
        {
            return "computer_use_document_not_named";
        }

        return OperationFloor.ContentKeyClass("container").Contains(key)
            ? "computer_use_document_not_named_container"
            : "computer_use_document_not_named_key";
    }

    /// <summary>
    /// Ronda 23 (índices de vista y esquema, t-menu-2 r21): the step a rule's act the catalog's exact
    /// schema refuses is kept as, never taken: {step, operation, the act's arguments, ok false, error
    /// «arguments_invalid:» and the arguments refused, source, refused}. The mind reads a refused last step as the
    /// model's turn (<c>refused_by_the_guard</c>). Null for the model's own act and for a second schema refusal in the
    /// sub-goal: the mission stops as before.
    /// </summary>
    internal static JsonObject? SchemaRefusalForTheModel(
        string operation, JsonObject arguments, string? source, JsonArray subgoalSteps, int stepNumber)
    {
        if (source != "rule"
            || subgoalSteps.OfType<JsonObject>().Any(step => (bool?)step["refused"] == true
                && ((string?)step["error"] ?? string.Empty).StartsWith(ArgumentsInvalid, StringComparison.Ordinal)))
        {
            return null;
        }

        IReadOnlyList<string> outside = MindPlanBoundary.ArgumentsOutsideExactSchema(operation, arguments);
        var refused = new JsonObject
        {
            ["step"] = stepNumber,
            ["operation"] = operation,
        };
        foreach (string key in new[] { "label", "index", "text", "key", "direction", "amount", "field", "manner" })
        {
            if (arguments[key] is JsonNode value)
            {
                refused[key] = value.DeepClone();
            }
        }

        refused["ok"] = false;
        refused["error"] = outside.Count == 0 ? ArgumentsInvalid : $"{ArgumentsInvalid}:{string.Join(",", outside)}";
        refused["source"] = "rule";
        refused["refused"] = true;
        return refused;
    }

    // The error a schema-refused act is handed back to the model with, followed by the arguments refused.
    internal const string ArgumentsInvalid = "arguments_invalid";

    internal static JsonObject? RefusalForTheModel(
        string operation, JsonObject arguments, string? source, JsonArray subgoalSteps, int stepNumber)
    {
        string key = ComputerUseSuccessCheck.Fold((string?)arguments["key"]).Trim().Replace(' ', '_');
        if (operation != "input.key.press" || key.Length == 0 || source != "rule"
            || ComputerUseMissionWindow.AlteringKey(key)
            || subgoalSteps.OfType<JsonObject>().Any(step => (bool?)step["refused"] == true
                && ComputerUseSuccessCheck.Fold((string?)step["key"]).Trim().Replace(' ', '_') == key))
        {
            return null;
        }

        return new JsonObject
        {
            ["step"] = stepNumber,
            ["operation"] = operation,
            ["key"] = key,
            ["ok"] = false,
            ["error"] = "document_not_named",
            ["source"] = "rule",
            ["refused"] = true,
        };
    }

    /// <summary>
    /// Safety review 2026-10-07: a key, a text, a click or a scroll goes to the mission's window, never to whatever holds the front when
    /// it is sent (the person's editor, BAXY itself, a window that came up meanwhile). The step names the window its
    /// decision was made on (the hwnd of the last view), also when the step was confirmed first and BAXY's own window
    /// is in front after the «sí». Goal v3 (point 0, fix 1): bound means the delivery is aimed at that window, not
    /// that it holds the front; the provider delivers to it without the keyboard when its field takes it (identity
    /// checked before every send) and only otherwise brings it to the front or sends nothing. A text also names its
    /// field (<see cref="TextField"/>), so it reaches that field and not a focus the provider would have to guess.
    /// When the mission names an application and that view is not its window (resolved for it, or of its known
    /// process), nothing is pressed or typed: false. With no application, the same for the person's window
    /// (<see cref="NoApplicationActs"/>).
    /// </summary>
    internal static bool BindToMissionWindow(
        string operation,
        JsonObject arguments,
        JsonObject? view,
        JsonObject state,
        string? application,
        JsonArray? steps = null)
    {
        if (operation is not ("input.key.press" or "input.text.type" or "input.visible.click" or "input.scroll"))
            return true;
        // Contract «Seguridad v2»: never VS Code, Visual Studio, an editor, a terminal, a console or BAXY when the
        // person did not name them, also with no application named (the mission works on the window in front). The
        // view marks such a window by its process (window «protected»), never by a title.
        if (ProtectedWindow(view))
            return false;
        JsonObject? window = view?["window"] as JsonObject;
        if (application is { Length: > 0 }
            && !((bool?)window?["requested"] == true || OfTheMissionFamily(state, window)))
            return false;
        // Goal v3 destino (r5a M5, v3-35 T3: «morado» typed into the person's window; t-menu-1: a right click there):
        // with no application resolved, the window in front is the person's, where they work; a key, a text, a click,
        // or a scroll goes only to a window the mission itself opened (its process) or one resolved for it,
        // never to that one, unless the person named it («en esta ventana…»).
        if (NoApplicationActs(operation, application, state, window))
            return false;
        // A click or a scroll is bound to it as well (v3 point 0 review): a look no longer brings the window to the
        // front, so the act takes the front for that window, and only that one, or does nothing.
        if ((long?)window?["hwnd"] is > 0 and long hwnd)
        {
            arguments["window"] = hwnd;
            // A key or a text: the field is always the one of this view (an index carried by the step may name a
            // control of another view). A click's index is the control of this view and stays.
            if (operation is "input.key.press" or "input.text.type")
            {
                arguments.Remove("index");
                // Goal v3 point 2 (forms): a text that names its field by its label goes to that field of this view
                // or nowhere (the provider refuses a named field without an index); never to the focus instead.
                if (operation == "input.text.type" && (string?)arguments["field"] is { Length: > 0 } label)
                {
                    if (LabelledField(view, label) is int labelled)
                        arguments["index"] = labelled;
                }
                else if (operation == "input.text.type" && TextField(view, steps) is int field)
                {
                    arguments["index"] = field;
                }
            }
        }

        // Goal v3 point 2 (overwrite guard): confirming, on this view, that a file that already exists is written over,
        // by a click on the confirming button or by Enter/Space on it when it has the keyboard focus.
        if (operation is "input.visible.click" or "input.key.press")
        {
            arguments.Remove("consequence");
            if (operation == "input.visible.click" ? Overwrites(view, (string?)arguments["label"]) : KeyOverwrites(view, (string?)arguments["key"]))
                arguments["consequence"] = "overwrite";
        }

        // Revisión de V (H1): Enter or space presses what has the keyboard, or, from a field, the result its list holds
        // chosen (a voice channel highlighted in a search). The name RiskPolicy has to ask about goes with the key
        // («onto»), from this view only.
        if (operation == "input.key.press")
        {
            arguments.Remove("onto");
            if (KeyLandsOnWhatAsks(view, (string?)arguments["key"]) is { } onto)
                arguments["onto"] = onto;
        }

        // Goal v3 ventana-misión: Ctrl+A, Supr or text on a document the mission neither opened nor created needs the
        // request to name it.
        return !ComputerUseMissionWindow.ForeignDocumentAct(operation, arguments, view, state);
    }

    /// <summary>
    /// Goal v3 destino, extended by the round-5 integration: an act of a mission with no application resolved — a key,
    /// a text, a click or a scroll — on a window the mission neither opened (its process) nor had resolved for
    /// it: the person's own window in front, where they work. Nothing goes there, unless the person named that window
    /// as the destination («en esta ventana…»: the mission's <c>frontWindow</c>, read by the mind).
    /// </summary>
    internal static bool NoApplicationActs(string operation, string? application, JsonObject state, JsonObject? window) =>
        operation is "input.key.press" or "input.text.type" or "input.visible.click" or "input.scroll"
        && application is not { Length: > 0 }
        && (bool?)state["frontWindow"] != true
        && (bool?)window?["requested"] != true
        && !OfTheMissionFamily(state, window);

    /// <summary>A developer's or BAXY's own window the request did not name, as the view marks it by its process.</summary>
    internal static bool ProtectedWindow(JsonObject? view) => (bool?)view?["window"]?["protected"] == true;

    /// <summary>
    /// A click that answers yes to writing over a file that already exists: its label confirms («Sí», «Yes»,
    /// «Reemplazar») and the view it was decided on warns of the overwrite («ya existe», «¿Desea reemplazarlo?»,
    /// «already exists»), in its written text or in a text control. Both patterns are data (operation_floor.v1.json
    /// «computerUse.overwrite»). A Replace dialog's «Reemplazar todo» with no such warning is not one.
    /// </summary>
    internal static bool Overwrites(JsonObject? view, string? label) =>
        view is not null && ConfirmsOverwrite(label) && WarnsOfOverwrite(view);

    /// <summary>
    /// Enter or Space that presses the confirming button of a view that warns of an overwrite: the button with the
    /// keyboard focus confirms («Sí» after a Tab), or the view reports no focus and has a confirming button (fail
    /// closed: the key may land on it). A focused «No» or a field is not one.
    /// </summary>
    internal static bool KeyOverwrites(JsonObject? view, string? key)
    {
        if (view is null || key is not ("enter" or "space") || !WarnsOfOverwrite(view))
            return false;
        if (view["window"]?["focused"] is JsonObject focused && (string?)focused["name"] is { } focusedName)
            return ConfirmsOverwrite(focusedName);
        return (view["controls"] as JsonArray ?? new JsonArray()).OfType<JsonObject>()
            .Any(control => (string?)control["kind"] != "Text" && ConfirmsOverwrite((string?)control["name"]));
    }

    /// <summary>
    /// Revisión de V (H1): the name Enter or space would press on this view that needs the person's word
    /// (<see cref="Kernel.Policy.RiskPolicy.PressedNameAsksMoreThanItsLabel"/>, RiskPolicy's own reading): the focused control, or,
    /// with the keyboard in a field, an item of a list, a menu or a grid the view shows chosen. Null when none asks.
    /// </summary>
    internal static string? KeyLandsOnWhatAsks(JsonObject? view, string? key)
    {
        if (view is null || key is not ("enter" or "space"))
            return null;
        JsonObject? focused = view["window"]?["focused"] as JsonObject;
        IEnumerable<string?> names = [(string?)focused?["name"]];
        if ((string?)focused?["kind"] is "Edit" or "ComboBox" or "Document")
        {
            names = names.Concat((view["controls"] as JsonArray ?? new JsonArray()).OfType<JsonObject>()
                .Where(control => (string?)control["kind"] is "ListItem" or "DataItem" or "MenuItem"
                    && ((string?)control["state"] ?? string.Empty).Split(' ').Contains("selected"))
                .Select(control => (string?)control["name"]));
        }

        return names.FirstOrDefault(name => Kernel.Policy.RiskPolicy.PressedNameAsksMoreThanItsLabel(null, name));
    }

    private static bool ConfirmsOverwrite(string? label) =>
        ComputerUseSuccessCheck.Fold(label) is { Length: > 0 } folded && OperationFloor.OverwriteConfirm.IsMatch(folded);

    private static bool WarnsOfOverwrite(JsonObject view)
    {
        IEnumerable<string> said = ComputerUseSuccessCheck.TextLines(view).Select(line => (string?)line ?? string.Empty)
            .Concat((view["controls"] as JsonArray ?? new JsonArray()).OfType<JsonObject>()
                .Where(control => (string?)control["kind"] == "Text")
                .Select(control => ComputerUseSuccessCheck.Fold((string?)control["name"])));
        return said.Any(OperationFloor.OverwriteWarning.IsMatch);
    }
}
