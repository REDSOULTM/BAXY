using System.Globalization;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace Baxy.App;

// Choices: an entry shown chosen, a choice that moved the window's place, and whether the option was chosen
// already before the click.
internal static partial class ComputerUseSuccessCheck
{
    // «current» is the place the window shows now: the item chosen in its navigation (a side list or tree, a tab). An
    // item merely selected in a content list is not (measured on Explorer: one click on the «Descargas» folder of the
    // Home view selects it and opens nothing; Enter or a double click opens it).
    private static bool HasState(JsonObject control, string state, JsonObject view, JsonArray steps)
    {
        string[] states = Fold((string?)control["state"]).Split(' ');
        return state == "current"
            ? states.Contains("selected") && !IsContentItem(control, view["controls"] as JsonArray)
                && ChosenWhereTheWindowIs(control, view, steps)
            : states.Contains(state);
    }

    /// <summary>
    /// Encargo TZ-OSC (tandas z3/z4 t4-c04 t3, «en configuracion pon el modo oscuro»): the option is the current value of
    /// a choice box of the window: a ComboBox, never a box that searches or takes an address, nor one these steps typed
    /// into, whose value is the option's whole name. «oscuro» typed into the search, then «Elige tu modo» = Oscuro with
    /// its entry «Oscuro» selected: a setting's value, not what the search echoes (a search's matches are never the value
    /// of another box of the window).
    /// </summary>
    private static bool ChoiceBoxValue(JsonObject option, JsonObject view, JsonArray steps)
    {
        string name = Fold((string?)option["name"]).Trim();
        if (name.Length == 0)
        {
            return false;
        }

        var typedInto = new HashSet<string>(
            steps.OfType<JsonObject>().Where(step => (string?)step["operation"] == "input.text.type")
                .Select(step => Fold((string?)step["into"]).Trim()),
            StringComparer.Ordinal);
        return (view["controls"] as JsonArray ?? []).OfType<JsonObject>().Any(box =>
            (string?)box["kind"] == "ComboBox" && Fold((string?)box["value"]).Trim() == name
            && Fold((string?)box["name"]) is { } boxName
            && !SearchBox.IsMatch(boxName) && !AddressBox.IsMatch(boxName) && !typedInto.Contains(boxName.Trim()));
    }

    // The kinds a click selects in place: an entry of a list, a table or a tree.
    private static readonly HashSet<string> EntryKinds = new(StringComparer.Ordinal) { "ListItem", "DataItem", "TreeItem" };

    /// <summary>
    /// Pasada r18 (v3-50, v3-52): an entry of a list, a table or a tree shown selected is where the window is only when
    /// it was so at the sub-goal's first look (<c>selectedAtStart</c>), or when the act that chose it, or a later one
    /// on it, moved the window (<see cref="ChoiceMovedThePlace"/>). A click or a key that only selected it left the
    /// window where it was: an archive selected in a one-column file list is not opened, a section of a settings list
    /// selected while the page beside it still shows the other one is not reached. A look whose first selection was not
    /// kept judges a choice made without a click on the entry as before.
    /// </summary>
    internal static bool ChosenWhereTheWindowIs(JsonObject control, JsonObject view, JsonArray steps)
    {
        if ((string?)control["kind"] is not { } kind || !EntryKinds.Contains(kind))
        {
            return true;
        }

        string name = Fold((string?)control["name"]).Trim();
        if (view["selectedAtStart"] is JsonArray atStart && atStart.Any(node => Fold((string?)node).Trim() == name))
        {
            return true;
        }

        if (view["selectedAtStart"] is not JsonArray && !ClicksNaming(steps, name).Any())
        {
            return true;
        }

        return ChoiceMovedThePlace(name, steps, view["selectedBeforeClick"] as JsonObject, view, out _);
    }

