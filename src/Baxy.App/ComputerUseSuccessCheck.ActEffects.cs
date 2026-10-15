using System.Globalization;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace Baxy.App;

// What an act of the sub-goal did, read on the look: what it opened, pressed, refused or brought (a window, a menu,
// a container, the keyboard focus).
internal static partial class ComputerUseSuccessCheck
{
    /// <summary>
    /// «opened:place=value» (estabilización, encargo C; review H1): an opening of this sub-goal that opened that place of
    /// the application by its address (receipt «placeOpened»), and the value in a line of the window that was not there
    /// on the application's own look right before it (<see cref="ShownLines"/>, recorded when the opening was decided).
    /// The value anywhere is no arrival: the person's page may already show it (Spotify's home lists a band, Steam's
    /// library a game); a line the window shows unchanged proves nothing, and with no look of the application before the
    /// opening nothing is proved. What a field holds is the address's own echo, never a result.
    /// </summary>
    internal static bool PlaceOpened(string rest, JsonObject view, JsonArray steps)
    {
        int equals = rest.IndexOf('=', StringComparison.Ordinal);
        string place = equals > 0 ? Fold(rest[..equals]).Trim() : string.Empty;
        string value = equals > 0 ? Fold(rest[(equals + 1)..]).Trim() : string.Empty;
        if (place.Length == 0 || value.Length == 0)
        {
            return false;
        }

        HashSet<string> now = ShownLines(view);
        foreach (JsonObject step in steps.OfType<JsonObject>())
        {
            if ((bool?)step["ok"] != true || (string?)step["operation"] != "app.open" || (bool?)step["placeOpened"] != true
                || Fold((string?)step[ComputerUseMission.PlaceArgument]).Trim() != place
                || view["textBeforeClick"]?[((int?)step["step"] ?? 0).ToString(CultureInfo.InvariantCulture)] is not JsonArray before)
            {
                continue;
            }

            var shown = new HashSet<string>(before.Select(line => (string?)line ?? string.Empty), StringComparer.Ordinal);
            if (now.Any(line => !shown.Contains(line) && line.Contains(value, StringComparison.Ordinal)))
            {
                return true;
            }
        }

        return false;
    }

    /// <summary>
    /// The folded lines a look shows: the window's title, each control's name (and its value, except a field's, which
    /// holds what was put in it) and each line of written text.
    /// </summary>
    internal static HashSet<string> ShownLines(JsonObject view)
    {
        var lines = new HashSet<string>(StringComparer.Ordinal) { Fold((string?)view["window"]?["title"]).Trim() };
        foreach (JsonObject control in (view["controls"] as JsonArray ?? []).OfType<JsonObject>())
        {
            lines.Add(Fold((string?)control["name"]).Trim());
            if ((string?)control["kind"] is not ("Edit" or "ComboBox" or "Document"))
            {
                lines.Add(Fold((string?)control["value"]).Trim());
            }
        }

        foreach (JsonNode? line in TextLines(view))
        {
            lines.Add(Fold((string?)line).Trim());
        }

        lines.Remove(string.Empty);
        return lines;
    }

    // «focus:search»: the window's keyboard is in a text field (not read-only, not a password, not an address bar) that
    // this sub-goal brought it to: it did not have it at the application's first look, the last verified step was a
    // click on a search control or on that field, or a find key, and nothing was typed (an echo of typed text is never
    // arriving). A search box shown on every page proves nothing until the mission puts the keyboard in it (measured
    // 2026-10-07: the search button focused the box and listed recent searches; no navigation item was chosen).
    private static readonly Regex SearchWord = new(@"\b(?:busc\w*|busqueda|search\w*|find)\b", RegexOptions.CultureInvariant);
    private static readonly Regex AddressWord = new(@"\b(?:direccion\w*|address|url)\b", RegexOptions.CultureInvariant);
    internal static readonly HashSet<string> FindKeys = new(StringComparer.Ordinal) { "ctrl_f", "ctrl_k", "ctrl_e", "f3" };

    // The view read its window behind another one, without the front (v3 point 0). Where the keyboard is in that window
    // is still read (HasKeyboardFocus, ronda 24b x7); a window without an accessible tree says nothing either way.
    internal static bool LookedBehind(JsonObject? view) => (bool?)view?["window"]?["foreground"] == false;

