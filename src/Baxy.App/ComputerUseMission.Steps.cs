using System.Globalization;
using System.Text.Json;
using System.Text.Json.Nodes;
using Baxy.Contracts;

namespace Baxy.App;

// The record of a step: its receipt, a search burst expanded, and an act that repeats or cycles.
internal static partial class ComputerUseMission
{
    /// <summary>
    /// Once a view shows the window the provider resolved as the sub-goal's
    /// application (titled like it, or the person's browser for «the
    /// browser»), the mission keeps looking at that process (a later
    /// foreground change does not move the surface). Never the frame host shared by the packaged apps
    /// (ApplicationFrameHost): a look bound to it could take another app's frame (Settings vs the Store) and keys
    /// would be allowed there; the provider names the hosted app's process instead.
    /// </summary>
    /// <summary>
    /// The controls the look right before click <paramref name="step"/> listed: their names (controlsBeforeClick, with the
    /// ones listed for the goal's words: encargo S13b) and,
    /// for a name the provider gave as one entry for several controls («repeated»: DesktopUiaWorker joins each kind and
    /// name), how many controls it held (countsBeforeClick; revisión 3 de r24, B1: seven «Sin título» listed once).
    /// </summary>
    internal static void RecordControlsBeforeClick(JsonObject state, JsonObject view, int step)
    {
        string key = step.ToString(CultureInfo.InvariantCulture);
        var named = state["controlsBeforeClick"] as JsonObject ?? new JsonObject();
        named[key] = ComputerUseSuccessCheck.ControlNames(view, reserved: true);
        state["controlsBeforeClick"] = named;
        var counted = state["countsBeforeClick"] as JsonObject ?? new JsonObject();
        counted[key] = ComputerUseSuccessCheck.ControlCounts(view);
        state["countsBeforeClick"] = counted;
    }

    internal static void RecordResponse(JsonObject record, OperationResponse response)
    {
        bool ok = response.Status == OperationStatuses.Completed && response.Verified;
        record["ok"] = ok;
        if (!ok)
        {
            record["error"] = response.ErrorCode
                ?? (response.Status == OperationStatuses.Pending ? "computer_use_step_pending" : "computer_use_step_failed");
            if (response.EffectMayHaveOccurred)
            {
                // Pressed, but its post-read did not hold (a slow page changed after the verification window): the act
                // may have taken effect, so arriving afterwards is not «already there» (MayHaveActed).
                record["effectUncertain"] = true;
            }
        }

        if (response.Result is { ValueKind: JsonValueKind.Object } result)
        {
            // Review 2 of palanca 6 (finding 3): popupBorn, a popup of the window born of the click (a flyout opened by an
            // arrow with the pointer), is what a failed mission closes after it (ListsLeftOpen).
            foreach (string key in new[] { "cascadeStage", "method", "targeted", "focused", "surfaceChanged", "placeMoved", "absentOrDisabled", "selected", "selectable", "toggled", "processId", "name", "kind", "alreadyRunning", "windowsActivation", "windowTitle", "frontChanged", "frontRestored", "newDocument", "placeOpened", "opened", "popupBorn" })
            {
                if (result.TryGetProperty(key, out JsonElement value)
                    && value.ValueKind is JsonValueKind.String or JsonValueKind.True
                        or JsonValueKind.False or JsonValueKind.Number)
                {
                    record[key] = JsonNode.Parse(value.GetRawText());
                }
            }

            // Ronda 20b, palanca 8, objetivo 3 (v3-44): the window of another process the click handed its effect to.
            if (result.TryGetProperty("handedTo", out JsonElement handed) && handed.ValueKind == JsonValueKind.Object)
            {
                record["handedTo"] = JsonNode.Parse(handed.GetRawText());
            }

            // A search burst's sub-acts (goal v3 point 0, fix 3): each becomes a step of its own (ExpandSearchBurst).
            if (result.TryGetProperty("acts", out JsonElement acts) && acts.ValueKind == JsonValueKind.Array)
            {
                record["acts"] = JsonNode.Parse(acts.GetRawText());
            }
        }

        if (ok)
        {
            record["changed"] = (bool?)record["surfaceChanged"] == true
                || record["handedTo"] is JsonObject
                || (bool?)record["absentOrDisabled"] == true
                || (bool?)record["selected"] == true
                || (bool?)record["toggled"] == true
                || (string?)record["operation"] is "app.open" or "file.open" or "input.key.press" or "input.text.type";
        }
    }