    /// <summary>
    /// Review 1 of ronda 20b: whether the act that chose the entry named <paramref name="name"/> moved the window, or a
    /// later verified act on it did (a click naming it, a key such as Enter that opens it). The chooser is the last act
    /// before which the entry was not shown selected (<paramref name="selectedBefore"/>, keyed by step): a click
    /// repeated on an entry already chosen is not the one that chose it, and a key that only selected it after an
    /// earlier act moved the window to its folder is (a navigation, then an arrow onto the archive: no arrival). An
    /// act without its record may have chosen it, but a click on the entry repeated after an earlier verified one on
    /// it. <paramref name="chosen"/> is false when the entry was shown selected before every act (none chose it).
    /// An opening of the application moves nothing here, unless it chose the entry by opening a place of the application
    /// by its address (<c>placeOpened</c>, as <see cref="ComputerUseMission.MayHaveActed"/> takes it): encargo E5 (bancos
    /// fw2, fw3, e5c1, e5c2: Configuración already open on Inicio, «ir a Sistema» opened by its address and Sistema
    /// selected after it; the check never held, the model's «done» was refused and the mission stopped with the page on
    /// screen). Without any such record, a click on the entry that moved the window reached it (the second press of an
    /// entry already reached changes nothing and takes nothing back).
    /// </summary>
    private static bool ChoiceMovedThePlace(string name, JsonArray steps, JsonObject? selectedBefore, JsonObject? view, out bool chosen)
    {
        if (selectedBefore is null && ClicksNaming(steps, name).ToList() is { Count: > 0 } clicks)
        {
            // No record of what was selected before each act: a click on the entry that moved the window reached it.
            chosen = true;
            return clicks.Any(click => MovedThePlace(click, steps, view));
        }

        int chooser = -1;
        for (int index = steps.Count - 1; index >= 0 && chooser < 0; index--)
        {
            if (steps[index] is not JsonObject step)
            {
                continue;
            }

            JsonArray? before = (int?)step["step"] is int number
                ? selectedBefore?[number.ToString(CultureInfo.InvariantCulture)] as JsonArray
                : null;
            if (before is null
                ? !(NamesTheEntry(step, name) && steps.Take(index).OfType<JsonObject>().Any(earlier => NamesTheEntry(earlier, name)))
                : !before.Any(node => Fold((string?)node).Trim() == name))
            {
                chooser = index;
            }
        }

        chosen = chooser >= 0;
        if (!chosen)
        {
            // Shown selected before each act of the sub-goal: none chose it (and with no act, nothing moved it there).
            return steps.Count > 0;
        }

        for (int index = chooser; index < steps.Count; index++)
        {
            if (steps[index] is JsonObject act && (bool?)act["ok"] == true
                && ((string?)act["operation"] == "app.open"
                    ? index == chooser && (bool?)act["placeOpened"] == true
                    : (index == chooser || NamesTheEntry(act, name) || (string?)act["operation"] == "input.key.press")
                        && MovedThePlace(act, steps, view)))
            {
                return true;
            }
        }

        return false;
    }

    /// <summary>Whether a verified click of these steps pressed (or opened) a control named <paramref name="name"/>.</summary>
    internal static bool ClickedByName(string? name, JsonArray steps) => ClicksNaming(steps, Fold(name).Trim()).Any();

    /// <summary>
    /// Whether <paramref name="text"/> is what these steps typed, or holds it as whole words while no verified click or
    /// opening after that typing moved the window elsewhere: on screen only because it was typed. Twin of the mind's
    /// cu_evidence._echoes_typing.
    /// </summary>
    internal static bool EchoesTyping(string? text, JsonArray steps)
    {
        string cited = Fold(text).Trim(QuoteMarks);
        if (cited.Length == 0)
        {
            return false;
        }

        for (int index = 0; index < steps.Count; index++)
        {
            if (steps[index] is not JsonObject step || (string?)step["operation"] != "input.text.type"
                || Fold((string?)step["text"]).Trim() is not { Length: > 0 } typed)
            {
                continue;
            }

            if (cited == typed)
            {
                return true;
            }

            bool moved = steps.Skip(index + 1).OfType<JsonObject>().Any(later => (bool?)later["ok"] == true
                && (bool?)later["changed"] != false && (string?)later["operation"] is "input.visible.click" or "app.open");
            if (typed.Length >= 3 && !moved
                && Regex.IsMatch(cited, $@"(?<!\w){Regex.Escape(typed)}(?!\w)", RegexOptions.CultureInvariant))
            {
                return true;
            }
        }

        return false;
    }

    // The verified clicks of these steps on a control so named (its label, without an opening word, or its receipt's name).
    private static IEnumerable<JsonObject> ClicksNaming(JsonArray steps, string name) =>
        steps.OfType<JsonObject>().Where(step => NamesTheEntry(step, name));

