using System.Text.Json.Nodes;

namespace Baxy.App;

// What the mind receives: the compact view, the judge's inputs, the step history and the last text typed.
internal static partial class ComputerUseMission
{
    /// <summary>
    /// Ronda 24b (banco r23 c6): the mission's last text typed (its receipt's «text», «atCaret», «intoSearch»), for the
    /// mind's «enviar», whose sub-goal history no longer holds it: an Enter after a text left in the search sends none.
    /// </summary>
    internal static JsonObject? LastTyped(JsonArray? steps)
    {
        JsonObject? typed = (steps ?? []).OfType<JsonObject>().LastOrDefault(step =>
            (string?)step["operation"] == "input.text.type" && (bool?)step["ok"] == true);
        if (typed is null)
            return null;
        var last = new JsonObject { ["text"] = (string?)typed["text"] ?? string.Empty };
        foreach (string key in new[] { "atCaret", "intoSearch", "otherField" })
        {
            if ((bool?)typed[key] == true)
                last[key] = true;
        }

        return last;
    }

    /// <summary>What the mind receives: indices, kinds, names, states, zones, colours and the text by zone; no rectangles, hashes or identities.</summary>
    internal static JsonObject CompactForTheMind(JsonObject view)
    {
        var compact = new JsonObject();
        if (view["window"] is JsonObject window)
        {
            // The rectangles are the mind's geometry (a control covering the window, the list holding the items, a
            // browser's page apart from its frame); the model's prompt does not print them.
            compact["window"] = new JsonObject
            {
                ["title"] = window["title"]?.DeepClone(),
                ["process"] = window["process"]?.DeepClone(),
                ["rect"] = window["rect"]?.DeepClone(),
                ["focused"] = window["focused"]?.DeepClone(),
            };
            if ((bool?)window["requested"] == true)
            {
                // The provider resolved this window for the application (its process, its titled window): the mind
                // takes it as the application in front.
                compact["window"]!["requested"] = true;
            }

            // Encargo EX: the provider read the window through the modal dialog that disabled it.
            if ((bool?)window["modal"] == true)
            {
                compact["window"]!["modal"] = true;
            }
        }

        var controls = new JsonArray();
        if (view["controls"] is JsonArray listed)
        {
            foreach (JsonNode? node in listed)
            {
                if (node is not JsonObject control)
                {
                    continue;
                }

                var item = new JsonObject
                {
                    ["i"] = control["i"]?.DeepClone(),
                    ["kind"] = control["kind"]?.DeepClone(),
                    ["name"] = control["name"]?.DeepClone(),
                };
                if ((string?)control["state"] is { Length: > 0 } state)
                {
                    item["state"] = state;
                }

                if ((string?)control["value"] is { Length: > 0 } value)
                {
                    item["value"] = value.Length > 40 ? value[..40] : value;
                }
                else if (control["value"] is JsonValue)
                {
                    // r26 (c25 x5, y4): a value read and found empty (null: unread), what the mind takes for an empty body.
                    item["empty"] = true;
                }

                if ((string?)control["itemType"] is { Length: > 0 } itemType)
                {
                    // What the item is, as the application says it (a folder, a shortcut, an application): the mind
                    // tells a place from a file by it.
                    item["itemType"] = itemType;
                }

                if ((string?)control["shortcut"] is { Length: > 0 } shortcut)
                {
                    // Goal v3 B3: the key the application itself declares for the control (UIA AcceleratorKey or
                    // AccessKey), shown to the model next to it.
                    item["shortcut"] = shortcut;
                }

                if ((string?)control["zone"] is { Length: > 0 } zone)
                {
                    item["zone"] = zone;
                }

                if ((string?)control["color"] is { Length: > 0 } color)
                {
                    item["color"] = color;
                }

                if (control["repeated"] is JsonValue repeated)
                {
                    item["repeated"] = repeated.DeepClone();
                }

                if ((bool?)control["systemMenu"] == true)
                {
                    // Ronda 20b, palanca 8: the window's system menu chain, as the provider found it under the title bar.
                    item["systemMenu"] = true;
                }

                if ((bool?)control["body"] == true)
                {
                    // Ronda 21: the window's content surface (a canvas, a document), listed past the view's cap.
                    item["body"] = true;
                }

                if ((bool?)control["reserved"] == true)
                {
                    // Revision 2 of ronda 21: listed past the cut only for the goal's words; the mind's look parts
                    // (look_parts, twin of LookText) leave it out like the shell does.
                    item["reserved"] = true;
                }

                if (control["rect"] is JsonObject rect)
                {
                    item["rect"] = rect.DeepClone();
                }

                controls.Add((JsonNode?)item);
            }
        }

        compact["controls"] = controls;
        // Pasada r15b (v3-27, v3-29): the actionables the window shows disabled, apart and without index: the mind
        // tells the model they exist and wait for input, never a control to press.
        if (view["disabled"] is JsonArray disabled && disabled.Count > 0)
        {
            compact["disabled"] = disabled.DeepClone();
        }

        // How many controls the window's tree holds beside the listed ones (at most 60): the mind tells a name that
        // lies beyond the listing (a click by label resolves it against the whole tree) from one the window lacks.
        if (view["controlCount"] is JsonValue controlCount)
        {
            compact["controlCount"] = controlCount.DeepClone();
        }

        if (view["text"] is JsonObject text)
        {
            compact["text"] = text.DeepClone();
        }

        if (view["newText"] is JsonArray appeared)
        {
            compact["newText"] = appeared.DeepClone();
        }

        // What the sub-goal's last verified click made appear (NoteWhatAppeared), on every view: empty when none.
        compact["newTextAfterClick"] = view["newTextAfterClick"] is JsonArray afterClick ? afterClick.DeepClone() : new JsonArray();
        // Ronda 20b (v3-43): the check of the goal held on this window and its question is still unanswered on it
        // (QuestionDatumUnread): the mind leaves the place to the model, which reads the datum or steps to the page.
        if ((bool?)view["questionPending"] == true)
        {
            compact["questionPending"] = true;
        }

        return compact;
    }