    /// <summary>
    /// Goal v3 point 0, fix 3: a search burst (a click that names <c>search</c>) opened, typed and chose in one pause
    /// of the person; its receipt says each sub-act. Each one becomes a step of its own in the mission's record, as if
    /// it had been decided alone (the opener click with its search, the text with where it went, the result's click),
    /// so every check, the history the mind reads and the final read them as they read any step. The burst's own error
    /// stays on the sub-act it stopped before. Any other step is left as it is. Returns the last step.
    /// </summary>
    internal static JsonObject ExpandSearchBurst(JsonArray steps, JsonObject record)
    {
        if (record["acts"] is not JsonArray acts || acts.Count == 0 || steps.Count == 0 || !ReferenceEquals(steps[^1], record))
        {
            record.Remove("acts");
            return record;
        }

        steps.RemoveAt(steps.Count - 1);
        int number = (int?)record["step"] ?? steps.Count + 1;
        JsonObject last = record;
        for (int position = 0; position < acts.Count; position++)
        {
            if (acts[position] is not JsonObject act)
            {
                continue;
            }

            // The opener keeps what was decided (its label, index, search and the view it was decided on); the others
            // only what the burst did.
            JsonObject step = position == 0
                ? (JsonObject)record.DeepClone()
                : new JsonObject
                {
                    ["operation"] = act["operation"]?.DeepClone(),
                    ["source"] = record["source"]?.DeepClone(),
                };
            step.Remove("acts");
            foreach (string key in new[] { "ok", "error", "surfaceChanged", "selected", "selectable", "absentOrDisabled", "toggled",
                "focused", "frontChanged", "frontRestored", "effectUncertain", "changed", "name", "kind", "method", "cascadeStage", "targeted" })
            {
                step.Remove(key);
            }

            step["step"] = number + position;
            step["searchBurst"] = true;
            if (record["subgoal"] is JsonNode subgoal)
            {
                step["subgoal"] = subgoal.DeepClone();
            }

            foreach (string key in new[] { "label", "text", "into", "ok", "error", "method", "kind", "surfaceChanged", "selected" })
            {
                if (act[key] is JsonNode value)
                {
                    step[key] = value.DeepClone();
                }
            }

            bool ok = (bool?)step["ok"] == true;
            if (ok)
            {
                step["changed"] = (bool?)step["surfaceChanged"] == true || (bool?)step["selected"] == true
                    || (string?)step["operation"] == "input.text.type";
            }
            else if ((bool?)record["effectUncertain"] == true)
            {
                step["effectUncertain"] = true;
            }

            steps.Add((JsonNode?)step);
            last = step;
        }

        return last;
    }

    private static bool SameStep(JsonObject previous, string operation, JsonObject arguments)
    {
        if ((string?)previous["operation"] != operation)
        {
            return false;
        }

        // Goal v3 B3: opening a control's arrow or its context menu is another act than clicking it.
        foreach (string key in new[] { "label", "index", "text", "key", "direction", "appId", "manner", PlaceArgument })
        {
            string? before = previous[key]?.ToJsonString();
            string? now = arguments[key]?.ToJsonString();
            if (!string.Equals(before, now, StringComparison.Ordinal))
            {
                return false;
            }
        }

        return true;
    }

    // Encargo U1: the mark of a rule's click decided on a look behind the person's window (AgainInFront).
    internal const string DecidedBehindField = "decidedBehind";

    /// <summary>
    /// Encargo U1 (banco ctl1 u1: the rule pressed «Abre Tu biblioteca» on a player read behind the person's window, its
    /// post-read unchanged; the next look, in front, still showed the button as before, and the model's «none» ended in
    /// «no vi un control»): a rule's click whose press the window did not show (post-read unchanged) and whose control
    /// <paramref name="view"/> still shows as it showed right before the press (its name and value at its index).
    /// </summary>
    internal static bool PressedWithoutEffect(JsonObject state, JsonObject step, JsonObject? view) =>
        view is not null && (string?)step["operation"] == "input.visible.click" && (bool?)step["rule"] == true
        && (bool?)step["ok"] == false && (string?)step["error"] == "visible_button_postread_unchanged"
        && (int?)step["step"] is int number
        && state["clickedBefore"]?[number.ToString(CultureInfo.InvariantCulture)] is JsonObject before
        && ComputerUseSuccessCheck.ClickedControl(view, step) is { } now
        && ComputerUseSuccessCheck.Fold((string?)now["name"]).Trim() == ComputerUseSuccessCheck.Fold((string?)before["name"]).Trim()
        && ComputerUseSuccessCheck.Fold((string?)now["value"]).Trim() == ComputerUseSuccessCheck.Fold((string?)before["value"]).Trim();