    // A verified click on a control so named (its label, without an opening word, or its receipt's name).
    private static bool NamesTheEntry(JsonObject step, string name) =>
        name.Length > 0 && (bool?)step["ok"] == true
        && (string?)step["operation"] == "input.visible.click"
        && (WithoutOpening(Fold((string?)step["label"])).Trim() == name || Fold((string?)step["name"]).Trim() == name);

    /// <summary>
    /// Whether this act moved the window to another place: its receipt saw the surface change, the look after it showed
    /// controls the look before it lacked (<c>broughtNew</c>) or that the sub-goal had not seen (<c>appeared</c>), or the
    /// window's title it reread differs from the one before it (the look it was decided on, <c>titleBefore</c>; without
    /// that record the act right before it, else the sub-goal's first look when it is the first act).
    /// A selection made by its pattern alone (selected, nothing else) moved nothing. Revision 2 of ronda 20b: nor did a
    /// click that only opened the control (<see cref="OnlyOpened"/>), nor an act, a click or a key, whose only novelty
    /// was a menu's entries (<see cref="BroughtOnlyMenu"/>) while the title stayed.
    /// </summary>
    internal static bool MovedThePlace(JsonObject act, JsonArray steps, JsonObject? view)
    {
        if (OnlyOpened(act))
        {
            // Revision 2 of ronda 20b: a click that opened the entry's context menu (manner open or menu) pressed
            // nothing; the menu it drew is no place reached.
            return false;
        }

        if (((bool?)act["surfaceChanged"] == true || (bool?)act["broughtNew"] == true
            || act["appeared"] is JsonArray { Count: > 0 })
            && !BroughtOnlyMenu(act, view))
        {
            return true;
        }

        string title = Fold((string?)act["windowTitle"]).Trim();
        if (title.Length == 0)
        {
            return false;
        }

        // Review 3 of ronda 20b: the title before this act is the one of the look it was decided on (titleBefore).
        // Without that record, only the act right before it tells it, and only by its own reread title (a click's
        // receipt carries none, so nothing is known), or the sub-goal's first look when this act is the first one:
        // an older title would make a key that did nothing after a click that changed the window pass for a move.
        string? before = (string?)act["titleBefore"] is { } decidedOn ? Fold(decidedOn).Trim() : null;
        if (before is null)
        {
            int at = steps.IndexOf(act);
            if (at > 0)
            {
                before = steps[at - 1] is JsonObject previous && Fold((string?)previous["windowTitle"]).Trim() is { Length: > 0 } seen
                    ? seen
                    : null;
            }
            else if (at == 0)
            {
                before = (string?)view?["subgoalFirstText"] is { Length: > 0 } first ? Fold(first.Split('\n', 2)[0]).Trim() : null;
            }
        }

        return before is { Length: > 0 } && before != title;
    }

    // The kinds of a menu's entries and of the menu itself.
    internal static readonly HashSet<string> MenuKinds = new(StringComparer.Ordinal) { "Menu", "MenuItem" };

    /// <summary>
    /// Revision 2 of ronda 20b: all the act made appear were a menu's entries (a context menu opened on the entry by a
    /// click or by a key such as Shift+F10 or the menu key): its receipt says so (<c>appearedOnlyMenu</c>, marked when
    /// the look after it was read), or every name it brought is shown in <paramref name="view"/> only as a menu or a
    /// menu entry. A surface that changed with nothing new named, or with any other control new, is not this.
    /// </summary>
    internal static bool BroughtOnlyMenu(JsonObject act, JsonObject? view)
    {
        if (act["appeared"] is not JsonArray { Count: > 0 } appeared)
        {
            return false;
        }

        if ((bool?)act["appearedOnlyMenu"] == true)
        {
            return true;
        }

        if (view?["controls"] is not JsonArray controls)
        {
            return false;
        }

        return appeared.All(node =>
        {
            string name = Fold((string?)node).Trim();
            var named = controls.OfType<JsonObject>().Where(control => Fold((string?)control["name"]).Trim() == name).ToList();
            return named.Count > 0 && named.All(control => MenuKinds.Contains((string?)control["kind"] ?? string.Empty));
        });
    }