    // Review 1 of r24b (B2): a look behind the person's window that names no focused element cannot tell where the
    // keyboard is (no element of a native window without the front has HasKeyboardFocus; a partial read). In front, no
    // focused element is a fact (the keyboard on the document, which the list does not carry).
    internal static bool FocusUnread(JsonObject? view) => LookedBehind(view) && view?["window"]?["focused"] is not JsonObject;

    internal static string FocusSignature(JsonObject view) =>
        view["window"]?["focused"] is JsonObject focused
            ? $"{(string?)focused["kind"]}|{Fold((string?)focused["name"])}"
            : string.Empty;

    /// <summary>
    /// Goal v3 B3 (review of the closed menus, finding 4): a step that only opened a control's arrow, its list or its
    /// context menu («manner» open or menu) pressed nothing. It is no click on that control for any check that reads a
    /// click as the act done or the place reached: «hacer clic en Nueva pestaña» answered by opening its arrow is not
    /// done. A double click is a press. Ronda 24 (t-menu-3): opening a menu entry whose only action is to open (a
    /// MenuItem the receipt expanded, method «expand») is pressing it, as the ordinary click on it does the very same; the
    /// arrow of a split button (it acts by itself) and the list of a combo box (no value chosen) stay only opened.
    /// </summary>
    internal static bool OnlyOpened(JsonObject step) =>
        (string?)step["operation"] == "input.visible.click" && (string?)step["manner"] is "open" or "menu"
        && !OpenIsItsPress(step);

    /// <summary>
    /// Ronda 24 (t-menu-3): an «open» on a control whose only action is to open: a menu entry (kind MenuItem) the
    /// receipt says it expanded (method «expand») and read open. Twin of cu_history._open_is_its_press.
    /// </summary>
    internal static bool OpenIsItsPress(JsonObject step) =>
        (string?)step["manner"] == "open" && (string?)step["kind"] == "MenuItem"
        && (string?)step["method"] == "expand" && (bool?)step["opened"] == true;

    /// <summary>A click that pressed its control (the ordinary click or a double click), not one that only opened it.</summary>
    internal static bool Pressed(JsonObject step) =>
        (string?)step["operation"] == "input.visible.click" && !OnlyOpened(step);

    internal static int RefusedClicks(JsonArray steps, JsonObject arguments)
    {
        string label = Fold((string?)arguments["label"]);
        string? manner = (string?)arguments["manner"];
        return label.Length == 0
            ? 0
            : steps.OfType<JsonObject>().Count(step =>
                (string?)step["operation"] == "input.visible.click" && (bool?)step["ok"] == false
                && Fold((string?)step["label"]) == label && (string?)step["manner"] == manner);
    }

    /// <summary>
    /// «appeared:X» (pasada r15b, t-form-1, t-form-3): a control named X that an act of this sub-goal made appear (the
    /// step's <c>appeared</c>: in the look after it, in none of the look before it) and the view still shows. What
    /// opens a form is proved by the form itself, never by a field the window showed from the start (a font box on a
    /// ribbon, a side panel always there).
    /// </summary>
    private static bool AppearedByAnAct(string name, JsonObject view, JsonArray steps)
    {
        // Review of cierre-de-subobjetivos (finding 5): the control's whole name (a label's colon aside), never a name
        // that only contains it («Voltear horizontal» is no «Horizontal» field).
        string needle = BareName(name);
        if (needle.Length == 0 || !FindControls(view, name).Any(control => BareName((string?)control["name"]) == needle))
        {
            return false;
        }

        return steps.OfType<JsonObject>().Any(step =>
            (bool?)step["ok"] == true && step["appeared"] is JsonArray appeared
            && appeared.Any(node => BareName((string?)node) == needle));
    }

    /// <summary>The atom «menuOpened:» (ronda 21), lower-cased as atoms are read.</summary>
    internal const string MenuOpenedAtom = "menuopened";

    // The kinds whose own context menu is the menu of an empty space of what they hold (a list, a grid, a tree, a pane).
    private static readonly HashSet<string> MenuContainerKinds = new(StringComparer.Ordinal) { "List", "Tree", "DataGrid", "Table", "Pane" };

    /// <summary>The kind of the control of <paramref name="view"/> at <paramref name="index"/>, or null.</summary>
    internal static string? MenuTargetKind(JsonObject? view, JsonNode? index)
    {
        if (index is not JsonValue value || !value.TryGetValue(out int at))
        {
            return null;
        }

        return (view?["controls"] as JsonArray ?? []).OfType<JsonObject>()
            .Where(control => control["i"] is JsonValue i && i.TryGetValue(out int seen) && seen == at)
            .Select(control => (string?)control["kind"])
            .FirstOrDefault(kind => !string.IsNullOrEmpty(kind));
    }

