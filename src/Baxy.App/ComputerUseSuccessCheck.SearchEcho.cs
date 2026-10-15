using System.Globalization;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace Baxy.App;

// A search's echo: the query a box, a title or a results page only repeats is no arrival, and what a search found
// or did not find.
internal static partial class ComputerUseSuccessCheck
{
    // A field whose name says it looks something up (or holds an address); a field of unknown name counts as one.
    // The place is named by a query BAXY typed, not reached: the last thing typed was the name, into a search or an
    // address box, and either nothing submitted it (no Enter, no click after it), or a search submitted it, its box
    // still holds the query (its results are what is shown) and no click went from them to the place by name (a
    // search whose Enter opened the place leaves no box holding it). While it stands, a window that shows the
    // name (its title, its selected tab, its header) is echoing the query (measured on Explorer: «Imágenes» typed
    // into «Buscar en ETC» titled the window «imagenes - Resultados de la búsqueda en ETC», its selected tab the
    // same, and the mission said it was in Imágenes). An address, a «go to» box or a switcher entered leads to the
    // place it names; a search term that asks for the act itself takes its results (searchResultsProve).
    // Ronda 23 (v3-58): with no typing of the name in these steps, a text an earlier turn typed into a search or an
    // address box on this window's application (typedBefore) is the same echo while the view still shows it as a
    // query: a search box's field holds it, or the page is a web search's results whose query holds it
    // (SearchResultsEchoThePlace: a site's own results page reached by typing its address in an earlier turn still is
    // that site). A turn closes what it typed, so it counts as submitted; a click on the place by its whole name in
    // these steps still ends the echo.
    internal static bool QueryEchoNames(
        string place, JsonObject view, JsonArray steps, bool searchResultsProve, IReadOnlyList<TypedEarlier>? typedBefore = null)
    {
        string target = Fold(place);
        if (target.Length == 0)
        {
            return false;
        }

        bool submitted = false;
        // A click on a match that only holds the name inside a longer one (falsos éxitos v3 M3, v3-58: «configuracion»
        // typed into a help search and «Herramienta de configuración de webcam – Link» pressed; the tab it opened passed
        // control:configuracion:current): the window went to one of the matches, never to the place.
        bool wentToAMatch = false;
        // Ronda 24 (t-scroll-3): the latest verified click on a match (its label holds the name), by its step number.
        string? matchClick = null;
        for (int index = steps.Count - 1; index >= 0; index--)
        {
            if (steps[index] is not JsonObject step || (bool?)step["ok"] != true)
            {
                continue;
            }

            switch ((string?)step["operation"])
            {
                case "input.visible.click":
                    // Only a click on the place itself, by its name (or the act of opening it), went there: an item
                    // that merely holds the name («Imágenes viejas» among the results) is one of the matches. A click
                    // that only selected an item of the results (its receipt says selected, or it pressed a content
                    // item) left the results in front: measured on Explorer, «Imágenes» selected in the list while
                    // the window stayed «imagenes - Resultados de la búsqueda en Trabajo».
                    // Ronda 24 (v3-44): nor did it while the window still bears the very title the typing gave it and a
                    // field still holds the query (TitleStillTheTypings).
                    string clicked = WithoutOpening(Fold((string?)step["label"] ?? (string?)step["name"]));
                    if (clicked == target && !OnlySelected(step) && !OnlyOpened(step) && !TitleStillTheTypings(target, view, steps, index))
                    {
                        return false;
                    }

                    wentToAMatch |= clicked != target && clicked.Contains(target, StringComparison.Ordinal);
                    if (clicked.Contains(target, StringComparison.Ordinal))
                    {
                        matchClick ??= ((int?)step["step"] ?? index + 1).ToString(CultureInfo.InvariantCulture);
                    }

                    submitted = true;
                    break;
                case "input.key.press" when Fold((string?)step["key"]) == "enter":
                    submitted = true;
                    break;
                case "input.text.type":
                    if (!EchoesItsQuery(step) || !Fold((string?)step["text"]).Contains(target, StringComparison.Ordinal))
                    {
                        return false;
                    }

                    // A match pressed keeps the echo only while the window does not show the place by its whole name
                    // (Settings: «sonido» typed, «Configuración de sonido» pressed, its page headed «Sonido»).
                    // Ronda 24 (t-scroll-3): a box that keeps the query after a match was pressed (Settings does not
                    // empty its search) echoes nothing once the page is headed by the whole name and the window went
                    // elsewhere (most of its controls are new since that click): «fuentes» typed, its match pressed,
                    // the page «Fuentes» in front.
                    // Encargo IMP3: nor does it once the match pressed put the keyboard into the place's own box.
                    bool focusedThere = FocusedIntoThePlace(view, target, steps);
                    return !submitted || (wentToAMatch && !ShowsThePlaceWhole(view, target, (string?)step["text"]) && !focusedThere)
                        || (!searchResultsProve && IsSearchBox((string?)step["into"]) && AFieldHolds(view, (string?)step["text"])
                            && !(matchClick is not null && ((HeadedByTheName(view, target) && NavigatedSince(view, matchClick)) || focusedThere)))
                        || (!searchResultsProve && ShowsSearchResultsPage(view));
            }
        }

        string? process = (string?)view["window"]?["process"];
        // Encargo IMP4 (imp3 imp-wa-leer: the search kept «musica» from an earlier turn, «Música 29/9/2026» pressed opened
        // the group and the earlier typing still read as its echo, so the mission pressed «Juanito … musica» next): a match
        // pressed that put the keyboard into the place's own box arrived, whoever typed the query.
        if (submitted && FocusedIntoThePlace(view, target, steps))
        {
            return false;
        }

        return !searchResultsProve && typedBefore is not null && typedBefore.Any(earlier =>
            earlier.Into is { Length: > 0 } into && (SearchBox.IsMatch(Fold(into)) || AddressBox.IsMatch(Fold(into)))
            && Fold(earlier.Text).Contains(target, StringComparison.Ordinal)
            && (earlier.Process is not { Length: > 0 } typedOn || string.Equals(typedOn, process, StringComparison.OrdinalIgnoreCase))
            && ((IsSearchBox(into) && AFieldHolds(view, earlier.Text)) || SearchResultsEchoThePlace(place, view)));
    }

