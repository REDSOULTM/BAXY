using System.Globalization;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace Baxy.App;

// What the mind's judge of the «done» needs from the App (the control a click pressed by its identity, the first look's
// ids, the focused part) and the App's own checks of a planned check (exact atoms, a citation off the place).
// Estabilización R16: the App's twin of that judge (EvidenceRefusal) is gone; the mind's _checked_act is the one judge.
internal static partial class ComputerUseSuccessCheck
{
    // The switch state a control shows («on», «off»), or empty: selection, focus and an opened list are no switch.
    private static string SwitchState(JsonObject control)
    {
        string[] states = ((string?)control["state"] ?? string.Empty).Split(' ');
        return states.Contains("on", StringComparer.Ordinal) ? "on" : states.Contains("off", StringComparer.Ordinal) ? "off" : string.Empty;
    }

    /// <summary>
    /// Revisión 2 de r22 (bloqueante 1): the control a click presses, by its identity (its id), as the look right
    /// before the click showed it: its name, state and value. By the click's index, else by its label when one control
    /// alone bears it; null when the control has no id.
    /// </summary>
    internal static JsonObject? ClickedControl(JsonObject view, JsonObject arguments)
    {
        var controls = (view["controls"] as JsonArray ?? []).OfType<JsonObject>().ToList();
        JsonObject? target = null;
        if (arguments["index"] is JsonValue index && index.TryGetValue(out int at))
        {
            target = controls.FirstOrDefault(control => (int?)control["i"] == at);
        }

        if (target is null && Fold((string?)arguments["label"]).Trim() is { Length: > 0 } label)
        {
            var named = controls.Where(control => Fold((string?)control["name"]).Trim() == label).Take(2).ToList();
            target = named.Count == 1 ? named[0] : null;
        }

        return target is not null && (string?)target["id"] is { Length: > 0 } id
            ? new JsonObject
            {
                ["id"] = id,
                ["name"] = target["name"]?.DeepClone(),
                ["state"] = target["state"]?.DeepClone(),
                ["value"] = target["value"]?.DeepClone(),
            }
            : null;
    }

    /// <summary>
    /// Revisión 2 de r22 (bloqueante 1): the steps whose clicked control (<see cref="ClickedControl"/>, by step) is in
    /// the view by the same id and shows another name, another value or another switch state.
    /// </summary>
    internal static List<int> ChangedByClick(JsonObject view, JsonObject clickedBefore)
    {
        var controls = (view["controls"] as JsonArray ?? []).OfType<JsonObject>().ToList();
        var changed = new List<int>();
        foreach (var (key, node) in clickedBefore)
        {
            if (node is not JsonObject was || (string?)was["id"] is not { Length: > 0 } id
                || !int.TryParse(key, NumberStyles.Integer, CultureInfo.InvariantCulture, out int step))
            {
                continue;
            }

            JsonObject? now = controls.FirstOrDefault(control => (string?)control["id"] == id);
            if (now is not null && (Fold((string?)now["name"]).Trim() != Fold((string?)was["name"]).Trim()
                || Fold((string?)now["value"]).Trim() != Fold((string?)was["value"]).Trim()
                || SwitchState(now) != SwitchState(was)))
            {
                changed.Add(step);
            }
        }

        return changed;
    }

