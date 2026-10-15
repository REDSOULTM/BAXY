using System.Text.Json.Nodes;

namespace Baxy.App;

/// <summary>
/// Ronda 21, destino por contenido (pasada r18: t-file-1, t-file-3, t-menu-4, t-form-4, t-drag-2). A mission whose
/// request names no application looked only at the window in front, the person's own, and the window holding what the
/// request names was never looked at. The mind reads what the request names of the window where it happens (its
/// <c>referent</c>: a menu, a dialog or a panel by its name, a selection, a document with something to save); the
/// desktop's windows (the provider's <c>candidateWindows</c>, top of the Z order first, each with the kinds and names
/// of the first controls of its tree) are weighed against it, by how the windows are made and never by which
/// application they are:
/// <list type="bullet">
/// <item>a name said (<c>referentLabels</c>) is a control of the window so named, or whose name holds it as words;</item>
/// <item>a selection (<c>referentSelection</c>) is in a window whose text pattern holds a non-empty selection.</item>
/// </list>
/// A save of what is shown with no window named («guardá esto») is no referent since the estabilización L: the mind asks
/// which window (semantic.limits.asks_which_window) and the engine never guesses it.
/// A developer's or BAXY's own window (<c>protected</c>) and a window the person's input went to a moment ago are never
/// bound. When the person pointed at the window in front themselves (<c>frontWindow</c>) it is the destination as before
/// and no other window is ever bound (revision 2, B2). One window clearly ahead is the mission's, its document still
/// not one the request names (revision 3, B1); several equal are asked about by their titles, never the first in Z
/// order; the person's own window fitting as well is said as such; none is an honest limit, with nothing opened.
/// </summary>
internal static class ComputerUseDestination
{
    /// <summary>
    /// What the request names of the window where it happens, as the mind read it. Ronda 24 (pasada r23 t-drag-2,
    /// t-form-4, t-file-3): a window is the destination by what the request's structure names (a menu, a panel, a tab:
    /// <see cref="Labels"/>; a dialog already open: <see cref="Dialogs"/>; a selection; a document that can save), never
    /// by a word of content: a quoted name said beside them (<see cref="Items"/>: the slide «Tres») adds to a window
    /// that fits and never makes one fit alone.
    /// </summary>
    internal sealed record Referent(
        IReadOnlyList<string> Labels,
        bool Selection,
        IReadOnlyList<string>? Items = null,
        IReadOnlyList<string>? Dialogs = null)
    {
        internal IReadOnlyList<string> Items { get; init; } = Items ?? [];

        internal IReadOnlyList<string> Dialogs { get; init; } = Dialogs ?? [];
    }

    internal enum Outcome
    {
        /// <summary>One window other than the one in front shows it: the mission is tied to it.</summary>
        Bound,

        /// <summary>
        /// Revision 1 (B1), revision 2 (B2): the person pointed at the window in front («esto», «en esta ventana»:
        /// <c>frontWindow</c>): the mission goes on in it as before, nothing is bound.
        /// </summary>
        Front,

        Ambiguous,

        /// <summary>No window that could be looked at shows it.</summary>
        NotFound,

        /// <summary>
        /// Revision 1 (B3): the window the person's input went to a moment ago shows it at least as well as any other: it
        /// is never acted in unless pointed at, and no other window is taken in its place.
        /// </summary>
        PersonsWindow,
    }

    /// <summary>The weighing's answer: the window bound, or the titles of the windows asked about.</summary>
    internal sealed record Choice(Outcome Outcome, JsonObject? Window, IReadOnlyList<string> Titles);

    /// <summary>The referent the mission's arguments carry; null when they carry none.</summary>
    internal static Referent? ReferentOf(JsonObject? arguments)
    {
        if (arguments is null)
            return null;
        List<string> labels = FoldedNames(arguments["referentLabels"]);
        List<string> dialogs = FoldedNames(arguments["referentDialogs"]);
        List<string> items = FoldedNames(arguments["referentItems"]);
        bool selection = (bool?)arguments["referentSelection"] == true;
        return labels.Count == 0 && dialogs.Count == 0 && !selection
            ? null
            : new Referent(labels, selection, items, dialogs);
    }

    private static List<string> FoldedNames(JsonNode? node) =>
        [.. (node as JsonArray ?? [])
            .Select(item => item is JsonValue value && value.TryGetValue(out string? label) ? ComputerUseSuccessCheck.Fold(label).Trim() : string.Empty)
            .Where(label => label.Length > 0)
            .Distinct(StringComparer.Ordinal)];

