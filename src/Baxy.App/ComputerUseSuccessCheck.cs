using System.Globalization;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace Baxy.App;

/// <summary>
/// The deterministic success check of a mission (CONTRATO_VISTA_ACCION.md
/// §4.3), evaluated by the shell over the last view and over independent
/// receipts; never by the model.
/// </summary>
internal static partial class ComputerUseSuccessCheck
{
    internal static bool Evaluate(
        string? check, JsonObject view, JsonArray steps, out string? satisfiedBy, JsonObject? aliases = null,
        DateTimeOffset? notBefore = null, IReadOnlyList<TypedEarlier>? typedBefore = null)
    {
        satisfiedBy = null;
        if (string.IsNullOrWhiteSpace(check))
        {
            return false;
        }

        // Revision 3 of ronda 20b (B-A): what a check reads is what is on screen; a closed menu's entries are listed
        // to be pressed by their command, never shown.
        view = OnScreen(view);
        // Ronda 24b (banco r23, y12): the choices whose click receipt shows only pixels. A term that holds only through
        // one of them is set aside: the rest of the check is read on this look first.
        JsonArray? withoutPixelChoices = WithoutPixelOnlyChoices(steps);
        foreach (string term in check.Split('|', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
        {
            string[] said = term.Split('&', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
            // A term that also asks for an act («title:X&stepDone:input.key.press:enter») is a search's own proof:
            // the results titled by what was searched are what it wants.
            bool searchResultsProve = said.Any(atom => AtomKind(atom) == "stepdone");
            foreach (string[] atoms in WithAliases(said, aliases))
            {
                if (atoms.Length > 0 && atoms.All(atom => Atom(atom, view, steps, searchResultsProve, notBefore, typedBefore)))
                {
                    if (withoutPixelChoices is not null && !atoms.All(atom => !IsClickStepDone(atom)
                            || Atom(atom, view, withoutPixelChoices, searchResultsProve, notBefore, typedBefore)))
                    {
                        continue;
                    }

                    satisfiedBy = ReferenceEquals(atoms, said) ? term : string.Join('&', atoms);
                    return true;
                }
            }
        }

        // Revision 1 of ronda 24b (B2): no other term held, so the sub-goal stays open. A name that came on screen by any
        // other act of the sub-goal (the gallery that opened before the choice) never proves the choice; one that the
        // choice itself brought makes it no pixel-only choice (PixelOnlyChoice) and its term held above.
        return false;
    }

    // UI Automation kinds of an entry that is chosen (a swatch, an option, a tab, a node, a row): a click on one is a
    // choice, and its receipt can say so (selected, toggled).
    private static readonly HashSet<string> ChoiceKinds = new(StringComparer.Ordinal)
    {
        "ListItem", "RadioButton", "TabItem", "TreeItem", "DataItem",
    };

    /// <summary>
    /// Ronda 24b (banco r23, y12): a verified click on an entry that is chosen whose receipt shows only the window's
    /// pixels (surfaceChanged, the window's hash): not selected, not toggled, not gone nor disabled (a gallery that
    /// closes on choosing), no popup, no new window and no change of front. Paint's swatch «Verde» gave
    /// surfaceChanged with selected=false; a focus ring or a hover redraws the pixels too. Such a receipt never closes a
    /// sub-goal alone: the look after it decides. Only when the post-read measured the selection (selected=false is in
    /// the receipt): a receipt that does not say it proves what it did before.
    /// Revision 1 of ronda 24b (B1, B3): nor when the look after the click found a name no look before it had (the step's
    /// <c>appeared</c>, MarkAppeared): that is more than pixels. Measured in the bank r23: Paint's swatch «Añil» said
    /// selected=false while the indicator's name went from «Color 1: Negro» to «Color 1: Añil» (e2), and Settings'
    /// ListItem «Colores» said selected=false while its page came («Elige tu modo», c5). Until that look is read (the
    /// receipts before it) the choice is set aside; a look that brought no new name leaves it pixel-only.
    /// </summary>
    internal static bool PixelOnlyChoice(JsonObject step) =>
        (string?)step["operation"] == "input.visible.click" && (bool?)step["ok"] == true
        && ChoiceKinds.Contains((string?)step["kind"] ?? string.Empty)
        && step["selected"] is JsonValue selected && selected.TryGetValue(out bool isSelected) && !isSelected
        && !EffectKeys.Any(key => (bool?)step[key] == true)
        && step["appeared"] is not JsonArray { Count: > 0 };

    // What a click receipt says the press did besides redrawing the window (the worker's post-read and the front's).
    private static readonly string[] EffectKeys =
    [
        "toggled", "absentOrDisabled", "popupBorn", "frontChanged", "broughtNew", "opened", "closed", "newDocument",
        "fieldTook", "dialogOpened", "targeted",
    ];

    /// <summary>The steps without the pixel-only choices (<see cref="PixelOnlyChoice"/>), or null when there is none.</summary>
    internal static JsonArray? WithoutPixelOnlyChoices(JsonArray steps)
    {
        if (!steps.OfType<JsonObject>().Any(PixelOnlyChoice))
        {
            return null;
        }

        return new JsonArray([.. steps.Where(node => node is not JsonObject step || !PixelOnlyChoice(step))
            .Select(node => node?.DeepClone())]);
    }

    private static bool IsClickStepDone(string atom) =>
        AtomKind(atom) == "stepdone"
        && atom[(atom.IndexOf(':', StringComparison.Ordinal) + 1)..].TrimStart()
            .StartsWith("input.visible.click", StringComparison.OrdinalIgnoreCase);

    // The exact atoms a witness is quoted for: what the screen or the disk showed, measured.
    private static readonly HashSet<string> WitnessAtoms = new(StringComparer.Ordinal) { "result", "value", "count", "file", "mark" };

    /// <summary>
    /// Ronda 24b (banco r23, e1): what an exact atom of the term that closed a sub-goal read, so the judge sees it
    /// without believing the final: {atom, via, shown, read}. «via» is where it was read (uia.&lt;kind&gt; for a control's
    /// name or value, ocr.&lt;zone&gt; for a line of the window's text, mark.&lt;zone&gt; for a text mark, count.&lt;kind&gt;,
    /// file); «shown» is what was measured there (cut to 160): the control's or line's text, the number of controls of
    /// that kind counted on the look, the file's size and last write time on disk. Revision 1 of r24b (B4): never the
    /// atom's own text. «read» is the mission id the journal recorded that look under (the view's «readMission»), so
    /// the judge finds the read itself; absent for a file. Null when the term has no such atom or the view does not
    /// carry it.
    /// </summary>
    internal static JsonObject? Witness(string? satisfiedBy, JsonObject? view)
    {
        if (string.IsNullOrWhiteSpace(satisfiedBy))
        {
            return null;
        }

        foreach (string atom in satisfiedBy.Split('&', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
        {
            string kind = AtomKind(atom);
            if (!WitnessAtoms.Contains(kind))
            {
                continue;
            }

            string rest = atom[(atom.IndexOf(':', StringComparison.Ordinal) + 1)..].Trim();
            if (view is null && kind != "file")
            {
                continue;
            }

            (string, string)? found = kind switch
            {
                "file" => FileSource(rest),
                "count" => CountSource(rest, view!),
                "result" => ResultSource(rest, view!),
                "value" => ValueSource(rest, view!),
                _ => MarkSource(rest, view!),
            };
            if (found is { } source)
            {
                string shown = source.Item2;
                var witness = new JsonObject
                {
                    ["atom"] = atom.Length > 160 ? atom[..160] : atom,
                    ["via"] = source.Item1,
                    ["shown"] = shown.Length > 160 ? shown[..160] : shown,
                };
                if (kind != "file" && (string?)view?["readMission"] is { Length: > 0 } read)
                {
                    witness["read"] = read;
                }

                return witness;
            }
        }

        return null;
    }

    /// <summary>The witness's source as a trace label with no content («uia.text», «ocr.tl», «file»).</summary>
    internal static string WitnessLabel(JsonObject witness) =>
        $"{AtomKind((string?)witness["atom"] ?? string.Empty)}.{new string(((string?)witness["via"] ?? "none").ToLowerInvariant().Where(c => char.IsAsciiLetterLower(c) || c == '.').ToArray())}";

    private static (string, string)? ResultSource(string expression, JsonObject view)
    {
        double[] values = CalculationValues(expression);
        bool Carries(string? text) => text is { Length: > 0 } && values.Length > 0 && ShownNumbers(text).Any(number =>
            values.Any(value => Math.Abs(number - value) <= 1e-9 * Math.Max(1, Math.Abs(value))));
        foreach (JsonObject control in (view["controls"] as JsonArray ?? []).OfType<JsonObject>())
        {
            if (Carries((string?)control["name"]))
            {
                return ($"uia.{(string?)control["kind"]}", (string?)control["name"] ?? string.Empty);
            }

            if (Carries((string?)control["value"]))
            {
                return ($"uia.{(string?)control["kind"]}", (string?)control["value"] ?? string.Empty);
            }
        }

        return TextSource(view, Carries);
    }

    // The file on disk as it is now: its size and last write time, measured (the atom held on them, «file:»).
    private static (string, string)? FileSource(string path)
    {
        try
        {
            var file = new FileInfo(path);
            return Path.IsPathRooted(path) && file.Exists
                ? ("file", $"{file.Length.ToString(CultureInfo.InvariantCulture)} B, {file.LastWriteTimeUtc.ToString("O", CultureInfo.InvariantCulture)}")
                : null;
        }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException or ArgumentException
            or NotSupportedException or System.Security.SecurityException)
        {
            return null;
        }
    }

    // How many controls of the atom's kind the look counted (what CountAtom compared).
    private static (string, string)? CountSource(string rest, JsonObject view) =>
        CountExpression.Match(rest) is { Success: true } match
            ? ($"count.{match.Groups[1].Value}", CountOf(match.Groups[1].Value, view).ToString(CultureInfo.InvariantCulture))
            : null;

    private static (string, string)? ValueSource(string rest, JsonObject view)
    {
        int equals = rest.IndexOf('=', StringComparison.Ordinal);
        if (equals <= 0)
        {
            return null;
        }

        string needle = Fold(rest[(equals + 1)..]);
        return FindControls(view, rest[..equals]).FirstOrDefault(control => ValueHolds(Fold((string?)control["value"]), needle))
            is { } field
            ? ($"uia.{(string?)field["kind"]}", (string?)field["value"] ?? string.Empty)
            : null;
    }

    private static (string, string)? MarkSource(string rest, JsonObject view)
    {
        string wanted = Fold(rest);
        foreach (JsonObject mark in (view["textMarks"] as JsonArray ?? []).OfType<JsonObject>())
        {
            if (wanted.Length > 0 && Fold((string?)mark["text"]).Contains(wanted, StringComparison.Ordinal))
            {
                return ($"mark.{(string?)mark["zone"]}", $"{(string?)mark["text"]} ink={(string?)mark["ink"]}");
            }
        }

        return TextSource(view, text => wanted.Length > 0 && Fold(text).Contains(wanted, StringComparison.Ordinal));
    }

    private static (string, string)? TextSource(JsonObject view, Func<string, bool> carries)
    {
        if (view["text"] is not JsonObject zones)
        {
            return null;
        }

        foreach ((string zone, JsonNode? lines) in zones)
        {
            foreach (JsonNode? line in lines as JsonArray ?? [])
            {
                if (line is JsonValue value && value.TryGetValue(out string? text) && carries(text))
                {
                    return ($"ocr.{zone}", text);
                }
            }
        }

        return null;
    }

    /// <summary>
    /// Revision 3 of ronda 20b (B-A): an entry of a window's classic menu read without opening it (the worker's
    /// «nameSource» «menu», identity «hmenu.&lt;id&gt;»). It is listed so it can be pressed by its command, but it is not
    /// on screen: it never proves that a control or a text shows. Twin of the mind's cu_view.closed_menu_entry.
    /// </summary>
    internal static bool ClosedMenuEntry(JsonObject control) =>
        (string?)control["nameSource"] == "menu"
        || ((string?)control["id"])?.StartsWith("hmenu.", StringComparison.Ordinal) == true;

    /// <summary>The view without the entries of closed menus: what is on screen (the same view when it has none).</summary>
    internal static JsonObject OnScreen(JsonObject view)
    {
        if (view["controls"] is not JsonArray controls || !controls.OfType<JsonObject>().Any(ClosedMenuEntry))
        {
            return view;
        }

        var shown = new JsonObject();
        foreach ((string key, JsonNode? value) in view)
        {
            shown[key] = key == "controls"
                ? new JsonArray([.. controls.Where(node => node is not JsonObject control || !ClosedMenuEntry(control))
                    .Select(node => node?.DeepClone())])
                : value?.DeepClone();
        }

        return shown;
    }

    // The atom kinds whose whole argument is a place's name (contract §4.4.1).
    private static readonly HashSet<string> NamedAtoms = new(StringComparer.Ordinal) { "text", "title", "page", "header", "mark" };
    private static readonly HashSet<string> ControlStates = new(StringComparer.Ordinal)
    {
        "selected", "current", "on", "off", "expanded", "focused", "collapsed",
    };

    /// <summary>
    /// A term's atoms as planned, then once per validated alias (the place said → the name it carries on screen,
    /// mission state «aliases»: {folded said: [names]}) with the said name replaced where an atom names it whole.
    /// The planned check (≤ 512 bytes) never changes; only what each of its atoms may be called on screen.
    /// </summary>
    internal static IEnumerable<string[]> WithAliases(string[] atoms, JsonObject? aliases)
    {
        yield return atoms;
        if (aliases is null)
        {
            yield break;
        }

        foreach ((string from, JsonNode? names) in aliases)
        {
            if (names is not JsonArray targets)
            {
                continue;
            }

            foreach (JsonNode? target in targets)
            {
                string? to = target is JsonValue value && value.TryGetValue(out string? text) ? text : null;
                if (string.IsNullOrWhiteSpace(to) || Fold(to) == Fold(from))
                {
                    continue;
                }

                string[] renamed = atoms.Select(atom => AliasAtom(atom, from, to)).ToArray();
                if (!renamed.SequenceEqual(atoms, StringComparer.Ordinal))
                {
                    yield return renamed;
                }
            }
        }
    }

    private static string AliasAtom(string atom, string from, string to)
    {
        int colon = atom.IndexOf(':', StringComparison.Ordinal);
        if (colon <= 0)
        {
            return atom;
        }

        string head = atom[..(colon + 1)];
        string kind = atom[..colon].Trim().ToLowerInvariant();
        string rest = atom[(colon + 1)..].Trim();
        string wanted = Fold(from);
        switch (kind)
        {
            case "stepdone":
                {
                    // Only a click's label is a place's name («stepDone:input.visible.click:crop»).
                    string[] parts = rest.Split(':', 2);
                    if (parts.Length < 2 || parts[0].Trim() != "input.visible.click")
                    {
                        return atom;
                    }

                    string name = parts[1].TrimStart('=');
                    return Fold(name) == wanted ? head + parts[0] + ":==" + to : atom;
                }

            case "control":
                {
                    string name = rest;
                    string suffix = string.Empty;
                    int split = rest.LastIndexOf(':');
                    if (split > 0 && ControlStates.Contains(rest[(split + 1)..]))
                    {
                        name = rest[..split];
                        suffix = rest[split..];
                    }

                    name = name.TrimStart('=');
                    // The translated name is the control's whole name (the mind matched it exactly): never a longer
                    // control that holds it.
                    return Fold(name) == wanted ? head + "==" + to + suffix : atom;
                }

            default:
                return NamedAtoms.Contains(kind) && Fold(rest) == wanted ? head + to : atom;
        }
    }

    // Atoms that read verified receipts and the disk, never the screen.
    private static readonly HashSet<string> ReceiptAtoms = new(StringComparer.Ordinal) { "stepdone", "file", MenuOpenedAtom };

    /// <summary>
    /// The check evaluated on receipts alone: a term holds only when every atom
    /// in it reads a verified step or a file. Such a term needs no
    /// new look at the screen to be known.
    /// </summary>
    internal static bool EvaluateReceipts(
        string? check, JsonArray steps, out string? satisfiedBy, JsonObject? aliases = null, DateTimeOffset? notBefore = null)
    {
        satisfiedBy = null;
        if (string.IsNullOrWhiteSpace(check))
        {
            return false;
        }

        var nothingSeen = new JsonObject();
        // Ronda 24b (banco r23, y12): a choice whose click receipt shows only pixels proves nothing on receipts alone;
        // the look after it reads the whole check (Evaluate).
        steps = WithoutPixelOnlyChoices(steps) ?? steps;
        foreach (string term in check.Split('|', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
        {
            string[] said = term.Split('&', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
            foreach (string[] atoms in WithAliases(said, aliases))
            {
                if (atoms.Length > 0
                    && atoms.All(atom => ReceiptAtoms.Contains(AtomKind(atom)) && !JudgedOnScreen(atom) && Atom(atom, nothingSeen, steps, notBefore: notBefore)))
                {
                    satisfiedBy = ReferenceEquals(atoms, said) ? term : string.Join('&', atoms);
                    return true;
                }
            }
        }

        return false;
    }

    // Typed text is a receipt only when the field cannot show it: whether it arrived is read on the next look
    // (TypedTextShows), never from the keys Windows accepted.
    private static bool JudgedOnScreen(string atom) =>
        atom.Trim().StartsWith("stepDone:input.text.type", StringComparison.OrdinalIgnoreCase);

    private static string AtomKind(string atom)
    {
        int colon = atom.IndexOf(':', StringComparison.Ordinal);
        return colon <= 0 ? string.Empty : atom[..colon].Trim().ToLowerInvariant();
    }

    /// <summary>When the sub-goal under way began (its state «subgoalStartedUtc», else the mission's «startedUtc»).</summary>
    internal static DateTimeOffset? SubgoalStarted(JsonObject state) =>
        DateTimeOffset.TryParse((string?)state["subgoalStartedUtc"] ?? (string?)state["startedUtc"],
            CultureInfo.InvariantCulture, DateTimeStyles.RoundtripKind, out DateTimeOffset started)
            ? started
            : null;

    // File systems that keep coarse write times (FAT: 2 s) may stamp a file written right after the start a little
    // before it.
    private static readonly TimeSpan FileTimeSlack = TimeSpan.FromSeconds(2);

    // Ronda 20b, revisión 1 (bloqueante 4): a number holds in a field only within digit bounds. With the aspect lock on,
    // a 3000×1000 image set to 500 high moved the width to 1500, and «1500» contained «500». «500 px» and «500px» hold
    // it; «1500», «500,5» and «2.500» do not. A value with letters still holds by containment. Revisión 2 (bloqueante 2):
    // the decimal zeros a window formats the number with («5,00 cm», «500,00», «500.0 px») hold it, as containment did.
    private static readonly Regex NumericValue = new(@"^[0-9]+(?:[.,][0-9]+)?$", RegexOptions.CultureInvariant);

    /// <summary>Whether a field's value (folded) holds the value of a <c>value:</c> atom (folded).</summary>
    internal static bool ValueHolds(string shown, string needle)
    {
        string number = needle.Trim();
        if (!NumericValue.IsMatch(number))
        {
            return shown.Contains(needle, StringComparison.Ordinal);
        }

        string zeros = number.Contains('.', StringComparison.Ordinal) || number.Contains(',', StringComparison.Ordinal)
            ? "0*"
            : "(?:[.,]0+)?";
        return Regex.IsMatch(
            shown, $"(?<![0-9])(?<![0-9][.,]){Regex.Escape(number)}{zeros}(?![.,]?[0-9])", RegexOptions.CultureInvariant);
    }

    internal static bool Atom(
        string atom, JsonObject view, JsonArray steps, bool searchResultsProve = false, DateTimeOffset? notBefore = null,
        IReadOnlyList<TypedEarlier>? typedBefore = null)
    {
        int colon = atom.IndexOf(':', StringComparison.Ordinal);
        if (colon <= 0)
        {
            return false;
        }

        string kind = atom[..colon].Trim().ToLowerInvariant();
        string rest = atom[(colon + 1)..].Trim();
        // Encargo S (banco e1 y8: the library opened by the first press, its button renamed two looks later; e2 u1: a
        // stranger's list «Tu biblioteca» titled the page while the library's own button still offered to open it): a
        // place with its own button is open or closed by that button alone. Open proves «page:»; closed, no atom of the
        // place (its title, its mark, a control of its name current or selected) does.
        if (PlaceOfAtom(kind, rest) is { } placed && PlaceToggle(placed, view) is bool open && (!open || kind == "page"))
        {
            return open;
        }

        switch (kind)
        {
            case "sent":
                return Sent(rest, view, steps);
            case "text":
                // A search's own proof reads its results, never only the box that repeats the query. Pasada r15b (v3-42):
                // and only while a field of the window holds what was typed; a list that names it unfiltered
                // («Google Chrome» among the installed programs) shows no search done.
                return (ViewContains(view, rest) && !(searchResultsProve
                        && (OnlyTheQueryShows(rest, view, steps) || !TypedQueryHeld(rest, view, steps))))
                    || (searchResultsProve && ResultInAnyOrder(rest, view, steps) && TypedQueryHeld(rest, view, steps));
            case "title":
                // Ronda 24b (u9): a web page drawn inside an application's own window (CEF, Electron, WebView2) titles
                // its root document, not the window («Spotify Premium» over the document «Spotify – Buscar»); that page
                // title is a second source, under the same echo guards. In a browser both are one.
                return view["window"] is JsonObject titled
                    && (Fold((string?)titled["title"]).Contains(Fold(rest), StringComparison.Ordinal)
                        || Fold(PageTitle(view)).Contains(Fold(rest), StringComparison.Ordinal))
                    && !QueryEchoNames(rest, view, steps, searchResultsProve, typedBefore)
                    && !TitleEchoedTheTyping(rest, steps, view);
            case "process":
                return view["window"] is JsonObject owned
                    && Fold((string?)owned["process"]).Contains(Fold(rest), StringComparison.Ordinal);
            case "control":
                {
                    string name = rest;
                    string? state = null;
                    int split = rest.LastIndexOf(':');
                    if (split > 0 && rest[(split + 1)..] is "selected" or "current" or "on" or "off" or "expanded" or "focused" or "collapsed")
                    {
                        name = rest[..split];
                        state = rest[(split + 1)..];
                    }

                    // «control:=informe»: the name whole, not inside a longer word («informe2» is not «informe»;
                    // «general (canal de texto)» is «general»). «control:==Datos» (an alias, §4.4.1): the control's
                    // name is exactly that, never a longer one that holds it («Uso de datos»).
                    bool exact = name.StartsWith("==", StringComparison.Ordinal);
                    bool whole = name.StartsWith('=');
                    name = exact ? name[2..] : whole ? name[1..] : name;

                    // What BAXY itself typed into a search or an address bar (its suggestions echo the query) never
                    // proves arriving (measured: the Explorer search echo passed for a folder that was never
                    // created). A name typed into the box of an item being created or renamed is that item's name.
                    var typed = new HashSet<string>(
                        steps.OfType<JsonObject>()
                            .Where(step => (string?)step["operation"] == "input.text.type" && EchoesItsQuery(step))
                            .Select(step => Fold((string?)step["text"])),
                        StringComparer.Ordinal);
                    // A tab selected or current that bears the query is the same echo (measured on Explorer: the tab
                    // «imagenes - Resultados de la búsqueda en Trabajo» passed control:imagenes:current).
                    // Ronda 23 (v3-58): and so is a tab of a web search's results page whose query holds the name an
                    // earlier turn of BAXY typed (QueryEchoNames, typedBefore: «configuración - Búsqueda» left selected).
                    // Revisión 3 r23: the screen alone never says it; the person's own search tab («gatos - Buscar con
                    // Google») is a tab they can be taken to and read.
                    // Encargo TZ-OSC (tandas z3/z4 t4-c04 t3): an option shown selected that is the value of a choice
                    // box of the window (ChoiceBoxValue) is that choice's value, never the query's echo, even when its
                    // name is what was typed («oscuro» typed, «Elige tu modo» = Oscuro with «Oscuro» selected).
                    bool echo = (state is "selected" or "current")
                        && QueryEchoNames(name, view, steps, searchResultsProve, typedBefore);
                    return FindControls(view, name).Any(control =>
                        (string?)control["kind"] is not ("Edit" or "ComboBox" or "Document")
                        && ((!echo && !typed.Contains(Fold((string?)control["name"])))
                            || (state == "selected" && Fold((string?)control["name"]).Trim() == Fold(name).Trim()
                                && ChoiceBoxValue(control, view, steps)))
                        && (!whole || NamesWhole(Fold((string?)control["name"]), Fold(name)))
                        && (!exact || Fold((string?)control["name"]).Trim() == Fold(name).Trim())
                        && (state is null || HasState(control, state, view, steps)));
                }
            case "value":
                {
                    int equals = rest.IndexOf('=', StringComparison.Ordinal);
                    if (equals <= 0)
                    {
                        return false;
                    }

                    string needle = Fold(rest[(equals + 1)..]);
                    return FindControls(view, rest[..equals]).Any(control =>
                        ValueHolds(Fold((string?)control["value"]), needle));
                }
            case "result":
                return ResultShows(rest, view);
            case "count":
                return CountAtom(rest, view);
            case "page":
                return !QueryEchoNames(rest, view, steps, searchResultsProve, typedBefore) && PageAtom(rest, view, steps);
            case "mark":
                return !QueryEchoNames(rest, view, steps, searchResultsProve, typedBefore)
                    && MarkAtom(rest, view, steps);
            case "header":
                return HeaderAppeared(rest, view, steps);
            case "focus":
                return FocusBrought(rest, view, steps);
            case "appeared":
                return AppearedByAnAct(rest, view, steps);
            case MenuOpenedAtom:
                return MenuOpenedByAct(rest, view, steps);
            case "born":
                // Review 3 of r20 P8 (blocker 1): a container born on a search for the kind is no container of it
                // (Edge: Ctrl+T, «youtube» typed into the address bar and entered, the tab born «youtube - Búsqueda» on
                // bing.com/search). The guards of the other place atoms: the query's echo, the title that repeated the
                // typing, and a web search's results page (v3-59 r7), unless a search's results are the proof asked.
                return BornContainer(rest, view)
                    && !QueryEchoNames(rest, view, steps, searchResultsProve, typedBefore)
                    && !TitleEchoedTheTyping(rest, steps)
                    && (searchResultsProve || !ShowsSearchResultsPage(view));
            case "stepdone":
                {
                    string[] parts = rest.Split(':', 2);
                    string operation = parts[0].Trim();
                    string? argument = parts.Length > 1 ? Fold(parts[1]) : null;
                    // «stepDone:input.visible.click:=red»: the clicked control's name holds the name whole, not
                    // inside a longer word (measured on Paint: «red» inside «Rectángulo redondeado» passed a click on
                    // that shape as the colour chosen). A bare «=» is the equals key's own name.
                    bool wholeLabel = operation == "input.visible.click" && argument is { Length: > 1 } && argument[0] == '=';
                    // «stepDone:input.visible.click:==Recortar» (an alias, §4.4.1): the clicked label is exactly that.
                    bool exactLabel = wholeLabel && argument is { Length: > 2 } && argument[1] == '=';
                    argument = exactLabel ? argument![2..].Trim() : wholeLabel ? argument![1..] : argument;
                    // Ronda 24b (banco r23 c6): «stepDone:input.text.type:written», a free text written where text is
                    // written: any text the view shows, except one typed at the caret into the window's search while
                    // another field could take it (the receipt's atCaret, intoSearch, otherField).
                    bool written = operation == "input.text.type" && argument == WrittenMarker;
                    argument = written ? null : argument;
                    // What this sub-goal typed so far into a search, an address bar or a field with no name.
                    var queries = new List<string>();
                    foreach (JsonNode? node in steps)
                    {
                        if (node is JsonObject typing && (bool?)typing["ok"] == true
                            && (string?)typing["operation"] == "input.text.type" && EchoesItsQuery(typing)
                            && Fold((string?)typing["text"]).Trim(QuoteMarks) is { Length: >= MinimumQuery } query)
                        {
                            queries.Add(query);
                        }

                        if (node is not JsonObject step || (bool?)step["ok"] != true
                            || (string?)step["operation"] != operation || OnlyOpened(step))
                        {
                            continue;
                        }

                        // On receipts alone (no look: EvaluateReceipts) a click that repeats the query is undecided
                        // and waits for the look after it (falsos éxitos v3 M2).
                        if (operation == "input.visible.click"
                            && ClickEchoesQuery(step, queries, undecidedEchoes: view["window"] is null && view["controls"] is null))
                        {
                            // A text that repeats what BAXY typed («No hay resultados para «X»») is no control named
                            // X (measured 2026-10-07 on Settings: a click on that message passed «hacer clic en X»
                            // and the mission learned it as the way there).
                            continue;
                        }

                        if (operation == "input.visible.click" && RowStandsForANode(step, view))
                        {
                            // Pasada r18 (v3-23): the row of a content list named like a navigation node is not the
                            // node: «hacer clic en Sistema» closed on the summary row «Sistema» under the collapsed node
                            // «Registros de Windows», and the procedure learned from it replayed that row.
                            continue;
                        }

                        if (operation == "input.text.type" && !TypedTextShows(step, view))
                        {
                            // Keys Windows accepted are not text the field holds (measured on Notepad: «lista: pan»
                            // arrived as «lista:nnnn» and the mission said it was written).
                            continue;
                        }

                        if (operation == "input.key.press" && !PasteLanded(step, view))
                        {
                            // Ronda 24 (pasada r23 t-long-1): a Ctrl+V Windows accepted 84 ms after an application
                            // opened left its tab with «0 caracteres» and passed on the receipt: a paste is done only
                            // when the look after it shows what it put (PasteLanded).
                            continue;
                        }

                        if (written && (bool?)step["atCaret"] == true && (bool?)step["intoSearch"] == true
                            && (bool?)step["otherField"] == true)
                        {
                            // «prueba BAXY C6» sat in Discord's search while «Mensaje @Ron92» stayed empty: no text written.
                            continue;
                        }

                        if (operation == "input.text.type" && OperationFloor.TypedIntoUnnamedPart(step))
                        {
                            // Ronda 20 P1 (v3-11 t2, seq 81-82): the receipt says the text went into a part of a
                            // document (a page's title) the step did not choose: the existing page «Sin título» was
                            // renamed and the term passed. Such a text reaches no sub-goal.
                            continue;
                        }

                        // The argument names the key pressed, the control clicked or what was typed
                        // («stepDone:input.text.type:=» is an expression typed with its equals sign).
                        if (exactLabel)
                        {
                            if (Fold((string?)step["label"]).Trim() == argument || Fold((string?)step["name"]).Trim() == argument)
                            {
                                return true;
                            }

                            continue;
                        }

                        if (wholeLabel)
                        {
                            if (NamesWhole(Fold((string?)step["label"]), argument!) || NamesWhole(Fold((string?)step["name"]), argument!))
                            {
                                return true;
                            }

                            continue;
                        }

                        if (argument is null
                            || Fold((string?)step["key"]) == argument
                            || Fold((string?)step["label"]).Contains(argument, StringComparison.Ordinal)
                            || Fold((string?)step["text"]).Contains(argument, StringComparison.Ordinal))
                        {
                            return true;
                        }
                    }

                    return false;
                }
            case "opened":
                return PlaceOpened(rest, view, steps);
            case "file":
                // A file proves the act only when this sub-goal wrote it: it exists and was last written since the
                // sub-goal began. A file of that name that was already there (an old save, the person's own) never
                // holds, nor does a check with no start to compare against.
                return rest.Length > 0 && Path.IsPathRooted(rest) && File.Exists(rest)
                    && notBefore is { } since
                    && File.GetLastWriteTimeUtc(rest) >= since.UtcDateTime - FileTimeSlack;
            default:
                return false;
        }
    }

    internal static string LookText(JsonObject view)
    {
        static string Part(string text) => text.Replace('\n', ' ').Replace('\r', ' ');
        var text = new StringBuilder();
        text.Append(Part(Fold((string?)view["window"]?["title"]))).Append('\n');
        // Revision 2 of ronda 21: a control listed only for the goal's words («reserved») is no part of what a look shows:
        // the sub-goal's first look carried no words, so it would read as new («seen_at_start», brought, numbers shown).
        foreach (JsonObject control in ComparedControls(view).Where(control => !ClosedMenuEntry(control)))
        {
            string value = Fold((string?)control["value"]);
            text.Append(Part(Fold((string?)control["name"]) + (value.Length > 0 ? "\t" + value : string.Empty))).Append('\n');
        }

        foreach (JsonNode? line in TextLines(view))
        {
            text.Append(Part(Fold((string?)line))).Append('\n');
        }

        return text.ToString();
    }

    internal static JsonArray TextLines(JsonObject view)
    {
        var lines = new JsonArray();
        if (view["text"] is JsonObject zones)
        {
            foreach ((string _, JsonNode? zone) in zones)
            {
                if (zone is not JsonArray zoneLines)
                {
                    continue;
                }

                foreach (JsonNode? line in zoneLines)
                {
                    string folded = Fold((string?)line);
                    if (folded.Length > 0)
                    {
                        lines.Add(folded);
                    }
                }
            }
        }

        return lines;
    }

    private static readonly Regex CountExpression = new(@"^([A-Za-z]+)\s*(<=|>=|==|<|>|=)\s*(\d+)$", RegexOptions.CultureInvariant);

    private static bool CountAtom(string rest, JsonObject view)
    {
        var match = CountExpression.Match(rest);
        if (!match.Success || !int.TryParse(match.Groups[3].Value, NumberStyles.Integer, CultureInfo.InvariantCulture, out int expected))
        {
            return false;
        }

        int count = CountOf(match.Groups[1].Value, view);
        return match.Groups[2].Value switch
        {
            "<=" => count <= expected,
            ">=" => count >= expected,
            "<" => count < expected,
            ">" => count > expected,
            _ => count == expected,
        };
    }

    // The controls of a kind on the look, a repeated one counted as many times as it repeats.
    private static int CountOf(string kind, JsonObject view)
    {
        int count = 0;
        foreach (JsonNode? node in view["controls"] as JsonArray ?? [])
        {
            if (node is JsonObject control && string.Equals((string?)control["kind"], kind, StringComparison.OrdinalIgnoreCase))
            {
                count += 1 + ((int?)control["repeated"] ?? 0);
            }
        }

        return count;
    }

    // The folded needle inside the folded name with no letter or digit glued on either side.
    private static bool NamesWhole(string name, string needle)
    {
        for (int at = name.IndexOf(needle, StringComparison.Ordinal); at >= 0;
             at = name.IndexOf(needle, at + 1, StringComparison.Ordinal))
        {
            int end = at + needle.Length;
            if ((at == 0 || !char.IsLetterOrDigit(name[at - 1])) && (end == name.Length || !char.IsLetterOrDigit(name[end])))
            {
                return true;
            }
        }

        return false;
    }

    private static long? LongOf(JsonNode? node) =>
        node is JsonValue value && value.TryGetValue(out long number) ? number
        : node is JsonValue small && small.TryGetValue(out int narrow) ? narrow
        : node is JsonValue element && element.TryGetValue(out JsonElement json) && json.ValueKind == JsonValueKind.Number
            && json.TryGetInt64(out long parsed) ? parsed
        : null;

    private static IEnumerable<JsonObject> FindControls(JsonObject view, string name)
    {
        string needle = Fold(name);
        if (needle.Length == 0 || view["controls"] is not JsonArray controls)
        {
            yield break;
        }

        foreach (JsonNode? node in controls)
        {
            if (node is JsonObject control && !ClosedMenuEntry(control)
                && Fold((string?)control["name"]).Contains(needle, StringComparison.Ordinal))
            {
                yield return control;
            }
        }
    }

    /// <summary>
    /// Whether the view shows <paramref name="needle"/>: in its title, a control's name or value (never a field's) or
    /// its written text. Ronda 20 P6 (v3-16): a citation of several of the view's lines as the mind's listing joins
    /// them («paisaJe.Jpg | Restablecer | 9», a zone's lines joined by « | ») is shown when each of its pieces is
    /// (<see cref="CitationPieces"/>); one piece the view lacks and it is not.
    /// </summary>
    internal static bool ViewContains(JsonObject view, string needle) =>
        ViewHolds(view, needle)
        || (CitationPieces(needle) is { Count: > 1 } pieces && pieces.All(piece => ViewHolds(view, piece)));

    /// <summary>
    /// Ronda 20 P6: the pieces of a citation split by the « | » the mind's listing joins a zone's lines with, each
    /// trimmed; the citation itself when it holds no such separator.
    /// </summary>
    internal static IReadOnlyList<string> CitationPieces(string? cited) =>
        (cited ?? string.Empty).Split('|', StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries);

    private static bool ViewHolds(JsonObject view, string needle)
    {
        string folded = Fold(needle);
        if (folded.Length == 0)
        {
            return false;
        }

        if (view["window"] is JsonObject window && Fold((string?)window["title"]).Contains(folded, StringComparison.Ordinal))
        {
            return true;
        }

        if (view["controls"] is JsonArray controls)
        {
            foreach (JsonNode? node in controls)
            {
                // What a field holds is what was typed into it (the echo), never where the window went.
                bool field = (string?)node?["kind"] is "Edit" or "ComboBox" or "Document";
                if (node is JsonObject control && !ClosedMenuEntry(control)
                    && (Fold((string?)control["name"]).Contains(folded, StringComparison.Ordinal)
                        || (!field && Fold((string?)control["value"]).Contains(folded, StringComparison.Ordinal))))
                {
                    return true;
                }
            }
        }

        if (view["text"] is JsonObject text)
        {
            var joined = new StringBuilder();
            foreach ((string _, JsonNode? zone) in text)
            {
                if (zone is JsonArray lines)
                {
                    foreach (JsonNode? line in lines)
                    {
                        joined.Append((string?)line).Append(' ');
                    }
                }
            }

            if (Fold(joined.ToString()).Contains(folded, StringComparison.Ordinal))
            {
                return true;
            }
        }

        return false;
    }

    internal static string Fold(string? value)
    {
        if (string.IsNullOrEmpty(value))
        {
            return string.Empty;
        }

        string form = value.Normalize(NormalizationForm.FormD).ToLowerInvariant();
        var builder = new StringBuilder(form.Length);
        foreach (char character in form)
        {
            if (CharUnicodeInfo.GetUnicodeCategory(character) != UnicodeCategory.NonSpacingMark)
            {
                builder.Append(character);
            }
        }

        return string.Join(' ', builder.ToString().Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries));
    }
}