    /// <summary>
    /// «menuOpened:X» (ronda 21, t-menu-1, t-menu-2): the context menu of X is open, by the state the act left, not by
    /// the key that opens it: a verified click of this sub-goal in the manner «menu» (its context menu by ShowContextMenu
    /// or WM_CONTEXTMENU) on X (its label names X) whose receipt says it opened (<c>opened</c>, unless the front was not
    /// held), or a menu (kind Menu) the view shows after it. Revisión 1 (hallazgo 3): a menu opened on another control
    /// («lista.txt» for «notas.txt») proves nothing of X's. «menuOpened:» with no name is an empty space's: the menu act
    /// on a container (a list, a grid, a tree, a pane: its kind in the view it was decided on), never on an item. A menu
    /// act that failed, or opened nothing, proves nothing: the key stays the fallback.
    /// </summary>
    internal static bool MenuOpenedByAct(string target, JsonObject view, JsonArray steps)
    {
        string named = Fold(target).Trim();
        JsonObject[] menus = [.. steps.OfType<JsonObject>().Where(step => (bool?)step["ok"] == true
            && (string?)step["operation"] == "input.visible.click" && (string?)step["manner"] == "menu"
            && (named.Length > 0
                ? Fold((string?)step["label"]).Contains(named, StringComparison.Ordinal)
                : (string?)step["targetKind"] is { } kind && MenuContainerKinds.Contains(kind)))];
        if (menus.Length == 0)
        {
            return false;
        }

        if (menus.Any(step => (bool?)step["opened"] == true))
        {
            return true;
        }

        return (view["controls"] as JsonArray ?? []).OfType<JsonObject>().Any(control => (string?)control["kind"] == "Menu");
    }

    /// <summary>The folded names of the view's tabs (TabItem), one per tab: two tabs of one name are two entries.</summary>
    internal static JsonArray TabNames(JsonObject view) =>
        new([.. (view["controls"] as JsonArray ?? []).OfType<JsonObject>()
            .Where(control => (string?)control["kind"] == "TabItem")
            .Select(control => (JsonNode?)JsonValue.Create(Fold((string?)control["name"])))]);

    /// <summary>
    /// Ronda 20 P8 (v3-37 «abrí una pestaña nueva de símbolo del sistema»): the atom «born:X», a container of kind X
    /// opened in this sub-goal. A tab (TabItem) chosen whose name holds X while the view shows more tabs so named than
    /// the sub-goal's first look did (view «subgoalFirstTabs»: one already open is no new one, another born is), or a
    /// window that came during the mission (born) titled with X when the first look's title was not.
    /// Review 1 of r20 P8 (finding 1): and more tabs in all than the first look showed (the person's tab renamed by
    /// going to X in it, «Google» become «YouTube», is no tab born); and a window none the first look knew (view
    /// «subgoalFirstWindows»: the one it read, those born earlier in the mission), so a look without that record
    /// proves no window born.
    /// </summary>
    internal static bool BornContainer(string kind, JsonObject view)
    {
        string named = Fold(kind).Trim(QuoteMarks);
        if (named.Length == 0)
        {
            return false;
        }

        if (view["subgoalFirstTabs"] is JsonArray before)
        {
            List<JsonObject> tabs = [.. (view["controls"] as JsonArray ?? []).OfType<JsonObject>()
                .Where(control => (string?)control["kind"] == "TabItem"
                    && Fold((string?)control["name"]).Contains(named, StringComparison.Ordinal))];
            int earlier = before.Count(name => Fold((string?)name).Contains(named, StringComparison.Ordinal));
            int all = (view["controls"] as JsonArray ?? []).OfType<JsonObject>().Count(control => (string?)control["kind"] == "TabItem");
            if (tabs.Count > earlier && all > before.Count && tabs.Any(tab =>
                    ((string?)tab["state"] ?? string.Empty).Split(' ').Contains("selected", StringComparer.Ordinal)))
            {
                return true;
            }
        }

        string firstTitle = ((string?)view["subgoalFirstText"] ?? string.Empty).Split('\n', 2)[0];
        return view["window"] is JsonObject window && (bool?)window["born"] == true
            && LongOf(window["hwnd"]) is long hwnd && view["subgoalFirstWindows"] is JsonArray knownThen
            && !knownThen.Any(known => LongOf(known) == hwnd)
            && Fold((string?)window["title"]).Contains(named, StringComparison.Ordinal)
            && !firstTitle.Contains(named, StringComparison.Ordinal);
    }