    /// <summary>The referent as the mission's state keeps it.</summary>
    internal static JsonObject ToState(Referent referent) => new()
    {
        ["labels"] = new JsonArray([.. referent.Labels.Select(label => (JsonNode?)label)]),
        ["items"] = new JsonArray([.. referent.Items.Select(item => (JsonNode?)item)]),
        ["dialogs"] = new JsonArray([.. referent.Dialogs.Select(dialog => (JsonNode?)dialog)]),
        ["selection"] = referent.Selection,
    };

    /// <summary>The referent the mission's state keeps; null when none.</summary>
    internal static Referent? FromState(JsonObject state) =>
        state["referent"] is JsonObject kept
            ? ReferentOf(new JsonObject
            {
                ["referentLabels"] = kept["labels"]?.DeepClone(),
                ["referentItems"] = kept["items"]?.DeepClone(),
                ["referentDialogs"] = kept["dialogs"]?.DeepClone(),
                ["referentSelection"] = (bool?)kept["selection"] == true,
            })
            : null;

    /// <summary>
    /// The window of <paramref name="candidates"/> the referent is in. Each window that shows every kind of thing the
    /// referent says (a name said, a dialog, a selection) is scored: two for each name or dialog said it shows, one for a
    /// selection. Revision 1 of r21:
    /// <list type="bullet">
    /// <item>(B1, revision 2 B2) when the person pointed at the window in front (<paramref name="frontWindow"/>: «en esta
    /// ventana») it is the destination, whether it shows what the request names or not, and nothing is weighed;</item>
    /// <item>(B3) the window the person's input went to a moment ago is weighed too: when it fits at least as well as the
    /// best other one, nothing is bound (<see cref="Outcome.PersonsWindow"/>), never another window in its place;
    /// without Raw Input (revision 2, B1) it is the window in front while the session's last input
    /// (<paramref name="personInputUnknownAgoMs"/>) is recent;</item>
    /// <item>a window the provider could not read in time (<c>unread</c>) or a developer's or BAXY's own
    /// (<c>protected</c>, never read) scores nothing: the final says «the windows I could look at».</item>
    /// </list>
    /// The top one alone is bound; several equal are asked about by their titles, never the first in Z order; none is
    /// <see cref="Outcome.NotFound"/>.
    /// </summary>
    internal static Choice Choose(
        Referent referent, JsonArray? candidates, bool frontWindow, long personRecentMs, long? personInputUnknownAgoMs = null)
    {
        // Revision 2 (B2): the person pointed at the window in front («esta página»): it is the destination, whether or
        // not it shows what the request names, and no window behind is ever bound in its place (a window behind
        // fitting by its menus is a guess, and its data are not the request's).
        if (frontWindow)
            return new Choice(Outcome.Front, (candidates ?? []).OfType<JsonObject>().FirstOrDefault(Foreground), []);
        var scored = new List<(JsonObject Window, int Score)>();
        int? persons = null;
        foreach (JsonObject window in (candidates ?? []).OfType<JsonObject>())
        {
            if ((bool?)window["protected"] == true || (bool?)window["unread"] == true || LongOf(window["hwnd"]) is not > 0)
                continue;
            if (Score(referent, window) is not int score)
                continue;
            if (PersonWorksIn(window, personRecentMs, personInputUnknownAgoMs))
                persons = Math.Max(persons ?? 0, score);
            else
                scored.Add((window, score));
        }

        if (scored.Count == 0)
            return new Choice(persons is null ? Outcome.NotFound : Outcome.PersonsWindow, null, []);

        int top = scored.Max(item => item.Score);
        if (persons >= top)
            return new Choice(Outcome.PersonsWindow, null, []);
        List<JsonObject> best = [.. scored.Where(item => item.Score == top).Select(item => item.Window)];
        if (best.Count == 1)
            return new Choice(Outcome.Bound, best[0], []);
        return new Choice(Outcome.Ambiguous, null,
            [.. best.Select(window => (string?)window["title"] ?? string.Empty).Where(title => title.Trim().Length > 0)]);
    }

    /// <summary>
    /// The window the person's input went to a moment ago. Revision 2 (B1), without Raw Input: no window of the person
    /// is known (no <c>personInputAgoMs</c>), only how long ago the session's last input came (the listing's
    /// <c>personInputUnknownAgoMs</c>); the window in front is then taken for the person's while that input is recent,
    /// as <see cref="ComputerUseMissionWindow.PersonMayWorkInFront"/> takes it on a look.
    /// </summary>
    internal static bool PersonWorksIn(JsonObject window, long personRecentMs, long? personInputUnknownAgoMs = null) =>
        LongOf(window["personInputAgoMs"]) is long ago
            ? ago <= personRecentMs
            : personInputUnknownAgoMs is long unknown && unknown <= personRecentMs && Foreground(window);