    /// <summary>
    /// Ronda 23 (v3-58): the page in front is a web search's results (<see cref="ShowsSearchResultsPage"/>) and a field
    /// of it holds the place as the query (a search box, or the address's query once its escapes are read): the title
    /// or the tab that names the place repeats what was searched. Measured on Edge: «configuración - Búsqueda» selected
    /// over bing.com/search?q=configuración passed control:configuracion:current. Revisión 3 r23: it is read only for
    /// a query BAXY typed in an earlier turn (<see cref="QueryEchoNames"/>, typedBefore); the person's own search tab
    /// («gatos - Buscar con Google») is a tab BAXY can go to and read.
    /// Revisión r23: only the query counts, never the site's own name in the address's host or path (a site's results
    /// page, on its own address, still is that site: title:youtube over youtube.com/results?search_query=gatos).
    /// </summary>
    internal static bool SearchResultsEchoThePlace(string place, JsonObject view)
    {
        string target = Fold(place).Trim(QuoteMarks);
        return target.Length > 0 && ShowsSearchResultsPage(view)
            && (view["controls"] as JsonArray ?? []).OfType<JsonObject>()
                .Append(view["window"]?["focused"] as JsonObject ?? new JsonObject())
                .Any(control => (string?)control["kind"] is "Edit" or "ComboBox" or "Document"
                    && Fold(QueryOf((string?)control["value"])).Contains(target, StringComparison.Ordinal));
    }

    // The query a field holds: in a web search's address (data «evidence.searchAddress»), the values after '?' (or
    // what follows the /search segment) with their escapes read; another address holds no query; any other field
    // holds its value as typed.
    private static string QueryOf(string? value)
    {
        string text = (value ?? string.Empty).Trim();
        bool address = text.Contains("://", StringComparison.Ordinal) || ComputerUseMission.WebAddress.IsMatch(text);
        if (!address)
        {
            return text;
        }

        var searchAddress = new Regex((string)OperationFloor.EvidenceRules["searchAddress"]!, RegexOptions.CultureInvariant);
        if (!searchAddress.IsMatch(Fold(text)))
        {
            return string.Empty;
        }

        int fragment = text.IndexOf('#', StringComparison.Ordinal);
        string located = fragment >= 0 ? text[..fragment] : text;
        int question = located.IndexOf('?', StringComparison.Ordinal);
        string query;
        if (question >= 0)
        {
            query = string.Join(' ', located[(question + 1)..].Split('&', StringSplitOptions.RemoveEmptyEntries)
                .Select(pair => pair.Contains('=', StringComparison.Ordinal) ? pair[(pair.IndexOf('=', StringComparison.Ordinal) + 1)..] : string.Empty));
        }
        else
        {
            Match segment = Regex.Match(located, @"/search(?:/|\b)", RegexOptions.CultureInvariant | RegexOptions.IgnoreCase);
            query = segment.Success ? located[(segment.Index + segment.Length)..].Replace('/', ' ') : string.Empty;
        }

        try
        {
            return Uri.UnescapeDataString(query.Replace('+', ' '));
        }
        catch (UriFormatException)
        {
            return query;
        }
    }

    // The place shown by its whole name: the window's title or one of its parts between dashes or bars, or a control
    // other than a field named exactly so. A tab or a title that only holds it inside a longer name («Herramienta de
    // configuración de webcam - Microsoft Edge») is one of the matches.
    // v3 r5a M2 (v3-44): a part of the title that is exactly the text typed is the window repeating the query while a
    // field still holds it or a line says nothing was found («devices and printers - Panel de control» over «Ningún
    // elemento coincide con la búsqueda»): it shows the query, not the place.
    // Encargo VZ (imp3d imp-dc-voz: «cotele» typed into a search, the channel joined, the window titled «Cotele!!!😎 |
    // Choche - Discord»): a part of the title is the name whole by its letters and digits, whatever marks adorn it.
    private static bool ShowsThePlaceWhole(JsonObject view, string target, string? typed)
    {
        string title = Fold((string?)view["window"]?["title"]);
        bool echoed = Fold(typed).Trim(QuoteMarks) == target && (AFieldHolds(view, typed) || SaysNothingFound(view));
        string named = Squeezed(target);
        if (!echoed && Regex.Split(title, @"\s+[-–—|]\s+", RegexOptions.CultureInvariant)
                .Any(part => part.Trim() == target || (named.Length >= 3 && Squeezed(part) == named)))
        {
            return true;
        }

        return (view["controls"] as JsonArray ?? []).OfType<JsonObject>().Any(control =>
            (string?)control["kind"] is not ("Edit" or "ComboBox" or "Document")
            && Fold((string?)control["name"]).Trim() == target);
    }