    /// <summary>
    /// Ronda 22: the words of a goal or of a piece of a citation that relate a proof to its goal: three letters or
    /// more, cut to five, never one of <paramref name="drop"/>; a word of a <paramref name="kin"/> group stands for the
    /// group's first; every digit is «#» and the word glued to it is read without it («Libro1» is «libro» and «#»). Twin of the mind's semantic.cu_buscar.proof_stems.
    /// </summary>
    internal static HashSet<string> ProofStems(string? text, IEnumerable<string> drop, IEnumerable<JsonArray> kin)
    {
        var dropped = drop.ToHashSet(StringComparer.Ordinal);
        var stems = new Dictionary<string, string>(StringComparer.Ordinal);
        foreach (JsonArray group in kin)
        {
            var cut = group.Select(word => Fold((string?)word)).Where(word => word.Length > 0)
                .Select(word => word.Length > 5 ? word[..5] : word).ToList();
            foreach (string stem in cut)
            {
                stems.TryAdd(stem, cut[0]);
            }
        }

        var found = new HashSet<string>(StringComparer.Ordinal);
        foreach (Match word in Regex.Matches(Fold(text), "[a-z0-9]+", RegexOptions.CultureInvariant))
        {
            string letters = new(word.Value.Where(character => !char.IsAsciiDigit(character)).ToArray());
            if (letters.Length != word.Value.Length)
            {
                found.Add("#");
            }

            if (letters.Length >= 3 && !dropped.Contains(letters))
            {
                string stem = letters.Length > 5 ? letters[..5] : letters;
                found.Add(stems.GetValueOrDefault(stem, stem));
            }
        }

        return found;
    }

    /// <summary>
    /// Ronda 20 P4 (v3-08): the ids (UIA runtime ids, the worker's «id») of a sub-goal's first look that a new part could
    /// be taken for: its empty text parts (a Document or an Edit with no value) and the part that has the keyboard.
    /// </summary>
    internal static JsonArray FirstIds(JsonObject view)
    {
        JsonObject? focused = FocusedControl(view);
        var ids = new JsonArray();
        foreach (JsonObject control in (view["controls"] as JsonArray ?? []).OfType<JsonObject>())
        {
            if ((string?)control["id"] is { Length: > 0 } id
                && (ReferenceEquals(control, focused)
                    || ((string?)control["kind"] is "Document" or "Edit" && string.IsNullOrEmpty((string?)control["value"]))))
            {
                ids.Add((JsonNode?)JsonValue.Create(id));
            }
        }

        return ids;
    }

    /// <summary>The listed control that has the keyboard (window.focused by its index «i»), or null.</summary>
    internal static JsonObject? FocusedControl(JsonObject view)
    {
        if (view["window"]?["focused"] is not JsonObject focused || focused["i"] is not JsonValue at
            || !at.TryGetValue(out int index))
        {
            return null;
        }

        return (view["controls"] as JsonArray ?? []).OfType<JsonObject>().FirstOrDefault(control =>
            control["i"] is JsonValue position && position.TryGetValue(out int listed) && listed == index);
    }

    /// <summary>
    /// Review of cierre-de-subobjetivos (finding 3): a goal whose whole work is to bring something up, so what its act
    /// made appear can close it: opening (data «evidence.openGoal») or going to a place («ir a X», data «placeGoal»).
    /// A drawing, a sort or any goal with an effect of its own is not.
    /// </summary>
    internal static bool BringsUpGoal(string? goal) =>
        !string.IsNullOrWhiteSpace(goal)
        && (OperationFloor.PlaceAsked(goal).Length > 0
            || Regex.IsMatch(Fold(goal).Trim(), (string)OperationFloor.EvidenceRules["openGoal"]!, RegexOptions.CultureInvariant));

    /// <summary>A text typed into a box that only searches (not an address bar, not a name box).</summary>
    internal static bool TypedIntoASearch(JsonObject typedStep) => IsSearchBox((string?)typedStep["into"]);

    // A goal of searching (data «evidence.searchGoal»): the query typed and sent is its own act.
    private static bool SearchGoal(string? goal) =>
        Regex.IsMatch(Fold(goal).Trim(), (string)OperationFloor.EvidenceRules["searchGoal"]!, RegexOptions.CultureInvariant);