    // Only the sub-goal at hand: the mind reasons about the steps toward the goal it is given.
    // What the mind's mirror of the done's judge needs besides the view (falsos éxitos v3 M1): the application's first
    // look in this sub-goal (its parts, ComputerUseSuccessCheck.LookText) and what BAXY typed in earlier missions of
    // the session. Read by the mind's check only; the model's prompt never prints them.
    internal static JsonObject ForTheJudge(
        JsonObject compact, JsonObject state, ComputerUseTypedLedger? typedInSession, JsonObject? view = null,
        JsonArray? steps = null)
    {
        // Ronda 24b (banco r23 c6): the mission's last text and where it went, for the mind's «enviar» (LastTyped).
        if (LastTyped(steps) is { } lastTyped)
        {
            compact["lastTyped"] = lastTyped;
        }

        if ((string?)state["subgoalFirstText"] is { Length: > 0 } firstLook)
        {
            compact["firstLook"] = firstLook;
        }

        // Ronda 20 P4 (v3-08): the ids of the first look's empty and focused parts, and the id of the part focused now
        // (ComputerUseSuccessCheck.NewPartByIdentity): what tells a new page's empty title from the one already there.
        if (state["subgoalFirstIds"] is JsonArray firstIds)
        {
            compact["firstIds"] = firstIds.DeepClone();
        }

        if (view is not null && (string?)ComputerUseSuccessCheck.FocusedControl(view)?["id"] is { Length: > 0 } focusedId)
        {
            compact["focusedId"] = focusedId;
        }

        if (typedInSession?.Texts is { Count: > 0 } typed)
        {
            compact["typedInSession"] = new JsonArray([.. typed.Select(text => (JsonNode?)JsonValue.Create(text))]);
        }

        // The options shown chosen right before each click of the sub-goal (pasada v3 r9): what tells the mind's judge
        // an option the click chose from one that already was.
        if (state["chosenBeforeClick"] is JsonObject chosenBefore)
        {
            compact["chosenBeforeClick"] = chosenBefore.DeepClone();
        }

        // Encargo EX: the mind's twin of NoteCreatedDocument is gone; it reads the click's «createdDocument» (HistoryForMind),
        // so the names and counts of the look before each click stay the App's.

        // Revisión 2 de r22 (bloqueante 1): the clicks whose own control, by its identity, now shows another name, value
        // or switch state (ComputerUseSuccessCheck.ChangedByClick): the mind has no identities, the App tells it.
        if (view is not null && state["clickedBefore"] is JsonObject clickedBefore)
        {
            var changed = ComputerUseSuccessCheck.ChangedByClick(view, clickedBefore);
            if (changed.Count > 0)
            {
                compact["changedByClick"] = new JsonArray([.. changed.Select(step => (JsonNode?)JsonValue.Create(step))]);
            }
        }

        return compact;
    }