    // Ronda 24 (t-scroll-3): the page is headed by the whole name: a written heading or a button called exactly so at
    // the window's top (T, TL). Revisión 1 r24: never a part of the title, which a search retitles with the query
    // typed: Explorer's suggestion «imagenes» pressed leaves «imagenes - Resultados de la búsqueda en ETC», a results
    // page whose title only repeats what BAXY typed.
    private static bool HeadedByTheName(JsonObject view, string target) =>
        (view["controls"] as JsonArray ?? []).OfType<JsonObject>().Any(control =>
            (string?)control["kind"] is "Text" or "Button" && (string?)control["zone"] is "T" or "TL"
            && Fold((string?)control["name"]).Trim() == target);

    // Ronda 24: the window shows something else than right before the click of step <paramref name="key"/>: at least 40 %
    // of its controls are new (the measure of ALastClickOpened). Unknown without the look before the click: false.
    private static bool NavigatedSince(JsonObject view, string key)
    {
        if (view["controlsBeforeClick"]?[key] is not JsonArray earlier)
        {
            return false;
        }

        var seenBefore = new HashSet<string>(earlier.Select(node => (string?)node ?? string.Empty), StringComparer.Ordinal);
        JsonArray now = ControlNames(view);
        int fresh = now.Count(node => !seenBefore.Contains((string?)node ?? string.Empty));
        return now.Count > 0 && fresh * 10 >= now.Count * 4;
    }

    // Ronda 24 (v3-44): the typing of the name before the step at <paramref name="before"/> retitled the window by it, the
    // window still bears that very title and a field still holds the query: a click on the place by its name changed
    // nothing the echo shows.
    private static bool TitleStillTheTypings(string target, JsonObject view, JsonArray steps, int before)
    {
        string now = Fold((string?)view["window"]?["title"]).Trim();
        for (int index = before - 1; index >= 0; index--)
        {
            if (steps[index] is not JsonObject step || (string?)step["operation"] != "input.text.type" || (bool?)step["ok"] != true)
            {
                continue;
            }

            string typedTitle = Fold((string?)step["windowTitle"]).Trim();
            return EchoesItsQuery(step) && Fold((string?)step["text"]).Contains(target, StringComparison.Ordinal)
                && typedTitle.Contains(target, StringComparison.Ordinal) && now == typedTitle
                && AFieldHolds(view, (string?)step["text"]);
        }

        return false;
    }

    // v3-59 r7: the page in front is a web search's results (an address of the page, as the address bar or the page's
    // own document holds it, matches data «evidence.searchAddress»). «wikipedia» typed into Edge's address bar opened
    // «wikipedia español - Búsqueda» on bing.com/search, whose title passed «ir a wikipedia»: the place typed was
    // searched for, not reached, whatever box took it; a result that names it still has to be pressed (a click on the
    // place by its name ends the echo before this is asked).
    internal static bool ShowsSearchResultsPage(JsonObject view)
    {
        var searchAddress = new Regex((string)OperationFloor.EvidenceRules["searchAddress"]!, RegexOptions.CultureInvariant);
        return (view["controls"] as JsonArray ?? []).OfType<JsonObject>()
            .Append(view["window"]?["focused"] as JsonObject ?? new JsonObject())
            .Any(control => (string?)control["kind"] is "Edit" or "Document" or "ComboBox"
                && searchAddress.IsMatch(Fold((string?)control["value"]).Trim()));
    }

    // A line of the window, or a control's name, saying a search found nothing (data «evidence.noResults»).
    private static bool SaysNothingFound(JsonObject view)
    {
        var nothingFound = new Regex((string)OperationFloor.EvidenceRules["noResults"]!, RegexOptions.CultureInvariant);
        return TextLines(view).Any(line => nothingFound.IsMatch(Fold((string?)line)))
            || (view["controls"] as JsonArray ?? []).OfType<JsonObject>().Any(control => nothingFound.IsMatch(Fold((string?)control["name"])));
    }

    // A click whose receipt says it only selected its control, or that pressed an item of a list, tree or grid (a
    // content item: selecting is what a single click does to it), did not go anywhere. Had it opened the place, the
    // search box no longer holds the query and the echo ends there anyway.
    private static bool OnlySelected(JsonObject step) =>
        (bool?)step["selected"] == true
        || (string?)step["kind"] is "ListItem" or "DataItem" or "TreeItem";