    /// <summary>
    /// The window's score against the referent; null when it lacks a kind of thing the referent says (no name said, no
    /// selection). Revision 1 (B2): a selection is the one the provider read through the window's
    /// text pattern (<c>selection</c>: a non-empty selected range), never guessed from a document or a field being there.
    /// </summary>
    internal static int? Score(Referent referent, JsonObject window)
    {
        List<(string Kind, string Name, bool Content)> controls = Controls(window);
        // Ronda 24: what the structure names (a menu, a panel, a tab, a dialog) is a control of the window's own frame,
        // never the content it shows: a document's name or a link of a page that mentions «girar» names no menu.
        // Revision 2 (B2): nor the tab of a document (a browser's page tab «Cómo girar una imagen»): see DocumentTabs.
        // Revision 3 (B1): nor any control the provider read inside a document (<c>content</c>), whatever its kind: a
        // real page lists its text as Text, Button or ListItem («Abrí el menú Imagen y elegí Girar», «Fuente: agencia»).
        bool documentTabs = DocumentTabs(window);
        List<(string Kind, string Name, bool Content)> frame = [.. controls.Where(control => !control.Content
            && control.Kind is not ("Document" or "Hyperlink")
            && !(documentTabs && control.Kind == "TabItem"))];
        int score = 0;
        bool fits = false;
        if (referent.Labels.Count > 0)
        {
            int shown = referent.Labels.Count(label => frame.Any(control => Names(control.Name, label)));
            if (shown == 0)
                return null;
            score += 2 * shown;
            fits = true;
        }

        // Ronda 24 (pasada r23 t-form-4): a dialog said («desde el cuadro de diálogo de Fuente») is a place the mission
        // opens on its way; it adds only when a window or a control already carries its name («Guardar como» open), and
        // is required only when nothing else of the structure is said: a dialog not open yet is seen nowhere.
        // Revision 4 (B2): the window's title names the dialog only when the window is the dialog itself: no document in
        // it (a page, a file) and a title that is the dialog's own name, not «document - application». The title of a
        // window that shows a document is that document's name, content («Fuentes tipográficas gratis - Navegador»,
        // «fuente.txt - Editor»), and never names a dialog of it.
        string title = DialogItself(window) ? ComputerUseSuccessCheck.Fold((string?)window["title"]).Trim() : string.Empty;
        int dialogs = referent.Dialogs.Count(dialog => (title.Length > 0 && Names(title, dialog))
            || frame.Any(control => Names(control.Name, dialog)));
        if (dialogs > 0)
        {
            score += 2 * dialogs;
            fits = true;
        }
        else if (referent.Dialogs.Count > 0 && referent is { Labels.Count: 0, Selection: false })
        {
            return null;
        }

        if (referent.Selection)
        {
            if ((bool?)window["selection"] != true)
                return null;
            score += 1;
            fits = true;
        }

        // Ronda 24 (pasada r23 t-drag-2): a quoted name said beside the structure (the slide «Tres») is content: it adds
        // to a window that fits and never makes one fit (a player listing a song «Tres» is no presentation).
        score += referent.Items.Count(item => controls.Any(control => Names(control.Name, item)));

        return fits ? score : null;
    }

    /// <summary>A control's folded name names the label: equal to it, or holding its words as a run.</summary>
    internal static bool Names(string foldedName, string foldedLabel)
    {
        if (foldedName.Length == 0 || foldedLabel.Length == 0)
            return false;
        if (string.Equals(foldedName, foldedLabel, StringComparison.Ordinal))
            return true;
        string[] name = Words(foldedName);
        string[] label = Words(foldedLabel);
        if (label.Length == 0 || label.Length > name.Length)
            return false;
        for (int start = 0; start + label.Length <= name.Length; start++)
        {
            if (label.Select((word, offset) => SameWord(name[start + offset], word)).All(same => same))
                return true;
        }

        return false;
    }

    // One word said in the singular or the plural is the same word (the person's «panel de miniaturas» is the window's
    // «Miniatura»; «Imágenes», «Imagen»).
    private static bool SameWord(string shown, string said) =>
        shown == said
        || shown + "s" == said || said + "s" == shown
        || shown + "es" == said || said + "es" == shown;