    internal static JsonArray HistoryForMind(JsonArray steps, int subgoalStart)
    {
        var history = new JsonArray();
        // Before the sub-goal only the search keys an earlier one spent (t-menu-3, t-long-4: ctrl_k opened Notepad's
        // «Vínculo» and was pressed again by the next sub-goal): marked «spent», never steps of this sub-goal.
        for (int index = 0; index < Math.Min(subgoalStart, steps.Count); index++)
        {
            if (SpentKey(steps, index) is { } spent)
            {
                history.Add((JsonNode?)spent);
            }
        }

        int start = Math.Max(Math.Max(0, subgoalStart), steps.Count - HistoryForTheMind);
        for (int index = Math.Max(0, subgoalStart); index < steps.Count; index++)
        {
            if (steps[index] is not JsonObject step)
            {
                continue;
            }

            // Before the window only the names the whole tree did not hold (a click by label alone, not found): the
            // mind never looks them up again in the sub-goal (pasada r7, v3-58: five names of the place found nowhere,
            // and the cycle started over once they left the window).
            if (index < start && !NotFoundByLabel(step))
            {
                continue;
            }

            var item = new JsonObject
            {
                ["step"] = step["step"]?.DeepClone(),
                ["operation"] = step["operation"]?.DeepClone(),
                ["ok"] = step["ok"]?.DeepClone(),
            };
            // «kind»: what the click pressed, by its receipt (a field keeps the caret when a pop-up of it hides it).
            // «field» and «into»: where a text went (the field it named, or the control that had the keyboard); the
            // mind never sends the same text to the same place a third time (review r10 campo-texto, finding 3).
            // «broughtNew» (NoteWhatTheClickBrought): the mind never presses again a command that created something in
            // a sub-goal of creating one (pasada r15b, v3-03: the mind's creates_again never saw it).
            // «checkUnmet»: a «done» after this step was refused, the planned check's exact atoms false (ronda 23, s01).
            // «searchNothingNew»: what bears the query typed was on the view before the search started (r24b, v1).
            // «manner»: an arrow, a list or a context menu opened, or a double click (goal v3 B3), never told as a click.
            // «entry»: a text chosen as one of a list box's own entries, never written (review of combos-galerias).
            // «selected»: the click's receipt saying whether the item of a list, a tree or tabs ended chosen; the mind
            // says a choice that held by the picture alone had no effect instead of looking it up blind (r15b v3-52).
            // «surfaceChanged» and «placeMoved» (ronda 24b, banco r23 s04): a node or a tab chosen whose place did not move
            // (its receipt ok and selected) is chosen without arriving; the mind never looks it up blind after it.
            // «awaited» (encargo IMP2): the search typed by this step was looked at again once, a moment later.
            // «createdDocument» (encargo EX): the new document this click made (ComputerUseMissionWindow.NoteCreatedDocument).
            foreach (string key in new[] { "label", "index", "text", "key", "direction", "appId", "error", "changed", "kind", "search", "searchBurst", "field", "entry", "into", "sameView", "sameText", "rule", "appeared", "broughtNew", "manner", "selected", "surfaceChanged", "placeMoved", "refused", "checkUnmet", "searchNothingNew", PlaceArgument, "placeOpened", "awaited", "createdDocument" })
            {
                // What appeared after a click or a text is the shell's own (check atom appeared:); the mind reads it
                // after a key only (its Escape's Cancel).
                if (step[key] is JsonNode value
                    && (key != "appeared" || (string?)step["operation"] == "input.key.press"))
                {
                    item[key] = value.DeepClone();
                }
            }

            // Encargo V: the control the worker left unpressed, by its whole name, for the step that names it.
            if ((string?)step["error"] == "visible_control_needs_confirmation" && step["name"] is JsonNode named)
            {
                item["name"] = named.DeepClone();
            }

            // The judge of the done in the mind reads the App's own verdicts (falsos éxitos v3 M1/M2): a click that
            // echoed a query typed before it, and a text typed into a box that only searches.
            if ((bool?)step["ok"] == true && (string?)step["operation"] == "input.visible.click"
                && ComputerUseSuccessCheck.ClickEchoesQuery(step, ComputerUseSuccessCheck.QueriesBefore(steps.Skip(Math.Max(0, subgoalStart)), step)))
            {
                item["echo"] = true;
            }

            if ((string?)step["operation"] == "input.text.type" && ComputerUseSuccessCheck.TypedIntoASearch(step))
            {
                item["query"] = true;
            }

            // Ronda 24 (t-menu-3): the App's verdict that an «open» was the menu entry's own press (OpenIsItsPress).
            if ((string?)step["operation"] == "input.visible.click" && ComputerUseSuccessCheck.OpenIsItsPress(step))
            {
                item["openPress"] = true;
            }

            history.Add((JsonNode?)item);
        }

        return history;
    }