    /// <summary>
    /// The evidence the model cites for «done» is only the echo of what this sub-goal typed: the citation is the typed
    /// text itself, or holds it while the query still echoes (<see cref="QueryEchoNames"/>: measured on Explorer, «imagenes
    /// - Resultados de la búsqueda en ETC» cited after «imagenes» was searched and nothing went from the results).
    /// </summary>
    internal static bool CitationEchoesQuery(string? cited, JsonObject view, JsonArray subgoalSteps, bool searchResultsProve = false)
    {
        string citation = Fold(cited).Trim(' ', '«', '»', '"', '\'');
        if (citation.Length == 0)
        {
            return false;
        }

        foreach (JsonObject step in subgoalSteps.OfType<JsonObject>())
        {
            if ((string?)step["operation"] != "input.text.type" || Fold((string?)step["text"]) is not { Length: > 0 } typed)
            {
                continue;
            }

            if (citation.Equals(typed, StringComparison.Ordinal)
                || (citation.Contains(typed, StringComparison.Ordinal) && QueryEchoNames(typed, view, subgoalSteps, searchResultsProve)))
            {
                return true;
            }
        }

        return false;
    }

    internal static bool SearchResultsProve(string? check) =>
        !string.IsNullOrWhiteSpace(check)
        && check.Split('|', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Any(term =>
            {
                string[] atoms = term.Split('&', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
                return atoms.Any(atom => AtomKind(atom) == "stepdone") && atoms.Any(atom => AtomKind(atom) is "title" or "text");
            });

    /// <summary>
    /// The text a search's check reads is what the sub-goal typed into that search, and it shows in one place only: the
    /// box repeating the query (a field's value never counts; a box drawn without a tree is one written line). A result
    /// shows it somewhere else too (a list line, a control, the title); measured on Steam's library, a box drawn without
    /// a tree holds «Cuphead» whether the library has it or not.
    /// </summary>
    internal static bool OnlyTheQueryShows(string needle, JsonObject view, JsonArray steps)
    {
        string folded = Fold(needle).Trim(QuoteMarks);
        if (folded.Length == 0 || !steps.OfType<JsonObject>().Any(step => (bool?)step["ok"] == true
            && (string?)step["operation"] == "input.text.type" && EchoesItsQuery(step)
            && Fold((string?)step["text"]).Trim(QuoteMarks).Contains(folded, StringComparison.Ordinal)))
        {
            return false;
        }

        // A line saying the search found nothing («No hay resultados para «X»», data «evidence.noResults») repeats the
        // query too, and is no result (falsos éxitos v3 M3).
        var nothingFound = new Regex((string)OperationFloor.EvidenceRules["noResults"]!, RegexOptions.CultureInvariant);
        bool Shows(string? text)
        {
            string line = Fold(text);
            return line.Contains(folded, StringComparison.Ordinal) && !nothingFound.IsMatch(line);
        }

        // Pasada v3 r9 (v3-42): a window that says its search found nothing shows no result, whatever repeats the query
        // («chrome - Programas» over «Ningún elemento coincide con el criterio de búsqueda.» and a help link quoting
        // «chrome»); and a title that repeated the query as it was typed is the box's echo, not a place it shows.
        if (SaysNothingFound(view))
        {
            return true;
        }

        // Ronda 24b (v1): only what was born after the search started is a place of its results (SearchStart).
        SearchStart? started = SearchStart.Of(folded, view, steps);
        int places = view["window"] is JsonObject window && Fold((string?)window["title"]).Contains(folded, StringComparison.Ordinal)
            && !TitleEchoedTheTyping(needle, steps, view) && started?.OldTitle(Fold((string?)window["title"])) != true ? 1 : 0;
        // Revision 3 of ronda 21: a control listed only for the goal's words («reserved») is no place of the result.
        places += ComparedControls(view)
            .Count(control => (string?)control["kind"] is not ("Edit" or "ComboBox" or "Document")
                && (Shows((string?)control["name"]) || Shows((string?)control["value"]))
                && started?.OldPlace(control) != true);
        // Ronda 20 P8 (v3-29): the OCR reads one box twice, a line under the other («copyright symboll | copyright
        // symbol»): lines of a zone that are only the query (EchoLine) and follow one another are one place.
        if (view["text"] is JsonObject zones)
        {
            foreach ((string zoneName, JsonNode? zone) in zones)
            {
                bool lastEchoed = false;
                foreach (JsonNode? line in zone as JsonArray ?? [])
                {
                    string text = Fold((string?)line);
                    if (text.Length == 0)
                    {
                        continue;
                    }

                    bool echoed = EchoLine(text, folded);
                    if (Shows(text) && !(echoed && lastEchoed) && started?.OldLine(zoneName, text) != true)
                    {
                        places++;
                    }

                    lastEchoed = echoed;
                }
            }
        }

        return places < 2;
    }

    /// <summary>
    /// Ronda 20 P8 (t-scroll-2): a search's result may say the query's words in another order («omega mayúscula» found
    /// as «Letra griega mayúscula Omega»). True when a control that is no field, still shown, appeared after a key
    /// that submitted a verified typing of the query (the key's receipt «appeared») and holds every content word of
    /// the query as a whole word (data «evidence.queryFunctionWords» are not content). A query of one content word
    /// needs no other order; a name that is only the query, or a line saying nothing was found, is no result.
    /// Review 1 of r20 P8 (finding 2): neither is a window that says its search found nothing (the guard the reading in
    /// order applies, <see cref="SaysNothingFound"/>), nor the window's own title shown as a control (a Window or a
    /// TitleBar, or a control named as the window is or was when the query was typed: Explorer's «informe mensual -
    /// Resultados de la búsqueda en Documentos» over «Ningún elemento coincide…»).
    /// </summary>
    internal static bool ResultInAnyOrder(string needle, JsonObject view, JsonArray steps)
    {
        string folded = Fold(needle).Trim(QuoteMarks);
        string[] words = [.. WordsOf(folded).Where(word => word.Length >= 2 && !QueryFunctionWords.Value.Contains(word)).Distinct()];
        if (words.Length < 2 || SaysNothingFound(view))
        {
            return false;
        }

        var titles = new HashSet<string>(steps.OfType<JsonObject>().Select(step => Fold((string?)step["windowTitle"]))
            .Append(Fold((string?)view["window"]?["title"])).Where(title => title.Length > 0), StringComparer.Ordinal);
        var nothingFound = new Regex((string)OperationFloor.EvidenceRules["noResults"]!, RegexOptions.CultureInvariant);
        // Ronda 24b (v1): a control the view already showed when the search started is none of its results.
        SearchStart? started = SearchStart.Of(folded, view, steps);
        List<JsonObject> shown = [.. (view["controls"] as JsonArray ?? []).OfType<JsonObject>()
            .Where(control => (string?)control["kind"] is not ("Edit" or "ComboBox" or "Document" or "Window" or "TitleBar")
                && !titles.Contains(Fold((string?)control["name"])) && started?.OldPlace(control) != true)];
        bool typed = false;
        foreach (JsonObject step in steps.OfType<JsonObject>().Where(step => (bool?)step["ok"] == true))
        {
            string? operation = (string?)step["operation"];
            if (operation == "input.text.type" && Fold((string?)step["text"]).Trim(QuoteMarks).Contains(folded, StringComparison.Ordinal))
            {
                typed = true;
                continue;
            }

            if (!typed || operation != "input.key.press" || step["appeared"] is not JsonArray appeared)
            {
                continue;
            }

            foreach (string name in appeared.Select(node => Fold((string?)node)).Where(name => name.Length > 0))
            {
                var nameWords = new HashSet<string>(WordsOf(name), StringComparer.Ordinal);
                if (!nothingFound.IsMatch(name) && !EchoLine(name, folded) && words.All(nameWords.Contains)
                    && shown.Any(control => Fold((string?)control["name"]) == name))
                {
                    return true;
                }
            }
        }

        return false;
    }

    // The runs of letters and digits of a folded text.
    private static string[] WordsOf(string folded) =>
        new string([.. folded.Select(character => char.IsLetterOrDigit(character) ? character : ' ')])
            .Split(' ', StringSplitOptions.RemoveEmptyEntries);

    private static readonly Lazy<HashSet<string>> QueryFunctionWords = new(() => new HashSet<string>(
        (OperationFloor.EvidenceRules["queryFunctionWords"] as JsonArray ?? []).Select(word => (string?)word ?? string.Empty),
        StringComparer.Ordinal));

    /// <summary>
    /// A folded line that says only the query: the query with at most two characters of noise about it (an OCR's
    /// stray letter, a magnifier read as «Q»), no other word.
    /// </summary>
    internal static bool EchoLine(string line, string foldedQuery)
    {
        int at = foldedQuery.Length == 0 ? -1 : line.IndexOf(foldedQuery, StringComparison.Ordinal);
        if (at < 0)
        {
            return false;
        }

        string noise = line[..at] + line[(at + foldedQuery.Length)..];
        return noise.Count(character => !char.IsWhiteSpace(character)) <= 2;
    }

    /// <summary>
    /// Revision 1 of r24b (finding 2): after a search the sub-goal started (its verified typing of a query, with the
    /// view it was decided on), the view shows the query only where it already showed it then (a banner, a recent
    /// search, a list as it was) and no filter narrowed it: the step after which this is seen (a key, a text, a click)
    /// carries «searchNothingNew», and the model reads that nothing it sees was brought by the search. Removed when the
    /// search does bring something, so a later look is never told an old state.
    /// </summary>
    internal static void MarkSearchNothingNew(JsonObject lastStep, JsonObject view, JsonArray subgoalSteps)
    {
        if ((bool?)lastStep["ok"] != true
            || (string?)lastStep["operation"] is not ("input.key.press" or "input.text.type" or "input.visible.click"))
        {
            return;
        }

        JsonObject? typing = subgoalSteps.OfType<JsonObject>().LastOrDefault(step => (bool?)step["ok"] == true
            && (string?)step["operation"] == "input.text.type" && EchoesItsQuery(step));
        string query = Fold((string?)typing?["text"]).Trim(QuoteMarks);
        bool nothingNew = false;
        if (query.Length > 0 && SearchStart.Of(query, view, subgoalSteps) is { Filtered: false })
        {
            // Without the start, the same view shows the query: what bears it was there before the search.
            JsonObject unstarted = view.DeepClone().AsObject();
            unstarted.Remove("viewBeforeTyping");
            nothingNew = OnlyTheQueryShows(query, view, subgoalSteps) && !OnlyTheQueryShows(query, unstarted, subgoalSteps);
        }

        if (nothingNew)
        {
            lastStep["searchNothingNew"] = true;
        }
        else
        {
            lastStep.Remove("searchNothingNew");
        }
    }

    /// <summary>
    /// Ronda 24b (v1): a listed control as one place of the view: its UIA runtime id (the worker's «id») with its name,
    /// so a container the window reused for other content is another place; without an id, its kind, name and rect.
    /// </summary>
    internal static string PlaceKey(JsonObject control)
    {
        string name = Fold((string?)control["name"]).Trim();
        if ((string?)control["id"] is { Length: > 0 } id)
        {
            return "id:" + id + "|" + name;
        }

        JsonNode? rect = control["rect"];
        return string.Create(CultureInfo.InvariantCulture,
            $"at:{(string?)control["kind"]}|{name}|{(int?)rect?["x"]},{(int?)rect?["y"]},{(int?)rect?["w"]},{(int?)rect?["h"]}");
    }

    /// <summary>
    /// Revision 1 of r24b (finding 4): where a listed control sits, whatever it says: its UIA runtime id; without one,
    /// its kind and rect.
    /// </summary>
    internal static string PlaceSeat(JsonObject control)
    {
        if ((string?)control["id"] is { Length: > 0 } id)
        {
            return "id:" + id;
        }

        JsonNode? rect = control["rect"];
        return string.Create(CultureInfo.InvariantCulture,
            $"at:{(string?)control["kind"]}|{(int?)rect?["x"]},{(int?)rect?["y"]},{(int?)rect?["w"]},{(int?)rect?["h"]}");
    }

    // What a listed control says: its name and its value, folded.
    private static string PlaceSays(JsonObject control) =>
        Fold((string?)control["name"]) + "\n" + Fold((string?)control["value"]);

    /// <summary>
    /// Pasada r15b (v3-42): a needle some verified typing of the steps carries is a search's results only while the
    /// window's search field (an Edit or a ComboBox named as a search, or the one the typing went into) still holds that
    /// typing. True when no typing carries it, or when the window shows no such field in its tree (a box drawn without
    /// one, measured on Steam and on Edge's settings: the results' own rule judges it alone).
    /// </summary>
    internal static bool TypedQueryHeld(string needle, JsonObject view, JsonArray steps)
    {
        string folded = Fold(needle).Trim(QuoteMarks);
        List<JsonObject> typed = steps.OfType<JsonObject>()
            .Where(step => (bool?)step["ok"] == true && (string?)step["operation"] == "input.text.type"
                && Fold((string?)step["text"]).Contains(folded, StringComparison.Ordinal))
            .ToList();
        if (folded.Length == 0 || typed.Count == 0)
        {
            return true;
        }

        var into = new HashSet<string>(typed.Select(step => Fold((string?)step["into"])).Where(name => name.Length > 0), StringComparer.Ordinal);
        // Ronda 20 P8 (v3-29): a search box drawn as a Document (the character map's «Buscar:») is such a field too,
        // when it says what it holds: one that exposes no value (or an empty one) says nothing either way.
        List<JsonObject> fields = (view["controls"] as JsonArray ?? []).OfType<JsonObject>()
            .Append(view["window"]?["focused"] as JsonObject ?? new JsonObject())
            .Where(control => ((string?)control["kind"] is "Edit" or "ComboBox"
                    || ((string?)control["kind"] == "Document" && Fold((string?)control["value"]).Trim().Length > 0))
                && (IsSearchBox((string?)control["name"]) || into.Contains(Fold((string?)control["name"]))))
            .ToList();
        return fields.Count == 0 || fields.Any(field => typed.Any(step =>
            Fold((string?)field["value"]).Contains(Fold((string?)step["text"]).Trim(QuoteMarks), StringComparison.Ordinal)));
    }

    private static bool AFieldHolds(JsonObject view, string? typed)
    {
        string query = Fold(typed);
        return query.Length > 0 && (view["controls"] as JsonArray ?? []).OfType<JsonObject>()
            .Append(view["window"]?["focused"] as JsonObject ?? new JsonObject())
            .Any(control => (string?)control["kind"] is "Edit" or "ComboBox"
                && Fold((string?)control["value"]).Contains(query, StringComparison.Ordinal));
    }

    private static readonly System.Text.RegularExpressions.Regex SearchBox = new(
        @"\b(?:busc\w*|busqueda|search\w*|find|filtr\w*|filter\w*)\b",
        System.Text.RegularExpressions.RegexOptions.CultureInvariant);

    private static readonly System.Text.RegularExpressions.Regex AddressBox = new(
        @"\b(?:a donde quieres ir|ir a|go to|jump to|quick switcher|direcc\w*|address|url)\b",
        System.Text.RegularExpressions.RegexOptions.CultureInvariant);

    // A box that only searches: its results are a list of matches, never the place itself. One that also takes an
    // address (a browser's bar «Buscar o escribir dirección») leads where it is sent.
    private static bool IsSearchBox(string? into)
    {
        string named = Fold(into);
        return named.Length > 0 && SearchBox.IsMatch(named) && !AddressBox.IsMatch(named);
    }

    /// <summary>
    /// The place <paramref name="asked"/> was searched by name in the window's own search box during this sub-goal and
    /// the screen at the end lists no item a person clicks whose name holds it (a description that mentions it, the
    /// box's own echo, are words only). Live n5: «Wi-Fi» on a PC without Wi-Fi.
    /// </summary>
    internal static bool SearchedAndNotFound(string asked, JsonArray subgoalSteps, JsonObject view)
    {
        string place = Fold(asked);
        if (place.Length == 0)
        {
            return false;
        }

        bool searched = subgoalSteps.OfType<JsonObject>().Any(step =>
            (string?)step["operation"] == "input.text.type" && (bool?)step["ok"] == true
            && IsSearchBox((string?)step["into"]) && Fold((string?)step["text"]) == place);
        // Revision 3 of ronda 21: a control listed only for the goal's words («reserved») is no item the search listed.
        return searched && !ComparedControls(view).Any(control =>
            ((string?)control["kind"] is not { } kind || !WordsOnlyKinds.Contains(kind))
            && Fold((string?)control["name"]).Contains(place, StringComparison.Ordinal));
    }

    /// <summary>
    /// Pasada v3 r9 (v3-42): the window's title named what this sub-goal typed into a search or an address box already
    /// right after the typing, before anything submitted it (the receipt of the typing step rereads the window's title:
    /// «chrome» typed into the Control Panel's search box titled the window «chrome - Programas» at once, and Enter
    /// changed nothing). That title is the box repeating the query, never the arrival nor the search's results: a
    /// browser's results page takes the query into its title only once it loads, after the submit.
    /// Pasada r18 (v3-42, sub-goal 1): with the look in hand (<paramref name="view"/>), the echo stands only while the
    /// window still bears that very title, and no verified click after the typing went to the place by its whole name
    /// and changed the surface (the escape <see cref="QueryEchoNames"/> gives): a link pressed that opened the page
    /// retitles the window by the place, and that title is the arrival, not the box's echo.
    /// Ronda 24 (v3-44): such a click ends the echo only when the title or the box shows it: under the very title the
    /// typing gave, with a field still holding the query, the click by name changed nothing the echo shows.
    /// </summary>
    internal static bool TitleEchoedTheTyping(string place, JsonArray steps, JsonObject? view = null)
    {
        string target = Fold(place).Trim(QuoteMarks);
        if (target.Length == 0)
        {
            return false;
        }

        string? now = view is null ? null : Fold((string?)view["window"]?["title"]).Trim();
        for (int index = 0; index < steps.Count; index++)
        {
            if (steps[index] is not JsonObject step
                || (string?)step["operation"] != "input.text.type" || (bool?)step["ok"] != true || !EchoesItsQuery(step)
                || !Fold((string?)step["text"]).Contains(target, StringComparison.Ordinal)
                || !Fold((string?)step["windowTitle"]).Contains(target, StringComparison.Ordinal))
            {
                continue;
            }

            if (now is null
                || (now == Fold((string?)step["windowTitle"]).Trim()
                    && (!WentByNameAfter(target, steps, index) || AFieldHolds(view!, (string?)step["text"]))))
            {
                return true;
            }
        }

        return false;
    }

    // A verified click after the step at <paramref name="after"/> on the place itself, by its whole name, that changed the
    // surface (its receipt, or the look after it showed new controls): a click that only selected an entry or opened a
    // menu went nowhere (QueryEchoNames reads it so).
    private static bool WentByNameAfter(string target, JsonArray steps, int after) =>
        steps.Skip(after + 1).OfType<JsonObject>().Any(step => (bool?)step["ok"] == true
            && (string?)step["operation"] == "input.visible.click"
            && WithoutOpening(Fold((string?)step["label"] ?? (string?)step["name"])).Trim() == target
            && !OnlySelected(step) && !OnlyOpened(step)
            && ((bool?)step["surfaceChanged"] == true || (bool?)step["broughtNew"] == true));

    private static bool EchoesItsQuery(JsonObject typedStep) =>
        (string?)typedStep["into"] is not { Length: > 0 } into || SearchBox.IsMatch(Fold(into)) || AddressBox.IsMatch(Fold(into));

    // The marks that delimit a query typed between quotes.
    private static readonly char[] QuoteMarks = ['"', '\'', '«', '»', '“', '”', '‘', '’', ' '];

    // The quotes a citation or a name may come wrapped in, opener to closer.
    private static readonly Dictionary<char, char> QuotePairs = new()
    {
        ['«'] = '»',
        ['"'] = '"',
        ['\''] = '\'',
        ['“'] = '”',
        ['‘'] = '’',
    };

    /// <summary>
    /// Ronda 24 (pasada r23, v3-53): the folded text without the quotes that wrap it, a balanced pair or a lone mark
    /// with no partner inside, never a mark that is part of the name: «Silenciar 'Audio del escritorio'» keeps its
    /// closing quote, so the citation and the control's name meet. Twin of the mind's cu_view._bare.
    /// </summary>
    internal static string Bare(string? text)
    {
        string bare = Fold(text).Trim();
        while (bare.Length > 0)
        {
            char head = bare[0];
            char tail = bare[^1];
            if (bare.Length >= 2 && QuotePairs.TryGetValue(head, out char closer) && closer == tail)
            {
                bare = bare[1..^1].Trim();
            }
            else if (QuotePairs.TryGetValue(head, out char partner) && !bare[1..].Contains(partner, StringComparison.Ordinal))
            {
                bare = bare[1..].Trim();
            }
            else if (QuotePairs.Where(pair => pair.Value == tail).Select(pair => (char?)pair.Key).FirstOrDefault() is char opening
                && !bare[..^1].Contains(opening, StringComparison.Ordinal))
            {
                bare = bare[..^1].Trim();
            }
            else
            {
                break;
            }
        }

        return bare;
    }

    // The kinds that only show words (a message, a field): never a result or an item a person clicks to get somewhere.
    private static readonly HashSet<string> WordsOnlyKinds = new(StringComparer.Ordinal) { "Text", "Edit", "ComboBox", "Document" };

    /// <summary>
    /// A verified click that echoes a query typed before it. A control that only shows words and holds the query inside
    /// a longer text («No hay resultados para «sistema»», «Resultados de sistema») is the window repeating it, whatever
    /// the receipt. Any other control whose name, without its quotes, is or holds the query echoes it only when nothing
    /// tells it did something (falsos éxitos v3 M2, v3-11: the label typed into «Búsqueda de Microsoft» and its own
    /// suggestion pressed, «surfaceChanged:false, absentOrDisabled:true»): its receipt saw no surface change, no switch
    /// toggled, nothing selected, and the look after it showed no control the look before it lacked («broughtNew»,
    /// <see cref="NoteWhatTheClickBrought"/>). UI Automation's receipt never says surfaceChanged when its postread holds
    /// (DesktopUiaWorker Click-Result), so a result that navigates («Sistema» pressed in Settings' search, «Cuphead» in
    /// a store's results) is told apart by the look after it. A click no look followed yet is
    /// <paramref name="undecidedEchoes"/>: a receipt alone cannot tell (the check waits for the look).
    /// </summary>
    internal static bool ClickEchoesQuery(JsonObject click, IReadOnlyList<string> queries, bool undecidedEchoes = false)
    {
        if (queries.Count == 0)
        {
            return false;
        }

        string name = Fold((string?)click["name"] ?? (string?)click["label"]);
        string bare = name.Trim(QuoteMarks);
        if (bare.Length == 0)
        {
            return false;
        }

        // Ronda 24b (banco r23 s04): a tab whose title holds the query in a longer text («descargas - Este equipo», the
        // tab of the search typed) is the window repeating it too, even when the press left it selected.
        if ((string?)click["kind"] is { } kind && (WordsOnlyKinds.Contains(kind) || kind == "TabItem")
            && queries.Any(query => bare != query && name.Contains(query, StringComparison.Ordinal)))
        {
            return true;
        }

        if ((bool?)click["surfaceChanged"] == true || (bool?)click["toggled"] == true || (bool?)click["selected"] == true
            || !queries.Any(query => bare.Contains(query, StringComparison.Ordinal)))
        {
            return false;
        }

        return (bool?)click["broughtNew"] is { } brought ? !brought : undecidedEchoes;
    }

    /// <summary>
    /// On a look after the mission's last step, when that step is a verified click: whether this look shows a control
    /// (or, on a window drawn without an accessible tree, a written line) the look right before the click did not. Kept
    /// on the click as «broughtNew»; once true it stays (a page drawn late). A click with no look kept before it is left
    /// undecided.
    /// </summary>
    internal static void NoteWhatTheClickBrought(JsonObject view, JsonArray steps)
    {
        if (steps.Count == 0 || steps[^1] is not JsonObject click || (bool?)click["ok"] != true
            || (string?)click["operation"] != "input.visible.click" || (bool?)click["broughtNew"] == true)
        {
            return;
        }

        string key = ((int?)click["step"] ?? steps.Count).ToString(CultureInfo.InvariantCulture);
        if (view["controlsBeforeClick"]?[key] is not JsonArray before)
        {
            return;
        }

        var named = new HashSet<string>(before.Select(node => (string?)node ?? string.Empty), StringComparer.Ordinal);
        JsonArray now = ControlNames(view);
        bool brought = now.Any(node => !named.Contains((string?)node ?? string.Empty));
        if (!brought && now.Count <= 1)
        {
            // No accessible tree: the written text tells, when it was kept before the click.
            if (view["textBeforeClick"]?[key] is not JsonArray written || written.Count == 0)
            {
                return;
            }

            var lines = new HashSet<string>(written.Select(node => Fold((string?)node)), StringComparer.Ordinal);
            brought = TextLines(view).Any(line => !lines.Contains(Fold((string?)line)));
        }

        click["broughtNew"] = brought;
    }

    /// <summary>
    /// What was typed into a search, an address bar or a field with no name before <paramref name="click"/>: three
    /// letters at least (a shorter text is in too many names to be its echo).
    /// </summary>
    internal static List<string> QueriesBefore(IEnumerable<JsonNode?> steps, JsonObject click)
    {
        var queries = new List<string>();
        foreach (JsonObject step in steps.OfType<JsonObject>())
        {
            if (ReferenceEquals(step, click))
            {
                break;
            }

            if ((bool?)step["ok"] == true && (string?)step["operation"] == "input.text.type" && EchoesItsQuery(step)
                && Fold((string?)step["text"]).Trim(QuoteMarks) is { Length: >= MinimumQuery } query)
            {
                queries.Add(query);
            }
        }

        return queries;
    }

    // The shortest typed query whose repetition in a clicked name counts as its echo.
    private const int MinimumQuery = 3;
}