    /// <summary>
    /// Pasada r18 (v3-23): a click on a row of a list (ListItem, DataItem) is no arrival at what its name says when the
    /// window has a navigation tree, the row is a content item (<see cref="IsContentItem"/>) the look still reads and a
    /// tree node of the same name is shown: that node is the place, not the row. By structure (kinds, zones, item types),
    /// never by an application. On receipts alone (no look) a row's click whose receipt is only its selection is
    /// undecided: the look after it decides. Contracase: a row with no tree beside it (a palette's colour) holds as
    /// before, and so does a row that took the window elsewhere (it is no longer read). Review 1 of r21: a row whose
    /// application says what it is (UIA ItemType: a file's type, a folder) is an item in its own right, never the node.
    /// Review 2 of r21 (blocker 1): a row only selected under a chosen, collapsed node is not rejected on the look. A
    /// summary of the node's children (v3-23: «Sistema» under «Registros de Windows») and a row of the node's own
    /// (a value «WallPaper» under a key with subkeys, a file under a folder with subfolders) have the same structure,
    /// both untyped (a Win32 list view fills no ItemType); the look holds it as the click asked.
    /// </summary>
    internal static bool RowStandsForANode(JsonObject step, JsonObject view)
    {
        if ((string?)step["kind"] is not ("ListItem" or "DataItem") || (bool?)step["opened"] == true
            || step["handedTo"] is JsonObject)
        {
            return false;
        }

        if (view["controls"] is not JsonArray controls)
        {
            // Receipts alone cannot see the tree: a row whose receipt is only its selection waits for the look.
            return view["window"] is null && OnlySelectedRow(step);
        }

        return ContentRowBesideATree(step, controls, out string name, out JsonObject[] trees)
            && trees.Any(tree => Fold((string?)tree["name"]).Trim() == name);
    }

    private static bool OnlySelectedRow(JsonObject step) =>
        (bool?)step["selected"] == true
        && (bool?)step["surfaceChanged"] != true
        && (bool?)step["broughtNew"] != true
        && (bool?)step["toggled"] != true
        && (bool?)step["absentOrDisabled"] != true
        && (step["appeared"] is not JsonArray appeared || appeared.Count == 0);

    // The clicked row is an untyped content item of the look and the window has a tree beside it.
    private static bool ContentRowBesideATree(JsonObject step, JsonArray controls, out string name, out JsonObject[] trees)
    {
        string folded = Fold((string?)step["name"] is { Length: > 0 } pressed ? pressed : (string?)step["label"]).Trim();
        name = folded;
        trees = [.. controls.OfType<JsonObject>().Where(control => (string?)control["kind"] == "TreeItem")];
        JsonObject? row = controls.OfType<JsonObject>().FirstOrDefault(control =>
            (string?)control["kind"] == (string?)step["kind"] && Fold((string?)control["name"]).Trim() == folded);
        return folded.Length > 0 && trees.Length > 0 && row is not null && IsContentItem(row, controls)
            && (string?)row["itemType"] is not { Length: > 0 };
    }

    // A ListItem or DataItem out of the window's left column (zones L, TL, BL), where content views list their items
    // and navigation lists never sit; or one in that column that shares its row with another item out of it: a tile of
    // a content grid that starts in the left third (measured on Explorer's Home, maximized: «Escritorio» and
    // «Descargas» are the first tiles of the row whose next tiles sit in the centre; large icons in a narrow window).
    // A side list has no item beside it. Same row: the vertical middles within half the item's height. Without
    // rectangles the zone alone decides.
    internal static bool IsContentItem(JsonObject control, JsonArray? controls = null)
    {
        if ((string?)control["kind"] is not ("ListItem" or "DataItem") || (string?)control["zone"] is not { Length: > 0 } zone)
        {
            return false;
        }

        if (!zone.EndsWith('L'))
        {
            return true;
        }

        if (controls is null || control["rect"] is not JsonObject rect || Number(rect["h"]) <= 0)
        {
            return false;
        }

        double middle = Number(rect["y"]) + (Number(rect["h"]) / 2);
        double reach = Number(rect["h"]) / 2;
        // A tile of the same grid has the item's size; a card of the page beside a navigation list does not (measured
        // on the Clock: the alarms of the page share a row with «Alarma» in the navigation).
        return controls.OfType<JsonObject>().Any(other =>
            !ReferenceEquals(other, control)
            && (string?)other["kind"] is "ListItem" or "DataItem"
            && (string?)other["zone"] is { Length: > 0 } otherZone && !otherZone.EndsWith('L')
            && other["rect"] is JsonObject otherRect && Number(otherRect["h"]) > 0
            && Math.Abs(Number(otherRect["y"]) + (Number(otherRect["h"]) / 2) - middle) <= reach
            && SameSize(rect, otherRect));
    }