    /// <summary>
    /// Encargo U1 (a): the sub-goal's last step <see cref="PressedWithoutEffect"/>, decided on a look behind the person's
    /// window (<see cref="DecidedBehindField"/>), and this look in front: the press went to a window that was coming to
    /// the front and never repainted, so the rule's same click is taken once more instead of handing the step to the
    /// model. Once: the press again is decided in front and carries no such mark. Null otherwise.
    /// </summary>
    internal static MindComputerUseStep? AgainInFront(JsonObject state, JsonArray steps, int start, JsonObject view)
    {
        if (steps.Count <= start || steps[^1] is not JsonObject last || (bool?)last[DecidedBehindField] != true
            || (bool?)view["window"]?["foreground"] != true || last["search"] is not null
            || !PressedWithoutEffect(state, last, view))
        {
            return null;
        }

        var arguments = new JsonObject();
        foreach (string key in new[] { "label", "index", "manner" })
        {
            if (last[key] is JsonNode value)
            {
                arguments[key] = value.DeepClone();
            }
        }

        return new MindComputerUseStep("input.visible.click", arguments, "la ventana ya está delante: el clic se repite una vez", Source: "rule");
    }

    // The view a step was taken from, by hash: what tells a cycle (the screen came back) from progress.
    private const string ViewHashField = "viewHash";

    // A step's mark that it is the one reopening its opener allowed in the sub-goal (RepeatsAnActThatCycled).
    internal const string ReopensField = "reopens";

    // A click's mark that the control it pressed opens something by the view's structure (ClicksAnOpener).
    internal const string OpenerField = "opener";

    /// <summary>
    /// The no-progress guard: this act already succeeded in this sub-goal from
    /// this very screen, so the screen went round back to it (a menu opened and
    /// closed, a toggle flipped twice) and taking it again would loop.
    /// </summary>
    internal static bool RepeatsAnActThatCycled(JsonArray subgoalSteps, string operation, JsonObject arguments, string viewHash) =>
        RepeatsAnActThatCycled(subgoalSteps, operation, arguments, viewHash, out _);

    /// <summary>
    /// As above; <paramref name="reopens"/> says that the act came back to its screen without being the cause
    /// (menus-efímeros, pasada r15b t-form-2, t-menu-3, t-file-4, t-form-3): what it opened lived only while its window
    /// was active and closed when the front went back to the person, so taking it again reopens it. Once per opener and
    /// sub-goal (the step is marked <see cref="ReopensField"/>): a second round is a cycle as before.
    /// </summary>
    internal static bool RepeatsAnActThatCycled(
        JsonArray subgoalSteps, string operation, JsonObject arguments, string viewHash, out bool reopens)
    {
        reopens = false;
        JsonObject[] steps = [.. subgoalSteps.OfType<JsonObject>()];
        int earlier = Array.FindLastIndex(steps, step => (bool?)step["ok"] == true
            && string.Equals((string?)step[ViewHashField], viewHash, StringComparison.Ordinal)
            && SameStep(step, operation, arguments));
        if (earlier < 0)
        {
            return false;
        }

        if (steps.Any(step => (bool?)step[ReopensField] == true && SameStep(step, operation, arguments)))
        {
            return true;
        }

        reopens = OpeningLostWithoutTheAct(steps, earlier);
        return !reopens;
    }