    /// <summary>
    /// The binding a chosen window gives the mission: tied to it, of its process, so every later look reads it and its
    /// acts are the mission's (no other window is read in its place). Revision 3 of r21 (B1): the window is the
    /// mission's, never a document the request names (<c>named</c>): a menu's, a panel's or a tab's name («Insertar»,
    /// «Archivo») names no document, so what selects, erases, pastes or writes over the content of the document it
    /// shows is refused as over any document the request does not name
    /// (<see cref="ComputerUseMissionWindow.ForeignDocumentAct"/>); the request naming its title still exempts it there.
    /// </summary>
    internal static void Bind(JsonObject state, JsonObject window, int stepCount)
    {
        long hwnd = LongOf(window["hwnd"]) ?? 0;
        state["windows"] = new JsonArray(hwnd);
        state["known"] = new JsonArray();
        state["tiedAtStep"] = stepCount;
        if (LongOf(window["processId"]) is long process and > 0 and <= int.MaxValue)
            state["processId"] = (int)process;
        state["destinationBound"] = new JsonObject
        {
            ["hwnd"] = hwnd,
            ["title"] = (string?)window["title"] ?? string.Empty,
        };
    }

    private static bool Foreground(JsonObject window) => (bool?)window["foreground"] == true;

    /// <summary>
    /// Revision 2 of ronda 24 (B2): the window's tabs are tabs of documents, content and never structure. A window whose
    /// tab strip holds the document it shows names that tab as its title does (the page tab «Cómo girar una imagen» of
    /// «Cómo girar una imagen - Navegador», the file tab «nota» of «nota - Editor»): a tab whose name is the title's part
    /// before its first separator, or begins with it, is the document's; so is a tab of two words or more that begins
    /// that part (a browser adds the count of its other pages after the page's title). Every tab of that strip is then
    /// one more document (a page in another tab). The tabs of a ribbon («Archivo», «Insertar» of «Informe - Procesador de textos») name
    /// no document, so they stay structure, also when one word of theirs begins a document's name («Inicio de obra»).
    /// </summary>
    internal static bool DocumentTabs(JsonObject window)
    {
        string title = ComputerUseSuccessCheck.Fold((string?)window["title"]).Trim();
        if (title.Length == 0)
            return false;
        string document = title;
        foreach (string separator in TitleSeparators)
        {
            int at = document.IndexOf(separator, StringComparison.Ordinal);
            if (at > 0)
                document = document[..at].Trim();
        }

        return Controls(window).Any(control => control.Kind == "TabItem" && control.Name.Length > 0
            && (Begins(control.Name, document) || (Begins(document, control.Name) && Words(control.Name).Length >= 2)));
    }

    /// <summary>
    /// Revision 4 of ronda 24 (B2): the window is a dialog itself, so its title is the dialog's name: no Document among
    /// its controls nor any control read inside one (<c>content</c>), and a title with no separator between a document's
    /// name and an application's («Guardar como», «Fuente», «Print»; never «fuente.txt - Editor» nor a page's title).
    /// </summary>
    internal static bool DialogItself(JsonObject window)
    {
        string title = ComputerUseSuccessCheck.Fold((string?)window["title"]).Trim();
        return title.Length > 0
            && !TitleSeparators.Any(separator => title.Contains(separator, StringComparison.Ordinal))
            && !(window["controls"] as JsonArray ?? []).OfType<JsonObject>()
                .Any(control => (bool?)control["content"] == true || (string?)control["kind"] == "Document");
    }

    // The window title's separators between the document's name and the application's.
    private static readonly string[] TitleSeparators = [" - ", " – ", " — ", " | "];

    // «text» begins with «start» up to a word's end.
    private static bool Begins(string text, string start) =>
        start.Length > 0 && text.StartsWith(start, StringComparison.Ordinal)
        && (text.Length == start.Length || !char.IsLetterOrDigit(text[start.Length]));

    // The window's first controls as the listing read them: each one's kind, folded name and whether the provider read
    // it inside a document (<c>content</c>: the page or file the window shows, never its frame).
    private static List<(string Kind, string Name, bool Content)> Controls(JsonObject window) =>
        [.. (window["controls"] as JsonArray ?? []).OfType<JsonObject>()
            .Select(control => ((string?)control["kind"] ?? string.Empty, ComputerUseSuccessCheck.Fold((string?)control["name"]).Trim(),
                (bool?)control["content"] == true))];

    private static string[] Words(string folded) =>
        folded.Split([' ', '.', ',', ':', ';', '(', ')', '-', '_', '/', '>', '…'], StringSplitOptions.RemoveEmptyEntries);

    internal static long? LongOf(JsonNode? node) =>
        node is JsonValue value && value.TryGetValue(out long number) ? number
        : node is JsonValue other && other.TryGetValue(out int small) ? small
        : null;
}