    /// <summary>
    /// A search key that brought up something not sought: verified, and the mission's very next step an Escape (the
    /// mind closes with Escape only what a search key opened that is no search). {step, operation, ok, key, process,
    /// spent} for the mind, which never presses that key again on that application; null otherwise.
    /// </summary>
    internal static JsonObject? SpentKey(JsonArray steps, int index)
    {
        // Ronda 21 (revisión 1, hallazgo b): a key the guard of documents the mission may not touch refused (never
        // pressed) is spent on that application the same, for every later sub-goal.
        if (index < steps.Count && steps[index] is JsonObject refused && (bool?)refused["refused"] == true
            && (string?)refused["operation"] == "input.key.press" && refused["key"] is JsonNode refusedKey)
        {
            var spentByGuard = new JsonObject
            {
                ["step"] = refused["step"]?.DeepClone(),
                ["operation"] = "input.key.press",
                ["ok"] = false,
                ["key"] = refusedKey.DeepClone(),
                ["spent"] = true,
            };
            if (refused["process"] is JsonNode refusedProcess)
            {
                spentByGuard["process"] = refusedProcess.DeepClone();
            }

            return spentByGuard;
        }

        if (index + 1 >= steps.Count || steps[index] is not JsonObject key || steps[index + 1] is not JsonObject next
            || (string?)key["operation"] != "input.key.press" || (bool?)key["ok"] != true
            || !ComputerUseSuccessCheck.FindKeys.Contains(ComputerUseSuccessCheck.Fold((string?)key["key"]))
            || (string?)next["operation"] != "input.key.press" || ComputerUseSuccessCheck.Fold((string?)next["key"]) != "escape")
        {
            return null;
        }

        var spent = new JsonObject
        {
            ["step"] = key["step"]?.DeepClone(),
            ["operation"] = "input.key.press",
            ["ok"] = true,
            ["key"] = key["key"]?.DeepClone(),
            ["spent"] = true,
        };
        if (key["process"] is JsonNode process)
        {
            spent["process"] = process.DeepClone();
        }

        return spent;
    }

    private static bool NotFoundByLabel(JsonObject step) =>
        (string?)step["operation"] == "input.visible.click"
        && step["ok"] is JsonValue ok && ok.TryGetValue(out bool succeeded) && !succeeded
        && (string?)step["error"] == "visible_button_not_found"
        && step["index"] is null;
}