    /// <summary>
    /// The windows a sub-goal's first look knows (review 1 of r20 P8, finding 1): those born earlier in the mission
    /// (<paramref name="born"/>) and the one it reads.
    /// </summary>
    internal static JsonArray KnownWindows(JsonArray? born, JsonObject view)
    {
        JsonArray known = born?.DeepClone() as JsonArray ?? [];
        if (view["window"]?["hwnd"] is JsonNode hwnd)
        {
            known.Add(hwnd.DeepClone());
        }

        return known;
    }

    // A folded name without the punctuation a label ends with («Tamaño:» is «tamano»).
    private static string BareName(string? name) => Fold(name).TrimEnd(':', '.', '…', '*', ' ');

    /// <summary>
    /// The atom «appeared:X» that closes a free sub-goal (pasada r15b): X is a control the next sub-goal's check names
    /// (control:X, with or without its state), an act of this sub-goal made it appear, the view shows it and the
    /// sub-goal's first look listed no control named so. Null when none.
    /// </summary>
    internal static string? NextSubgoalBroughtUp(string? nextCheck, JsonObject view, JsonArray steps, string? firstLook)
    {
        if (string.IsNullOrWhiteSpace(nextCheck))
        {
            return null;
        }

        var listedFirst = (firstLook ?? string.Empty).Split('\n').Skip(1).Select(line => line.Split('\t', 2)[0]).ToList();
        foreach (string atom in nextCheck.Split('|', '&'))
        {
            if (AtomKind(atom) != "control")
            {
                continue;
            }

            string name = atom.Trim()[(atom.Trim().IndexOf(':', StringComparison.Ordinal) + 1)..].TrimStart('=');
            int split = name.LastIndexOf(':');
            if (split > 0 && ControlStates.Contains(name[(split + 1)..]))
            {
                name = name[..split];
            }

            string needle = Fold(name);
            if (needle.Length > 0 && !listedFirst.Any(listed => listed.Contains(needle, StringComparison.Ordinal))
                && AppearedByAnAct(name, view, steps))
            {
                return $"appeared:{name}";
            }
        }

        return null;
    }

    private static bool FocusBrought(string rest, JsonObject view, JsonArray steps)
    {
        if (Fold(rest) != "search" || view["window"]?["focused"] is not JsonObject focused
            || (string?)focused["kind"] is not ("Edit" or "ComboBox")
            // Review 2 of r24b (B2): a start known (a look before any step of the sub-goal) is a guard; none known,
            // the step that moved the keyboard (focusBeforeStep, below) is the whole proof.
            || (view["focusAtStart"] is JsonValue start && start.TryGetValue(out string? atStart)
                && FocusSignature(view) == atStart))
        {
            return false;
        }

        string name = Fold((string?)focused["name"]);
        if (AddressWord.IsMatch(name))
        {
            return false;
        }

        JsonObject? listed = (view["controls"] as JsonArray)?.OfType<JsonObject>().FirstOrDefault(control =>
            (string?)control["kind"] == (string?)focused["kind"] && Fold((string?)control["name"]) == name);
        string[] states = Fold((string?)listed?["state"]).Split(' ');
        if (states.Contains("readonly") || states.Contains("password"))
        {
            return false;
        }

        if (steps.OfType<JsonObject>().Any(step => (string?)step["operation"] == "input.text.type"))
        {
            return false;
        }

        JsonObject? last = steps.OfType<JsonObject>().LastOrDefault(step => (bool?)step["ok"] == true);
        // Ronda 24b (x7): the step that arrived is the one that moved the keyboard into the field, in front or behind:
        // the focus on the look it was decided on differs from the one now. Not known, no proof.
        if (last?["step"] is not JsonValue number || !number.TryGetValue(out int stepNumber)
            || view["focusBeforeStep"]?[stepNumber.ToString(CultureInfo.InvariantCulture)] is not JsonValue before
            || !before.TryGetValue(out string? focusBefore) || focusBefore == FocusSignature(view))
        {
            return false;
        }

        switch ((string?)last?["operation"])
        {
            case "input.key.press":
                return FindKeys.Contains(Fold((string?)last!["key"]));
            case "input.visible.click":
                string label = Fold((string?)last!["label"]);
                return !OnlyOpened(last!) && !AddressWord.IsMatch(label) && (SearchWord.IsMatch(label) || (name.Length > 0 && label == name));
            default:
                return false;
        }
    }
}