    /// <summary>
    /// The sub-goal asks for the act of searching itself: a term of its check also asks for a step done
    /// («title:pdf&stepDone:input.key.press:enter»), so the results titled by the query are what it wants (the same
    /// reading <see cref="Evaluate"/> gives each term).
    /// </summary>
    // The goal is the search itself: a term both submits it (a step done) and reads the results on screen (title: or
    // text:). A receipt-only term («stepDone:input.visible.click:X» of a choice) is no search.
    // Ronda 23 (v2-s01, live r21): the atoms whose truth the engine computes itself, with no resemblance of names: a
    // calculation's value on screen, a field's value, a count of controls, a file written on disk. «born:»
    // is not one: it reads the new window's title by the name said, which a translated title would contradict.
    private static readonly HashSet<string> ExactAtoms = new(StringComparer.Ordinal) { "result", "value", "count", "file", "sent" };

    /// <summary>
    /// Ronda 23 (v2-s01: «calculá 37*12», the Enter did not evaluate, the display read 12 and the model's «done» citing
    /// «Se muestra 12» closed over the planned «result:37*12», which was false): the model's «done» never contradicts an
    /// exact atom of the planned check. True when every alternative of the check has at least one exact atom
    /// (<see cref="ExactAtoms"/>) and in none of them do all its exact atoms hold on the view; the alternatives' other
    /// atoms (a step done, a name on screen) are not read. An alternative judged by names alone leaves the model's
    /// citation to prove it, as before: false.
    /// </summary>
    internal static bool ExactCheckContradicts(string? check, JsonObject view, JsonArray steps, DateTimeOffset? notBefore = null)
    {
        if (string.IsNullOrWhiteSpace(check))
        {
            return false;
        }

        view = OnScreen(view);
        bool anyExact = false;
        foreach (string term in check.Split('|', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
        {
            string[] exact = term.Split('&', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                .Where(atom => ExactAtoms.Contains(AtomKind(atom)))
                .ToArray();
            if (exact.Length == 0)
            {
                return false;
            }

            anyExact = true;
            if (exact.All(atom => Atom(atom, view, steps, notBefore: notBefore)))
            {
                return false;
            }
        }

        return anyExact;
    }

    /// <summary>
    /// Ronda 24 (v3-59: «ir a wikipedia» closed citing «q curico», the query typed into the page's own search, while
    /// the window stayed on the new tab): the twin of <see cref="ExactCheckContradicts"/> for a goal of a place «ir a X».
    /// The model's «done» names the place it arrived at: true when the planned check does not hold on the view and
    /// neither a piece of the citation nor the window's title is the place.
    /// Ronda 28 (tanda c27u2 t2-c03: «ir a pantalla» closed citing «Pantalla de bloqueo», the page a click by
    /// resemblance had opened, because the two share one word): a text is the place only when one of its parts (data
    /// «evidence.placeParts»: «Red e Internet > Wi-Fi», «Wikipedia, la enciclopedia libre», «Bluetooth y dispositivos»)
    /// says every word of one of the place's names and no other (<see cref="ProofStems"/>: five letters, which reads a
    /// misspelt name, and the alias groups of «computerUse.evidenceAliases», which read the other language). The names
    /// are the place, those its check gives it (its title: and page: atoms) and those a translation of this mission
    /// gave it (<paramref name="placeNames"/>). A name that holds the place inside a longer one is another place; the
    /// window's title is read by the same rule, never by a shared word. Revisión 1 de r28: and the citation that names
    /// the place proves it only when the view reads the window there (the control named so chosen where the window is,
    /// or the label it marks); its name written inside another text or on a link is not that. A place arrived at is
    /// proved against the place, never by what BAXY typed nor by a label beside it. A goal that is no place, a check
    /// that holds, a title that names the place, or a citation of the place the view reads as where it is are not
    /// this: false.
    /// </summary>
    internal static bool CitationOffThePlace(
        string? cited, string? goal, string? check, JsonObject view, JsonArray steps, IEnumerable<string>? placeNames = null,
        JsonObject? aliases = null, DateTimeOffset? notBefore = null)
    {
        string place = OperationFloor.PlaceAsked(goal);
        if (place.Length == 0 || Fold(cited).Trim(QuoteMarks).Length == 0 || string.IsNullOrWhiteSpace(check)
            || Evaluate(check, view, steps, out _, aliases, notBefore))
        {
            return false;
        }

        JsonObject rules = OperationFloor.EvidenceRules;
        var drop = (rules["relevanceFillers"] as JsonArray ?? []).Select(node => Fold((string?)node)).ToList();
        drop.AddRange(Regex.Matches(Fold((string?)view["window"]?["process"]), "[a-z0-9]+", RegexOptions.CultureInvariant)
            .Select(match => match.Value));
        var kin = ((JsonObject)OperationFloor.ComputerUseData["evidenceAliases"]!)["groups"] is JsonArray groups
            ? groups.OfType<JsonArray>().ToList()
            : [];
        List<string> names = [.. check.Split(['|', '&'], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Where(atom => AtomKind(atom) is "title" or "page")
            .Select(atom => atom[(atom.IndexOf(':', StringComparison.Ordinal) + 1)..])
            .Prepend(place)
            .Concat(placeNames ?? [])];
        // A name made only of pieces too short to be words («Wi-Fi») is read as its letters joined («wifi»).
        HashSet<string> Words(string? text)
        {
            HashSet<string> stems = ProofStems(text, drop, kin);
            stems.Remove("#");
            if (stems.Count == 0 && Squeezed(Fold(text)) is { Length: >= 3 } joined && !joined.All(char.IsAsciiDigit))
            {
                stems.Add(joined.Length > 5 ? joined[..5] : joined);
            }

            return stems;
        }

        List<HashSet<string>> asked = names.Select(Words).Where(stems => stems.Count > 0).ToList();
        if (asked.Count == 0)
        {
            return false;
        }

        // Each way of splitting a name (by its marks alone; by its marks and the words that join two names): a place
        // whose own name joins two («Bluetooth y dispositivos») is read whole by the first, one of the two by the second.
        var splits = (rules["placeParts"] as JsonArray ?? [])
            .Select(node => new Regex((string)node!, RegexOptions.CultureInvariant | RegexOptions.IgnoreCase)).ToList();
        bool IsThePlace(string? text) => splits.Any(parts =>
            parts.Split(text ?? string.Empty).Select(Words).Any(said => asked.Any(said.SetEquals)));
        // The window's own title names the place and is no echo of what BAXY typed (the guards of the atom title:).
        if (IsThePlace((string?)view["window"]?["title"])
            && !names.Any(name => QueryEchoNames(name, view, steps, false) || TitleEchoedTheTyping(name, steps, view)))
        {
            return false;
        }

        if (!CitationPieces(cited).Any(IsThePlace))
        {
            return true;
        }

        // Revisión 1 de r28 (bloqueante 2: «Pantalla | Personalización» closed the same lock-screen page, its piece
        // «Pantalla» shown only inside «Pantalla de bloqueo»): naming the place proves nothing by itself. The window
        // must show it is there, read as a state: a control named as the place (the same rule, never a longer name
        // nor a field) that is the one chosen where the window is («current»: HasState), or the label the window marks
        // by its ink (MarkAtom, never one a click of the sub-goal may have lit). A link to the place, or its name
        // written anywhere else, is not being there.
        return !(view["controls"] as JsonArray ?? []).OfType<JsonObject>().Any(control => !ClosedMenuEntry(control)
                && (string?)control["kind"] is not ("Edit" or "ComboBox" or "Document")
                && IsThePlace((string?)control["name"]) && HasState(control, "current", view, steps))
            && !(view["textMarks"] as JsonArray ?? []).OfType<JsonObject>()
                .Any(mark => (string?)mark["text"] is { } label && IsThePlace(label) && MarkAtom(label, view, steps));
    }
}