    /// <summary>
    /// Whether what the act <paramref name="earlier"/> opened was lost by something other than the act itself, so the
    /// screen it came back to is no cycle of it. Only an opener by the view's structure (<see cref="OpenerField"/>: a
    /// combo box, a collapsed control) can lose its opening that way, and only with evidence that it was lost: an item
    /// it brought (a popup's, a gallery's) failed afterwards as not found or gone stale; or it reported a changed
    /// surface or a front taken while the look after it saw the window as before (the opening closed before the look).
    /// A front taken alone proves nothing (review of the branch, finding 2: every opener pressed in the person's pause
    /// takes the chain's front), nor does a button that brought a dialog whose later click failed (finding 4: a removal
    /// pressed again). A toggle pressed twice, or a menu its own second press closed, has none of them.
    /// </summary>
    private static bool OpeningLostWithoutTheAct(JsonObject[] steps, int earlier)
    {
        JsonObject act = steps[earlier];
        if ((bool?)act[OpenerField] != true)
        {
            return false;
        }

        if ((bool?)act["broughtNew"] == true)
        {
            for (int later = earlier + 1; later < steps.Length; later++)
            {
                if ((bool?)steps[later]["ok"] == false
                    && (string?)steps[later]["operation"] == "input.visible.click"
                    && (string?)steps[later]["error"] is "visible_button_not_found" or "visible_control_identity_stale"
                    && !SameStep(steps[later], (string?)act["operation"] ?? string.Empty, act))
                {
                    return true;
                }
            }
        }

        // Ronda 20 (P7, v3-28): an arrow or a list says it opened by its own key (opened: read open after the press), never
        // by surfaceChanged nor frontChanged; with the look after it seeing the window as before, its opening closed
        // before that look. A toggle explains its own change.
        return (bool?)act["sameView"] == true && (bool?)act["toggled"] != true
            && ((bool?)act["surfaceChanged"] == true || (bool?)act["frontChanged"] == true
                || (bool?)act["opened"] == true);
    }

    /// <summary>
    /// Whether a click presses a control that opens something living only while its window is active, by the
    /// structure of the view it was decided on (never a name): a combo box, or a control that says it is collapsed (a
    /// menu with a submenu, a split button's arrow, a drop-down). A menu entry or a button that acts is none (the
    /// provider's OpensWhileActive, same rule).
    /// </summary>
    internal static bool ClicksAnOpener(string operation, JsonObject arguments, JsonObject? view)
    {
        if (operation != "input.visible.click" || view?["controls"] is not JsonArray controls)
        {
            return false;
        }

        JsonObject? control = null;
        if (arguments["index"] is JsonNode index)
        {
            string wanted = index.ToJsonString();
            control = controls.OfType<JsonObject>().FirstOrDefault(item => item["i"]?.ToJsonString() == wanted);
        }
        else if ((string?)arguments["label"] is { Length: > 0 } label)
        {
            string wanted = ComputerUseSuccessCheck.Fold(label);
            JsonObject[] named = [.. controls.OfType<JsonObject>()
                .Where(item => ComputerUseSuccessCheck.Fold((string?)item["name"]) == wanted)];
            control = named.Length == 1 ? named[0] : null;
        }

        // Ronda 20 (P7, v3-37): an arrow or a context menu opened by its manner opens a list or a menu by definition,
        // whatever the control's kind (a split button that says no state).
        if ((string?)arguments["manner"] is "open" or "menu")
        {
            return control is not null;
        }

        return control is not null
            && ((string?)control["kind"] == "ComboBox"
                || ((string?)control["state"] ?? string.Empty).Split(' ', StringSplitOptions.RemoveEmptyEntries)
                    .Contains("collapsed", StringComparer.Ordinal));
    }

    private static string Describe(string operation, JsonObject arguments) => operation switch
    {
        "input.visible.click" => (string?)arguments["manner"] switch
        {
            "open" => $"abriendo «{(string?)arguments["label"]}»",
            "menu" => $"menú de «{(string?)arguments["label"]}»",
            "double" => $"doble clic en «{(string?)arguments["label"]}»",
            _ => $"clic en «{(string?)arguments["label"]}»",
        },
        "input.text.type" => "escribiendo",
        "input.key.press" => $"tecla {(string?)arguments["key"]}",
        "input.scroll" => "desplazando",
        "app.open" => "abriendo la aplicación",
        "file.open" => $"abriendo «{(string?)arguments["name"]}»",
        _ => operation,
    };

    // An act that opens the window the mission goes on in: the application, or a file of the person's with it.
    internal static bool OpensTheWindow(string operation) => operation is "app.open" or "file.open";

    // The mind's stop code for a file not opened, followed by its cause (cu_open_file.FILE_NOT_OPENED).
    private const string FileNotOpened = "file_not_opened";
}