    private static bool SameSize(JsonObject rect, JsonObject other)
    {
        double width = Number(rect["w"]);
        double height = Number(rect["h"]);
        return width > 0 && height > 0
            && Math.Abs(Number(other["w"]) - width) <= width * 0.25
            && Math.Abs(Number(other["h"]) - height) <= height * 0.25;
    }

    // The kinds that only show or take text, never an option chosen (twin of the mind's _NEVER_CHOSEN_KINDS).
    private static readonly HashSet<string> NeverChosenKinds = new(StringComparer.Ordinal)
    {
        "Text", "Edit", "Document", "Pane", "Window", "TitleBar", "Group", "ComboBox",
    };

    // A control shown chosen: an item selected, a switch or a toggle button on.
    private static bool Chosen(JsonObject control) =>
        !NeverChosenKinds.Contains((string?)control["kind"] ?? string.Empty)
        && ((string?)control["state"] ?? string.Empty).Split(' ') is { } states
        && (states.Contains("selected", StringComparer.Ordinal) || states.Contains("on", StringComparer.Ordinal));

    /// <summary>
    /// The folded names of every option shown chosen, whatever its kind (a radio button and a toggle button too): the
    /// look right before a click, against which the click is told to have chosen its option or found it chosen.
    /// </summary>
    internal static JsonArray ChosenNames(JsonObject view)
    {
        var names = new JsonArray();
        foreach (JsonObject control in (view["controls"] as JsonArray ?? []).OfType<JsonObject>())
        {
            if (Chosen(control) && Fold((string?)control["name"]) is { Length: > 0 } name)
            {
                names.Add((JsonNode?)JsonValue.Create(name));
            }
        }

        return names;
    }

    // Whether the look right before this click showed its option chosen; null when it was not recorded.
    private static bool? ChosenBeforeClick(JsonObject view, JsonObject click, string name)
    {
        string key = ((int?)click["step"] ?? -1).ToString(CultureInfo.InvariantCulture);
        return view["chosenBeforeClick"]?[key] is JsonArray before
            ? before.Any(node => Bare((string?)node) == name)
            : null;
    }

    private static bool ShowsChosen(JsonObject view, string name) =>
        (view["controls"] as JsonArray ?? []).OfType<JsonObject>()
            .Any(control => Chosen(control) && Bare((string?)control["name"]) == name);

    /// <summary>
    /// Pasada v3 r9 (v3-13): the option cited is shown chosen and no act of the sub-goal chose it: no key nor text was
    /// sent and every click on it found it chosen already. The state asked held before acting; it is told so.
    /// </summary>
    internal static bool AlreadyChosen(string? cited, JsonObject view, JsonArray subgoalSteps)
    {
        string name = Bare(cited);
        return name.Length > 0 && ShowsChosen(view, name)
            && !subgoalSteps.OfType<JsonObject>().Any(step => (bool?)step["ok"] == true
                && (string?)step["operation"] is "input.key.press" or "input.text.type")
            && ActsOn(subgoalSteps, name).All(click => (bool?)click["ok"] == true && ChosenBeforeClick(view, click, name) == true);
    }

    // Review of ronda 20b (finding 1): every click on the control that may have acted on it, verified or pressed with
    // its effect uncertain (a toggle whose sibling's mark never appeared): any uncertain one rules «already» out. Twin
    // of the mind's cu_history._acts_on.
    private static IEnumerable<JsonObject> ActsOn(JsonArray subgoalSteps, string name) =>
        subgoalSteps.OfType<JsonObject>().Where(step => (string?)step["operation"] == "input.visible.click"
            && Pressed(step)
            && ComputerUseMission.MayHaveActed(step)
            && Bare((string?)step["label"]) == name);

    // The folded names of the items shown chosen (selected), the list a click is judged against.
    internal static JsonArray SelectedNames(JsonObject view)
    {
        var names = new JsonArray();
        if (view["controls"] is JsonArray controls)
        {
            foreach (JsonNode? node in controls)
            {
                if (node is JsonObject control
                    && ((string?)control["state"] ?? string.Empty).Split(' ').Contains("selected", StringComparer.Ordinal)
                    && (string?)control["kind"] is "ListItem" or "TreeItem" or "TabItem" or "DataItem" or "MenuItem")
                {
                    names.Add((JsonNode?)JsonValue.Create(Fold((string?)control["name"])));
                }
            }
        }

        return names;
    }
}
